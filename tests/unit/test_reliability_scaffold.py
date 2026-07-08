"""
Unit tests for AQOS reliability scaffold.
"""

import pytest

from aqos.reliability import (
    ReliabilityEvent,
    ReliabilityResult,
    ReliabilitySeverity,
    ReliabilityStatus,
    build_reliability_event,
    build_reliability_result,
    normalize_reliability_severity,
    normalize_reliability_status,
    safe_execute,
    validate_attributes,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_integer,
    validate_positive_integer,
    validate_string,
)


def test_reliability_status_values():
    assert ReliabilityStatus.OK.value == "ok"
    assert ReliabilityStatus.DEGRADED.value == "degraded"
    assert ReliabilityStatus.FAILED.value == "failed"


def test_reliability_severity_values():
    assert ReliabilitySeverity.DEBUG.value == "debug"
    assert ReliabilitySeverity.INFO.value == "info"
    assert ReliabilitySeverity.WARNING.value == "warning"
    assert ReliabilitySeverity.ERROR.value == "error"
    assert ReliabilitySeverity.CRITICAL.value == "critical"


def test_normalize_reliability_status_accepts_enum_and_string():
    assert normalize_reliability_status(ReliabilityStatus.OK) == ReliabilityStatus.OK
    assert normalize_reliability_status(" OK ") == ReliabilityStatus.OK
    assert normalize_reliability_status("degraded") == ReliabilityStatus.DEGRADED
    assert normalize_reliability_status("FAILED") == ReliabilityStatus.FAILED


def test_normalize_reliability_status_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_reliability_status("bad")

    with pytest.raises(ValueError):
        normalize_reliability_status("")


def test_normalize_reliability_severity_accepts_enum_and_string():
    assert normalize_reliability_severity(ReliabilitySeverity.INFO) == ReliabilitySeverity.INFO
    assert normalize_reliability_severity(" INFO ") == ReliabilitySeverity.INFO
    assert normalize_reliability_severity("warning") == ReliabilitySeverity.WARNING
    assert normalize_reliability_severity("ERROR") == ReliabilitySeverity.ERROR


def test_normalize_reliability_severity_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_reliability_severity("bad")

    with pytest.raises(ValueError):
        normalize_reliability_severity("")


def test_validate_string_accepts_string():
    assert validate_string("", "Field") == ""
    assert validate_string("value", "Field") == "value"


def test_validate_string_rejects_non_string():
    with pytest.raises(ValueError):
        validate_string(123, "Field")


def test_validate_non_empty_string_accepts_trimmed_value():
    assert validate_non_empty_string(" value ", "Field") == "value"


def test_validate_non_empty_string_rejects_empty_value():
    with pytest.raises(ValueError):
        validate_non_empty_string("", "Field")

    with pytest.raises(ValueError):
        validate_non_empty_string("   ", "Field")


def test_validate_attributes_accepts_dictionary():
    attributes = {
        "symbol": "XAUUSD",
    }

    assert validate_attributes(attributes) == attributes


def test_validate_attributes_rejects_non_dictionary():
    with pytest.raises(ValueError):
        validate_attributes([])


def test_validate_positive_integer():
    assert validate_positive_integer(1, "Value") == 1

    with pytest.raises(ValueError):
        validate_positive_integer(0, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer(True, "Value")

    with pytest.raises(ValueError):
        validate_positive_integer("1", "Value")


def test_validate_non_negative_integer():
    assert validate_non_negative_integer(0, "Value") == 0
    assert validate_non_negative_integer(1, "Value") == 1

    with pytest.raises(ValueError):
        validate_non_negative_integer(-1, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer(True, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_integer("1", "Value")


def test_validate_non_negative_float():
    assert validate_non_negative_float(0, "Value") == 0.0
    assert validate_non_negative_float(1.5, "Value") == 1.5

    with pytest.raises(ValueError):
        validate_non_negative_float(-0.1, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float(True, "Value")

    with pytest.raises(ValueError):
        validate_non_negative_float("1", "Value")


def test_reliability_event_to_dict():
    event = ReliabilityEvent(
        name=" retry-attempt ",
        component=" data-service ",
        status="DEGRADED",
        severity="WARNING",
        message=" Retry scheduled. ",
        timestamp="2026-01-01T00:00:00+00:00",
        attributes={
            "attempt": 1,
        },
    )

    assert event.to_dict() == {
        "name": "retry-attempt",
        "component": "data-service",
        "status": "degraded",
        "severity": "warning",
        "message": "Retry scheduled.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "attributes": {
            "attempt": 1,
        },
    }


def test_reliability_event_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReliabilityEvent(name="", component="service")

    with pytest.raises(ValueError):
        ReliabilityEvent(name="event", component="")

    with pytest.raises(ValueError):
        ReliabilityEvent(name="event", component="service", status="bad")

    with pytest.raises(ValueError):
        ReliabilityEvent(name="event", component="service", severity="bad")

    with pytest.raises(ValueError):
        ReliabilityEvent(name="event", component="service", message=123)

    with pytest.raises(ValueError):
        ReliabilityEvent(name="event", component="service", timestamp="")

    with pytest.raises(ValueError):
        ReliabilityEvent(name="event", component="service", attributes=[])


def test_build_reliability_event():
    event = build_reliability_event(
        name="operation",
        component="service",
        status="ok",
        severity="info",
        message="Done.",
        timestamp="2026-01-01T00:00:00+00:00",
        attributes={
            "source": "test",
        },
    )

    assert isinstance(event, ReliabilityEvent)
    assert event.to_dict()["name"] == "operation"
    assert event.to_dict()["attributes"] == {
        "source": "test",
    }


def test_reliability_result_to_dict_and_event():
    result = ReliabilityResult(
        success=True,
        operation="fetch-data",
        component="data-service",
        status="OK",
        message="Fetched.",
        value={
            "rows": 10,
        },
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert result.failed is False

    assert result.to_dict() == {
        "success": True,
        "failed": False,
        "operation": "fetch-data",
        "component": "data-service",
        "status": "ok",
        "message": "Fetched.",
        "value": {
            "rows": 10,
        },
        "metadata": {
            "symbol": "XAUUSD",
        },
    }

    event = result.to_event()

    assert event.name == "fetch-data"
    assert event.component == "data-service"
    assert event.status == "OK"
    assert event.severity == ReliabilitySeverity.INFO


def test_reliability_result_failure_to_dict_and_event():
    result = ReliabilityResult(
        success=False,
        operation="fetch-data",
        component="data-service",
        status="failed",
        message="Operation failed.",
        error="Network error.",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert result.failed is True

    assert result.to_dict() == {
        "success": False,
        "failed": True,
        "operation": "fetch-data",
        "component": "data-service",
        "status": "failed",
        "message": "Operation failed.",
        "error": "Network error.",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }

    event = result.to_event()

    assert event.name == "fetch-data"
    assert event.severity == ReliabilitySeverity.ERROR
    assert event.attributes["error"] == "Network error."


def test_reliability_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        ReliabilityResult(
            success="yes",
            operation="operation",
            component="service",
        )

    with pytest.raises(ValueError):
        ReliabilityResult(
            success=True,
            operation="",
            component="service",
        )

    with pytest.raises(ValueError):
        ReliabilityResult(
            success=True,
            operation="operation",
            component="",
        )

    with pytest.raises(ValueError):
        ReliabilityResult(
            success=True,
            operation="operation",
            component="service",
            status="bad",
        )

    with pytest.raises(ValueError):
        ReliabilityResult(
            success=True,
            operation="operation",
            component="service",
            message=123,
        )

    with pytest.raises(ValueError):
        ReliabilityResult(
            success=True,
            operation="operation",
            component="service",
            error="",
        )

    with pytest.raises(ValueError):
        ReliabilityResult(
            success=True,
            operation="operation",
            component="service",
            metadata=[],
        )


def test_build_reliability_result():
    result = build_reliability_result(
        success=True,
        operation="operation",
        component="service",
        value=123,
    )

    assert isinstance(result, ReliabilityResult)
    assert result.success is True
    assert result.value == 123


def test_safe_execute_success():
    result = safe_execute(
        lambda: 10,
        operation_name="calculate",
        component="math",
        metadata={
            "source": "test",
        },
    )

    assert result.success is True
    assert result.failed is False
    assert result.value == 10
    assert result.message == "Operation completed successfully."
    assert result.metadata == {
        "source": "test",
    }


def test_safe_execute_failure():
    def fail():
        raise RuntimeError("boom")

    result = safe_execute(
        fail,
        operation_name="fail-op",
        component="test",
    )

    assert result.success is False
    assert result.failed is True
    assert result.status == ReliabilityStatus.FAILED
    assert result.message == "Operation failed."
    assert result.error == "boom"
    assert result.metadata == {
        "error_type": "RuntimeError",
    }


def test_safe_execute_rejects_invalid_values():
    with pytest.raises(ValueError):
        safe_execute(
            "bad",
            operation_name="operation",
            component="service",
        )

    with pytest.raises(ValueError):
        safe_execute(
            lambda: None,
            operation_name="",
            component="service",
        )

    with pytest.raises(ValueError):
        safe_execute(
            lambda: None,
            operation_name="operation",
            component="",
        )

    with pytest.raises(ValueError):
        safe_execute(
            lambda: None,
            operation_name="operation",
            component="service",
            metadata=[],
        )


def test_reliability_exports_are_sorted():
    import aqos.reliability as reliability

    assert reliability.__all__ == sorted(reliability.__all__)


def test_reliability_exports_exist():
    import aqos.reliability as reliability

    for export_name in reliability.__all__:
        assert hasattr(reliability, export_name), export_name