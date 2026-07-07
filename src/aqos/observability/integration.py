"""
AQOS observability integration helpers.

This module connects metrics, logs, traces, alerts, and health snapshots into
one small dependency-free observability bundle.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aqos.observability.alerts import (
    AlertManager,
    AlertRecord,
)
from aqos.observability.health import (
    ComponentHealth,
    ObservabilitySnapshot,
    collect_observability_snapshot,
    validate_component_health_list,
)
from aqos.observability.logging import (
    InMemoryLogSink,
    StructuredLogger,
    build_log_record,
    build_logger,
    log_exception,
)
from aqos.observability.metrics import (
    MetricPoint,
    MetricsRegistry,
)
from aqos.observability.tracing import (
    InMemoryTraceStore,
    TraceContext,
    TraceSpan,
    TraceStatus,
    build_trace_span,
    validate_duration_ms,
    validate_span_id,
    validate_trace_id,
)
from aqos.observability.base import (
    validate_attributes,
    validate_non_empty_string,
)


@dataclass(frozen=True)
class ObservedOperationResult:
    """Result returned from an observed operation."""

    operation: str
    component: str
    success: bool
    trace_id: str
    span_id: str
    result: Any = None
    error: str | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_operation_name(self.operation)
        validate_non_empty_string(self.component, "Component")

        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_trace_id(self.trace_id)
        validate_span_id(self.span_id)
        validate_attributes(self.attributes)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

        if self.duration_ms is not None:
            validate_duration_ms(self.duration_ms)

    def to_dict(self) -> dict[str, Any]:
        """Convert observed operation result into a serializable dictionary."""
        payload = {
            "operation": self.operation.strip(),
            "component": self.component.strip(),
            "success": self.success,
            "trace_id": self.trace_id.strip(),
            "span_id": self.span_id.strip(),
            "result": self.result,
            "error": self.error.strip() if self.error else None,
            "duration_ms": self.duration_ms,
            "attributes": dict(self.attributes),
        }

        return {
            key: value
            for key, value in payload.items()
            if value is not None
        }


@dataclass
class ObservabilityBundle:
    """Shared observability stores for AQOS runtime flows."""

    metrics_registry: MetricsRegistry = field(default_factory=MetricsRegistry)
    log_sink: InMemoryLogSink = field(default_factory=InMemoryLogSink)
    trace_store: InMemoryTraceStore = field(default_factory=InMemoryTraceStore)
    alert_manager: AlertManager = field(default_factory=AlertManager)
    components: list[ComponentHealth] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_observability_bundle(self)

    def logger(
        self,
        component: str,
        *,
        default_attributes: dict[str, Any] | None = None,
    ) -> StructuredLogger:
        """Create a structured logger backed by this bundle sink."""
        merged_attributes = {
            **self.attributes,
            **(default_attributes or {}),
        }

        return build_logger(
            component,
            sink=self.log_sink,
            default_attributes=merged_attributes,
        )

    def get_or_create_trace(
        self,
        *,
        trace_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceContext:
        """Get an existing trace or create a new one."""
        merged_attributes = {
            **self.attributes,
            **(attributes or {}),
        }

        if trace_id is not None:
            existing = self.trace_store.get_trace(trace_id)

            if existing is not None:
                return existing

        return self.trace_store.create_trace(
            trace_id=trace_id,
            attributes=merged_attributes,
        )

    def start_span(
        self,
        *,
        operation: str,
        component: str,
        trace_id: str | None = None,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
        start_time: str | None = None,
    ) -> TraceSpan:
        """Start a span inside this bundle."""
        validate_operation_name(operation)
        validate_non_empty_string(component, "Component")
        validate_attributes(attributes or {})

        context = self.get_or_create_trace(
            trace_id=trace_id,
            attributes=attributes or {},
        )

        span = build_trace_span(
            trace_id=context.trace_id,
            span_id=span_id,
            name=operation,
            component=component,
            parent_span_id=parent_span_id,
            start_time=start_time,
            attributes={
                **self.attributes,
                **(attributes or {}),
            },
        )

        context.add_span(span)
        return span

    def record_metric(
        self,
        point: MetricPoint,
        *,
        evaluate_alerts: bool = True,
        log_alerts: bool = True,
    ) -> list[AlertRecord]:
        """Record a metric point and optionally evaluate alerts."""
        if not isinstance(point, MetricPoint):
            raise ValueError("Point must be a MetricPoint.")

        if not isinstance(evaluate_alerts, bool):
            raise ValueError("Evaluate alerts must be a boolean.")

        if not isinstance(log_alerts, bool):
            raise ValueError("Log alerts must be a boolean.")

        self.metrics_registry.record(point)

        alerts: list[AlertRecord] = []

        if evaluate_alerts:
            alerts = self.alert_manager.evaluate_point(point)

        if log_alerts:
            for alert in alerts:
                self.log_sink.write(
                    build_log_record(
                        message=alert.message,
                        component=alert.component,
                        level=alert.severity,
                        event_name=f"alert.{alert.rule_name}",
                        attributes=alert.to_dict(),
                    ),
                )

        return alerts

    def add_component_health(self, component: ComponentHealth) -> ComponentHealth:
        """Add component health to the bundle."""
        if not isinstance(component, ComponentHealth):
            raise ValueError("Component must be a ComponentHealth.")

        self.components.append(component)
        return component

    def snapshot(
        self,
        *,
        name: str = "aqos-observability",
        details: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> ObservabilitySnapshot:
        """Collect an observability snapshot from this bundle."""
        return collect_observability_snapshot(
            name=name,
            components=self.components,
            metrics_registry=self.metrics_registry,
            log_sink=self.log_sink,
            trace_store=self.trace_store,
            alert_manager=self.alert_manager,
            details=details or {},
            timestamp=timestamp,
        )

    def summary(self) -> dict[str, Any]:
        """Return observability snapshot summary."""
        return self.snapshot().to_dict()

    def clear(self) -> None:
        """Clear all stores and component health."""
        self.metrics_registry.clear()
        self.log_sink.clear()
        self.trace_store.clear()
        self.alert_manager.clear()
        self.components.clear()


def validate_operation_name(operation: str) -> str:
    """Validate operation name."""
    normalized = validate_non_empty_string(operation, "Operation")

    if " " in normalized:
        raise ValueError("Operation cannot contain spaces.")

    return normalized


def validate_observability_bundle(bundle: ObservabilityBundle) -> ObservabilityBundle:
    """Validate an observability bundle."""
    if not isinstance(bundle.metrics_registry, MetricsRegistry):
        raise ValueError("Metrics registry must be a MetricsRegistry.")

    if not isinstance(bundle.log_sink, InMemoryLogSink):
        raise ValueError("Log sink must be an InMemoryLogSink.")

    if not isinstance(bundle.trace_store, InMemoryTraceStore):
        raise ValueError("Trace store must be an InMemoryTraceStore.")

    if not isinstance(bundle.alert_manager, AlertManager):
        raise ValueError("Alert manager must be an AlertManager.")

    validate_component_health_list(bundle.components)
    validate_attributes(bundle.attributes)

    return bundle


def build_operation_attributes(
    *,
    operation: str,
    component: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build standard operation attributes."""
    extra_attributes = attributes or {}

    if attributes is not None:
        validate_attributes(attributes)

    payload = {
        "operation": validate_operation_name(operation),
        "component": validate_non_empty_string(component, "Component"),
        **extra_attributes,
    }

    if trace_id is not None:
        payload["trace_id"] = validate_trace_id(trace_id)

    if span_id is not None:
        payload["span_id"] = validate_span_id(span_id)

    return payload


def build_observability_bundle(
    *,
    metrics_registry: MetricsRegistry | None = None,
    log_sink: InMemoryLogSink | None = None,
    trace_store: InMemoryTraceStore | None = None,
    alert_manager: AlertManager | None = None,
    components: list[ComponentHealth] | None = None,
    attributes: dict[str, Any] | None = None,
) -> ObservabilityBundle:
    """Build an observability bundle."""
    return ObservabilityBundle(
        metrics_registry=metrics_registry or MetricsRegistry(),
        log_sink=log_sink or InMemoryLogSink(),
        trace_store=trace_store or InMemoryTraceStore(),
        alert_manager=alert_manager or AlertManager(),
        components=components or [],
        attributes=attributes or {},
    )


def start_observed_operation(
    bundle: ObservabilityBundle,
    *,
    operation: str,
    component: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    start_time: str | None = None,
) -> TraceSpan:
    """Start an observed operation."""
    validate_observability_bundle(bundle)

    span = bundle.start_span(
        operation=operation,
        component=component,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        attributes=attributes or {},
        start_time=start_time,
    )

    operation_attributes = build_operation_attributes(
        operation=operation,
        component=component,
        trace_id=span.trace_id,
        span_id=span.span_id,
        attributes=attributes or {},
    )

    bundle.log_sink.write(
        build_log_record(
            message=f"Started operation {operation}.",
            component=component,
            level="info",
            event_name=f"operation.{operation}.started",
            attributes=operation_attributes,
            trace_id=span.trace_id,
            span_id=span.span_id,
        ),
    )

    bundle.metrics_registry.increment_counter(
        name=f"operation.{operation}.started",
        component=component,
        attributes=operation_attributes,
    )

    return span


def finish_observed_operation(
    bundle: ObservabilityBundle,
    span: TraceSpan,
    *,
    result: Any = None,
    success: bool = True,
    error: str | None = None,
    attributes: dict[str, Any] | None = None,
    end_time: str | None = None,
) -> ObservedOperationResult:
    """Finish an observed operation."""
    validate_observability_bundle(bundle)

    if not isinstance(span, TraceSpan):
        raise ValueError("Span must be a TraceSpan.")

    if not isinstance(success, bool):
        raise ValueError("Success must be a boolean.")

    operation_attributes = build_operation_attributes(
        operation=span.name,
        component=span.component,
        trace_id=span.trace_id,
        span_id=span.span_id,
        attributes=attributes or {},
    )

    if success and error is None:
        span.finish(
            status=TraceStatus.SUCCESS,
            end_time=end_time,
        )

        bundle.log_sink.write(
            build_log_record(
                message=f"Finished operation {span.name}.",
                component=span.component,
                level="info",
                event_name=f"operation.{span.name}.finished",
                attributes=operation_attributes,
                trace_id=span.trace_id,
                span_id=span.span_id,
            ),
        )

        metric_suffix = "success"
        error_message = None
    else:
        error_message = error or "Operation failed."

        span.fail(
            error_message,
            end_time=end_time,
        )

        bundle.log_sink.write(
            build_log_record(
                message=f"Failed operation {span.name}.",
                component=span.component,
                level="error",
                event_name=f"operation.{span.name}.failed",
                attributes=operation_attributes,
                error=error_message,
                trace_id=span.trace_id,
                span_id=span.span_id,
            ),
        )

        metric_suffix = "error"

    bundle.metrics_registry.increment_counter(
        name=f"operation.{span.name}.{metric_suffix}",
        component=span.component,
        attributes=operation_attributes,
    )

    if span.duration_ms is not None:
        bundle.metrics_registry.observe_histogram(
            name=f"operation.{span.name}.duration_ms",
            component=span.component,
            value=span.duration_ms,
            unit="ms",
            attributes=operation_attributes,
        )

    return ObservedOperationResult(
        operation=span.name,
        component=span.component,
        success=success and error is None,
        trace_id=span.trace_id,
        span_id=span.span_id,
        result=result,
        error=error_message,
        duration_ms=span.duration_ms,
        attributes=operation_attributes,
    )


def record_observed_exception(
    bundle: ObservabilityBundle,
    span: TraceSpan,
    exception: Exception,
    *,
    message: str = "Observed operation failed.",
    attributes: dict[str, Any] | None = None,
    end_time: str | None = None,
) -> ObservedOperationResult:
    """Record an exception for an observed operation."""
    validate_observability_bundle(bundle)

    if not isinstance(span, TraceSpan):
        raise ValueError("Span must be a TraceSpan.")

    if not isinstance(exception, Exception):
        raise ValueError("Exception must be an Exception.")

    span.fail(
        str(exception),
        end_time=end_time,
    )

    operation_attributes = build_operation_attributes(
        operation=span.name,
        component=span.component,
        trace_id=span.trace_id,
        span_id=span.span_id,
        attributes=attributes or {},
    )

    logger = bundle.logger(
        span.component,
        default_attributes=operation_attributes,
    )

    log_exception(
        logger,
        exception,
        message=message,
        attributes=attributes or {},
        trace_id=span.trace_id,
        span_id=span.span_id,
    )

    bundle.metrics_registry.increment_counter(
        name=f"operation.{span.name}.error",
        component=span.component,
        attributes=operation_attributes,
    )

    if span.duration_ms is not None:
        bundle.metrics_registry.observe_histogram(
            name=f"operation.{span.name}.duration_ms",
            component=span.component,
            value=span.duration_ms,
            unit="ms",
            attributes=operation_attributes,
        )

    return ObservedOperationResult(
        operation=span.name,
        component=span.component,
        success=False,
        trace_id=span.trace_id,
        span_id=span.span_id,
        error=str(exception),
        duration_ms=span.duration_ms,
        attributes=operation_attributes,
    )


def record_observed_metric(
    bundle: ObservabilityBundle,
    point: MetricPoint,
    *,
    evaluate_alerts: bool = True,
    log_alerts: bool = True,
) -> list[AlertRecord]:
    """Record an observed metric point."""
    validate_observability_bundle(bundle)

    return bundle.record_metric(
        point,
        evaluate_alerts=evaluate_alerts,
        log_alerts=log_alerts,
    )


def run_observed_operation(
    operation_callable: Callable[[], Any],
    bundle: ObservabilityBundle,
    *,
    operation: str,
    component: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    attributes: dict[str, Any] | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> ObservedOperationResult:
    """Run a callable inside an observed operation."""
    if not callable(operation_callable):
        raise ValueError("Operation callable must be callable.")

    span = start_observed_operation(
        bundle,
        operation=operation,
        component=component,
        trace_id=trace_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        attributes=attributes or {},
        start_time=start_time,
    )

    try:
        result = operation_callable()
    except Exception as exc:
        return record_observed_exception(
            bundle,
            span,
            exc,
            attributes=attributes or {},
            end_time=end_time,
        )

    return finish_observed_operation(
        bundle,
        span,
        result=result,
        success=True,
        attributes=attributes or {},
        end_time=end_time,
    )