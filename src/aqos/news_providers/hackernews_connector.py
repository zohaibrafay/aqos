"""
AQOS Hacker News / public JSON news connector.

This module provides a named connector for the Hacker News Algolia public JSON
API. It is useful as a no-key live HTTP ingestion source for validating AQOS
news ingestion against a real public JSON endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsProviderCapability,
    NewsProviderCredentials,
    NewsProviderResult,
    validate_metadata,
    validate_non_empty_string,
    validate_positive_integer,
    validate_string,
)
from aqos.news_providers.http_provider import (
    HttpNewsFetcher,
    HttpNewsProviderConfig,
    extract_rows_from_http_news_payload,
    load_http_news_feed_result,
    load_http_news_provider_result,
)
from aqos.news_providers.live_connectors import (
    LiveNewsConnectorDefinition,
    LiveNewsConnectorRuntimeConfig,
    build_live_news_connector_definition,
    build_live_news_connector_endpoint,
    build_live_news_connector_runtime_config,
    list_default_live_connector_capabilities,
    live_connector_runtime_to_http_config,
)
from aqos.news_providers.news_feed import NewsFeedProviderResult


class HackerNewsSearchEndpoint(str, Enum):
    """Supported Hacker News Algolia search endpoints."""

    SEARCH = "search"
    SEARCH_BY_DATE = "search_by_date"


class HackerNewsTag(str, Enum):
    """Supported Hacker News Algolia tags."""

    STORY = "story"
    COMMENT = "comment"
    POLL = "poll"
    JOB = "job"


@dataclass(frozen=True)
class HackerNewsQuery:
    """Hacker News public JSON query."""

    query_terms: list[str] = field(default_factory=list)
    tags: list[HackerNewsTag | str] = field(default_factory=lambda: [HackerNewsTag.STORY])
    endpoint: HackerNewsSearchEndpoint | str = HackerNewsSearchEndpoint.SEARCH
    page: int = 0
    hits_per_page: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_hackernews_string_list(self.query_terms, "Query terms")
        validate_hackernews_tags(self.tags)
        normalize_hackernews_search_endpoint(self.endpoint)

        if not isinstance(self.page, int) or self.page < 0:
            raise ValueError("Page must be a non-negative integer.")

        validate_positive_integer(self.hits_per_page, "Hits per page")
        validate_metadata(self.metadata, "Metadata")

    @property
    def query_expression(self) -> str:
        """Return query expression."""
        clean_terms = [term.strip() for term in self.query_terms if term.strip()]
        return " ".join(clean_terms).strip() or "markets"

    @property
    def tag_expression(self) -> str:
        """Return Algolia tag expression."""
        return ",".join(
            normalize_hackernews_tag(tag).value
            for tag in self.tags
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "query_terms": [term.strip().lower() for term in self.query_terms],
            "query_expression": self.query_expression,
            "tags": [
                normalize_hackernews_tag(tag).value
                for tag in self.tags
            ],
            "tag_expression": self.tag_expression,
            "endpoint": normalize_hackernews_search_endpoint(self.endpoint).value,
            "page": self.page,
            "hits_per_page": self.hits_per_page,
            "metadata": dict(self.metadata),
        }


def normalize_hackernews_search_endpoint(
    value: HackerNewsSearchEndpoint | str,
) -> HackerNewsSearchEndpoint:
    """Normalize Hacker News search endpoint."""
    if isinstance(value, HackerNewsSearchEndpoint):
        return value

    normalized = validate_non_empty_string(value, "Hacker News search endpoint").lower()

    try:
        return HackerNewsSearchEndpoint(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HackerNewsSearchEndpoint)
        raise ValueError(
            f"Invalid Hacker News search endpoint '{value}'. Valid endpoints: {valid}.",
        ) from exc


def normalize_hackernews_tag(value: HackerNewsTag | str) -> HackerNewsTag:
    """Normalize Hacker News tag."""
    if isinstance(value, HackerNewsTag):
        return value

    normalized = validate_non_empty_string(value, "Hacker News tag").lower()

    try:
        return HackerNewsTag(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HackerNewsTag)
        raise ValueError(f"Invalid Hacker News tag '{value}'. Valid tags: {valid}.") from exc


def validate_hackernews_string_list(
    values: list[str],
    field_name: str = "Values",
) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_hackernews_tags(
    tags: list[HackerNewsTag | str],
) -> list[HackerNewsTag | str]:
    """Validate Hacker News tags."""
    if not isinstance(tags, list):
        raise ValueError("Tags must be a list.")

    for tag in tags:
        normalize_hackernews_tag(tag)

    return tags


def build_hackernews_query(
    *,
    query_terms: list[str] | None = None,
    tags: list[HackerNewsTag | str] | None = None,
    endpoint: HackerNewsSearchEndpoint | str = HackerNewsSearchEndpoint.SEARCH,
    page: int = 0,
    hits_per_page: int = 10,
    metadata: dict[str, Any] | None = None,
) -> HackerNewsQuery:
    """Build Hacker News query."""
    return HackerNewsQuery(
        query_terms=query_terms or [],
        tags=tags or [HackerNewsTag.STORY],
        endpoint=endpoint,
        page=page,
        hits_per_page=hits_per_page,
        metadata=metadata or {},
    )


def hackernews_query_to_query_params(query: HackerNewsQuery) -> dict[str, Any]:
    """Convert Hacker News query to HTTP query params."""
    if not isinstance(query, HackerNewsQuery):
        raise ValueError("Query must be HackerNewsQuery.")

    return {
        "query": query.query_expression,
        "tags": query.tag_expression,
        "page": query.page,
        "hitsPerPage": query.hits_per_page,
    }


def build_hackernews_connector_definition(
    *,
    endpoint: HackerNewsSearchEndpoint | str = HackerNewsSearchEndpoint.SEARCH,
) -> LiveNewsConnectorDefinition:
    """Build Hacker News public JSON connector definition."""
    normalized_endpoint = normalize_hackernews_search_endpoint(endpoint)

    connector_endpoint = build_live_news_connector_endpoint(
        base_url="https://hn.algolia.com",
        endpoint=f"/api/v1/{normalized_endpoint.value}",
        payload_key="hits",
        default_query_params={
            "tags": "story",
        },
        default_headers={
            "Accept": "application/json",
            "User-Agent": "AQOS/0.27 HackerNews connector",
        },
        timeout_seconds=30,
    )

    return build_live_news_connector_definition(
        connector_id="hacker_news",
        name="Hacker News Algolia",
        category="public_json",
        endpoint=connector_endpoint,
        auth_type="none",
        status="ready",
        capabilities=list_default_live_connector_capabilities(category="public_json"),
        keyword_query_param="query",
        description="Public no-key Hacker News Algolia JSON connector.",
        metadata={
            "official": True,
            "requires_api_key": False,
            "endpoint": normalized_endpoint.value,
        },
    )


def build_hackernews_runtime_config(
    *,
    query: HackerNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorRuntimeConfig:
    """Build Hacker News runtime config."""
    query = query or build_hackernews_query(query_terms=["markets"])

    if not isinstance(query, HackerNewsQuery):
        raise ValueError("Query must be HackerNewsQuery.")

    return build_live_news_connector_runtime_config(
        connector=build_hackernews_connector_definition(endpoint=query.endpoint),
        credentials=credentials or NewsProviderCredentials(),
        keywords=[],
        query_params=hackernews_query_to_query_params(query),
        headers=headers or {},
        payload_key="hits",
        metadata={
            **query.metadata,
            **(metadata or {}),
        },
    )


def build_hackernews_http_config(
    *,
    query: HackerNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderConfig:
    """Build HTTP config for Hacker News."""
    runtime_config = build_hackernews_runtime_config(
        query=query,
        credentials=credentials,
        headers=headers,
        metadata=metadata,
    )

    return live_connector_runtime_to_http_config(runtime_config)


def hackernews_raw_row_to_normalized_news_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one Hacker News row into AQOS-compatible news row."""
    validate_metadata(row, "Hacker News row")

    title = str(row.get("title") or row.get("story_title") or row.get("comment_text") or "")
    url = str(row.get("url") or row.get("story_url") or "")
    article_id = str(
        row.get("objectID")
        or row.get("story_id")
        or row.get("id")
        or url
        or title
        or ""
    )
    created_at = str(row.get("created_at") or row.get("created_at_i") or "")
    author = str(row.get("author") or "")
    points = row.get("points")
    num_comments = row.get("num_comments")

    return {
        "article_id": article_id,
        "published_at": created_at,
        "title": title,
        "source": "news.ycombinator.com",
        "source_type": "blog",
        "url": url,
        "description": title,
        "content": str(row.get("comment_text") or row.get("story_text") or title),
        "language": "en",
        "country": "",
        "symbol": str(row.get("symbol") or ""),
        "topics": list(row.get("topics") or ["macro"]),
        "event_type": str(row.get("event_type") or "news"),
        "impact": str(row.get("impact") or "unknown"),
        "sentiment": str(row.get("sentiment") or "unknown"),
        "relevance_score": float(row.get("relevance_score") or 0.0),
        "provider_id": str(row.get("provider_id") or "hacker_news"),
        "metadata": {
            "hn_author": author,
            "hn_points": points,
            "hn_num_comments": num_comments,
            "hn_object_id": row.get("objectID", ""),
            "hn_tags": row.get("_tags", []),
        },
        "raw_payload": dict(row),
    }


def normalize_hackernews_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    payload_key: str = "hits",
) -> dict[str, list[dict[str, Any]]]:
    """Normalize Hacker News payload rows."""
    rows = extract_rows_from_http_news_payload(payload, key=payload_key)

    return {
        payload_key: [
            hackernews_raw_row_to_normalized_news_row(row)
            for row in rows
        ]
    }


def load_hackernews_news_feed_result(
    *,
    query: HackerNewsQuery | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsFeedProviderResult:
    """Load Hacker News news feed result."""
    config = build_hackernews_http_config(query=query)

    resolved_payload = (
        normalize_hackernews_payload(payload, payload_key="hits")
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_hackernews_payload(raw_payload, payload_key="hits")

    return load_http_news_feed_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )


def load_hackernews_news_provider_result(
    *,
    query: HackerNewsQuery | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load Hacker News generic news provider result."""
    config = build_hackernews_http_config(query=query)

    resolved_payload = (
        normalize_hackernews_payload(payload, payload_key="hits")
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_hackernews_payload(raw_payload, payload_key="hits")

    return load_http_news_provider_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )