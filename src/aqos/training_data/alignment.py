"""
AQOS news-to-candle alignment engine.

This module aligns historical news/macro events with historical OHLCV candles
so AQOS can train models on price action plus event context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from aqos.training_data.base import (
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_positive_integer,
    validate_string,
)
from aqos.training_data.events import (
    HistoricalEventDataset,
    HistoricalEventImpact,
    HistoricalEventRow,
    event_row_to_feature_dict,
    normalize_historical_event_impact,
)
from aqos.training_data.ohlcv import (
    HistoricalOhlcvDataset,
    HistoricalOhlcvRow,
    ohlcv_dataset_to_feature_rows,
)


class EventAlignmentMode(str, Enum):
    """Supported event alignment modes."""

    BEFORE_OR_AT = "before_or_at"
    AFTER_OR_AT = "after_or_at"
    NEAREST = "nearest"
    WINDOW = "window"


@dataclass(frozen=True)
class EventAlignmentConfig:
    """Event alignment configuration."""

    mode: EventAlignmentMode | str = EventAlignmentMode.BEFORE_OR_AT
    lookback_minutes: int = 240
    lookahead_minutes: int = 0
    max_events_per_candle: int = 5
    include_low_impact: bool = True
    include_medium_impact: bool = True
    include_high_impact: bool = True
    include_critical_impact: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_event_alignment_mode(self.mode)
        validate_non_negative_integer(self.lookback_minutes, "Lookback minutes")
        validate_non_negative_integer(self.lookahead_minutes, "Lookahead minutes")
        validate_positive_integer(self.max_events_per_candle, "Max events per candle")

        for field_name, value in [
            ("Include low impact", self.include_low_impact),
            ("Include medium impact", self.include_medium_impact),
            ("Include high impact", self.include_high_impact),
            ("Include critical impact", self.include_critical_impact),
        ]:
            if not isinstance(value, bool):
                raise ValueError(f"{field_name} must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    def impact_allowed(self, impact: HistoricalEventImpact | str) -> bool:
        """Return whether impact is allowed."""
        normalized = normalize_historical_event_impact(impact)

        return {
            HistoricalEventImpact.LOW: self.include_low_impact,
            HistoricalEventImpact.MEDIUM: self.include_medium_impact,
            HistoricalEventImpact.HIGH: self.include_high_impact,
            HistoricalEventImpact.CRITICAL: self.include_critical_impact,
            HistoricalEventImpact.UNKNOWN: True,
        }[normalized]

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "mode": normalize_event_alignment_mode(self.mode).value,
            "lookback_minutes": self.lookback_minutes,
            "lookahead_minutes": self.lookahead_minutes,
            "max_events_per_candle": self.max_events_per_candle,
            "include_low_impact": self.include_low_impact,
            "include_medium_impact": self.include_medium_impact,
            "include_high_impact": self.include_high_impact,
            "include_critical_impact": self.include_critical_impact,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class AlignedEvent:
    """Event aligned to a candle."""

    candle_timestamp: str
    event: HistoricalEventRow
    minutes_from_candle: int
    alignment_mode: EventAlignmentMode | str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.candle_timestamp, "Candle timestamp")

        if not isinstance(self.event, HistoricalEventRow):
            raise ValueError("Event must be HistoricalEventRow.")

        if isinstance(self.minutes_from_candle, bool) or not isinstance(self.minutes_from_candle, int):
            raise ValueError("Minutes from candle must be an integer.")

        normalize_event_alignment_mode(self.alignment_mode)
        validate_metadata(self.metadata, "Metadata")

    @property
    def event_id(self) -> str:
        """Return event ID."""
        return self.event.event_id

    @property
    def event_timestamp(self) -> str:
        """Return event timestamp."""
        return self.event.timestamp

    @property
    def before_candle(self) -> bool:
        """Return whether event happened before candle."""
        return self.minutes_from_candle <= 0

    @property
    def after_candle(self) -> bool:
        """Return whether event happened after candle."""
        return self.minutes_from_candle >= 0

    def to_dict(self) -> dict[str, Any]:
        """Convert aligned event to dictionary."""
        return {
            "candle_timestamp": self.candle_timestamp.strip(),
            "event_id": self.event_id.strip(),
            "event_timestamp": self.event_timestamp.strip(),
            "minutes_from_candle": self.minutes_from_candle,
            "before_candle": self.before_candle,
            "after_candle": self.after_candle,
            "alignment_mode": normalize_event_alignment_mode(self.alignment_mode).value,
            "event": self.event.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CandleEventAlignmentRow:
    """OHLCV candle with aligned events."""

    candle: HistoricalOhlcvRow
    aligned_events: list[AlignedEvent] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.candle, HistoricalOhlcvRow):
            raise ValueError("Candle must be HistoricalOhlcvRow.")

        validate_aligned_events(self.aligned_events)
        validate_metadata(self.metadata, "Metadata")

    @property
    def timestamp(self) -> str:
        """Return candle timestamp."""
        return self.candle.timestamp

    @property
    def event_count(self) -> int:
        """Return aligned event count."""
        return len(self.aligned_events)

    @property
    def has_events(self) -> bool:
        """Return whether candle has aligned events."""
        return self.event_count > 0

    @property
    def high_impact_event_count(self) -> int:
        """Return high impact aligned event count."""
        return len([item for item in self.aligned_events if item.event.high_impact])

    def to_dict(self) -> dict[str, Any]:
        """Convert aligned candle row to dictionary."""
        return {
            "timestamp": self.timestamp,
            "candle": self.candle.to_dict(),
            "aligned_events": [item.to_dict() for item in self.aligned_events],
            "event_count": self.event_count,
            "has_events": self.has_events,
            "high_impact_event_count": self.high_impact_event_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CandleEventAlignmentDataset:
    """Dataset containing candles with aligned events."""

    dataset_id: str
    symbol: str
    rows: list[CandleEventAlignmentRow] = field(default_factory=list)
    config: EventAlignmentConfig = field(default_factory=EventAlignmentConfig)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        validate_non_empty_string(self.symbol, "Symbol")
        validate_candle_event_alignment_rows(self.rows)

        if not isinstance(self.config, EventAlignmentConfig):
            raise ValueError("Config must be EventAlignmentConfig.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def row_count(self) -> int:
        """Return row count."""
        return len(self.rows)

    @property
    def event_count(self) -> int:
        """Return total aligned event count."""
        return sum(row.event_count for row in self.rows)

    @property
    def candles_with_events(self) -> int:
        """Return number of candles with at least one event."""
        return len([row for row in self.rows if row.has_events])

    @property
    def empty(self) -> bool:
        """Return whether alignment dataset is empty."""
        return self.row_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert alignment dataset to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": self.symbol.strip().upper(),
            "rows": [row.to_dict() for row in self.rows],
            "row_count": self.row_count,
            "event_count": self.event_count,
            "candles_with_events": self.candles_with_events,
            "empty": self.empty,
            "config": self.config.to_dict(),
            "metadata": dict(self.metadata),
        }


def normalize_event_alignment_mode(mode: EventAlignmentMode | str) -> EventAlignmentMode:
    """Normalize event alignment mode."""
    if isinstance(mode, EventAlignmentMode):
        return mode

    normalized = validate_non_empty_string(mode, "Event alignment mode").lower()

    try:
        return EventAlignmentMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in EventAlignmentMode)
        raise ValueError(
            f"Invalid event alignment mode '{mode}'. Valid modes: {valid}.",
        ) from exc


def parse_alignment_timestamp(value: str) -> datetime:
    """Parse ISO-like timestamp for alignment."""
    validate_non_empty_string(value, "Timestamp")

    normalized = value.strip().replace("Z", "+00:00")

    return datetime.fromisoformat(normalized)


def minutes_between_timestamps(start: str, end: str) -> int:
    """Return minute difference from start to end."""
    start_dt = parse_alignment_timestamp(start)
    end_dt = parse_alignment_timestamp(end)

    delta = end_dt - start_dt
    return int(delta.total_seconds() // 60)


def validate_aligned_events(events: list[AlignedEvent]) -> list[AlignedEvent]:
    """Validate aligned events."""
    if not isinstance(events, list):
        raise ValueError("Aligned events must be a list.")

    for event in events:
        if not isinstance(event, AlignedEvent):
            raise ValueError("Aligned events must contain AlignedEvent objects.")

    return events


def validate_candle_event_alignment_rows(
    rows: list[CandleEventAlignmentRow],
) -> list[CandleEventAlignmentRow]:
    """Validate candle event alignment rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        if not isinstance(row, CandleEventAlignmentRow):
            raise ValueError("Rows must contain CandleEventAlignmentRow objects.")

    return rows


def build_event_alignment_config(
    *,
    mode: EventAlignmentMode | str = EventAlignmentMode.BEFORE_OR_AT,
    lookback_minutes: int = 240,
    lookahead_minutes: int = 0,
    max_events_per_candle: int = 5,
    include_low_impact: bool = True,
    include_medium_impact: bool = True,
    include_high_impact: bool = True,
    include_critical_impact: bool = True,
    metadata: dict[str, Any] | None = None,
) -> EventAlignmentConfig:
    """Build event alignment config."""
    return EventAlignmentConfig(
        mode=mode,
        lookback_minutes=lookback_minutes,
        lookahead_minutes=lookahead_minutes,
        max_events_per_candle=max_events_per_candle,
        include_low_impact=include_low_impact,
        include_medium_impact=include_medium_impact,
        include_high_impact=include_high_impact,
        include_critical_impact=include_critical_impact,
        metadata=metadata or {},
    )


def event_is_within_alignment_window(
    *,
    candle_timestamp: str,
    event_timestamp: str,
    config: EventAlignmentConfig,
) -> bool:
    """Return whether event is inside candle alignment window."""
    if not isinstance(config, EventAlignmentConfig):
        raise ValueError("Config must be EventAlignmentConfig.")

    minutes_from_candle = minutes_between_timestamps(candle_timestamp, event_timestamp)
    mode = normalize_event_alignment_mode(config.mode)

    if mode == EventAlignmentMode.BEFORE_OR_AT:
        return -config.lookback_minutes <= minutes_from_candle <= 0

    if mode == EventAlignmentMode.AFTER_OR_AT:
        return 0 <= minutes_from_candle <= config.lookahead_minutes

    if mode == EventAlignmentMode.NEAREST:
        return (
            -config.lookback_minutes
            <= minutes_from_candle
            <= config.lookahead_minutes
        )

    if mode == EventAlignmentMode.WINDOW:
        return (
            -config.lookback_minutes
            <= minutes_from_candle
            <= config.lookahead_minutes
        )

    return False


def build_aligned_event(
    *,
    candle_timestamp: str,
    event: HistoricalEventRow,
    alignment_mode: EventAlignmentMode | str,
    metadata: dict[str, Any] | None = None,
) -> AlignedEvent:
    """Build aligned event."""
    return AlignedEvent(
        candle_timestamp=candle_timestamp,
        event=event,
        minutes_from_candle=minutes_between_timestamps(candle_timestamp, event.timestamp),
        alignment_mode=alignment_mode,
        metadata=metadata or {},
    )


def align_events_to_candle(
    *,
    candle: HistoricalOhlcvRow,
    events: list[HistoricalEventRow],
    config: EventAlignmentConfig | None = None,
) -> CandleEventAlignmentRow:
    """Align events to one OHLCV candle."""
    if not isinstance(candle, HistoricalOhlcvRow):
        raise ValueError("Candle must be HistoricalOhlcvRow.")

    config = config or EventAlignmentConfig()
    if not isinstance(config, EventAlignmentConfig):
        raise ValueError("Config must be EventAlignmentConfig.")

    if not isinstance(events, list):
        raise ValueError("Events must be a list.")

    aligned_events: list[AlignedEvent] = []

    for event in events:
        if not isinstance(event, HistoricalEventRow):
            raise ValueError("Events must contain HistoricalEventRow objects.")

        if not config.impact_allowed(event.impact):
            continue

        if event_is_within_alignment_window(
            candle_timestamp=candle.timestamp,
            event_timestamp=event.timestamp,
            config=config,
        ):
            aligned_events.append(
                build_aligned_event(
                    candle_timestamp=candle.timestamp,
                    event=event,
                    alignment_mode=config.mode,
                )
            )

    aligned_events = sorted(
        aligned_events,
        key=lambda item: (abs(item.minutes_from_candle), item.event.timestamp),
    )[: config.max_events_per_candle]

    return CandleEventAlignmentRow(
        candle=candle,
        aligned_events=aligned_events,
        metadata={
            "alignment_mode": normalize_event_alignment_mode(config.mode).value,
        },
    )


def align_event_dataset_to_ohlcv_dataset(
    *,
    ohlcv_dataset: HistoricalOhlcvDataset,
    event_dataset: HistoricalEventDataset,
    config: EventAlignmentConfig | None = None,
    dataset_id: str = "",
) -> CandleEventAlignmentDataset:
    """Align event dataset to OHLCV dataset."""
    if not isinstance(ohlcv_dataset, HistoricalOhlcvDataset):
        raise ValueError("OHLCV dataset must be HistoricalOhlcvDataset.")

    if not isinstance(event_dataset, HistoricalEventDataset):
        raise ValueError("Event dataset must be HistoricalEventDataset.")

    config = config or EventAlignmentConfig()
    if not isinstance(config, EventAlignmentConfig):
        raise ValueError("Config must be EventAlignmentConfig.")

    rows = [
        align_events_to_candle(
            candle=candle,
            events=event_dataset.events,
            config=config,
        )
        for candle in ohlcv_dataset.rows
    ]

    return CandleEventAlignmentDataset(
        dataset_id=dataset_id or f"{ohlcv_dataset.dataset_id}-aligned-events",
        symbol=ohlcv_dataset.symbol,
        rows=rows,
        config=config,
        metadata={
            "ohlcv_dataset_id": ohlcv_dataset.dataset_id,
            "event_dataset_id": event_dataset.dataset_id,
        },
    )


def aligned_row_to_training_features(
    row: CandleEventAlignmentRow,
) -> dict[str, Any]:
    """Convert aligned candle/event row to model-ready feature row."""
    if not isinstance(row, CandleEventAlignmentRow):
        raise ValueError("Row must be CandleEventAlignmentRow.")

    candle_features = {
        "timestamp": row.candle.timestamp,
        "open": float(row.candle.open),
        "high": float(row.candle.high),
        "low": float(row.candle.low),
        "close": float(row.candle.close),
        "volume": float(row.candle.volume),
        "body_size": row.candle.body_size,
        "range_size": row.candle.range_size,
        "typical_price": row.candle.typical_price,
        "bullish": int(row.candle.bullish),
        "bearish": int(row.candle.bearish),
    }

    event_features = aggregate_aligned_event_features(row.aligned_events)

    return {
        **candle_features,
        **event_features,
    }


def aggregate_aligned_event_features(events: list[AlignedEvent]) -> dict[str, Any]:
    """Aggregate aligned events into candle-level event features."""
    validate_aligned_events(events)

    event_count = len(events)
    high_impact_count = len([event for event in events if event.event.high_impact])
    directional_count = len([event for event in events if event.event.directional])

    impact_scores: list[float] = []
    sentiment_scores: list[float] = []
    relevance_scores: list[float] = []
    surprises: list[float] = []

    for aligned_event in events:
        features = event_row_to_feature_dict(aligned_event.event)
        impact_scores.append(float(features["event_impact_score"]))
        sentiment_scores.append(float(features["event_sentiment_score"]))
        relevance_scores.append(float(features["event_relevance_score"]))
        surprises.append(float(features["event_surprise"]))

    return {
        "aligned_event_count": event_count,
        "aligned_high_impact_event_count": high_impact_count,
        "aligned_directional_event_count": directional_count,
        "aligned_event_impact_score_max": max(impact_scores) if impact_scores else 0.0,
        "aligned_event_impact_score_avg": round(sum(impact_scores) / len(impact_scores), 10)
        if impact_scores
        else 0.0,
        "aligned_event_sentiment_score_sum": round(sum(sentiment_scores), 10)
        if sentiment_scores
        else 0.0,
        "aligned_event_sentiment_score_avg": round(sum(sentiment_scores) / len(sentiment_scores), 10)
        if sentiment_scores
        else 0.0,
        "aligned_event_relevance_score_max": max(relevance_scores) if relevance_scores else 0.0,
        "aligned_event_relevance_score_avg": round(sum(relevance_scores) / len(relevance_scores), 10)
        if relevance_scores
        else 0.0,
        "aligned_event_surprise_sum": round(sum(surprises), 10) if surprises else 0.0,
        "aligned_event_ids": [event.event_id for event in events],
    }


def alignment_dataset_to_training_rows(
    dataset: CandleEventAlignmentDataset,
) -> list[dict[str, Any]]:
    """Convert alignment dataset to training rows."""
    if not isinstance(dataset, CandleEventAlignmentDataset):
        raise ValueError("Dataset must be CandleEventAlignmentDataset.")

    return [aligned_row_to_training_features(row) for row in dataset.rows]