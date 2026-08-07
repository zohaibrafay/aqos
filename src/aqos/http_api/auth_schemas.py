from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aqos.users.models import UserProfile, UserSession


AQOS_HTTP_AUTH_SCHEMAS_VERSION = "1.0"

#: Bounds on credentials accepted at the edge.
#:
#: The password policy itself lives in ``aqos.users.passwords``; these only stop
#: absurd input from reaching it, and the maximum guards against a very long
#: string being fed into the key derivation function.
MIN_PASSWORD_LENGTH = 1
MAX_PASSWORD_LENGTH = 512
MAX_EMAIL_LENGTH = 320
MAX_CLIENT_LABEL_LENGTH = 191


class LoginRequest(BaseModel):
    """Credentials presented at the login endpoint."""

    email: str = Field(min_length=3, max_length=MAX_EMAIL_LENGTH)
    password: str = Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
    )
    client_label: str | None = Field(
        default=None,
        max_length=MAX_CLIENT_LABEL_LENGTH,
    )

    def masked(self) -> dict[str, Any]:
        """
        A form of the request that is safe to log.

        The password is not included at all — not masked, not truncated — so it
        cannot reach a log file through this object.
        """

        return {
            "email": self.email,
            "client_label": self.client_label,
        }


class UserResponse(BaseModel):
    """
    A user as the API describes them.

    Built by an explicit allow list rather than from the model's own
    ``to_dict``: a field added to the ORM later must not appear on the wire just
    because it exists.
    """

    user_id: str
    email: str
    display_name: str
    role: str
    status: str
    timezone: str | None = None
    locale: str | None = None
    is_active: bool = False

    @classmethod
    def from_profile(cls, profile: UserProfile) -> "UserResponse":
        return cls(
            user_id=profile.user_id,
            email=profile.email,
            display_name=profile.display_name,
            role=profile.role.value,
            status=profile.status.value,
            timezone=profile.timezone,
            locale=profile.locale,
            is_active=profile.is_active,
        )


class SessionResponse(BaseModel):
    """
    A session as the API describes it.

    Carries no token and no token hash: the raw token is shown once at login,
    and the hash is a stored secret that no endpoint has a reason to reveal.
    """

    session_id: str
    user_id: str
    created_at_utc: datetime
    expires_at_utc: datetime
    last_seen_at_utc: datetime | None = None
    client_label: str | None = None
    is_active: bool = False

    @classmethod
    def from_session(cls, user_session: UserSession) -> "SessionResponse":
        return cls(
            session_id=user_session.session_id,
            user_id=user_session.user_id,
            created_at_utc=user_session.created_at_utc,
            expires_at_utc=user_session.expires_at_utc,
            last_seen_at_utc=user_session.last_seen_at_utc,
            client_label=user_session.client_label,
            is_active=user_session.is_active(),
        )


class LoginResponse(BaseModel):
    """
    The one and only time a raw session token is returned.

    Only the hash is stored, so a token that is lost here cannot be recovered
    from the database; the caller has to log in again.
    """

    token: str
    token_type: str = "bearer"
    expires_at_utc: datetime
    user: UserResponse
    session: SessionResponse


class LogoutResponse(BaseModel):
    revoked: bool
    session_id: str | None = None


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


__all__ = [
    "AQOS_HTTP_AUTH_SCHEMAS_VERSION",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "MAX_CLIENT_LABEL_LENGTH",
    "MAX_EMAIL_LENGTH",
    "MAX_PASSWORD_LENGTH",
    "MIN_PASSWORD_LENGTH",
    "SessionListResponse",
    "SessionResponse",
    "UserResponse",
]
