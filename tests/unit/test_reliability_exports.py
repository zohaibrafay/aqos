"""
Unit tests for AQOS reliability package exports.
"""

import inspect

import aqos.reliability as reliability


EXPECTED_RELIABILITY_EXPORTS = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerEvent",
    "CircuitBreakerEventType",
    "CircuitBreakerState",
    "CircuitBreakerStats",
    "Deadline",
    "DeadlineCheckResult",
    "ProtectedOperationResult",
    "RateLimitBucket",
    "RateLimitConfig",
    "RateLimitDecision",
    "RateLimitResult",
    "RateLimiter",
    "ReliabilityEvent",
    "ReliabilityProfile",
    "ReliabilityResult",
    "ReliabilitySeverity",
    "ReliabilityStatus",
    "ReliabilityToolkit",
    "RetryAttempt",
    "RetryBackoffStrategy",
    "RetryExecutionResult",
    "RetryPolicy",
    "RetryState",
    "RuntimeSupervisor",
    "RuntimeSupervisorConfig",
    "SupervisionRecord",
    "SupervisorEvent",
    "SupervisorEventType",
    "SupervisorState",
    "TimeoutConfig",
    "TimeoutExecutionResult",
    "TimeoutState",
    "build_circuit_breaker",
    "build_circuit_breaker_config",
    "build_circuit_breaker_event",
    "build_circuit_breaker_stats",
    "build_deadline",
    "build_deadline_check_result",
    "build_protected_operation_result",
    "build_rate_limit_bucket",
    "build_rate_limit_config",
    "build_rate_limit_result",
    "build_rate_limiter",
    "build_reliability_event",
    "build_reliability_profile",
    "build_reliability_result",
    "build_reliability_toolkit",
    "build_retry_attempt",
    "build_retry_callable",
    "build_retry_policy",
    "build_retry_state",
    "build_runtime_supervisor",
    "build_runtime_supervisor_config",
    "build_supervision_record",
    "build_supervisor_event",
    "build_supervisor_key",
    "build_timeout_config",
    "build_timeout_execution_result",
    "calculate_deadline_at",
    "calculate_elapsed_seconds",
    "calculate_rate_limit_reset_at",
    "calculate_remaining_seconds",
    "calculate_retry_after_seconds",
    "calculate_retry_delay",
    "compose_reliability_metadata",
    "execute_with_deadline",
    "is_deadline_expired",
    "is_rate_limit_window_expired",
    "normalize_circuit_breaker_event_type",
    "normalize_circuit_breaker_state",
    "normalize_rate_limit_decision",
    "normalize_reliability_severity",
    "normalize_reliability_status",
    "normalize_retry_backoff_strategy",
    "normalize_supervisor_event_type",
    "normalize_supervisor_state",
    "normalize_supervisor_timestamp",
    "normalize_timeout_state",
    "parse_circuit_datetime",
    "parse_rate_limit_datetime",
    "parse_timeout_datetime",
    "protect_operation",
    "reliability_result_from_exception",
    "run_with_retry",
    "safe_execute",
    "should_retry_attempt",
    "validate_attributes",
    "validate_boolean",
    "validate_circuit_breaker_events",
    "validate_non_empty_string",
    "validate_non_negative_float",
    "validate_non_negative_integer",
    "validate_positive_integer",
    "validate_rate_limit_key",
    "validate_retry_attempts",
    "validate_retry_exception_types",
    "validate_string",
    "validate_string_list",
    "validate_supervision_records",
    "validate_supervisor_events",
    "validate_timeout_seconds",
]


CLASS_EXPORTS = [
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerEvent",
    "CircuitBreakerEventType",
    "CircuitBreakerState",
    "CircuitBreakerStats",
    "Deadline",
    "DeadlineCheckResult",
    "ProtectedOperationResult",
    "RateLimitBucket",
    "RateLimitConfig",
    "RateLimitDecision",
    "RateLimitResult",
    "RateLimiter",
    "ReliabilityEvent",
    "ReliabilityProfile",
    "ReliabilityResult",
    "ReliabilitySeverity",
    "ReliabilityStatus",
    "ReliabilityToolkit",
    "RetryAttempt",
    "RetryBackoffStrategy",
    "RetryExecutionResult",
    "RetryPolicy",
    "RetryState",
    "RuntimeSupervisor",
    "RuntimeSupervisorConfig",
    "SupervisionRecord",
    "SupervisorEvent",
    "SupervisorEventType",
    "SupervisorState",
    "TimeoutConfig",
    "TimeoutExecutionResult",
    "TimeoutState",
]


FUNCTION_EXPORTS = [
    export_name
    for export_name in EXPECTED_RELIABILITY_EXPORTS
    if export_name not in CLASS_EXPORTS
]


def test_reliability_exports_are_complete():
    assert reliability.__all__ == EXPECTED_RELIABILITY_EXPORTS


def test_reliability_exports_are_sorted():
    assert reliability.__all__ == sorted(reliability.__all__)


def test_reliability_exports_are_unique():
    assert len(reliability.__all__) == len(set(reliability.__all__))


def test_reliability_exports_exist_on_package():
    for export_name in EXPECTED_RELIABILITY_EXPORTS:
        assert hasattr(reliability, export_name), export_name


def test_reliability_class_exports_are_classes():
    for export_name in CLASS_EXPORTS:
        assert inspect.isclass(getattr(reliability, export_name)), export_name


def test_reliability_function_exports_are_callables():
    for export_name in FUNCTION_EXPORTS:
        assert callable(getattr(reliability, export_name)), export_name


def test_reliability_core_exports_import_directly():
    from aqos.reliability import (  # noqa: PLC0415
        CircuitBreaker,
        Deadline,
        RateLimiter,
        ReliabilityProfile,
        ReliabilityResult,
        RetryPolicy,
        RuntimeSupervisor,
    )

    assert CircuitBreaker.__name__ == "CircuitBreaker"
    assert Deadline.__name__ == "Deadline"
    assert RateLimiter.__name__ == "RateLimiter"
    assert ReliabilityProfile.__name__ == "ReliabilityProfile"
    assert ReliabilityResult.__name__ == "ReliabilityResult"
    assert RetryPolicy.__name__ == "RetryPolicy"
    assert RuntimeSupervisor.__name__ == "RuntimeSupervisor"


def test_reliability_export_groups_exist():
    base_exports = {
        "ReliabilityEvent",
        "ReliabilityResult",
        "ReliabilitySeverity",
        "ReliabilityStatus",
    }
    retry_exports = {
        "RetryAttempt",
        "RetryBackoffStrategy",
        "RetryExecutionResult",
        "RetryPolicy",
        "RetryState",
    }
    circuit_breaker_exports = {
        "CircuitBreaker",
        "CircuitBreakerConfig",
        "CircuitBreakerEvent",
        "CircuitBreakerStats",
    }
    rate_limit_exports = {
        "RateLimitBucket",
        "RateLimitConfig",
        "RateLimitDecision",
        "RateLimitResult",
        "RateLimiter",
    }
    timeout_exports = {
        "Deadline",
        "DeadlineCheckResult",
        "TimeoutConfig",
        "TimeoutExecutionResult",
        "TimeoutState",
    }
    supervisor_exports = {
        "RuntimeSupervisor",
        "RuntimeSupervisorConfig",
        "SupervisionRecord",
        "SupervisorEvent",
        "SupervisorState",
    }
    integration_exports = {
        "ProtectedOperationResult",
        "ReliabilityProfile",
        "ReliabilityToolkit",
    }

    exports = set(reliability.__all__)

    assert base_exports.issubset(exports)
    assert retry_exports.issubset(exports)
    assert circuit_breaker_exports.issubset(exports)
    assert rate_limit_exports.issubset(exports)
    assert timeout_exports.issubset(exports)
    assert supervisor_exports.issubset(exports)
    assert integration_exports.issubset(exports)