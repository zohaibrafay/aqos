"""
AQOS retry policy primitives.

This module provides dependency-free retry policies, retry state tracking,
backoff calculation, and retry execution helpers.
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
    validate_positive_integer,
    validate_string,
)


class RetryBackoffStrategy(str, Enum):
    """Supported retry backoff strategies."""

    NONE = "none"
    CONSTANT = "constant"
    LINEAR = "linear"
    EXPONENTIAL = "exponential"


@dataclass(frozen=True)
class RetryPolicy:
    """Retry policy configuration."""

    max_attempts: int = 3
    backoff_strategy: RetryBackoffStrategy | str = RetryBackoffStrategy.EXPONENTIAL
    initial_delay_seconds: float = 0.1
    max_delay_seconds: float = 5.0
    retry_on_exceptions: tuple[type[BaseException], ...] = (Exception,)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_positive_integer(self.max_attempts, "Max attempts")
        normalize_retry_backoff_strategy(self.backoff_strategy)
        validate_non_negative_float(self.initial_delay_seconds, "Initial delay seconds")
        validate_non_negative_float(self.max_delay_seconds, "Max delay seconds")
        validate_retry_exception_types(self.retry_on_exceptions)
        validate_attributes(self.metadata)

    def should_retry_exception(self, exception: BaseException) -> bool:
        """Return whether an exception should be retried."""
        if not isinstance(exception, BaseException):
            raise ValueError("Exception must be a BaseException.")

        return isinstance(exception, self.retry_on_exceptions)

    def calculate_delay(self, attempt_number: int) -> float:
        """Calculate retry delay for an attempt."""
        return calculate_retry_delay(
            attempt_number=attempt_number,
            strategy=self.backoff_strategy,
            initial_delay_seconds=self.initial_delay_seconds,
            max_delay_seconds=self.max_delay_seconds,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert retry policy into a serializable dictionary."""
        return {
            "max_attempts": self.max_attempts,
            "backoff_strategy": normalize_retry_backoff_strategy(self.backoff_strategy).value,
            "initial_delay_seconds": float(self.initial_delay_seconds),
            "max_delay_seconds": float(self.max_delay_seconds),
            "retry_on_exceptions": [
                exception_type.__name__
                for exception_type in self.retry_on_exceptions
            ],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RetryAttempt:
    """Single retry attempt result."""

    attempt_number: int
    success: bool
    delay_seconds: float = 0.0
    value: Any = None
    error: str | None = None
    error_type: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_positive_integer(self.attempt_number, "Attempt number")

        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_non_negative_float(self.delay_seconds, "Delay seconds")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_attributes(self.metadata)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

        if self.error_type is not None:
            validate_non_empty_string(self.error_type, "Error type")

    @property
    def failed(self) -> bool:
        """Return whether attempt failed."""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Convert retry attempt into a serializable dictionary."""
        payload = {
            "attempt_number": self.attempt_number,
            "success": self.success,
            "failed": self.failed,
            "delay_seconds": float(self.delay_seconds),
            "value": self.value,
            "error": self.error.strip() if self.error else None,
            "error_type": self.error_type.strip() if self.error_type else None,
            "timestamp": self.timestamp.strip(),
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass
class RetryState:
    """Mutable retry state."""

    operation: str
    component: str
    policy: RetryPolicy = field(default_factory=RetryPolicy)
    attempts: list[RetryAttempt] = field(default_factory=list)
    completed: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")

        if not isinstance(self.policy, RetryPolicy):
            raise ValueError("Policy must be a RetryPolicy.")

        validate_retry_attempts(self.attempts)

        if not isinstance(self.completed, bool):
            raise ValueError("Completed must be a boolean.")

        validate_attributes(self.metadata)

    @property
    def attempt_count(self) -> int:
        """Return attempt count."""
        return len(self.attempts)

    @property
    def remaining_attempts(self) -> int:
        """Return remaining attempts."""
        return max(
            self.policy.max_attempts - self.attempt_count,
            0,
        )

    @property
    def last_attempt(self) -> RetryAttempt | None:
        """Return latest attempt."""
        if not self.attempts:
            return None

        return self.attempts[-1]

    @property
    def succeeded(self) -> bool:
        """Return whether retry state succeeded."""
        return self.completed and self.last_attempt is not None and self.last_attempt.success

    @property
    def failed(self) -> bool:
        """Return whether retry state failed."""
        return self.completed and not self.succeeded

    def can_attempt(self) -> bool:
        """Return whether another attempt can run."""
        return not self.completed and self.attempt_count < self.policy.max_attempts

    def next_attempt_number(self) -> int:
        """Return next attempt number."""
        return self.attempt_count + 1

    def next_delay_seconds(self) -> float:
        """Return next delay seconds."""
        return self.policy.calculate_delay(self.next_attempt_number())

    def record_attempt(self, attempt: RetryAttempt) -> RetryAttempt:
        """Record retry attempt."""
        if not isinstance(attempt, RetryAttempt):
            raise ValueError("Attempt must be a RetryAttempt.")

        expected = self.next_attempt_number()

        if attempt.attempt_number != expected:
            raise ValueError(f"Attempt number must be {expected}.")

        self.attempts.append(attempt)

        if attempt.success or self.attempt_count >= self.policy.max_attempts:
            self.completed = True

        return attempt

    def to_dict(self) -> dict[str, Any]:
        """Convert retry state into a serializable dictionary."""
        return {
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "policy": self.policy.to_dict(),
            "attempts": [
                attempt.to_dict()
                for attempt in self.attempts
            ],
            "attempt_count": self.attempt_count,
            "remaining_attempts": self.remaining_attempts,
            "completed": self.completed,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class RetryExecutionResult:
    """Result of executing an operation with retry."""

    success: bool
    operation: str
    component: str
    attempts: list[RetryAttempt]
    value: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")
        validate_retry_attempts(self.attempts)
        validate_attributes(self.metadata)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

    @property
    def failed(self) -> bool:
        """Return whether execution failed."""
        return not self.success

    @property
    def attempt_count(self) -> int:
        """Return attempt count."""
        return len(self.attempts)

    def to_reliability_result(self) -> ReliabilityResult:
        """Convert retry execution into reliability result."""
        return build_reliability_result(
            success=self.success,
            operation=self.operation,
            component=self.component,
            status=ReliabilityStatus.OK if self.success else ReliabilityStatus.FAILED,
            message="Retry operation completed successfully."
            if self.success
            else "Retry operation failed.",
            value=self.value,
            error=self.error,
            metadata={
                "attempt_count": self.attempt_count,
                "attempts": [
                    attempt.to_dict()
                    for attempt in self.attempts
                ],
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert retry execution result into dictionary."""
        payload = {
            "success": self.success,
            "failed": self.failed,
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "attempt_count": self.attempt_count,
            "attempts": [
                attempt.to_dict()
                for attempt in self.attempts
            ],
            "value": self.value,
            "error": self.error.strip() if self.error else None,
            "metadata": dict(self.metadata),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


def normalize_retry_backoff_strategy(
    strategy: RetryBackoffStrategy | str,
) -> RetryBackoffStrategy:
    """Normalize retry backoff strategy."""
    if isinstance(strategy, RetryBackoffStrategy):
        return strategy

    normalized = validate_non_empty_string(strategy, "Retry backoff strategy").lower()

    try:
        return RetryBackoffStrategy(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in RetryBackoffStrategy)
        raise ValueError(
            f"Invalid retry backoff strategy '{strategy}'. Valid strategies: {valid}.",
        ) from exc


def validate_retry_exception_types(
    exception_types: tuple[type[BaseException], ...],
) -> tuple[type[BaseException], ...]:
    """Validate retry exception type tuple."""
    if not isinstance(exception_types, tuple):
        raise ValueError("Retry exception types must be a tuple.")

    if not exception_types:
        raise ValueError("Retry exception types cannot be empty.")

    for exception_type in exception_types:
        if not isinstance(exception_type, type) or not issubclass(exception_type, BaseException):
            raise ValueError("Retry exception types must be exception classes.")

    return exception_types


def validate_retry_attempts(attempts: list[RetryAttempt]) -> list[RetryAttempt]:
    """Validate retry attempt list."""
    if not isinstance(attempts, list):
        raise ValueError("Attempts must be a list.")

    for attempt in attempts:
        if not isinstance(attempt, RetryAttempt):
            raise ValueError("Attempts must contain RetryAttempt objects.")

    return attempts


def calculate_retry_delay(
    *,
    attempt_number: int,
    strategy: RetryBackoffStrategy | str = RetryBackoffStrategy.EXPONENTIAL,
    initial_delay_seconds: float = 0.1,
    max_delay_seconds: float = 5.0,
) -> float:
    """Calculate retry delay seconds."""
    validate_positive_integer(attempt_number, "Attempt number")
    normalized_strategy = normalize_retry_backoff_strategy(strategy)
    initial_delay = validate_non_negative_float(
        initial_delay_seconds,
        "Initial delay seconds",
    )
    max_delay = validate_non_negative_float(
        max_delay_seconds,
        "Max delay seconds",
    )

    if normalized_strategy == RetryBackoffStrategy.NONE:
        delay = 0.0
    elif normalized_strategy == RetryBackoffStrategy.CONSTANT:
        delay = initial_delay
    elif normalized_strategy == RetryBackoffStrategy.LINEAR:
        delay = initial_delay * attempt_number
    elif normalized_strategy == RetryBackoffStrategy.EXPONENTIAL:
        delay = initial_delay * (2 ** (attempt_number - 1))
    else:
        raise ValueError("Unsupported retry backoff strategy.")

    if max_delay > 0:
        delay = min(delay, max_delay)

    return float(delay)


def build_retry_policy(
    *,
    max_attempts: int = 3,
    backoff_strategy: RetryBackoffStrategy | str = RetryBackoffStrategy.EXPONENTIAL,
    initial_delay_seconds: float = 0.1,
    max_delay_seconds: float = 5.0,
    retry_on_exceptions: tuple[type[BaseException], ...] = (Exception,),
    metadata: dict[str, Any] | None = None,
) -> RetryPolicy:
    """Build retry policy."""
    return RetryPolicy(
        max_attempts=max_attempts,
        backoff_strategy=backoff_strategy,
        initial_delay_seconds=initial_delay_seconds,
        max_delay_seconds=max_delay_seconds,
        retry_on_exceptions=retry_on_exceptions,
        metadata=metadata or {},
    )


def build_retry_attempt(
    *,
    attempt_number: int,
    success: bool,
    delay_seconds: float = 0.0,
    value: Any = None,
    error: str | None = None,
    error_type: str | None = None,
    timestamp: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RetryAttempt:
    """Build retry attempt."""
    attempt_kwargs: dict[str, Any] = {
        "attempt_number": attempt_number,
        "success": success,
        "delay_seconds": delay_seconds,
        "value": value,
        "error": error,
        "error_type": error_type,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        attempt_kwargs["timestamp"] = timestamp

    return RetryAttempt(**attempt_kwargs)


def build_retry_state(
    *,
    operation: str,
    component: str,
    policy: RetryPolicy | None = None,
    attempts: list[RetryAttempt] | None = None,
    completed: bool = False,
    metadata: dict[str, Any] | None = None,
) -> RetryState:
    """Build retry state."""
    return RetryState(
        operation=operation,
        component=component,
        policy=policy or RetryPolicy(),
        attempts=attempts or [],
        completed=completed,
        metadata=metadata or {},
    )


def should_retry_attempt(
    *,
    policy: RetryPolicy,
    attempt_number: int,
    exception: BaseException,
) -> bool:
    """Return whether another retry should happen after an exception."""
    if not isinstance(policy, RetryPolicy):
        raise ValueError("Policy must be a RetryPolicy.")

    validate_positive_integer(attempt_number, "Attempt number")

    if not isinstance(exception, BaseException):
        raise ValueError("Exception must be a BaseException.")

    return attempt_number < policy.max_attempts and policy.should_retry_exception(exception)


def run_with_retry(
    operation: Callable[[], Any],
    *,
    policy: RetryPolicy | None = None,
    operation_name: str,
    component: str,
    metadata: dict[str, Any] | None = None,
) -> RetryExecutionResult:
    """Run callable with retry policy.

    This function does not sleep. It calculates and records intended delays,
    keeping tests and runtime orchestration deterministic.
    """
    if not callable(operation):
        raise ValueError("Operation must be callable.")

    retry_policy = policy or RetryPolicy()
    validate_non_empty_string(operation_name, "Operation name")
    validate_non_empty_string(component, "Component")

    if metadata is not None:
        validate_attributes(metadata)

    state = build_retry_state(
        operation=operation_name,
        component=component,
        policy=retry_policy,
        metadata=metadata or {},
    )

    last_error: str | None = None

    while state.can_attempt():
        attempt_number = state.next_attempt_number()
        delay_seconds = retry_policy.calculate_delay(attempt_number)

        try:
            value = operation()
            state.record_attempt(
                build_retry_attempt(
                    attempt_number=attempt_number,
                    success=True,
                    delay_seconds=delay_seconds,
                    value=value,
                ),
            )

            return RetryExecutionResult(
                success=True,
                operation=operation_name,
                component=component,
                attempts=list(state.attempts),
                value=value,
                metadata={
                    "policy": retry_policy.to_dict(),
                    **(metadata or {}),
                },
            )
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
            state.record_attempt(
                build_retry_attempt(
                    attempt_number=attempt_number,
                    success=False,
                    delay_seconds=delay_seconds,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                ),
            )

            if not should_retry_attempt(
                policy=retry_policy,
                attempt_number=attempt_number,
                exception=exc,
            ):
                break

    return RetryExecutionResult(
        success=False,
        operation=operation_name,
        component=component,
        attempts=list(state.attempts),
        error=last_error or "Operation failed.",
        metadata={
            "policy": retry_policy.to_dict(),
            **(metadata or {}),
        },
    )