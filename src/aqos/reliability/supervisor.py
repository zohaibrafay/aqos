"""
AQOS runtime supervisor primitives.

This module coordinates retry, circuit breaker, rate limiter, and deadline
helpers into one deterministic runtime supervision layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
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
from aqos.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    build_circuit_breaker,
)
from aqos.reliability.rate_limiter import (
    RateLimitConfig,
    RateLimiter,
    build_rate_limiter,
)
from aqos.reliability.retry import (
    RetryPolicy,
    run_with_retry,
)
from aqos.reliability.timeout import (
    TimeoutConfig,
    build_deadline,
    execute_with_deadline,
)


class SupervisorState(str, Enum):
    """Supported supervisor states."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"


class SupervisorEventType(str, Enum):
    """Supported supervisor event types."""

    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"
    DEGRADED = "degraded"
    REGISTERED = "registered"
    CLEARED = "cleared"


@dataclass(frozen=True)
class SupervisorEvent:
    """Runtime supervisor event."""

    event_type: SupervisorEventType | str
    operation: str
    component: str
    state: SupervisorState | str
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_supervisor_event_type(self.event_type)
        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")
        normalize_supervisor_state(self.state)
        validate_string(self.message, "Message")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_attributes(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert supervisor event into dictionary."""
        return {
            "event_type": normalize_supervisor_event_type(self.event_type).value,
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "state": normalize_supervisor_state(self.state).value,
            "message": self.message.strip(),
            "timestamp": self.timestamp.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RuntimeSupervisorConfig:
    """Runtime supervisor configuration."""

    enable_retry: bool = True
    enable_circuit_breaker: bool = True
    enable_rate_limiter: bool = True
    enable_deadline: bool = True
    default_component: str = "runtime"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_boolean(self.enable_retry, "Enable retry")
        validate_boolean(self.enable_circuit_breaker, "Enable circuit breaker")
        validate_boolean(self.enable_rate_limiter, "Enable rate limiter")
        validate_boolean(self.enable_deadline, "Enable deadline")
        validate_non_empty_string(self.default_component, "Default component")
        validate_attributes(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        """Convert config into dictionary."""
        return {
            "enable_retry": self.enable_retry,
            "enable_circuit_breaker": self.enable_circuit_breaker,
            "enable_rate_limiter": self.enable_rate_limiter,
            "enable_deadline": self.enable_deadline,
            "default_component": self.default_component.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SupervisionRecord:
    """Single supervised operation record."""

    operation: str
    component: str
    state: SupervisorState | str
    success: bool
    started_at: str
    finished_at: str
    duration_seconds: float = 0.0
    value: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")
        normalize_supervisor_state(self.state)

        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_non_empty_string(self.started_at, "Started at")
        validate_non_empty_string(self.finished_at, "Finished at")
        validate_non_negative_float(self.duration_seconds, "Duration seconds")
        validate_attributes(self.metadata)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

    @property
    def failed(self) -> bool:
        """Return whether record failed."""
        return not self.success

    def to_reliability_result(self) -> ReliabilityResult:
        """Convert record into reliability result."""
        return build_reliability_result(
            success=self.success,
            operation=self.operation,
            component=self.component,
            status=ReliabilityStatus.OK if self.success else ReliabilityStatus.FAILED,
            message="Supervised operation completed successfully."
            if self.success
            else "Supervised operation failed.",
            value=self.value,
            error=self.error,
            metadata=self.to_dict(),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert record into dictionary."""
        payload = {
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "state": normalize_supervisor_state(self.state).value,
            "success": self.success,
            "failed": self.failed,
            "started_at": self.started_at.strip(),
            "finished_at": self.finished_at.strip(),
            "duration_seconds": float(self.duration_seconds),
            "value": self.value,
            "error": self.error.strip() if self.error else None,
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass
class RuntimeSupervisor:
    """Runtime reliability supervisor."""

    config: RuntimeSupervisorConfig = field(default_factory=RuntimeSupervisorConfig)
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    circuit_breaker_config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    rate_limiter: RateLimiter = field(default_factory=RateLimiter)
    timeout_config: TimeoutConfig = field(default_factory=TimeoutConfig)
    circuit_breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    records: list[SupervisionRecord] = field(default_factory=list)
    events: list[SupervisorEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.config, RuntimeSupervisorConfig):
            raise ValueError("Config must be a RuntimeSupervisorConfig.")

        if not isinstance(self.retry_policy, RetryPolicy):
            raise ValueError("Retry policy must be a RetryPolicy.")

        if not isinstance(self.circuit_breaker_config, CircuitBreakerConfig):
            raise ValueError("Circuit breaker config must be a CircuitBreakerConfig.")

        if not isinstance(self.rate_limiter, RateLimiter):
            raise ValueError("Rate limiter must be a RateLimiter.")

        if not isinstance(self.timeout_config, TimeoutConfig):
            raise ValueError("Timeout config must be a TimeoutConfig.")

        for breaker in self.circuit_breakers.values():
            if not isinstance(breaker, CircuitBreaker):
                raise ValueError("Circuit breakers must contain CircuitBreaker objects.")

        validate_supervision_records(self.records)
        validate_supervisor_events(self.events)
        validate_attributes(self.metadata)

    def add_event(
        self,
        *,
        event_type: SupervisorEventType | str,
        operation: str,
        component: str,
        state: SupervisorState | str,
        message: str = "",
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> SupervisorEvent:
        """Add supervisor event."""
        event = build_supervisor_event(
            event_type=event_type,
            operation=operation,
            component=component,
            state=state,
            message=message,
            metadata=metadata or {},
            timestamp=timestamp,
        )
        self.events.append(event)
        return event

    def get_or_create_circuit_breaker(
        self,
        operation: str,
        component: str,
    ) -> CircuitBreaker:
        """Get or create circuit breaker for operation."""
        normalized_operation = validate_non_empty_string(operation, "Operation")
        normalized_component = validate_non_empty_string(component, "Component")
        key = build_supervisor_key(
            operation=normalized_operation,
            component=normalized_component,
        )

        breaker = self.circuit_breakers.get(key)

        if breaker is None:
            breaker = build_circuit_breaker(
                name=normalized_operation,
                component=normalized_component,
                config=self.circuit_breaker_config,
            )
            self.circuit_breakers[key] = breaker
            self.add_event(
                event_type=SupervisorEventType.REGISTERED,
                operation=normalized_operation,
                component=normalized_component,
                state=SupervisorState.IDLE,
                message="Circuit breaker registered.",
                metadata={
                    "key": key,
                },
            )

        return breaker

    def supervise(
        self,
        operation: Callable[[], Any],
        *,
        operation_name: str,
        component: str | None = None,
        rate_limit_key: str | None = None,
        now: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ReliabilityResult:
        """Run an operation through enabled reliability controls."""
        if not callable(operation):
            raise ValueError("Operation must be callable.")

        normalized_operation = validate_non_empty_string(operation_name, "Operation name")
        normalized_component = validate_non_empty_string(
            component or self.config.default_component,
            "Component",
        )

        if metadata is not None:
            validate_attributes(metadata)

        started_at = normalize_supervisor_timestamp(now)
        self.add_event(
            event_type=SupervisorEventType.STARTED,
            operation=normalized_operation,
            component=normalized_component,
            state=SupervisorState.RUNNING,
            message="Supervised operation started.",
            metadata=metadata or {},
            timestamp=started_at,
        )

        guarded_operation = operation

        if self.config.enable_retry:
            guarded_operation = build_retry_callable(
                guarded_operation,
                operation_name=normalized_operation,
                component=normalized_component,
                retry_policy=self.retry_policy,
                metadata=metadata or {},
            )

        if self.config.enable_deadline:
            deadline = build_deadline(
                operation=normalized_operation,
                component=normalized_component,
                config=self.timeout_config,
                started_at=started_at,
                metadata=metadata or {},
            )

            base_operation = guarded_operation

            def deadline_operation(base_operation: Callable[[], Any] = base_operation) -> Any:
                deadline_result = execute_with_deadline(
                    base_operation,
                    deadline=deadline,
                    now=started_at,
                    metadata=metadata or {},
                    )

                if not deadline_result.success:
                    raise RuntimeError(deadline_result.error or "Deadline operation failed.")

                return deadline_result.value

            guarded_operation = deadline_operation

        if self.config.enable_circuit_breaker:
            breaker = self.get_or_create_circuit_breaker(
                normalized_operation,
                normalized_component,
            )
            base_operation = guarded_operation

            def circuit_operation(base_operation: Callable[[], Any] = base_operation) -> Any:
                circuit_result = breaker.execute(
                    base_operation,
                    now=started_at,
                )

                if not circuit_result.success:
                    raise RuntimeError(circuit_result.error or "Circuit breaker operation failed.")

                return circuit_result.value

            guarded_operation = circuit_operation

        if self.config.enable_rate_limiter:
            key = rate_limit_key or build_supervisor_key(
                operation=normalized_operation,
                component=normalized_component,
            )
            base_operation = guarded_operation

            def rate_limited_operation(base_operation: Callable[[], Any] = base_operation) -> Any:
                rate_result = self.rate_limiter.execute(
                    key,
                    base_operation,
                    now=started_at,
                )

                if not rate_result.success:
                    raise RuntimeError(rate_result.error or "Rate-limited operation failed.")

                return rate_result.value

            guarded_operation = rate_limited_operation

        try:
            value = guarded_operation()
            finished_at = started_at

            record = build_supervision_record(
                operation=normalized_operation,
                component=normalized_component,
                state=SupervisorState.COMPLETED,
                success=True,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=0.0,
                value=value,
                metadata={
                    "controls": self.enabled_controls(),
                    **(metadata or {}),
                },
            )
            self.records.append(record)
            self.add_event(
                event_type=SupervisorEventType.COMPLETED,
                operation=normalized_operation,
                component=normalized_component,
                state=SupervisorState.COMPLETED,
                message="Supervised operation completed.",
                metadata=record.to_dict(),
                timestamp=finished_at,
            )

            return record.to_reliability_result()
        except Exception as exc:  # noqa: BLE001
            finished_at = started_at
            record = build_supervision_record(
                operation=normalized_operation,
                component=normalized_component,
                state=SupervisorState.FAILED,
                success=False,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=0.0,
                error=str(exc),
                metadata={
                    "error_type": exc.__class__.__name__,
                    "controls": self.enabled_controls(),
                    **(metadata or {}),
                },
            )
            self.records.append(record)
            self.add_event(
                event_type=SupervisorEventType.FAILED,
                operation=normalized_operation,
                component=normalized_component,
                state=SupervisorState.FAILED,
                message="Supervised operation failed.",
                metadata=record.to_dict(),
                timestamp=finished_at,
            )

            return record.to_reliability_result()

    def latest_records(self, limit: int | None = None) -> list[SupervisionRecord]:
        """Return latest supervision records."""
        if limit is None:
            return list(self.records)

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("Limit must be a positive integer.")

        return self.records[-limit:]

    def latest_events(self, limit: int | None = None) -> list[SupervisorEvent]:
        """Return latest supervisor events."""
        if limit is None:
            return list(self.events)

        if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
            raise ValueError("Limit must be a positive integer.")

        return self.events[-limit:]

    def enabled_controls(self) -> list[str]:
        """Return enabled reliability controls."""
        controls: list[str] = []

        if self.config.enable_retry:
            controls.append("retry")

        if self.config.enable_circuit_breaker:
            controls.append("circuit_breaker")

        if self.config.enable_rate_limiter:
            controls.append("rate_limiter")

        if self.config.enable_deadline:
            controls.append("deadline")

        return controls

    def summary(self) -> dict[str, Any]:
        """Return runtime supervisor summary."""
        successful_records = [
            record
            for record in self.records
            if record.success
        ]
        failed_records = [
            record
            for record in self.records
            if record.failed
        ]

        return {
            "records": len(self.records),
            "events": len(self.events),
            "successful_records": len(successful_records),
            "failed_records": len(failed_records),
            "circuit_breakers": len(self.circuit_breakers),
            "enabled_controls": self.enabled_controls(),
            "config": self.config.to_dict(),
            "metadata": dict(self.metadata),
        }

    def clear(self) -> None:
        """Clear runtime supervisor state."""
        self.records.clear()
        self.events.clear()
        self.circuit_breakers.clear()


def normalize_supervisor_state(state: SupervisorState | str) -> SupervisorState:
    """Normalize supervisor state."""
    if isinstance(state, SupervisorState):
        return state

    normalized = validate_non_empty_string(state, "Supervisor state").lower()

    try:
        return SupervisorState(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SupervisorState)
        raise ValueError(
            f"Invalid supervisor state '{state}'. Valid states: {valid}.",
        ) from exc


def normalize_supervisor_event_type(
    event_type: SupervisorEventType | str,
) -> SupervisorEventType:
    """Normalize supervisor event type."""
    if isinstance(event_type, SupervisorEventType):
        return event_type

    normalized = validate_non_empty_string(event_type, "Supervisor event type").lower()

    try:
        return SupervisorEventType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SupervisorEventType)
        raise ValueError(
            f"Invalid supervisor event type '{event_type}'. Valid event types: {valid}.",
        ) from exc


def validate_boolean(value: bool, field_name: str) -> bool:
    """Validate boolean value."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def validate_supervision_records(
    records: list[SupervisionRecord],
) -> list[SupervisionRecord]:
    """Validate supervision records."""
    if not isinstance(records, list):
        raise ValueError("Records must be a list.")

    for record in records:
        if not isinstance(record, SupervisionRecord):
            raise ValueError("Records must contain SupervisionRecord objects.")

    return records


def validate_supervisor_events(
    events: list[SupervisorEvent],
) -> list[SupervisorEvent]:
    """Validate supervisor events."""
    if not isinstance(events, list):
        raise ValueError("Events must be a list.")

    for event in events:
        if not isinstance(event, SupervisorEvent):
            raise ValueError("Events must contain SupervisorEvent objects.")

    return events


def build_supervisor_key(
    *,
    operation: str,
    component: str,
) -> str:
    """Build stable supervisor key."""
    normalized_operation = validate_non_empty_string(operation, "Operation")
    normalized_component = validate_non_empty_string(component, "Component")

    return f"{normalized_component}:{normalized_operation}"


def normalize_supervisor_timestamp(value: str | None = None) -> str:
    """Normalize supervisor timestamp."""
    if value is None:
        return datetime.now(UTC).isoformat()

    return validate_non_empty_string(value, "Timestamp")


def build_supervisor_event(
    *,
    event_type: SupervisorEventType | str,
    operation: str,
    component: str,
    state: SupervisorState | str,
    message: str = "",
    timestamp: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SupervisorEvent:
    """Build supervisor event."""
    event_kwargs: dict[str, Any] = {
        "event_type": event_type,
        "operation": operation,
        "component": component,
        "state": state,
        "message": message,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        event_kwargs["timestamp"] = timestamp

    return SupervisorEvent(**event_kwargs)


def build_supervision_record(
    *,
    operation: str,
    component: str,
    state: SupervisorState | str,
    success: bool,
    started_at: str,
    finished_at: str,
    duration_seconds: float = 0.0,
    value: Any = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SupervisionRecord:
    """Build supervision record."""
    return SupervisionRecord(
        operation=operation,
        component=component,
        state=state,
        success=success,
        started_at=started_at,
        finished_at=finished_at,
        duration_seconds=duration_seconds,
        value=value,
        error=error,
        metadata=metadata or {},
    )


def build_runtime_supervisor_config(
    *,
    enable_retry: bool = True,
    enable_circuit_breaker: bool = True,
    enable_rate_limiter: bool = True,
    enable_deadline: bool = True,
    default_component: str = "runtime",
    metadata: dict[str, Any] | None = None,
) -> RuntimeSupervisorConfig:
    """Build runtime supervisor config."""
    return RuntimeSupervisorConfig(
        enable_retry=enable_retry,
        enable_circuit_breaker=enable_circuit_breaker,
        enable_rate_limiter=enable_rate_limiter,
        enable_deadline=enable_deadline,
        default_component=default_component,
        metadata=metadata or {},
    )


def build_runtime_supervisor(
    *,
    config: RuntimeSupervisorConfig | None = None,
    retry_policy: RetryPolicy | None = None,
    circuit_breaker_config: CircuitBreakerConfig | None = None,
    rate_limit_config: RateLimitConfig | None = None,
    rate_limiter: RateLimiter | None = None,
    timeout_config: TimeoutConfig | None = None,
    metadata: dict[str, Any] | None = None,
) -> RuntimeSupervisor:
    """Build runtime supervisor."""
    return RuntimeSupervisor(
        config=config or RuntimeSupervisorConfig(),
        retry_policy=retry_policy or RetryPolicy(),
        circuit_breaker_config=circuit_breaker_config or CircuitBreakerConfig(),
        rate_limiter=rate_limiter
        or build_rate_limiter(
            config=rate_limit_config or RateLimitConfig(),
        ),
        timeout_config=timeout_config or TimeoutConfig(),
        metadata=metadata or {},
    )


def build_retry_callable(
    operation: Callable[[], Any],
    *,
    operation_name: str,
    component: str,
    retry_policy: RetryPolicy,
    metadata: dict[str, Any] | None = None,
) -> Callable[[], Any]:
    """Wrap operation with retry."""
    if not callable(operation):
        raise ValueError("Operation must be callable.")

    if not isinstance(retry_policy, RetryPolicy):
        raise ValueError("Retry policy must be a RetryPolicy.")

    def wrapped() -> Any:
        result = run_with_retry(
            operation,
            policy=retry_policy,
            operation_name=operation_name,
            component=component,
            metadata=metadata or {},
        )

        if not result.success:
            raise RuntimeError(result.error or "Retry operation failed.")

        return result.value

    return wrapped