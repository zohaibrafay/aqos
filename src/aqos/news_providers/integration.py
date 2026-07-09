"""
AQOS news integration hub.

This module orchestrates local JSON, HTTP, news feed, economic calendar,
generic news provider results, sentiment enrichment, and macro normalization
into one AQOS-ready news/macro pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsEventRecord,
    NewsProviderResult,
    build_news_provider_result,
    news_provider_failure,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)
from aqos.news_providers.economic_calendar import EconomicCalendarProviderResult
from aqos.news_providers.http_provider import (
    HttpNewsFetcher,
    HttpNewsProviderConfig,
    load_http_news_provider_result,
)
from aqos.news_providers.local_json import (
    LocalJsonNewsProviderConfig,
    load_local_json_news_provider_result,
)
from aqos.news_providers.news_feed import (
    NewsFeedProviderResult,
    NewsFeedQuery,
    news_feed_result_to_news_provider_result,
)
from aqos.news_providers.normalization import (
    MacroEventNormalizationConfig,
    MacroEventNormalizationResult,
    apply_sentiment_results_to_news_records,
    build_macro_event_normalization_config,
    normalize_economic_calendar_result_for_macro_pipeline,
    normalize_historical_event_rows_for_macro_pipeline,
    normalize_news_provider_result_for_macro_pipeline,
    news_event_records_to_historical_event_rows,
)
from aqos.news_providers.sentiment import SentimentClassificationResult


class NewsIntegrationSourceKind(str, Enum):
    """Supported news integration source kinds."""

    NEWS_PROVIDER_RESULT = "news_provider_result"
    NEWS_FEED_RESULT = "news_feed_result"
    ECONOMIC_CALENDAR_RESULT = "economic_calendar_result"
    LOCAL_JSON = "local_json"
    HTTP = "http"
    MANUAL_RECORDS = "manual_records"
    UNKNOWN = "unknown"


class NewsIntegrationStatus(str, Enum):
    """Supported news integration statuses."""

    READY = "ready"
    EMPTY = "empty"
    PARTIAL = "partial"
    ERROR = "error"


@dataclass(frozen=True)
class NewsIntegrationHubConfig:
    """News integration hub configuration."""

    hub_id: str
    name: str = "AQOS News Integration Hub"
    default_symbol: str = ""
    normalize_macro_events: bool = True
    deduplicate_records: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.hub_id, "Hub ID")
        validate_non_empty_string(self.name, "Hub name")
        validate_string(self.default_symbol, "Default symbol")

        if not isinstance(self.normalize_macro_events, bool):
            raise ValueError("Normalize macro events must be a boolean.")

        if not isinstance(self.deduplicate_records, bool):
            raise ValueError("Deduplicate records must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "hub_id": self.hub_id.strip(),
            "name": self.name.strip(),
            "default_symbol": self.default_symbol.strip().upper(),
            "normalize_macro_events": self.normalize_macro_events,
            "deduplicate_records": self.deduplicate_records,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsIntegrationSource:
    """Single news integration source."""

    source_id: str
    source_kind: NewsIntegrationSourceKind | str
    provider_result: NewsProviderResult | None = None
    news_feed_result: NewsFeedProviderResult | None = None
    economic_calendar_result: EconomicCalendarProviderResult | None = None
    local_json_config: LocalJsonNewsProviderConfig | None = None
    http_config: HttpNewsProviderConfig | None = None
    manual_records: list[NewsEventRecord] = field(default_factory=list)
    query: NewsFeedQuery | None = None
    payload: dict[str, Any] | list[dict[str, Any]] | None = None
    payload_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.source_id, "Source ID")
        normalize_news_integration_source_kind(self.source_kind)

        if self.provider_result is not None and not isinstance(
            self.provider_result,
            NewsProviderResult,
        ):
            raise ValueError("Provider result must be NewsProviderResult.")

        if self.news_feed_result is not None and not isinstance(
            self.news_feed_result,
            NewsFeedProviderResult,
        ):
            raise ValueError("News feed result must be NewsFeedProviderResult.")

        if self.economic_calendar_result is not None and not isinstance(
            self.economic_calendar_result,
            EconomicCalendarProviderResult,
        ):
            raise ValueError("Economic calendar result must be EconomicCalendarProviderResult.")

        if self.local_json_config is not None and not isinstance(
            self.local_json_config,
            LocalJsonNewsProviderConfig,
        ):
            raise ValueError("Local JSON config must be LocalJsonNewsProviderConfig.")

        if self.http_config is not None and not isinstance(
            self.http_config,
            HttpNewsProviderConfig,
        ):
            raise ValueError("HTTP config must be HttpNewsProviderConfig.")

        validate_news_event_records(self.manual_records)

        if self.query is not None and not isinstance(self.query, NewsFeedQuery):
            raise ValueError("Query must be NewsFeedQuery.")

        if self.payload is not None and not isinstance(self.payload, dict | list):
            raise ValueError("Payload must be a dictionary or list.")

        validate_string(self.payload_key, "Payload key")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert source to dictionary."""
        return {
            "source_id": self.source_id.strip(),
            "source_kind": normalize_news_integration_source_kind(self.source_kind).value,
            "has_provider_result": self.provider_result is not None,
            "has_news_feed_result": self.news_feed_result is not None,
            "has_economic_calendar_result": self.economic_calendar_result is not None,
            "has_local_json_config": self.local_json_config is not None,
            "has_http_config": self.http_config is not None,
            "manual_record_count": len(self.manual_records),
            "has_query": self.query is not None,
            "has_payload": self.payload is not None,
            "payload_key": self.payload_key.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsIntegrationSummary:
    """News integration summary."""

    hub_id: str
    status: NewsIntegrationStatus | str = NewsIntegrationStatus.EMPTY
    source_count: int = 0
    successful_source_count: int = 0
    failed_source_count: int = 0
    record_count: int = 0
    duplicate_count: int = 0
    macro_row_count: int = 0
    issue_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.hub_id, "Hub ID")
        normalize_news_integration_status(self.status)
        validate_non_negative_integer_like(self.source_count, "Source count")
        validate_non_negative_integer_like(self.successful_source_count, "Successful source count")
        validate_non_negative_integer_like(self.failed_source_count, "Failed source count")
        validate_non_negative_integer_like(self.record_count, "Record count")
        validate_non_negative_integer_like(self.duplicate_count, "Duplicate count")
        validate_non_negative_integer_like(self.macro_row_count, "Macro row count")
        validate_non_negative_integer_like(self.issue_count, "Issue count")
        validate_metadata(self.metadata, "Metadata")

    @property
    def ready(self) -> bool:
        """Return whether summary is ready."""
        return normalize_news_integration_status(self.status) == NewsIntegrationStatus.READY

    @property
    def empty(self) -> bool:
        """Return whether summary is empty."""
        return self.record_count == 0 and self.macro_row_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "hub_id": self.hub_id.strip(),
            "status": normalize_news_integration_status(self.status).value,
            "source_count": self.source_count,
            "successful_source_count": self.successful_source_count,
            "failed_source_count": self.failed_source_count,
            "record_count": self.record_count,
            "duplicate_count": self.duplicate_count,
            "macro_row_count": self.macro_row_count,
            "issue_count": self.issue_count,
            "ready": self.ready,
            "empty": self.empty,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsIntegrationResult:
    """News integration result."""

    success: bool
    provider_result: NewsProviderResult
    macro_result: MacroEventNormalizationResult | None = None
    summary: NewsIntegrationSummary | None = None
    issues: list[str] = field(default_factory=list)
    source_results: dict[str, NewsProviderResult] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        if not isinstance(self.provider_result, NewsProviderResult):
            raise ValueError("Provider result must be NewsProviderResult.")

        if self.macro_result is not None and not isinstance(
            self.macro_result,
            MacroEventNormalizationResult,
        ):
            raise ValueError("Macro result must be MacroEventNormalizationResult.")

        if self.summary is not None and not isinstance(self.summary, NewsIntegrationSummary):
            raise ValueError("Summary must be NewsIntegrationSummary.")

        validate_string_list(self.issues, "Issues")

        if not isinstance(self.source_results, dict):
            raise ValueError("Source results must be a dictionary.")

        for key, value in self.source_results.items():
            validate_non_empty_string(key, "Source result key")

            if not isinstance(value, NewsProviderResult):
                raise ValueError("Source results must contain NewsProviderResult objects.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether integration failed."""
        return not self.success

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "failed": self.failed,
            "provider_result": self.provider_result.to_dict(),
            "macro_result": self.macro_result.to_dict() if self.macro_result is not None else None,
            "summary": self.summary.to_dict() if self.summary is not None else None,
            "issues": [issue.strip() for issue in self.issues],
            "issue_count": self.issue_count,
            "source_results": {
                key: value.to_dict()
                for key, value in self.source_results.items()
            },
            "metadata": dict(self.metadata),
        }


def normalize_news_integration_source_kind(
    value: NewsIntegrationSourceKind | str,
) -> NewsIntegrationSourceKind:
    """Normalize news integration source kind."""
    if isinstance(value, NewsIntegrationSourceKind):
        return value

    normalized = validate_non_empty_string(value, "News integration source kind").lower()

    try:
        return NewsIntegrationSourceKind(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsIntegrationSourceKind)
        raise ValueError(
            f"Invalid news integration source kind '{value}'. Valid kinds: {valid}.",
        ) from exc


def normalize_news_integration_status(
    value: NewsIntegrationStatus | str,
) -> NewsIntegrationStatus:
    """Normalize news integration status."""
    if isinstance(value, NewsIntegrationStatus):
        return value

    normalized = validate_non_empty_string(value, "News integration status").lower()

    try:
        return NewsIntegrationStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsIntegrationStatus)
        raise ValueError(
            f"Invalid news integration status '{value}'. Valid statuses: {valid}.",
        ) from exc


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_non_negative_integer_like(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_news_event_records(records: list[NewsEventRecord]) -> list[NewsEventRecord]:
    """Validate news event records."""
    if not isinstance(records, list):
        raise ValueError("Records must be a list.")

    for record in records:
        if not isinstance(record, NewsEventRecord):
            raise ValueError("Records must contain NewsEventRecord objects.")

    return records


def build_news_integration_hub_config(
    *,
    hub_id: str,
    name: str = "AQOS News Integration Hub",
    default_symbol: str = "",
    normalize_macro_events: bool = True,
    deduplicate_records: bool = True,
    metadata: dict[str, Any] | None = None,
) -> NewsIntegrationHubConfig:
    """Build news integration hub config."""
    return NewsIntegrationHubConfig(
        hub_id=hub_id,
        name=name,
        default_symbol=default_symbol,
        normalize_macro_events=normalize_macro_events,
        deduplicate_records=deduplicate_records,
        metadata=metadata or {},
    )


def build_news_integration_source(
    *,
    source_id: str,
    source_kind: NewsIntegrationSourceKind | str,
    provider_result: NewsProviderResult | None = None,
    news_feed_result: NewsFeedProviderResult | None = None,
    economic_calendar_result: EconomicCalendarProviderResult | None = None,
    local_json_config: LocalJsonNewsProviderConfig | None = None,
    http_config: HttpNewsProviderConfig | None = None,
    manual_records: list[NewsEventRecord] | None = None,
    query: NewsFeedQuery | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    payload_key: str = "",
    metadata: dict[str, Any] | None = None,
) -> NewsIntegrationSource:
    """Build news integration source."""
    return NewsIntegrationSource(
        source_id=source_id,
        source_kind=source_kind,
        provider_result=provider_result,
        news_feed_result=news_feed_result,
        economic_calendar_result=economic_calendar_result,
        local_json_config=local_json_config,
        http_config=http_config,
        manual_records=manual_records or [],
        query=query,
        payload=payload,
        payload_key=payload_key,
        metadata=metadata or {},
    )


def build_news_integration_summary(
    *,
    hub_id: str,
    status: NewsIntegrationStatus | str = NewsIntegrationStatus.EMPTY,
    source_count: int = 0,
    successful_source_count: int = 0,
    failed_source_count: int = 0,
    record_count: int = 0,
    duplicate_count: int = 0,
    macro_row_count: int = 0,
    issue_count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> NewsIntegrationSummary:
    """Build news integration summary."""
    return NewsIntegrationSummary(
        hub_id=hub_id,
        status=status,
        source_count=source_count,
        successful_source_count=successful_source_count,
        failed_source_count=failed_source_count,
        record_count=record_count,
        duplicate_count=duplicate_count,
        macro_row_count=macro_row_count,
        issue_count=issue_count,
        metadata=metadata or {},
    )


def build_news_integration_result(
    *,
    success: bool,
    provider_result: NewsProviderResult,
    macro_result: MacroEventNormalizationResult | None = None,
    summary: NewsIntegrationSummary | None = None,
    issues: list[str] | None = None,
    source_results: dict[str, NewsProviderResult] | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsIntegrationResult:
    """Build news integration result."""
    return NewsIntegrationResult(
        success=success,
        provider_result=provider_result,
        macro_result=macro_result,
        summary=summary,
        issues=issues or [],
        source_results=source_results or {},
        metadata=metadata or {},
    )


def resolve_news_integration_source(
    source: NewsIntegrationSource,
    *,
    fetchers: dict[str, HttpNewsFetcher] | None = None,
) -> NewsProviderResult:
    """Resolve integration source into NewsProviderResult."""
    if not isinstance(source, NewsIntegrationSource):
        raise ValueError("Source must be NewsIntegrationSource.")

    source_kind = normalize_news_integration_source_kind(source.source_kind)
    fetchers = fetchers or {}

    if source_kind == NewsIntegrationSourceKind.NEWS_PROVIDER_RESULT:
        if source.provider_result is None:
            return news_provider_failure(
                message="Missing provider result.",
                code="missing_provider_result",
                provider_id=source.source_id,
            )

        return source.provider_result

    if source_kind == NewsIntegrationSourceKind.NEWS_FEED_RESULT:
        if source.news_feed_result is None:
            return news_provider_failure(
                message="Missing news feed result.",
                code="missing_news_feed_result",
                provider_id=source.source_id,
            )

        return news_feed_result_to_news_provider_result(source.news_feed_result)

    if source_kind == NewsIntegrationSourceKind.ECONOMIC_CALENDAR_RESULT:
        if source.economic_calendar_result is None:
            return news_provider_failure(
                message="Missing economic calendar result.",
                code="missing_economic_calendar_result",
                provider_id=source.source_id,
            )

        from aqos.news_providers.economic_calendar import (
            economic_calendar_result_to_news_provider_result,
        )

        return economic_calendar_result_to_news_provider_result(
            source.economic_calendar_result,
        )

    if source_kind == NewsIntegrationSourceKind.LOCAL_JSON:
        if source.local_json_config is None:
            return news_provider_failure(
                message="Missing local JSON config.",
                code="missing_local_json_config",
                provider_id=source.source_id,
            )

        return load_local_json_news_provider_result(
            source.local_json_config,
            query=source.query,
            payload_key=source.payload_key,
        )

    if source_kind == NewsIntegrationSourceKind.HTTP:
        if source.http_config is None:
            return news_provider_failure(
                message="Missing HTTP config.",
                code="missing_http_config",
                provider_id=source.source_id,
            )

        return load_http_news_provider_result(
            source.http_config,
            query=source.query,
            payload=source.payload,
            payload_key=source.payload_key,
            fetcher=fetchers.get(source.source_id),
        )

    if source_kind == NewsIntegrationSourceKind.MANUAL_RECORDS:
        return build_news_provider_result(
            success=True,
            records=source.manual_records,
            message="Loaded manual news records.",
            provider_id=source.source_id,
            metadata={
                "source_kind": source_kind.value,
            },
        )

    return news_provider_failure(
        message=f"Unsupported source kind: {source_kind.value}",
        code="unsupported_source_kind",
        provider_id=source.source_id,
    )


def merge_news_provider_results(
    results: list[NewsProviderResult],
    *,
    provider_id: str = "news-integration",
    deduplicate: bool = True,
) -> tuple[NewsProviderResult, int]:
    """Merge provider results."""
    if not isinstance(results, list):
        raise ValueError("Results must be a list.")

    records: list[NewsEventRecord] = []
    issues: list[str] = []

    for result in results:
        if not isinstance(result, NewsProviderResult):
            raise ValueError("Results must contain NewsProviderResult objects.")

        records.extend(result.records)

        for issue in result.issues:
            issues.append(issue.message)

    duplicate_count = 0

    if deduplicate:
        records, duplicate_count = deduplicate_news_event_records(records)

    merged = build_news_provider_result(
        success=True,
        records=records,
        message="Merged news provider results.",
        provider_id=provider_id,
        metadata={
            "source_result_count": len(results),
            "duplicate_count": duplicate_count,
            "issue_messages": issues,
        },
    )

    return merged, duplicate_count


def news_event_record_key(record: NewsEventRecord) -> str:
    """Build stable news event record deduplication key."""
    if not isinstance(record, NewsEventRecord):
        raise ValueError("Record must be NewsEventRecord.")

    payload = record.to_dict()

    return "|".join(
        [
            str(payload["timestamp"]).strip().lower(),
            str(payload["title"]).strip().lower(),
            str(payload["symbol"]).strip().upper(),
            str(payload["source"]).strip().lower(),
            str(payload["event_type"]).strip().lower(),
        ]
    )


def deduplicate_news_event_records(
    records: list[NewsEventRecord],
) -> tuple[list[NewsEventRecord], int]:
    """Deduplicate news event records."""
    validate_news_event_records(records)

    seen: set[str] = set()
    output: list[NewsEventRecord] = []
    duplicate_count = 0

    for record in records:
        key = news_event_record_key(record)

        if key in seen:
            duplicate_count += 1
            continue

        seen.add(key)
        output.append(record)

    return output, duplicate_count


def build_macro_config_for_news_integration(
    *,
    config: NewsIntegrationHubConfig,
    macro_config: MacroEventNormalizationConfig | None = None,
) -> MacroEventNormalizationConfig:
    """Build or reuse macro config for news integration."""
    if not isinstance(config, NewsIntegrationHubConfig):
        raise ValueError("Config must be NewsIntegrationHubConfig.")

    if macro_config is not None:
        if not isinstance(macro_config, MacroEventNormalizationConfig):
            raise ValueError("Macro config must be MacroEventNormalizationConfig.")

        return macro_config

    return build_macro_event_normalization_config(
        dataset_id=f"{config.hub_id}-macro-events",
        symbol=config.default_symbol,
        deduplicate=True,
    )


def run_news_integration_hub(
    *,
    config: NewsIntegrationHubConfig,
    sources: list[NewsIntegrationSource],
    macro_config: MacroEventNormalizationConfig | None = None,
    sentiment_results: list[SentimentClassificationResult] | None = None,
    fetchers: dict[str, HttpNewsFetcher] | None = None,
) -> NewsIntegrationResult:
    """Run AQOS news integration hub."""
    if not isinstance(config, NewsIntegrationHubConfig):
        raise ValueError("Config must be NewsIntegrationHubConfig.")

    if not isinstance(sources, list):
        raise ValueError("Sources must be a list.")

    source_results: dict[str, NewsProviderResult] = {}
    provider_results: list[NewsProviderResult] = []
    issues: list[str] = []

    for source in sources:
        if not isinstance(source, NewsIntegrationSource):
            raise ValueError("Sources must contain NewsIntegrationSource objects.")

        result = resolve_news_integration_source(
            source,
            fetchers=fetchers,
        )

        source_results[source.source_id] = result
        provider_results.append(result)

        if result.failed:
            issues.append(f"{source.source_id}: {result.message}")

    merged_provider_result, duplicate_count = merge_news_provider_results(
        provider_results,
        provider_id=config.hub_id,
        deduplicate=config.deduplicate_records,
    )

    records = merged_provider_result.records

    if sentiment_results:
        records = apply_sentiment_results_to_news_records(
            records,
            sentiment_results,
        )
        merged_provider_result = build_news_provider_result(
            success=True,
            records=records,
            message="Merged news provider results with sentiment enrichment.",
            provider_id=config.hub_id,
            metadata={
                **merged_provider_result.metadata,
                "sentiment_result_count": len(sentiment_results),
            },
        )

    resolved_macro_result: MacroEventNormalizationResult | None = None

    if config.normalize_macro_events:
        resolved_macro_config = build_macro_config_for_news_integration(
            config=config,
            macro_config=macro_config,
        )
        rows = news_event_records_to_historical_event_rows(records)
        resolved_macro_result = normalize_historical_event_rows_for_macro_pipeline(
            rows,
            config=resolved_macro_config,
        )

    successful_source_count = len([result for result in provider_results if result.success])
    failed_source_count = len(provider_results) - successful_source_count
    macro_row_count = resolved_macro_result.row_count if resolved_macro_result else 0

    status = infer_news_integration_status(
        record_count=merged_provider_result.record_count,
        source_count=len(sources),
        failed_source_count=failed_source_count,
        macro_row_count=macro_row_count,
    )

    summary = build_news_integration_summary(
        hub_id=config.hub_id,
        status=status,
        source_count=len(sources),
        successful_source_count=successful_source_count,
        failed_source_count=failed_source_count,
        record_count=merged_provider_result.record_count,
        duplicate_count=duplicate_count,
        macro_row_count=macro_row_count,
        issue_count=len(issues),
        metadata={
            "normalize_macro_events": config.normalize_macro_events,
        },
    )

    return build_news_integration_result(
        success=status != NewsIntegrationStatus.ERROR,
        provider_result=merged_provider_result,
        macro_result=resolved_macro_result,
        summary=summary,
        issues=issues,
        source_results=source_results,
        metadata={
            "config": config.to_dict(),
        },
    )


def infer_news_integration_status(
    *,
    record_count: int,
    source_count: int,
    failed_source_count: int,
    macro_row_count: int = 0,
) -> NewsIntegrationStatus:
    """Infer integration status."""
    validate_non_negative_integer_like(record_count, "Record count")
    validate_non_negative_integer_like(source_count, "Source count")
    validate_non_negative_integer_like(failed_source_count, "Failed source count")
    validate_non_negative_integer_like(macro_row_count, "Macro row count")

    if source_count == 0:
        return NewsIntegrationStatus.EMPTY

    if record_count == 0 and failed_source_count == source_count:
        return NewsIntegrationStatus.ERROR

    if record_count == 0 and macro_row_count == 0:
        return NewsIntegrationStatus.EMPTY

    if failed_source_count > 0:
        return NewsIntegrationStatus.PARTIAL

    return NewsIntegrationStatus.READY