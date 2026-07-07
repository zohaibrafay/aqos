"""
Economic calendar service.

Provides a lightweight economic calendar service for storing,
retrieving, filtering, and checking macroeconomic events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class EconomicCalendarEvent:
    """
    Represents an economic calendar event.
    """

    event_id: str
    title: str
    country: str
    currency: str
    event_time: str
    impact: str
    forecast: float | None = None
    previous: float | None = None
    actual: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class EconomicCalendarService:
    """
    Service layer for economic calendar events.
    """

    VALID_IMPACTS = {
        "low",
        "medium",
        "high",
    }

    def __init__(self) -> None:
        self._events: dict[str, EconomicCalendarEvent] = {}

    def create_event(
        self,
        event_id: str,
        title: str,
        country: str,
        currency: str,
        event_time: str,
        impact: str,
        forecast: float | None = None,
        previous: float | None = None,
        actual: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EconomicCalendarEvent:
        """
        Create a validated economic calendar event.
        """

        normalized_impact = impact.lower().strip()
        normalized_currency = currency.upper().strip()
        normalized_country = country.strip()

        event = EconomicCalendarEvent(
            event_id=event_id,
            title=title,
            country=normalized_country,
            currency=normalized_currency,
            event_time=event_time,
            impact=normalized_impact,
            forecast=forecast,
            previous=previous,
            actual=actual,
            metadata=metadata or {},
        )

        self._validate_event(event)

        return event

    def add_event(
        self,
        event: EconomicCalendarEvent,
    ) -> EconomicCalendarEvent:
        """
        Add an economic calendar event.
        """

        self._validate_event(event)

        if event.event_id in self._events:
            raise ValueError("Economic calendar event already exists.")

        self._events[event.event_id] = event

        return event

    def add(
        self,
        event_id: str,
        title: str,
        country: str,
        currency: str,
        event_time: str,
        impact: str,
        forecast: float | None = None,
        previous: float | None = None,
        actual: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> EconomicCalendarEvent:
        """
        Create and add an economic calendar event.
        """

        event = self.create_event(
            event_id=event_id,
            title=title,
            country=country,
            currency=currency,
            event_time=event_time,
            impact=impact,
            forecast=forecast,
            previous=previous,
            actual=actual,
            metadata=metadata,
        )

        return self.add_event(event)

    def get(
        self,
        event_id: str,
    ) -> EconomicCalendarEvent | None:
        """
        Get an event by ID.
        """

        self._validate_event_id(event_id)

        return self._events.get(event_id)

    def get_required(
        self,
        event_id: str,
    ) -> EconomicCalendarEvent:
        """
        Get an event or raise if it does not exist.
        """

        event = self.get(event_id)

        if event is None:
            raise ValueError("Economic calendar event does not exist.")

        return event

    def exists(
        self,
        event_id: str,
    ) -> bool:
        """
        Check whether an event exists.
        """

        self._validate_event_id(event_id)

        return event_id in self._events

    def list(self) -> list[EconomicCalendarEvent]:
        """
        Return all events sorted by event time.
        """

        return sorted(
            self._events.values(),
            key=lambda event: event.event_time,
        )

    def upcoming(
        self,
        reference_time: str,
        limit: int | None = None,
    ) -> list[EconomicCalendarEvent]:
        """
        Return upcoming events from a reference time.
        """

        self._validate_event_time(reference_time)

        events = [
            event
            for event in self.list()
            if event.event_time >= reference_time
        ]

        if limit is None:
            return events

        self._validate_limit(limit)

        return events[:limit]

    def past(
        self,
        reference_time: str,
        limit: int | None = None,
    ) -> list[EconomicCalendarEvent]:
        """
        Return past events before a reference time.
        """

        self._validate_event_time(reference_time)

        events = [
            event
            for event in reversed(self.list())
            if event.event_time < reference_time
        ]

        if limit is None:
            return events

        self._validate_limit(limit)

        return events[:limit]

    def within_window(
        self,
        start_time: str,
        end_time: str,
    ) -> list[EconomicCalendarEvent]:
        """
        Return events inside a time window.
        """

        self._validate_event_time(start_time)
        self._validate_event_time(end_time)

        if end_time < start_time:
            raise ValueError("End time cannot be earlier than start time.")

        return [
            event
            for event in self.list()
            if start_time <= event.event_time <= end_time
        ]

    def filter_by_currency(
        self,
        currency: str,
    ) -> list[EconomicCalendarEvent]:
        """
        Return events for a currency.
        """

        normalized_currency = currency.upper().strip()
        self._validate_currency(normalized_currency)

        return [
            event
            for event in self.list()
            if event.currency == normalized_currency
        ]

    def filter_by_country(
        self,
        country: str,
    ) -> list[EconomicCalendarEvent]:
        """
        Return events for a country.
        """

        self._validate_country(country)

        return [
            event
            for event in self.list()
            if event.country == country
        ]

    def filter_by_impact(
        self,
        impact: str,
    ) -> list[EconomicCalendarEvent]:
        """
        Return events by impact level.
        """

        normalized_impact = impact.lower().strip()
        self._validate_impact(normalized_impact)

        return [
            event
            for event in self.list()
            if event.impact == normalized_impact
        ]

    def high_impact(
        self,
        currency: str | None = None,
    ) -> list[EconomicCalendarEvent]:
        """
        Return high-impact events.
        """

        events = self.filter_by_impact("high")

        if currency is None:
            return events

        normalized_currency = currency.upper().strip()
        self._validate_currency(normalized_currency)

        return [
            event
            for event in events
            if event.currency == normalized_currency
        ]

    def has_high_impact_event(
        self,
        currency: str,
        start_time: str,
        end_time: str,
    ) -> bool:
        """
        Check whether a high-impact event exists in a time window.
        """

        normalized_currency = currency.upper().strip()
        self._validate_currency(normalized_currency)

        events = self.within_window(
            start_time=start_time,
            end_time=end_time,
        )

        return any(
            event.currency == normalized_currency
            and event.impact == "high"
            for event in events
        )

    def count(self) -> int:
        """
        Return number of events.
        """

        return len(self._events)

    def remove(
        self,
        event_id: str,
    ) -> None:
        """
        Remove an event.
        """

        self._validate_event_id(event_id)

        self._events.pop(event_id, None)

    def clear(self) -> None:
        """
        Clear all events.
        """

        self._events.clear()

    def _validate_event(
        self,
        event: EconomicCalendarEvent,
    ) -> None:
        """
        Validate an economic calendar event.
        """

        self._validate_event_id(event.event_id)

        if not event.title:
            raise ValueError("Event title cannot be empty.")

        self._validate_country(event.country)
        self._validate_currency(event.currency)
        self._validate_event_time(event.event_time)
        self._validate_impact(event.impact)

    def _validate_event_id(
        self,
        event_id: str,
    ) -> None:
        """
        Validate event ID.
        """

        if not event_id:
            raise ValueError("Event ID cannot be empty.")

    def _validate_country(
        self,
        country: str,
    ) -> None:
        """
        Validate country.
        """

        if not country:
            raise ValueError("Country cannot be empty.")

    def _validate_currency(
        self,
        currency: str,
    ) -> None:
        """
        Validate currency.
        """

        if not currency:
            raise ValueError("Currency cannot be empty.")

    def _validate_event_time(
        self,
        event_time: str,
    ) -> None:
        """
        Validate event time.
        """

        if not event_time:
            raise ValueError("Event time cannot be empty.")

    def _validate_impact(
        self,
        impact: str,
    ) -> None:
        """
        Validate impact level.
        """

        if impact not in self.VALID_IMPACTS:
            raise ValueError("Impact must be low, medium, or high.")

    def _validate_limit(
        self,
        limit: int,
    ) -> None:
        """
        Validate limit.
        """

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")


__all__ = [
    "EconomicCalendarEvent",
    "EconomicCalendarService",
]