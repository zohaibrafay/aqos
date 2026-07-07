"""
Common time utilities.

Defines reusable datetime helpers for AQOS modules.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any


ISO_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
DATE_FORMAT = "%Y-%m-%d"


def utc_now() -> datetime:
    """
    Return the current timezone-aware UTC datetime.
    """

    return datetime.now(UTC)


def utc_now_iso() -> str:
    """
    Return the current UTC datetime as ISO string.
    """

    return format_datetime(utc_now())


def today_utc() -> date:
    """
    Return today's UTC date.
    """

    return utc_now().date()


def parse_datetime(
    value: str | datetime,
) -> datetime:
    """
    Parse a string or datetime into a timezone-aware UTC datetime.
    """

    if isinstance(value, datetime):
        return to_utc(value)

    if not isinstance(value, str):
        raise TypeError("Datetime value must be a string or datetime.")

    text = value.strip()

    if not text:
        raise ValueError("Datetime value cannot be empty.")

    normalized_text = text.replace("Z", "+00:00")

    try:
        parsed = datetime.fromisoformat(normalized_text)
    except ValueError as exc:
        raise ValueError("Datetime value must be ISO formatted.") from exc

    return to_utc(parsed)


def parse_date(
    value: str | date,
) -> date:
    """
    Parse a string or date into a date object.
    """

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not isinstance(value, str):
        raise TypeError("Date value must be a string or date.")

    text = value.strip()

    if not text:
        raise ValueError("Date value cannot be empty.")

    try:
        return datetime.strptime(text, DATE_FORMAT).date()
    except ValueError as exc:
        raise ValueError("Date value must use YYYY-MM-DD format.") from exc


def to_utc(
    value: datetime,
) -> datetime:
    """
    Convert a datetime to timezone-aware UTC.

    Naive datetimes are treated as UTC.
    """

    if not isinstance(value, datetime):
        raise TypeError("Datetime value must be a datetime.")

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)

    return value.astimezone(UTC)


def format_datetime(
    value: datetime,
    fmt: str = ISO_DATETIME_FORMAT,
) -> str:
    """
    Format datetime as a string.
    """

    if not isinstance(fmt, str):
        raise TypeError("Datetime format must be a string.")

    normalized = to_utc(value)

    return normalized.strftime(fmt)


def format_date(
    value: date,
    fmt: str = DATE_FORMAT,
) -> str:
    """
    Format date as a string.
    """

    if not isinstance(value, date):
        raise TypeError("Date value must be a date.")

    if not isinstance(fmt, str):
        raise TypeError("Date format must be a string.")

    return value.strftime(fmt)


def datetime_to_timestamp(
    value: datetime,
) -> float:
    """
    Convert datetime to Unix timestamp seconds.
    """

    return float(to_utc(value).timestamp())


def timestamp_to_datetime(
    value: int | float,
) -> datetime:
    """
    Convert Unix timestamp seconds to UTC datetime.
    """

    if not isinstance(value, int | float):
        raise TypeError("Timestamp must be numeric.")

    return datetime.fromtimestamp(float(value), tz=UTC)


def add_seconds(
    value: datetime,
    seconds: int | float,
) -> datetime:
    """
    Add seconds to datetime.
    """

    if not isinstance(seconds, int | float):
        raise TypeError("Seconds must be numeric.")

    return to_utc(value) + timedelta(seconds=float(seconds))


def add_minutes(
    value: datetime,
    minutes: int | float,
) -> datetime:
    """
    Add minutes to datetime.
    """

    if not isinstance(minutes, int | float):
        raise TypeError("Minutes must be numeric.")

    return to_utc(value) + timedelta(minutes=float(minutes))


def add_hours(
    value: datetime,
    hours: int | float,
) -> datetime:
    """
    Add hours to datetime.
    """

    if not isinstance(hours, int | float):
        raise TypeError("Hours must be numeric.")

    return to_utc(value) + timedelta(hours=float(hours))


def add_days(
    value: datetime,
    days: int | float,
) -> datetime:
    """
    Add days to datetime.
    """

    if not isinstance(days, int | float):
        raise TypeError("Days must be numeric.")

    return to_utc(value) + timedelta(days=float(days))


def seconds_between(
    start: datetime,
    end: datetime,
) -> float:
    """
    Return seconds between two datetimes.
    """

    return float((to_utc(end) - to_utc(start)).total_seconds())


def minutes_between(
    start: datetime,
    end: datetime,
) -> float:
    """
    Return minutes between two datetimes.
    """

    return seconds_between(start, end) / 60.0


def hours_between(
    start: datetime,
    end: datetime,
) -> float:
    """
    Return hours between two datetimes.
    """

    return seconds_between(start, end) / 3600.0


def days_between(
    start: datetime,
    end: datetime,
) -> float:
    """
    Return days between two datetimes.
    """

    return seconds_between(start, end) / 86_400.0


def is_past(
    value: datetime,
    reference: datetime | None = None,
) -> bool:
    """
    Return True if datetime is before reference.
    """

    reference_time = to_utc(reference or utc_now())

    return to_utc(value) < reference_time


def is_future(
    value: datetime,
    reference: datetime | None = None,
) -> bool:
    """
    Return True if datetime is after reference.
    """

    reference_time = to_utc(reference or utc_now())

    return to_utc(value) > reference_time


def is_within_window(
    value: datetime,
    start: datetime,
    end: datetime,
) -> bool:
    """
    Return True if datetime is between start and end inclusive.
    """

    target = to_utc(value)

    return to_utc(start) <= target <= to_utc(end)


def normalize_time_payload(
    payload: dict[str, Any],
    key: str,
) -> datetime:
    """
    Extract and parse datetime from payload.
    """

    if not isinstance(payload, dict):
        raise TypeError("Payload must be a dictionary.")

    if key not in payload:
        raise ValueError(f"Payload is missing required datetime key: {key}")

    return parse_datetime(payload[key])


__all__ = [
    "DATE_FORMAT",
    "ISO_DATETIME_FORMAT",
    "add_days",
    "add_hours",
    "add_minutes",
    "add_seconds",
    "datetime_to_timestamp",
    "days_between",
    "format_date",
    "format_datetime",
    "hours_between",
    "is_future",
    "is_past",
    "is_within_window",
    "minutes_between",
    "normalize_time_payload",
    "parse_date",
    "parse_datetime",
    "seconds_between",
    "timestamp_to_datetime",
    "to_utc",
    "today_utc",
    "utc_now",
    "utc_now_iso",
]