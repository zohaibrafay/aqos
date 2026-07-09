"""
AQOS NewsAPI / MarketAux style connector.

This module provides named connectors for API-key based financial/news APIs
that return article lists, such as NewsAPI-style and MarketAux-style providers.
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


class ApiNewsConnectorKind(str, Enum):
    """Supported API news connector kinds."""

    NEWS_API = "news_api"
    MARKETAUX = "marketaux"


class ApiNewsSortBy(str, Enum):
    """Supported API news sorting modes."""

    RELEVANCY = "relevancy"
    POPULARITY = "popularity"
    PUBLISHED_AT = "publishedAt"


@dataclass(frozen=True)
class ApiNewsQuery:
    """Generic API news query for NewsAPI / MarketAux style providers."""

    query_terms: list[str] = field(default_factory=list)
    symbol: str = ""
    country: str = ""
    language: str = "en"
    category: str = ""
    from_date: str = ""
    to_date: str = ""
    sort_by: ApiNewsSortBy | str = ApiNewsSortBy.PUBLISHED_AT
    page: int = 1
    page_size: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_api_news_string_list(self.query_terms, "Query terms")
        validate_string(self.symbol, "Symbol")
        validate_string(self.country, "Country")
        validate_string(self.language, "Language")
        validate_string(self.category, "Category")
        validate_string(self.from_date, "From date")
        validate_string(self.to_date, "To date")
        normalize_api_news_sort_by(self.sort_by)
        validate_positive_integer(self.page, "Page")
        validate_positive_integer(self.page_size, "Page size")
        validate_metadata(self.metadata, "Metadata")

    @property
    def query_expression(self) -> str:
        """Return API query expression."""
        parts = [term.strip() for term in self.query_terms if term.strip()]

        if self.symbol.strip():
            parts.append(self.symbol.strip().upper())

        return " OR ".join(parts).strip() or "markets"

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "query_terms": [term.strip().lower() for term in self.query_terms],
            "query_expression": self.query_expression,
            "symbol": self.symbol.strip().upper(),
            "country": self.country.strip().lower(),
            "language": self.language.strip().lower(),
            "category": self.category.strip().lower(),
            "from_date": self.from_date.strip(),
            "to_date": self.to_date.strip(),
            "sort_by": normalize_api_news_sort_by(self.sort_by).value,
            "page": self.page,
            "page_size": self.page_size,
            "metadata": dict(self.metadata),
        }


def normalize_api_news_connector_kind(
    value: ApiNewsConnectorKind | str,
) -> ApiNewsConnectorKind:
    """Normalize API news connector kind."""
    if isinstance(value, ApiNewsConnectorKind):
        return value

    normalized = validate_non_empty_string(value, "API news connector kind").lower()

    try:
        return ApiNewsConnectorKind(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ApiNewsConnectorKind)
        raise ValueError(
            f"Invalid API news connector kind '{value}'. Valid kinds: {valid}.",
        ) from exc


def normalize_api_news_sort_by(value: ApiNewsSortBy | str) -> ApiNewsSortBy:
    """Normalize API news sorting mode."""
    if isinstance(value, ApiNewsSortBy):
        return value

    normalized = validate_non_empty_string(value, "API news sort by")

    try:
        return ApiNewsSortBy(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ApiNewsSortBy)
        raise ValueError(
            f"Invalid API news sort by '{value}'. Valid values: {valid}.",
        ) from exc


def validate_api_news_string_list(
    values: list[str],
    field_name: str = "Values",
) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def build_api_news_query(
    *,
    query_terms: list[str] | None = None,
    symbol: str = "",
    country: str = "",
    language: str = "en",
    category: str = "",
    from_date: str = "",
    to_date: str = "",
    sort_by: ApiNewsSortBy | str = ApiNewsSortBy.PUBLISHED_AT,
    page: int = 1,
    page_size: int = 10,
    metadata: dict[str, Any] | None = None,
) -> ApiNewsQuery:
    """Build API news query."""
    return ApiNewsQuery(
        query_terms=query_terms or [],
        symbol=symbol,
        country=country,
        language=language,
        category=category,
        from_date=from_date,
        to_date=to_date,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
        metadata=metadata or {},
    )


def api_news_query_to_query_params(
    query: ApiNewsQuery,
    *,
    connector_kind: ApiNewsConnectorKind | str,
) -> dict[str, Any]:
    """Convert API news query to provider-specific HTTP query params."""
    if not isinstance(query, ApiNewsQuery):
        raise ValueError("Query must be ApiNewsQuery.")

    kind = normalize_api_news_connector_kind(connector_kind)

    if kind == ApiNewsConnectorKind.NEWS_API:
        params: dict[str, Any] = {
            "q": query.query_expression,
            "language": query.language.strip().lower() or "en",
            "sortBy": normalize_api_news_sort_by(query.sort_by).value,
            "page": query.page,
            "pageSize": query.page_size,
        }

        if query.from_date.strip():
            params["from"] = query.from_date.strip()

        if query.to_date.strip():
            params["to"] = query.to_date.strip()

        return params

    if kind == ApiNewsConnectorKind.MARKETAUX:
        params = {
            "search": query.query_expression,
            "language": query.language.strip().lower() or "en",
            "page": query.page,
            "limit": query.page_size,
        }

        if query.symbol.strip():
            params["symbols"] = query.symbol.strip().upper()

        if query.country.strip():
            params["countries"] = query.country.strip().lower()

        if query.category.strip():
            params["filter_entities"] = "true"
            params["entity_types"] = query.category.strip().lower()

        return params

    raise ValueError(f"Unsupported API news connector kind: {connector_kind}.")


def build_newsapi_connector_definition() -> LiveNewsConnectorDefinition:
    """Build NewsAPI-style connector definition."""
    endpoint = build_live_news_connector_endpoint(
        base_url="https://newsapi.org",
        endpoint="/v2/everything",
        payload_key="articles",
        default_headers={
            "Accept": "application/json",
            "User-Agent": "AQOS/0.27 NewsAPI connector",
        },
        timeout_seconds=30,
    )

    return build_live_news_connector_definition(
        connector_id="news_api",
        name="NewsAPI",
        category="financial_news",
        endpoint=endpoint,
        auth_type="api_key",
        status="needs_api_key",
        capabilities=list_default_live_connector_capabilities(category="financial_news"),
        api_key_query_param="apiKey",
        keyword_query_param="q",
        description="NewsAPI-style article connector requiring an API key.",
        metadata={
            "official": True,
            "requires_api_key": True,
            "payload_key": "articles",
        },
    )


def build_marketaux_connector_definition() -> LiveNewsConnectorDefinition:
    """Build MarketAux-style connector definition."""
    endpoint = build_live_news_connector_endpoint(
        base_url="https://api.marketaux.com",
        endpoint="/v1/news/all",
        payload_key="data",
        default_headers={
            "Accept": "application/json",
            "User-Agent": "AQOS/0.27 MarketAux connector",
        },
        timeout_seconds=30,
    )

    return build_live_news_connector_definition(
        connector_id="marketaux",
        name="MarketAux",
        category="financial_news",
        endpoint=endpoint,
        auth_type="api_key",
        status="needs_api_key",
        capabilities=list_default_live_connector_capabilities(category="financial_news"),
        api_key_query_param="api_token",
        keyword_query_param="search",
        country_query_param="countries",
        description="MarketAux-style financial news connector requiring an API key.",
        metadata={
            "official": True,
            "requires_api_key": True,
            "payload_key": "data",
        },
    )


def build_api_news_connector_definition(
    *,
    connector_kind: ApiNewsConnectorKind | str,
) -> LiveNewsConnectorDefinition:
    """Build API news connector definition by kind."""
    kind = normalize_api_news_connector_kind(connector_kind)

    if kind == ApiNewsConnectorKind.NEWS_API:
        return build_newsapi_connector_definition()

    if kind == ApiNewsConnectorKind.MARKETAUX:
        return build_marketaux_connector_definition()

    raise ValueError(f"Unsupported API news connector kind: {connector_kind}.")


def build_api_news_runtime_config(
    *,
    connector_kind: ApiNewsConnectorKind | str,
    query: ApiNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorRuntimeConfig:
    """Build API news runtime config."""
    query = query or build_api_news_query(query_terms=["markets"])

    if not isinstance(query, ApiNewsQuery):
        raise ValueError("Query must be ApiNewsQuery.")

    kind = normalize_api_news_connector_kind(connector_kind)
    payload_key = "articles" if kind == ApiNewsConnectorKind.NEWS_API else "data"

    return build_live_news_connector_runtime_config(
        connector=build_api_news_connector_definition(connector_kind=kind),
        credentials=credentials or NewsProviderCredentials(auth_type="api_key"),
        symbol=query.symbol,
        country=query.country,
        query_params=api_news_query_to_query_params(
            query,
            connector_kind=kind,
        ),
        headers=headers or {},
        payload_key=payload_key,
        metadata={
            **query.metadata,
            **(metadata or {}),
            "api_news_connector_kind": kind.value,
        },
    )


def build_api_news_http_config(
    *,
    connector_kind: ApiNewsConnectorKind | str,
    query: ApiNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderConfig:
    """Build HTTP config for API news connector."""
    runtime_config = build_api_news_runtime_config(
        connector_kind=connector_kind,
        query=query,
        credentials=credentials,
        headers=headers,
        metadata=metadata,
    )

    return live_connector_runtime_to_http_config(runtime_config)


def api_news_raw_row_to_normalized_news_row(
    row: dict[str, Any],
    *,
    connector_kind: ApiNewsConnectorKind | str,
) -> dict[str, Any]:
    """Normalize one API news row into AQOS-compatible news row."""
    validate_metadata(row, "API news row")

    kind = normalize_api_news_connector_kind(connector_kind)

    if kind == ApiNewsConnectorKind.NEWS_API:
        source_payload = row.get("source") or {}
        source_name = ""

        if isinstance(source_payload, dict):
            source_name = str(source_payload.get("name") or source_payload.get("id") or "")

        return {
            "article_id": str(row.get("url") or row.get("title") or ""),
            "published_at": str(row.get("publishedAt") or row.get("published_at") or ""),
            "title": str(row.get("title") or ""),
            "source": source_name,
            "source_type": "news_api",
            "url": str(row.get("url") or ""),
            "description": str(row.get("description") or ""),
            "content": str(row.get("content") or row.get("description") or ""),
            "language": str(row.get("language") or ""),
            "country": str(row.get("country") or ""),
            "symbol": str(row.get("symbol") or ""),
            "topics": list(row.get("topics") or ["macro"]),
            "event_type": str(row.get("event_type") or "news"),
            "impact": str(row.get("impact") or "unknown"),
            "sentiment": str(row.get("sentiment") or "unknown"),
            "relevance_score": float(row.get("relevance_score") or 0.0),
            "provider_id": "news_api",
            "metadata": {
                "author": row.get("author", ""),
                "url_to_image": row.get("urlToImage", ""),
                "source_payload": source_payload,
            },
            "raw_payload": dict(row),
        }

    if kind == ApiNewsConnectorKind.MARKETAUX:
        source_payload = row.get("source") or ""
        source_name = ""

        if isinstance(source_payload, str):
            source_name = source_payload
        elif isinstance(source_payload, dict):
            source_name = str(source_payload.get("name") or source_payload.get("domain") or "")

        entities = row.get("entities") or []
        symbol = ""

        if isinstance(entities, list) and entities:
            first_entity = entities[0]
            if isinstance(first_entity, dict):
                symbol = str(first_entity.get("symbol") or first_entity.get("name") or "")

        return {
            "article_id": str(row.get("uuid") or row.get("id") or row.get("url") or ""),
            "published_at": str(row.get("published_at") or row.get("publishedAt") or ""),
            "title": str(row.get("title") or ""),
            "source": source_name,
            "source_type": "news_api",
            "url": str(row.get("url") or ""),
            "description": str(row.get("description") or row.get("snippet") or ""),
            "content": str(row.get("snippet") or row.get("description") or ""),
            "language": str(row.get("language") or ""),
            "country": str(row.get("country") or ""),
            "symbol": str(row.get("symbol") or symbol),
            "topics": list(row.get("topics") or ["macro"]),
            "event_type": str(row.get("event_type") or "news"),
            "impact": str(row.get("impact") or "unknown"),
            "sentiment": str(row.get("sentiment") or "unknown"),
            "relevance_score": float(row.get("relevance_score") or row.get("score") or 0.0),
            "provider_id": "marketaux",
            "metadata": {
                "image_url": row.get("image_url", ""),
                "entities": entities,
                "keywords": row.get("keywords", []),
                "source_payload": source_payload,
            },
            "raw_payload": dict(row),
        }

    raise ValueError(f"Unsupported API news connector kind: {connector_kind}.")


def normalize_api_news_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    connector_kind: ApiNewsConnectorKind | str,
    payload_key: str = "",
) -> dict[str, list[dict[str, Any]]]:
    """Normalize API news payload rows."""
    kind = normalize_api_news_connector_kind(connector_kind)
    resolved_payload_key = payload_key or (
        "articles" if kind == ApiNewsConnectorKind.NEWS_API else "data"
    )
    rows = extract_rows_from_http_news_payload(payload, key=resolved_payload_key)

    return {
        resolved_payload_key: [
            api_news_raw_row_to_normalized_news_row(row, connector_kind=kind)
            for row in rows
        ]
    }


def load_api_news_feed_result(
    *,
    connector_kind: ApiNewsConnectorKind | str,
    query: ApiNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsFeedProviderResult:
    """Load API news feed result."""
    kind = normalize_api_news_connector_kind(connector_kind)
    payload_key = "articles" if kind == ApiNewsConnectorKind.NEWS_API else "data"
    config = build_api_news_http_config(
        connector_kind=kind,
        query=query,
        credentials=credentials,
    )

    resolved_payload = (
        normalize_api_news_payload(
            payload,
            connector_kind=kind,
            payload_key=payload_key,
        )
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_api_news_payload(
                raw_payload,
                connector_kind=kind,
                payload_key=payload_key,
            )

    return load_http_news_feed_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )


def load_api_news_provider_result(
    *,
    connector_kind: ApiNewsConnectorKind | str,
    query: ApiNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load API news provider result."""
    kind = normalize_api_news_connector_kind(connector_kind)
    payload_key = "articles" if kind == ApiNewsConnectorKind.NEWS_API else "data"
    config = build_api_news_http_config(
        connector_kind=kind,
        query=query,
        credentials=credentials,
    )

    resolved_payload = (
        normalize_api_news_payload(
            payload,
            connector_kind=kind,
            payload_key=payload_key,
        )
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_api_news_payload(
                raw_payload,
                connector_kind=kind,
                payload_key=payload_key,
            )

    return load_http_news_provider_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )


def load_newsapi_news_provider_result(
    *,
    query: ApiNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load NewsAPI provider result."""
    return load_api_news_provider_result(
        connector_kind=ApiNewsConnectorKind.NEWS_API,
        query=query,
        credentials=credentials,
        payload=payload,
        fetcher=fetcher,
    )


def load_marketaux_news_provider_result(
    *,
    query: ApiNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load MarketAux provider result."""
    return load_api_news_provider_result(
        connector_kind=ApiNewsConnectorKind.MARKETAUX,
        query=query,
        credentials=credentials,
        payload=payload,
        fetcher=fetcher,
    )