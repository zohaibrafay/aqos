"""
AQOS observability base primitives.

This module contains small, dependency-free building blocks used by the
observability subsystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ObservabilityStatus(str, Enum):
    """Generic observability status values."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class ObservabilitySeverity(str, Enum):
    """Generic observability severity values."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ObservabilityEvent:
    """
    Generic observability event.

    This event is intentionally small so metrics, logs, traces, alerts, and
    health snapshots can reuse it without coupling to a third-party library.
    """

    name: str
    component: str
    severity: ObservabilitySeverity | str = ObservabilitySeverity.INFO
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Event name")
        validate_non_empty_string(self.component, "Component")
        normalize_severity(self.severity)
        validate_string(self.message, "Message")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_attributes(self.attributes)

    def to_dict(self) -> dict[str, Any]:
        """Convert event into a serializable dictionary."""
        return {
            "name": self.name.strip(),
            "component": self.component.strip(),
            "severity": normalize_severity(self.severity).value,
            "message": self.message.strip(),
            "timestamp": self.timestamp.strip(),
            "attributes": dict(self.attributes),
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
    """Validate event attributes."""
    if not isinstance(attributes, dict):
        raise ValueError("Attributes must be a dictionary.")

    return attributes


def normalize_status(status: ObservabilityStatus | str) -> ObservabilityStatus:
    """Normalize observability status."""
    if isinstance(status, ObservabilityStatus):
        return status

    if not isinstance(status, str) or not status.strip():
        raise ValueError("Status must be a non-empty string.")

    normalized = status.strip().lower()

    try:
        return ObservabilityStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ObservabilityStatus)
        raise ValueError(f"Invalid status '{status}'. Valid statuses: {valid}.") from exc


def normalize_severity(severity: ObservabilitySeverity | str) -> ObservabilitySeverity:
    """Normalize observability severity."""
    if isinstance(severity, ObservabilitySeverity):
        return severity

    if not isinstance(severity, str) or not severity.strip():
        raise ValueError("Severity must be a non-empty string.")

    normalized = severity.strip().lower()

    try:
        return ObservabilitySeverity(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ObservabilitySeverity)
        raise ValueError(f"Invalid severity '{severity}'. Valid severities: {valid}.") from exc


def build_observability_event(
    *,
    name: str,
    component: str,
    severity: ObservabilitySeverity | str = ObservabilitySeverity.INFO,
    message: str = "",
    attributes: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> ObservabilityEvent:
    """Build an observability event."""
    event_kwargs: dict[str, Any] = {
        "name": name,
        "component": component,
        "severity": severity,
        "message": message,
        "attributes": attributes or {},
    }

    if timestamp is not None:
        event_kwargs["timestamp"] = timestamp

    return ObservabilityEvent(**event_kwargs)