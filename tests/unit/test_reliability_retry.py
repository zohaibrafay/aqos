"""
Unit tests for AQOS retry primitives.
"""

import pytest

from aqos.reliability import (
    ReliabilityStatus,
    RetryAttempt,
    RetryBackoffStrategy,
    RetryExecutionResult,
    RetryPolicy,
    RetryState,
    build_retry_attempt,
    build_retry_policy,
    build_retry_state,
    calculate_retry_delay,
    normalize_retry_backoff_strategy,
    run_with_retry,
    should_retry_attempt,
    validate_retry_attempts,
    validate_retry_exception_types,
)


def test_retry_backoff_strategy_values():
    assert RetryBackoffStrategy.NONE.value == "none"
    assert RetryBackoffStrategy.CONSTANT.value == "constant"
    assert RetryBackoffStrategy.LINEAR.value == "linear"
    assert RetryBackoffStrategy.EXPONENTIAL.value == "exponential"


def test_normalize_retry_backoff_strategy_accepts_enum_and_string():
    assert normalize_retry_backoff_strategy(RetryBackoffStrategy.NONE) == RetryBackoffStrategy.NONE
    assert normalize_retry_backoff_strategy(" NONE ") == RetryBackoffStrategy.NONE
    assert normalize_retry_backoff_strategy("constant") == RetryBackoffStrategy.CONSTANT
    assert normalize_retry_backoff_strategy("LINEAR") == RetryBackoffStrategy.LINEAR


def test_normalize_retry_backoff_strategy_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_retry_backoff_strategy("bad")

    with pytest.raises(ValueError):
        normalize_retry_backoff_strategy("")


def test_validate_retry_exception_types():
    assert validate_retry_exception_types((Exception, RuntimeError)) == (Exception, RuntimeError)

    with pytest.raises(ValueError):
        validate_retry_exception_types([Exception])

    with pytest.raises(ValueError):
        validate_retry_exception_types(())

    with pytest.raises(ValueError):
        validate_retry_exception_types((str,))


def test_calculate_retry_delay():
    assert calculate_retry_delay(
        attempt_number=1,
        strategy="none",
        initial_delay_seconds=0.5,
        max_delay_seconds=10,
    ) == 0.0

    assert calculate_retry_delay(
        attempt_number=2,
        strategy="constant",
        initial_delay_seconds=0.5,
        max_delay_seconds=10,
    ) == 0.5

    assert calculate_retry_delay(
        attempt_number=3,
        strategy="linear",
        initial_delay_seconds=0.5,
        max_delay_seconds=10,
    ) == 1.5

    assert calculate_retry_delay(
        attempt_number=4,
        strategy="exponential",
        initial_delay_seconds=0.5,
        max_delay_seconds=10,
    ) == 4.0

    assert calculate_retry_delay(
        attempt_number=5,
        strategy="exponential",
        initial_delay_seconds=1,
        max_delay_seconds=3,
    ) == 3.0


def test_calculate_retry_delay_rejects_invalid_values():
    with pytest.raises(ValueError):
        calculate_retry_delay(attempt_number=0)

    with pytest.raises(ValueError):
        calculate_retry_delay(attempt_number=1, strategy="bad")

    with pytest.raises(ValueError):
        calculate_retry_delay(attempt_number=1, initial_delay_seconds=-1)

    with pytest.raises(ValueError):
        calculate_retry_delay(attempt_number=1, max_delay_seconds=-1)


def test_retry_policy_to_dict_and_should_retry_exception():
    policy = RetryPolicy(
        max_attempts=4,
        backoff_strategy="LINEAR",
        initial_delay_seconds=0.25,
        max_delay_seconds=2.0,
        retry_on_exceptions=(RuntimeError,),
        metadata={
            "service": "market-data",
        },
    )

    assert policy.should_retry_exception(RuntimeError("boom")) is True
    assert policy.should_retry_exception(ValueError("bad")) is False
    assert policy.calculate_delay(2) == 0.5

    assert policy.to_dict() == {
        "max_attempts": 4,
        "backoff_strategy": "linear",
        "initial_delay_seconds": 0.25,
        "max_delay_seconds": 2.0,
        "retry_on_exceptions": [
            "RuntimeError",
        ],
        "metadata": {
            "service": "market-data",
        },
    }


def test_retry_policy_rejects_invalid_values():
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)

    with pytest.raises(ValueError):
        RetryPolicy(backoff_strategy="bad")

    with pytest.raises(ValueError):
        RetryPolicy(initial_delay_seconds=-1)

    with pytest.raises(ValueError):
        RetryPolicy(max_delay_seconds=-1)

    with pytest.raises(ValueError):
        RetryPolicy(retry_on_exceptions=[Exception])

    with pytest.raises(ValueError):
        RetryPolicy(metadata=[])

    policy = RetryPolicy()

    with pytest.raises(ValueError):
        policy.should_retry_exception("bad")


def test_build_retry_policy():
    policy = build_retry_policy(
        max_attempts=2,
        backoff_strategy="constant",
        initial_delay_seconds=0.2,
        max_delay_seconds=1.0,
        retry_on_exceptions=(RuntimeError,),
        metadata={
            "source": "test",
        },
    )

    assert isinstance(policy, RetryPolicy)
    assert policy.max_attempts == 2
    assert policy.to_dict()["metadata"] == {
        "source": "test",
    }


def test_retry_attempt_to_dict():
    attempt = RetryAttempt(
        attempt_number=1,
        success=False,
        delay_seconds=0.5,
        error="Network error.",
        error_type="RuntimeError",
        timestamp="2026-01-01T00:00:00+00:00",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert attempt.failed is True
    assert attempt.to_dict() == {
        "attempt_number": 1,
        "success": False,
        "failed": True,
        "delay_seconds": 0.5,
        "error": "Network error.",
        "error_type": "RuntimeError",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_retry_attempt_success_to_dict():
    attempt = RetryAttempt(
        attempt_number=1,
        success=True,
        delay_seconds=0,
        value=123,
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert attempt.failed is False
    assert attempt.to_dict() == {
        "attempt_number": 1,
        "success": True,
        "failed": False,
        "delay_seconds": 0.0,
        "value": 123,
        "timestamp": "2026-01-01T00:00:00+00:00",
        "metadata": {},
    }


def test_retry_attempt_rejects_invalid_values():
    with pytest.raises(ValueError):
        RetryAttempt(attempt_number=0, success=True)

    with pytest.raises(ValueError):
        RetryAttempt(attempt_number=1, success="yes")

    with pytest.raises(ValueError):
        RetryAttempt(attempt_number=1, success=True, delay_seconds=-1)

    with pytest.raises(ValueError):
        RetryAttempt(attempt_number=1, success=False, error="")

    with pytest.raises(ValueError):
        RetryAttempt(attempt_number=1, success=False, error_type="")

    with pytest.raises(ValueError):
        RetryAttempt(attempt_number=1, success=True, timestamp="")

    with pytest.raises(ValueError):
        RetryAttempt(attempt_number=1, success=True, metadata=[])


def test_build_retry_attempt():
    attempt = build_retry_attempt(
        attempt_number=1,
        success=True,
        value="ok",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(attempt, RetryAttempt)
    assert attempt.value == "ok"


def test_validate_retry_attempts():
    attempt = build_retry_attempt(attempt_number=1, success=True)

    assert validate_retry_attempts([attempt]) == [
        attempt,
    ]

    with pytest.raises(ValueError):
        validate_retry_attempts("bad")

    with pytest.raises(ValueError):
        validate_retry_attempts(["bad"])


def test_retry_state_records_attempts_and_completion():
    policy = build_retry_policy(
        max_attempts=2,
        backoff_strategy="constant",
        initial_delay_seconds=0.5,
    )
    state = RetryState(
        operation="fetch-data",
        component="data-service",
        policy=policy,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert state.can_attempt() is True
    assert state.next_attempt_number() == 1
    assert state.next_delay_seconds() == 0.5
    assert state.remaining_attempts == 2

    failed_attempt = build_retry_attempt(
        attempt_number=1,
        success=False,
        error="Network error.",
    )

    assert state.record_attempt(failed_attempt) is failed_attempt
    assert state.completed is False
    assert state.attempt_count == 1
    assert state.remaining_attempts == 1

    success_attempt = build_retry_attempt(
        attempt_number=2,
        success=True,
        value="done",
    )

    state.record_attempt(success_attempt)

    assert state.completed is True
    assert state.succeeded is True
    assert state.failed is False


def test_retry_state_completes_when_max_attempts_reached():
    state = build_retry_state(
        operation="fetch-data",
        component="data-service",
        policy=build_retry_policy(max_attempts=1),
    )

    state.record_attempt(
        build_retry_attempt(
            attempt_number=1,
            success=False,
            error="boom",
        ),
    )

    assert state.completed is True
    assert state.succeeded is False
    assert state.failed is True
    assert state.can_attempt() is False


def test_retry_state_to_dict():
    state = build_retry_state(
        operation="fetch-data",
        component="data-service",
        policy=build_retry_policy(max_attempts=1),
        metadata={
            "symbol": "XAUUSD",
        },
    )

    state.record_attempt(
        build_retry_attempt(
            attempt_number=1,
            success=True,
            value=10,
            timestamp="2026-01-01T00:00:00+00:00",
        ),
    )

    payload = state.to_dict()

    assert payload["operation"] == "fetch-data"
    assert payload["component"] == "data-service"
    assert payload["attempt_count"] == 1
    assert payload["remaining_attempts"] == 0
    assert payload["completed"] is True
    assert payload["succeeded"] is True
    assert payload["metadata"] == {
        "symbol": "XAUUSD",
    }


def test_retry_state_rejects_invalid_values():
    with pytest.raises(ValueError):
        RetryState(operation="", component="service")

    with pytest.raises(ValueError):
        RetryState(operation="operation", component="")

    with pytest.raises(ValueError):
        RetryState(operation="operation", component="service", policy="bad")

    with pytest.raises(ValueError):
        RetryState(operation="operation", component="service", attempts=["bad"])

    with pytest.raises(ValueError):
        RetryState(operation="operation", component="service", completed="yes")

    with pytest.raises(ValueError):
        RetryState(operation="operation", component="service", metadata=[])

    state = build_retry_state(operation="operation", component="service")

    with pytest.raises(ValueError):
        state.record_attempt("bad")

    with pytest.raises(ValueError):
        state.record_attempt(
            build_retry_attempt(
                attempt_number=2,
                success=True,
            ),
        )


def test_build_retry_state():
    state = build_retry_state(
        operation="operation",
        component="service",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(state, RetryState)
    assert state.operation == "operation"
    assert state.metadata == {
        "source": "test",
    }


def test_should_retry_attempt():
    policy = build_retry_policy(
        max_attempts=3,
        retry_on_exceptions=(RuntimeError,),
    )

    assert should_retry_attempt(
        policy=policy,
        attempt_number=1,
        exception=RuntimeError("boom"),
    ) is True

    assert should_retry_attempt(
        policy=policy,
        attempt_number=3,
        exception=RuntimeError("boom"),
    ) is False

    assert should_retry_attempt(
        policy=policy,
        attempt_number=1,
        exception=ValueError("bad"),
    ) is False


def test_should_retry_attempt_rejects_invalid_values():
    policy = RetryPolicy()

    with pytest.raises(ValueError):
        should_retry_attempt(
            policy="bad",
            attempt_number=1,
            exception=RuntimeError("boom"),
        )

    with pytest.raises(ValueError):
        should_retry_attempt(
            policy=policy,
            attempt_number=0,
            exception=RuntimeError("boom"),
        )

    with pytest.raises(ValueError):
        should_retry_attempt(
            policy=policy,
            attempt_number=1,
            exception="bad",
        )


def test_retry_execution_result_to_dict_and_reliability_result():
    attempts = [
        build_retry_attempt(
            attempt_number=1,
            success=True,
            value=10,
            timestamp="2026-01-01T00:00:00+00:00",
        ),
    ]

    result = RetryExecutionResult(
        success=True,
        operation="calculate",
        component="math",
        attempts=attempts,
        value=10,
        metadata={
            "source": "test",
        },
    )

    assert result.failed is False
    assert result.attempt_count == 1
    assert result.to_dict()["value"] == 10

    reliability_result = result.to_reliability_result()

    assert reliability_result.success is True
    assert reliability_result.status == ReliabilityStatus.OK
    assert reliability_result.metadata["attempt_count"] == 1


def test_retry_execution_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        RetryExecutionResult(
            success="yes",
            operation="operation",
            component="service",
            attempts=[],
        )

    with pytest.raises(ValueError):
        RetryExecutionResult(
            success=True,
            operation="",
            component="service",
            attempts=[],
        )

    with pytest.raises(ValueError):
        RetryExecutionResult(
            success=True,
            operation="operation",
            component="",
            attempts=[],
        )

    with pytest.raises(ValueError):
        RetryExecutionResult(
            success=True,
            operation="operation",
            component="service",
            attempts=["bad"],
        )

    with pytest.raises(ValueError):
        RetryExecutionResult(
            success=False,
            operation="operation",
            component="service",
            attempts=[],
            error="",
        )

    with pytest.raises(ValueError):
        RetryExecutionResult(
            success=True,
            operation="operation",
            component="service",
            attempts=[],
            metadata=[],
        )


def test_run_with_retry_success_first_attempt():
    result = run_with_retry(
        lambda: 10,
        policy=build_retry_policy(max_attempts=3),
        operation_name="calculate",
        component="math",
        metadata={
            "source": "test",
        },
    )

    assert result.success is True
    assert result.value == 10
    assert result.attempt_count == 1
    assert result.attempts[0].success is True
    assert result.metadata["source"] == "test"


def test_run_with_retry_success_after_failures():
    calls = {
        "count": 0,
    }

    def flaky():
        calls["count"] += 1

        if calls["count"] < 3:
            raise RuntimeError("temporary")

        return "ok"

    result = run_with_retry(
        flaky,
        policy=build_retry_policy(
            max_attempts=3,
            backoff_strategy="constant",
            initial_delay_seconds=0.2,
            retry_on_exceptions=(RuntimeError,),
        ),
        operation_name="flaky-op",
        component="test",
    )

    assert result.success is True
    assert result.value == "ok"
    assert result.attempt_count == 3
    assert [
        attempt.success
        for attempt in result.attempts
    ] == [
        False,
        False,
        True,
    ]


def test_run_with_retry_failure_when_max_attempts_reached():
    def fail():
        raise RuntimeError("boom")

    result = run_with_retry(
        fail,
        policy=build_retry_policy(
            max_attempts=2,
            retry_on_exceptions=(RuntimeError,),
        ),
        operation_name="fail-op",
        component="test",
    )

    assert result.success is False
    assert result.failed is True
    assert result.error == "boom"
    assert result.attempt_count == 2


def test_run_with_retry_stops_on_non_retryable_exception():
    def fail():
        raise ValueError("bad")

    result = run_with_retry(
        fail,
        policy=build_retry_policy(
            max_attempts=3,
            retry_on_exceptions=(RuntimeError,),
        ),
        operation_name="fail-op",
        component="test",
    )

    assert result.success is False
    assert result.error == "bad"
    assert result.attempt_count == 1


def test_run_with_retry_rejects_invalid_values():
    with pytest.raises(ValueError):
        run_with_retry(
            "bad",
            operation_name="operation",
            component="service",
        )

    with pytest.raises(ValueError):
        run_with_retry(
            lambda: None,
            operation_name="",
            component="service",
        )

    with pytest.raises(ValueError):
        run_with_retry(
            lambda: None,
            operation_name="operation",
            component="",
        )

    with pytest.raises(ValueError):
        run_with_retry(
            lambda: None,
            operation_name="operation",
            component="service",
            metadata=[],
        )


def test_reliability_retry_exports_exist():
    import aqos.reliability as reliability

    expected_exports = [
        "RetryAttempt",
        "RetryBackoffStrategy",
        "RetryExecutionResult",
        "RetryPolicy",
        "RetryState",
        "build_retry_attempt",
        "build_retry_policy",
        "build_retry_state",
        "calculate_retry_delay",
        "normalize_retry_backoff_strategy",
        "run_with_retry",
        "should_retry_attempt",
        "validate_retry_attempts",
        "validate_retry_exception_types",
    ]

    for export_name in expected_exports:
        assert hasattr(reliability, export_name), export_name