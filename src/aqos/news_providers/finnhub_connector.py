"""
AQOS Finnhub news connector.

This module provides a named connector for Finnhub-style market, company,
forex, crypto, and general financial news feeds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
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


class FinnhubNewsEndpoint(str, Enum):
    """Supported Finnhub news endpoints."""

    MARKET_NEWS = "market_news"
    COMPANY_NEWS = "company_news"


class FinnhubNewsCategory(str, Enum):
    """Supported Finnhub market news categories."""

    GENERAL = "general"
    FOREX = "forex"
    CRYPTO = "crypto"
    MERGER = "merger"


@dataclass(frozen=True)
class FinnhubNewsQuery:
    """Finnhub news query."""

    endpoint: FinnhubNewsEndpoint | str = FinnhubNewsEndpoint.MARKET_NEWS
    category: FinnhubNewsCategory | str = FinnhubNewsCategory.GENERAL
    symbol: str = ""
    from_date: str = ""
    to_date: str = ""
    min_id: int = 0
    max_records: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_finnhub_news_endpoint(self.endpoint)
        normalize_finnhub_news_category(self.category)
        validate_string(self.symbol, "Symbol")
        validate_string(self.from_date, "From date")
        validate_string(self.to_date, "To date")

        if not isinstance(self.min_id, int) or self.min_id < 0:
            raise ValueError("Min ID must be a non-negative integer.")

        validate_positive_integer(self.max_records, "Max records")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "endpoint": normalize_finnhub_news_endpoint(self.endpoint).value,
            "category": normalize_finnhub_news_category(self.category).value,
            "symbol": self.symbol.strip().upper(),
            "from_date": self.from_date.strip(),
            "to_date": self.to_date.strip(),
            "min_id": self.min_id,
            "max_records": self.max_records,
            "metadata": dict(self.metadata),
        }


def normalize_finnhub_news_endpoint(
    value: FinnhubNewsEndpoint | str,
) -> FinnhubNewsEndpoint:
    """Normalize Finnhub news endpoint."""
    if isinstance(value, FinnhubNewsEndpoint):
        return value

    normalized = validate_non_empty_string(value, "Finnhub news endpoint").lower()

    try:
        return FinnhubNewsEndpoint(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in FinnhubNewsEndpoint)
        raise ValueError(
            f"Invalid Finnhub news endpoint '{value}'. Valid endpoints: {valid}.",
        ) from exc


def normalize_finnhub_news_category(
    value: FinnhubNewsCategory | str,
) -> FinnhubNewsCategory:
    """Normalize Finnhub news category."""
    if isinstance(value, FinnhubNewsCategory):
        return value

    normalized = validate_non_empty_string(value, "Finnhub news category").lower()

    try:
        return FinnhubNewsCategory(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in FinnhubNewsCategory)
        raise ValueError(
            f"Invalid Finnhub news category '{value}'. Valid categories: {valid}.",
        ) from exc


def build_finnhub_news_query(
    *,
    endpoint: FinnhubNewsEndpoint | str = FinnhubNewsEndpoint.MARKET_NEWS,
    category: FinnhubNewsCategory | str = FinnhubNewsCategory.GENERAL,
    symbol: str = "",
    from_date: str = "",
    to_date: str = "",
    min_id: int = 0,
    max_records: int = 10,
    metadata: dict[str, Any] | None = None,
) -> FinnhubNewsQuery:
    """Build Finnhub news query."""
    return FinnhubNewsQuery(
        endpoint=endpoint,
        category=category,
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
        min_id=min_id,
        max_records=max_records,
        metadata=metadata or {},
    )


def finnhub_query_to_query_params(query: FinnhubNewsQuery) -> dict[str, Any]:
    """Convert Finnhub query to HTTP query params."""
    if not isinstance(query, FinnhubNewsQuery):
        raise ValueError("Query must be FinnhubNewsQuery.")

    endpoint = normalize_finnhub_news_endpoint(query.endpoint)

    if endpoint == FinnhubNewsEndpoint.MARKET_NEWS:
        params: dict[str, Any] = {
            "category": normalize_finnhub_news_category(query.category).value,
            "minId": query.min_id,
        }

        return params

    if endpoint == FinnhubNewsEndpoint.COMPANY_NEWS:
        params = {}

        if query.symbol.strip():
            params["symbol"] = query.symbol.strip().upper()

        if query.from_date.strip():
            params["from"] = query.from_date.strip()

        if query.to_date.strip():
            params["to"] = query.to_date.strip()

        return params

    raise ValueError(f"Unsupported Finnhub endpoint: {query.endpoint}.")


def build_finnhub_connector_definition(
    *,
    endpoint: FinnhubNewsEndpoint | str = FinnhubNewsEndpoint.MARKET_NEWS,
) -> LiveNewsConnectorDefinition:
    """Build Finnhub connector definition."""
    normalized_endpoint = normalize_finnhub_news_endpoint(endpoint)
    endpoint_path = (
        "/api/v1/news"
        if normalized_endpoint == FinnhubNewsEndpoint.MARKET_NEWS
        else "/api/v1/company-news"
    )

    connector_endpoint = build_live_news_connector_endpoint(
        base_url="https://finnhub.io",
        endpoint=endpoint_path,
        payload_key="data",
        default_headers={
            "Accept": "application/json",
            "User-Agent": "AQOS/0.27 Finnhub connector",
        },
        timeout_seconds=30,
        metadata={
            "finnhub_endpoint": normalized_endpoint.value,
        },
    )

    return build_live_news_connector_definition(
        connector_id="finnhub",
        name="Finnhub News",
        category="financial_news",
        endpoint=connector_endpoint,
        auth_type="api_key",
        status="needs_api_key",
        capabilities=list_default_live_connector_capabilities(category="financial_news"),
        api_key_query_param="token",
        symbol_query_param="symbol",
        description="Finnhub financial news connector requiring an API key.",
        metadata={
            "official": True,
            "requires_api_key": True,
            "endpoint": normalized_endpoint.value,
            "payload_key": "data",
        },
    )


def build_finnhub_runtime_config(
    *,
    query: FinnhubNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorRuntimeConfig:
    """Build Finnhub runtime config."""
    query = query or build_finnhub_news_query()

    if not isinstance(query, FinnhubNewsQuery):
        raise ValueError("Query must be FinnhubNewsQuery.")

    return build_live_news_connector_runtime_config(
        connector=build_finnhub_connector_definition(endpoint=query.endpoint),
        credentials=credentials or NewsProviderCredentials(auth_type="api_key"),
        symbol=query.symbol,
        query_params=finnhub_query_to_query_params(query),
        headers=headers or {},
        payload_key="data",
        metadata={
            **query.metadata,
            **(metadata or {}),
        },
    )


def build_finnhub_http_config(
    *,
    query: FinnhubNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderConfig:
    """Build HTTP config for Finnhub."""
    runtime_config = build_finnhub_runtime_config(
        query=query,
        credentials=credentials,
        headers=headers,
        metadata=metadata,
    )

    return live_connector_runtime_to_http_config(runtime_config)


def finnhub_category_to_topic(category: FinnhubNewsCategory | str) -> str:
    """Map Finnhub category to AQOS news topic."""
    normalized = normalize_finnhub_news_category(category)

    if normalized == FinnhubNewsCategory.FOREX:
        return "forex"

    if normalized == FinnhubNewsCategory.CRYPTO:
        return "crypto"

    if normalized == FinnhubNewsCategory.MERGER:
        return "equities"

    return "macro"


def finnhub_raw_row_to_normalized_news_row(
    row: dict[str, Any],
    *,
    category: FinnhubNewsCategory | str = FinnhubNewsCategory.GENERAL,
) -> dict[str, Any]:
    """Normalize one Finnhub row into AQOS-compatible news row."""
    validate_metadata(row, "Finnhub row")

    normalized_category = normalize_finnhub_news_category(category)
    article_id = str(row.get("id") or row.get("url") or row.get("headline") or "")
    published_at = str(row.get("datetime") or row.get("published_at") or "")
    source = str(row.get("source") or "")
    title = str(row.get("headline") or row.get("title") or "")
    description = str(row.get("summary") or row.get("description") or "")
    url = str(row.get("url") or "")

    return {
        "article_id": article_id,
        "published_at": published_at,
        "title": title,
        "source": source,
        "source_type": "news_api",
        "url": url,
        "description": description,
        "content": str(row.get("content") or description),
        "language": str(row.get("language") or "en"),
        "country": str(row.get("country") or ""),
        "symbol": str(row.get("related") or row.get("symbol") or ""),
        "topics": list(row.get("topics") or [finnhub_category_to_topic(normalized_category)]),
        "event_type": str(row.get("event_type") or "news"),
        "impact": str(row.get("impact") or "unknown"),
        "sentiment": str(row.get("sentiment") or "unknown"),
        "relevance_score": float(row.get("relevance_score") or 0.0),
        "provider_id": "finnhub",
        "metadata": {
            "finnhub_category": normalized_category.value,
            "image": row.get("image", ""),
            "related": row.get("related", ""),
        },
        "raw_payload": dict(row),
    }


def normalize_finnhub_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    category: FinnhubNewsCategory | str = FinnhubNewsCategory.GENERAL,
    payload_key: str = "data",
) -> dict[str, list[dict[str, Any]]]:
    """Normalize Finnhub payload rows."""
    rows = extract_rows_from_http_news_payload(payload, key=payload_key)

    return {
        payload_key: [
            finnhub_raw_row_to_normalized_news_row(row, category=category)
            for row in rows
        ]
    }


def load_finnhub_news_feed_result(
    *,
    query: FinnhubNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsFeedProviderResult:
    """Load Finnhub news feed result."""
    query = query or build_finnhub_news_query()
    category = query.category
    config = build_finnhub_http_config(
        query=query,
        credentials=credentials,
    )

    resolved_payload = (
        normalize_finnhub_payload(payload, category=category, payload_key="data")
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_finnhub_payload(
                raw_payload,
                category=category,
                payload_key="data",
            )

    return load_http_news_feed_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )


def load_finnhub_news_provider_result(
    *,
    query: FinnhubNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load Finnhub generic news provider result."""
    query = query or build_finnhub_news_query()
    category = query.category
    config = build_finnhub_http_config(
        query=query,
        credentials=credentials,
    )

    resolved_payload = (
        normalize_finnhub_payload(payload, category=category, payload_key="data")
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_finnhub_payload(
                raw_payload,
                category=category,
                payload_key="data",
            )

    return load_http_news_provider_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )