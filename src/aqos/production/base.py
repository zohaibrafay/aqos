"""
AQOS production base primitives.

This module contains dependency-free production hardening building blocks used
by readiness checks, release gates, deployment manifests, runtime config
validation, and production integration helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Callable


class ProductionStatus(str, Enum):
    """Supported production statuses."""

    READY = "ready"
    WARNING = "warning"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ProductionSeverity(str, Enum):
    """Supported production severities."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class ProductionCheckResult:
    """Result of a production check."""

    name: str
    status: ProductionStatus | str
    severity: ProductionSeverity | str = ProductionSeverity.INFO
    passed: bool = True
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Check name")
        normalize_production_status(self.status)
        normalize_production_severity(self.severity)

        if not isinstance(self.passed, bool):
            raise ValueError("Passed must be a boolean.")

        validate_string(self.message, "Message")
        validate_details(self.details)
        validate_non_empty_string(self.timestamp, "Timestamp")

    @property
    def failed(self) -> bool:
        """Return whether check failed."""
        return not self.passed

    @property
    def blocking(self) -> bool:
        """Return whether result blocks production release."""
        return normalize_production_status(self.status) == ProductionStatus.BLOCKED

    def to_dict(self) -> dict[str, Any]:
        """Convert check result into dictionary."""
        return {
            "name": self.name.strip(),
            "status": normalize_production_status(self.status).value,
            "severity": normalize_production_severity(self.severity).value,
            "passed": self.passed,
            "failed": self.failed,
            "blocking": self.blocking,
            "message": self.message.strip(),
            "details": dict(self.details),
            "timestamp": self.timestamp.strip(),
        }


@dataclass(frozen=True)
class ProductionGateResult:
    """Aggregated production gate result."""

    gate_name: str
    status: ProductionStatus | str
    checks: list[ProductionCheckResult] = field(default_factory=list)
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.gate_name, "Gate name")
        normalize_production_status(self.status)
        validate_check_results(self.checks)
        validate_string(self.message, "Message")
        validate_details(self.metadata)
        validate_non_empty_string(self.timestamp, "Timestamp")

    @property
    def passed(self) -> bool:
        """Return whether gate passed."""
        return normalize_production_status(self.status) == ProductionStatus.READY

    @property
    def failed(self) -> bool:
        """Return whether gate failed."""
        return not self.passed

    @property
    def blocking_checks(self) -> list[ProductionCheckResult]:
        """Return blocking checks."""
        return [
            check
            for check in self.checks
            if check.blocking
        ]

    @property
    def warning_checks(self) -> list[ProductionCheckResult]:
        """Return warning checks."""
        return [
            check
            for check in self.checks
            if normalize_production_status(check.status) == ProductionStatus.WARNING
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert gate result into dictionary."""
        return {
            "gate_name": self.gate_name.strip(),
            "status": normalize_production_status(self.status).value,
            "passed": self.passed,
            "failed": self.failed,
            "message": self.message.strip(),
            "checks": [
                check.to_dict()
                for check in self.checks
            ],
            "blocking_checks": len(self.blocking_checks),
            "warning_checks": len(self.warning_checks),
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp.strip(),
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


def validate_boolean(value: bool, field_name: str) -> bool:
    """Validate boolean value."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def validate_details(details: dict[str, Any]) -> dict[str, Any]:
    """Validate details dictionary."""
    if not isinstance(details, dict):
        raise ValueError("Details must be a dictionary.")

    return details


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def validate_non_negative_float(value: float | int, field_name: str) -> float:
    """Validate non-negative number."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return float(value)


def validate_percentage(value: float | int, field_name: str) -> float:
    """Validate percentage value from 0 to 100."""
    percentage = validate_non_negative_float(value, field_name)

    if percentage > 100:
        raise ValueError(f"{field_name} must be between 0 and 100.")

    return percentage


def validate_check_results(
    checks: list[ProductionCheckResult],
) -> list[ProductionCheckResult]:
    """Validate production check result list."""
    if not isinstance(checks, list):
        raise ValueError("Checks must be a list.")

    for check in checks:
        if not isinstance(check, ProductionCheckResult):
            raise ValueError("Checks must contain ProductionCheckResult objects.")

    return checks


def normalize_production_status(status: ProductionStatus | str) -> ProductionStatus:
    """Normalize production status."""
    if isinstance(status, ProductionStatus):
        return status

    normalized = validate_non_empty_string(status, "Production status").lower()

    try:
        return ProductionStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductionStatus)
        raise ValueError(
            f"Invalid production status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_production_severity(
    severity: ProductionSeverity | str,
) -> ProductionSeverity:
    """Normalize production severity."""
    if isinstance(severity, ProductionSeverity):
        return severity

    normalized = validate_non_empty_string(severity, "Production severity").lower()

    try:
        return ProductionSeverity(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductionSeverity)
        raise ValueError(
            f"Invalid production severity '{severity}'. Valid severities: {valid}.",
        ) from exc


def build_production_check_result(
    *,
    name: str,
    status: ProductionStatus | str,
    severity: ProductionSeverity | str = ProductionSeverity.INFO,
    passed: bool = True,
    message: str = "",
    details: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> ProductionCheckResult:
    """Build production check result."""
    result_kwargs: dict[str, Any] = {
        "name": name,
        "status": status,
        "severity": severity,
        "passed": passed,
        "message": message,
        "details": details or {},
    }

    if timestamp is not None:
        result_kwargs["timestamp"] = timestamp

    return ProductionCheckResult(**result_kwargs)


def build_production_gate_result(
    *,
    gate_name: str,
    status: ProductionStatus | str,
    checks: list[ProductionCheckResult] | None = None,
    message: str = "",
    metadata: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> ProductionGateResult:
    """Build production gate result."""
    result_kwargs: dict[str, Any] = {
        "gate_name": gate_name,
        "status": status,
        "checks": checks or [],
        "message": message,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        result_kwargs["timestamp"] = timestamp

    return ProductionGateResult(**result_kwargs)


def aggregate_production_status(
    checks: list[ProductionCheckResult],
) -> ProductionStatus:
    """Aggregate production status from checks."""
    validate_check_results(checks)

    if not checks:
        return ProductionStatus.UNKNOWN

    if any(check.blocking for check in checks):
        return ProductionStatus.BLOCKED

    if any(
        normalize_production_status(check.status) == ProductionStatus.WARNING
        for check in checks
    ):
        return ProductionStatus.WARNING

    if all(
        normalize_production_status(check.status) == ProductionStatus.READY
        and check.passed
        for check in checks
    ):
        return ProductionStatus.READY

    return ProductionStatus.UNKNOWN


def safe_production_check(
    check: Callable[[], ProductionCheckResult],
    *,
    name: str,
) -> ProductionCheckResult:
    """Run production check safely."""
    if not callable(check):
        raise ValueError("Check must be callable.")

    validate_non_empty_string(name, "Check name")

    try:
        result = check()

        if not isinstance(result, ProductionCheckResult):
            raise ValueError("Check must return ProductionCheckResult.")

        return result
    except Exception as exc:  # noqa: BLE001
        return build_production_check_result(
            name=name,
            status=ProductionStatus.BLOCKED,
            severity=ProductionSeverity.ERROR,
            passed=False,
            message="Production check failed.",
            details={
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            },
        )