"""
Unit tests for AQOS observability metrics.
"""

import pytest

from aqos.observability import (
    CounterMetric,
    GaugeMetric,
    HistogramMetric,
    MetricPoint,
    MetricType,
    MetricsRegistry,
    build_metric_point,
    merge_attributes,
    metric_key,
    normalize_metric_type,
    validate_metric_name,
    validate_metric_value,
)


def test_metric_type_values():
    assert MetricType.COUNTER.value == "counter"
    assert MetricType.GAUGE.value == "gauge"
    assert MetricType.HISTOGRAM.value == "histogram"


def test_normalize_metric_type_accepts_enum_and_string():
    assert normalize_metric_type(MetricType.COUNTER) == MetricType.COUNTER
    assert normalize_metric_type(" COUNTER ") == MetricType.COUNTER
    assert normalize_metric_type("gauge") == MetricType.GAUGE
    assert normalize_metric_type("HISTOGRAM") == MetricType.HISTOGRAM


def test_normalize_metric_type_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_metric_type("bad")

    with pytest.raises(ValueError):
        normalize_metric_type("")


def test_validate_metric_name_accepts_valid_name():
    assert validate_metric_name("api.requests") == "api.requests"


def test_validate_metric_name_rejects_invalid_name():
    with pytest.raises(ValueError):
        validate_metric_name("")

    with pytest.raises(ValueError):
        validate_metric_name("api requests")


def test_validate_metric_value_accepts_numeric_values():
    assert validate_metric_value(1) == 1.0
    assert validate_metric_value(1.5) == 1.5


def test_validate_metric_value_rejects_invalid_values():
    with pytest.raises(ValueError):
        validate_metric_value(True)

    with pytest.raises(ValueError):
        validate_metric_value("1")


def test_metric_key_builds_stable_key():
    assert metric_key("api.requests", "api") == "api.requests::api"


def test_merge_attributes_merges_dictionaries():
    assert merge_attributes(
        {
            "symbol": "XAUUSD",
        },
        {
            "timeframe": "H1",
        },
    ) == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_merge_attributes_rejects_invalid_values():
    with pytest.raises(ValueError):
        merge_attributes([], {})

    with pytest.raises(ValueError):
        merge_attributes({}, [])


def test_metric_point_to_dict():
    point = MetricPoint(
        name="api.requests",
        metric_type="COUNTER",
        value=3,
        component="api",
        timestamp="2026-01-01T00:00:00+00:00",
        unit="count",
        attributes={
            "route": "/health",
        },
    )

    assert point.to_dict() == {
        "name": "api.requests",
        "metric_type": "counter",
        "value": 3.0,
        "component": "api",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "unit": "count",
        "attributes": {
            "route": "/health",
        },
    }


def test_metric_point_to_event():
    point = MetricPoint(
        name="api.requests",
        metric_type="counter",
        value=3,
        component="api",
        timestamp="2026-01-01T00:00:00+00:00",
        unit="count",
    )

    event = point.to_event()
    payload = event.to_dict()

    assert payload["name"] == "metric.api.requests"
    assert payload["component"] == "api"
    assert payload["severity"] == "info"
    assert payload["message"] == "Metric api.requests recorded."
    assert payload["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert payload["attributes"]["metric_type"] == "counter"
    assert payload["attributes"]["value"] == 3.0


def test_metric_point_rejects_invalid_values():
    with pytest.raises(ValueError):
        MetricPoint(
            name="",
            metric_type="counter",
            value=1,
            component="api",
        )

    with pytest.raises(ValueError):
        MetricPoint(
            name="api.requests",
            metric_type="bad",
            value=1,
            component="api",
        )

    with pytest.raises(ValueError):
        MetricPoint(
            name="api.requests",
            metric_type="counter",
            value="bad",
            component="api",
        )

    with pytest.raises(ValueError):
        MetricPoint(
            name="api.requests",
            metric_type="counter",
            value=1,
            component="",
        )


def test_build_metric_point_with_timestamp():
    point = build_metric_point(
        name="api.latency",
        metric_type="histogram",
        value=25,
        component="api",
        unit="ms",
        attributes={
            "route": "/health",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert point.to_dict() == {
        "name": "api.latency",
        "metric_type": "histogram",
        "value": 25.0,
        "component": "api",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "unit": "ms",
        "attributes": {
            "route": "/health",
        },
    }


def test_counter_metric_increment():
    counter = CounterMetric(
        name="api.requests",
        component="api",
        attributes={
            "route": "/health",
        },
    )

    point = counter.increment(
        2,
        method="GET",
    )

    assert counter.value == 2.0
    assert point.to_dict()["metric_type"] == "counter"
    assert point.to_dict()["value"] == 2.0
    assert point.to_dict()["attributes"] == {
        "route": "/health",
        "method": "GET",
    }


def test_counter_metric_rejects_negative_values():
    with pytest.raises(ValueError):
        CounterMetric(
            name="api.requests",
            component="api",
            value=-1,
        )

    counter = CounterMetric(
        name="api.requests",
        component="api",
    )

    with pytest.raises(ValueError):
        counter.increment(-1)


def test_gauge_metric_set_increment_and_decrement():
    gauge = GaugeMetric(
        name="active.positions",
        component="execution",
        unit="positions",
    )

    point = gauge.set(5)
    assert point.value == 5.0

    point = gauge.increment(2)
    assert point.value == 7.0

    point = gauge.decrement(3)
    assert point.value == 4.0

    assert gauge.value == 4.0
    assert point.to_dict()["metric_type"] == "gauge"


def test_histogram_metric_observe_and_summary():
    histogram = HistogramMetric(
        name="api.latency",
        component="api",
        unit="ms",
    )

    point_1 = histogram.observe(25)
    point_2 = histogram.observe(75)

    assert point_1.value == 25.0
    assert point_2.value == 75.0
    assert histogram.count == 2
    assert histogram.total == 100.0
    assert histogram.minimum == 25.0
    assert histogram.maximum == 75.0
    assert histogram.mean == 50.0

    assert histogram.summary() == {
        "name": "api.latency",
        "component": "api",
        "metric_type": "histogram",
        "unit": "ms",
        "count": 2,
        "total": 100.0,
        "min": 25.0,
        "max": 75.0,
        "mean": 50.0,
        "attributes": {},
    }


def test_histogram_metric_empty_summary():
    histogram = HistogramMetric(
        name="api.latency",
        component="api",
        unit="ms",
    )

    assert histogram.summary() == {
        "name": "api.latency",
        "component": "api",
        "metric_type": "histogram",
        "unit": "ms",
        "count": 0,
        "total": 0.0,
        "min": None,
        "max": None,
        "mean": None,
        "attributes": {},
    }


def test_metrics_registry_records_metrics():
    registry = MetricsRegistry()

    counter_point = registry.increment_counter(
        name="api.requests",
        component="api",
        amount=2,
        attributes={
            "route": "/health",
        },
    )

    gauge_point = registry.set_gauge(
        name="active.positions",
        component="execution",
        value=3,
        unit="positions",
    )

    histogram_point = registry.observe_histogram(
        name="api.latency",
        component="api",
        value=25,
        unit="ms",
    )

    assert counter_point.value == 2.0
    assert gauge_point.value == 3.0
    assert histogram_point.value == 25.0

    assert len(registry.latest_points()) == 3
    assert len(registry.latest_points(limit=2)) == 2

    summary = registry.summary()

    assert summary["counters"] == 1
    assert summary["gauges"] == 1
    assert summary["histograms"] == 1
    assert summary["points"] == 3
    assert summary["counter_values"]["api.requests::api"] == 2.0
    assert summary["gauge_values"]["active.positions::execution"] == 3.0
    assert summary["histogram_values"]["api.latency::api"]["count"] == 1


def test_metrics_registry_reuses_metric_instances():
    registry = MetricsRegistry()

    first = registry.counter("api.requests", "api")
    second = registry.counter("api.requests", "api")

    assert first is second

    registry.increment_counter("api.requests", "api")
    registry.increment_counter("api.requests", "api")

    assert first.value == 2.0


def test_metrics_registry_record_rejects_invalid_point():
    registry = MetricsRegistry()

    with pytest.raises(ValueError):
        registry.record("bad")


def test_metrics_registry_latest_points_rejects_invalid_limit():
    registry = MetricsRegistry()

    with pytest.raises(ValueError):
        registry.latest_points(limit=0)

    with pytest.raises(ValueError):
        registry.latest_points(limit="bad")


def test_metrics_registry_clear_points_and_clear():
    registry = MetricsRegistry()

    registry.increment_counter("api.requests", "api")
    registry.set_gauge("active.positions", "execution", 2)
    registry.observe_histogram("api.latency", "api", 25)

    assert registry.summary()["points"] == 3

    registry.clear_points()

    assert registry.summary()["points"] == 0
    assert registry.summary()["counters"] == 1

    registry.clear()

    assert registry.summary()["points"] == 0
    assert registry.summary()["counters"] == 0
    assert registry.summary()["gauges"] == 0
    assert registry.summary()["histograms"] == 0


def test_observability_metrics_exports_exist():
    import aqos.observability as observability

    expected_exports = [
        "CounterMetric",
        "GaugeMetric",
        "HistogramMetric",
        "MetricPoint",
        "MetricType",
        "MetricsRegistry",
        "build_metric_point",
        "merge_attributes",
        "metric_key",
        "normalize_metric_type",
        "validate_metric_name",
        "validate_metric_value",
    ]

    for export_name in expected_exports:
        assert hasattr(observability, export_name), export_name