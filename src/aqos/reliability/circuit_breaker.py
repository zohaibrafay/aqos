"""
AQOS circuit breaker primitives.

This module provides dependency-free circuit breaker state management,
failure tracking, half-open recovery, and protected operation execution.
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
    validate_non_negative_integer,
    validate_positive_integer,
    validate_string,
)


class CircuitBreakerState(str, Enum):
    """Supported circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerEventType(str, Enum):
    """Supported circuit breaker event types."""

    SUCCESS = "success"
    FAILURE = "failure"
    OPENED = "opened"
    CLOSED = "closed"
    HALF_OPENED = "half_opened"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    failure_threshold: int = 3
    recovery_timeout_seconds: float = 30.0
    success_threshold: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_positive_integer(self.failure_threshold, "Failure threshold")
        validate_non_negative_float(self.recovery_timeout_seconds, "Recovery timeout seconds")
        validate_positive_integer(self.success_threshold, "Success threshold")
        validate_attributes(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert config into dictionary."""
        return {
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_seconds": float(self.recovery_timeout_seconds),
            "success_threshold": self.success_threshold,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CircuitBreakerEvent:
    """Single circuit breaker event."""

    event_type: CircuitBreakerEventType | str
    state: CircuitBreakerState | str
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_circuit_breaker_event_type(self.event_type)
        normalize_circuit_breaker_state(self.state)
        validate_string(self.message, "Message")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_attributes(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert event into dictionary."""
        return {
            "event_type": normalize_circuit_breaker_event_type(self.event_type).value,
            "state": normalize_circuit_breaker_state(self.state).value,
            "message": self.message.strip(),
            "timestamp": self.timestamp.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass
class CircuitBreakerStats:
    """Circuit breaker counters and timestamps."""

    failure_count: int = 0
    success_count: int = 0
    rejected_count: int = 0
    opened_at: str | None = None
    last_failure_at: str | None = None
    last_success_at: str | None = None

    def __post_init__(self) -> None:
        validate_non_negative_integer(self.failure_count, "Failure count")
        validate_non_negative_integer(self.success_count, "Success count")
        validate_non_negative_integer(self.rejected_count, "Rejected count")

        if self.opened_at is not None:
            validate_non_empty_string(self.opened_at, "Opened at")

        if self.last_failure_at is not None:
            validate_non_empty_string(self.last_failure_at, "Last failure at")

        if self.last_success_at is not None:
            validate_non_empty_string(self.last_success_at, "Last success at")

    def record_success(self, timestamp: str | None = None) -> None:
        """Record success."""
        now = timestamp or datetime.now(UTC).isoformat()
        validate_non_empty_string(now, "Timestamp")

        self.success_count += 1
        self.last_success_at = now

    def record_failure(self, timestamp: str | None = None) -> None:
        """Record failure."""
        now = timestamp or datetime.now(UTC).isoformat()
        validate_non_empty_string(now, "Timestamp")

        self.failure_count += 1
        self.last_failure_at = now

    def record_rejected(self) -> None:
        """Record rejected call."""
        self.rejected_count += 1

    def reset_counts(self) -> None:
        """Reset success and failure counts."""
        self.failure_count = 0
        self.success_count = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert stats into dictionary."""
        payload = {
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "rejected_count": self.rejected_count,
            "opened_at": self.opened_at,
            "last_failure_at": self.last_failure_at,
            "last_success_at": self.last_success_at,
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass
class CircuitBreaker:
    """Dependency-free circuit breaker."""

    name: str
    component: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    state: CircuitBreakerState | str = CircuitBreakerState.CLOSED
    stats: CircuitBreakerStats = field(default_factory=CircuitBreakerStats)
    events: list[CircuitBreakerEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Circuit breaker name")
        validate_non_empty_string(self.component, "Component")

        if not isinstance(self.config, CircuitBreakerConfig):
            raise ValueError("Config must be a CircuitBreakerConfig.")

        self.state = normalize_circuit_breaker_state(self.state)

        if not isinstance(self.stats, CircuitBreakerStats):
            raise ValueError("Stats must be CircuitBreakerStats.")

        validate_circuit_breaker_events(self.events)
        validate_attributes(self.metadata)

    @property
    def closed(self) -> bool:
        """Return whether circuit is closed."""
        return self.state == CircuitBreakerState.CLOSED

    @property
    def open(self) -> bool:
        """Return whether circuit is open."""
        return self.state == CircuitBreakerState.OPEN

    @property
    def half_open(self) -> bool:
        """Return whether circuit is half-open."""
        return self.state == CircuitBreakerState.HALF_OPEN

    def add_event(
        self,
        *,
        event_type: CircuitBreakerEventType | str,
        message: str = "",
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> CircuitBreakerEvent:
        """Add circuit breaker event."""
        event = build_circuit_breaker_event(
            event_type=event_type,
            state=self.state,
            message=message,
            metadata=metadata or {},
            timestamp=timestamp,
        )
        self.events.append(event)
        return event

    def should_allow_request(self, now: str | None = None) -> bool:
        """Return whether a request should be allowed."""
        if self.closed or self.half_open:
            return True

        if self.open and self.recovery_timeout_elapsed(now=now):
            self.transition_to_half_open(now=now)
            return True

        return False

    def recovery_timeout_elapsed(self, now: str | None = None) -> bool:
        """Return whether open circuit recovery timeout has elapsed."""
        if not self.stats.opened_at:
            return True

        opened_at = parse_circuit_datetime(self.stats.opened_at)
        current = parse_circuit_datetime(now) if now is not None else datetime.now(UTC)

        return current >= opened_at + timedelta(seconds=self.config.recovery_timeout_seconds)

    def transition_to_open(self, now: str | None = None) -> None:
        """Open circuit breaker."""
        timestamp = now or datetime.now(UTC).isoformat()
        validate_non_empty_string(timestamp, "Timestamp")

        self.state = CircuitBreakerState.OPEN
        self.stats.opened_at = timestamp
        self.stats.success_count = 0
        self.add_event(
            event_type=CircuitBreakerEventType.OPENED,
            message="Circuit breaker opened.",
            timestamp=timestamp,
        )

    def transition_to_half_open(self, now: str | None = None) -> None:
        """Move circuit breaker to half-open."""
        timestamp = now or datetime.now(UTC).isoformat()
        validate_non_empty_string(timestamp, "Timestamp")

        self.state = CircuitBreakerState.HALF_OPEN
        self.stats.reset_counts()
        self.add_event(
            event_type=CircuitBreakerEventType.HALF_OPENED,
            message="Circuit breaker half-opened.",
            timestamp=timestamp,
        )

    def transition_to_closed(self, now: str | None = None) -> None:
        """Close circuit breaker."""
        timestamp = now or datetime.now(UTC).isoformat()
        validate_non_empty_string(timestamp, "Timestamp")

        self.state = CircuitBreakerState.CLOSED
        self.stats.opened_at = None
        self.stats.reset_counts()
        self.add_event(
            event_type=CircuitBreakerEventType.CLOSED,
            message="Circuit breaker closed.",
            timestamp=timestamp,
        )

    def record_success(self, now: str | None = None) -> None:
        """Record successful operation."""
        timestamp = now or datetime.now(UTC).isoformat()
        self.stats.record_success(timestamp)
        self.add_event(
            event_type=CircuitBreakerEventType.SUCCESS,
            message="Circuit breaker operation succeeded.",
            timestamp=timestamp,
        )

        if self.half_open and self.stats.success_count >= self.config.success_threshold:
            self.transition_to_closed(now=timestamp)

        if self.closed:
            self.stats.failure_count = 0

    def record_failure(self, error: str = "", now: str | None = None) -> None:
        """Record failed operation."""
        validate_string(error, "Error")
        timestamp = now or datetime.now(UTC).isoformat()

        self.stats.record_failure(timestamp)
        self.add_event(
            event_type=CircuitBreakerEventType.FAILURE,
            message=error or "Circuit breaker operation failed.",
            metadata={
                "error": error,
            },
            timestamp=timestamp,
        )

        if self.half_open:
            self.transition_to_open(now=timestamp)
            return

        if self.closed and self.stats.failure_count >= self.config.failure_threshold:
            self.transition_to_open(now=timestamp)

    def reject_request(self) -> CircuitBreakerEvent:
        """Reject request because circuit is open."""
        self.stats.record_rejected()
        return self.add_event(
            event_type=CircuitBreakerEventType.REJECTED,
            message="Circuit breaker is open.",
        )

    def execute(
        self,
        operation: Callable[[], Any],
        *,
        now: str | None = None,
    ) -> ReliabilityResult:
        """Execute operation through circuit breaker."""
        if not callable(operation):
            raise ValueError("Operation must be callable.")

        if not self.should_allow_request(now=now):
            self.reject_request()
            return build_reliability_result(
                success=False,
                operation=self.name,
                component=self.component,
                status=ReliabilityStatus.DEGRADED,
                message="Circuit breaker rejected operation.",
                error="Circuit breaker is open.",
                metadata=self.to_dict(),
            )

        try:
            value = operation()
            self.record_success(now=now)

            return build_reliability_result(
                success=True,
                operation=self.name,
                component=self.component,
                status=ReliabilityStatus.OK,
                message="Circuit breaker operation completed successfully.",
                value=value,
                metadata=self.to_dict(),
            )
        except Exception as exc:  # noqa: BLE001
            self.record_failure(str(exc), now=now)

            return build_reliability_result(
                success=False,
                operation=self.name,
                component=self.component,
                status=ReliabilityStatus.FAILED,
                message="Circuit breaker operation failed.",
                error=str(exc),
                metadata={
                    "error_type": exc.__class__.__name__,
                    **self.to_dict(),
                },
            )

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.state = CircuitBreakerState.CLOSED
        self.stats = CircuitBreakerStats()
        self.events.clear()

    def to_dict(self) -> dict[str, Any]:
        """Convert circuit breaker into dictionary."""
        return {
            "name": self.name.strip(),
            "component": self.component.strip(),
            "state": normalize_circuit_breaker_state(self.state).value,
            "closed": self.closed,
            "open": self.open,
            "half_open": self.half_open,
            "config": self.config.to_dict(),
            "stats": self.stats.to_dict(),
            "events": [
                event.to_dict()
                for event in self.events
            ],
            "metadata": dict(self.metadata),
        }


def normalize_circuit_breaker_state(
    state: CircuitBreakerState | str,
) -> CircuitBreakerState:
    """Normalize circuit breaker state."""
    if isinstance(state, CircuitBreakerState):
        return state

    normalized = validate_non_empty_string(state, "Circuit breaker state").lower()

    try:
        return CircuitBreakerState(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in CircuitBreakerState)
        raise ValueError(
            f"Invalid circuit breaker state '{state}'. Valid states: {valid}.",
        ) from exc


def normalize_circuit_breaker_event_type(
    event_type: CircuitBreakerEventType | str,
) -> CircuitBreakerEventType:
    """Normalize circuit breaker event type."""
    if isinstance(event_type, CircuitBreakerEventType):
        return event_type

    normalized = validate_non_empty_string(event_type, "Circuit breaker event type").lower()

    try:
        return CircuitBreakerEventType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in CircuitBreakerEventType)
        raise ValueError(
            f"Invalid circuit breaker event type '{event_type}'. Valid event types: {valid}.",
        ) from exc


def validate_circuit_breaker_events(
    events: list[CircuitBreakerEvent],
) -> list[CircuitBreakerEvent]:
    """Validate circuit breaker events."""
    if not isinstance(events, list):
        raise ValueError("Events must be a list.")

    for event in events:
        if not isinstance(event, CircuitBreakerEvent):
            raise ValueError("Events must contain CircuitBreakerEvent objects.")

    return events


def parse_circuit_datetime(value: str) -> datetime:
    """Parse circuit datetime."""
    normalized = validate_non_empty_string(value, "Datetime")
    parsed = datetime.fromisoformat(normalized)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)

    return parsed


def build_circuit_breaker_config(
    *,
    failure_threshold: int = 3,
    recovery_timeout_seconds: float = 30.0,
    success_threshold: int = 1,
    metadata: dict[str, Any] | None = None,
) -> CircuitBreakerConfig:
    """Build circuit breaker config."""
    return CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=recovery_timeout_seconds,
        success_threshold=success_threshold,
        metadata=metadata or {},
    )


def build_circuit_breaker_event(
    *,
    event_type: CircuitBreakerEventType | str,
    state: CircuitBreakerState | str,
    message: str = "",
    timestamp: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CircuitBreakerEvent:
    """Build circuit breaker event."""
    event_kwargs: dict[str, Any] = {
        "event_type": event_type,
        "state": state,
        "message": message,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        event_kwargs["timestamp"] = timestamp

    return CircuitBreakerEvent(**event_kwargs)


def build_circuit_breaker_stats(
    *,
    failure_count: int = 0,
    success_count: int = 0,
    rejected_count: int = 0,
    opened_at: str | None = None,
    last_failure_at: str | None = None,
    last_success_at: str | None = None,
) -> CircuitBreakerStats:
    """Build circuit breaker stats."""
    return CircuitBreakerStats(
        failure_count=failure_count,
        success_count=success_count,
        rejected_count=rejected_count,
        opened_at=opened_at,
        last_failure_at=last_failure_at,
        last_success_at=last_success_at,
    )


def build_circuit_breaker(
    *,
    name: str,
    component: str,
    config: CircuitBreakerConfig | None = None,
    state: CircuitBreakerState | str = CircuitBreakerState.CLOSED,
    stats: CircuitBreakerStats | None = None,
    events: list[CircuitBreakerEvent] | None = None,
    metadata: dict[str, Any] | None = None,
) -> CircuitBreaker:
    """Build circuit breaker."""
    return CircuitBreaker(
        name=name,
        component=component,
        config=config or CircuitBreakerConfig(),
        state=state,
        stats=stats or CircuitBreakerStats(),
        events=events or [],
        metadata=metadata or {},
    )