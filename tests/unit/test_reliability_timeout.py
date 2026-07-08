"""
Unit tests for AQOS timeout and deadline primitives.
"""

import pytest

from aqos.reliability import (
    Deadline,
    DeadlineCheckResult,
    ReliabilityStatus,
    TimeoutConfig,
    TimeoutExecutionResult,
    TimeoutState,
    build_deadline,
    build_deadline_check_result,
    build_timeout_config,
    build_timeout_execution_result,
    calculate_deadline_at,
    calculate_elapsed_seconds,
    calculate_remaining_seconds,
    execute_with_deadline,
    is_deadline_expired,
    normalize_timeout_state,
    parse_timeout_datetime,
    validate_timeout_seconds,
)


def test_timeout_state_values():
    assert TimeoutState.ACTIVE.value == "active"
    assert TimeoutState.EXPIRED.value == "expired"
    assert TimeoutState.CANCELLED.value == "cancelled"
    assert TimeoutState.COMPLETED.value == "completed"


def test_normalize_timeout_state_accepts_enum_and_string():
    assert normalize_timeout_state(TimeoutState.ACTIVE) == TimeoutState.ACTIVE
    assert normalize_timeout_state(" ACTIVE ") == TimeoutState.ACTIVE
    assert normalize_timeout_state("expired") == TimeoutState.EXPIRED
    assert normalize_timeout_state("CANCELLED") == TimeoutState.CANCELLED


def test_normalize_timeout_state_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_timeout_state("bad")

    with pytest.raises(ValueError):
        normalize_timeout_state("")


def test_validate_timeout_seconds():
    assert validate_timeout_seconds(1) == 1.0
    assert validate_timeout_seconds(1.5) == 1.5

    with pytest.raises(ValueError):
        validate_timeout_seconds(0)

    with pytest.raises(ValueError):
        validate_timeout_seconds(-1)

    with pytest.raises(ValueError):
        validate_timeout_seconds(True)


def test_parse_timeout_datetime():
    parsed = parse_timeout_datetime("2026-01-01T00:00:00+00:00")

    assert parsed.isoformat() == "2026-01-01T00:00:00+00:00"

    parsed_naive = parse_timeout_datetime("2026-01-01T00:00:00")

    assert parsed_naive.isoformat() == "2026-01-01T00:00:00+00:00"

    with pytest.raises(ValueError):
        parse_timeout_datetime("")


def test_timeout_time_helpers():
    started_at = "2026-01-01T00:00:00+00:00"

    assert calculate_deadline_at(
        started_at,
        60,
    ) == "2026-01-01T00:01:00+00:00"

    assert calculate_elapsed_seconds(
        started_at,
        now="2026-01-01T00:00:30+00:00",
    ) == 30.0

    assert calculate_remaining_seconds(
        started_at,
        60,
        now="2026-01-01T00:00:30+00:00",
    ) == 30.0

    assert calculate_remaining_seconds(
        started_at,
        60,
        now="2026-01-01T00:02:00+00:00",
    ) == 0.0

    assert is_deadline_expired(
        started_at,
        60,
        now="2026-01-01T00:00:59+00:00",
    ) is False

    assert is_deadline_expired(
        started_at,
        60,
        now="2026-01-01T00:01:00+00:00",
    ) is True

    assert is_deadline_expired(
        started_at,
        60,
        grace_seconds=10,
        now="2026-01-01T00:01:05+00:00",
    ) is False


def test_timeout_config_to_dict():
    config = TimeoutConfig(
        timeout_seconds=10,
        grace_seconds=2,
        metadata={
            "service": "market-data",
        },
    )

    assert config.to_dict() == {
        "timeout_seconds": 10.0,
        "grace_seconds": 2.0,
        "metadata": {
            "service": "market-data",
        },
    }


def test_timeout_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        TimeoutConfig(timeout_seconds=0)

    with pytest.raises(ValueError):
        TimeoutConfig(grace_seconds=-1)

    with pytest.raises(ValueError):
        TimeoutConfig(metadata=[])


def test_build_timeout_config():
    config = build_timeout_config(
        timeout_seconds=5,
        grace_seconds=1,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(config, TimeoutConfig)
    assert config.to_dict()["metadata"] == {
        "source": "test",
    }


def test_deadline_check_result_to_dict_and_reliability_result():
    result = DeadlineCheckResult(
        expired=False,
        operation="fetch-data",
        component="data-service",
        state="ACTIVE",
        elapsed_seconds=5,
        remaining_seconds=10,
        deadline_at="2026-01-01T00:00:15+00:00",
        checked_at="2026-01-01T00:00:05+00:00",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert result.active is True

    assert result.to_dict() == {
        "expired": False,
        "active": True,
        "operation": "fetch-data",
        "component": "data-service",
        "state": "active",
        "elapsed_seconds": 5.0,
        "remaining_seconds": 10.0,
        "deadline_at": "2026-01-01T00:00:15+00:00",
        "checked_at": "2026-01-01T00:00:05+00:00",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }

    reliability_result = result.to_reliability_result()

    assert reliability_result.success is True
    assert reliability_result.status == ReliabilityStatus.OK


def test_deadline_check_result_expired_reliability_result():
    result = DeadlineCheckResult(
        expired=True,
        operation="fetch-data",
        component="data-service",
        state="expired",
        elapsed_seconds=15,
        remaining_seconds=0,
        deadline_at="2026-01-01T00:00:10+00:00",
        checked_at="2026-01-01T00:00:15+00:00",
    )

    reliability_result = result.to_reliability_result()

    assert reliability_result.success is False
    assert reliability_result.status == ReliabilityStatus.DEGRADED
    assert reliability_result.error == "Operation deadline expired."


def test_deadline_check_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired="yes",
            operation="operation",
            component="service",
            state="active",
            elapsed_seconds=0,
            remaining_seconds=1,
            deadline_at="2026-01-01T00:00:01+00:00",
            checked_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired=False,
            operation="",
            component="service",
            state="active",
            elapsed_seconds=0,
            remaining_seconds=1,
            deadline_at="2026-01-01T00:00:01+00:00",
            checked_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired=False,
            operation="operation",
            component="",
            state="active",
            elapsed_seconds=0,
            remaining_seconds=1,
            deadline_at="2026-01-01T00:00:01+00:00",
            checked_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired=False,
            operation="operation",
            component="service",
            state="bad",
            elapsed_seconds=0,
            remaining_seconds=1,
            deadline_at="2026-01-01T00:00:01+00:00",
            checked_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired=False,
            operation="operation",
            component="service",
            state="active",
            elapsed_seconds=-1,
            remaining_seconds=1,
            deadline_at="2026-01-01T00:00:01+00:00",
            checked_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired=False,
            operation="operation",
            component="service",
            state="active",
            elapsed_seconds=0,
            remaining_seconds=1,
            deadline_at="",
            checked_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired=False,
            operation="operation",
            component="service",
            state="active",
            elapsed_seconds=0,
            remaining_seconds=1,
            deadline_at="2026-01-01T00:00:01+00:00",
            checked_at="",
        )

    with pytest.raises(ValueError):
        DeadlineCheckResult(
            expired=False,
            operation="operation",
            component="service",
            state="active",
            elapsed_seconds=0,
            remaining_seconds=1,
            deadline_at="2026-01-01T00:00:01+00:00",
            checked_at="2026-01-01T00:00:00+00:00",
            metadata=[],
        )


def test_build_deadline_check_result():
    result = build_deadline_check_result(
        expired=False,
        operation="operation",
        component="service",
        state="active",
        elapsed_seconds=0,
        remaining_seconds=10,
        deadline_at="2026-01-01T00:00:10+00:00",
        checked_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(result, DeadlineCheckResult)
    assert result.expired is False


def test_deadline_to_dict_and_check_active():
    deadline = Deadline(
        operation=" fetch-data ",
        component=" data-service ",
        config=build_timeout_config(
            timeout_seconds=10,
            grace_seconds=2,
        ),
        started_at="2026-01-01T00:00:00+00:00",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    check = deadline.check(
        now="2026-01-01T00:00:05+00:00",
    )

    assert deadline.active is True
    assert deadline.deadline_at() == "2026-01-01T00:00:10+00:00"
    assert deadline.expires_at() == "2026-01-01T00:00:12+00:00"
    assert check.expired is False
    assert check.elapsed_seconds == 5.0
    assert check.remaining_seconds == 7.0

    payload = deadline.to_dict()

    assert payload["operation"] == "fetch-data"
    assert payload["component"] == "data-service"
    assert payload["state"] == "active"
    assert payload["metadata"] == {
        "symbol": "XAUUSD",
    }


def test_deadline_check_marks_expired():
    deadline = build_deadline(
        operation="fetch-data",
        component="data-service",
        config=build_timeout_config(timeout_seconds=10),
        started_at="2026-01-01T00:00:00+00:00",
    )

    check = deadline.check(
        now="2026-01-01T00:00:10+00:00",
    )

    assert check.expired is True
    assert deadline.expired is True
    assert deadline.active is False


def test_deadline_complete_cancel_and_reset():
    deadline = build_deadline(
        operation="operation",
        component="service",
        started_at="2026-01-01T00:00:00+00:00",
    )

    deadline.complete()

    assert deadline.completed is True

    deadline.cancel()

    assert deadline.cancelled is True

    deadline.reset(
        started_at="2026-01-01T00:01:00+00:00",
    )

    assert deadline.active is True
    assert deadline.started_at == "2026-01-01T00:01:00+00:00"


def test_deadline_rejects_invalid_values():
    with pytest.raises(ValueError):
        Deadline(operation="", component="service")

    with pytest.raises(ValueError):
        Deadline(operation="operation", component="")

    with pytest.raises(ValueError):
        Deadline(operation="operation", component="service", config="bad")

    with pytest.raises(ValueError):
        Deadline(operation="operation", component="service", started_at="")

    with pytest.raises(ValueError):
        Deadline(operation="operation", component="service", state="bad")

    with pytest.raises(ValueError):
        Deadline(operation="operation", component="service", metadata=[])


def test_build_deadline():
    deadline = build_deadline(
        operation="operation",
        component="service",
        config=build_timeout_config(timeout_seconds=5),
        started_at="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(deadline, Deadline)
    assert deadline.metadata == {
        "source": "test",
    }


def test_timeout_execution_result_to_dict_and_reliability_result():
    check = build_deadline_check_result(
        expired=False,
        operation="operation",
        component="service",
        state="active",
        elapsed_seconds=1,
        remaining_seconds=9,
        deadline_at="2026-01-01T00:00:10+00:00",
        checked_at="2026-01-01T00:00:01+00:00",
    )

    result = TimeoutExecutionResult(
        success=True,
        operation="operation",
        component="service",
        deadline_check=check,
        value=10,
        metadata={
            "source": "test",
        },
    )

    assert result.failed is False
    assert result.to_dict()["value"] == 10

    reliability_result = result.to_reliability_result()

    assert reliability_result.success is True
    assert reliability_result.status == ReliabilityStatus.OK


def test_timeout_execution_result_rejects_invalid_values():
    check = build_deadline_check_result(
        expired=False,
        operation="operation",
        component="service",
        state="active",
        elapsed_seconds=0,
        remaining_seconds=1,
        deadline_at="2026-01-01T00:00:01+00:00",
        checked_at="2026-01-01T00:00:00+00:00",
    )

    with pytest.raises(ValueError):
        TimeoutExecutionResult(
            success="yes",
            operation="operation",
            component="service",
            deadline_check=check,
        )

    with pytest.raises(ValueError):
        TimeoutExecutionResult(
            success=True,
            operation="",
            component="service",
            deadline_check=check,
        )

    with pytest.raises(ValueError):
        TimeoutExecutionResult(
            success=True,
            operation="operation",
            component="",
            deadline_check=check,
        )

    with pytest.raises(ValueError):
        TimeoutExecutionResult(
            success=True,
            operation="operation",
            component="service",
            deadline_check="bad",
        )

    with pytest.raises(ValueError):
        TimeoutExecutionResult(
            success=False,
            operation="operation",
            component="service",
            deadline_check=check,
            error="",
        )

    with pytest.raises(ValueError):
        TimeoutExecutionResult(
            success=True,
            operation="operation",
            component="service",
            deadline_check=check,
            metadata=[],
        )


def test_build_timeout_execution_result():
    check = build_deadline_check_result(
        expired=False,
        operation="operation",
        component="service",
        state="active",
        elapsed_seconds=0,
        remaining_seconds=1,
        deadline_at="2026-01-01T00:00:01+00:00",
        checked_at="2026-01-01T00:00:00+00:00",
    )

    result = build_timeout_execution_result(
        success=True,
        operation="operation",
        component="service",
        deadline_check=check,
        value="ok",
    )

    assert isinstance(result, TimeoutExecutionResult)
    assert result.value == "ok"


def test_execute_with_deadline_success():
    deadline = build_deadline(
        operation="operation",
        component="service",
        config=build_timeout_config(timeout_seconds=10),
        started_at="2026-01-01T00:00:00+00:00",
    )

    result = execute_with_deadline(
        lambda: 10,
        deadline=deadline,
        now="2026-01-01T00:00:05+00:00",
        metadata={
            "source": "test",
        },
    )

    assert result.success is True
    assert result.value == 10
    assert deadline.completed is True
    assert result.metadata == {
        "source": "test",
    }


def test_execute_with_deadline_expired_before_execution():
    called = {
        "value": False,
    }

    def operation():
        called["value"] = True
        return 10

    deadline = build_deadline(
        operation="operation",
        component="service",
        config=build_timeout_config(timeout_seconds=1),
        started_at="2026-01-01T00:00:00+00:00",
    )

    result = execute_with_deadline(
        operation,
        deadline=deadline,
        now="2026-01-01T00:00:02+00:00",
    )

    assert result.success is False
    assert result.error == "Operation deadline expired."
    assert called["value"] is False
    assert deadline.expired is True


def test_execute_with_deadline_cancelled():
    deadline = build_deadline(
        operation="operation",
        component="service",
        started_at="2026-01-01T00:00:00+00:00",
    )
    deadline.cancel()

    result = execute_with_deadline(
        lambda: 10,
        deadline=deadline,
        now="2026-01-01T00:00:00+00:00",
    )

    assert result.success is False
    assert result.error == "Deadline is not active."


def test_execute_with_deadline_operation_failure():
    deadline = build_deadline(
        operation="operation",
        component="service",
        started_at="2026-01-01T00:00:00+00:00",
    )

    def fail():
        raise RuntimeError("boom")

    result = execute_with_deadline(
        fail,
        deadline=deadline,
        now="2026-01-01T00:00:00+00:00",
    )

    assert result.success is False
    assert result.error == "boom"
    assert result.metadata == {
        "error_type": "RuntimeError",
    }


def test_execute_with_deadline_rejects_invalid_values():
    deadline = build_deadline(
        operation="operation",
        component="service",
    )

    with pytest.raises(ValueError):
        execute_with_deadline(
            "bad",
            deadline=deadline,
        )

    with pytest.raises(ValueError):
        execute_with_deadline(
            lambda: None,
            deadline="bad",
        )

    with pytest.raises(ValueError):
        execute_with_deadline(
            lambda: None,
            deadline=deadline,
            metadata=[],
        )


def test_reliability_timeout_exports_exist():
    import aqos.reliability as reliability

    expected_exports = [
        "Deadline",
        "DeadlineCheckResult",
        "TimeoutConfig",
        "TimeoutExecutionResult",
        "TimeoutState",
        "build_deadline",
        "build_deadline_check_result",
        "build_timeout_config",
        "build_timeout_execution_result",
        "calculate_deadline_at",
        "calculate_elapsed_seconds",
        "calculate_remaining_seconds",
        "execute_with_deadline",
        "is_deadline_expired",
        "normalize_timeout_state",
        "parse_timeout_datetime",
        "validate_timeout_seconds",
    ]

    for export_name in expected_exports:
        assert hasattr(reliability, export_name), export_name