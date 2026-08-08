from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.requests import Request

from aqos.http_api.auth import (
    AuthenticatedCaller,
    extract_bearer_token,
    login,
    logout,
    resolve_caller,
    revoke_owned_session,
)
from aqos.http_api.auth_schemas import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SessionListResponse,
    SessionResponse,
    UserResponse,
)
from aqos.http_api.dependencies import get_write_session
from aqos.http_api.responses import json_response
from aqos.users.repositories import UserSessionRepository


AQOS_HTTP_AUTH_ROUTES_VERSION = "1.0"

AUTH_PREFIX = "/auth"


def get_current_caller(
    request: Request,
    session: Session = Depends(get_write_session),
) -> AuthenticatedCaller:
    """
    The authenticated caller behind a request.

    A write session is used because resolving a caller advances the session's
    last-seen timestamp; that write has to commit or the record never moves.
    The read-only business endpoints deliberately do not use this: Sprint 058
    gave them ``get_read_only_caller`` so a burst of GETs cannot become a burst
    of UPDATEs. This is for requests that mean to write anyway — the session
    endpoints here, and the Sprint 059 signal actions, which share this one
    write session so the caller touch and the transition commit together.
    """

    return resolve_caller(session, extract_bearer_token(request))


def build_auth_router() -> APIRouter:
    router = APIRouter(prefix=AUTH_PREFIX, tags=["auth"])

    @router.post("/login")
    def post_login(
        payload: LoginRequest,
        session: Session = Depends(get_write_session),
    ):
        profile, issued = login(
            session=session,
            email=payload.email,
            password=payload.password,
            client_label=payload.client_label,
        )

        # The only place a raw token is ever returned. Only its hash is stored,
        # so a token lost here cannot be recovered from the database.
        body = LoginResponse(
            token=issued.token,
            expires_at_utc=issued.session.expires_at_utc,
            user=UserResponse.from_profile(profile),
            session=SessionResponse.from_session(issued.session),
        )

        return json_response(body.model_dump(mode="json"), status_code=201)

    @router.post("/logout")
    def post_logout(
        request: Request,
        session: Session = Depends(get_write_session),
    ):
        """
        Revoke the caller's current session.

        Deliberately not behind :func:`get_current_caller`: revoking an already
        dead token should succeed rather than fail on authentication, because
        the caller's intent is satisfied either way.
        """

        revoked_session_id = logout(session, extract_bearer_token(request))

        body = LogoutResponse(
            revoked=revoked_session_id is not None,
            session_id=revoked_session_id,
        )

        return json_response(body.model_dump(mode="json"))

    @router.get("/me")
    def get_me(caller: AuthenticatedCaller = Depends(get_current_caller)):
        return json_response(
            UserResponse.from_profile(caller.user).model_dump(mode="json")
        )

    @router.get("/sessions")
    def get_sessions(
        caller: AuthenticatedCaller = Depends(get_current_caller),
        session: Session = Depends(get_write_session),
    ):
        """
        The caller's own sessions.

        Scoped to the caller's user id, so one user can never enumerate
        another's devices.
        """

        records = UserSessionRepository(session).list_sessions(
            user_id=caller.user_id,
        )
        body = SessionListResponse(
            sessions=[
                SessionResponse.from_session(record) for record in records
            ],
            total=len(records),
        )

        return json_response(body.model_dump(mode="json"))

    @router.post("/sessions/{session_id}/revoke")
    def post_revoke_session(
        session_id: str,
        caller: AuthenticatedCaller = Depends(get_current_caller),
        session: Session = Depends(get_write_session),
    ):
        """
        Revoke one of the caller's own sessions.

        Someone else's session id answers as not found, so this cannot be used
        to probe which session ids exist on other accounts.
        """

        revoked = revoke_owned_session(session, caller, session_id)

        return json_response({"revoked": revoked, "session_id": session_id})

    @router.post("/logout-all")
    def post_logout_all(
        caller: AuthenticatedCaller = Depends(get_current_caller),
        session: Session = Depends(get_write_session),
    ):
        """Revoke every session this user holds, including the current one."""

        revoked = UserSessionRepository(session).revoke_user_sessions(
            user_id=caller.user_id,
        )

        return json_response({"revoked": revoked})

    return router


__all__ = [
    "AQOS_HTTP_AUTH_ROUTES_VERSION",
    "AUTH_PREFIX",
    "build_auth_router",
    "get_current_caller",
]
