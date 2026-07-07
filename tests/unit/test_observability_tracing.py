"""
Unit tests for AQOS observability tracing utilities.
"""

import pytest

from aqos.observability import (
    InMemoryTraceStore,
    TraceContext,
    TraceSpan,
    TraceStatus,
    build_span_id,
    build_trace_id,
    build_trace_span,
    calculate_duration_ms,
    compact_trace_payload,
    normalize_trace_status,
    validate_duration_ms,
    validate_span_id,
    validate_trace_id,
)


def test_trace_status_values():
    assert TraceStatus.STARTED.value == "started"
    assert TraceStatus.SUCCESS.value == "success"
    assert TraceStatus.ERROR.value == "error"
    assert TraceStatus.CANCELLED.value == "cancelled"


def test_build_trace_id_and_span_id():
    trace_id = build_trace_id()
    span_id = build_span_id()

    assert trace_id.startswith("trace-")
    assert span_id.startswith("span-")
    assert len(trace_id) > len("trace-")
    assert len(span_id) > len("span-")


def test_validate_trace_id_and_span_id():
    assert validate_trace_id(" trace-1 ") == "trace-1"
    assert validate_span_id(" span-1 ") == "span-1"

    with pytest.raises(ValueError):
        validate_trace_id("")

    with pytest.raises(ValueError):
        validate_span_id("")


def test_validate_duration_ms():
    assert validate_duration_ms(0) == 0.0
    assert validate_duration_ms(10) == 10.0

    with pytest.raises(ValueError):
        validate_duration_ms(-1)

    with pytest.raises(ValueError):
        validate_duration_ms("bad")

    with pytest.raises(ValueError):
        validate_duration_ms(True)


def test_normalize_trace_status_accepts_enum_and_string():
    assert normalize_trace_status(TraceStatus.STARTED) == TraceStatus.STARTED
    assert normalize_trace_status(" SUCCESS ") == TraceStatus.SUCCESS
    assert normalize_trace_status("error") == TraceStatus.ERROR
    assert normalize_trace_status("CANCELLED") == TraceStatus.CANCELLED


def test_normalize_trace_status_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_trace_status("bad")

    with pytest.raises(ValueError):
        normalize_trace_status("")


def test_calculate_duration_ms():
    assert calculate_duration_ms(
        "2026-01-01T00:00:00+00:00",
        "2026-01-01T00:00:01+00:00",
    ) == 1000.0


def test_calculate_duration_ms_rejects_invalid_time_order():
    with pytest.raises(ValueError):
        calculate_duration_ms(
            "2026-01-01T00:00:01+00:00",
            "2026-01-01T00:00:00+00:00",
        )


def test_compact_trace_payload_removes_none_values():
    payload = compact_trace_payload(
        {
            "trace_id": "trace-1",
            "error": None,
            "status": "success",
        },
    )

    assert payload == {
        "trace_id": "trace-1",
        "status": "success",
    }


def test_trace_span_to_dict():
    span = TraceSpan(
        trace_id="trace-1",
        span_id="span-1",
        name="market-state",
        component="market-agent",
        parent_span_id="span-root",
        status="SUCCESS",
        start_time="2026-01-01T00:00:00+00:00",
        end_time="2026-01-01T00:00:01+00:00",
        duration_ms=1000,
        attributes={
            "symbol": "XAUUSD",
        },
    )

    assert span.to_dict() == {
        "trace_id": "trace-1",
        "span_id": "span-1",
        "name": "market-state",
        "component": "market-agent",
        "parent_span_id": "span-root",
        "status": "success",
        "start_time": "2026-01-01T00:00:00+00:00",
        "end_time": "2026-01-01T00:00:01+00:00",
        "duration_ms": 1000,
        "attributes": {
            "symbol": "XAUUSD",
        },
        "events": [],
    }


def test_trace_span_add_event():
    span = TraceSpan(
        trace_id="trace-1",
        span_id="span-1",
        name="market-state",
        component="market-agent",
        start_time="2026-01-01T00:00:00+00:00",
    )

    event = span.add_event(
        "market.state.loaded",
        severity="info",
        message="Market state loaded.",
        attributes={
            "symbol": "XAUUSD",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert event.to_dict() == {
        "name": "market.state.loaded",
        "component": "market-agent",
        "severity": "info",
        "message": "Market state loaded.",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "attributes": {
            "trace_id": "trace-1",
            "span_id": "span-1",
            "symbol": "XAUUSD",
        },
    }
    assert len(span.events) == 1


def test_trace_span_finish_success():
    span = TraceSpan(
        trace_id="trace-1",
        span_id="span-1",
        name="market-state",
        component="market-agent",
        start_time="2026-01-01T00:00:00+00:00",
    )

    finished = span.finish(
        status="success",
        end_time="2026-01-01T00:00:01+00:00",
    )

    assert finished is span
    assert span.status == TraceStatus.SUCCESS
    assert span.end_time == "2026-01-01T00:00:01+00:00"
    assert span.duration_ms == 1000.0
    assert span.is_finished is True


def test_trace_span_fail_sets_error_status():
    span = TraceSpan(
        trace_id="trace-1",
        span_id="span-1",
        name="risk-check",
        component="risk-agent",
        start_time="2026-01-01T00:00:00+00:00",
    )

    span.fail(
        "Invalid stop loss.",
        end_time="2026-01-01T00:00:01+00:00",
    )

    assert span.status == TraceStatus.ERROR
    assert span.error == "Invalid stop loss."
    assert span.duration_ms == 1000.0


def test_trace_span_rejects_invalid_values():
    with pytest.raises(ValueError):
        TraceSpan(
            trace_id="",
            span_id="span-1",
            name="market-state",
            component="market-agent",
        )

    with pytest.raises(ValueError):
        TraceSpan(
            trace_id="trace-1",
            span_id="",
            name="market-state",
            component="market-agent",
        )

    with pytest.raises(ValueError):
        TraceSpan(
            trace_id="trace-1",
            span_id="span-1",
            name="",
            component="market-agent",
        )

    with pytest.raises(ValueError):
        TraceSpan(
            trace_id="trace-1",
            span_id="span-1",
            name="market-state",
            component="",
        )

    with pytest.raises(ValueError):
        TraceSpan(
            trace_id="trace-1",
            span_id="span-1",
            name="market-state",
            component="market-agent",
            status="bad",
        )

    with pytest.raises(ValueError):
        TraceSpan(
            trace_id="trace-1",
            span_id="span-1",
            name="market-state",
            component="market-agent",
            attributes=[],
        )


def test_build_trace_span_with_explicit_values():
    span = build_trace_span(
        trace_id="trace-1",
        span_id="span-1",
        name="api-health",
        component="api",
        parent_span_id="span-root",
        start_time="2026-01-01T00:00:00+00:00",
        attributes={
            "route": "/health",
        },
    )

    assert span.to_dict() == {
        "trace_id": "trace-1",
        "span_id": "span-1",
        "name": "api-health",
        "component": "api",
        "parent_span_id": "span-root",
        "status": "started",
        "start_time": "2026-01-01T00:00:00+00:00",
        "attributes": {
            "route": "/health",
        },
        "events": [],
    }


def test_trace_context_starts_and_finishes_spans():
    context = TraceContext(
        trace_id="trace-1",
        attributes={
            "symbol": "XAUUSD",
        },
    )

    root = context.start_span(
        name="trade-workflow",
        component="orchestrator",
        span_id="span-root",
    )

    child = context.start_span(
        name="market-state",
        component="market-agent",
        span_id="span-child",
        parent_span_id=root.span_id,
        attributes={
            "timeframe": "H1",
        },
    )

    assert context.get_span("span-root") is root
    assert context.get_span("span-child") is child
    assert context.root_spans() == [
        root,
    ]
    assert context.child_spans("span-root") == [
        child,
    ]

    context.finish_span(
        "span-child",
        end_time=child.start_time,
    )

    assert len(context.open_spans()) == 1
    assert len(context.finished_spans()) == 1


def test_trace_context_to_dict():
    context = TraceContext(
        trace_id="trace-1",
        attributes={
            "symbol": "XAUUSD",
        },
    )

    context.start_span(
        name="trade-workflow",
        component="orchestrator",
        span_id="span-root",
        attributes={
            "timeframe": "H1",
        },
    )

    payload = context.to_dict()

    assert payload["trace_id"] == "trace-1"
    assert payload["attributes"] == {
        "symbol": "XAUUSD",
    }
    assert payload["span_count"] == 1
    assert payload["open_span_count"] == 1
    assert payload["finished_span_count"] == 0
    assert payload["spans"][0]["attributes"] == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_trace_context_rejects_invalid_values():
    with pytest.raises(ValueError):
        TraceContext(trace_id="")

    with pytest.raises(ValueError):
        TraceContext(
            trace_id="trace-1",
            attributes=[],
        )

    with pytest.raises(ValueError):
        TraceContext(
            trace_id="trace-1",
            spans=["bad"],
        )

    with pytest.raises(ValueError):
        TraceContext(
            trace_id="trace-1",
            spans=[
                TraceSpan(
                    trace_id="trace-2",
                    span_id="span-1",
                    name="span",
                    component="api",
                ),
            ],
        )


def test_trace_context_rejects_duplicate_and_missing_spans():
    context = TraceContext(trace_id="trace-1")

    span = TraceSpan(
        trace_id="trace-1",
        span_id="span-1",
        name="span",
        component="api",
    )

    context.add_span(span)

    with pytest.raises(ValueError):
        context.add_span(span)

    with pytest.raises(ValueError):
        context.get_required_span("missing-span")


def test_in_memory_trace_store_create_get_and_summary():
    store = InMemoryTraceStore()

    context = store.create_trace(
        trace_id="trace-1",
        attributes={
            "workflow": "trade",
        },
    )

    span = store.start_span(
        "trace-1",
        name="trade-workflow",
        component="orchestrator",
        span_id="span-1",
    )

    store.finish_span(
        "trace-1",
        "span-1",
        end_time=span.start_time,
    )

    assert store.get_trace("trace-1") is context
    assert store.get_required_trace("trace-1") is context
    assert store.list_traces() == [
        context,
    ]
    assert store.summary() == {
        "traces": 1,
        "spans": 1,
        "open_spans": 0,
        "finished_spans": 1,
        "trace_ids": [
            "trace-1",
        ],
    }


def test_in_memory_trace_store_rejects_invalid_values():
    store = InMemoryTraceStore()

    store.create_trace(trace_id="trace-1")

    with pytest.raises(ValueError):
        store.create_trace(trace_id="trace-1")

    with pytest.raises(ValueError):
        store.get_required_trace("missing-trace")

    with pytest.raises(ValueError):
        store.start_span(
            "missing-trace",
            name="span",
            component="api",
        )


def test_in_memory_trace_store_clear():
    store = InMemoryTraceStore()

    store.create_trace(trace_id="trace-1")
    assert store.summary()["traces"] == 1

    store.clear()
    assert store.summary()["traces"] == 0


def test_observability_tracing_exports_exist():
    import aqos.observability as observability

    expected_exports = [
        "InMemoryTraceStore",
        "TraceContext",
        "TraceSpan",
        "TraceStatus",
        "build_span_id",
        "build_trace_id",
        "build_trace_span",
        "calculate_duration_ms",
        "compact_trace_payload",
        "normalize_trace_status",
        "validate_duration_ms",
        "validate_span_id",
        "validate_trace_id",
    ]

    for export_name in expected_exports:
        assert hasattr(observability, export_name), export_name