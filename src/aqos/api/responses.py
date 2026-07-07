"""
AQOS API response envelope utilities.

This module provides framework-independent API response objects.
It does not depend on FastAPI, Flask, Django, or any HTTP framework.

The goal is to keep AQOS API responses consistent across future API,
CLI, dashboard, and service boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ApiStatus(str, Enum):
    """Supported API response statuses."""

    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True)
class ApiError:
    """
    Structured API error object.
    """

    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not self.code.strip():
            raise ValueError("API error code must be a non-empty string.")

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("API error message must be a non-empty string.")

        if self.field is not None and not isinstance(self.field, str):
            raise ValueError("API error field must be a string or None.")

        if not isinstance(self.details, dict):
            raise ValueError("API error details must be a dictionary.")

    def to_dict(self) -> dict[str, Any]:
        """Convert the API error into a serializable dictionary."""
        payload: dict[str, Any] = {
            "code": self.code.strip().upper(),
            "message": self.message.strip(),
        }

        if self.field:
            payload["field"] = self.field

        if self.details:
            payload["details"] = self.details

        return payload


@dataclass(frozen=True)
class ApiResponse:
    """
    Standard AQOS API response envelope.
    """

    success: bool
    message: str
    data: Any = None
    errors: list[ApiError] = dataclass_field(default_factory=list)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("API response success must be a boolean.")

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("API response message must be a non-empty string.")

        if not isinstance(self.errors, list):
            raise ValueError("API response errors must be a list.")

        for error in self.errors:
            if not isinstance(error, ApiError):
                raise ValueError("API response errors must contain ApiError objects.")

        if not isinstance(self.metadata, dict):
            raise ValueError("API response metadata must be a dictionary.")

    @property
    def status(self) -> ApiStatus:
        """Return the response status."""
        return ApiStatus.SUCCESS if self.success else ApiStatus.ERROR

    def to_dict(self) -> dict[str, Any]:
        """Convert the response envelope into a serializable dictionary."""
        return {
            "success": self.success,
            "status": self.status.value,
            "message": self.message.strip(),
            "data": self.data,
            "errors": [error.to_dict() for error in self.errors],
            "metadata": self.metadata,
        }


def utc_timestamp() -> str:
    """Return the current UTC timestamp in ISO-8601 format."""
    return datetime.now(UTC).isoformat()


def build_api_metadata(
    *,
    request_id: str | None = None,
    source: str = "aqos-api",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build standard API metadata."""
    metadata: dict[str, Any] = {
        "source": source,
        "timestamp": utc_timestamp(),
    }

    if request_id:
        metadata["request_id"] = request_id

    if extra:
        metadata.update(extra)

    return metadata


def api_success(
    *,
    message: str = "Request completed successfully.",
    data: Any = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Create a successful API response."""
    response_metadata = build_api_metadata(request_id=request_id)

    if metadata:
        response_metadata.update(metadata)

    return ApiResponse(
        success=True,
        message=message,
        data=data,
        errors=[],
        metadata=response_metadata,
    )


def api_error(
    *,
    code: str,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> ApiError:
    """Create an API error object."""
    return ApiError(
        code=code,
        message=message,
        field=field,
        details=details or {},
    )


def api_failure(
    *,
    message: str = "Request failed.",
    errors: list[ApiError] | None = None,
    data: Any = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Create a failed API response."""
    response_metadata = build_api_metadata(request_id=request_id)

    if metadata:
        response_metadata.update(metadata)

    return ApiResponse(
        success=False,
        message=message,
        data=data,
        errors=errors or [],
        metadata=response_metadata,
    )


def validation_failure(
    *,
    message: str = "Validation failed.",
    field: str,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Create a validation failure response."""
    return api_failure(
        message=message,
        errors=[
            api_error(
                code="VALIDATION_ERROR",
                message=message,
                field=field,
                details=details,
            )
        ],
        request_id=request_id,
    )


def not_found_failure(
    *,
    resource: str,
    identifier: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Create a not-found failure response."""
    return api_failure(
        message=f"{resource} was not found.",
        errors=[
            api_error(
                code="NOT_FOUND",
                message=f"{resource} with identifier '{identifier}' was not found.",
                field="identifier",
                details={
                    "resource": resource,
                    "identifier": identifier,
                },
            )
        ],
        request_id=request_id,
    )


def exception_failure(
    exception: Exception,
    *,
    message: str = "Unexpected API error.",
    request_id: str | None = None,
) -> ApiResponse:
    """Create a failure response from an exception."""
    return api_failure(
        message=message,
        errors=[
            api_error(
                code=exception.__class__.__name__,
                message=str(exception),
                details={
                    "exception_type": exception.__class__.__name__,
                },
            )
        ],
        request_id=request_id,
    )