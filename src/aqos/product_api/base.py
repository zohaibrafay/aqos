"""
AQOS product API base primitives.

This module contains dependency-free product-facing API primitives used by
signals, portfolios, research, analytics, and product workflow endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ProductApiStatus(str, Enum):
    """Supported product API response statuses."""

    SUCCESS = "success"
    FAILURE = "failure"
    ERROR = "error"


class ProductApiErrorCode(str, Enum):
    """Supported product API error codes."""

    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    CONFLICT = "conflict"
    RATE_LIMITED = "rate_limited"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class ProductApiError:
    """Product API error payload."""

    code: ProductApiErrorCode | str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_product_api_error_code(self.code)
        validate_non_empty_string(self.message, "Error message")
        validate_metadata(self.details, "Error details")

    def to_dict(self) -> dict[str, Any]:
        """Convert error into dictionary."""
        return {
            "code": normalize_product_api_error_code(self.code).value,
            "message": self.message.strip(),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ProductApiMeta:
    """Product API metadata payload."""

    request_id: str
    api_version: str = "v1"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    source: str = "aqos-product-api"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.request_id, "Request ID")
        validate_non_empty_string(self.api_version, "API version")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_non_empty_string(self.source, "Source")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert meta into dictionary."""
        return {
            "request_id": self.request_id.strip(),
            "api_version": self.api_version.strip(),
            "timestamp": self.timestamp.strip(),
            "source": self.source.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductApiResponse:
    """Standard product API response envelope."""

    status: ProductApiStatus | str
    data: dict[str, Any] = field(default_factory=dict)
    message: str = ""
    error: ProductApiError | None = None
    meta: ProductApiMeta | None = None

    def __post_init__(self) -> None:
        normalize_product_api_status(self.status)
        validate_metadata(self.data, "Data")
        validate_string(self.message, "Message")

        if self.error is not None and not isinstance(self.error, ProductApiError):
            raise ValueError("Error must be a ProductApiError.")

        if self.meta is not None and not isinstance(self.meta, ProductApiMeta):
            raise ValueError("Meta must be a ProductApiMeta.")

    @property
    def success(self) -> bool:
        """Return whether response is successful."""
        return normalize_product_api_status(self.status) == ProductApiStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """Return whether response failed."""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Convert response into dictionary."""
        return {
            "status": normalize_product_api_status(self.status).value,
            "success": self.success,
            "failed": self.failed,
            "message": self.message.strip(),
            "data": dict(self.data),
            "error": self.error.to_dict() if self.error else None,
            "meta": self.meta.to_dict() if self.meta else None,
        }


@dataclass(frozen=True)
class ProductApiRequestContext:
    """Product API request context."""

    request_id: str
    user_id: str = ""
    tenant_id: str = ""
    role: str = "user"
    api_version: str = "v1"
    source: str = "aqos-product-api"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.request_id, "Request ID")
        validate_string(self.user_id, "User ID")
        validate_string(self.tenant_id, "Tenant ID")
        validate_non_empty_string(self.role, "Role")
        validate_non_empty_string(self.api_version, "API version")
        validate_non_empty_string(self.source, "Source")
        validate_metadata(self.metadata, "Metadata")

    def to_meta(self) -> ProductApiMeta:
        """Convert context into product API meta."""
        return build_product_api_meta(
            request_id=self.request_id,
            api_version=self.api_version,
            source=self.source,
            metadata={
                "user_id": self.user_id.strip(),
                "tenant_id": self.tenant_id.strip(),
                "role": self.role.strip(),
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert context into dictionary."""
        return {
            "request_id": self.request_id.strip(),
            "user_id": self.user_id.strip(),
            "tenant_id": self.tenant_id.strip(),
            "role": self.role.strip(),
            "api_version": self.api_version.strip(),
            "source": self.source.strip(),
            "metadata": dict(self.metadata),
        }


def validate_string(value: str, field_name: str) -> str:
    """Validate string value."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    return value


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate non-empty string value."""
    validate_string(value, field_name)

    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_metadata(value: dict[str, Any], field_name: str = "Metadata") -> dict[str, Any]:
    """Validate metadata dictionary."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    return value


def validate_boolean(value: bool, field_name: str) -> bool:
    """Validate boolean value."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def validate_non_negative_float(value: float | int, field_name: str) -> float:
    """Validate non-negative number."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return float(value)


def validate_percentage(value: float | int, field_name: str) -> float:
    """Validate percentage from 0 to 100."""
    percentage = validate_non_negative_float(value, field_name)

    if percentage > 100:
        raise ValueError(f"{field_name} must be between 0 and 100.")

    return percentage


def validate_product_symbol(symbol: str) -> str:
    """Validate product-facing trading symbol."""
    normalized = validate_non_empty_string(symbol, "Symbol").upper()

    if not normalized.replace("/", "").replace("-", "").isalnum():
        raise ValueError("Symbol must be alphanumeric and may include '/' or '-'.")

    return normalized


def validate_product_timeframe(timeframe: str) -> str:
    """Validate product-facing timeframe."""
    normalized = validate_non_empty_string(timeframe, "Timeframe").upper()

    valid_timeframes = {
        "M1",
        "M5",
        "M15",
        "M30",
        "H1",
        "H4",
        "D1",
        "W1",
    }

    if normalized not in valid_timeframes:
        raise ValueError(
            "Timeframe must be one of: D1, H1, H4, M1, M5, M15, M30, W1.",
        )

    return normalized


def normalize_product_api_status(status: ProductApiStatus | str) -> ProductApiStatus:
    """Normalize product API status."""
    if isinstance(status, ProductApiStatus):
        return status

    normalized = validate_non_empty_string(status, "Product API status").lower()

    try:
        return ProductApiStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductApiStatus)
        raise ValueError(
            f"Invalid product API status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_product_api_error_code(
    code: ProductApiErrorCode | str,
) -> ProductApiErrorCode:
    """Normalize product API error code."""
    if isinstance(code, ProductApiErrorCode):
        return code

    normalized = validate_non_empty_string(code, "Product API error code").lower()

    try:
        return ProductApiErrorCode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductApiErrorCode)
        raise ValueError(
            f"Invalid product API error code '{code}'. Valid error codes: {valid}.",
        ) from exc


def build_product_api_error(
    *,
    code: ProductApiErrorCode | str,
    message: str,
    details: dict[str, Any] | None = None,
) -> ProductApiError:
    """Build product API error."""
    return ProductApiError(
        code=code,
        message=message,
        details=details or {},
    )


def build_product_api_meta(
    *,
    request_id: str,
    api_version: str = "v1",
    timestamp: str | None = None,
    source: str = "aqos-product-api",
    metadata: dict[str, Any] | None = None,
) -> ProductApiMeta:
    """Build product API meta."""
    meta_kwargs: dict[str, Any] = {
        "request_id": request_id,
        "api_version": api_version,
        "source": source,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        meta_kwargs["timestamp"] = timestamp

    return ProductApiMeta(**meta_kwargs)


def build_product_api_context(
    *,
    request_id: str,
    user_id: str = "",
    tenant_id: str = "",
    role: str = "user",
    api_version: str = "v1",
    source: str = "aqos-product-api",
    metadata: dict[str, Any] | None = None,
) -> ProductApiRequestContext:
    """Build product API request context."""
    return ProductApiRequestContext(
        request_id=request_id,
        user_id=user_id,
        tenant_id=tenant_id,
        role=role,
        api_version=api_version,
        source=source,
        metadata=metadata or {},
    )


def build_product_api_response(
    *,
    status: ProductApiStatus | str,
    data: dict[str, Any] | None = None,
    message: str = "",
    error: ProductApiError | None = None,
    meta: ProductApiMeta | None = None,
) -> ProductApiResponse:
    """Build product API response."""
    return ProductApiResponse(
        status=status,
        data=data or {},
        message=message,
        error=error,
        meta=meta,
    )


def product_api_success(
    *,
    data: dict[str, Any] | None = None,
    message: str = "",
    context: ProductApiRequestContext | None = None,
    meta: ProductApiMeta | None = None,
) -> ProductApiResponse:
    """Build successful product API response."""
    return build_product_api_response(
        status=ProductApiStatus.SUCCESS,
        data=data or {},
        message=message,
        meta=meta or context.to_meta() if context else meta,
    )


def product_api_failure(
    *,
    message: str,
    code: ProductApiErrorCode | str = ProductApiErrorCode.VALIDATION_ERROR,
    details: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    context: ProductApiRequestContext | None = None,
    meta: ProductApiMeta | None = None,
) -> ProductApiResponse:
    """Build failed product API response."""
    return build_product_api_response(
        status=ProductApiStatus.FAILURE,
        data=data or {},
        message=message,
        error=build_product_api_error(
            code=code,
            message=message,
            details=details or {},
        ),
        meta=meta or context.to_meta() if context else meta,
    )


def product_api_error(
    *,
    message: str,
    code: ProductApiErrorCode | str = ProductApiErrorCode.INTERNAL_ERROR,
    details: dict[str, Any] | None = None,
    context: ProductApiRequestContext | None = None,
    meta: ProductApiMeta | None = None,
) -> ProductApiResponse:
    """Build error product API response."""
    return build_product_api_response(
        status=ProductApiStatus.ERROR,
        data={},
        message=message,
        error=build_product_api_error(
            code=code,
            message=message,
            details=details or {},
        ),
        meta=meta or context.to_meta() if context else meta,
    )


def safe_product_api_call(
    operation,
    *,
    context: ProductApiRequestContext | None = None,
    operation_name: str = "product-api-operation",
) -> ProductApiResponse:
    """Run a product API operation safely."""
    if not callable(operation):
        raise ValueError("Operation must be callable.")

    validate_non_empty_string(operation_name, "Operation name")

    try:
        response = operation()

        if not isinstance(response, ProductApiResponse):
            raise ValueError("Operation must return ProductApiResponse.")

        return response
    except Exception as exc:  # noqa: BLE001
        return product_api_error(
            message="Product API operation failed.",
            details={
                "operation": operation_name.strip(),
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
            context=context,
        )