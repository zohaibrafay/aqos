"""
Unit tests for AQOS observability integration helpers.
"""

import pytest

from aqos.observability import (
    AlertRule,
    ComponentHealth,
    MetricPoint,
    MetricsRegistry,
    ObservabilityBundle,
    ObservedOperationResult,
    build_observability_bundle,
    build_operation_attributes,
    finish_observed_operation,
    record_observed_exception,
    record_observed_metric,
    run_observed_operation,
    start_observed_operation,
    validate_observability_bundle,
    validate_operation_name,
)


def test_validate_operation_name():
    assert validate_operation_name("trade-workflow") == "trade-workflow"

    with pytest.raises(ValueError):
        validate_operation_name("")

    with pytest.raises(ValueError):
        validate_operation_name("trade workflow")


def test_build_operation_attributes():
    attributes = build_operation_attributes(
        operation="trade-workflow",
        component="orchestrator",
        trace_id="trace-1",
        span_id="span-1",
        attributes={
            "symbol": "XAUUSD",
        },
    )

    assert attributes == {
        "operation": "trade-workflow",
        "component": "orchestrator",
        "trace_id": "trace-1",
        "span_id": "span-1",
        "symbol": "XAUUSD",
    }


def test_build_operation_attributes_rejects_invalid_values():
    with pytest.raises(ValueError):
        build_operation_attributes(
            operation="",
            component="api",
        )

    with pytest.raises(ValueError):
        build_operation_attributes(
            operation="api-health",
            component="",
        )

    with pytest.raises(ValueError):
        build_operation_attributes(
            operation="api-health",
            component="api",
            attributes=[],
        )


def test_observed_operation_result_to_dict_success():
    result = ObservedOperationResult(
        operation="trade-workflow",
        component="orchestrator",
        success=True,
        trace_id="trace-1",
        span_id="span-1",
        result={
            "status": "ok",
        },
        duration_ms=1000,
        attributes={
            "symbol": "XAUUSD",
        },
    )

    assert result.to_dict() == {
        "operation": "trade-workflow",
        "component": "orchestrator",
        "success": True,
        "trace_id": "trace-1",
        "span_id": "span-1",
        "result": {
            "status": "ok",
        },
        "duration_ms": 1000,
        "attributes": {
            "symbol": "XAUUSD",
        },
    }


def test_observed_operation_result_to_dict_error():
    result = ObservedOperationResult(
        operation="risk-check",
        component="risk-agent",
        success=False,
        trace_id="trace-1",
        span_id="span-1",
        error="Invalid stop loss.",
    )

    assert result.to_dict() == {
        "operation": "risk-check",
        "component": "risk-agent",
        "success": False,
        "trace_id": "trace-1",
        "span_id": "span-1",
        "error": "Invalid stop loss.",
        "attributes": {},
    }


def test_observed_operation_result_rejects_invalid_values():
    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="",
            component="api",
            success=True,
            trace_id="trace-1",
            span_id="span-1",
        )

    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="api-health",
            component="",
            success=True,
            trace_id="trace-1",
            span_id="span-1",
        )

    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="api-health",
            component="api",
            success="yes",
            trace_id="trace-1",
            span_id="span-1",
        )

    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="api-health",
            component="api",
            success=False,
            trace_id="",
            span_id="span-1",
        )

    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="api-health",
            component="api",
            success=False,
            trace_id="trace-1",
            span_id="",
        )

    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="api-health",
            component="api",
            success=False,
            trace_id="trace-1",
            span_id="span-1",
            error="",
        )

    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="api-health",
            component="api",
            success=True,
            trace_id="trace-1",
            span_id="span-1",
            duration_ms=-1,
        )

    with pytest.raises(ValueError):
        ObservedOperationResult(
            operation="api-health",
            component="api",
            success=True,
            trace_id="trace-1",
            span_id="span-1",
            attributes=[],
        )


def test_build_observability_bundle_defaults():
    bundle = build_observability_bundle(
        attributes={
            "env": "test",
        },
    )

    assert isinstance(bundle, ObservabilityBundle)
    assert isinstance(bundle.metrics_registry, MetricsRegistry)
    assert bundle.attributes == {
        "env": "test",
    }
    assert bundle.summary()["status"] == "ok"


def test_validate_observability_bundle_rejects_invalid_values():
    bundle = build_observability_bundle()
    assert validate_observability_bundle(bundle) is bundle

    with pytest.raises(ValueError):
        ObservabilityBundle(metrics_registry="bad")

    with pytest.raises(ValueError):
        ObservabilityBundle(log_sink="bad")

    with pytest.raises(ValueError):
        ObservabilityBundle(trace_store="bad")

    with pytest.raises(ValueError):
        ObservabilityBundle(alert_manager="bad")

    with pytest.raises(ValueError):
        ObservabilityBundle(components=["bad"])

    with pytest.raises(ValueError):
        ObservabilityBundle(attributes=[])


def test_bundle_logger_writes_to_shared_sink():
    bundle = build_observability_bundle(
        attributes={
            "env": "test",
        },
    )

    logger = bundle.logger(
        "api",
        default_attributes={
            "route": "/health",
        },
    )

    record = logger.info("API healthy.")

    assert bundle.log_sink.count() == 1
    assert record.to_dict()["attributes"] == {
        "env": "test",
        "route": "/health",
    }


def test_bundle_component_health_and_snapshot():
    bundle = build_observability_bundle()

    component = bundle.add_component_health(
        ComponentHealth(
            component="api",
            status="ok",
        ),
    )

    snapshot = bundle.snapshot(
        name="aqos-test",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert snapshot.to_dict()["name"] == "aqos-test"
    assert snapshot.to_dict()["status"] == "ok"
    assert snapshot.to_dict()["components"] == [
        component.to_dict(),
    ]


def test_bundle_add_component_health_rejects_invalid_value():
    bundle = build_observability_bundle()

    with pytest.raises(ValueError):
        bundle.add_component_health("bad")


def test_record_observed_metric_records_and_emits_alert():
    bundle = build_observability_bundle()

    bundle.alert_manager.register_rule(
        AlertRule(
            name="high-api-latency",
            metric_name="api.latency",
            component="api",
            operator=">",
            threshold=200,
            message="API latency is high.",
        ),
    )

    point = MetricPoint(
        name="api.latency",
        metric_type="histogram",
        value=250,
        component="api",
        unit="ms",
    )

    emitted = record_observed_metric(bundle, point)

    assert len(emitted) == 1
    assert emitted[0].rule_name == "high-api-latency"
    assert bundle.metrics_registry.summary()["points"] == 1
    assert bundle.alert_manager.summary()["alerts"] == 1
    assert bundle.log_sink.count() == 1
    assert bundle.log_sink.latest()[0].event_name == "alert.high-api-latency"


def test_record_observed_metric_without_alert_evaluation():
    bundle = build_observability_bundle()

    point = MetricPoint(
        name="api.latency",
        metric_type="histogram",
        value=250,
        component="api",
        unit="ms",
    )

    emitted = record_observed_metric(
        bundle,
        point,
        evaluate_alerts=False,
    )

    assert emitted == []
    assert bundle.metrics_registry.summary()["points"] == 1
    assert bundle.alert_manager.summary()["alerts"] == 0


def test_record_observed_metric_rejects_invalid_values():
    bundle = build_observability_bundle()

    with pytest.raises(ValueError):
        record_observed_metric(bundle, "bad")

    with pytest.raises(ValueError):
        bundle.record_metric(
            MetricPoint(
                name="api.latency",
                metric_type="histogram",
                value=250,
                component="api",
            ),
            evaluate_alerts="yes",
        )

    with pytest.raises(ValueError):
        bundle.record_metric(
            MetricPoint(
                name="api.latency",
                metric_type="histogram",
                value=250,
                component="api",
            ),
            log_alerts="yes",
        )


def test_start_observed_operation():
    bundle = build_observability_bundle(
        attributes={
            "env": "test",
        },
    )

    span = start_observed_operation(
        bundle,
        operation="trade-workflow",
        component="orchestrator",
        trace_id="trace-1",
        span_id="span-1",
        attributes={
            "symbol": "XAUUSD",
        },
        start_time="2026-01-01T00:00:00+00:00",
    )

    assert span.trace_id == "trace-1"
    assert span.span_id == "span-1"
    assert span.name == "trade-workflow"
    assert span.component == "orchestrator"
    assert span.attributes == {
        "env": "test",
        "symbol": "XAUUSD",
    }

    assert bundle.trace_store.summary()["traces"] == 1
    assert bundle.trace_store.summary()["spans"] == 1
    assert bundle.log_sink.count() == 1
    assert bundle.metrics_registry.summary()["points"] == 1


def test_finish_observed_operation_success():
    bundle = build_observability_bundle()

    span = start_observed_operation(
        bundle,
        operation="trade-workflow",
        component="orchestrator",
        trace_id="trace-1",
        span_id="span-1",
        start_time="2026-01-01T00:00:00+00:00",
    )

    result = finish_observed_operation(
        bundle,
        span,
        result={
            "order_id": "order-1",
        },
        end_time="2026-01-01T00:00:01+00:00",
    )

    assert result.to_dict() == {
        "operation": "trade-workflow",
        "component": "orchestrator",
        "success": True,
        "trace_id": "trace-1",
        "span_id": "span-1",
        "result": {
            "order_id": "order-1",
        },
        "duration_ms": 1000.0,
        "attributes": {
            "operation": "trade-workflow",
            "component": "orchestrator",
            "trace_id": "trace-1",
            "span_id": "span-1",
        },
    }

    assert span.status.value == "success"
    assert bundle.log_sink.count() == 2
    assert bundle.metrics_registry.summary()["points"] == 3


def test_finish_observed_operation_failure():
    bundle = build_observability_bundle()

    span = start_observed_operation(
        bundle,
        operation="risk-check",
        component="risk-agent",
        trace_id="trace-1",
        span_id="span-1",
        start_time="2026-01-01T00:00:00+00:00",
    )

    result = finish_observed_operation(
        bundle,
        span,
        success=False,
        error="Invalid stop loss.",
        end_time="2026-01-01T00:00:01+00:00",
    )

    assert result.success is False
    assert result.error == "Invalid stop loss."
    assert span.status.value == "error"
    assert bundle.log_sink.latest()[-1].level.value == "error"
    assert bundle.metrics_registry.summary()["points"] == 3


def test_finish_observed_operation_rejects_invalid_values():
    bundle = build_observability_bundle()

    with pytest.raises(ValueError):
        finish_observed_operation(
            bundle,
            "bad",
        )

    span = start_observed_operation(
        bundle,
        operation="api-health",
        component="api",
    )

    with pytest.raises(ValueError):
        finish_observed_operation(
            bundle,
            span,
            success="yes",
        )


def test_record_observed_exception():
    bundle = build_observability_bundle()

    span = start_observed_operation(
        bundle,
        operation="risk-check",
        component="risk-agent",
        trace_id="trace-1",
        span_id="span-1",
        start_time="2026-01-01T00:00:00+00:00",
    )

    exception = ValueError("Invalid stop loss.")

    result = record_observed_exception(
        bundle,
        span,
        exception,
        message="Risk validation failed.",
        attributes={
            "symbol": "XAUUSD",
        },
        end_time="2026-01-01T00:00:01+00:00",
    )

    assert result.success is False
    assert result.error == "Invalid stop loss."
    assert result.duration_ms == 1000.0
    assert span.status.value == "error"
    assert bundle.log_sink.latest()[-1].event_name == "log.exception"
    assert bundle.metrics_registry.summary()["points"] == 3


def test_record_observed_exception_rejects_invalid_values():
    bundle = build_observability_bundle()

    span = start_observed_operation(
        bundle,
        operation="risk-check",
        component="risk-agent",
    )

    with pytest.raises(ValueError):
        record_observed_exception(
            bundle,
            "bad",
            ValueError("Invalid."),
        )

    with pytest.raises(ValueError):
        record_observed_exception(
            bundle,
            span,
            "bad",
        )


def test_run_observed_operation_success():
    bundle = build_observability_bundle()

    result = run_observed_operation(
        lambda: {
            "status": "ok",
        },
        bundle,
        operation="api-health",
        component="api",
        trace_id="trace-1",
        span_id="span-1",
        start_time="2026-01-01T00:00:00+00:00",
        end_time="2026-01-01T00:00:01+00:00",
    )

    assert result.success is True
    assert result.result == {
        "status": "ok",
    }
    assert result.duration_ms == 1000.0
    assert bundle.trace_store.summary()["finished_spans"] == 1
    assert bundle.log_sink.count() == 2


def test_run_observed_operation_exception():
    bundle = build_observability_bundle()

    def failing_operation():
        raise ValueError("Boom.")

    result = run_observed_operation(
        failing_operation,
        bundle,
        operation="api-health",
        component="api",
        trace_id="trace-1",
        span_id="span-1",
        start_time="2026-01-01T00:00:00+00:00",
        end_time="2026-01-01T00:00:01+00:00",
    )

    assert result.success is False
    assert result.error == "Boom."
    assert result.duration_ms == 1000.0
    assert bundle.trace_store.summary()["finished_spans"] == 1
    assert bundle.log_sink.latest()[-1].event_name == "log.exception"


def test_run_observed_operation_rejects_invalid_callable():
    bundle = build_observability_bundle()

    with pytest.raises(ValueError):
        run_observed_operation(
            "bad",
            bundle,
            operation="api-health",
            component="api",
        )


def test_bundle_clear():
    bundle = build_observability_bundle()

    bundle.add_component_health(
        ComponentHealth(component="api"),
    )
    start_observed_operation(
        bundle,
        operation="api-health",
        component="api",
    )

    assert bundle.summary()["metrics_summary"]["points"] == 1
    assert bundle.summary()["logs_summary"]["records"] == 1
    assert bundle.summary()["traces_summary"]["traces"] == 1
    assert len(bundle.components) == 1

    bundle.clear()

    assert bundle.summary()["metrics_summary"]["points"] == 0
    assert bundle.summary()["logs_summary"]["records"] == 0
    assert bundle.summary()["traces_summary"]["traces"] == 0
    assert len(bundle.components) == 0


def test_observability_integration_exports_exist():
    import aqos.observability as observability

    expected_exports = [
        "ObservabilityBundle",
        "ObservedOperationResult",
        "build_observability_bundle",
        "build_operation_attributes",
        "finish_observed_operation",
        "record_observed_exception",
        "record_observed_metric",
        "run_observed_operation",
        "start_observed_operation",
        "validate_observability_bundle",
        "validate_operation_name",
    ]

    for export_name in expected_exports:
        assert hasattr(observability, export_name), export_name