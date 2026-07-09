"""
AQOS economic calendar provider contracts.

This module defines economic calendar event records, query filters,
normalization helpers, and provider result structures for macro events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsEventRecord,
    NewsProviderCapability,
    NewsProviderConfig,
    NewsProviderResult,
    NewsProviderType,
    build_news_event_record,
    build_news_provider_config,
    build_news_provider_result,
    normalize_news_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_integer,
    validate_score,
    validate_string,
)
from aqos.training_data.events import (
    HistoricalEventImpact,
    HistoricalEventSentiment,
    HistoricalEventType,
    normalize_historical_event_impact,
    normalize_historical_event_sentiment,
)


class EconomicCalendarEventCategory(str, Enum):
    """Supported economic calendar categories."""

    INFLATION = "inflation"
    EMPLOYMENT = "employment"
    INTEREST_RATE = "interest_rate"
    GDP = "gdp"
    PMI = "pmi"
    RETAIL_SALES = "retail_sales"
    CENTRAL_BANK = "central_bank"
    HOUSING = "housing"
    TRADE = "trade"
    ENERGY = "energy"
    UNKNOWN = "unknown"


class EconomicCalendarImportance(str, Enum):
    """Supported economic calendar importance values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class EconomicCalendarQuery:
    """Economic calendar query."""

    symbol: str = ""
    countries: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    categories: list[EconomicCalendarEventCategory | str] = field(default_factory=list)
    min_importance: EconomicCalendarImportance | str = EconomicCalendarImportance.LOW
    start_date: str = ""
    end_date: str = ""
    keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_string_list(self.countries, "Countries")
        validate_string_list(self.currencies, "Currencies")
        validate_economic_calendar_categories(self.categories)
        normalize_economic_calendar_importance(self.min_importance)
        validate_string(self.start_date, "Start date")
        validate_string(self.end_date, "End date")
        validate_string_list(self.keywords, "Keywords")
        validate_metadata(self.metadata, "Metadata")

    @property
    def bounded(self) -> bool:
        """Return whether query has start and end date."""
        return bool(self.start_date.strip()) and bool(self.end_date.strip())

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "countries": [item.strip().upper() for item in self.countries],
            "currencies": [item.strip().upper() for item in self.currencies],
            "categories": [
                normalize_economic_calendar_category(item).value
                for item in self.categories
            ],
            "min_importance": normalize_economic_calendar_importance(
                self.min_importance,
            ).value,
            "start_date": self.start_date.strip(),
            "end_date": self.end_date.strip(),
            "bounded": self.bounded,
            "keywords": [item.strip().lower() for item in self.keywords],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class EconomicCalendarEvent:
    """Normalized economic calendar event."""

    event_id: str
    timestamp: str
    title: str
    country: str = ""
    currency: str = ""
    category: EconomicCalendarEventCategory | str = EconomicCalendarEventCategory.UNKNOWN
    importance: EconomicCalendarImportance | str = EconomicCalendarImportance.UNKNOWN
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN
    actual_value: float | None = None
    forecast_value: float | None = None
    previous_value: float | None = None
    surprise: float | None = None
    unit: str = ""
    source: str = ""
    provider_id: str = ""
    url: str = ""
    description: str = ""
    relevance_score: float = 0.0
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.event_id, "Event ID")
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_non_empty_string(self.title, "Title")
        validate_string(self.country, "Country")
        validate_string(self.currency, "Currency")
        normalize_economic_calendar_category(self.category)
        normalize_economic_calendar_importance(self.importance)
        normalize_historical_event_impact(self.impact)
        normalize_historical_event_sentiment(self.sentiment)

        if self.actual_value is not None:
            validate_number_like(self.actual_value, "Actual value")

        if self.forecast_value is not None:
            validate_number_like(self.forecast_value, "Forecast value")

        if self.previous_value is not None:
            validate_number_like(self.previous_value, "Previous value")

        if self.surprise is not None:
            validate_number_like(self.surprise, "Surprise")

        validate_string(self.unit, "Unit")
        validate_string(self.source, "Source")
        validate_string(self.provider_id, "Provider ID")
        validate_string(self.url, "URL")
        validate_string(self.description, "Description")
        validate_score(self.relevance_score, "Relevance score")
        validate_metadata(self.raw_payload, "Raw payload")
        validate_metadata(self.metadata, "Metadata")

    @property
    def has_actual_forecast(self) -> bool:
        """Return whether event has actual and forecast values."""
        return self.actual_value is not None and self.forecast_value is not None

    @property
    def calculated_surprise(self) -> float | None:
        """Return explicit or calculated surprise."""
        if self.surprise is not None:
            return float(self.surprise)

        if self.actual_value is None or self.forecast_value is None:
            return None

        return round(float(self.actual_value) - float(self.forecast_value), 10)

    @property
    def high_importance(self) -> bool:
        """Return whether event is high importance."""
        return normalize_economic_calendar_importance(self.importance) in {
            EconomicCalendarImportance.HIGH,
            EconomicCalendarImportance.CRITICAL,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "event_id": self.event_id.strip(),
            "timestamp": self.timestamp.strip(),
            "title": self.title.strip(),
            "country": self.country.strip().upper(),
            "currency": self.currency.strip().upper(),
            "category": normalize_economic_calendar_category(self.category).value,
            "importance": normalize_economic_calendar_importance(self.importance).value,
            "impact": normalize_historical_event_impact(self.impact).value,
            "sentiment": normalize_historical_event_sentiment(self.sentiment).value,
            "actual_value": self.actual_value,
            "forecast_value": self.forecast_value,
            "previous_value": self.previous_value,
            "surprise": self.calculated_surprise,
            "unit": self.unit.strip(),
            "source": self.source.strip(),
            "provider_id": self.provider_id.strip(),
            "url": self.url.strip(),
            "description": self.description.strip(),
            "relevance_score": float(self.relevance_score),
            "has_actual_forecast": self.has_actual_forecast,
            "high_importance": self.high_importance,
            "raw_payload": dict(self.raw_payload),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class EconomicCalendarProviderResult:
    """Economic calendar provider result."""

    success: bool
    events: list[EconomicCalendarEvent] = field(default_factory=list)
    query: EconomicCalendarQuery | None = None
    message: str = ""
    provider_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_economic_calendar_events(self.events)

        if self.query is not None and not isinstance(self.query, EconomicCalendarQuery):
            raise ValueError("Query must be EconomicCalendarQuery.")

        validate_string(self.message, "Message")
        validate_string(self.provider_id, "Provider ID")
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether result failed."""
        return not self.success

    @property
    def event_count(self) -> int:
        """Return event count."""
        return len(self.events)

    @property
    def high_importance_count(self) -> int:
        """Return high importance count."""
        return len([event for event in self.events if event.high_importance])

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "failed": self.failed,
            "events": [event.to_dict() for event in self.events],
            "event_count": self.event_count,
            "high_importance_count": self.high_importance_count,
            "query": self.query.to_dict() if self.query is not None else None,
            "message": self.message.strip(),
            "provider_id": self.provider_id.strip(),
            "metadata": dict(self.metadata),
        }


def normalize_economic_calendar_category(
    value: EconomicCalendarEventCategory | str,
) -> EconomicCalendarEventCategory:
    """Normalize economic calendar category."""
    if isinstance(value, EconomicCalendarEventCategory):
        return value

    normalized = validate_non_empty_string(value, "Economic calendar category").lower()

    try:
        return EconomicCalendarEventCategory(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in EconomicCalendarEventCategory)
        raise ValueError(
            f"Invalid economic calendar category '{value}'. Valid categories: {valid}.",
        ) from exc


def normalize_economic_calendar_importance(
    value: EconomicCalendarImportance | str,
) -> EconomicCalendarImportance:
    """Normalize economic calendar importance."""
    if isinstance(value, EconomicCalendarImportance):
        return value

    normalized = validate_non_empty_string(value, "Economic calendar importance").lower()

    try:
        return EconomicCalendarImportance(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in EconomicCalendarImportance)
        raise ValueError(
            f"Invalid economic calendar importance '{value}'. Valid importance values: {valid}.",
        ) from exc


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_number_like(value: int | float, field_name: str) -> float:
    """Validate number-like value."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    return float(value)


def validate_economic_calendar_categories(
    categories: list[EconomicCalendarEventCategory | str],
) -> list[EconomicCalendarEventCategory | str]:
    """Validate economic calendar categories."""
    if not isinstance(categories, list):
        raise ValueError("Categories must be a list.")

    for category in categories:
        normalize_economic_calendar_category(category)

    return categories


def validate_economic_calendar_events(
    events: list[EconomicCalendarEvent],
) -> list[EconomicCalendarEvent]:
    """Validate economic calendar events."""
    if not isinstance(events, list):
        raise ValueError("Events must be a list.")

    for event in events:
        if not isinstance(event, EconomicCalendarEvent):
            raise ValueError("Events must contain EconomicCalendarEvent objects.")

    return events


def build_economic_calendar_query(
    *,
    symbol: str = "",
    countries: list[str] | None = None,
    currencies: list[str] | None = None,
    categories: list[EconomicCalendarEventCategory | str] | None = None,
    min_importance: EconomicCalendarImportance | str = EconomicCalendarImportance.LOW,
    start_date: str = "",
    end_date: str = "",
    keywords: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EconomicCalendarQuery:
    """Build economic calendar query."""
    return EconomicCalendarQuery(
        symbol=symbol,
        countries=countries or [],
        currencies=currencies or [],
        categories=categories or [],
        min_importance=min_importance,
        start_date=start_date,
        end_date=end_date,
        keywords=keywords or [],
        metadata=metadata or {},
    )


def build_economic_calendar_event(
    *,
    event_id: str,
    timestamp: str,
    title: str,
    country: str = "",
    currency: str = "",
    category: EconomicCalendarEventCategory | str = EconomicCalendarEventCategory.UNKNOWN,
    importance: EconomicCalendarImportance | str = EconomicCalendarImportance.UNKNOWN,
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN,
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN,
    actual_value: float | None = None,
    forecast_value: float | None = None,
    previous_value: float | None = None,
    surprise: float | None = None,
    unit: str = "",
    source: str = "",
    provider_id: str = "",
    url: str = "",
    description: str = "",
    relevance_score: float = 0.0,
    raw_payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> EconomicCalendarEvent:
    """Build economic calendar event."""
    return EconomicCalendarEvent(
        event_id=event_id,
        timestamp=timestamp,
        title=title,
        country=country,
        currency=currency,
        category=category,
        importance=importance,
        impact=impact,
        sentiment=sentiment,
        actual_value=actual_value,
        forecast_value=forecast_value,
        previous_value=previous_value,
        surprise=surprise,
        unit=unit,
        source=source,
        provider_id=provider_id,
        url=url,
        description=description,
        relevance_score=relevance_score,
        raw_payload=raw_payload or {},
        metadata=metadata or {},
    )


def build_economic_calendar_provider_config(
    *,
    provider_id: str,
    name: str,
    base_url: str = "",
    status: str = "inactive",
    metadata: dict[str, Any] | None = None,
) -> NewsProviderConfig:
    """Build economic calendar provider config."""
    return build_news_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=NewsProviderType.ECONOMIC_CALENDAR,
        base_url=base_url,
        status=status,
        capabilities=[
            NewsProviderCapability.ECONOMIC_CALENDAR,
            NewsProviderCapability.MACRO_EVENTS,
            NewsProviderCapability.HISTORICAL_NEWS,
            NewsProviderCapability.COUNTRY_FILTERING,
            NewsProviderCapability.CURRENCY_FILTERING,
        ],
        metadata=metadata or {},
    )


def build_economic_calendar_provider_result(
    *,
    success: bool,
    events: list[EconomicCalendarEvent] | None = None,
    query: EconomicCalendarQuery | None = None,
    message: str = "",
    provider_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> EconomicCalendarProviderResult:
    """Build economic calendar provider result."""
    return EconomicCalendarProviderResult(
        success=success,
        events=events or [],
        query=query,
        message=message,
        provider_id=provider_id,
        metadata=metadata or {},
    )


def infer_impact_from_importance(
    importance: EconomicCalendarImportance | str,
) -> HistoricalEventImpact:
    """Infer historical event impact from calendar importance."""
    normalized = normalize_economic_calendar_importance(importance)

    mapping = {
        EconomicCalendarImportance.LOW: HistoricalEventImpact.LOW,
        EconomicCalendarImportance.MEDIUM: HistoricalEventImpact.MEDIUM,
        EconomicCalendarImportance.HIGH: HistoricalEventImpact.HIGH,
        EconomicCalendarImportance.CRITICAL: HistoricalEventImpact.CRITICAL,
        EconomicCalendarImportance.UNKNOWN: HistoricalEventImpact.UNKNOWN,
    }

    return mapping[normalized]


def infer_sentiment_from_surprise(
    surprise: float | None,
    *,
    positive_surprise_is_bullish: bool = True,
    threshold: float = 0.0,
) -> HistoricalEventSentiment:
    """Infer sentiment from economic surprise."""
    validate_non_negative_float(threshold, "Threshold")

    if surprise is None:
        return HistoricalEventSentiment.UNKNOWN

    if surprise > threshold:
        return (
            HistoricalEventSentiment.BULLISH
            if positive_surprise_is_bullish
            else HistoricalEventSentiment.BEARISH
        )

    if surprise < -threshold:
        return (
            HistoricalEventSentiment.BEARISH
            if positive_surprise_is_bullish
            else HistoricalEventSentiment.BULLISH
        )

    return HistoricalEventSentiment.NEUTRAL


def economic_calendar_event_to_news_record(
    event: EconomicCalendarEvent,
    *,
    symbol: str = "",
) -> NewsEventRecord:
    """Convert economic calendar event to news event record."""
    if not isinstance(event, EconomicCalendarEvent):
        raise ValueError("Event must be EconomicCalendarEvent.")

    return build_news_event_record(
        event_id=event.event_id,
        timestamp=event.timestamp,
        title=event.title,
        event_type=HistoricalEventType.ECONOMIC_CALENDAR,
        symbol=symbol,
        impact=normalize_historical_event_impact(event.impact),
        sentiment=normalize_historical_event_sentiment(event.sentiment),
        source=event.source,
        provider_id=event.provider_id,
        url=event.url,
        description=event.description,
        country=event.country,
        currency=event.currency,
        relevance_score=event.relevance_score,
        raw_payload=event.to_dict(),
        metadata={
            "category": normalize_economic_calendar_category(event.category).value,
            "importance": normalize_economic_calendar_importance(event.importance).value,
            "actual_value": event.actual_value,
            "forecast_value": event.forecast_value,
            "previous_value": event.previous_value,
            "surprise": event.calculated_surprise,
            "unit": event.unit,
        },
    )


def economic_calendar_events_to_news_records(
    events: list[EconomicCalendarEvent],
    *,
    symbol: str = "",
) -> list[NewsEventRecord]:
    """Convert economic calendar events to news records."""
    validate_economic_calendar_events(events)

    return [
        economic_calendar_event_to_news_record(
            event,
            symbol=symbol,
        )
        for event in events
    ]


def economic_calendar_result_to_news_provider_result(
    result: EconomicCalendarProviderResult,
    *,
    symbol: str = "",
) -> NewsProviderResult:
    """Convert economic calendar result to generic news provider result."""
    if not isinstance(result, EconomicCalendarProviderResult):
        raise ValueError("Result must be EconomicCalendarProviderResult.")

    records = economic_calendar_events_to_news_records(
        result.events,
        symbol=symbol,
    )

    return build_news_provider_result(
        success=result.success,
        records=records,
        message=result.message,
        provider_id=result.provider_id,
        metadata={
            **result.metadata,
            "source_result_type": "economic_calendar",
            "event_count": result.event_count,
        },
    )


def filter_economic_calendar_events(
    events: list[EconomicCalendarEvent],
    *,
    query: EconomicCalendarQuery,
) -> list[EconomicCalendarEvent]:
    """Filter economic calendar events using query."""
    validate_economic_calendar_events(events)

    if not isinstance(query, EconomicCalendarQuery):
        raise ValueError("Query must be EconomicCalendarQuery.")

    query_payload = query.to_dict()
    countries = set(query_payload["countries"])
    currencies = set(query_payload["currencies"])
    categories = set(query_payload["categories"])
    keywords = set(query_payload["keywords"])

    importance_rank = {
        EconomicCalendarImportance.UNKNOWN.value: 0,
        EconomicCalendarImportance.LOW.value: 1,
        EconomicCalendarImportance.MEDIUM.value: 2,
        EconomicCalendarImportance.HIGH.value: 3,
        EconomicCalendarImportance.CRITICAL.value: 4,
    }
    min_rank = importance_rank[query_payload["min_importance"]]

    filtered: list[EconomicCalendarEvent] = []

    for event in events:
        event_payload = event.to_dict()

        if countries and event_payload["country"] not in countries:
            continue

        if currencies and event_payload["currency"] not in currencies:
            continue

        if categories and event_payload["category"] not in categories:
            continue

        if importance_rank[event_payload["importance"]] < min_rank:
            continue

        if keywords:
            title_description = f"{event_payload['title']} {event_payload['description']}".lower()

            if not any(keyword in title_description for keyword in keywords):
                continue

        filtered.append(event)

    return filtered