"""
Unit tests for AQOS observability health snapshots.
"""

import pytest

from aqos.observability import (
    AlertManager,
    AlertRule,
    ComponentHealth,
    InMemoryLogSink,
    InMemoryTraceStore,
    MetricsRegistry,
    ObservabilitySnapshot,
    ObservabilityStatus,
    StructuredLogRecord,
    build_alerts_summary,
    build_component_health,
    build_logs_summary,
    build_metrics_summary,
    build_observability_snapshot,
    build_traces_summary,
    collect_observability_snapshot,
    resolve_health_snapshot_status,
    validate_component_health_list,
    validate_health_message,
    validate_non_negative_integer,
)


def test_validate_health_message():
    assert validate_health_message("") == ""
    assert validate_health_message(" Healthy. ") == "Healthy."

    with pytest.raises(ValueError):
        validate_health_message(123)


def test_validate_non_negative_integer():
    assert validate_non_negative_integer(0, "Count") == 0
    assert validate_non_negative_integer(3, "Count") == 3

    with pytest.raises(ValueError):
        validate_non_negative_integer(-1, "Count")

    with pytest.raises(ValueError):
        validate_non_negative_integer(True, "Count")

    with pytest.raises(ValueError):
        validate_non_negative_integer("1", "Count")


def test_component_health_to_dict():
    health = ComponentHealth(
        component="market-agent",
        status="OK",
        message="Market agent healthy.",
        timestamp="2026-01-01T00:00:00+00:00",
        details={
            "symbol": "XAUUSD",
        },
    )

    assert health.to_dict() == {
        "component": "market-agent",
        "status": "ok",
        "message": "Market agent healthy.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "details": {
            "symbol": "XAUUSD",
        },
    }


def test_component_health_to_event():
    health = ComponentHealth(
        component="risk-agent",
        status="warning",
        message="Risk threshold close.",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    event = health.to_event()
    payload = event.to_dict()

    assert payload["name"] == "health.risk-agent"
    assert payload["component"] == "risk-agent"
    assert payload["severity"] == "warning"
    assert payload["message"] == "Risk threshold close."
    assert payload["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert payload["attributes"]["status"] == "warning"


def test_component_health_defaults():
    health = ComponentHealth(
        component="api",
    )

    payload = health.to_dict()

    assert payload["component"] == "api"
    assert payload["status"] == "ok"
    assert payload["message"] == ""
    assert payload["timestamp"]
    assert payload["details"] == {}


def test_component_health_rejects_invalid_values():
    with pytest.raises(ValueError):
        ComponentHealth(component="")

    with pytest.raises(ValueError):
        ComponentHealth(component="api", status="bad")

    with pytest.raises(ValueError):
        ComponentHealth(component="api", message=123)

    with pytest.raises(ValueError):
        ComponentHealth(component="api", timestamp="")

    with pytest.raises(ValueError):
        ComponentHealth(component="api", details=[])


def test_build_component_health_with_timestamp():
    health = build_component_health(
        component="api",
        status="error",
        message="API failed.",
        details={
            "route": "/health",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert health.to_dict() == {
        "component": "api",
        "status": "error",
        "message": "API failed.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "details": {
            "route": "/health",
        },
    }


def test_validate_component_health_list():
    component = ComponentHealth(component="api")

    assert validate_component_health_list([component]) == [component]

    with pytest.raises(ValueError):
        validate_component_health_list("bad")

    with pytest.raises(ValueError):
        validate_component_health_list(["bad"])


def test_resolve_health_snapshot_status_from_components():
    assert resolve_health_snapshot_status(
        [
            ComponentHealth(component="api", status="ok"),
        ],
    ) == ObservabilityStatus.OK

    assert resolve_health_snapshot_status(
        [
            ComponentHealth(component="api", status="warning"),
        ],
    ) == ObservabilityStatus.WARNING

    assert resolve_health_snapshot_status(
        [
            ComponentHealth(component="api", status="error"),
        ],
    ) == ObservabilityStatus.ERROR


def test_resolve_health_snapshot_status_from_counts():
    assert resolve_health_snapshot_status(
        [],
        active_alerts=1,
    ) == ObservabilityStatus.WARNING

    assert resolve_health_snapshot_status(
        [],
        open_spans=1,
    ) == ObservabilityStatus.WARNING

    assert resolve_health_snapshot_status(
        [],
        error_logs=1,
    ) == ObservabilityStatus.ERROR


def test_resolve_health_snapshot_status_rejects_invalid_counts():
    with pytest.raises(ValueError):
        resolve_health_snapshot_status([], active_alerts=-1)

    with pytest.raises(ValueError):
        resolve_health_snapshot_status([], error_logs=-1)

    with pytest.raises(ValueError):
        resolve_health_snapshot_status([], open_spans=-1)


def test_build_metrics_summary_empty_and_from_registry():
    assert build_metrics_summary() == {
        "counters": 0,
        "gauges": 0,
        "histograms": 0,
        "points": 0,
        "counter_values": {},
        "gauge_values": {},
        "histogram_values": {},
    }

    registry = MetricsRegistry()
    registry.increment_counter("api.requests", "api")

    summary = build_metrics_summary(registry)

    assert summary["counters"] == 1
    assert summary["points"] == 1

    with pytest.raises(ValueError):
        build_metrics_summary("bad")


def test_build_logs_summary_empty_and_from_sink():
    assert build_logs_summary() == {
        "records": 0,
        "levels": {},
        "components": {},
    }

    sink = InMemoryLogSink()
    sink.write(
        StructuredLogRecord(
            message="API ok.",
            component="api",
            level="info",
        ),
    )
    sink.write(
        StructuredLogRecord(
            message="Risk failed.",
            component="risk-agent",
            level="error",
        ),
    )

    summary = build_logs_summary(sink)

    assert summary == {
        "records": 2,
        "levels": {
            "info": 1,
            "error": 1,
        },
        "components": {
            "api": 1,
            "risk-agent": 1,
        },
    }

    with pytest.raises(ValueError):
        build_logs_summary("bad")


def test_build_traces_summary_empty_and_from_store():
    assert build_traces_summary() == {
        "traces": 0,
        "spans": 0,
        "open_spans": 0,
        "finished_spans": 0,
        "trace_ids": [],
    }

    store = InMemoryTraceStore()
    trace = store.create_trace(trace_id="trace-1")
    trace.start_span(
        name="trade-workflow",
        component="orchestrator",
        span_id="span-1",
    )

    summary = build_traces_summary(store)

    assert summary["traces"] == 1
    assert summary["spans"] == 1
    assert summary["open_spans"] == 1

    with pytest.raises(ValueError):
        build_traces_summary("bad")


def test_build_alerts_summary_empty_and_from_manager():
    assert build_alerts_summary() == {
        "rules": 0,
        "alerts": 0,
        "active_alerts": 0,
        "resolved_alerts": 0,
        "suppressed_alerts": 0,
        "rule_names": [],
    }

    manager = AlertManager()
    manager.register_rule(
        AlertRule(
            name="high-latency",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold=200,
        ),
    )

    summary = build_alerts_summary(manager)

    assert summary["rules"] == 1
    assert summary["rule_names"] == [
        "high-latency",
    ]

    with pytest.raises(ValueError):
        build_alerts_summary("bad")


def test_observability_snapshot_to_dict():
    component = ComponentHealth(
        component="api",
        status="ok",
        message="API healthy.",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    snapshot = ObservabilitySnapshot(
        name="aqos-test",
        status="OK",
        timestamp="2026-01-01T00:00:01+00:00",
        components=[
            component,
        ],
        metrics_summary={
            "points": 1,
        },
        logs_summary={
            "records": 1,
        },
        traces_summary={
            "traces": 1,
        },
        alerts_summary={
            "active_alerts": 0,
        },
        details={
            "env": "test",
        },
    )

    assert snapshot.to_dict() == {
        "name": "aqos-test",
        "status": "ok",
        "timestamp": "2026-01-01T00:00:01+00:00",
        "components": [
            component.to_dict(),
        ],
        "metrics_summary": {
            "points": 1,
        },
        "logs_summary": {
            "records": 1,
        },
        "traces_summary": {
            "traces": 1,
        },
        "alerts_summary": {
            "active_alerts": 0,
        },
        "details": {
            "env": "test",
        },
    }


def test_observability_snapshot_to_event():
    snapshot = ObservabilitySnapshot(
        name="aqos-test",
        status="warning",
        timestamp="2026-01-01T00:00:01+00:00",
    )

    event = snapshot.to_event()
    payload = event.to_dict()

    assert payload["name"] == "health.snapshot.aqos-test"
    assert payload["component"] == "aqos-test"
    assert payload["severity"] == "warning"
    assert payload["message"] == "Observability snapshot status is warning."
    assert payload["timestamp"] == "2026-01-01T00:00:01+00:00"
    assert payload["attributes"]["status"] == "warning"


def test_observability_snapshot_rejects_invalid_values():
    with pytest.raises(ValueError):
        ObservabilitySnapshot(name="")

    with pytest.raises(ValueError):
        ObservabilitySnapshot(status="bad")

    with pytest.raises(ValueError):
        ObservabilitySnapshot(timestamp="")

    with pytest.raises(ValueError):
        ObservabilitySnapshot(components=["bad"])

    with pytest.raises(ValueError):
        ObservabilitySnapshot(metrics_summary=[])

    with pytest.raises(ValueError):
        ObservabilitySnapshot(logs_summary=[])

    with pytest.raises(ValueError):
        ObservabilitySnapshot(traces_summary=[])

    with pytest.raises(ValueError):
        ObservabilitySnapshot(alerts_summary=[])

    with pytest.raises(ValueError):
        ObservabilitySnapshot(details=[])


def test_build_observability_snapshot_resolves_status():
    snapshot = build_observability_snapshot(
        name="aqos-test",
        components=[
            ComponentHealth(component="api", status="ok"),
        ],
        logs_summary={
            "levels": {},
        },
        traces_summary={
            "open_spans": 0,
        },
        alerts_summary={
            "active_alerts": 0,
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert snapshot.status == ObservabilityStatus.OK

    warning_snapshot = build_observability_snapshot(
        name="aqos-test",
        alerts_summary={
            "active_alerts": 1,
        },
    )

    assert warning_snapshot.status == ObservabilityStatus.WARNING

    error_snapshot = build_observability_snapshot(
        name="aqos-test",
        logs_summary={
            "levels": {
                "error": 1,
            },
        },
    )

    assert error_snapshot.status == ObservabilityStatus.ERROR


def test_collect_observability_snapshot():
    registry = MetricsRegistry()
    registry.increment_counter("api.requests", "api")

    sink = InMemoryLogSink()
    sink.write(
        StructuredLogRecord(
            message="API ok.",
            component="api",
            level="info",
        ),
    )

    trace_store = InMemoryTraceStore()
    trace_store.create_trace(trace_id="trace-1")

    alert_manager = AlertManager()
    alert_manager.register_rule(
        AlertRule(
            name="high-latency",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold=200,
        ),
    )

    snapshot = collect_observability_snapshot(
        name="aqos-test",
        components=[
            ComponentHealth(component="api", status="ok"),
        ],
        metrics_registry=registry,
        log_sink=sink,
        trace_store=trace_store,
        alert_manager=alert_manager,
        details={
            "env": "test",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    payload = snapshot.to_dict()

    assert payload["name"] == "aqos-test"
    assert payload["status"] == "ok"
    assert payload["metrics_summary"]["points"] == 1
    assert payload["logs_summary"]["records"] == 1
    assert payload["traces_summary"]["traces"] == 1
    assert payload["alerts_summary"]["rules"] == 1
    assert payload["details"] == {
        "env": "test",
    }


def test_observability_health_exports_exist():
    import aqos.observability as observability

    expected_exports = [
        "ComponentHealth",
        "ObservabilitySnapshot",
        "build_alerts_summary",
        "build_component_health",
        "build_logs_summary",
        "build_metrics_summary",
        "build_observability_snapshot",
        "build_traces_summary",
        "collect_observability_snapshot",
        "resolve_health_snapshot_status",
        "validate_component_health_list",
        "validate_health_message",
        "validate_non_negative_integer",
    ]

    for export_name in expected_exports:
        assert hasattr(observability, export_name), export_name