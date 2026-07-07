"""
AQOS observability health snapshot aggregator.

This module aggregates metrics, logs, traces, alerts, and component health into
a single dependency-free health snapshot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from aqos.observability.alerts import AlertManager
from aqos.observability.base import (
    ObservabilityEvent,
    ObservabilityStatus,
    build_observability_event,
    normalize_status,
    validate_attributes,
    validate_non_empty_string,
)
from aqos.observability.logging import InMemoryLogSink, normalize_log_level
from aqos.observability.metrics import MetricsRegistry
from aqos.observability.tracing import InMemoryTraceStore


@dataclass(frozen=True)
class ComponentHealth:
    """Health state for a single AQOS component."""

    component: str
    status: ObservabilityStatus | str = ObservabilityStatus.OK
    message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.component, "Component")
        normalize_status(self.status)
        validate_health_message(self.message)
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_attributes(self.details)

    def to_dict(self) -> dict[str, Any]:
        """Convert component health into a serializable dictionary."""
        return {
            "component": self.component.strip(),
            "status": normalize_status(self.status).value,
            "message": self.message.strip(),
            "timestamp": self.timestamp.strip(),
            "details": dict(self.details),
        }

    def to_event(self) -> ObservabilityEvent:
        """Convert component health into an observability event."""
        payload = self.to_dict()

        severity = "info"
        if payload["status"] == ObservabilityStatus.WARNING.value:
            severity = "warning"
        if payload["status"] == ObservabilityStatus.ERROR.value:
            severity = "error"

        return build_observability_event(
            name=f"health.{payload['component']}",
            component=payload["component"],
            severity=severity,
            message=payload["message"] or f"{payload['component']} health is {payload['status']}.",
            attributes=payload,
            timestamp=payload["timestamp"],
        )


@dataclass(frozen=True)
class ObservabilitySnapshot:
    """Aggregated observability health snapshot."""

    name: str = "aqos-observability"
    status: ObservabilityStatus | str = ObservabilityStatus.OK
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    components: list[ComponentHealth] = field(default_factory=list)
    metrics_summary: dict[str, Any] = field(default_factory=dict)
    logs_summary: dict[str, Any] = field(default_factory=dict)
    traces_summary: dict[str, Any] = field(default_factory=dict)
    alerts_summary: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Snapshot name")
        normalize_status(self.status)
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_component_health_list(self.components)
        validate_attributes(self.metrics_summary)
        validate_attributes(self.logs_summary)
        validate_attributes(self.traces_summary)
        validate_attributes(self.alerts_summary)
        validate_attributes(self.details)

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot into a serializable dictionary."""
        return {
            "name": self.name.strip(),
            "status": normalize_status(self.status).value,
            "timestamp": self.timestamp.strip(),
            "components": [
                component.to_dict()
                for component in self.components
            ],
            "metrics_summary": dict(self.metrics_summary),
            "logs_summary": dict(self.logs_summary),
            "traces_summary": dict(self.traces_summary),
            "alerts_summary": dict(self.alerts_summary),
            "details": dict(self.details),
        }

    def to_event(self) -> ObservabilityEvent:
        """Convert snapshot into an observability event."""
        payload = self.to_dict()

        severity = "info"
        if payload["status"] == ObservabilityStatus.WARNING.value:
            severity = "warning"
        if payload["status"] == ObservabilityStatus.ERROR.value:
            severity = "error"

        return build_observability_event(
            name=f"health.snapshot.{payload['name']}",
            component=payload["name"],
            severity=severity,
            message=f"Observability snapshot status is {payload['status']}.",
            attributes=payload,
            timestamp=payload["timestamp"],
        )


def validate_health_message(message: str) -> str:
    """Validate health message."""
    if not isinstance(message, str):
        raise ValueError("Message must be a string.")

    return message.strip()


def validate_component_health_list(components: list[ComponentHealth]) -> list[ComponentHealth]:
    """Validate component health list."""
    if not isinstance(components, list):
        raise ValueError("Components must be a list.")

    for component in components:
        if not isinstance(component, ComponentHealth):
            raise ValueError("Components must contain ComponentHealth objects.")

    return components


def build_component_health(
    *,
    component: str,
    status: ObservabilityStatus | str = ObservabilityStatus.OK,
    message: str = "",
    details: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> ComponentHealth:
    """Build component health."""
    component_kwargs: dict[str, Any] = {
        "component": component,
        "status": status,
        "message": message,
        "details": details or {},
    }

    if timestamp is not None:
        component_kwargs["timestamp"] = timestamp

    return ComponentHealth(**component_kwargs)


def resolve_health_snapshot_status(
    components: list[ComponentHealth] | None = None,
    *,
    active_alerts: int = 0,
    error_logs: int = 0,
    open_spans: int = 0,
) -> ObservabilityStatus:
    """Resolve aggregate health snapshot status."""
    component_list = components or []
    validate_component_health_list(component_list)
    validate_non_negative_integer(active_alerts, "Active alerts")
    validate_non_negative_integer(error_logs, "Error logs")
    validate_non_negative_integer(open_spans, "Open spans")

    statuses = [
        normalize_status(component.status)
        for component in component_list
    ]

    if ObservabilityStatus.ERROR in statuses:
        return ObservabilityStatus.ERROR

    if error_logs > 0:
        return ObservabilityStatus.ERROR

    if ObservabilityStatus.WARNING in statuses:
        return ObservabilityStatus.WARNING

    if active_alerts > 0:
        return ObservabilityStatus.WARNING

    if open_spans > 0:
        return ObservabilityStatus.WARNING

    return ObservabilityStatus.OK


def build_logs_summary(log_sink: InMemoryLogSink | None = None) -> dict[str, Any]:
    """Build summary for structured logs."""
    if log_sink is None:
        return {
            "records": 0,
            "levels": {},
            "components": {},
        }

    if not isinstance(log_sink, InMemoryLogSink):
        raise ValueError("Log sink must be an InMemoryLogSink.")

    levels: dict[str, int] = {}
    components: dict[str, int] = {}

    for record in log_sink.records:
        payload = record.to_dict()
        level = normalize_log_level(payload["level"]).value
        component = payload["component"]

        levels[level] = levels.get(level, 0) + 1
        components[component] = components.get(component, 0) + 1

    return {
        "records": log_sink.count(),
        "levels": levels,
        "components": components,
    }


def build_metrics_summary(registry: MetricsRegistry | None = None) -> dict[str, Any]:
    """Build summary for metrics registry."""
    if registry is None:
        return {
            "counters": 0,
            "gauges": 0,
            "histograms": 0,
            "points": 0,
            "counter_values": {},
            "gauge_values": {},
            "histogram_values": {},
        }

    if not isinstance(registry, MetricsRegistry):
        raise ValueError("Metrics registry must be a MetricsRegistry.")

    return registry.summary()


def build_traces_summary(trace_store: InMemoryTraceStore | None = None) -> dict[str, Any]:
    """Build summary for trace store."""
    if trace_store is None:
        return {
            "traces": 0,
            "spans": 0,
            "open_spans": 0,
            "finished_spans": 0,
            "trace_ids": [],
        }

    if not isinstance(trace_store, InMemoryTraceStore):
        raise ValueError("Trace store must be an InMemoryTraceStore.")

    return trace_store.summary()


def build_alerts_summary(alert_manager: AlertManager | None = None) -> dict[str, Any]:
    """Build summary for alert manager."""
    if alert_manager is None:
        return {
            "rules": 0,
            "alerts": 0,
            "active_alerts": 0,
            "resolved_alerts": 0,
            "suppressed_alerts": 0,
            "rule_names": [],
        }

    if not isinstance(alert_manager, AlertManager):
        raise ValueError("Alert manager must be an AlertManager.")

    return alert_manager.summary()


def build_observability_snapshot(
    *,
    name: str = "aqos-observability",
    components: list[ComponentHealth] | None = None,
    metrics_summary: dict[str, Any] | None = None,
    logs_summary: dict[str, Any] | None = None,
    traces_summary: dict[str, Any] | None = None,
    alerts_summary: dict[str, Any] | None = None,
    details: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> ObservabilitySnapshot:
    """Build an observability health snapshot."""
    component_list = components or []
    metric_data = metrics_summary or {}
    log_data = logs_summary or {}
    trace_data = traces_summary or {}
    alert_data = alerts_summary or {}

    status = resolve_health_snapshot_status(
        component_list,
        active_alerts=int(alert_data.get("active_alerts", 0)),
        error_logs=int(log_data.get("levels", {}).get("error", 0))
        + int(log_data.get("levels", {}).get("critical", 0)),
        open_spans=int(trace_data.get("open_spans", 0)),
    )

    snapshot_kwargs: dict[str, Any] = {
        "name": name,
        "status": status,
        "components": component_list,
        "metrics_summary": metric_data,
        "logs_summary": log_data,
        "traces_summary": trace_data,
        "alerts_summary": alert_data,
        "details": details or {},
    }

    if timestamp is not None:
        snapshot_kwargs["timestamp"] = timestamp

    return ObservabilitySnapshot(**snapshot_kwargs)


def collect_observability_snapshot(
    *,
    name: str = "aqos-observability",
    components: list[ComponentHealth] | None = None,
    metrics_registry: MetricsRegistry | None = None,
    log_sink: InMemoryLogSink | None = None,
    trace_store: InMemoryTraceStore | None = None,
    alert_manager: AlertManager | None = None,
    details: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> ObservabilitySnapshot:
    """Collect a health snapshot from observability stores."""
    return build_observability_snapshot(
        name=name,
        components=components or [],
        metrics_summary=build_metrics_summary(metrics_registry),
        logs_summary=build_logs_summary(log_sink),
        traces_summary=build_traces_summary(trace_store),
        alerts_summary=build_alerts_summary(alert_manager),
        details=details or {},
        timestamp=timestamp,
    )


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value