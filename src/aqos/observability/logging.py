"""
AQOS structured logging primitives.

This module provides dependency-free structured log records and an in-memory
logger that can be used by agents, services, CLI commands, and API wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.observability.base import (
    ObservabilityEvent,
    ObservabilitySeverity,
    build_observability_event,
    normalize_severity,
    validate_attributes,
    validate_non_empty_string,
    validate_string,
)


class LogLevel(str, Enum):
    """Supported structured log levels."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class StructuredLogRecord:
    """Structured log record."""

    message: str
    component: str
    level: LogLevel | ObservabilitySeverity | str = LogLevel.INFO
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_name: str = "log.recorded"
    attributes: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    trace_id: str | None = None
    span_id: str | None = None

    def __post_init__(self) -> None:
        validate_non_empty_string(self.message, "Message")
        validate_non_empty_string(self.component, "Component")
        normalize_log_level(self.level)
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_non_empty_string(self.event_name, "Event name")
        validate_attributes(self.attributes)

        if self.error is not None:
            validate_non_empty_string(self.error, "Error")

        if self.trace_id is not None:
            validate_non_empty_string(self.trace_id, "Trace ID")

        if self.span_id is not None:
            validate_non_empty_string(self.span_id, "Span ID")

    def to_dict(self) -> dict[str, Any]:
        """Convert log record into a serializable dictionary."""
        payload = {
            "message": self.message.strip(),
            "component": self.component.strip(),
            "level": normalize_log_level(self.level).value,
            "timestamp": self.timestamp.strip(),
            "event_name": self.event_name.strip(),
            "attributes": dict(self.attributes),
            "error": self.error.strip() if self.error is not None else None,
            "trace_id": self.trace_id.strip() if self.trace_id is not None else None,
            "span_id": self.span_id.strip() if self.span_id is not None else None,
        }

        return compact_log_record(payload)

    def to_event(self) -> ObservabilityEvent:
        """Convert structured log record into an observability event."""
        return build_observability_event(
            name=self.event_name,
            component=self.component,
            severity=normalize_log_level(self.level).value,
            message=self.message,
            attributes=self.to_dict(),
            timestamp=self.timestamp,
        )


@dataclass
class InMemoryLogSink:
    """Simple in-memory sink for structured logs."""

    records: list[StructuredLogRecord] = field(default_factory=list)

    def write(self, record: StructuredLogRecord) -> StructuredLogRecord:
        """Write a structured log record."""
        if not isinstance(record, StructuredLogRecord):
            raise ValueError("Record must be a StructuredLogRecord.")

        self.records.append(record)
        return record

    def latest(self, limit: int | None = None) -> list[StructuredLogRecord]:
        """Return latest log records."""
        if limit is None:
            return list(self.records)

        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("Limit must be a positive integer.")

        return self.records[-limit:]

    def filter_by_level(self, level: LogLevel | ObservabilitySeverity | str) -> list[StructuredLogRecord]:
        """Return records matching level."""
        normalized = normalize_log_level(level)

        return [
            record
            for record in self.records
            if normalize_log_level(record.level) == normalized
        ]

    def filter_by_component(self, component: str) -> list[StructuredLogRecord]:
        """Return records matching component."""
        normalized = validate_non_empty_string(component, "Component")

        return [
            record
            for record in self.records
            if record.component.strip() == normalized
        ]

    def count(self) -> int:
        """Return number of stored log records."""
        return len(self.records)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return stored records as dictionaries."""
        return [
            record.to_dict()
            for record in self.records
        ]

    def clear(self) -> None:
        """Clear stored log records."""
        self.records.clear()


@dataclass
class StructuredLogger:
    """Dependency-free structured logger."""

    component: str
    sink: InMemoryLogSink = field(default_factory=InMemoryLogSink)
    default_attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.component, "Component")
        validate_attributes(self.default_attributes)

        if not isinstance(self.sink, InMemoryLogSink):
            raise ValueError("Sink must be an InMemoryLogSink.")

    def log(
        self,
        message: str,
        *,
        level: LogLevel | ObservabilitySeverity | str = LogLevel.INFO,
        event_name: str = "log.recorded",
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> StructuredLogRecord:
        """Write a structured log record."""
        merged_attributes = merge_log_attributes(
            self.default_attributes,
            attributes or {},
        )

        record = build_log_record(
            message=message,
            component=self.component,
            level=level,
            event_name=event_name,
            attributes=merged_attributes,
            error=error,
            trace_id=trace_id,
            span_id=span_id,
        )

        return self.sink.write(record)

    def debug(
        self,
        message: str,
        *,
        event_name: str = "log.debug",
        attributes: dict[str, Any] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> StructuredLogRecord:
        """Write debug log."""
        return self.log(
            message,
            level=LogLevel.DEBUG,
            event_name=event_name,
            attributes=attributes,
            trace_id=trace_id,
            span_id=span_id,
        )

    def info(
        self,
        message: str,
        *,
        event_name: str = "log.info",
        attributes: dict[str, Any] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> StructuredLogRecord:
        """Write info log."""
        return self.log(
            message,
            level=LogLevel.INFO,
            event_name=event_name,
            attributes=attributes,
            trace_id=trace_id,
            span_id=span_id,
        )

    def warning(
        self,
        message: str,
        *,
        event_name: str = "log.warning",
        attributes: dict[str, Any] | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> StructuredLogRecord:
        """Write warning log."""
        return self.log(
            message,
            level=LogLevel.WARNING,
            event_name=event_name,
            attributes=attributes,
            trace_id=trace_id,
            span_id=span_id,
        )

    def error(
        self,
        message: str,
        *,
        event_name: str = "log.error",
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> StructuredLogRecord:
        """Write error log."""
        return self.log(
            message,
            level=LogLevel.ERROR,
            event_name=event_name,
            attributes=attributes,
            error=error,
            trace_id=trace_id,
            span_id=span_id,
        )

    def critical(
        self,
        message: str,
        *,
        event_name: str = "log.critical",
        attributes: dict[str, Any] | None = None,
        error: str | None = None,
        trace_id: str | None = None,
        span_id: str | None = None,
    ) -> StructuredLogRecord:
        """Write critical log."""
        return self.log(
            message,
            level=LogLevel.CRITICAL,
            event_name=event_name,
            attributes=attributes,
            error=error,
            trace_id=trace_id,
            span_id=span_id,
        )


def normalize_log_level(level: LogLevel | ObservabilitySeverity | str) -> LogLevel:
    """Normalize log level."""
    if isinstance(level, LogLevel):
        return level

    if isinstance(level, ObservabilitySeverity):
        return LogLevel(level.value)

    severity = normalize_severity(level)

    return LogLevel(severity.value)


def merge_log_attributes(
    base_attributes: dict[str, Any],
    extra_attributes: dict[str, Any],
) -> dict[str, Any]:
    """Merge structured log attributes."""
    validate_attributes(base_attributes)
    validate_attributes(extra_attributes)

    return {
        **base_attributes,
        **extra_attributes,
    }


def compact_log_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove empty optional values from log payload."""
    validate_attributes(payload)

    return {
        key: value
        for key, value in payload.items()
        if value is not None
    }


def build_log_record(
    *,
    message: str,
    component: str,
    level: LogLevel | ObservabilitySeverity | str = LogLevel.INFO,
    event_name: str = "log.recorded",
    attributes: dict[str, Any] | None = None,
    error: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    timestamp: str | None = None,
) -> StructuredLogRecord:
    """Build a structured log record."""
    log_kwargs: dict[str, Any] = {
        "message": message,
        "component": component,
        "level": normalize_log_level(level),
        "event_name": event_name,
        "attributes": attributes or {},
        "error": error,
        "trace_id": trace_id,
        "span_id": span_id,
    }

    if timestamp is not None:
        log_kwargs["timestamp"] = timestamp

    return StructuredLogRecord(**log_kwargs)


def build_logger(
    component: str,
    *,
    sink: InMemoryLogSink | None = None,
    default_attributes: dict[str, Any] | None = None,
) -> StructuredLogger:
    """Build a structured logger."""
    return StructuredLogger(
        component=component,
        sink=sink or InMemoryLogSink(),
        default_attributes=default_attributes or {},
    )


def log_exception(
    logger: StructuredLogger,
    exception: Exception,
    *,
    message: str = "Exception captured.",
    event_name: str = "log.exception",
    attributes: dict[str, Any] | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> StructuredLogRecord:
    """Log an exception using a structured logger."""
    if not isinstance(logger, StructuredLogger):
        raise ValueError("Logger must be a StructuredLogger.")

    if not isinstance(exception, Exception):
        raise ValueError("Exception must be an Exception.")

    return logger.error(
        message,
        event_name=event_name,
        attributes={
            **(attributes or {}),
            "exception_type": type(exception).__name__,
        },
        error=str(exception),
        trace_id=trace_id,
        span_id=span_id,
    )