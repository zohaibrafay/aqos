"""
Unit tests for EconomicCalendarService.
"""

import pytest

from aqos.services import (
    EconomicCalendarEvent,
    EconomicCalendarService,
)


def test_create_event():
    service = EconomicCalendarService()

    event = service.create_event(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="usd",
        event_time="2026-01-01T13:30:00",
        impact="HIGH",
        forecast=3.2,
        previous=3.1,
        actual=3.3,
        metadata={"category": "inflation"},
    )

    assert isinstance(event, EconomicCalendarEvent)
    assert event.event_id == "event-1"
    assert event.title == "US CPI"
    assert event.country == "United States"
    assert event.currency == "USD"
    assert event.impact == "high"
    assert event.forecast == 3.2
    assert event.previous == 3.1
    assert event.actual == 3.3
    assert event.metadata["category"] == "inflation"


def test_add_event_object():
    service = EconomicCalendarService()

    event = service.create_event(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00",
        impact="high",
    )

    added = service.add_event(event)

    assert added.event_id == "event-1"
    assert service.count() == 1


def test_add_event_directly():
    service = EconomicCalendarService()

    event = service.add(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00",
        impact="high",
    )

    assert event.event_id == "event-1"
    assert service.count() == 1


def test_add_duplicate_event():
    service = EconomicCalendarService()

    service.add(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00",
        impact="high",
    )

    with pytest.raises(ValueError):
        service.add(
            event_id="event-1",
            title="US CPI Duplicate",
            country="United States",
            currency="USD",
            event_time="2026-01-01T13:30:00",
            impact="high",
        )


def test_get_event():
    service = EconomicCalendarService()

    service.add(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00",
        impact="high",
    )

    event = service.get("event-1")

    assert event is not None
    assert event.event_id == "event-1"


def test_get_missing_event():
    service = EconomicCalendarService()

    event = service.get("missing")

    assert event is None


def test_get_required_missing_event():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.get_required("missing")


def test_exists_true():
    service = EconomicCalendarService()

    service.add(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00",
        impact="high",
    )

    assert service.exists("event-1") is True


def test_exists_false():
    service = EconomicCalendarService()

    assert service.exists("event-1") is False


def test_list_events_sorted_by_time():
    service = EconomicCalendarService()

    service.add(
        event_id="event-2",
        title="FOMC",
        country="United States",
        currency="USD",
        event_time="2026-01-02T19:00:00",
        impact="high",
    )
    service.add(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00",
        impact="high",
    )

    events = service.list()

    assert events[0].event_id == "event-1"
    assert events[1].event_id == "event-2"


def test_upcoming_events():
    service = EconomicCalendarService()

    service.add("event-1", "Past CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "Future CPI", "United States", "USD", "2026-01-02T13:30:00", "high")

    events = service.upcoming(
        reference_time="2026-01-02T00:00:00",
    )

    assert len(events) == 1
    assert events[0].event_id == "event-2"


def test_upcoming_events_with_limit():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "FOMC", "United States", "USD", "2026-01-02T19:00:00", "high")

    events = service.upcoming(
        reference_time="2026-01-01T00:00:00",
        limit=1,
    )

    assert len(events) == 1
    assert events[0].event_id == "event-1"


def test_past_events():
    service = EconomicCalendarService()

    service.add("event-1", "Past CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "Future CPI", "United States", "USD", "2026-01-02T13:30:00", "high")

    events = service.past(
        reference_time="2026-01-02T00:00:00",
    )

    assert len(events) == 1
    assert events[0].event_id == "event-1"


def test_within_window():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "FOMC", "United States", "USD", "2026-01-02T19:00:00", "high")

    events = service.within_window(
        start_time="2026-01-01T00:00:00",
        end_time="2026-01-01T23:59:59",
    )

    assert len(events) == 1
    assert events[0].event_id == "event-1"


def test_filter_by_currency():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "EU CPI", "Eurozone", "EUR", "2026-01-01T10:00:00", "medium")

    events = service.filter_by_currency("usd")

    assert len(events) == 1
    assert events[0].event_id == "event-1"


def test_filter_by_country():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "EU CPI", "Eurozone", "EUR", "2026-01-01T10:00:00", "medium")

    events = service.filter_by_country("Eurozone")

    assert len(events) == 1
    assert events[0].event_id == "event-2"


def test_filter_by_impact():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "Minor Event", "United States", "USD", "2026-01-01T10:00:00", "low")

    events = service.filter_by_impact("high")

    assert len(events) == 1
    assert events[0].event_id == "event-1"


def test_high_impact_events():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "Minor Event", "United States", "USD", "2026-01-01T10:00:00", "low")

    events = service.high_impact()

    assert len(events) == 1
    assert events[0].event_id == "event-1"


def test_high_impact_events_by_currency():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "EU CPI", "Eurozone", "EUR", "2026-01-01T10:00:00", "high")

    events = service.high_impact("USD")

    assert len(events) == 1
    assert events[0].currency == "USD"


def test_has_high_impact_event_true():
    service = EconomicCalendarService()

    service.add("event-1", "FOMC", "United States", "USD", "2026-01-01T19:00:00", "high")

    result = service.has_high_impact_event(
        currency="USD",
        start_time="2026-01-01T18:00:00",
        end_time="2026-01-01T20:00:00",
    )

    assert result is True


def test_has_high_impact_event_false():
    service = EconomicCalendarService()

    service.add("event-1", "Minor Event", "United States", "USD", "2026-01-01T19:00:00", "low")

    result = service.has_high_impact_event(
        currency="USD",
        start_time="2026-01-01T18:00:00",
        end_time="2026-01-01T20:00:00",
    )

    assert result is False


def test_remove_event():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")

    service.remove("event-1")

    assert service.exists("event-1") is False
    assert service.count() == 0


def test_clear_events():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")
    service.add("event-2", "FOMC", "United States", "USD", "2026-01-02T19:00:00", "high")

    service.clear()

    assert service.count() == 0


def test_empty_event_id():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.add("", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")


def test_empty_title():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.add("event-1", "", "United States", "USD", "2026-01-01T13:30:00", "high")


def test_empty_country():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.add("event-1", "US CPI", "", "USD", "2026-01-01T13:30:00", "high")


def test_empty_currency():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.add("event-1", "US CPI", "United States", "", "2026-01-01T13:30:00", "high")


def test_empty_event_time():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.add("event-1", "US CPI", "United States", "USD", "", "high")


def test_invalid_impact():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "critical")


def test_invalid_limit():
    service = EconomicCalendarService()

    service.add("event-1", "US CPI", "United States", "USD", "2026-01-01T13:30:00", "high")

    with pytest.raises(ValueError):
        service.upcoming(
            reference_time="2026-01-01T00:00:00",
            limit=0,
        )


def test_invalid_window():
    service = EconomicCalendarService()

    with pytest.raises(ValueError):
        service.within_window(
            start_time="2026-01-02T00:00:00",
            end_time="2026-01-01T00:00:00",
        )