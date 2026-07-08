"""
AQOS reliability integration helpers.

This module provides high-level convenience helpers for composing retry,
circuit breaker, rate limiting, deadline, and runtime supervision primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from aqos.reliability.base import (
    ReliabilityResult,
    ReliabilityStatus,
    build_reliability_result,
    safe_execute,
    validate_attributes,
    validate_non_empty_string,
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
from aqos.reliability.supervisor import (
    RuntimeSupervisor,
    RuntimeSupervisorConfig,
    build_runtime_supervisor,
)
from aqos.reliability.timeout import (
    Deadline,
    TimeoutConfig,
    build_deadline,
    execute_with_deadline,
)


@dataclass(frozen=True)
class ReliabilityProfile:
    """Reusable reliability profile."""

    name: str
    component: str
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    circuit_breaker_config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    rate_limit_config: RateLimitConfig = field(default_factory=RateLimitConfig)
    timeout_config: TimeoutConfig = field(default_factory=TimeoutConfig)
    supervisor_config: RuntimeSupervisorConfig = field(default_factory=RuntimeSupervisorConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Profile name")
        validate_non_empty_string(self.component, "Component")

        if not isinstance(self.retry_policy, RetryPolicy):
            raise ValueError("Retry policy must be a RetryPolicy.")

        if not isinstance(self.circuit_breaker_config, CircuitBreakerConfig):
            raise ValueError("Circuit breaker config must be a CircuitBreakerConfig.")

        if not isinstance(self.rate_limit_config, RateLimitConfig):
            raise ValueError("Rate limit config must be a RateLimitConfig.")

        if not isinstance(self.timeout_config, TimeoutConfig):
            raise ValueError("Timeout config must be a TimeoutConfig.")

        if not isinstance(self.supervisor_config, RuntimeSupervisorConfig):
            raise ValueError("Supervisor config must be a RuntimeSupervisorConfig.")

        validate_attributes(self.metadata)

    def build_rate_limiter(self) -> RateLimiter:
        """Build rate limiter for this profile."""
        return build_rate_limiter(
            config=self.rate_limit_config,
            metadata={
                "profile": self.name.strip(),
                **self.metadata,
            },
        )

    def build_circuit_breaker(self, operation: str) -> CircuitBreaker:
        """Build circuit breaker for this profile."""
        return build_circuit_breaker(
            name=operation,
            component=self.component,
            config=self.circuit_breaker_config,
            metadata={
                "profile": self.name.strip(),
                **self.metadata,
            },
        )

    def build_deadline(self, operation: str, *, started_at: str | None = None) -> Deadline:
        """Build deadline for this profile."""
        return build_deadline(
            operation=operation,
            component=self.component,
            config=self.timeout_config,
            started_at=started_at,
            metadata={
                "profile": self.name.strip(),
                **self.metadata,
            },
        )

    def build_supervisor(self) -> RuntimeSupervisor:
        """Build runtime supervisor for this profile."""
        return build_runtime_supervisor(
            config=self.supervisor_config,
            retry_policy=self.retry_policy,
            circuit_breaker_config=self.circuit_breaker_config,
            rate_limit_config=self.rate_limit_config,
            timeout_config=self.timeout_config,
            metadata={
                "profile": self.name.strip(),
                **self.metadata,
            },
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert profile into dictionary."""
        return {
            "name": self.name.strip(),
            "component": self.component.strip(),
            "retry_policy": self.retry_policy.to_dict(),
            "circuit_breaker_config": self.circuit_breaker_config.to_dict(),
            "rate_limit_config": self.rate_limit_config.to_dict(),
            "timeout_config": self.timeout_config.to_dict(),
            "supervisor_config": self.supervisor_config.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProtectedOperationResult:
    """Result of a protected operation pipeline."""

    success: bool
    operation: str
    component: str
    reliability_result: ReliabilityResult
    controls: list[str] = field(default_factory=list)
    value: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_non_empty_string(self.operation, "Operation")
        validate_non_empty_string(self.component, "Component")

        if not isinstance(self.reliability_result, ReliabilityResult):
            raise ValueError("Reliability result must be a ReliabilityResult.")

        validate_string_list(self.controls, "Controls")
        validate_attributes(self.metadata)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

    @property
    def failed(self) -> bool:
        """Return whether operation failed."""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Convert protected operation result into dictionary."""
        payload = {
            "success": self.success,
            "failed": self.failed,
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "reliability_result": self.reliability_result.to_dict(),
            "controls": list(self.controls),
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
class ReliabilityToolkit:
    """Convenience toolkit for reliability-protected operations."""

    profile: ReliabilityProfile = field(default_factory=lambda: build_reliability_profile())
    supervisor: RuntimeSupervisor | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.profile, ReliabilityProfile):
            raise ValueError("Profile must be a ReliabilityProfile.")

        if self.supervisor is not None and not isinstance(self.supervisor, RuntimeSupervisor):
            raise ValueError("Supervisor must be a RuntimeSupervisor.")

        validate_attributes(self.metadata)

    def get_supervisor(self) -> RuntimeSupervisor:
        """Get or build supervisor."""
        if self.supervisor is None:
            self.supervisor = self.profile.build_supervisor()

        return self.supervisor

    def run_basic(
        self,
        operation: Callable[[], Any],
        *,
        operation_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProtectedOperationResult:
        """Run operation with base safe execution only."""
        if metadata is not None:
            validate_attributes(metadata)

        result = safe_execute(
            operation,
            operation_name=operation_name,
            component=self.profile.component,
            metadata={
                **self.metadata,
                **(metadata or {}),
            },
        )

        return build_protected_operation_result(
            success=result.success,
            operation=operation_name,
            component=self.profile.component,
            reliability_result=result,
            controls=[
                "safe_execute",
            ],
            value=result.value,
            error=result.error,
            metadata={
                **self.metadata,
                **(metadata or {}),
            },
        )

    def run_with_retry(
        self,
        operation: Callable[[], Any],
        *,
        operation_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> ProtectedOperationResult:
        """Run operation with retry policy."""
        if metadata is not None:
            validate_attributes(metadata)

        retry_result = run_with_retry(
            operation,
            policy=self.profile.retry_policy,
            operation_name=operation_name,
            component=self.profile.component,
            metadata={
                **self.metadata,
                **(metadata or {}),
            },
        )
        reliability_result = retry_result.to_reliability_result()

        return build_protected_operation_result(
            success=retry_result.success,
            operation=operation_name,
            component=self.profile.component,
            reliability_result=reliability_result,
            controls=[
                "retry",
            ],
            value=retry_result.value,
            error=retry_result.error,
            metadata={
                **self.metadata,
                **(metadata or {}),
            },
        )

    def run_supervised(
        self,
        operation: Callable[[], Any],
        *,
        operation_name: str,
        rate_limit_key: str | None = None,
        now: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ProtectedOperationResult:
        """Run operation through runtime supervisor."""
        if metadata is not None:
            validate_attributes(metadata)

        supervisor = self.get_supervisor()
        result = supervisor.supervise(
            operation,
            operation_name=operation_name,
            component=self.profile.component,
            rate_limit_key=rate_limit_key,
            now=now,
            metadata={
                **self.metadata,
                **(metadata or {}),
            },
        )

        return build_protected_operation_result(
            success=result.success,
            operation=operation_name,
            component=self.profile.component,
            reliability_result=result,
            controls=supervisor.enabled_controls(),
            value=result.value,
            error=result.error,
            metadata={
                **self.metadata,
                **(metadata or {}),
            },
        )

    def summary(self) -> dict[str, Any]:
        """Return toolkit summary."""
        return {
            "profile": self.profile.to_dict(),
            "has_supervisor": self.supervisor is not None,
            "supervisor": self.supervisor.summary() if self.supervisor else None,
            "metadata": dict(self.metadata),
        }


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate string list."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def build_reliability_profile(
    *,
    name: str = "default",
    component: str = "runtime",
    retry_policy: RetryPolicy | None = None,
    circuit_breaker_config: CircuitBreakerConfig | None = None,
    rate_limit_config: RateLimitConfig | None = None,
    timeout_config: TimeoutConfig | None = None,
    supervisor_config: RuntimeSupervisorConfig | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReliabilityProfile:
    """Build reliability profile."""
    return ReliabilityProfile(
        name=name,
        component=component,
        retry_policy=retry_policy or RetryPolicy(),
        circuit_breaker_config=circuit_breaker_config or CircuitBreakerConfig(),
        rate_limit_config=rate_limit_config or RateLimitConfig(),
        timeout_config=timeout_config or TimeoutConfig(),
        supervisor_config=supervisor_config or RuntimeSupervisorConfig(),
        metadata=metadata or {},
    )


def build_protected_operation_result(
    *,
    success: bool,
    operation: str,
    component: str,
    reliability_result: ReliabilityResult,
    controls: list[str] | None = None,
    value: Any = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProtectedOperationResult:
    """Build protected operation result."""
    return ProtectedOperationResult(
        success=success,
        operation=operation,
        component=component,
        reliability_result=reliability_result,
        controls=controls or [],
        value=value,
        error=error,
        metadata=metadata or {},
    )


def build_reliability_toolkit(
    *,
    profile: ReliabilityProfile | None = None,
    supervisor: RuntimeSupervisor | None = None,
    metadata: dict[str, Any] | None = None,
) -> ReliabilityToolkit:
    """Build reliability toolkit."""
    return ReliabilityToolkit(
        profile=profile or build_reliability_profile(),
        supervisor=supervisor,
        metadata=metadata or {},
    )


def protect_operation(
    operation: Callable[[], Any],
    *,
    operation_name: str,
    profile: ReliabilityProfile | None = None,
    rate_limit_key: str | None = None,
    now: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProtectedOperationResult:
    """Protect operation using a temporary reliability toolkit."""
    toolkit = build_reliability_toolkit(
        profile=profile or build_reliability_profile(),
    )

    return toolkit.run_supervised(
        operation,
        operation_name=operation_name,
        rate_limit_key=rate_limit_key,
        now=now,
        metadata=metadata,
    )


def compose_reliability_metadata(
    *,
    profile: ReliabilityProfile,
    operation: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose standard reliability metadata."""
    if not isinstance(profile, ReliabilityProfile):
        raise ValueError("Profile must be a ReliabilityProfile.")

    validate_non_empty_string(operation, "Operation")

    if extra is not None:
        validate_attributes(extra)

    return {
        "profile": profile.name.strip(),
        "component": profile.component.strip(),
        "operation": operation.strip(),
        **profile.metadata,
        **(extra or {}),
    }


def reliability_result_from_exception(
    exception: BaseException,
    *,
    operation: str,
    component: str,
    metadata: dict[str, Any] | None = None,
) -> ReliabilityResult:
    """Build reliability result from exception."""
    if not isinstance(exception, BaseException):
        raise ValueError("Exception must be a BaseException.")

    if metadata is not None:
        validate_attributes(metadata)

    return build_reliability_result(
        success=False,
        operation=operation,
        component=component,
        status=ReliabilityStatus.FAILED,
        message="Operation failed with exception.",
        error=str(exception),
        metadata={
            "error_type": exception.__class__.__name__,
            **(metadata or {}),
        },
    )