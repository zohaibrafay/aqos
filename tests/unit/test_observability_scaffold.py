"""
Unit tests for AQOS observability scaffold.
"""

import pytest

from aqos.observability import (
    ObservabilityEvent,
    ObservabilitySeverity,
    ObservabilityStatus,
    build_observability_event,
    normalize_severity,
    normalize_status,
    validate_attributes,
    validate_non_empty_string,
    validate_string,
)


def test_observability_status_values():
    assert ObservabilityStatus.OK.value == "ok"
    assert ObservabilityStatus.WARNING.value == "warning"
    assert ObservabilityStatus.ERROR.value == "error"


def test_observability_severity_values():
    assert ObservabilitySeverity.DEBUG.value == "debug"
    assert ObservabilitySeverity.INFO.value == "info"
    assert ObservabilitySeverity.WARNING.value == "warning"
    assert ObservabilitySeverity.ERROR.value == "error"
    assert ObservabilitySeverity.CRITICAL.value == "critical"


def test_normalize_status_accepts_enum_and_string():
    assert normalize_status(ObservabilityStatus.OK) == ObservabilityStatus.OK
    assert normalize_status(" OK ") == ObservabilityStatus.OK
    assert normalize_status("warning") == ObservabilityStatus.WARNING
    assert normalize_status("ERROR") == ObservabilityStatus.ERROR


def test_normalize_status_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_status("bad")

    with pytest.raises(ValueError):
        normalize_status("")


def test_normalize_severity_accepts_enum_and_string():
    assert normalize_severity(ObservabilitySeverity.INFO) == ObservabilitySeverity.INFO
    assert normalize_severity(" INFO ") == ObservabilitySeverity.INFO
    assert normalize_severity("warning") == ObservabilitySeverity.WARNING
    assert normalize_severity("CRITICAL") == ObservabilitySeverity.CRITICAL


def test_normalize_severity_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_severity("bad")

    with pytest.raises(ValueError):
        normalize_severity("")


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


def test_observability_event_to_dict():
    event = ObservabilityEvent(
        name="market.state.loaded",
        component="market-agent",
        severity="INFO",
        message="Market state loaded.",
        timestamp="2026-01-01T00:00:00+00:00",
        attributes={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert event.to_dict() == {
        "name": "market.state.loaded",
        "component": "market-agent",
        "severity": "info",
        "message": "Market state loaded.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "attributes": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    }


def test_observability_event_defaults():
    event = ObservabilityEvent(
        name="system.started",
        component="aqos",
    )

    payload = event.to_dict()

    assert payload["name"] == "system.started"
    assert payload["component"] == "aqos"
    assert payload["severity"] == "info"
    assert payload["message"] == ""
    assert payload["timestamp"]
    assert payload["attributes"] == {}


def test_observability_event_rejects_invalid_values():
    with pytest.raises(ValueError):
        ObservabilityEvent(
            name="",
            component="aqos",
        )

    with pytest.raises(ValueError):
        ObservabilityEvent(
            name="system.started",
            component="",
        )

    with pytest.raises(ValueError):
        ObservabilityEvent(
            name="system.started",
            component="aqos",
            severity="bad",
        )

    with pytest.raises(ValueError):
        ObservabilityEvent(
            name="system.started",
            component="aqos",
            message=123,
        )

    with pytest.raises(ValueError):
        ObservabilityEvent(
            name="system.started",
            component="aqos",
            timestamp="",
        )

    with pytest.raises(ValueError):
        ObservabilityEvent(
            name="system.started",
            component="aqos",
            attributes=[],
        )


def test_build_observability_event_with_timestamp():
    event = build_observability_event(
        name="risk.approved",
        component="risk-agent",
        severity="warning",
        message="Risk approved with warning.",
        attributes={
            "symbol": "XAUUSD",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert event.to_dict() == {
        "name": "risk.approved",
        "component": "risk-agent",
        "severity": "warning",
        "message": "Risk approved with warning.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "attributes": {
            "symbol": "XAUUSD",
        },
    }


def test_observability_exports_are_sorted():
    import aqos.observability as observability

    assert observability.__all__ == sorted(observability.__all__)


def test_observability_exports_exist():
    import aqos.observability as observability

    for export_name in observability.__all__:
        assert hasattr(observability, export_name), export_name