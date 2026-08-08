from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session
from starlette.requests import Request

from aqos.database.types import database_utc_now
from aqos.http_api.errors import ApiErrorCode, AqosApiError, NotFoundApiError
from aqos.users.models import UserProfile, UserSession, UserStatus
from aqos.users.repositories import (
    AuthenticationOutcome,
    UserCredentialRepository,
    UserProfileRepository,
    UserSessionRepository,
)


AQOS_HTTP_AUTH_VERSION = "1.0"

AUTHORIZATION_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "

#: What every failed login says, whatever actually went wrong.
#:
#: Distinguishing "no such account" from "wrong password" tells an attacker
#: which emails are registered, so both answer identically.
INVALID_CREDENTIALS_MESSAGE = "Email or password is incorrect."

#: Said only when the account itself is locked.
#:
#: This one is worth distinguishing: the user cannot fix it by retrying, and a
#: lockout is only reachable by someone who already knows the address.
ACCOUNT_LOCKED_MESSAGE = (
    "This account is temporarily locked after repeated failed attempts."
)

INACTIVE_ACCOUNT_MESSAGE = "This account is not active."
MISSING_TOKEN_MESSAGE = "Authentication is required."
INVALID_TOKEN_MESSAGE = "The session token is invalid or has expired."

#: Statuses that may hold a session.
ACTIVE_USER_STATUSES = (UserStatus.ACTIVE,)


class UnauthorizedApiError(AqosApiError):
    def __init__(self, message: str = MISSING_TOKEN_MESSAGE) -> None:
        super().__init__(ApiErrorCode.UNAUTHORIZED, message)


class ForbiddenApiError(AqosApiError):
    def __init__(self, message: str = INACTIVE_ACCOUNT_MESSAGE) -> None:
        super().__init__(ApiErrorCode.FORBIDDEN, message)


@dataclass(frozen=True)
class AuthenticatedCaller:
    """The user and session behind an authenticated request."""

    user: UserProfile
    session: UserSession

    @property
    def user_id(self) -> str:
        return self.user.user_id

    @property
    def session_id(self) -> str:
        return self.session.session_id


def extract_bearer_token(request: Request) -> str | None:
    """
    Read the bearer token from the Authorization header.

    The scheme comparison is case insensitive because clients vary, but a
    malformed header yields nothing rather than a partial guess.
    """

    header = request.headers.get(AUTHORIZATION_HEADER)

    if not header:
        return None

    if not header.lower().startswith(BEARER_PREFIX.lower()):
        return None

    token = header[len(BEARER_PREFIX):].strip()

    return token or None


def login(
    session: Session,
    email: str,
    password: str,
    client_label: str | None = None,
    now_utc: datetime | None = None,
):
    """
    Verify credentials and issue a session.

    Every failure below a lockout returns the same message, so the endpoint
    cannot be used to discover which addresses are registered.
    """

    timestamp = now_utc or database_utc_now()

    try:
        profile = UserProfileRepository(session).find_by_email(email)
    except ValueError:
        # An address that is not an address cannot match a stored one, so this
        # is the same failure as an unknown user and is reported identically.
        # Letting the normalizer's error escape would answer with a 500, which
        # tells a caller their input never reached the credential check — and
        # logs a traceback for what is only ever bad input.
        profile = None

    if profile is None:
        # Still an explicit failure, worded exactly like a wrong password.
        raise UnauthorizedApiError(INVALID_CREDENTIALS_MESSAGE)

    result = UserCredentialRepository(session).authenticate(
        user_id=profile.user_id,
        password=password,
        now_utc=timestamp,
    )

    if not result.authenticated:
        # Every failed attempt mutates credential state — the attempt counter,
        # and on the attempt that trips the threshold the lockout deadline too.
        # Raising would roll all of it back with the transaction, leaving a
        # counter that resets on each failure and a lockout that never sticks.
        # This is committed before the failure is reported, whatever the reason.
        session.commit()

        if result.outcome == AuthenticationOutcome.LOCKED:
            raise AqosApiError(
                ApiErrorCode.FORBIDDEN,
                ACCOUNT_LOCKED_MESSAGE,
                details={
                    "locked_until_utc": (
                        result.locked_until_utc.isoformat()
                        if result.locked_until_utc
                        else None
                    )
                },
            )

        raise UnauthorizedApiError(INVALID_CREDENTIALS_MESSAGE)

    assert_user_may_hold_a_session(profile)

    issued = UserSessionRepository(session).create_session(
        user_id=profile.user_id,
        client_label=client_label,
        created_at_utc=timestamp,
    )

    return profile, issued


def assert_user_may_hold_a_session(profile: UserProfile) -> None:
    """
    A suspended or archived user must not get a session.

    Checked after the password so that the answer for a wrong password is the
    same whatever the account's status.
    """

    if profile.status not in ACTIVE_USER_STATUSES:
        raise ForbiddenApiError(INACTIVE_ACCOUNT_MESSAGE)


def resolve_caller(
    session: Session,
    token: str | None,
    now_utc: datetime | None = None,
    touch: bool = True,
) -> AuthenticatedCaller:
    """
    Turn a bearer token into the caller it represents.

    An expired or revoked session is refused the same way a nonexistent one is:
    the holder of a dead token learns only that it no longer works.
    """

    if not token:
        raise UnauthorizedApiError(MISSING_TOKEN_MESSAGE)

    sessions = UserSessionRepository(session)
    user_session = sessions.resolve_active_session(token, now_utc=now_utc)

    if user_session is None:
        raise UnauthorizedApiError(INVALID_TOKEN_MESSAGE)

    profile = UserProfileRepository(session).get(user_session.user_id)

    if profile is None:
        # The session outlived its user; treat it as dead rather than trusted.
        raise UnauthorizedApiError(INVALID_TOKEN_MESSAGE)

    assert_user_may_hold_a_session(profile)

    if touch:
        sessions.touch_session(
            user_session.session_id,
            seen_at_utc=now_utc or database_utc_now(),
        )

    return AuthenticatedCaller(user=profile, session=user_session)


def revoke_owned_session(
    session: Session,
    caller: "AuthenticatedCaller",
    session_id: str,
) -> bool:
    """
    Revoke one of the caller's own sessions.

    A session belonging to somebody else answers exactly like one that does not
    exist. Distinguishing them would let a caller probe for valid session ids
    across accounts, so ownership failure and absence share one answer.
    """

    sessions = UserSessionRepository(session)
    record = sessions.get(session_id)

    if record is None or record.user_id != caller.user_id:
        raise NotFoundApiError(
            "Session was not found.",
            details={"session_id": session_id},
        )

    return sessions.revoke_session(session_id)


def logout(session: Session, token: str | None) -> str | None:
    """
    Revoke the session behind a token.

    Returns the revoked session id, or None when the token matched nothing.
    Revoking an already dead token is not an error: the caller's intent is
    satisfied either way.
    """

    if not token:
        return None

    sessions = UserSessionRepository(session)
    user_session = sessions.find_by_token(token)

    if user_session is None:
        return None

    # Only report a revocation that actually happened; the repository refuses
    # to revoke twice, and saying otherwise would misreport an already dead
    # session as having just been ended.
    if not sessions.revoke_session(user_session.session_id):
        return None

    return user_session.session_id


__all__ = [
    "ACCOUNT_LOCKED_MESSAGE",
    "ACTIVE_USER_STATUSES",
    "AQOS_HTTP_AUTH_VERSION",
    "AUTHORIZATION_HEADER",
    "AuthenticatedCaller",
    "BEARER_PREFIX",
    "ForbiddenApiError",
    "INACTIVE_ACCOUNT_MESSAGE",
    "INVALID_CREDENTIALS_MESSAGE",
    "INVALID_TOKEN_MESSAGE",
    "MISSING_TOKEN_MESSAGE",
    "UnauthorizedApiError",
    "assert_user_may_hold_a_session",
    "extract_bearer_token",
    "login",
    "logout",
    "resolve_caller",
    "revoke_owned_session",
]
