from __future__ import annotations

from typing import Any

from fastapi import Depends
from sqlalchemy.orm import Session
from starlette.requests import Request

from aqos.http_api.auth import (
    AuthenticatedCaller,
    extract_bearer_token,
    resolve_caller,
)
from aqos.http_api.dependencies import get_session
from aqos.http_api.errors import ApiErrorCode, AqosApiError, NotFoundApiError


AQOS_HTTP_AUTHZ_VERSION = "1.0"

CROSS_USER_FILTER_MESSAGE = "You can only read your own data."

#: What a caller is told when a resource belongs to somebody else.
#:
#: Deliberately identical to a genuinely missing resource. Distinguishing them
#: would turn every detail endpoint into an existence oracle: a caller could
#: enumerate which ids are real on other accounts by comparing responses.
NOT_FOUND_MESSAGE_BY_RESOURCE = {
    "signal": "Signal was not found.",
    "account": "Account was not found.",
    "paper_session": "Paper session was not found.",
    "report": "Report was not found for this account.",
}

DEFAULT_NOT_FOUND_MESSAGE = "Resource was not found."


def get_read_only_caller(
    request: Request,
    session: Session = Depends(get_session),
) -> AuthenticatedCaller:
    """
    The authenticated caller, resolved without writing anything.

    Business endpoints are reads and must stay reads. Sprint 057's
    ``get_current_caller`` advances the session's last-seen timestamp, which
    would turn every protected GET into a write; here the lookup runs on a read
    session with the touch disabled, so a burst of reads cannot become a burst
    of UPDATEs.
    """

    return resolve_caller(
        session,
        extract_bearer_token(request),
        touch=False,
    )


def resolve_scoped_user_id(
    caller: AuthenticatedCaller,
    requested_user_id: str | None,
) -> str:
    """
    Decide whose data a list endpoint may read.

    Omitting the filter means "my own data". Asking for somebody else's is
    refused outright rather than quietly narrowed: silently returning an empty
    list would look like a real answer and would hide the attempt from the
    caller and from anyone reading the logs.
    """

    if requested_user_id is None or requested_user_id == caller.user_id:
        return caller.user_id

    raise AqosApiError(
        ApiErrorCode.FORBIDDEN,
        CROSS_USER_FILTER_MESSAGE,
        details={"requested_user_id": requested_user_id},
    )


def not_found_for(resource: str, resource_id: str) -> NotFoundApiError:
    return NotFoundApiError(
        NOT_FOUND_MESSAGE_BY_RESOURCE.get(resource, DEFAULT_NOT_FOUND_MESSAGE),
        details={f"{resource}_id": resource_id},
    )


def assert_owned_by_caller(
    caller: AuthenticatedCaller,
    owner_user_id: str | None,
    resource: str,
    resource_id: str,
) -> None:
    """
    Refuse a resource that belongs to somebody else.

    Answers exactly as if the resource did not exist, which is what keeps ids
    on other accounts from being discovered by comparing responses.
    """

    if owner_user_id == caller.user_id:
        return

    raise not_found_for(resource, resource_id)


def require_owned_record(
    caller: AuthenticatedCaller,
    record: Any,
    resource: str,
    resource_id: str,
    owner_attribute: str = "user_id",
) -> Any:
    """
    Load-or-refuse in one step.

    A missing record and one owned by another user produce the same answer,
    which is the property that stops ids being probed.
    """

    if record is None:
        raise not_found_for(resource, resource_id)

    assert_owned_by_caller(
        caller=caller,
        owner_user_id=getattr(record, owner_attribute, None),
        resource=resource,
        resource_id=resource_id,
    )

    return record


__all__ = [
    "AQOS_HTTP_AUTHZ_VERSION",
    "CROSS_USER_FILTER_MESSAGE",
    "DEFAULT_NOT_FOUND_MESSAGE",
    "NOT_FOUND_MESSAGE_BY_RESOURCE",
    "assert_owned_by_caller",
    "get_read_only_caller",
    "not_found_for",
    "require_owned_record",
    "resolve_scoped_user_id",
]
