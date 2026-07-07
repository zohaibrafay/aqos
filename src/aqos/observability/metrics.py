"""
AQOS observability metrics primitives.

This module provides dependency-free metric objects and an in-memory registry
for counters, gauges, and distribution-style metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.observability.base import (
    ObservabilityEvent,
    build_observability_event,
    validate_attributes,
    validate_non_empty_string,
)


class MetricType(str, Enum):
    """Supported metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"


@dataclass(frozen=True)
class MetricPoint:
    """Single metric data point."""

    name: str
    metric_type: MetricType | str
    value: float
    component: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    unit: str = "count"
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_metric_name(self.name)
        normalize_metric_type(self.metric_type)
        validate_metric_value(self.value)
        validate_non_empty_string(self.component, "Component")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_non_empty_string(self.unit, "Unit")
        validate_attributes(self.attributes)

    def to_dict(self) -> dict[str, Any]:
        """Convert metric point into a serializable dictionary."""
        return {
            "name": self.name.strip(),
            "metric_type": normalize_metric_type(self.metric_type).value,
            "value": float(self.value),
            "component": self.component.strip(),
            "timestamp": self.timestamp.strip(),
            "unit": self.unit.strip(),
            "attributes": dict(self.attributes),
        }

    def to_event(self) -> ObservabilityEvent:
        """Convert metric point into an observability event."""
        return build_observability_event(
            name=f"metric.{self.name.strip()}",
            component=self.component,
            severity="info",
            message=f"Metric {self.name.strip()} recorded.",
            attributes=self.to_dict(),
            timestamp=self.timestamp,
        )


@dataclass
class CounterMetric:
    """Monotonic increasing counter metric."""

    name: str
    component: str
    unit: str = "count"
    attributes: dict[str, Any] = field(default_factory=dict)
    value: float = 0.0

    def __post_init__(self) -> None:
        validate_metric_name(self.name)
        validate_non_empty_string(self.component, "Component")
        validate_non_empty_string(self.unit, "Unit")
        validate_attributes(self.attributes)
        validate_metric_value(self.value)

        if self.value < 0:
            raise ValueError("Counter value cannot be negative.")

    def increment(self, amount: float = 1.0, **attributes: Any) -> MetricPoint:
        """Increment counter and return latest metric point."""
        validate_metric_value(amount)

        if amount < 0:
            raise ValueError("Counter increment amount cannot be negative.")

        self.value += float(amount)

        return self.to_point(attributes=attributes)

    def to_point(self, *, attributes: dict[str, Any] | None = None) -> MetricPoint:
        """Return current counter value as metric point."""
        merged_attributes = merge_attributes(self.attributes, attributes or {})

        return MetricPoint(
            name=self.name,
            metric_type=MetricType.COUNTER,
            value=self.value,
            component=self.component,
            unit=self.unit,
            attributes=merged_attributes,
        )


@dataclass
class GaugeMetric:
    """Gauge metric that can move up or down."""

    name: str
    component: str
    unit: str = "value"
    attributes: dict[str, Any] = field(default_factory=dict)
    value: float = 0.0

    def __post_init__(self) -> None:
        validate_metric_name(self.name)
        validate_non_empty_string(self.component, "Component")
        validate_non_empty_string(self.unit, "Unit")
        validate_attributes(self.attributes)
        validate_metric_value(self.value)

    def set(self, value: float, **attributes: Any) -> MetricPoint:
        """Set gauge value and return latest metric point."""
        validate_metric_value(value)
        self.value = float(value)

        return self.to_point(attributes=attributes)

    def increment(self, amount: float = 1.0, **attributes: Any) -> MetricPoint:
        """Increment gauge value and return latest metric point."""
        validate_metric_value(amount)
        self.value += float(amount)

        return self.to_point(attributes=attributes)

    def decrement(self, amount: float = 1.0, **attributes: Any) -> MetricPoint:
        """Decrement gauge value and return latest metric point."""
        validate_metric_value(amount)
        self.value -= float(amount)

        return self.to_point(attributes=attributes)

    def to_point(self, *, attributes: dict[str, Any] | None = None) -> MetricPoint:
        """Return current gauge value as metric point."""
        merged_attributes = merge_attributes(self.attributes, attributes or {})

        return MetricPoint(
            name=self.name,
            metric_type=MetricType.GAUGE,
            value=self.value,
            component=self.component,
            unit=self.unit,
            attributes=merged_attributes,
        )


@dataclass
class HistogramMetric:
    """Simple distribution metric storing observed values."""

    name: str
    component: str
    unit: str = "value"
    attributes: dict[str, Any] = field(default_factory=dict)
    values: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_metric_name(self.name)
        validate_non_empty_string(self.component, "Component")
        validate_non_empty_string(self.unit, "Unit")
        validate_attributes(self.attributes)

        for value in self.values:
            validate_metric_value(value)

        self.values = [float(value) for value in self.values]

    def observe(self, value: float, **attributes: Any) -> MetricPoint:
        """Observe a value and return metric point for the observation."""
        validate_metric_value(value)
        self.values.append(float(value))

        merged_attributes = merge_attributes(
            self.attributes,
            {
                **attributes,
                "count": self.count,
                "min": self.minimum,
                "max": self.maximum,
                "mean": self.mean,
            },
        )

        return MetricPoint(
            name=self.name,
            metric_type=MetricType.HISTOGRAM,
            value=float(value),
            component=self.component,
            unit=self.unit,
            attributes=merged_attributes,
        )

    @property
    def count(self) -> int:
        """Return number of observations."""
        return len(self.values)

    @property
    def total(self) -> float:
        """Return total observed value."""
        return float(sum(self.values))

    @property
    def minimum(self) -> float | None:
        """Return minimum observed value."""
        if not self.values:
            return None

        return float(min(self.values))

    @property
    def maximum(self) -> float | None:
        """Return maximum observed value."""
        if not self.values:
            return None

        return float(max(self.values))

    @property
    def mean(self) -> float | None:
        """Return mean observed value."""
        if not self.values:
            return None

        return self.total / self.count

    def summary(self) -> dict[str, Any]:
        """Return histogram summary."""
        return {
            "name": self.name.strip(),
            "component": self.component.strip(),
            "metric_type": MetricType.HISTOGRAM.value,
            "unit": self.unit.strip(),
            "count": self.count,
            "total": self.total,
            "min": self.minimum,
            "max": self.maximum,
            "mean": self.mean,
            "attributes": dict(self.attributes),
        }


@dataclass
class MetricsRegistry:
    """In-memory metrics registry."""

    counters: dict[str, CounterMetric] = field(default_factory=dict)
    gauges: dict[str, GaugeMetric] = field(default_factory=dict)
    histograms: dict[str, HistogramMetric] = field(default_factory=dict)
    points: list[MetricPoint] = field(default_factory=list)

    def counter(
        self,
        name: str,
        component: str,
        *,
        unit: str = "count",
        attributes: dict[str, Any] | None = None,
    ) -> CounterMetric:
        """Get or create counter metric."""
        key = metric_key(name, component)

        if key not in self.counters:
            self.counters[key] = CounterMetric(
                name=name,
                component=component,
                unit=unit,
                attributes=attributes or {},
            )

        return self.counters[key]

    def gauge(
        self,
        name: str,
        component: str,
        *,
        unit: str = "value",
        attributes: dict[str, Any] | None = None,
    ) -> GaugeMetric:
        """Get or create gauge metric."""
        key = metric_key(name, component)

        if key not in self.gauges:
            self.gauges[key] = GaugeMetric(
                name=name,
                component=component,
                unit=unit,
                attributes=attributes or {},
            )

        return self.gauges[key]

    def histogram(
        self,
        name: str,
        component: str,
        *,
        unit: str = "value",
        attributes: dict[str, Any] | None = None,
    ) -> HistogramMetric:
        """Get or create histogram metric."""
        key = metric_key(name, component)

        if key not in self.histograms:
            self.histograms[key] = HistogramMetric(
                name=name,
                component=component,
                unit=unit,
                attributes=attributes or {},
            )

        return self.histograms[key]

    def record(self, point: MetricPoint) -> MetricPoint:
        """Record a metric point."""
        if not isinstance(point, MetricPoint):
            raise ValueError("Point must be a MetricPoint.")

        self.points.append(point)
        return point

    def increment_counter(
        self,
        name: str,
        component: str,
        amount: float = 1.0,
        *,
        unit: str = "count",
        attributes: dict[str, Any] | None = None,
    ) -> MetricPoint:
        """Increment and record counter metric."""
        counter = self.counter(
            name=name,
            component=component,
            unit=unit,
            attributes=attributes,
        )

        point = counter.increment(amount)
        return self.record(point)

    def set_gauge(
        self,
        name: str,
        component: str,
        value: float,
        *,
        unit: str = "value",
        attributes: dict[str, Any] | None = None,
    ) -> MetricPoint:
        """Set and record gauge metric."""
        gauge = self.gauge(
            name=name,
            component=component,
            unit=unit,
            attributes=attributes,
        )

        point = gauge.set(value)
        return self.record(point)

    def observe_histogram(
        self,
        name: str,
        component: str,
        value: float,
        *,
        unit: str = "value",
        attributes: dict[str, Any] | None = None,
    ) -> MetricPoint:
        """Observe and record histogram metric."""
        histogram = self.histogram(
            name=name,
            component=component,
            unit=unit,
            attributes=attributes,
        )

        point = histogram.observe(value)
        return self.record(point)

    def latest_points(self, limit: int | None = None) -> list[MetricPoint]:
        """Return latest recorded metric points."""
        if limit is None:
            return list(self.points)

        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("Limit must be a positive integer.")

        return self.points[-limit:]

    def summary(self) -> dict[str, Any]:
        """Return registry summary."""
        return {
            "counters": len(self.counters),
            "gauges": len(self.gauges),
            "histograms": len(self.histograms),
            "points": len(self.points),
            "counter_values": {
                key: metric.value
                for key, metric in self.counters.items()
            },
            "gauge_values": {
                key: metric.value
                for key, metric in self.gauges.items()
            },
            "histogram_values": {
                key: metric.summary()
                for key, metric in self.histograms.items()
            },
        }

    def clear_points(self) -> None:
        """Clear recorded metric points without deleting metric objects."""
        self.points.clear()

    def clear(self) -> None:
        """Clear all metrics and points."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.points.clear()


def validate_metric_name(name: str) -> str:
    """Validate metric name."""
    normalized = validate_non_empty_string(name, "Metric name")

    if " " in normalized:
        raise ValueError("Metric name cannot contain spaces.")

    return normalized


def validate_metric_value(value: float) -> float:
    """Validate metric numeric value."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Metric value must be numeric.")

    return float(value)


def normalize_metric_type(metric_type: MetricType | str) -> MetricType:
    """Normalize metric type."""
    if isinstance(metric_type, MetricType):
        return metric_type

    normalized = validate_non_empty_string(metric_type, "Metric type").lower()

    try:
        return MetricType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MetricType)
        raise ValueError(f"Invalid metric type '{metric_type}'. Valid metric types: {valid}.") from exc


def metric_key(name: str, component: str) -> str:
    """Build stable metric registry key."""
    return f"{validate_metric_name(name)}::{validate_non_empty_string(component, 'Component')}"


def merge_attributes(
    base_attributes: dict[str, Any],
    extra_attributes: dict[str, Any],
) -> dict[str, Any]:
    """Merge metric attributes."""
    validate_attributes(base_attributes)
    validate_attributes(extra_attributes)

    return {
        **base_attributes,
        **extra_attributes,
    }


def build_metric_point(
    *,
    name: str,
    metric_type: MetricType | str,
    value: float,
    component: str,
    unit: str = "count",
    attributes: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> MetricPoint:
    """Build a metric point."""
    metric_kwargs: dict[str, Any] = {
        "name": name,
        "metric_type": metric_type,
        "value": value,
        "component": component,
        "unit": unit,
        "attributes": attributes or {},
    }

    if timestamp is not None:
        metric_kwargs["timestamp"] = timestamp

    return MetricPoint(**metric_kwargs)