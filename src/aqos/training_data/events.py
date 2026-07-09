"""
AQOS historical news and macro event training contracts.

This module defines historical macro/news event rows, event datasets,
impact metadata, sentiment metadata, and model-ready event structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.training_data.base import (
    TrainingDataConfig,
    TrainingDataHealth,
    TrainingDataStatus,
    build_training_data_config,
    build_training_data_health,
    normalize_training_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_number,
    validate_string,
)


class HistoricalEventType(str, Enum):
    """Supported historical event types."""

    NEWS = "news"
    ECONOMIC_CALENDAR = "economic_calendar"
    CENTRAL_BANK = "central_bank"
    GEOPOLITICAL = "geopolitical"
    EARNINGS = "earnings"
    CRYPTO = "crypto"
    MARKET_STRUCTURE = "market_structure"
    UNKNOWN = "unknown"


class HistoricalEventImpact(str, Enum):
    """Supported historical event impact levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class HistoricalEventSentiment(str, Enum):
    """Supported historical event sentiment values."""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HistoricalEventRow:
    """Historical news or macro event row."""

    event_id: str
    timestamp: str
    event_type: HistoricalEventType | str
    title: str
    symbol: str = ""
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN
    source: str = ""
    description: str = ""
    actual_value: float | None = None
    forecast_value: float | None = None
    previous_value: float | None = None
    surprise: float | None = None
    relevance_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.event_id, "Event ID")
        validate_non_empty_string(self.timestamp, "Timestamp")
        normalize_historical_event_type(self.event_type)
        validate_non_empty_string(self.title, "Title")
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_training_symbol(self.symbol)

        normalize_historical_event_impact(self.impact)
        normalize_historical_event_sentiment(self.sentiment)
        validate_string(self.source, "Source")
        validate_string(self.description, "Description")

        if self.actual_value is not None:
            validate_number(self.actual_value, "Actual value")

        if self.forecast_value is not None:
            validate_number(self.forecast_value, "Forecast value")

        if self.previous_value is not None:
            validate_number(self.previous_value, "Previous value")

        if self.surprise is not None:
            validate_number(self.surprise, "Surprise")

        validate_score(self.relevance_score, "Relevance score")
        validate_metadata(self.metadata, "Metadata")

    @property
    def has_numeric_values(self) -> bool:
        """Return whether event has numeric economic values."""
        return any(
            value is not None
            for value in [
                self.actual_value,
                self.forecast_value,
                self.previous_value,
                self.surprise,
            ]
        )

    @property
    def high_impact(self) -> bool:
        """Return whether event is high impact."""
        return normalize_historical_event_impact(self.impact) in {
            HistoricalEventImpact.HIGH,
            HistoricalEventImpact.CRITICAL,
        }

    @property
    def directional(self) -> bool:
        """Return whether event has directional sentiment."""
        return normalize_historical_event_sentiment(self.sentiment) in {
            HistoricalEventSentiment.BULLISH,
            HistoricalEventSentiment.BEARISH,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert historical event row to dictionary."""
        return {
            "event_id": self.event_id.strip(),
            "timestamp": self.timestamp.strip(),
            "event_type": normalize_historical_event_type(self.event_type).value,
            "title": self.title.strip(),
            "symbol": normalize_training_symbol(self.symbol) if self.symbol.strip() else "",
            "impact": normalize_historical_event_impact(self.impact).value,
            "sentiment": normalize_historical_event_sentiment(self.sentiment).value,
            "source": self.source.strip(),
            "description": self.description.strip(),
            "actual_value": self.actual_value,
            "forecast_value": self.forecast_value,
            "previous_value": self.previous_value,
            "surprise": self.surprise,
            "relevance_score": float(self.relevance_score),
            "has_numeric_values": self.has_numeric_values,
            "high_impact": self.high_impact,
            "directional": self.directional,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HistoricalEventDataset:
    """Historical event dataset."""

    config: TrainingDataConfig
    events: list[HistoricalEventRow] = field(default_factory=list)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.config, TrainingDataConfig):
            raise ValueError("Config must be TrainingDataConfig.")

        validate_historical_event_rows(self.events)
        validate_string(self.source, "Source")
        validate_metadata(self.metadata, "Metadata")

    @property
    def dataset_id(self) -> str:
        """Return dataset ID."""
        return self.config.dataset_id

    @property
    def symbol(self) -> str:
        """Return dataset symbol."""
        return normalize_training_symbol(self.config.symbol)

    @property
    def event_count(self) -> int:
        """Return event count."""
        return len(self.events)

    @property
    def empty(self) -> bool:
        """Return whether dataset is empty."""
        return self.event_count == 0

    @property
    def high_impact_count(self) -> int:
        """Return high impact event count."""
        return len([event for event in self.events if event.high_impact])

    @property
    def directional_count(self) -> int:
        """Return directional event count."""
        return len([event for event in self.events if event.directional])

    @property
    def first_timestamp(self) -> str:
        """Return first timestamp."""
        return self.events[0].timestamp if self.events else ""

    @property
    def last_timestamp(self) -> str:
        """Return last timestamp."""
        return self.events[-1].timestamp if self.events else ""

    def health(self) -> TrainingDataHealth:
        """Build event dataset health."""
        status = TrainingDataStatus.READY if self.events else TrainingDataStatus.EMPTY

        return build_training_data_health(
            dataset_id=self.dataset_id,
            status=status,
            event_count=self.event_count,
            metadata={
                "symbol": self.symbol,
                "source": self.source,
                "high_impact_count": self.high_impact_count,
                "directional_count": self.directional_count,
            },
        )

    def to_events(self) -> list[dict[str, Any]]:
        """Convert events to dictionaries."""
        return [event.to_dict() for event in self.events]

    def to_dict(self) -> dict[str, Any]:
        """Convert dataset to dictionary."""
        return {
            "config": self.config.to_dict(),
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "source": self.source.strip(),
            "events": self.to_events(),
            "event_count": self.event_count,
            "empty": self.empty,
            "high_impact_count": self.high_impact_count,
            "directional_count": self.directional_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "health": self.health().to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HistoricalEventSummary:
    """Historical event dataset summary."""

    dataset_id: str
    symbol: str
    event_count: int = 0
    high_impact_count: int = 0
    directional_count: int = 0
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    first_timestamp: str = ""
    last_timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        validate_non_negative_integer(self.event_count, "Event count")
        validate_non_negative_integer(self.high_impact_count, "High impact count")
        validate_non_negative_integer(self.directional_count, "Directional count")
        validate_non_negative_integer(self.bullish_count, "Bullish count")
        validate_non_negative_integer(self.bearish_count, "Bearish count")
        validate_non_negative_integer(self.neutral_count, "Neutral count")
        validate_string(self.first_timestamp, "First timestamp")
        validate_string(self.last_timestamp, "Last timestamp")
        validate_metadata(self.metadata, "Metadata")

    @property
    def has_events(self) -> bool:
        """Return whether summary has events."""
        return self.event_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "event_count": self.event_count,
            "high_impact_count": self.high_impact_count,
            "directional_count": self.directional_count,
            "bullish_count": self.bullish_count,
            "bearish_count": self.bearish_count,
            "neutral_count": self.neutral_count,
            "first_timestamp": self.first_timestamp.strip(),
            "last_timestamp": self.last_timestamp.strip(),
            "has_events": self.has_events,
            "metadata": dict(self.metadata),
        }


def validate_score(value: int | float, field_name: str) -> float:
    """Validate score between 0 and 1."""
    score = validate_number(value, field_name)

    if score < 0 or score > 1:
        raise ValueError(f"{field_name} must be between 0 and 1.")

    return score


def normalize_historical_event_type(
    event_type: HistoricalEventType | str,
) -> HistoricalEventType:
    """Normalize historical event type."""
    if isinstance(event_type, HistoricalEventType):
        return event_type

    normalized = validate_non_empty_string(event_type, "Historical event type").lower()

    try:
        return HistoricalEventType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HistoricalEventType)
        raise ValueError(
            f"Invalid historical event type '{event_type}'. Valid event types: {valid}.",
        ) from exc


def normalize_historical_event_impact(
    impact: HistoricalEventImpact | str,
) -> HistoricalEventImpact:
    """Normalize historical event impact."""
    if isinstance(impact, HistoricalEventImpact):
        return impact

    normalized = validate_non_empty_string(impact, "Historical event impact").lower()

    try:
        return HistoricalEventImpact(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HistoricalEventImpact)
        raise ValueError(
            f"Invalid historical event impact '{impact}'. Valid impacts: {valid}.",
        ) from exc


def normalize_historical_event_sentiment(
    sentiment: HistoricalEventSentiment | str,
) -> HistoricalEventSentiment:
    """Normalize historical event sentiment."""
    if isinstance(sentiment, HistoricalEventSentiment):
        return sentiment

    normalized = validate_non_empty_string(sentiment, "Historical event sentiment").lower()

    try:
        return HistoricalEventSentiment(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HistoricalEventSentiment)
        raise ValueError(
            f"Invalid historical event sentiment '{sentiment}'. Valid sentiments: {valid}.",
        ) from exc


def validate_historical_event_rows(
    events: list[HistoricalEventRow],
) -> list[HistoricalEventRow]:
    """Validate historical event rows."""
    if not isinstance(events, list):
        raise ValueError("Events must be a list.")

    for event in events:
        if not isinstance(event, HistoricalEventRow):
            raise ValueError("Events must contain HistoricalEventRow objects.")

    return events


def validate_raw_event_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate raw event rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        validate_metadata(row, "Event row")

    return rows


def build_historical_event_row(
    *,
    event_id: str,
    timestamp: str,
    event_type: HistoricalEventType | str,
    title: str,
    symbol: str = "",
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN,
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN,
    source: str = "",
    description: str = "",
    actual_value: float | None = None,
    forecast_value: float | None = None,
    previous_value: float | None = None,
    surprise: float | None = None,
    relevance_score: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> HistoricalEventRow:
    """Build historical event row."""
    return HistoricalEventRow(
        event_id=event_id,
        timestamp=timestamp,
        event_type=event_type,
        title=title,
        symbol=symbol,
        impact=impact,
        sentiment=sentiment,
        source=source,
        description=description,
        actual_value=actual_value,
        forecast_value=forecast_value,
        previous_value=previous_value,
        surprise=surprise,
        relevance_score=relevance_score,
        metadata=metadata or {},
    )


def raw_row_to_historical_event_row(
    row: dict[str, Any],
    *,
    symbol: str = "",
) -> HistoricalEventRow:
    """Convert raw event row to historical event row."""
    validate_metadata(row, "Event row")

    return build_historical_event_row(
        event_id=str(row["event_id"]),
        timestamp=str(row["timestamp"]),
        event_type=str(row.get("event_type", HistoricalEventType.UNKNOWN.value)),
        title=str(row["title"]),
        symbol=str(row.get("symbol", symbol)),
        impact=str(row.get("impact", HistoricalEventImpact.UNKNOWN.value)),
        sentiment=str(row.get("sentiment", HistoricalEventSentiment.UNKNOWN.value)),
        source=str(row.get("source", "")),
        description=str(row.get("description", "")),
        actual_value=row.get("actual_value"),
        forecast_value=row.get("forecast_value"),
        previous_value=row.get("previous_value"),
        surprise=row.get("surprise"),
        relevance_score=float(row.get("relevance_score", 0.0) or 0.0),
        metadata=dict(row.get("metadata", {})),
    )


def raw_rows_to_historical_event_rows(
    rows: list[dict[str, Any]],
    *,
    symbol: str = "",
) -> list[HistoricalEventRow]:
    """Convert raw event rows to historical event rows."""
    validate_raw_event_rows(rows)

    return [
        raw_row_to_historical_event_row(
            row,
            symbol=symbol,
        )
        for row in rows
    ]


def build_historical_event_dataset(
    *,
    dataset_id: str,
    symbol: str,
    events: list[HistoricalEventRow] | None = None,
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> HistoricalEventDataset:
    """Build historical event dataset."""
    config = build_training_data_config(
        dataset_id=dataset_id,
        symbol=symbol,
    )

    return HistoricalEventDataset(
        config=config,
        events=events or [],
        source=source,
        metadata=metadata or {},
    )


def raw_rows_to_historical_event_dataset(
    *,
    dataset_id: str,
    symbol: str,
    rows: list[dict[str, Any]],
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> HistoricalEventDataset:
    """Convert raw event rows to event dataset."""
    events = raw_rows_to_historical_event_rows(
        rows,
        symbol=symbol,
    )

    return build_historical_event_dataset(
        dataset_id=dataset_id,
        symbol=symbol,
        events=events,
        source=source,
        metadata=metadata or {},
    )


def summarize_historical_event_dataset(
    dataset: HistoricalEventDataset,
) -> HistoricalEventSummary:
    """Summarize historical event dataset."""
    if not isinstance(dataset, HistoricalEventDataset):
        raise ValueError("Dataset must be HistoricalEventDataset.")

    bullish_count = len(
        [
            event
            for event in dataset.events
            if normalize_historical_event_sentiment(event.sentiment)
            == HistoricalEventSentiment.BULLISH
        ]
    )
    bearish_count = len(
        [
            event
            for event in dataset.events
            if normalize_historical_event_sentiment(event.sentiment)
            == HistoricalEventSentiment.BEARISH
        ]
    )
    neutral_count = len(
        [
            event
            for event in dataset.events
            if normalize_historical_event_sentiment(event.sentiment)
            == HistoricalEventSentiment.NEUTRAL
        ]
    )

    return HistoricalEventSummary(
        dataset_id=dataset.dataset_id,
        symbol=dataset.symbol,
        event_count=dataset.event_count,
        high_impact_count=dataset.high_impact_count,
        directional_count=dataset.directional_count,
        bullish_count=bullish_count,
        bearish_count=bearish_count,
        neutral_count=neutral_count,
        first_timestamp=dataset.first_timestamp,
        last_timestamp=dataset.last_timestamp,
        metadata={
            "source": dataset.source,
        },
    )


def filter_historical_events_by_impact(
    dataset: HistoricalEventDataset,
    *,
    impact: HistoricalEventImpact | str,
) -> HistoricalEventDataset:
    """Filter historical events by impact."""
    if not isinstance(dataset, HistoricalEventDataset):
        raise ValueError("Dataset must be HistoricalEventDataset.")

    normalized_impact = normalize_historical_event_impact(impact)

    return HistoricalEventDataset(
        config=dataset.config,
        events=[
            event
            for event in dataset.events
            if normalize_historical_event_impact(event.impact) == normalized_impact
        ],
        source=dataset.source,
        metadata={
            **dataset.metadata,
            "filtered_by_impact": normalized_impact.value,
        },
    )


def filter_historical_events_by_sentiment(
    dataset: HistoricalEventDataset,
    *,
    sentiment: HistoricalEventSentiment | str,
) -> HistoricalEventDataset:
    """Filter historical events by sentiment."""
    if not isinstance(dataset, HistoricalEventDataset):
        raise ValueError("Dataset must be HistoricalEventDataset.")

    normalized_sentiment = normalize_historical_event_sentiment(sentiment)

    return HistoricalEventDataset(
        config=dataset.config,
        events=[
            event
            for event in dataset.events
            if normalize_historical_event_sentiment(event.sentiment)
            == normalized_sentiment
        ],
        source=dataset.source,
        metadata={
            **dataset.metadata,
            "filtered_by_sentiment": normalized_sentiment.value,
        },
    )


def event_row_to_feature_dict(event: HistoricalEventRow) -> dict[str, Any]:
    """Convert historical event row to model-ready feature dictionary."""
    if not isinstance(event, HistoricalEventRow):
        raise ValueError("Event must be HistoricalEventRow.")

    impact = normalize_historical_event_impact(event.impact)
    sentiment = normalize_historical_event_sentiment(event.sentiment)

    impact_score = {
        HistoricalEventImpact.LOW: 0.25,
        HistoricalEventImpact.MEDIUM: 0.5,
        HistoricalEventImpact.HIGH: 0.75,
        HistoricalEventImpact.CRITICAL: 1.0,
        HistoricalEventImpact.UNKNOWN: 0.0,
    }[impact]

    sentiment_score = {
        HistoricalEventSentiment.BULLISH: 1.0,
        HistoricalEventSentiment.BEARISH: -1.0,
        HistoricalEventSentiment.NEUTRAL: 0.0,
        HistoricalEventSentiment.MIXED: 0.0,
        HistoricalEventSentiment.UNKNOWN: 0.0,
    }[sentiment]

    return {
        "event_id": event.event_id.strip(),
        "event_timestamp": event.timestamp.strip(),
        "event_type": normalize_historical_event_type(event.event_type).value,
        "event_impact": impact.value,
        "event_sentiment": sentiment.value,
        "event_impact_score": impact_score,
        "event_sentiment_score": sentiment_score,
        "event_relevance_score": float(event.relevance_score),
        "event_has_numeric_values": int(event.has_numeric_values),
        "event_high_impact": int(event.high_impact),
        "event_directional": int(event.directional),
        "event_surprise": float(event.surprise) if event.surprise is not None else 0.0,
    }


def event_dataset_to_feature_rows(
    dataset: HistoricalEventDataset,
) -> list[dict[str, Any]]:
    """Convert event dataset into model-ready event feature rows."""
    if not isinstance(dataset, HistoricalEventDataset):
        raise ValueError("Dataset must be HistoricalEventDataset.")

    return [event_row_to_feature_dict(event) for event in dataset.events]