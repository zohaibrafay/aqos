"""
AQOS local JSON news provider.

This module loads local JSON news / macro / article data and converts it into
AQOS provider results. It is useful for testing, offline datasets, fixtures,
and replaying historical news without using paid APIs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aqos.news_providers.base import (
    NewsEventRecord,
    NewsProviderCapability,
    NewsProviderConfig,
    NewsProviderResult,
    NewsProviderStatus,
    NewsProviderType,
    build_news_event_record,
    build_news_provider_config,
    build_news_provider_result,
    news_provider_failure,
    normalize_news_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)
from aqos.news_providers.news_feed import (
    NewsFeedArticle,
    NewsFeedProviderResult,
    NewsFeedQuery,
    build_news_feed_article,
    build_news_feed_provider_result,
    filter_news_feed_articles,
    news_feed_articles_to_news_records,
)
from aqos.training_data.events import (
    HistoricalEventImpact,
    HistoricalEventSentiment,
    HistoricalEventType,
)


@dataclass(frozen=True)
class LocalJsonNewsProviderConfig:
    """Local JSON news provider config."""

    provider_id: str
    name: str = "Local JSON News Provider"
    file_path: str = ""
    status: NewsProviderStatus | str = NewsProviderStatus.ACTIVE
    symbol: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_non_empty_string(self.name, "Provider name")
        validate_string(self.file_path, "File path")
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_metadata(self.metadata, "Metadata")

    @property
    def has_file_path(self) -> bool:
        """Return whether config has file path."""
        return bool(self.file_path.strip())

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "name": self.name.strip(),
            "file_path": self.file_path.strip(),
            "status": self.status.value if hasattr(self.status, "value") else str(self.status).strip(),
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "has_file_path": self.has_file_path,
            "metadata": dict(self.metadata),
        }


def build_local_json_news_provider_config(
    *,
    provider_id: str,
    name: str = "Local JSON News Provider",
    file_path: str = "",
    status: NewsProviderStatus | str = NewsProviderStatus.ACTIVE,
    symbol: str = "",
    metadata: dict[str, Any] | None = None,
) -> LocalJsonNewsProviderConfig:
    """Build local JSON news provider config."""
    return LocalJsonNewsProviderConfig(
        provider_id=provider_id,
        name=name,
        file_path=file_path,
        status=status,
        symbol=symbol,
        metadata=metadata or {},
    )


def build_local_json_news_provider_base_config(
    *,
    provider_id: str,
    name: str = "Local JSON News Provider",
    status: NewsProviderStatus | str = NewsProviderStatus.ACTIVE,
    metadata: dict[str, Any] | None = None,
) -> NewsProviderConfig:
    """Build generic news provider config for local JSON provider."""
    return build_news_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=NewsProviderType.LOCAL_JSON,
        status=status,
        capabilities=[
            NewsProviderCapability.HISTORICAL_NEWS,
            NewsProviderCapability.LIVE_NEWS,
            NewsProviderCapability.KEYWORD_FILTERING,
            NewsProviderCapability.SYMBOL_MAPPING,
            NewsProviderCapability.COUNTRY_FILTERING,
        ],
        metadata=metadata or {},
    )


def read_local_json_payload(file_path: str) -> dict[str, Any] | list[dict[str, Any]]:
    """Read local JSON payload from disk."""
    validate_non_empty_string(file_path, "File path")

    path = Path(file_path)

    if not path.exists():
        raise ValueError(f"Local JSON file does not exist: {file_path}")

    if not path.is_file():
        raise ValueError(f"Local JSON path must be a file: {file_path}")

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON file: {file_path}") from exc

    if not isinstance(payload, dict | list):
        raise ValueError("Local JSON payload must be a dictionary or list.")

    if isinstance(payload, list):
        for row in payload:
            validate_metadata(row, "JSON row")

    return payload


def extract_rows_from_local_json_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    key: str = "",
) -> list[dict[str, Any]]:
    """Extract rows from local JSON payload."""
    if isinstance(payload, list):
        return [dict(row) for row in payload]

    validate_metadata(payload, "Payload")

    if key:
        validate_non_empty_string(key, "Payload key")

        if key not in payload:
            raise ValueError(f"Payload key '{key}' was not found.")

        rows = payload[key]

        if not isinstance(rows, list):
            raise ValueError(f"Payload key '{key}' must contain a list.")

        for row in rows:
            validate_metadata(row, "Payload row")

        return [dict(row) for row in rows]

    for candidate_key in ["articles", "records", "events", "news", "items", "data"]:
        rows = payload.get(candidate_key)

        if isinstance(rows, list):
            for row in rows:
                validate_metadata(row, "Payload row")

            return [dict(row) for row in rows]

    raise ValueError("Could not find rows in local JSON payload.")


def raw_json_row_to_news_feed_article(
    row: dict[str, Any],
    *,
    provider_id: str = "",
    default_symbol: str = "",
) -> NewsFeedArticle:
    """Convert raw JSON row to NewsFeedArticle."""
    validate_metadata(row, "JSON row")

    article_id = str(
        row.get("article_id")
        or row.get("event_id")
        or row.get("id")
        or row.get("guid")
        or row.get("objectID")
        or row.get("story_id")
        or row.get("url")
        or row.get("story_url")
        or row.get("title")
        or row.get("story_title")
        or ""
    )
    published_at = str(
        row.get("published_at")
        or row.get("timestamp")
        or row.get("date")
        or row.get("created_at")
        or row.get("created_at_i")
        or row.get("seendate")
        or ""
    )
    title=str(row.get("title") or row.get("story_title") or row.get("comment_text") or "")

    return build_news_feed_article(
        article_id=article_id,
        published_at=published_at,
        title=title,
        source=str(
            row.get("source")
            or row.get("publisher")
            or row.get("domain")
            or ("news.ycombinator.com" if row.get("objectID") else "")
            or ""
        ),
        source_type=str(row.get("source_type") or "local_json"),
        url=str(row.get("url") or row.get("story_url") or ""),
        author=str(row.get("author") or ""),
        description=str(
            row.get("description")
            or row.get("summary")
            or row.get("story_text")
            or row.get("comment_text")
            or row.get("title")
            or row.get("story_title")
            or ""
        ),
        content=str(
            row.get("content")
            or row.get("body")
            or row.get("story_text")
            or row.get("comment_text")
            or row.get("title")
            or row.get("story_title")
            or ""
        ),
        language=str(row.get("language") or ""),
        country=str(row.get("country") or row.get("sourcecountry") or ""),
        symbol=str(row.get("symbol") or default_symbol),
        topics=list(row.get("topics") or ["macro"]),
        event_type=str(row.get("event_type") or HistoricalEventType.NEWS.value),
        impact=str(row.get("impact") or HistoricalEventImpact.UNKNOWN.value),
        sentiment=str(row.get("sentiment") or HistoricalEventSentiment.UNKNOWN.value),
        relevance_score=float(row.get("relevance_score") or 0.0),
        provider_id=str(row.get("provider_id") or provider_id),
        raw_payload=dict(row),
        metadata=dict(row.get("metadata") or {}),
    )


def raw_json_row_to_news_event_record(
    row: dict[str, Any],
    *,
    provider_id: str = "",
    default_symbol: str = "",
) -> NewsEventRecord:
    """Convert raw JSON row directly to NewsEventRecord."""
    validate_metadata(row, "JSON row")

    event_id = str(
        row.get("event_id")
        or row.get("article_id")
        or row.get("id")
        or row.get("guid")
        or row.get("objectID")
        or row.get("story_id")
        or row.get("url")
        or row.get("story_url")
        or row.get("title")
        or row.get("story_title")
        or ""
    )
    timestamp = str(
        row.get("timestamp")
        or row.get("published_at")
        or row.get("date")
        or row.get("created_at")
        or row.get("created_at_i")
        or row.get("seendate")
        or ""
    )
    title=str(row.get("title") or row.get("story_title") or row.get("comment_text") or "")

    return build_news_event_record(
        event_id=event_id,
        timestamp=timestamp,
        title=title,
        event_type=str(row.get("event_type") or HistoricalEventType.NEWS.value),
        symbol=str(row.get("symbol") or default_symbol),
        impact=str(row.get("impact") or HistoricalEventImpact.UNKNOWN.value),
        sentiment=str(row.get("sentiment") or HistoricalEventSentiment.UNKNOWN.value),
        source=str(
            row.get("source")
            or row.get("publisher")
            or row.get("domain")
            or ("news.ycombinator.com" if row.get("objectID") else "")
            or ""
        ),
        provider_id=str(row.get("provider_id") or provider_id),
        url=str(row.get("url") or row.get("story_url") or ""),
        description=str(
            row.get("description")
            or row.get("summary")
            or row.get("story_text")
            or row.get("comment_text")
            or row.get("title")
            or row.get("story_title")
            or ""
        ),
        country=str(row.get("country") or row.get("sourcecountry") or ""),
        currency=str(row.get("currency") or ""),
        relevance_score=float(row.get("relevance_score") or 0.0),
        raw_payload=dict(row),
        metadata=dict(row.get("metadata") or {}),
    )


def local_json_rows_to_news_feed_articles(
    rows: list[dict[str, Any]],
    *,
    provider_id: str = "",
    default_symbol: str = "",
) -> list[NewsFeedArticle]:
    """Convert local JSON rows to news feed articles."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    return [
        raw_json_row_to_news_feed_article(
            row,
            provider_id=provider_id,
            default_symbol=default_symbol,
        )
        for row in rows
    ]


def local_json_rows_to_news_event_records(
    rows: list[dict[str, Any]],
    *,
    provider_id: str = "",
    default_symbol: str = "",
) -> list[NewsEventRecord]:
    """Convert local JSON rows to news event records."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    return [
        raw_json_row_to_news_event_record(
            row,
            provider_id=provider_id,
            default_symbol=default_symbol,
        )
        for row in rows
    ]


def load_local_json_news_feed_result(
    config: LocalJsonNewsProviderConfig,
    *,
    query: NewsFeedQuery | None = None,
    payload_key: str = "",
) -> NewsFeedProviderResult:
    """Load local JSON news feed result from disk."""
    if not isinstance(config, LocalJsonNewsProviderConfig):
        raise ValueError("Config must be LocalJsonNewsProviderConfig.")

    payload = read_local_json_payload(config.file_path)
    rows = extract_rows_from_local_json_payload(payload, key=payload_key)
    articles = local_json_rows_to_news_feed_articles(
        rows,
        provider_id=config.provider_id,
        default_symbol=config.symbol,
    )

    if query is not None:
        articles = filter_news_feed_articles(articles, query=query)

    return build_news_feed_provider_result(
        success=True,
        articles=articles,
        query=query,
        message="Loaded local JSON news feed.",
        provider_id=config.provider_id,
        metadata={
            "file_path": config.file_path,
            "row_count": len(rows),
        },
    )


def load_local_json_news_provider_result(
    config: LocalJsonNewsProviderConfig,
    *,
    query: NewsFeedQuery | None = None,
    payload_key: str = "",
) -> NewsProviderResult:
    """Load local JSON generic news provider result from disk."""
    if not isinstance(config, LocalJsonNewsProviderConfig):
        raise ValueError("Config must be LocalJsonNewsProviderConfig.")

    try:
        feed_result = load_local_json_news_feed_result(
            config,
            query=query,
            payload_key=payload_key,
        )
    except ValueError as exc:
        return news_provider_failure(
            message=str(exc),
            code="local_json_news_provider_error",
            provider_id=config.provider_id,
            metadata={
                "file_path": config.file_path,
            },
        )

    records = news_feed_articles_to_news_records(feed_result.articles)

    return build_news_provider_result(
        success=True,
        records=records,
        message=feed_result.message,
        provider_id=config.provider_id,
        metadata={
            **feed_result.metadata,
            "source_result_type": "local_json",
        },
    )