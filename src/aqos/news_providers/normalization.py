"""
AQOS macro event normalization pipeline.

This module converts news provider records, news feed articles, economic
calendar events, and sentiment-enriched records into AQOS historical event
rows that can be aligned with candles and used for model training.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsEventRecord,
    NewsProviderResult,
    normalize_news_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_score,
    validate_string,
)
from aqos.news_providers.economic_calendar import (
    EconomicCalendarProviderResult,
    economic_calendar_result_to_news_provider_result,
)
from aqos.news_providers.news_feed import (
    NewsFeedProviderResult,
    news_feed_result_to_news_provider_result,
)
from aqos.news_providers.sentiment import (
    SentimentClassificationResult,
    apply_sentiment_result_to_news_record,
)
from aqos.training_data.events import (
    HistoricalEventImpact,
    HistoricalEventRow,
    HistoricalEventSentiment,
    HistoricalEventType,
    build_historical_event_row,
    normalize_historical_event_impact,
    normalize_historical_event_sentiment,
    normalize_historical_event_type,
    validate_historical_event_rows,
)


class MacroEventNormalizationStatus(str, Enum):
    """Supported macro event normalization statuses."""

    READY = "ready"
    EMPTY = "empty"
    WARNING = "warning"
    ERROR = "error"


class MacroEventSourceKind(str, Enum):
    """Supported macro event source kinds."""

    NEWS_PROVIDER = "news_provider"
    NEWS_FEED = "news_feed"
    ECONOMIC_CALENDAR = "economic_calendar"
    SENTIMENT = "sentiment"
    MANUAL = "manual"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MacroEventNormalizationConfig:
    """Macro event normalization config."""

    dataset_id: str
    symbol: str = ""
    allowed_event_types: list[HistoricalEventType | str] = field(default_factory=list)
    allowed_impacts: list[HistoricalEventImpact | str] = field(default_factory=list)
    allowed_sentiments: list[HistoricalEventSentiment | str] = field(default_factory=list)
    allowed_countries: list[str] = field(default_factory=list)
    allowed_currencies: list[str] = field(default_factory=list)
    min_relevance_score: float = 0.0
    deduplicate: bool = True
    include_unknown_symbol: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_historical_event_type_filters(self.allowed_event_types)
        validate_historical_event_impact_filters(self.allowed_impacts)
        validate_historical_event_sentiment_filters(self.allowed_sentiments)
        validate_string_list(self.allowed_countries, "Allowed countries")
        validate_string_list(self.allowed_currencies, "Allowed currencies")
        validate_score(self.min_relevance_score, "Minimum relevance score")

        if not isinstance(self.deduplicate, bool):
            raise ValueError("Deduplicate must be a boolean.")

        if not isinstance(self.include_unknown_symbol, bool):
            raise ValueError("Include unknown symbol must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def has_filters(self) -> bool:
        """Return whether config has active filters."""
        return bool(
            self.symbol.strip()
            or self.allowed_event_types
            or self.allowed_impacts
            or self.allowed_sentiments
            or self.allowed_countries
            or self.allowed_currencies
            or self.min_relevance_score > 0
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "allowed_event_types": [
                normalize_historical_event_type(item).value
                for item in self.allowed_event_types
            ],
            "allowed_impacts": [
                normalize_historical_event_impact(item).value
                for item in self.allowed_impacts
            ],
            "allowed_sentiments": [
                normalize_historical_event_sentiment(item).value
                for item in self.allowed_sentiments
            ],
            "allowed_countries": [item.strip().upper() for item in self.allowed_countries],
            "allowed_currencies": [item.strip().upper() for item in self.allowed_currencies],
            "min_relevance_score": float(self.min_relevance_score),
            "deduplicate": self.deduplicate,
            "include_unknown_symbol": self.include_unknown_symbol,
            "has_filters": self.has_filters,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MacroEventNormalizationSummary:
    """Macro event normalization summary."""

    dataset_id: str
    status: MacroEventNormalizationStatus | str = MacroEventNormalizationStatus.EMPTY
    input_count: int = 0
    output_count: int = 0
    duplicate_count: int = 0
    dropped_count: int = 0
    high_impact_count: int = 0
    directional_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_macro_event_normalization_status(self.status)
        validate_non_negative_integer(self.input_count, "Input count")
        validate_non_negative_integer(self.output_count, "Output count")
        validate_non_negative_integer(self.duplicate_count, "Duplicate count")
        validate_non_negative_integer(self.dropped_count, "Dropped count")
        validate_non_negative_integer(self.high_impact_count, "High impact count")
        validate_non_negative_integer(self.directional_count, "Directional count")
        validate_metadata(self.metadata, "Metadata")

    @property
    def empty(self) -> bool:
        """Return whether summary is empty."""
        return self.output_count == 0

    @property
    def ready(self) -> bool:
        """Return whether summary is ready."""
        return normalize_macro_event_normalization_status(self.status) == MacroEventNormalizationStatus.READY

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "status": normalize_macro_event_normalization_status(self.status).value,
            "input_count": self.input_count,
            "output_count": self.output_count,
            "duplicate_count": self.duplicate_count,
            "dropped_count": self.dropped_count,
            "high_impact_count": self.high_impact_count,
            "directional_count": self.directional_count,
            "empty": self.empty,
            "ready": self.ready,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MacroEventNormalizationResult:
    """Macro event normalization result."""

    success: bool
    rows: list[HistoricalEventRow] = field(default_factory=list)
    summary: MacroEventNormalizationSummary | None = None
    message: str = ""
    issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_historical_event_rows(self.rows)

        if self.summary is not None and not isinstance(
            self.summary,
            MacroEventNormalizationSummary,
        ):
            raise ValueError("Summary must be MacroEventNormalizationSummary.")

        validate_string(self.message, "Message")
        validate_string_list(self.issues, "Issues")
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether normalization failed."""
        return not self.success

    @property
    def row_count(self) -> int:
        """Return row count."""
        return len(self.rows)

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "failed": self.failed,
            "rows": [row.to_dict() for row in self.rows],
            "row_count": self.row_count,
            "summary": self.summary.to_dict() if self.summary is not None else None,
            "message": self.message.strip(),
            "issues": [issue.strip() for issue in self.issues],
            "issue_count": self.issue_count,
            "metadata": dict(self.metadata),
        }


def normalize_macro_event_normalization_status(
    value: MacroEventNormalizationStatus | str,
) -> MacroEventNormalizationStatus:
    """Normalize macro event normalization status."""
    if isinstance(value, MacroEventNormalizationStatus):
        return value

    normalized = validate_non_empty_string(value, "Macro event normalization status").lower()

    try:
        return MacroEventNormalizationStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MacroEventNormalizationStatus)
        raise ValueError(
            f"Invalid macro event normalization status '{value}'. Valid statuses: {valid}.",
        ) from exc


def normalize_macro_event_source_kind(value: MacroEventSourceKind | str) -> MacroEventSourceKind:
    """Normalize macro event source kind."""
    if isinstance(value, MacroEventSourceKind):
        return value

    normalized = validate_non_empty_string(value, "Macro event source kind").lower()

    try:
        return MacroEventSourceKind(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MacroEventSourceKind)
        raise ValueError(
            f"Invalid macro event source kind '{value}'. Valid source kinds: {valid}.",
        ) from exc


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_historical_event_type_filters(
    values: list[HistoricalEventType | str],
) -> list[HistoricalEventType | str]:
    """Validate historical event type filters."""
    if not isinstance(values, list):
        raise ValueError("Allowed event types must be a list.")

    for value in values:
        normalize_historical_event_type(value)

    return values


def validate_historical_event_impact_filters(
    values: list[HistoricalEventImpact | str],
) -> list[HistoricalEventImpact | str]:
    """Validate historical event impact filters."""
    if not isinstance(values, list):
        raise ValueError("Allowed impacts must be a list.")

    for value in values:
        normalize_historical_event_impact(value)

    return values


def validate_historical_event_sentiment_filters(
    values: list[HistoricalEventSentiment | str],
) -> list[HistoricalEventSentiment | str]:
    """Validate historical event sentiment filters."""
    if not isinstance(values, list):
        raise ValueError("Allowed sentiments must be a list.")

    for value in values:
        normalize_historical_event_sentiment(value)

    return values


def build_macro_event_normalization_config(
    *,
    dataset_id: str,
    symbol: str = "",
    allowed_event_types: list[HistoricalEventType | str] | None = None,
    allowed_impacts: list[HistoricalEventImpact | str] | None = None,
    allowed_sentiments: list[HistoricalEventSentiment | str] | None = None,
    allowed_countries: list[str] | None = None,
    allowed_currencies: list[str] | None = None,
    min_relevance_score: float = 0.0,
    deduplicate: bool = True,
    include_unknown_symbol: bool = True,
    metadata: dict[str, Any] | None = None,
) -> MacroEventNormalizationConfig:
    """Build macro event normalization config."""
    return MacroEventNormalizationConfig(
        dataset_id=dataset_id,
        symbol=symbol,
        allowed_event_types=allowed_event_types or [],
        allowed_impacts=allowed_impacts or [],
        allowed_sentiments=allowed_sentiments or [],
        allowed_countries=allowed_countries or [],
        allowed_currencies=allowed_currencies or [],
        min_relevance_score=min_relevance_score,
        deduplicate=deduplicate,
        include_unknown_symbol=include_unknown_symbol,
        metadata=metadata or {},
    )


def build_macro_event_normalization_summary(
    *,
    dataset_id: str,
    status: MacroEventNormalizationStatus | str = MacroEventNormalizationStatus.EMPTY,
    input_count: int = 0,
    output_count: int = 0,
    duplicate_count: int = 0,
    dropped_count: int = 0,
    high_impact_count: int = 0,
    directional_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> MacroEventNormalizationSummary:
    """Build macro event normalization summary."""
    return MacroEventNormalizationSummary(
        dataset_id=dataset_id,
        status=status,
        input_count=input_count,
        output_count=output_count,
        duplicate_count=duplicate_count,
        dropped_count=dropped_count,
        high_impact_count=high_impact_count,
        directional_count=directional_count,
        metadata=metadata or {},
    )


def build_macro_event_normalization_result(
    *,
    success: bool,
    rows: list[HistoricalEventRow] | None = None,
    summary: MacroEventNormalizationSummary | None = None,
    message: str = "",
    issues: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> MacroEventNormalizationResult:
    """Build macro event normalization result."""
    return MacroEventNormalizationResult(
        success=success,
        rows=rows or [],
        summary=summary,
        message=message,
        issues=issues or [],
        metadata=metadata or {},
    )


def news_event_record_to_historical_event_row(
    record: NewsEventRecord,
) -> HistoricalEventRow:
    """Convert NewsEventRecord to HistoricalEventRow."""
    if not isinstance(record, NewsEventRecord):
        raise ValueError("Record must be NewsEventRecord.")

    surprise = record.metadata.get("surprise", 0.0)

    if surprise is None:
        surprise = 0.0

    return build_historical_event_row(
        event_id=record.event_id,
        timestamp=record.timestamp,
        title=record.title,
        event_type=normalize_historical_event_type(record.event_type),
        symbol=record.symbol,
        impact=normalize_historical_event_impact(record.impact),
        sentiment=normalize_historical_event_sentiment(record.sentiment),
        source=record.source,
        description=record.description,
        country=record.country,
        currency=record.currency,
        relevance_score=record.relevance_score,
        surprise=float(surprise),
        metadata={
            **record.metadata,
            "url": record.url,
            "provider_id": record.provider_id,
            "raw_payload": dict(record.raw_payload),
        },
    )


def news_event_records_to_historical_event_rows(
    records: list[NewsEventRecord],
) -> list[HistoricalEventRow]:
    """Convert NewsEventRecord list to HistoricalEventRow list."""
    if not isinstance(records, list):
        raise ValueError("Records must be a list.")

    return [news_event_record_to_historical_event_row(record) for record in records]


def news_provider_result_to_historical_event_rows(
    result: NewsProviderResult,
) -> list[HistoricalEventRow]:
    """Convert NewsProviderResult to HistoricalEventRow list."""
    if not isinstance(result, NewsProviderResult):
        raise ValueError("Result must be NewsProviderResult.")

    return news_event_records_to_historical_event_rows(result.records)


def news_feed_result_to_historical_event_rows(
    result: NewsFeedProviderResult,
) -> list[HistoricalEventRow]:
    """Convert NewsFeedProviderResult to HistoricalEventRow list."""
    if not isinstance(result, NewsFeedProviderResult):
        raise ValueError("Result must be NewsFeedProviderResult.")

    news_result = news_feed_result_to_news_provider_result(result)

    return news_provider_result_to_historical_event_rows(news_result)


def economic_calendar_result_to_historical_event_rows(
    result: EconomicCalendarProviderResult,
    *,
    symbol: str = "",
) -> list[HistoricalEventRow]:
    """Convert EconomicCalendarProviderResult to HistoricalEventRow list."""
    if not isinstance(result, EconomicCalendarProviderResult):
        raise ValueError("Result must be EconomicCalendarProviderResult.")

    news_result = economic_calendar_result_to_news_provider_result(
        result,
        symbol=symbol,
    )

    return news_provider_result_to_historical_event_rows(news_result)


def historical_event_row_key(row: HistoricalEventRow) -> str:
    """Build stable deduplication key for a historical event row."""
    if not isinstance(row, HistoricalEventRow):
        raise ValueError("Row must be HistoricalEventRow.")

    payload = row.to_dict()

    return "|".join(
        [
            str(payload.get("timestamp", "")).strip().lower(),
            str(payload.get("title", "")).strip().lower(),
            str(payload.get("symbol", "")).strip().upper(),
            str(payload.get("source", "")).strip().lower(),
            str(payload.get("event_type", "")).strip().lower(),
        ]
    )


def deduplicate_historical_event_rows(
    rows: list[HistoricalEventRow],
) -> tuple[list[HistoricalEventRow], int]:
    """Deduplicate historical event rows."""
    validate_historical_event_rows(rows)

    seen: set[str] = set()
    deduplicated: list[HistoricalEventRow] = []
    duplicate_count = 0

    for row in rows:
        key = historical_event_row_key(row)

        if key in seen:
            duplicate_count += 1
            continue

        seen.add(key)
        deduplicated.append(row)

    return deduplicated, duplicate_count


def historical_event_row_matches_config(
    row: HistoricalEventRow,
    config: MacroEventNormalizationConfig,
) -> bool:
    """Return whether row matches normalization config."""
    if not isinstance(row, HistoricalEventRow):
        raise ValueError("Row must be HistoricalEventRow.")

    if not isinstance(config, MacroEventNormalizationConfig):
        raise ValueError("Config must be MacroEventNormalizationConfig.")

    payload = row.to_dict()
    config_payload = config.to_dict()

    if config_payload["symbol"]:
        row_symbol = str(payload.get("symbol", "")).strip().upper()

        if not row_symbol and not config.include_unknown_symbol:
            return False

        if row_symbol and row_symbol != config_payload["symbol"]:
            return False

    if config_payload["allowed_event_types"] and payload["event_type"] not in config_payload["allowed_event_types"]:
        return False

    if config_payload["allowed_impacts"] and payload["impact"] not in config_payload["allowed_impacts"]:
        return False

    if config_payload["allowed_sentiments"] and payload["sentiment"] not in config_payload["allowed_sentiments"]:
        return False

    if config_payload["allowed_countries"] and payload["country"] not in config_payload["allowed_countries"]:
        return False

    if config_payload["allowed_currencies"] and payload["currency"] not in config_payload["allowed_currencies"]:
        return False

    if float(payload["relevance_score"]) < config.min_relevance_score:
        return False

    return True


def filter_historical_event_rows_for_macro_pipeline(
    rows: list[HistoricalEventRow],
    *,
    config: MacroEventNormalizationConfig,
) -> list[HistoricalEventRow]:
    """Filter historical event rows using normalization config."""
    validate_historical_event_rows(rows)

    if not isinstance(config, MacroEventNormalizationConfig):
        raise ValueError("Config must be MacroEventNormalizationConfig.")

    return [
        row
        for row in rows
        if historical_event_row_matches_config(row, config)
    ]


def summarize_normalized_macro_event_rows(
    *,
    dataset_id: str,
    input_count: int,
    output_rows: list[HistoricalEventRow],
    duplicate_count: int = 0,
    dropped_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> MacroEventNormalizationSummary:
    """Summarize normalized macro event rows."""
    validate_historical_event_rows(output_rows)

    status = (
        MacroEventNormalizationStatus.READY
        if output_rows
        else MacroEventNormalizationStatus.EMPTY
    )

    high_impact_count = len([row for row in output_rows if row.high_impact])
    directional_count = len([row for row in output_rows if row.directional])

    return build_macro_event_normalization_summary(
        dataset_id=dataset_id,
        status=status,
        input_count=input_count,
        output_count=len(output_rows),
        duplicate_count=duplicate_count,
        dropped_count=dropped_count,
        high_impact_count=high_impact_count,
        directional_count=directional_count,
        metadata=metadata or {},
    )


def normalize_historical_event_rows_for_macro_pipeline(
    rows: list[HistoricalEventRow],
    *,
    config: MacroEventNormalizationConfig,
) -> MacroEventNormalizationResult:
    """Normalize, deduplicate, filter, and summarize historical event rows."""
    validate_historical_event_rows(rows)

    if not isinstance(config, MacroEventNormalizationConfig):
        raise ValueError("Config must be MacroEventNormalizationConfig.")

    working_rows = list(rows)
    duplicate_count = 0

    if config.deduplicate:
        working_rows, duplicate_count = deduplicate_historical_event_rows(working_rows)

    filtered_rows = filter_historical_event_rows_for_macro_pipeline(
        working_rows,
        config=config,
    )
    dropped_count = len(rows) - len(filtered_rows) - duplicate_count

    summary = summarize_normalized_macro_event_rows(
        dataset_id=config.dataset_id,
        input_count=len(rows),
        output_rows=filtered_rows,
        duplicate_count=duplicate_count,
        dropped_count=max(dropped_count, 0),
        metadata={
            "has_filters": config.has_filters,
        },
    )

    return build_macro_event_normalization_result(
        success=True,
        rows=filtered_rows,
        summary=summary,
        message="Macro events normalized.",
        metadata={
            "config": config.to_dict(),
        },
    )


def normalize_news_provider_result_for_macro_pipeline(
    result: NewsProviderResult,
    *,
    config: MacroEventNormalizationConfig,
) -> MacroEventNormalizationResult:
    """Normalize NewsProviderResult into macro pipeline rows."""
    rows = news_provider_result_to_historical_event_rows(result)

    return normalize_historical_event_rows_for_macro_pipeline(
        rows,
        config=config,
    )


def normalize_news_feed_result_for_macro_pipeline(
    result: NewsFeedProviderResult,
    *,
    config: MacroEventNormalizationConfig,
) -> MacroEventNormalizationResult:
    """Normalize NewsFeedProviderResult into macro pipeline rows."""
    rows = news_feed_result_to_historical_event_rows(result)

    return normalize_historical_event_rows_for_macro_pipeline(
        rows,
        config=config,
    )


def normalize_economic_calendar_result_for_macro_pipeline(
    result: EconomicCalendarProviderResult,
    *,
    config: MacroEventNormalizationConfig,
    symbol: str = "",
) -> MacroEventNormalizationResult:
    """Normalize EconomicCalendarProviderResult into macro pipeline rows."""
    rows = economic_calendar_result_to_historical_event_rows(
        result,
        symbol=symbol or config.symbol,
    )

    return normalize_historical_event_rows_for_macro_pipeline(
        rows,
        config=config,
    )


def apply_sentiment_results_to_news_records(
    records: list[NewsEventRecord],
    results: list[SentimentClassificationResult],
) -> list[NewsEventRecord]:
    """Apply sentiment results to matching news records."""
    if not isinstance(records, list):
        raise ValueError("Records must be a list.")

    if not isinstance(results, list):
        raise ValueError("Results must be a list.")

    result_by_event_id: dict[str, SentimentClassificationResult] = {}

    for result in results:
        if not isinstance(result, SentimentClassificationResult):
            raise ValueError("Results must contain SentimentClassificationResult objects.")

        event_id = result.request_id.replace("-sentiment", "").strip()
        result_by_event_id[event_id] = result

    enriched: list[NewsEventRecord] = []

    for record in records:
        if not isinstance(record, NewsEventRecord):
            raise ValueError("Records must contain NewsEventRecord objects.")

        sentiment_result = result_by_event_id.get(record.event_id)

        if sentiment_result is None:
            enriched.append(record)
            continue

        enriched.append(
            apply_sentiment_result_to_news_record(
                record,
                sentiment_result,
            )
        )

    return enriched


def rank_historical_event_rows_by_relevance(
    rows: list[HistoricalEventRow],
) -> list[HistoricalEventRow]:
    """Rank rows by relevance score and impact."""
    validate_historical_event_rows(rows)

    impact_rank = {
        HistoricalEventImpact.UNKNOWN.value: 0,
        HistoricalEventImpact.LOW.value: 1,
        HistoricalEventImpact.MEDIUM.value: 2,
        HistoricalEventImpact.HIGH.value: 3,
        HistoricalEventImpact.CRITICAL.value: 4,
    }

    return sorted(
        rows,
        key=lambda row: (
            float(row.to_dict()["relevance_score"]),
            impact_rank[row.to_dict()["impact"]],
            row.to_dict()["timestamp"],
        ),
        reverse=True,
    )