"""
Unit tests for common time utilities.
"""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from aqos.common import (
    DATE_FORMAT,
    ISO_DATETIME_FORMAT,
    add_days,
    add_hours,
    add_minutes,
    add_seconds,
    datetime_to_timestamp,
    days_between,
    format_date,
    format_datetime,
    hours_between,
    is_future,
    is_past,
    is_within_window,
    minutes_between,
    normalize_time_payload,
    parse_date,
    parse_datetime,
    seconds_between,
    timestamp_to_datetime,
    to_utc,
    today_utc,
    utc_now,
    utc_now_iso,
)


def test_time_formats():
    assert ISO_DATETIME_FORMAT == "%Y-%m-%dT%H:%M:%SZ"
    assert DATE_FORMAT == "%Y-%m-%d"


def test_utc_now():
    value = utc_now()

    assert isinstance(value, datetime)
    assert value.tzinfo == UTC


def test_utc_now_iso():
    value = utc_now_iso()

    assert isinstance(value, str)
    assert value.endswith("Z")


def test_today_utc():
    value = today_utc()

    assert isinstance(value, date)


def test_parse_datetime_from_z_string():
    value = parse_datetime("2026-01-02T03:04:05Z")

    assert value == datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )


def test_parse_datetime_from_offset_string():
    value = parse_datetime("2026-01-02T08:04:05+05:00")

    assert value == datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )


def test_parse_datetime_from_naive_datetime():
    raw = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
    )

    value = parse_datetime(raw)

    assert value == datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )


def test_parse_datetime_from_aware_datetime():
    raw = datetime(
        2026,
        1,
        2,
        8,
        4,
        5,
        tzinfo=timezone(timedelta(hours=5)),
    )

    value = parse_datetime(raw)

    assert value == datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )


def test_parse_datetime_rejects_invalid_type():
    with pytest.raises(TypeError):
        parse_datetime(123)


def test_parse_datetime_rejects_empty_string():
    with pytest.raises(ValueError):
        parse_datetime("")


def test_parse_datetime_rejects_invalid_format():
    with pytest.raises(ValueError):
        parse_datetime("not-a-date")


def test_parse_date_from_string():
    value = parse_date("2026-01-02")

    assert value == date(2026, 1, 2)


def test_parse_date_from_date():
    raw = date(2026, 1, 2)

    assert parse_date(raw) == raw


def test_parse_date_from_datetime():
    raw = datetime(2026, 1, 2, 3, 4, 5)

    assert parse_date(raw) == date(2026, 1, 2)


def test_parse_date_rejects_invalid_type():
    with pytest.raises(TypeError):
        parse_date(123)


def test_parse_date_rejects_empty_string():
    with pytest.raises(ValueError):
        parse_date("")


def test_parse_date_rejects_invalid_format():
    with pytest.raises(ValueError):
        parse_date("02-01-2026")


def test_to_utc_with_naive_datetime():
    raw = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
    )

    value = to_utc(raw)

    assert value.tzinfo == UTC
    assert value.hour == 3


def test_to_utc_with_aware_datetime():
    raw = datetime(
        2026,
        1,
        2,
        8,
        4,
        5,
        tzinfo=timezone(timedelta(hours=5)),
    )

    value = to_utc(raw)

    assert value == datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )


def test_to_utc_rejects_invalid_type():
    with pytest.raises(TypeError):
        to_utc("invalid")


def test_format_datetime():
    value = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )

    assert format_datetime(value) == "2026-01-02T03:04:05Z"


def test_format_datetime_custom_format():
    value = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )

    assert format_datetime(value, "%Y/%m/%d") == "2026/01/02"


def test_format_datetime_rejects_invalid_format_type():
    value = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )

    with pytest.raises(TypeError):
        format_datetime(value, 123)


def test_format_date():
    assert format_date(date(2026, 1, 2)) == "2026-01-02"


def test_format_date_custom_format():
    assert format_date(date(2026, 1, 2), "%d/%m/%Y") == "02/01/2026"


def test_format_date_rejects_invalid_date_type():
    with pytest.raises(TypeError):
        format_date("2026-01-02")


def test_format_date_rejects_invalid_format_type():
    with pytest.raises(TypeError):
        format_date(date(2026, 1, 2), 123)


def test_datetime_to_timestamp():
    value = datetime(
        1970,
        1,
        1,
        0,
        0,
        1,
        tzinfo=UTC,
    )

    assert datetime_to_timestamp(value) == 1.0


def test_timestamp_to_datetime():
    value = timestamp_to_datetime(1)

    assert value == datetime(
        1970,
        1,
        1,
        0,
        0,
        1,
        tzinfo=UTC,
    )


def test_timestamp_to_datetime_rejects_invalid_type():
    with pytest.raises(TypeError):
        timestamp_to_datetime("1")


def test_add_seconds():
    value = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    assert add_seconds(value, 30) == datetime(2026, 1, 1, 0, 0, 30, tzinfo=UTC)


def test_add_seconds_rejects_invalid_type():
    with pytest.raises(TypeError):
        add_seconds(datetime(2026, 1, 1, tzinfo=UTC), "30")


def test_add_minutes():
    value = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    assert add_minutes(value, 2) == datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC)


def test_add_minutes_rejects_invalid_type():
    with pytest.raises(TypeError):
        add_minutes(datetime(2026, 1, 1, tzinfo=UTC), "2")


def test_add_hours():
    value = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    assert add_hours(value, 2) == datetime(2026, 1, 1, 2, 0, 0, tzinfo=UTC)


def test_add_hours_rejects_invalid_type():
    with pytest.raises(TypeError):
        add_hours(datetime(2026, 1, 1, tzinfo=UTC), "2")


def test_add_days():
    value = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    assert add_days(value, 2) == datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)


def test_add_days_rejects_invalid_type():
    with pytest.raises(TypeError):
        add_days(datetime(2026, 1, 1, tzinfo=UTC), "2")


def test_seconds_between():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 0, 1, 0, tzinfo=UTC)

    assert seconds_between(start, end) == 60.0


def test_minutes_between():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 0, 2, 0, tzinfo=UTC)

    assert minutes_between(start, end) == 2.0


def test_hours_between():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 1, 2, 0, 0, tzinfo=UTC)

    assert hours_between(start, end) == 2.0


def test_days_between():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)

    assert days_between(start, end) == 2.0


def test_is_past():
    reference = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)
    value = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)

    assert is_past(value, reference=reference) is True


def test_is_future():
    reference = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    value = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)

    assert is_future(value, reference=reference) is True


def test_is_within_window():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)
    value = datetime(2026, 1, 2, 0, 0, 0, tzinfo=UTC)

    assert is_within_window(value, start, end) is True


def test_is_within_window_false():
    start = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 1, 3, 0, 0, 0, tzinfo=UTC)
    value = datetime(2026, 1, 4, 0, 0, 0, tzinfo=UTC)

    assert is_within_window(value, start, end) is False


def test_normalize_time_payload():
    payload = {
        "event_time": "2026-01-02T03:04:05Z",
    }

    value = normalize_time_payload(payload, "event_time")

    assert value == datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )


def test_normalize_time_payload_rejects_invalid_payload():
    with pytest.raises(TypeError):
        normalize_time_payload("invalid", "event_time")


def test_normalize_time_payload_rejects_missing_key():
    with pytest.raises(ValueError):
        normalize_time_payload({}, "event_time")