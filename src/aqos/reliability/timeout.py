"""
AQOS timeout and deadline primitives.

This module provides dependency-free timeout configuration, deadline tracking,
deadline checks, and deterministic deadline-protected execution helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Callable

from aqos.reliability.base import (
    ReliabilityResult,
    ReliabilityStatus,
    build_reliability_result,
    validate_attributes,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_string,
)


class TimeoutState(str, Enum):
    """Supported timeout states."""

    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


@dataclass(frozen=True)
class TimeoutConfig:
    """Timeout configuration."""

    timeout_seconds: float = 30.0
    grace_seconds: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_timeout_seconds(self.timeout_seconds)
        validate_non_negative_float(self.grace_seconds, "Grace seconds")
        validate_attributes(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert timeout config into dictionary."""
        return {
            "timeout_seconds": float(self.timeout_seconds),
            "grace_seconds": float(self.grace_seconds),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DeadlineCheckResult:
    """Result of checking a deadline."""

    expired: bool
    operation: str
    component: str
    state: TimeoutState | str
    elapsed_seconds: float
    remaining_seconds: float
    deadline_at: str
    checked_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.expired, bool):
            raise ValueError("Expired must be a boolean.")

        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")
        normalize_timeout_state(self.state)
        validate_non_negative_float(self.elapsed_seconds, "Elapsed seconds")
        validate_non_negative_float(self.remaining_seconds, "Remaining seconds")
        validate_non_empty_string(self.deadline_at, "Deadline at")
        validate_non_empty_string(self.checked_at, "Checked at")
        validate_attributes(self.metadata)

    @property
    def active(self) -> bool:
        """Return whether deadline is active."""
        return normalize_timeout_state(self.state) == TimeoutState.ACTIVE

    def to_reliability_result(self) -> ReliabilityResult:
        """Convert check result into reliability result."""
        return build_reliability_result(
            success=not self.expired,
            operation=self.operation,
            component=self.component,
            status=ReliabilityStatus.OK if not self.expired else ReliabilityStatus.DEGRADED,
            message="Deadline is active."
            if not self.expired
            else "Deadline has expired.",
            error=None if not self.expired else "Operation deadline expired.",
            metadata=self.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert check result into dictionary."""
        return {
            "expired": self.expired,
            "active": self.active,
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "state": normalize_timeout_state(self.state).value,
            "elapsed_seconds": float(self.elapsed_seconds),
            "remaining_seconds": float(self.remaining_seconds),
            "deadline_at": self.deadline_at.strip(),
            "checked_at": self.checked_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass
class Deadline:
    """Mutable operation deadline."""

    operation: str
    component: str
    config: TimeoutConfig = field(default_factory=TimeoutConfig)
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    state: TimeoutState | str = TimeoutState.ACTIVE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")

        if not isinstance(self.config, TimeoutConfig):
            raise ValueError("Config must be a TimeoutConfig.")

        validate_non_empty_string(self.started_at, "Started at")
        self.state = normalize_timeout_state(self.state)
        validate_attributes(self.metadata)

    @property
    def active(self) -> bool:
        """Return whether deadline is active."""
        return self.state == TimeoutState.ACTIVE

    @property
    def expired(self) -> bool:
        """Return whether deadline state is expired."""
        return self.state == TimeoutState.EXPIRED

    @property
    def cancelled(self) -> bool:
        """Return whether deadline state is cancelled."""
        return self.state == TimeoutState.CANCELLED

    @property
    def completed(self) -> bool:
        """Return whether deadline state is completed."""
        return self.state == TimeoutState.COMPLETED

    def deadline_at(self) -> str:
        """Return deadline timestamp without grace period."""
        return calculate_deadline_at(
            self.started_at,
            self.config.timeout_seconds,
        )

    def expires_at(self) -> str:
        """Return deadline timestamp including grace period."""
        return calculate_deadline_at(
            self.started_at,
            self.config.timeout_seconds + self.config.grace_seconds,
        )

    def elapsed_seconds(self, now: str | None = None) -> float:
        """Return elapsed seconds."""
        return calculate_elapsed_seconds(
            self.started_at,
            now=now,
        )

    def remaining_seconds(self, now: str | None = None) -> float:
        """Return remaining seconds including grace period."""
        return calculate_remaining_seconds(
            self.started_at,
            self.config.timeout_seconds + self.config.grace_seconds,
            now=now,
        )

    def check(self, now: str | None = None) -> DeadlineCheckResult:
        """Check deadline state."""
        checked_at = parse_timeout_datetime(now).isoformat() if now is not None else datetime.now(UTC).isoformat()

        if self.active and is_deadline_expired(
            self.started_at,
            self.config.timeout_seconds,
            grace_seconds=self.config.grace_seconds,
            now=checked_at,
        ):
            self.state = TimeoutState.EXPIRED

        return build_deadline_check_result(
            expired=self.expired,
            operation=self.operation,
            component=self.component,
            state=self.state,
            elapsed_seconds=self.elapsed_seconds(now=checked_at),
            remaining_seconds=self.remaining_seconds(now=checked_at),
            deadline_at=self.deadline_at(),
            checked_at=checked_at,
            metadata={
                "expires_at": self.expires_at(),
                **self.metadata,
            },
        )

    def complete(self) -> None:
        """Mark deadline as completed."""
        self.state = TimeoutState.COMPLETED

    def cancel(self) -> None:
        """Mark deadline as cancelled."""
        self.state = TimeoutState.CANCELLED

    def reset(self, started_at: str | None = None) -> None:
        """Reset deadline to active state."""
        self.started_at = started_at or datetime.now(UTC).isoformat()
        validate_non_empty_string(self.started_at, "Started at")
        self.state = TimeoutState.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Convert deadline into dictionary."""
        return {
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "config": self.config.to_dict(),
            "started_at": self.started_at.strip(),
            "deadline_at": self.deadline_at(),
            "expires_at": self.expires_at(),
            "state": normalize_timeout_state(self.state).value,
            "active": self.active,
            "expired": self.expired,
            "cancelled": self.cancelled,
            "completed": self.completed,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TimeoutExecutionResult:
    """Result of deadline-protected execution."""

    success: bool
    operation: str
    component: str
    deadline_check: DeadlineCheckResult
    value: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")

        if not isinstance(self.deadline_check, DeadlineCheckResult):
            raise ValueError("Deadline check must be a DeadlineCheckResult.")

        validate_attributes(self.metadata)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

    @property
    def failed(self) -> bool:
        """Return whether execution failed."""
        return not self.success

    def to_reliability_result(self) -> ReliabilityResult:
        """Convert execution result into reliability result."""
        return build_reliability_result(
            success=self.success,
            operation=self.operation,
            component=self.component,
            status=ReliabilityStatus.OK if self.success else ReliabilityStatus.FAILED,
            message="Deadline operation completed successfully."
            if self.success
            else "Deadline operation failed.",
            value=self.value,
            error=self.error,
            metadata=self.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert timeout execution result into dictionary."""
        payload = {
            "success": self.success,
            "failed": self.failed,
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "deadline_check": self.deadline_check.to_dict(),
            "value": self.value,
            "error": self.error.strip() if self.error else None,
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


def normalize_timeout_state(state: TimeoutState | str) -> TimeoutState:
    """Normalize timeout state."""
    if isinstance(state, TimeoutState):
        return state

    normalized = validate_non_empty_string(state, "Timeout state").lower()

    try:
        return TimeoutState(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TimeoutState)
        raise ValueError(
            f"Invalid timeout state '{state}'. Valid states: {valid}.",
        ) from exc


def validate_timeout_seconds(timeout_seconds: float | int) -> float:
    """Validate timeout seconds."""
    seconds = validate_non_negative_float(timeout_seconds, "Timeout seconds")

    if seconds <= 0:
        raise ValueError("Timeout seconds must be greater than zero.")

    return seconds


def parse_timeout_datetime(value: str) -> datetime:
    """Parse timeout datetime."""
    normalized = validate_non_empty_string(value, "Datetime")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed


def calculate_deadline_at(
    started_at: str,
    timeout_seconds: float | int,
) -> str:
    """Calculate deadline timestamp."""
    started = parse_timeout_datetime(started_at)
    seconds = validate_timeout_seconds(timeout_seconds)

    return (started + timedelta(seconds=seconds)).isoformat()


def calculate_elapsed_seconds(
    started_at: str,
    *,
    now: str | None = None,
) -> float:
    """Calculate elapsed seconds."""
    started = parse_timeout_datetime(started_at)
    current = parse_timeout_datetime(now) if now is not None else datetime.now(UTC)

    return max(
        (current - started).total_seconds(),
        0.0,
    )


def calculate_remaining_seconds(
    started_at: str,
    timeout_seconds: float | int,
    *,
    now: str | None = None,
) -> float:
    """Calculate remaining seconds."""
    deadline = parse_timeout_datetime(
        calculate_deadline_at(
            started_at,
            timeout_seconds,
        ),
    )
    current = parse_timeout_datetime(now) if now is not None else datetime.now(UTC)

    return max(
        (deadline - current).total_seconds(),
        0.0,
    )


def is_deadline_expired(
    started_at: str,
    timeout_seconds: float | int,
    *,
    grace_seconds: float | int = 0.0,
    now: str | None = None,
) -> bool:
    """Return whether deadline has expired."""
    total_seconds = validate_timeout_seconds(timeout_seconds) + validate_non_negative_float(
        grace_seconds,
        "Grace seconds",
    )
    deadline = parse_timeout_datetime(
        calculate_deadline_at(
            started_at,
            total_seconds,
        ),
    )
    current = parse_timeout_datetime(now) if now is not None else datetime.now(UTC)

    return current >= deadline


def build_timeout_config(
    *,
    timeout_seconds: float = 30.0,
    grace_seconds: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> TimeoutConfig:
    """Build timeout config."""
    return TimeoutConfig(
        timeout_seconds=timeout_seconds,
        grace_seconds=grace_seconds,
        metadata=metadata or {},
    )


def build_deadline(
    *,
    operation: str,
    component: str,
    config: TimeoutConfig | None = None,
    started_at: str | None = None,
    state: TimeoutState | str = TimeoutState.ACTIVE,
    metadata: dict[str, Any] | None = None,
) -> Deadline:
    """Build deadline."""
    deadline_kwargs: dict[str, Any] = {
        "operation": operation,
        "component": component,
        "config": config or TimeoutConfig(),
        "state": state,
        "metadata": metadata or {},
    }

    if started_at is not None:
        deadline_kwargs["started_at"] = started_at

    return Deadline(**deadline_kwargs)


def build_deadline_check_result(
    *,
    expired: bool,
    operation: str,
    component: str,
    state: TimeoutState | str,
    elapsed_seconds: float,
    remaining_seconds: float,
    deadline_at: str,
    checked_at: str,
    metadata: dict[str, Any] | None = None,
) -> DeadlineCheckResult:
    """Build deadline check result."""
    return DeadlineCheckResult(
        expired=expired,
        operation=operation,
        component=component,
        state=state,
        elapsed_seconds=elapsed_seconds,
        remaining_seconds=remaining_seconds,
        deadline_at=deadline_at,
        checked_at=checked_at,
        metadata=metadata or {},
    )


def build_timeout_execution_result(
    *,
    success: bool,
    operation: str,
    component: str,
    deadline_check: DeadlineCheckResult,
    value: Any = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TimeoutExecutionResult:
    """Build timeout execution result."""
    return TimeoutExecutionResult(
        success=success,
        operation=operation,
        component=component,
        deadline_check=deadline_check,
        value=value,
        error=error,
        metadata=metadata or {},
    )


def execute_with_deadline(
    operation: Callable[[], Any],
    *,
    deadline: Deadline,
    now: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> TimeoutExecutionResult:
    """Execute callable if deadline is active and not expired.

    This helper is deterministic and does not interrupt long-running code. It
    checks the deadline before running the operation and captures the result.
    """
    if not callable(operation):
        raise ValueError("Operation must be callable.")

    if not isinstance(deadline, Deadline):
        raise ValueError("Deadline must be a Deadline.")

    if metadata is not None:
        validate_attributes(metadata)

    check = deadline.check(now=now)

    if check.expired:
        return build_timeout_execution_result(
            success=False,
            operation=deadline.operation,
            component=deadline.component,
            deadline_check=check,
            error="Operation deadline expired.",
            metadata=metadata or {},
        )

    if not deadline.active:
        return build_timeout_execution_result(
            success=False,
            operation=deadline.operation,
            component=deadline.component,
            deadline_check=check,
            error="Deadline is not active.",
            metadata=metadata or {},
        )

    try:
        value = operation()
        deadline.complete()

        return build_timeout_execution_result(
            success=True,
            operation=deadline.operation,
            component=deadline.component,
            deadline_check=check,
            value=value,
            metadata=metadata or {},
        )
    except Exception as exc:  # noqa: BLE001
        return build_timeout_execution_result(
            success=False,
            operation=deadline.operation,
            component=deadline.component,
            deadline_check=check,
            error=str(exc),
            metadata={
                "error_type": exc.__class__.__name__,
                **(metadata or {}),
            },
        )