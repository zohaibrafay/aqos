"""
Unit tests for AQOS observability alerting.
"""

import pytest

from aqos.observability import (
    AlertManager,
    AlertOperator,
    AlertRecord,
    AlertRule,
    AlertState,
    MetricPoint,
    build_alert_id,
    build_alert_record,
    build_alert_rule,
    compare_alert_values,
    normalize_alert_operator,
    normalize_alert_state,
    validate_alert_message,
)


def sample_metric_point(value=250.0):
    return MetricPoint(
        name="api.latency",
        metric_type="histogram",
        value=value,
        component="api",
        timestamp="2026-01-01T00:00:00+00:00",
        unit="ms",
        attributes={
            "route": "/health",
        },
    )


def sample_alert_rule():
    return AlertRule(
        name="high-api-latency",
        metric_name="api.latency",
        component="api",
        operator=">",
        threshold=200.0,
        severity="warning",
        message="API latency is high.",
        attributes={
            "team": "platform",
        },
    )


def test_alert_state_values():
    assert AlertState.ACTIVE.value == "active"
    assert AlertState.RESOLVED.value == "resolved"
    assert AlertState.SUPPRESSED.value == "suppressed"


def test_alert_operator_values():
    assert AlertOperator.GT.value == ">"
    assert AlertOperator.GTE.value == ">="
    assert AlertOperator.LT.value == "<"
    assert AlertOperator.LTE.value == "<="
    assert AlertOperator.EQ.value == "=="
    assert AlertOperator.NE.value == "!="


def test_build_alert_id():
    alert_id = build_alert_id()

    assert alert_id.startswith("alert-")
    assert len(alert_id) > len("alert-")


def test_normalize_alert_state_accepts_enum_and_string():
    assert normalize_alert_state(AlertState.ACTIVE) == AlertState.ACTIVE
    assert normalize_alert_state(" ACTIVE ") == AlertState.ACTIVE
    assert normalize_alert_state("resolved") == AlertState.RESOLVED
    assert normalize_alert_state("SUPPRESSED") == AlertState.SUPPRESSED


def test_normalize_alert_state_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_alert_state("bad")

    with pytest.raises(ValueError):
        normalize_alert_state("")


def test_normalize_alert_operator_accepts_enum_symbol_and_aliases():
    assert normalize_alert_operator(AlertOperator.GT) == AlertOperator.GT
    assert normalize_alert_operator(">") == AlertOperator.GT
    assert normalize_alert_operator("gt") == AlertOperator.GT
    assert normalize_alert_operator("greater_than") == AlertOperator.GT
    assert normalize_alert_operator(">=") == AlertOperator.GTE
    assert normalize_alert_operator("gte") == AlertOperator.GTE
    assert normalize_alert_operator("<") == AlertOperator.LT
    assert normalize_alert_operator("lte") == AlertOperator.LTE
    assert normalize_alert_operator("eq") == AlertOperator.EQ
    assert normalize_alert_operator("!=") == AlertOperator.NE


def test_normalize_alert_operator_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_alert_operator("bad")

    with pytest.raises(ValueError):
        normalize_alert_operator("")


def test_compare_alert_values():
    assert compare_alert_values(10, ">", 5) is True
    assert compare_alert_values(10, ">=", 10) is True
    assert compare_alert_values(5, "<", 10) is True
    assert compare_alert_values(10, "<=", 10) is True
    assert compare_alert_values(10, "==", 10) is True
    assert compare_alert_values(10, "!=", 5) is True

    assert compare_alert_values(5, ">", 10) is False
    assert compare_alert_values(10, "!=", 10) is False


def test_compare_alert_values_rejects_invalid_values():
    with pytest.raises(ValueError):
        compare_alert_values("bad", ">", 10)

    with pytest.raises(ValueError):
        compare_alert_values(10, "bad", 10)

    with pytest.raises(ValueError):
        compare_alert_values(10, ">", "bad")


def test_validate_alert_message():
    assert validate_alert_message("") == ""
    assert validate_alert_message(" Alert triggered. ") == "Alert triggered."

    with pytest.raises(ValueError):
        validate_alert_message(123)


def test_alert_rule_to_dict():
    rule = sample_alert_rule()

    assert rule.to_dict() == {
        "name": "high-api-latency",
        "metric_name": "api.latency",
        "component": "api",
        "operator": ">",
        "threshold": 200.0,
        "severity": "warning",
        "message": "API latency is high.",
        "enabled": True,
        "attributes": {
            "team": "platform",
        },
    }


def test_alert_rule_matches_metric_point():
    rule = sample_alert_rule()

    assert rule.matches(sample_metric_point(250.0)) is True
    assert rule.matches(sample_metric_point(100.0)) is False

    wrong_metric = MetricPoint(
        name="api.requests",
        metric_type="counter",
        value=250,
        component="api",
    )

    wrong_component = MetricPoint(
        name="api.latency",
        metric_type="histogram",
        value=250,
        component="worker",
    )

    assert rule.matches(wrong_metric) is False
    assert rule.matches(wrong_component) is False


def test_disabled_alert_rule_does_not_match():
    rule = AlertRule(
        name="disabled-rule",
        metric_name="api.latency",
        component="api",
        operator=">",
        threshold=200,
        enabled=False,
    )

    assert rule.matches(sample_metric_point(250.0)) is False


def test_alert_rule_rejects_invalid_values():
    with pytest.raises(ValueError):
        AlertRule(
            name="",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold=200,
        )

    with pytest.raises(ValueError):
        AlertRule(
            name="rule",
            metric_name="",
            component="api",
            operator=">",
            threshold=200,
        )

    with pytest.raises(ValueError):
        AlertRule(
            name="rule",
            metric_name="api.latency",
            component="",
            operator=">",
            threshold=200,
        )

    with pytest.raises(ValueError):
        AlertRule(
            name="rule",
            metric_name="api.latency",
            component="api",
            operator="bad",
            threshold=200,
        )

    with pytest.raises(ValueError):
        AlertRule(
            name="rule",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold="bad",
        )

    with pytest.raises(ValueError):
        AlertRule(
            name="rule",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold=200,
            severity="bad",
        )

    with pytest.raises(ValueError):
        AlertRule(
            name="rule",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold=200,
            enabled="yes",
        )

    with pytest.raises(ValueError):
        AlertRule(
            name="rule",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold=200,
            attributes=[],
        )


def test_build_alert_rule():
    rule = build_alert_rule(
        name="high-api-latency",
        metric_name="api.latency",
        component="api",
        operator="gt",
        threshold=200,
        message="API latency is high.",
    )

    assert isinstance(rule, AlertRule)
    assert rule.to_dict()["operator"] == ">"
    assert rule.to_dict()["message"] == "API latency is high."


def test_build_alert_record():
    rule = sample_alert_rule()
    point = sample_metric_point()

    alert = build_alert_record(
        rule=rule,
        point=point,
        alert_id="alert-1",
        timestamp="2026-01-01T00:00:01+00:00",
    )

    assert alert.to_dict() == {
        "alert_id": "alert-1",
        "rule_name": "high-api-latency",
        "metric_name": "api.latency",
        "component": "api",
        "severity": "warning",
        "state": "active",
        "message": "API latency is high.",
        "value": 250.0,
        "threshold": 200.0,
        "timestamp": "2026-01-01T00:00:01+00:00",
        "attributes": {
            "metric": point.to_dict(),
            "rule": rule.to_dict(),
            "team": "platform",
        },
    }


def test_build_alert_record_default_message():
    rule = AlertRule(
        name="high-api-latency",
        metric_name="api.latency",
        component="api",
        operator=">",
        threshold=200,
    )

    alert = build_alert_record(
        rule=rule,
        point=sample_metric_point(),
        alert_id="alert-1",
    )

    assert alert.message == "Alert rule 'high-api-latency' triggered for api.latency."


def test_build_alert_record_rejects_invalid_values():
    with pytest.raises(ValueError):
        build_alert_record(
            rule="bad",
            point=sample_metric_point(),
        )

    with pytest.raises(ValueError):
        build_alert_record(
            rule=sample_alert_rule(),
            point="bad",
        )


def test_alert_record_to_event():
    alert = build_alert_record(
        rule=sample_alert_rule(),
        point=sample_metric_point(),
        alert_id="alert-1",
        timestamp="2026-01-01T00:00:01+00:00",
    )

    event = alert.to_event()
    payload = event.to_dict()

    assert payload["name"] == "alert.high-api-latency"
    assert payload["component"] == "api"
    assert payload["severity"] == "warning"
    assert payload["message"] == "API latency is high."
    assert payload["timestamp"] == "2026-01-01T00:00:01+00:00"
    assert payload["attributes"]["alert_id"] == "alert-1"


def test_alert_record_resolve_and_suppress():
    alert = build_alert_record(
        rule=sample_alert_rule(),
        point=sample_metric_point(),
        alert_id="alert-1",
    )

    alert.resolve(message="Latency recovered.")

    assert alert.state == AlertState.RESOLVED
    assert alert.message == "Latency recovered."

    alert.suppress(message="Muted during maintenance.")

    assert alert.state == AlertState.SUPPRESSED
    assert alert.message == "Muted during maintenance."


def test_alert_record_rejects_invalid_values():
    with pytest.raises(ValueError):
        AlertRecord(
            alert_id="",
            rule_name="rule",
            metric_name="metric",
            component="api",
            severity="warning",
            state="active",
            message="Alert.",
            value=1,
            threshold=1,
        )

    with pytest.raises(ValueError):
        AlertRecord(
            alert_id="alert-1",
            rule_name="rule",
            metric_name="metric",
            component="api",
            severity="bad",
            state="active",
            message="Alert.",
            value=1,
            threshold=1,
        )

    with pytest.raises(ValueError):
        AlertRecord(
            alert_id="alert-1",
            rule_name="rule",
            metric_name="metric",
            component="api",
            severity="warning",
            state="bad",
            message="Alert.",
            value=1,
            threshold=1,
        )

    with pytest.raises(ValueError):
        AlertRecord(
            alert_id="alert-1",
            rule_name="rule",
            metric_name="metric",
            component="api",
            severity="warning",
            state="active",
            message="",
            value=1,
            threshold=1,
        )


def test_alert_manager_register_evaluate_and_summary():
    manager = AlertManager()
    rule = sample_alert_rule()

    assert manager.register_rule(rule) is rule
    assert manager.get_rule("high-api-latency") is rule
    assert manager.get_required_rule("high-api-latency") is rule
    assert manager.list_rules() == [rule]

    emitted = manager.evaluate_point(sample_metric_point(250.0))

    assert len(emitted) == 1
    assert emitted[0].rule_name == "high-api-latency"
    assert emitted[0].state == AlertState.ACTIVE
    assert manager.active_alerts() == emitted
    assert manager.alerts_by_rule("high-api-latency") == emitted

    assert manager.summary() == {
        "rules": 1,
        "alerts": 1,
        "active_alerts": 1,
        "resolved_alerts": 0,
        "suppressed_alerts": 0,
        "rule_names": [
            "high-api-latency",
        ],
    }


def test_alert_manager_evaluate_points():
    manager = AlertManager()
    manager.register_rule(sample_alert_rule())

    emitted = manager.evaluate_points(
        [
            sample_metric_point(100.0),
            sample_metric_point(250.0),
            sample_metric_point(300.0),
        ],
    )

    assert len(emitted) == 2
    assert manager.summary()["alerts"] == 2


def test_alert_manager_resolve_and_suppress_alerts():
    manager = AlertManager()
    manager.register_rule(sample_alert_rule())

    emitted = manager.evaluate_point(sample_metric_point(250.0))
    alert = emitted[0]

    manager.resolve_alert(
        alert.alert_id,
        message="Resolved.",
    )

    assert manager.active_alerts() == []
    assert manager.resolved_alerts() == [alert]

    manager.suppress_alert(
        alert.alert_id,
        message="Suppressed.",
    )

    assert manager.resolved_alerts() == []
    assert manager.suppressed_alerts() == [alert]


def test_alert_manager_upsert_rule_replaces_rule():
    manager = AlertManager()

    original = sample_alert_rule()
    replacement = AlertRule(
        name="high-api-latency",
        metric_name="api.latency",
        component="api",
        operator=">",
        threshold=500,
    )

    manager.register_rule(original)
    manager.upsert_rule(replacement)

    assert manager.get_required_rule("high-api-latency") is replacement


def test_alert_manager_clear_alerts_and_clear():
    manager = AlertManager()
    manager.register_rule(sample_alert_rule())
    manager.evaluate_point(sample_metric_point(250.0))

    assert manager.summary()["alerts"] == 1

    manager.clear_alerts()

    assert manager.summary()["alerts"] == 0
    assert manager.summary()["rules"] == 1

    manager.clear()

    assert manager.summary()["alerts"] == 0
    assert manager.summary()["rules"] == 0


def test_alert_manager_rejects_invalid_values():
    manager = AlertManager()

    with pytest.raises(ValueError):
        manager.register_rule("bad")

    with pytest.raises(ValueError):
        manager.upsert_rule("bad")

    manager.register_rule(sample_alert_rule())

    with pytest.raises(ValueError):
        manager.register_rule(sample_alert_rule())

    with pytest.raises(ValueError):
        manager.get_required_rule("missing-rule")

    with pytest.raises(ValueError):
        manager.evaluate_point("bad")

    with pytest.raises(ValueError):
        manager.evaluate_points("bad")

    with pytest.raises(ValueError):
        manager.get_required_alert("missing-alert")

    with pytest.raises(ValueError):
        manager.alerts_by_rule("")


def test_observability_alerts_exports_exist():
    import aqos.observability as observability

    expected_exports = [
        "AlertManager",
        "AlertOperator",
        "AlertRecord",
        "AlertRule",
        "AlertState",
        "build_alert_id",
        "build_alert_record",
        "build_alert_rule",
        "compare_alert_values",
        "normalize_alert_operator",
        "normalize_alert_state",
        "validate_alert_message",
    ]

    for export_name in expected_exports:
        assert hasattr(observability, export_name), export_name