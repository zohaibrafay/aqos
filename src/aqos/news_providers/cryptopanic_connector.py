"""
AQOS CryptoPanic crypto news connector.

This module provides a named connector for CryptoPanic-style crypto news feeds.
It normalizes crypto news posts, currency tags, votes, sentiment filters, and
provider payloads into AQOS news provider records.
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


class CryptoPanicPostKind(str, Enum):
    """Supported CryptoPanic post kinds."""

    NEWS = "news"
    MEDIA = "media"
    ALL = "all"


class CryptoPanicFilter(str, Enum):
    """Supported CryptoPanic filters."""

    RISING = "rising"
    HOT = "hot"
    IMPORTANT = "important"
    BULLISH = "bullish"
    BEARISH = "bearish"
    LOL = "lol"
    NONE = "none"


@dataclass(frozen=True)
class CryptoPanicNewsQuery:
    """CryptoPanic crypto news query."""

    currencies: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    kind: CryptoPanicPostKind | str = CryptoPanicPostKind.NEWS
    filter: CryptoPanicFilter | str = CryptoPanicFilter.NONE
    public: bool = True
    page: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_cryptopanic_string_list(self.currencies, "Currencies")
        validate_cryptopanic_string_list(self.regions, "Regions")
        normalize_cryptopanic_post_kind(self.kind)
        normalize_cryptopanic_filter(self.filter)

        if not isinstance(self.public, bool):
            raise ValueError("Public must be a boolean.")

        validate_positive_integer(self.page, "Page")
        validate_metadata(self.metadata, "Metadata")

    @property
    def currency_expression(self) -> str:
        """Return comma-separated currency expression."""
        return ",".join(currency.strip().upper() for currency in self.currencies if currency.strip())

    @property
    def region_expression(self) -> str:
        """Return comma-separated region expression."""
        return ",".join(region.strip().lower() for region in self.regions if region.strip())

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "currencies": [currency.strip().upper() for currency in self.currencies],
            "currency_expression": self.currency_expression,
            "regions": [region.strip().lower() for region in self.regions],
            "region_expression": self.region_expression,
            "kind": normalize_cryptopanic_post_kind(self.kind).value,
            "filter": normalize_cryptopanic_filter(self.filter).value,
            "public": self.public,
            "page": self.page,
            "metadata": dict(self.metadata),
        }


def normalize_cryptopanic_post_kind(
    value: CryptoPanicPostKind | str,
) -> CryptoPanicPostKind:
    """Normalize CryptoPanic post kind."""
    if isinstance(value, CryptoPanicPostKind):
        return value

    normalized = validate_non_empty_string(value, "CryptoPanic post kind").lower()

    try:
        return CryptoPanicPostKind(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in CryptoPanicPostKind)
        raise ValueError(
            f"Invalid CryptoPanic post kind '{value}'. Valid kinds: {valid}.",
        ) from exc


def normalize_cryptopanic_filter(
    value: CryptoPanicFilter | str,
) -> CryptoPanicFilter:
    """Normalize CryptoPanic filter."""
    if isinstance(value, CryptoPanicFilter):
        return value

    normalized = validate_non_empty_string(value, "CryptoPanic filter").lower()

    try:
        return CryptoPanicFilter(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in CryptoPanicFilter)
        raise ValueError(
            f"Invalid CryptoPanic filter '{value}'. Valid filters: {valid}.",
        ) from exc


def validate_cryptopanic_string_list(
    values: list[str],
    field_name: str = "Values",
) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def build_cryptopanic_news_query(
    *,
    currencies: list[str] | None = None,
    regions: list[str] | None = None,
    kind: CryptoPanicPostKind | str = CryptoPanicPostKind.NEWS,
    filter: CryptoPanicFilter | str = CryptoPanicFilter.NONE,
    public: bool = True,
    page: int = 1,
    metadata: dict[str, Any] | None = None,
) -> CryptoPanicNewsQuery:
    """Build CryptoPanic news query."""
    return CryptoPanicNewsQuery(
        currencies=currencies or [],
        regions=regions or [],
        kind=kind,
        filter=filter,
        public=public,
        page=page,
        metadata=metadata or {},
    )


def cryptopanic_query_to_query_params(query: CryptoPanicNewsQuery) -> dict[str, Any]:
    """Convert CryptoPanic query to HTTP query params."""
    if not isinstance(query, CryptoPanicNewsQuery):
        raise ValueError("Query must be CryptoPanicNewsQuery.")

    params: dict[str, Any] = {
        "public": "true" if query.public else "false",
        "kind": normalize_cryptopanic_post_kind(query.kind).value,
        "page": query.page,
    }

    if query.currency_expression:
        params["currencies"] = query.currency_expression

    if query.region_expression:
        params["regions"] = query.region_expression

    normalized_filter = normalize_cryptopanic_filter(query.filter)

    if normalized_filter != CryptoPanicFilter.NONE:
        params["filter"] = normalized_filter.value

    return params


def build_cryptopanic_connector_definition() -> LiveNewsConnectorDefinition:
    """Build CryptoPanic connector definition."""
    endpoint = build_live_news_connector_endpoint(
        base_url="https://cryptopanic.com",
        endpoint="/api/v1/posts/",
        payload_key="results",
        default_headers={
            "Accept": "application/json",
            "User-Agent": "AQOS/0.27 CryptoPanic connector",
        },
        timeout_seconds=30,
    )

    return build_live_news_connector_definition(
        connector_id="cryptopanic",
        name="CryptoPanic",
        category="crypto_news",
        endpoint=endpoint,
        auth_type="api_key",
        status="needs_api_key",
        capabilities=list_default_live_connector_capabilities(category="crypto_news"),
        api_key_query_param="auth_token",
        keyword_query_param="currencies",
        description="CryptoPanic-style crypto news connector requiring an API token.",
        metadata={
            "official": True,
            "requires_api_key": True,
            "payload_key": "results",
        },
    )


def build_cryptopanic_runtime_config(
    *,
    query: CryptoPanicNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorRuntimeConfig:
    """Build CryptoPanic runtime config."""
    query = query or build_cryptopanic_news_query(currencies=["BTC"])

    if not isinstance(query, CryptoPanicNewsQuery):
        raise ValueError("Query must be CryptoPanicNewsQuery.")

    return build_live_news_connector_runtime_config(
        connector=build_cryptopanic_connector_definition(),
        credentials=credentials or NewsProviderCredentials(auth_type="api_key"),
        query_params=cryptopanic_query_to_query_params(query),
        headers=headers or {},
        payload_key="results",
        metadata={
            **query.metadata,
            **(metadata or {}),
        },
    )


def build_cryptopanic_http_config(
    *,
    query: CryptoPanicNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderConfig:
    """Build HTTP config for CryptoPanic."""
    runtime_config = build_cryptopanic_runtime_config(
        query=query,
        credentials=credentials,
        headers=headers,
        metadata=metadata,
    )

    return live_connector_runtime_to_http_config(runtime_config)


def cryptopanic_votes_to_sentiment(votes: dict[str, Any]) -> str:
    """Infer sentiment from CryptoPanic vote payload."""
    validate_metadata(votes, "Votes")

    positive = safe_int(votes.get("positive"))
    negative = safe_int(votes.get("negative"))

    if positive > negative:
        return "bullish"

    if negative > positive:
        return "bearish"

    if positive == 0 and negative == 0:
        return "unknown"

    return "neutral"


def cryptopanic_votes_to_impact(votes: dict[str, Any]) -> str:
    """Infer impact from CryptoPanic vote payload."""
    validate_metadata(votes, "Votes")

    important = safe_int(votes.get("important"))
    comments = safe_int(votes.get("comments"))
    positive = safe_int(votes.get("positive"))
    negative = safe_int(votes.get("negative"))

    score = important * 3 + comments + positive + negative

    if score >= 20:
        return "high"

    if score >= 8:
        return "medium"

    if score > 0:
        return "low"

    return "unknown"


def safe_int(value: Any) -> int:
    """Safely convert value to integer."""
    if value is None:
        return 0

    try:
        cleaned = str(value).replace(",", "").strip()

        if not cleaned:
            return 0

        return int(float(cleaned))
    except (TypeError, ValueError):
        return 0


def extract_cryptopanic_currency_symbol(row: dict[str, Any]) -> str:
    """Extract primary crypto currency symbol from CryptoPanic row."""
    currencies = row.get("currencies") or []

    if isinstance(currencies, list) and currencies:
        first_currency = currencies[0]

        if isinstance(first_currency, dict):
            return str(first_currency.get("code") or first_currency.get("symbol") or "")

        if isinstance(first_currency, str):
            return first_currency

    return str(row.get("currency") or row.get("symbol") or "")


def extract_cryptopanic_source_name(row: dict[str, Any]) -> str:
    """Extract source name from CryptoPanic row."""
    source = row.get("source") or {}

    if isinstance(source, dict):
        source_name = str(source.get("title") or source.get("domain") or "")
        return source_name or "CryptoPanic"

    if isinstance(source, str):
        return source or "CryptoPanic"

    return "CryptoPanic"


def cryptopanic_raw_row_to_normalized_news_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one CryptoPanic row into AQOS-compatible news row."""
    validate_metadata(row, "CryptoPanic row")

    votes = row.get("votes") or {}

    if not isinstance(votes, dict):
        votes = {}

    symbol = extract_cryptopanic_currency_symbol(row)
    source_name = extract_cryptopanic_source_name(row)
    url = str(row.get("url") or row.get("slug") or "")
    title = str(row.get("title") or "")

    return {
        "article_id": str(row.get("id") or url or title),
        "published_at": str(row.get("published_at") or row.get("created_at") or ""),
        "title": title,
        "source": source_name,
        "source_type": "news_api",
        "url": url,
        "description": title,
        "content": str(row.get("content") or title),
        "language": str(row.get("language") or "en"),
        "country": "",
        "symbol": symbol.upper(),
        "topics": list(row.get("topics") or ["crypto"]),
        "event_type": str(row.get("event_type") or "news"),
        "impact": str(row.get("impact") or cryptopanic_votes_to_impact(votes)),
        "sentiment": str(row.get("sentiment") or cryptopanic_votes_to_sentiment(votes)),
        "relevance_score": float(row.get("relevance_score") or min(1.0, safe_int(votes.get("important")) / 10.0)),
        "provider_id": "cryptopanic",
        "metadata": {
            "kind": row.get("kind", ""),
            "domain": row.get("domain", ""),
            "source_payload": row.get("source", {}),
            "currencies": row.get("currencies", []),
            "votes": votes,
            "slug": row.get("slug", ""),
        },
        "raw_payload": dict(row),
    }


def normalize_cryptopanic_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    payload_key: str = "results",
) -> dict[str, list[dict[str, Any]]]:
    """Normalize CryptoPanic payload rows."""
    rows = extract_rows_from_http_news_payload(payload, key=payload_key)

    return {
        payload_key: [
            cryptopanic_raw_row_to_normalized_news_row(row)
            for row in rows
        ]
    }


def load_cryptopanic_news_feed_result(
    *,
    query: CryptoPanicNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsFeedProviderResult:
    """Load CryptoPanic news feed result."""
    config = build_cryptopanic_http_config(
        query=query,
        credentials=credentials,
    )

    resolved_payload = (
        normalize_cryptopanic_payload(payload, payload_key="results")
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_cryptopanic_payload(
                raw_payload,
                payload_key="results",
            )

    return load_http_news_feed_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )


def load_cryptopanic_news_provider_result(
    *,
    query: CryptoPanicNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load CryptoPanic generic news provider result."""
    config = build_cryptopanic_http_config(
        query=query,
        credentials=credentials,
    )

    resolved_payload = (
        normalize_cryptopanic_payload(payload, payload_key="results")
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_cryptopanic_payload(
                raw_payload,
                payload_key="results",
            )

    return load_http_news_provider_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )