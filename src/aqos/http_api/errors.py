from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any


AQOS_API_ERRORS_VERSION = "1.0"


class ApiErrorCode(str, Enum):
    """Structured error codes the API may return."""

    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    RATE_LIMITED = "rate_limited"
    DATABASE_UNAVAILABLE = "database_unavailable"
    NOT_READY = "not_ready"
    INTERNAL_ERROR = "internal_error"


HTTP_STATUS_BY_ERROR_CODE: dict[ApiErrorCode, int] = {
    ApiErrorCode.VALIDATION_ERROR: 422,
    ApiErrorCode.NOT_FOUND: 404,
    ApiErrorCode.CONFLICT: 409,
    ApiErrorCode.UNAUTHORIZED: 401,
    ApiErrorCode.FORBIDDEN: 403,
    ApiErrorCode.RATE_LIMITED: 429,
    ApiErrorCode.DATABASE_UNAVAILABLE: 503,
    ApiErrorCode.NOT_READY: 503,
    ApiErrorCode.INTERNAL_ERROR: 500,
}

#: The message returned for any unhandled exception.
#:
#: Never the exception text: an unexpected error can carry a connection string,
#: a query fragment or a file path, none of which belongs in a response.
GENERIC_INTERNAL_MESSAGE = "An internal error occurred."


class AqosApiError(Exception):
    """
    An error the API knows how to represent.

    Anything raised as one of these is safe to show a caller. Everything else
    is reported with a generic message instead.
    """

    def __init__(
        self,
        code: ApiErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)

        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = status_code or status_for_error_code(code)


class ValidationApiError(AqosApiError):
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ApiErrorCode.VALIDATION_ERROR, message, details)


class NotFoundApiError(AqosApiError):
    def __init__(
        self,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ApiErrorCode.NOT_FOUND, message, details)


class DatabaseUnavailableApiError(AqosApiError):
    def __init__(
        self,
        message: str = "The database is not available.",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(ApiErrorCode.DATABASE_UNAVAILABLE, message, details)


def status_for_error_code(code: ApiErrorCode) -> int:
    """
    Map a code to an HTTP status.

    An unmapped code falls back to 500 rather than to something successful, so a
    new code can never accidentally read as a working response.
    """

    return HTTP_STATUS_BY_ERROR_CODE.get(code, 500)


@dataclass(frozen=True)
class ApiErrorBody:
    """The single error shape every AQOS API failure uses."""

    code: ApiErrorCode
    message: str
    request_id: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code.value,
                "message": self.message,
                "details": self.details,
                "request_id": self.request_id,
            }
        }


def build_error_payload(
    code: ApiErrorCode,
    message: str,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return ApiErrorBody(
        code=code,
        message=message,
        request_id=request_id,
        details=details or {},
    ).to_dict()


def build_internal_error_payload(
    request_id: str | None = None,
) -> dict[str, Any]:
    """
    The payload for an unexpected failure.

    Deliberately carries no details: the request id is how an operator ties the
    response back to the logged exception.
    """

    return build_error_payload(
        code=ApiErrorCode.INTERNAL_ERROR,
        message=GENERIC_INTERNAL_MESSAGE,
        request_id=request_id,
    )


__all__ = [
    "AQOS_API_ERRORS_VERSION",
    "ApiErrorBody",
    "ApiErrorCode",
    "AqosApiError",
    "DatabaseUnavailableApiError",
    "GENERIC_INTERNAL_MESSAGE",
    "HTTP_STATUS_BY_ERROR_CODE",
    "NotFoundApiError",
    "ValidationApiError",
    "build_error_payload",
    "build_internal_error_payload",
    "status_for_error_code",
]
