"""
AQOS reliability base primitives.

This module contains dependency-free reliability building blocks used by retry
policies, circuit breakers, rate limiters, deadlines, supervisors, and runtime
resilience helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable


class ReliabilityStatus(str, Enum):
    """Supported reliability statuses."""

    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


class ReliabilitySeverity(str, Enum):
    """Supported reliability event severities."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ReliabilityEvent:
    """Single reliability event."""

    name: str
    component: str
    status: ReliabilityStatus | str = ReliabilityStatus.OK
    severity: ReliabilitySeverity | str = ReliabilitySeverity.INFO
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Event name")
        validate_non_empty_string(self.component, "Component")
        normalize_reliability_status(self.status)
        normalize_reliability_severity(self.severity)
        validate_string(self.message, "Message")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_attributes(self.attributes)

    def to_dict(self) -> dict[str, Any]:
        """Convert reliability event into a serializable dictionary."""
        return {
            "name": self.name.strip(),
            "component": self.component.strip(),
            "status": normalize_reliability_status(self.status).value,
            "severity": normalize_reliability_severity(self.severity).value,
            "message": self.message.strip(),
            "timestamp": self.timestamp.strip(),
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class ReliabilityResult:
    """Result of a reliability-protected operation."""

    success: bool
    operation: str
    component: str
    status: ReliabilityStatus | str = ReliabilityStatus.OK
    message: str = ""
    value: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")
        normalize_reliability_status(self.status)
        validate_string(self.message, "Message")
        validate_attributes(self.metadata)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

    @property
    def failed(self) -> bool:
        """Return whether operation failed."""
        return not self.success

    def to_event(self) -> ReliabilityEvent:
        """Convert result into a reliability event."""
        severity = ReliabilitySeverity.INFO if self.success else ReliabilitySeverity.ERROR

        return build_reliability_event(
            name=self.operation,
            component=self.component,
            status=self.status,
            severity=severity,
            message=self.message or self.error or "",
            attributes={
                "success": self.success,
                "error": self.error,
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert reliability result into a serializable dictionary."""
        payload = {
            "success": self.success,
            "failed": self.failed,
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "status": normalize_reliability_status(self.status).value,
            "message": self.message.strip(),
            "value": self.value,
            "error": self.error.strip() if self.error else None,
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


def validate_string(value: str, field_name: str) -> str:
    """Validate a string value."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    return value


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string value."""
    validate_string(value, field_name)

    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Validate attributes dictionary."""
    if not isinstance(attributes, dict):
        raise ValueError("Attributes must be a dictionary.")

    return attributes


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate a positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate a non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_non_negative_float(value: float | int, field_name: str) -> float:
    """Validate a non-negative number."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return float(value)


def normalize_reliability_status(
    status: ReliabilityStatus | str,
) -> ReliabilityStatus:
    """Normalize reliability status."""
    if isinstance(status, ReliabilityStatus):
        return status

    normalized = validate_non_empty_string(status, "Reliability status").lower()

    try:
        return ReliabilityStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ReliabilityStatus)
        raise ValueError(
            f"Invalid reliability status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_reliability_severity(
    severity: ReliabilitySeverity | str,
) -> ReliabilitySeverity:
    """Normalize reliability severity."""
    if isinstance(severity, ReliabilitySeverity):
        return severity

    normalized = validate_non_empty_string(severity, "Reliability severity").lower()

    try:
        return ReliabilitySeverity(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ReliabilitySeverity)
        raise ValueError(
            f"Invalid reliability severity '{severity}'. Valid severities: {valid}.",
        ) from exc


def build_reliability_event(
    *,
    name: str,
    component: str,
    status: ReliabilityStatus | str = ReliabilityStatus.OK,
    severity: ReliabilitySeverity | str = ReliabilitySeverity.INFO,
    message: str = "",
    timestamp: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> ReliabilityEvent:
    """Build a reliability event."""
    event_kwargs: dict[str, Any] = {
        "name": name,
        "component": component,
        "status": status,
        "severity": severity,
        "message": message,
        "attributes": attributes or {},
    }

    if timestamp is not None:
        event_kwargs["timestamp"] = timestamp

    return ReliabilityEvent(**event_kwargs)


def build_reliability_result(
    *,
    success: bool,
    operation: str,
    component: str,
    status: ReliabilityStatus | str = ReliabilityStatus.OK,
    message: str = "",
    value: Any = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReliabilityResult:
    """Build reliability result."""
    return ReliabilityResult(
        success=success,
        operation=operation,
        component=component,
        status=status,
        message=message,
        value=value,
        error=error,
        metadata=metadata or {},
    )


def safe_execute(
    operation: Callable[[], Any],
    *,
    operation_name: str,
    component: str,
    metadata: dict[str, Any] | None = None,
) -> ReliabilityResult:
    """Execute callable and capture success/failure as a reliability result."""
    if not callable(operation):
        raise ValueError("Operation must be callable.")

    validate_non_empty_string(operation_name, "Operation name")
    validate_non_empty_string(component, "Component")
    if metadata is not None:
        validate_attributes(metadata)

    try:
        value = operation()

        return build_reliability_result(
            success=True,
            operation=operation_name,
            component=component,
            status=ReliabilityStatus.OK,
            message="Operation completed successfully.",
            value=value,
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        return build_reliability_result(
            success=False,
            operation=operation_name,
            component=component,
            status=ReliabilityStatus.FAILED,
            message="Operation failed.",
            error=str(exc),
            metadata={
                "error_type": exc.__class__.__name__,
                **(metadata or {}),
            },
        )