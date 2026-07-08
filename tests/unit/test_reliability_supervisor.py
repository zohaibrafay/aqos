"""
Unit tests for AQOS runtime supervisor primitives.
"""

import pytest

from aqos.reliability import (
    ReliabilityStatus,
    RuntimeSupervisor,
    RuntimeSupervisorConfig,
    SupervisionRecord,
    SupervisorEvent,
    SupervisorEventType,
    SupervisorState,
    build_rate_limit_config,
    build_retry_callable,
    build_retry_policy,
    build_runtime_supervisor,
    build_runtime_supervisor_config,
    build_supervision_record,
    build_supervisor_event,
    build_supervisor_key,
    normalize_supervisor_event_type,
    normalize_supervisor_state,
    normalize_supervisor_timestamp,
    validate_boolean,
    validate_supervision_records,
    validate_supervisor_events,
)


def test_supervisor_state_values():
    assert SupervisorState.IDLE.value == "idle"
    assert SupervisorState.RUNNING.value == "running"
    assert SupervisorState.COMPLETED.value == "completed"
    assert SupervisorState.FAILED.value == "failed"
    assert SupervisorState.DEGRADED.value == "degraded"


def test_supervisor_event_type_values():
    assert SupervisorEventType.STARTED.value == "started"
    assert SupervisorEventType.COMPLETED.value == "completed"
    assert SupervisorEventType.FAILED.value == "failed"
    assert SupervisorEventType.DEGRADED.value == "degraded"
    assert SupervisorEventType.REGISTERED.value == "registered"
    assert SupervisorEventType.CLEARED.value == "cleared"


def test_normalize_supervisor_state_accepts_enum_and_string():
    assert normalize_supervisor_state(SupervisorState.IDLE) == SupervisorState.IDLE
    assert normalize_supervisor_state(" IDLE ") == SupervisorState.IDLE
    assert normalize_supervisor_state("running") == SupervisorState.RUNNING
    assert normalize_supervisor_state("FAILED") == SupervisorState.FAILED


def test_normalize_supervisor_state_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_supervisor_state("bad")

    with pytest.raises(ValueError):
        normalize_supervisor_state("")


def test_normalize_supervisor_event_type_accepts_enum_and_string():
    assert normalize_supervisor_event_type(SupervisorEventType.STARTED) == SupervisorEventType.STARTED
    assert normalize_supervisor_event_type(" STARTED ") == SupervisorEventType.STARTED
    assert normalize_supervisor_event_type("completed") == SupervisorEventType.COMPLETED
    assert normalize_supervisor_event_type("FAILED") == SupervisorEventType.FAILED


def test_normalize_supervisor_event_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_supervisor_event_type("bad")

    with pytest.raises(ValueError):
        normalize_supervisor_event_type("")


def test_validate_boolean():
    assert validate_boolean(True, "Enabled") is True
    assert validate_boolean(False, "Enabled") is False

    with pytest.raises(ValueError):
        validate_boolean("yes", "Enabled")


def test_build_supervisor_key_and_timestamp():
    assert build_supervisor_key(
        operation="fetch-data",
        component="data-service",
    ) == "data-service:fetch-data"

    assert normalize_supervisor_timestamp("2026-01-01T00:00:00+00:00") == "2026-01-01T00:00:00+00:00"

    with pytest.raises(ValueError):
        build_supervisor_key(
            operation="",
            component="data-service",
        )

    with pytest.raises(ValueError):
        normalize_supervisor_timestamp("")


def test_supervisor_event_to_dict():
    event = SupervisorEvent(
        event_type="STARTED",
        operation=" fetch-data ",
        component=" data-service ",
        state="RUNNING",
        message=" Started. ",
        timestamp="2026-01-01T00:00:00+00:00",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert event.to_dict() == {
        "event_type": "started",
        "operation": "fetch-data",
        "component": "data-service",
        "state": "running",
        "message": "Started.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_supervisor_event_rejects_invalid_values():
    with pytest.raises(ValueError):
        SupervisorEvent(
            event_type="bad",
            operation="operation",
            component="service",
            state="running",
        )

    with pytest.raises(ValueError):
        SupervisorEvent(
            event_type="started",
            operation="",
            component="service",
            state="running",
        )

    with pytest.raises(ValueError):
        SupervisorEvent(
            event_type="started",
            operation="operation",
            component="",
            state="running",
        )

    with pytest.raises(ValueError):
        SupervisorEvent(
            event_type="started",
            operation="operation",
            component="service",
            state="bad",
        )

    with pytest.raises(ValueError):
        SupervisorEvent(
            event_type="started",
            operation="operation",
            component="service",
            state="running",
            message=123,
        )

    with pytest.raises(ValueError):
        SupervisorEvent(
            event_type="started",
            operation="operation",
            component="service",
            state="running",
            timestamp="",
        )

    with pytest.raises(ValueError):
        SupervisorEvent(
            event_type="started",
            operation="operation",
            component="service",
            state="running",
            metadata=[],
        )


def test_build_supervisor_event():
    event = build_supervisor_event(
        event_type="started",
        operation="operation",
        component="service",
        state="running",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(event, SupervisorEvent)
    assert event.to_dict()["event_type"] == "started"


def test_runtime_supervisor_config_to_dict():
    config = RuntimeSupervisorConfig(
        enable_retry=True,
        enable_circuit_breaker=False,
        enable_rate_limiter=True,
        enable_deadline=False,
        default_component="api",
        metadata={
            "env": "test",
        },
    )

    assert config.to_dict() == {
        "enable_retry": True,
        "enable_circuit_breaker": False,
        "enable_rate_limiter": True,
        "enable_deadline": False,
        "default_component": "api",
        "metadata": {
            "env": "test",
        },
    }


def test_runtime_supervisor_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        RuntimeSupervisorConfig(enable_retry="yes")

    with pytest.raises(ValueError):
        RuntimeSupervisorConfig(enable_circuit_breaker="yes")

    with pytest.raises(ValueError):
        RuntimeSupervisorConfig(enable_rate_limiter="yes")

    with pytest.raises(ValueError):
        RuntimeSupervisorConfig(enable_deadline="yes")

    with pytest.raises(ValueError):
        RuntimeSupervisorConfig(default_component="")

    with pytest.raises(ValueError):
        RuntimeSupervisorConfig(metadata=[])


def test_build_runtime_supervisor_config():
    config = build_runtime_supervisor_config(
        enable_retry=False,
        default_component="api",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(config, RuntimeSupervisorConfig)
    assert config.enable_retry is False
    assert config.metadata == {
        "source": "test",
    }


def test_supervision_record_to_dict_and_reliability_result():
    record = SupervisionRecord(
        operation=" fetch-data ",
        component=" data-service ",
        state="COMPLETED",
        success=True,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:00+00:00",
        duration_seconds=0,
        value={
            "rows": 10,
        },
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert record.failed is False

    assert record.to_dict() == {
        "operation": "fetch-data",
        "component": "data-service",
        "state": "completed",
        "success": True,
        "failed": False,
        "started_at": "2026-01-01T00:00:00+00:00",
        "finished_at": "2026-01-01T00:00:00+00:00",
        "duration_seconds": 0.0,
        "value": {
            "rows": 10,
        },
        "metadata": {
            "symbol": "XAUUSD",
        },
    }

    reliability_result = record.to_reliability_result()

    assert reliability_result.success is True
    assert reliability_result.status == ReliabilityStatus.OK


def test_supervision_record_failure_to_reliability_result():
    record = SupervisionRecord(
        operation="fetch-data",
        component="data-service",
        state="failed",
        success=False,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:00+00:00",
        error="boom",
    )

    reliability_result = record.to_reliability_result()

    assert record.failed is True
    assert reliability_result.success is False
    assert reliability_result.status == ReliabilityStatus.FAILED
    assert reliability_result.error == "boom"


def test_supervision_record_rejects_invalid_values():
    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="",
            component="service",
            state="completed",
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="",
            state="completed",
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="service",
            state="bad",
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="service",
            state="completed",
            success="yes",
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="service",
            state="completed",
            success=True,
            started_at="",
            finished_at="2026-01-01T00:00:00+00:00",
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="service",
            state="completed",
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="",
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="service",
            state="completed",
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
            duration_seconds=-1,
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="service",
            state="failed",
            success=False,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
            error="",
        )

    with pytest.raises(ValueError):
        SupervisionRecord(
            operation="operation",
            component="service",
            state="completed",
            success=True,
            started_at="2026-01-01T00:00:00+00:00",
            finished_at="2026-01-01T00:00:00+00:00",
            metadata=[],
        )


def test_build_supervision_record():
    record = build_supervision_record(
        operation="operation",
        component="service",
        state="completed",
        success=True,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:00+00:00",
        value=10,
    )

    assert isinstance(record, SupervisionRecord)
    assert record.value == 10


def test_validate_supervision_records_and_events():
    record = build_supervision_record(
        operation="operation",
        component="service",
        state="completed",
        success=True,
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:00+00:00",
    )
    event = build_supervisor_event(
        event_type="completed",
        operation="operation",
        component="service",
        state="completed",
    )

    assert validate_supervision_records([record]) == [
        record,
    ]
    assert validate_supervisor_events([event]) == [
        event,
    ]

    with pytest.raises(ValueError):
        validate_supervision_records("bad")

    with pytest.raises(ValueError):
        validate_supervision_records(["bad"])

    with pytest.raises(ValueError):
        validate_supervisor_events("bad")

    with pytest.raises(ValueError):
        validate_supervisor_events(["bad"])


def test_build_retry_callable_success_and_failure():
    wrapped = build_retry_callable(
        lambda: 10,
        operation_name="operation",
        component="service",
        retry_policy=build_retry_policy(max_attempts=1),
    )

    assert wrapped() == 10

    failing = build_retry_callable(
        lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        operation_name="operation",
        component="service",
        retry_policy=build_retry_policy(max_attempts=1),
    )

    with pytest.raises(RuntimeError):
        failing()

    with pytest.raises(ValueError):
        build_retry_callable(
            "bad",
            operation_name="operation",
            component="service",
            retry_policy=build_retry_policy(),
        )

    with pytest.raises(ValueError):
        build_retry_callable(
            lambda: None,
            operation_name="operation",
            component="service",
            retry_policy="bad",
        )


def test_runtime_supervisor_supervise_success():
    supervisor = build_runtime_supervisor(
        config=build_runtime_supervisor_config(
            enable_retry=True,
            enable_circuit_breaker=True,
            enable_rate_limiter=True,
            enable_deadline=True,
            default_component="api",
        ),
        rate_limit_config=build_rate_limit_config(
            max_requests=5,
            window_seconds=60,
        ),
    )

    result = supervisor.supervise(
        lambda: 10,
        operation_name="calculate",
        component="math",
        rate_limit_key="user-1",
        now="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    assert result.success is True
    assert result.value == 10
    assert len(supervisor.records) == 1
    assert supervisor.records[0].success is True
    assert supervisor.summary()["successful_records"] == 1
    assert supervisor.summary()["circuit_breakers"] == 1


def test_runtime_supervisor_supervise_failure():
    supervisor = build_runtime_supervisor(
        config=build_runtime_supervisor_config(
            enable_rate_limiter=False,
            enable_deadline=False,
        ),
        retry_policy=build_retry_policy(max_attempts=1),
    )

    def fail():
        raise RuntimeError("boom")

    result = supervisor.supervise(
        fail,
        operation_name="fail-op",
        component="test",
        now="2026-01-01T00:00:00+00:00",
    )

    assert result.success is False
    assert result.error is not None
    assert len(supervisor.records) == 1
    assert supervisor.records[0].failed is True
    assert supervisor.summary()["failed_records"] == 1


def test_runtime_supervisor_supervise_rate_limited():
    supervisor = build_runtime_supervisor(
        config=build_runtime_supervisor_config(
            enable_retry=False,
            enable_circuit_breaker=False,
            enable_rate_limiter=True,
            enable_deadline=False,
        ),
        rate_limit_config=build_rate_limit_config(
            max_requests=1,
            window_seconds=60,
        ),
    )

    first = supervisor.supervise(
        lambda: 10,
        operation_name="limited-op",
        component="api",
        rate_limit_key="user-1",
        now="2026-01-01T00:00:00+00:00",
    )
    second = supervisor.supervise(
        lambda: 20,
        operation_name="limited-op",
        component="api",
        rate_limit_key="user-1",
        now="2026-01-01T00:00:01+00:00",
    )

    assert first.success is True
    assert second.success is False
    assert supervisor.summary()["failed_records"] == 1


def test_runtime_supervisor_latest_records_events_and_clear():
    supervisor = build_runtime_supervisor(
        config=build_runtime_supervisor_config(
            enable_retry=False,
            enable_circuit_breaker=False,
            enable_rate_limiter=False,
            enable_deadline=False,
        ),
    )

    supervisor.supervise(
        lambda: 10,
        operation_name="op-1",
        component="service",
        now="2026-01-01T00:00:00+00:00",
    )
    supervisor.supervise(
        lambda: 20,
        operation_name="op-2",
        component="service",
        now="2026-01-01T00:00:01+00:00",
    )

    assert len(supervisor.latest_records(limit=1)) == 1
    assert supervisor.latest_records(limit=1)[0].operation == "op-2"
    assert len(supervisor.latest_events(limit=1)) == 1

    with pytest.raises(ValueError):
        supervisor.latest_records(limit=0)

    with pytest.raises(ValueError):
        supervisor.latest_events(limit=0)

    supervisor.clear()

    assert supervisor.summary()["records"] == 0
    assert supervisor.summary()["events"] == 0


def test_runtime_supervisor_rejects_invalid_values():
    with pytest.raises(ValueError):
        RuntimeSupervisor(config="bad")

    with pytest.raises(ValueError):
        RuntimeSupervisor(retry_policy="bad")

    with pytest.raises(ValueError):
        RuntimeSupervisor(circuit_breaker_config="bad")

    with pytest.raises(ValueError):
        RuntimeSupervisor(rate_limiter="bad")

    with pytest.raises(ValueError):
        RuntimeSupervisor(timeout_config="bad")

    with pytest.raises(ValueError):
        RuntimeSupervisor(circuit_breakers={"bad": "bad"})

    with pytest.raises(ValueError):
        RuntimeSupervisor(records=["bad"])

    with pytest.raises(ValueError):
        RuntimeSupervisor(events=["bad"])

    with pytest.raises(ValueError):
        RuntimeSupervisor(metadata=[])

    supervisor = build_runtime_supervisor()

    with pytest.raises(ValueError):
        supervisor.supervise(
            "bad",
            operation_name="operation",
        )

    with pytest.raises(ValueError):
        supervisor.supervise(
            lambda: None,
            operation_name="",
        )

    with pytest.raises(ValueError):
        supervisor.supervise(
            lambda: None,
            operation_name="operation",
            metadata=[],
        )


def test_build_runtime_supervisor():
    supervisor = build_runtime_supervisor(
        config=build_runtime_supervisor_config(
            enable_retry=False,
        ),
        metadata={
            "source": "test",
        },
    )

    assert isinstance(supervisor, RuntimeSupervisor)
    assert supervisor.config.enable_retry is False
    assert supervisor.metadata == {
        "source": "test",
    }


def test_reliability_supervisor_exports_exist():
    import aqos.reliability as reliability

    expected_exports = [
        "RuntimeSupervisor",
        "RuntimeSupervisorConfig",
        "SupervisionRecord",
        "SupervisorEvent",
        "SupervisorEventType",
        "SupervisorState",
        "build_retry_callable",
        "build_runtime_supervisor",
        "build_runtime_supervisor_config",
        "build_supervision_record",
        "build_supervisor_event",
        "build_supervisor_key",
        "normalize_supervisor_event_type",
        "normalize_supervisor_state",
        "normalize_supervisor_timestamp",
        "validate_boolean",
        "validate_supervision_records",
        "validate_supervisor_events",
    ]

    for export_name in expected_exports:
        assert hasattr(reliability, export_name), export_name