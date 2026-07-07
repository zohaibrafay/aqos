"""
AQOS tracing utilities.

This module provides dependency-free trace/span primitives for following
workflows across agents, services, API wrappers, and CLI commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from aqos.observability.base import (
    ObservabilityEvent,
    build_observability_event,
    validate_attributes,
    validate_non_empty_string,
)


class TraceStatus(str, Enum):
    """Supported trace/span statuses."""

    STARTED = "started"
    SUCCESS = "success"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class TraceSpan:
    """Single trace span."""

    trace_id: str
    span_id: str
    name: str
    component: str
    parent_span_id: str | None = None
    status: TraceStatus | str = TraceStatus.STARTED
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: str | None = None
    duration_ms: float | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[ObservabilityEvent] = field(default_factory=list)
    error: str | None = None

    def __post_init__(self) -> None:
        validate_trace_id(self.trace_id)
        validate_span_id(self.span_id)
        validate_non_empty_string(self.name, "Span name")
        validate_non_empty_string(self.component, "Component")
        normalize_trace_status(self.status)
        validate_non_empty_string(self.start_time, "Start time")
        validate_attributes(self.attributes)

        if self.parent_span_id is not None:
            validate_span_id(self.parent_span_id)

        if self.end_time is not None:
            validate_non_empty_string(self.end_time, "End time")

        if self.duration_ms is not None:
            validate_duration_ms(self.duration_ms)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

        for event in self.events:
            if not isinstance(event, ObservabilityEvent):
                raise ValueError("Events must contain ObservabilityEvent objects.")

    def add_event(
        self,
        name: str,
        *,
        severity: str = "info",
        message: str = "",
        attributes: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> ObservabilityEvent:
        """Add an event to the span."""
        event_attributes = {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            **(attributes or {}),
        }

        event = build_observability_event(
            name=name,
            component=self.component,
            severity=severity,
            message=message,
            attributes=event_attributes,
            timestamp=timestamp,
        )

        self.events.append(event)
        return event

    def finish(
        self,
        *,
        status: TraceStatus | str = TraceStatus.SUCCESS,
        end_time: str | None = None,
        error: str | None = None,
    ) -> "TraceSpan":
        """Finish the span."""
        normalized_status = normalize_trace_status(status)

        self.status = normalized_status
        self.end_time = end_time or datetime.now(UTC).isoformat()
        self.duration_ms = calculate_duration_ms(
            self.start_time,
            self.end_time,
        )

        if error is not None:
            self.error = validate_non_empty_string(error, "Error")
            self.status = TraceStatus.ERROR

        return self

    def fail(
        self,
        error: str,
        *,
        end_time: str | None = None,
    ) -> "TraceSpan":
        """Finish span with error status."""
        return self.finish(
            status=TraceStatus.ERROR,
            end_time=end_time,
            error=error,
        )

    @property
    def is_finished(self) -> bool:
        """Return whether span is finished."""
        return self.end_time is not None

    def to_dict(self) -> dict[str, Any]:
        """Convert span into serializable dictionary."""
        payload = {
            "trace_id": self.trace_id.strip(),
            "span_id": self.span_id.strip(),
            "name": self.name.strip(),
            "component": self.component.strip(),
            "parent_span_id": self.parent_span_id.strip() if self.parent_span_id else None,
            "status": normalize_trace_status(self.status).value,
            "start_time": self.start_time.strip(),
            "end_time": self.end_time.strip() if self.end_time else None,
            "duration_ms": self.duration_ms,
            "attributes": dict(self.attributes),
            "events": [
                event.to_dict()
                for event in self.events
            ],
            "error": self.error.strip() if self.error else None,
        }

        return compact_trace_payload(payload)


@dataclass
class TraceContext:
    """Trace context containing multiple spans."""

    trace_id: str = field(default_factory=lambda: build_trace_id())
    attributes: dict[str, Any] = field(default_factory=dict)
    spans: list[TraceSpan] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_trace_id(self.trace_id)
        validate_attributes(self.attributes)

        for span in self.spans:
            if not isinstance(span, TraceSpan):
                raise ValueError("Spans must contain TraceSpan objects.")

            if span.trace_id != self.trace_id:
                raise ValueError("Span trace ID must match trace context ID.")

    def start_span(
        self,
        name: str,
        component: str,
        *,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """Start and register a new span."""
        span = build_trace_span(
            trace_id=self.trace_id,
            span_id=span_id,
            name=name,
            component=component,
            parent_span_id=parent_span_id,
            attributes={
                **self.attributes,
                **(attributes or {}),
            },
        )

        self.add_span(span)
        return span

    def add_span(self, span: TraceSpan) -> TraceSpan:
        """Add an existing span to the trace context."""
        if not isinstance(span, TraceSpan):
            raise ValueError("Span must be a TraceSpan.")

        if span.trace_id != self.trace_id:
            raise ValueError("Span trace ID must match trace context ID.")

        if self.get_span(span.span_id) is not None:
            raise ValueError("Span already exists in trace context.")

        self.spans.append(span)
        return span

    def get_span(self, span_id: str) -> TraceSpan | None:
        """Get a span by ID."""
        normalized = validate_span_id(span_id)

        for span in self.spans:
            if span.span_id == normalized:
                return span

        return None

    def finish_span(
        self,
        span_id: str,
        *,
        status: TraceStatus | str = TraceStatus.SUCCESS,
        error: str | None = None,
        end_time: str | None = None,
    ) -> TraceSpan:
        """Finish a span by ID."""
        span = self.get_required_span(span_id)

        return span.finish(
            status=status,
            error=error,
            end_time=end_time,
        )

    def get_required_span(self, span_id: str) -> TraceSpan:
        """Get a span by ID or raise."""
        span = self.get_span(span_id)

        if span is None:
            raise ValueError("Span not found.")

        return span

    def root_spans(self) -> list[TraceSpan]:
        """Return root spans."""
        return [
            span
            for span in self.spans
            if span.parent_span_id is None
        ]

    def child_spans(self, parent_span_id: str) -> list[TraceSpan]:
        """Return child spans for parent span ID."""
        normalized = validate_span_id(parent_span_id)

        return [
            span
            for span in self.spans
            if span.parent_span_id == normalized
        ]

    def open_spans(self) -> list[TraceSpan]:
        """Return unfinished spans."""
        return [
            span
            for span in self.spans
            if not span.is_finished
        ]

    def finished_spans(self) -> list[TraceSpan]:
        """Return finished spans."""
        return [
            span
            for span in self.spans
            if span.is_finished
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert trace context into serializable dictionary."""
        return {
            "trace_id": self.trace_id.strip(),
            "attributes": dict(self.attributes),
            "spans": [
                span.to_dict()
                for span in self.spans
            ],
            "span_count": len(self.spans),
            "open_span_count": len(self.open_spans()),
            "finished_span_count": len(self.finished_spans()),
        }


@dataclass
class InMemoryTraceStore:
    """In-memory trace store."""

    traces: dict[str, TraceContext] = field(default_factory=dict)

    def create_trace(
        self,
        *,
        trace_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceContext:
        """Create and store a trace context."""
        context = TraceContext(
            trace_id=trace_id or build_trace_id(),
            attributes=attributes or {},
        )

        if context.trace_id in self.traces:
            raise ValueError("Trace already exists.")

        self.traces[context.trace_id] = context
        return context

    def get_trace(self, trace_id: str) -> TraceContext | None:
        """Get trace by ID."""
        normalized = validate_trace_id(trace_id)

        return self.traces.get(normalized)

    def get_required_trace(self, trace_id: str) -> TraceContext:
        """Get trace by ID or raise."""
        trace = self.get_trace(trace_id)

        if trace is None:
            raise ValueError("Trace not found.")

        return trace

    def start_span(
        self,
        trace_id: str,
        name: str,
        component: str,
        *,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceSpan:
        """Start span on an existing trace."""
        trace = self.get_required_trace(trace_id)

        return trace.start_span(
            name=name,
            component=component,
            span_id=span_id,
            parent_span_id=parent_span_id,
            attributes=attributes,
        )

    def finish_span(
        self,
        trace_id: str,
        span_id: str,
        *,
        status: TraceStatus | str = TraceStatus.SUCCESS,
        error: str | None = None,
        end_time: str | None = None,
    ) -> TraceSpan:
        """Finish span on an existing trace."""
        trace = self.get_required_trace(trace_id)

        return trace.finish_span(
            span_id,
            status=status,
            error=error,
            end_time=end_time,
        )

    def list_traces(self) -> list[TraceContext]:
        """List stored traces."""
        return list(self.traces.values())

    def summary(self) -> dict[str, Any]:
        """Return trace store summary."""
        traces = self.list_traces()

        return {
            "traces": len(traces),
            "spans": sum(len(trace.spans) for trace in traces),
            "open_spans": sum(len(trace.open_spans()) for trace in traces),
            "finished_spans": sum(len(trace.finished_spans()) for trace in traces),
            "trace_ids": list(self.traces.keys()),
        }

    def clear(self) -> None:
        """Clear trace store."""
        self.traces.clear()


def build_trace_id() -> str:
    """Build a trace ID."""
    return f"trace-{uuid4().hex}"


def build_span_id() -> str:
    """Build a span ID."""
    return f"span-{uuid4().hex}"


def validate_trace_id(trace_id: str) -> str:
    """Validate trace ID."""
    return validate_non_empty_string(trace_id, "Trace ID")


def validate_span_id(span_id: str) -> str:
    """Validate span ID."""
    return validate_non_empty_string(span_id, "Span ID")


def validate_duration_ms(duration_ms: float) -> float:
    """Validate duration in milliseconds."""
    if isinstance(duration_ms, bool) or not isinstance(duration_ms, int | float):
        raise ValueError("Duration must be numeric.")

    if duration_ms < 0:
        raise ValueError("Duration cannot be negative.")

    return float(duration_ms)


def normalize_trace_status(status: TraceStatus | str) -> TraceStatus:
    """Normalize trace status."""
    if isinstance(status, TraceStatus):
        return status

    normalized = validate_non_empty_string(status, "Trace status").lower()

    try:
        return TraceStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TraceStatus)
        raise ValueError(f"Invalid trace status '{status}'. Valid statuses: {valid}.") from exc


def calculate_duration_ms(start_time: str, end_time: str) -> float:
    """Calculate duration in milliseconds between two ISO timestamps."""
    validate_non_empty_string(start_time, "Start time")
    validate_non_empty_string(end_time, "End time")

    start = datetime.fromisoformat(start_time)
    end = datetime.fromisoformat(end_time)

    duration = (end - start).total_seconds() * 1000

    if duration < 0:
        raise ValueError("End time cannot be before start time.")

    return float(duration)


def compact_trace_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove empty optional values from trace payload."""
    validate_attributes(payload)

    return {
        key: value
        for key, value in payload.items()
        if value is not None
    }


def build_trace_span(
    *,
    trace_id: str,
    name: str,
    component: str,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    status: TraceStatus | str = TraceStatus.STARTED,
    start_time: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> TraceSpan:
    """Build a trace span."""
    span_kwargs: dict[str, Any] = {
        "trace_id": trace_id,
        "span_id": span_id or build_span_id(),
        "name": name,
        "component": component,
        "parent_span_id": parent_span_id,
        "status": status,
        "attributes": attributes or {},
    }

    if start_time is not None:
        span_kwargs["start_time"] = start_time

    return TraceSpan(**span_kwargs)