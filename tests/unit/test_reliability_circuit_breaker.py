"""
Unit tests for AQOS circuit breaker primitives.
"""

import pytest

from aqos.reliability import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerEvent,
    CircuitBreakerEventType,
    CircuitBreakerState,
    CircuitBreakerStats,
    ReliabilityStatus,
    build_circuit_breaker,
    build_circuit_breaker_config,
    build_circuit_breaker_event,
    build_circuit_breaker_stats,
    normalize_circuit_breaker_event_type,
    normalize_circuit_breaker_state,
    parse_circuit_datetime,
    validate_circuit_breaker_events,
)


def test_circuit_breaker_state_values():
    assert CircuitBreakerState.CLOSED.value == "closed"
    assert CircuitBreakerState.OPEN.value == "open"
    assert CircuitBreakerState.HALF_OPEN.value == "half_open"


def test_circuit_breaker_event_type_values():
    assert CircuitBreakerEventType.SUCCESS.value == "success"
    assert CircuitBreakerEventType.FAILURE.value == "failure"
    assert CircuitBreakerEventType.OPENED.value == "opened"
    assert CircuitBreakerEventType.CLOSED.value == "closed"
    assert CircuitBreakerEventType.HALF_OPENED.value == "half_opened"
    assert CircuitBreakerEventType.REJECTED.value == "rejected"


def test_normalize_circuit_breaker_state_accepts_enum_and_string():
    assert normalize_circuit_breaker_state(CircuitBreakerState.CLOSED) == CircuitBreakerState.CLOSED
    assert normalize_circuit_breaker_state(" CLOSED ") == CircuitBreakerState.CLOSED
    assert normalize_circuit_breaker_state("open") == CircuitBreakerState.OPEN
    assert normalize_circuit_breaker_state("HALF_OPEN") == CircuitBreakerState.HALF_OPEN


def test_normalize_circuit_breaker_state_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_circuit_breaker_state("bad")

    with pytest.raises(ValueError):
        normalize_circuit_breaker_state("")


def test_normalize_circuit_breaker_event_type_accepts_enum_and_string():
    assert normalize_circuit_breaker_event_type(CircuitBreakerEventType.SUCCESS) == CircuitBreakerEventType.SUCCESS
    assert normalize_circuit_breaker_event_type(" SUCCESS ") == CircuitBreakerEventType.SUCCESS
    assert normalize_circuit_breaker_event_type("opened") == CircuitBreakerEventType.OPENED
    assert normalize_circuit_breaker_event_type("HALF_OPENED") == CircuitBreakerEventType.HALF_OPENED


def test_normalize_circuit_breaker_event_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_circuit_breaker_event_type("bad")

    with pytest.raises(ValueError):
        normalize_circuit_breaker_event_type("")


def test_parse_circuit_datetime():
    parsed = parse_circuit_datetime("2026-01-01T00:00:00+00:00")

    assert parsed.isoformat() == "2026-01-01T00:00:00+00:00"

    parsed_naive = parse_circuit_datetime("2026-01-01T00:00:00")

    assert parsed_naive.isoformat() == "2026-01-01T00:00:00+00:00"

    with pytest.raises(ValueError):
        parse_circuit_datetime("")


def test_circuit_breaker_config_to_dict():
    config = CircuitBreakerConfig(
        failure_threshold=2,
        recovery_timeout_seconds=10,
        success_threshold=2,
        metadata={
            "service": "market-data",
        },
    )

    assert config.to_dict() == {
        "failure_threshold": 2,
        "recovery_timeout_seconds": 10.0,
        "success_threshold": 2,
        "metadata": {
            "service": "market-data",
        },
    }


def test_circuit_breaker_config_rejects_invalid_values():
    with pytest.raises(ValueError):
        CircuitBreakerConfig(failure_threshold=0)

    with pytest.raises(ValueError):
        CircuitBreakerConfig(recovery_timeout_seconds=-1)

    with pytest.raises(ValueError):
        CircuitBreakerConfig(success_threshold=0)

    with pytest.raises(ValueError):
        CircuitBreakerConfig(metadata=[])


def test_build_circuit_breaker_config():
    config = build_circuit_breaker_config(
        failure_threshold=2,
        recovery_timeout_seconds=5,
        success_threshold=1,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(config, CircuitBreakerConfig)
    assert config.to_dict()["metadata"] == {
        "source": "test",
    }


def test_circuit_breaker_event_to_dict():
    event = CircuitBreakerEvent(
        event_type="OPENED",
        state="OPEN",
        message=" Opened. ",
        timestamp="2026-01-01T00:00:00+00:00",
        metadata={
            "reason": "failures",
        },
    )

    assert event.to_dict() == {
        "event_type": "opened",
        "state": "open",
        "message": "Opened.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "metadata": {
            "reason": "failures",
        },
    }


def test_circuit_breaker_event_rejects_invalid_values():
    with pytest.raises(ValueError):
        CircuitBreakerEvent(event_type="bad", state="closed")

    with pytest.raises(ValueError):
        CircuitBreakerEvent(event_type="success", state="bad")

    with pytest.raises(ValueError):
        CircuitBreakerEvent(event_type="success", state="closed", message=123)

    with pytest.raises(ValueError):
        CircuitBreakerEvent(event_type="success", state="closed", timestamp="")

    with pytest.raises(ValueError):
        CircuitBreakerEvent(event_type="success", state="closed", metadata=[])


def test_build_circuit_breaker_event():
    event = build_circuit_breaker_event(
        event_type="success",
        state="closed",
        message="OK.",
        timestamp="2026-01-01T00:00:00+00:00",
        metadata={
            "attempt": 1,
        },
    )

    assert isinstance(event, CircuitBreakerEvent)
    assert event.to_dict()["metadata"] == {
        "attempt": 1,
    }


def test_circuit_breaker_stats_records_and_resets():
    stats = CircuitBreakerStats()

    stats.record_failure("2026-01-01T00:00:00+00:00")
    stats.record_success("2026-01-01T00:00:01+00:00")
    stats.record_rejected()

    assert stats.to_dict() == {
        "failure_count": 1,
        "success_count": 1,
        "rejected_count": 1,
        "last_failure_at": "2026-01-01T00:00:00+00:00",
        "last_success_at": "2026-01-01T00:00:01+00:00",
    }

    stats.reset_counts()

    assert stats.failure_count == 0
    assert stats.success_count == 0
    assert stats.rejected_count == 1


def test_circuit_breaker_stats_rejects_invalid_values():
    with pytest.raises(ValueError):
        CircuitBreakerStats(failure_count=-1)

    with pytest.raises(ValueError):
        CircuitBreakerStats(success_count=-1)

    with pytest.raises(ValueError):
        CircuitBreakerStats(rejected_count=-1)

    with pytest.raises(ValueError):
        CircuitBreakerStats(opened_at="")

    with pytest.raises(ValueError):
        CircuitBreakerStats(last_failure_at="")

    with pytest.raises(ValueError):
        CircuitBreakerStats(last_success_at="")


def test_build_circuit_breaker_stats():
    stats = build_circuit_breaker_stats(
        failure_count=1,
        success_count=2,
        rejected_count=3,
        opened_at="2026-01-01T00:00:00+00:00",
    )

    assert isinstance(stats, CircuitBreakerStats)
    assert stats.failure_count == 1
    assert stats.success_count == 2
    assert stats.rejected_count == 3


def test_validate_circuit_breaker_events():
    event = build_circuit_breaker_event(
        event_type="success",
        state="closed",
    )

    assert validate_circuit_breaker_events([event]) == [
        event,
    ]

    with pytest.raises(ValueError):
        validate_circuit_breaker_events("bad")

    with pytest.raises(ValueError):
        validate_circuit_breaker_events(["bad"])


def test_circuit_breaker_to_dict_and_properties():
    breaker = CircuitBreaker(
        name=" market-data ",
        component=" data-service ",
        config=build_circuit_breaker_config(failure_threshold=2),
        metadata={
            "symbol": "XAUUSD",
        },
    )

    payload = breaker.to_dict()

    assert breaker.closed is True
    assert breaker.open is False
    assert breaker.half_open is False
    assert payload["name"] == "market-data"
    assert payload["component"] == "data-service"
    assert payload["state"] == "closed"
    assert payload["metadata"] == {
        "symbol": "XAUUSD",
    }


def test_circuit_breaker_rejects_invalid_values():
    with pytest.raises(ValueError):
        CircuitBreaker(name="", component="service")

    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", component="")

    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", component="service", config="bad")

    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", component="service", state="bad")

    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", component="service", stats="bad")

    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", component="service", events=["bad"])

    with pytest.raises(ValueError):
        CircuitBreaker(name="breaker", component="service", metadata=[])


def test_circuit_breaker_records_success():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
    )

    breaker.record_success(now="2026-01-01T00:00:00+00:00")

    assert breaker.closed is True
    assert breaker.stats.success_count == 1
    assert breaker.events[-1].event_type == CircuitBreakerEventType.SUCCESS


def test_circuit_breaker_opens_after_failure_threshold():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(failure_threshold=2),
    )

    breaker.record_failure("first", now="2026-01-01T00:00:00+00:00")

    assert breaker.closed is True
    assert breaker.stats.failure_count == 1

    breaker.record_failure("second", now="2026-01-01T00:00:01+00:00")

    assert breaker.open is True
    assert breaker.stats.opened_at == "2026-01-01T00:00:01+00:00"
    assert breaker.events[-1].event_type == CircuitBreakerEventType.OPENED


def test_circuit_breaker_half_open_after_recovery_timeout():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(
            failure_threshold=1,
            recovery_timeout_seconds=10,
        ),
    )

    breaker.record_failure("boom", now="2026-01-01T00:00:00+00:00")

    assert breaker.open is True

    assert breaker.should_allow_request(now="2026-01-01T00:00:05+00:00") is False
    assert breaker.should_allow_request(now="2026-01-01T00:00:10+00:00") is True
    assert breaker.half_open is True


def test_circuit_breaker_closes_after_half_open_success_threshold():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(
            failure_threshold=1,
            recovery_timeout_seconds=1,
            success_threshold=2,
        ),
    )

    breaker.record_failure("boom", now="2026-01-01T00:00:00+00:00")
    breaker.should_allow_request(now="2026-01-01T00:00:01+00:00")

    assert breaker.half_open is True

    breaker.record_success(now="2026-01-01T00:00:02+00:00")

    assert breaker.half_open is True

    breaker.record_success(now="2026-01-01T00:00:03+00:00")

    assert breaker.closed is True


def test_circuit_breaker_reopens_on_half_open_failure():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(
            failure_threshold=1,
            recovery_timeout_seconds=1,
        ),
    )

    breaker.record_failure("boom", now="2026-01-01T00:00:00+00:00")
    breaker.should_allow_request(now="2026-01-01T00:00:01+00:00")

    assert breaker.half_open is True

    breaker.record_failure("again", now="2026-01-01T00:00:02+00:00")

    assert breaker.open is True
    assert breaker.stats.opened_at == "2026-01-01T00:00:02+00:00"


def test_circuit_breaker_rejects_open_request_before_timeout():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(
            failure_threshold=1,
            recovery_timeout_seconds=10,
        ),
    )

    breaker.record_failure("boom", now="2026-01-01T00:00:00+00:00")

    assert breaker.should_allow_request(now="2026-01-01T00:00:05+00:00") is False

    event = breaker.reject_request()

    assert event.event_type == CircuitBreakerEventType.REJECTED
    assert breaker.stats.rejected_count == 1


def test_circuit_breaker_execute_success():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
    )

    result = breaker.execute(
        lambda: 10,
        now="2026-01-01T00:00:00+00:00",
    )

    assert result.success is True
    assert result.status == ReliabilityStatus.OK
    assert result.value == 10
    assert breaker.closed is True


def test_circuit_breaker_execute_failure_opens_breaker():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(failure_threshold=1),
    )

    def fail():
        raise RuntimeError("boom")

    result = breaker.execute(
        fail,
        now="2026-01-01T00:00:00+00:00",
    )

    assert result.success is False
    assert result.status == ReliabilityStatus.FAILED
    assert result.error == "boom"
    assert breaker.open is True


def test_circuit_breaker_execute_rejects_when_open():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(
            failure_threshold=1,
            recovery_timeout_seconds=10,
        ),
    )

    breaker.record_failure("boom", now="2026-01-01T00:00:00+00:00")

    result = breaker.execute(
        lambda: 10,
        now="2026-01-01T00:00:05+00:00",
    )

    assert result.success is False
    assert result.status == ReliabilityStatus.DEGRADED
    assert result.error == "Circuit breaker is open."
    assert breaker.stats.rejected_count == 1


def test_circuit_breaker_execute_rejects_invalid_operation():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
    )

    with pytest.raises(ValueError):
        breaker.execute("bad")


def test_circuit_breaker_reset():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        config=build_circuit_breaker_config(failure_threshold=1),
    )

    breaker.record_failure("boom", now="2026-01-01T00:00:00+00:00")

    assert breaker.open is True
    assert breaker.events

    breaker.reset()

    assert breaker.closed is True
    assert breaker.events == []
    assert breaker.stats.failure_count == 0


def test_build_circuit_breaker():
    breaker = build_circuit_breaker(
        name="operation",
        component="service",
        metadata={
            "source": "test",
        },
    )

    assert isinstance(breaker, CircuitBreaker)
    assert breaker.metadata == {
        "source": "test",
    }


def test_reliability_circuit_breaker_exports_exist():
    import aqos.reliability as reliability

    expected_exports = [
        "CircuitBreaker",
        "CircuitBreakerConfig",
        "CircuitBreakerEvent",
        "CircuitBreakerEventType",
        "CircuitBreakerState",
        "CircuitBreakerStats",
        "build_circuit_breaker",
        "build_circuit_breaker_config",
        "build_circuit_breaker_event",
        "build_circuit_breaker_stats",
        "normalize_circuit_breaker_event_type",
        "normalize_circuit_breaker_state",
        "parse_circuit_datetime",
        "validate_circuit_breaker_events",
    ]

    for export_name in expected_exports:
        assert hasattr(reliability, export_name), export_name