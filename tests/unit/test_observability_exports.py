"""
Unit tests for AQOS observability package exports.
"""

import inspect

import aqos.observability as observability


EXPECTED_OBSERVABILITY_EXPORTS = [
    "AlertManager",
    "AlertOperator",
    "AlertRecord",
    "AlertRule",
    "AlertState",
    "ComponentHealth",
    "CounterMetric",
    "GaugeMetric",
    "HistogramMetric",
    "InMemoryLogSink",
    "InMemoryTraceStore",
    "LogLevel",
    "MetricPoint",
    "MetricType",
    "MetricsRegistry",
    "ObservabilityBundle",
    "ObservabilityEvent",
    "ObservabilitySeverity",
    "ObservabilitySnapshot",
    "ObservabilityStatus",
    "ObservedOperationResult",
    "StructuredLogRecord",
    "StructuredLogger",
    "TraceContext",
    "TraceSpan",
    "TraceStatus",
    "build_alert_id",
    "build_alert_record",
    "build_alert_rule",
    "build_alerts_summary",
    "build_component_health",
    "build_log_record",
    "build_logger",
    "build_logs_summary",
    "build_metric_point",
    "build_metrics_summary",
    "build_observability_bundle",
    "build_observability_event",
    "build_observability_snapshot",
    "build_operation_attributes",
    "build_span_id",
    "build_trace_id",
    "build_trace_span",
    "build_traces_summary",
    "calculate_duration_ms",
    "collect_observability_snapshot",
    "compact_log_record",
    "compact_trace_payload",
    "compare_alert_values",
    "finish_observed_operation",
    "log_exception",
    "merge_attributes",
    "merge_log_attributes",
    "metric_key",
    "normalize_alert_operator",
    "normalize_alert_state",
    "normalize_log_level",
    "normalize_metric_type",
    "normalize_severity",
    "normalize_status",
    "normalize_trace_status",
    "record_observed_exception",
    "record_observed_metric",
    "resolve_health_snapshot_status",
    "run_observed_operation",
    "start_observed_operation",
    "validate_alert_message",
    "validate_attributes",
    "validate_component_health_list",
    "validate_duration_ms",
    "validate_health_message",
    "validate_metric_name",
    "validate_metric_value",
    "validate_non_empty_string",
    "validate_non_negative_integer",
    "validate_observability_bundle",
    "validate_operation_name",
    "validate_span_id",
    "validate_string",
    "validate_trace_id",
]


def test_observability_exports_are_complete():
    assert observability.__all__ == EXPECTED_OBSERVABILITY_EXPORTS


def test_observability_exports_are_unique():
    assert len(observability.__all__) == len(set(observability.__all__))


def test_observability_exports_are_sorted():
    assert observability.__all__ == sorted(observability.__all__)


def test_observability_exports_exist_on_package():
    for export_name in EXPECTED_OBSERVABILITY_EXPORTS:
        assert hasattr(observability, export_name), export_name


def test_observability_class_exports_are_classes():
    class_exports = [
        export_name
        for export_name in EXPECTED_OBSERVABILITY_EXPORTS
        if export_name[0].isupper()
    ]

    for export_name in class_exports:
        exported = getattr(observability, export_name)
        assert inspect.isclass(exported), export_name


def test_observability_function_exports_are_callables():
    function_exports = [
        export_name
        for export_name in EXPECTED_OBSERVABILITY_EXPORTS
        if not export_name[0].isupper()
    ]

    for export_name in function_exports:
        exported = getattr(observability, export_name)
        assert callable(exported), export_name


def test_core_observability_exports_import_directly():
    from aqos.observability import (  # noqa: PLC0415
        AlertManager,
        ComponentHealth,
        InMemoryLogSink,
        InMemoryTraceStore,
        MetricsRegistry,
        ObservabilityBundle,
        ObservabilityEvent,
        ObservabilitySnapshot,
        build_observability_bundle,
        collect_observability_snapshot,
    )

    assert AlertManager is observability.AlertManager
    assert ComponentHealth is observability.ComponentHealth
    assert InMemoryLogSink is observability.InMemoryLogSink
    assert InMemoryTraceStore is observability.InMemoryTraceStore
    assert MetricsRegistry is observability.MetricsRegistry
    assert ObservabilityBundle is observability.ObservabilityBundle
    assert ObservabilityEvent is observability.ObservabilityEvent
    assert ObservabilitySnapshot is observability.ObservabilitySnapshot
    assert build_observability_bundle is observability.build_observability_bundle
    assert collect_observability_snapshot is observability.collect_observability_snapshot


def test_observability_export_groups_exist():
    base_exports = {
        "ObservabilityEvent",
        "ObservabilitySeverity",
        "ObservabilityStatus",
        "build_observability_event",
    }

    metric_exports = {
        "CounterMetric",
        "GaugeMetric",
        "HistogramMetric",
        "MetricPoint",
        "MetricType",
        "MetricsRegistry",
    }

    logging_exports = {
        "InMemoryLogSink",
        "LogLevel",
        "StructuredLogRecord",
        "StructuredLogger",
    }

    tracing_exports = {
        "InMemoryTraceStore",
        "TraceContext",
        "TraceSpan",
        "TraceStatus",
    }

    alert_exports = {
        "AlertManager",
        "AlertOperator",
        "AlertRecord",
        "AlertRule",
        "AlertState",
    }

    health_exports = {
        "ComponentHealth",
        "ObservabilitySnapshot",
        "collect_observability_snapshot",
    }

    integration_exports = {
        "ObservabilityBundle",
        "ObservedOperationResult",
        "run_observed_operation",
    }

    all_exports = set(observability.__all__)

    assert base_exports.issubset(all_exports)
    assert metric_exports.issubset(all_exports)
    assert logging_exports.issubset(all_exports)
    assert tracing_exports.issubset(all_exports)
    assert alert_exports.issubset(all_exports)
    assert health_exports.issubset(all_exports)
    assert integration_exports.issubset(all_exports)