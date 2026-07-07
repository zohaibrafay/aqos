"""
Unit tests for AQOS observability structured logging.
"""

import pytest

from aqos.observability import (
    InMemoryLogSink,
    LogLevel,
    ObservabilitySeverity,
    StructuredLogRecord,
    StructuredLogger,
    build_log_record,
    build_logger,
    compact_log_record,
    log_exception,
    merge_log_attributes,
    normalize_log_level,
)


def test_log_level_values():
    assert LogLevel.DEBUG.value == "debug"
    assert LogLevel.INFO.value == "info"
    assert LogLevel.WARNING.value == "warning"
    assert LogLevel.ERROR.value == "error"
    assert LogLevel.CRITICAL.value == "critical"


def test_normalize_log_level_accepts_enum_and_string():
    assert normalize_log_level(LogLevel.INFO) == LogLevel.INFO
    assert normalize_log_level(ObservabilitySeverity.WARNING) == LogLevel.WARNING
    assert normalize_log_level(" INFO ") == LogLevel.INFO
    assert normalize_log_level("error") == LogLevel.ERROR
    assert normalize_log_level("CRITICAL") == LogLevel.CRITICAL


def test_normalize_log_level_rejects_invalid_value():
    with pytest.raises(ValueError):
        normalize_log_level("bad")

    with pytest.raises(ValueError):
        normalize_log_level("")


def test_merge_log_attributes_merges_dictionaries():
    assert merge_log_attributes(
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


def test_merge_log_attributes_rejects_invalid_values():
    with pytest.raises(ValueError):
        merge_log_attributes([], {})

    with pytest.raises(ValueError):
        merge_log_attributes({}, [])


def test_compact_log_record_removes_none_values():
    payload = compact_log_record(
        {
            "message": "ok",
            "error": None,
            "trace_id": "trace-1",
        },
    )

    assert payload == {
        "message": "ok",
        "trace_id": "trace-1",
    }


def test_structured_log_record_to_dict():
    record = StructuredLogRecord(
        message="Market state loaded.",
        component="market-agent",
        level="INFO",
        timestamp="2026-01-01T00:00:00+00:00",
        event_name="market.state.loaded",
        attributes={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        trace_id="trace-1",
        span_id="span-1",
    )

    assert record.to_dict() == {
        "message": "Market state loaded.",
        "component": "market-agent",
        "level": "info",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "event_name": "market.state.loaded",
        "attributes": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        "trace_id": "trace-1",
        "span_id": "span-1",
    }


def test_structured_log_record_to_dict_with_error():
    record = StructuredLogRecord(
        message="Risk failed.",
        component="risk-agent",
        level="error",
        timestamp="2026-01-01T00:00:00+00:00",
        event_name="risk.failed",
        error="Invalid stop loss.",
    )

    assert record.to_dict() == {
        "message": "Risk failed.",
        "component": "risk-agent",
        "level": "error",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "event_name": "risk.failed",
        "attributes": {},
        "error": "Invalid stop loss.",
    }


def test_structured_log_record_to_event():
    record = StructuredLogRecord(
        message="Trade executed.",
        component="execution-agent",
        level="warning",
        timestamp="2026-01-01T00:00:00+00:00",
        event_name="trade.executed",
        attributes={
            "order_id": "order-1",
        },
    )

    event = record.to_event()
    payload = event.to_dict()

    assert payload["name"] == "trade.executed"
    assert payload["component"] == "execution-agent"
    assert payload["severity"] == "warning"
    assert payload["message"] == "Trade executed."
    assert payload["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert payload["attributes"]["event_name"] == "trade.executed"
    assert payload["attributes"]["level"] == "warning"


def test_structured_log_record_defaults():
    record = StructuredLogRecord(
        message="System started.",
        component="aqos",
    )

    payload = record.to_dict()

    assert payload["message"] == "System started."
    assert payload["component"] == "aqos"
    assert payload["level"] == "info"
    assert payload["event_name"] == "log.recorded"
    assert payload["timestamp"]
    assert payload["attributes"] == {}


def test_structured_log_record_rejects_invalid_values():
    with pytest.raises(ValueError):
        StructuredLogRecord(message="", component="aqos")

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="")

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="aqos", level="bad")

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="aqos", timestamp="")

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="aqos", event_name="")

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="aqos", attributes=[])

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="aqos", error="")

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="aqos", trace_id="")

    with pytest.raises(ValueError):
        StructuredLogRecord(message="ok", component="aqos", span_id="")


def test_build_log_record_with_timestamp():
    record = build_log_record(
        message="API request completed.",
        component="api",
        level="debug",
        event_name="api.request.completed",
        attributes={
            "route": "/health",
        },
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert record.to_dict() == {
        "message": "API request completed.",
        "component": "api",
        "level": "debug",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "event_name": "api.request.completed",
        "attributes": {
            "route": "/health",
        },
    }


def test_in_memory_log_sink_write_and_latest():
    sink = InMemoryLogSink()

    record_1 = StructuredLogRecord(
        message="one",
        component="api",
    )
    record_2 = StructuredLogRecord(
        message="two",
        component="api",
    )

    assert sink.write(record_1) == record_1
    assert sink.write(record_2) == record_2

    assert sink.count() == 2
    assert sink.latest() == [
        record_1,
        record_2,
    ]
    assert sink.latest(limit=1) == [
        record_2,
    ]


def test_in_memory_log_sink_filters_records():
    sink = InMemoryLogSink()

    info_record = StructuredLogRecord(
        message="Info",
        component="api",
        level="info",
    )
    error_record = StructuredLogRecord(
        message="Error",
        component="risk",
        level="error",
    )

    sink.write(info_record)
    sink.write(error_record)

    assert sink.filter_by_level("info") == [
        info_record,
    ]
    assert sink.filter_by_component("risk") == [
        error_record,
    ]


def test_in_memory_log_sink_to_dicts_and_clear():
    sink = InMemoryLogSink()

    sink.write(
        StructuredLogRecord(
            message="Info",
            component="api",
            level="info",
            timestamp="2026-01-01T00:00:00+00:00",
        ),
    )

    assert sink.to_dicts() == [
        {
            "message": "Info",
            "component": "api",
            "level": "info",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "event_name": "log.recorded",
            "attributes": {},
        },
    ]

    sink.clear()

    assert sink.count() == 0
    assert sink.latest() == []


def test_in_memory_log_sink_rejects_invalid_values():
    sink = InMemoryLogSink()

    with pytest.raises(ValueError):
        sink.write("bad")

    with pytest.raises(ValueError):
        sink.latest(limit=0)

    with pytest.raises(ValueError):
        sink.latest(limit="bad")

    with pytest.raises(ValueError):
        sink.filter_by_component("")


def test_structured_logger_writes_logs():
    sink = InMemoryLogSink()

    logger = StructuredLogger(
        component="market-agent",
        sink=sink,
        default_attributes={
            "symbol": "XAUUSD",
        },
    )

    record = logger.info(
        "Market state loaded.",
        event_name="market.state.loaded",
        attributes={
            "timeframe": "H1",
        },
        trace_id="trace-1",
        span_id="span-1",
    )

    assert sink.count() == 1
    assert record.to_dict() == {
        "message": "Market state loaded.",
        "component": "market-agent",
        "level": "info",
        "event_name": "market.state.loaded",
        "attributes": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        "trace_id": "trace-1",
        "span_id": "span-1",
        "timestamp": record.timestamp,
    }


def test_structured_logger_level_helpers():
    logger = build_logger("api")

    debug_record = logger.debug("debug message")
    info_record = logger.info("info message")
    warning_record = logger.warning("warning message")
    error_record = logger.error("error message", error="Error detail.")
    critical_record = logger.critical("critical message", error="Critical detail.")

    assert debug_record.level == LogLevel.DEBUG
    assert info_record.level == LogLevel.INFO
    assert warning_record.level == LogLevel.WARNING
    assert error_record.level == LogLevel.ERROR
    assert critical_record.level == LogLevel.CRITICAL

    assert logger.sink.count() == 5
    assert logger.sink.filter_by_level("error") == [
        error_record,
    ]


def test_structured_logger_rejects_invalid_values():
    with pytest.raises(ValueError):
        StructuredLogger(component="")

    with pytest.raises(ValueError):
        StructuredLogger(
            component="api",
            sink="bad",
        )

    with pytest.raises(ValueError):
        StructuredLogger(
            component="api",
            default_attributes=[],
        )


def test_build_logger_creates_logger():
    logger = build_logger(
        "risk-agent",
        default_attributes={
            "symbol": "XAUUSD",
        },
    )

    record = logger.warning("Risk threshold close.")

    assert isinstance(logger, StructuredLogger)
    assert record.to_dict()["component"] == "risk-agent"
    assert record.to_dict()["attributes"] == {
        "symbol": "XAUUSD",
    }


def test_log_exception_records_error():
    logger = build_logger("risk-agent")

    try:
        raise ValueError("Invalid stop loss.")
    except ValueError as exc:
        record = log_exception(
            logger,
            exc,
            message="Risk validation failed.",
            attributes={
                "symbol": "XAUUSD",
            },
            trace_id="trace-1",
        )

    payload = record.to_dict()

    assert payload["message"] == "Risk validation failed."
    assert payload["level"] == "error"
    assert payload["event_name"] == "log.exception"
    assert payload["error"] == "Invalid stop loss."
    assert payload["trace_id"] == "trace-1"
    assert payload["attributes"] == {
        "symbol": "XAUUSD",
        "exception_type": "ValueError",
    }


def test_log_exception_rejects_invalid_values():
    logger = build_logger("risk-agent")

    with pytest.raises(ValueError):
        log_exception(
            "bad",
            ValueError("Invalid."),
        )

    with pytest.raises(ValueError):
        log_exception(
            logger,
            "bad",
        )


def test_observability_logging_exports_exist():
    import aqos.observability as observability

    expected_exports = [
        "InMemoryLogSink",
        "LogLevel",
        "StructuredLogRecord",
        "StructuredLogger",
        "build_log_record",
        "build_logger",
        "compact_log_record",
        "log_exception",
        "merge_log_attributes",
        "normalize_log_level",
    ]

    for export_name in expected_exports:
        assert hasattr(observability, export_name), export_name