"""
AQOS GDELT live news connector.

This module provides a named connector for GDELT DOC 2.0 news article data.
It converts GDELT query settings into AQOS live connector runtime configs and
HTTP news provider configs.
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


class GdeltDocMode(str, Enum):
    """Supported GDELT DOC API modes."""

    ARTLIST = "artlist"
    TIMELINE_VOL = "timelinevol"
    TIMELINE_VOL_RAW = "timelinevolraw"
    TIMELINE_TONE = "timelinetone"


class GdeltSortMode(str, Enum):
    """Supported GDELT sort modes."""

    HYBRID_RELEVANCE = "hybridrel"
    DATE_DESC = "datedesc"
    DATE_ASC = "dateasc"


@dataclass(frozen=True)
class GdeltNewsQuery:
    """GDELT news query."""

    query_terms: list[str] = field(default_factory=list)
    exact_phrase: str = ""
    symbol: str = ""
    source_country: str = ""
    source_language: str = ""
    domain: str = ""
    theme: str = ""
    timespan: str = ""
    start_datetime: str = ""
    end_datetime: str = ""
    mode: GdeltDocMode | str = GdeltDocMode.ARTLIST
    sort: GdeltSortMode | str = GdeltSortMode.HYBRID_RELEVANCE
    max_records: int = 10
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_gdelt_string_list(self.query_terms, "Query terms")
        validate_string(self.exact_phrase, "Exact phrase")
        validate_string(self.symbol, "Symbol")
        validate_string(self.source_country, "Source country")
        validate_string(self.source_language, "Source language")
        validate_string(self.domain, "Domain")
        validate_string(self.theme, "Theme")
        validate_string(self.timespan, "Timespan")
        validate_string(self.start_datetime, "Start datetime")
        validate_string(self.end_datetime, "End datetime")
        normalize_gdelt_doc_mode(self.mode)
        normalize_gdelt_sort_mode(self.sort)
        validate_positive_integer(self.max_records, "Max records")
        validate_metadata(self.metadata, "Metadata")

    @property
    def query_expression(self) -> str:
        """Return GDELT query expression."""
        parts: list[str] = []

        clean_terms = [term.strip() for term in self.query_terms if term.strip()]

        if clean_terms:
            parts.append(" OR ".join(clean_terms))

        if self.exact_phrase.strip():
            parts.append(f'"{self.exact_phrase.strip()}"')

        if self.symbol.strip():
            parts.append(self.symbol.strip().upper())

        return " ".join(parts).strip() or "markets"

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "query_terms": [term.strip().lower() for term in self.query_terms],
            "exact_phrase": self.exact_phrase.strip(),
            "symbol": self.symbol.strip().upper(),
            "source_country": self.source_country.strip().upper(),
            "source_language": self.source_language.strip().lower(),
            "domain": self.domain.strip().lower(),
            "theme": self.theme.strip(),
            "timespan": self.timespan.strip(),
            "start_datetime": self.start_datetime.strip(),
            "end_datetime": self.end_datetime.strip(),
            "mode": normalize_gdelt_doc_mode(self.mode).value,
            "sort": normalize_gdelt_sort_mode(self.sort).value,
            "max_records": self.max_records,
            "query_expression": self.query_expression,
            "metadata": dict(self.metadata),
        }


def normalize_gdelt_doc_mode(value: GdeltDocMode | str) -> GdeltDocMode:
    """Normalize GDELT DOC mode."""
    if isinstance(value, GdeltDocMode):
        return value

    normalized = validate_non_empty_string(value, "GDELT DOC mode").lower()

    try:
        return GdeltDocMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in GdeltDocMode)
        raise ValueError(f"Invalid GDELT DOC mode '{value}'. Valid modes: {valid}.") from exc


def normalize_gdelt_sort_mode(value: GdeltSortMode | str) -> GdeltSortMode:
    """Normalize GDELT sort mode."""
    if isinstance(value, GdeltSortMode):
        return value

    normalized = validate_non_empty_string(value, "GDELT sort mode").lower()

    try:
        return GdeltSortMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in GdeltSortMode)
        raise ValueError(f"Invalid GDELT sort mode '{value}'. Valid modes: {valid}.") from exc


def validate_gdelt_string_list(
    values: list[str],
    field_name: str = "Values",
) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def build_gdelt_news_query(
    *,
    query_terms: list[str] | None = None,
    exact_phrase: str = "",
    symbol: str = "",
    source_country: str = "",
    source_language: str = "",
    domain: str = "",
    theme: str = "",
    timespan: str = "",
    start_datetime: str = "",
    end_datetime: str = "",
    mode: GdeltDocMode | str = GdeltDocMode.ARTLIST,
    sort: GdeltSortMode | str = GdeltSortMode.HYBRID_RELEVANCE,
    max_records: int = 10,
    metadata: dict[str, Any] | None = None,
) -> GdeltNewsQuery:
    """Build GDELT news query."""
    return GdeltNewsQuery(
        query_terms=query_terms or [],
        exact_phrase=exact_phrase,
        symbol=symbol,
        source_country=source_country,
        source_language=source_language,
        domain=domain,
        theme=theme,
        timespan=timespan,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        mode=mode,
        sort=sort,
        max_records=max_records,
        metadata=metadata or {},
    )


def gdelt_query_to_query_params(query: GdeltNewsQuery) -> dict[str, Any]:
    """Convert GDELT query to HTTP query params."""
    if not isinstance(query, GdeltNewsQuery):
        raise ValueError("Query must be GdeltNewsQuery.")

    params: dict[str, Any] = {
        "query": query.query_expression,
        "mode": normalize_gdelt_doc_mode(query.mode).value,
        "format": "json",
        "maxrecords": query.max_records,
        "sort": normalize_gdelt_sort_mode(query.sort).value,
    }

    if query.source_country.strip():
        params["sourcecountry"] = query.source_country.strip().upper()

    if query.source_language.strip():
        params["sourcelang"] = query.source_language.strip().lower()

    if query.domain.strip():
        params["domain"] = query.domain.strip().lower()

    if query.theme.strip():
        params["theme"] = query.theme.strip()

    if query.timespan.strip():
        params["timespan"] = query.timespan.strip()

    if query.start_datetime.strip():
        params["startdatetime"] = query.start_datetime.strip()

    if query.end_datetime.strip():
        params["enddatetime"] = query.end_datetime.strip()

    return params


def build_gdelt_connector_definition() -> LiveNewsConnectorDefinition:
    """Build GDELT live connector definition."""
    endpoint = build_live_news_connector_endpoint(
        base_url="https://api.gdeltproject.org",
        endpoint="/api/v2/doc/doc",
        payload_key="articles",
        default_query_params={
            "format": "json",
            "mode": "artlist",
        },
        default_headers={
            "Accept": "application/json",
            "User-Agent": "AQOS/0.27 GDELT connector",
        },
        timeout_seconds=30,
    )

    return build_live_news_connector_definition(
        connector_id="gdelt",
        name="GDELT DOC 2.0",
        category="global_news",
        endpoint=endpoint,
        auth_type="none",
        status="ready",
        capabilities=list_default_live_connector_capabilities(category="global_news"),
        keyword_query_param="query",
        country_query_param="sourcecountry",
        description="Public global news connector using the GDELT DOC 2.0 API.",
        metadata={
            "official": True,
            "requires_api_key": False,
        },
    )


def build_gdelt_runtime_config(
    *,
    query: GdeltNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorRuntimeConfig:
    """Build GDELT runtime config."""
    query = query or build_gdelt_news_query(query_terms=["markets"])

    if not isinstance(query, GdeltNewsQuery):
        raise ValueError("Query must be GdeltNewsQuery.")

    return build_live_news_connector_runtime_config(
        connector=build_gdelt_connector_definition(),
        credentials=credentials or NewsProviderCredentials(),
        symbol=query.symbol,
        keywords=[],
        country=query.source_country,
        query_params=gdelt_query_to_query_params(query),
        headers=headers or {},
        payload_key="articles",
        metadata={
            **query.metadata,
            **(metadata or {}),
        },
    )


def build_gdelt_http_config(
    *,
    query: GdeltNewsQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderConfig:
    """Build HTTP config for GDELT."""
    runtime_config = build_gdelt_runtime_config(
        query=query,
        credentials=credentials,
        headers=headers,
        metadata=metadata,
    )

    return live_connector_runtime_to_http_config(runtime_config)


def gdelt_raw_row_to_normalized_news_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one GDELT row into AQOS-compatible news row."""
    validate_metadata(row, "GDELT row")

    return {
        "article_id": str(row.get("article_id") or row.get("id") or row.get("url") or ""),
        "published_at": str(row.get("published_at") or row.get("seendate") or row.get("timestamp") or ""),
        "title": str(row.get("title") or ""),
        "source": str(row.get("source") or row.get("domain") or ""),
        "source_type": "news_api",
        "url": str(row.get("url") or row.get("url_mobile") or ""),
        "description": str(row.get("description") or row.get("summary") or ""),
        "content": str(row.get("content") or ""),
        "language": str(row.get("language") or row.get("sourcelang") or ""),
        "country": str(row.get("country") or row.get("sourcecountry") or ""),
        "symbol": str(row.get("symbol") or ""),
        "topics": list(row.get("topics") or ["macro"]),
        "event_type": str(row.get("event_type") or "news"),
        "impact": str(row.get("impact") or "unknown"),
        "sentiment": str(row.get("sentiment") or "unknown"),
        "relevance_score": float(row.get("relevance_score") or 0.0),
        "provider_id": str(row.get("provider_id") or "gdelt"),
        "metadata": {
            "gdelt_domain": row.get("domain", ""),
            "gdelt_language": row.get("language", row.get("sourcelang", "")),
            "gdelt_source_country": row.get("sourcecountry", ""),
        },
        "raw_payload": dict(row),
    }


def normalize_gdelt_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    payload_key: str = "articles",
) -> dict[str, list[dict[str, Any]]]:
    """Normalize GDELT payload rows."""
    rows = extract_rows_from_http_news_payload(payload, key=payload_key)

    return {
        payload_key: [
            gdelt_raw_row_to_normalized_news_row(row)
            for row in rows
        ]
    }


def load_gdelt_news_feed_result(
    *,
    query: GdeltNewsQuery | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsFeedProviderResult:
    """Load GDELT news feed result."""
    config = build_gdelt_http_config(query=query)

    resolved_payload = (
        normalize_gdelt_payload(payload, payload_key="articles")
        if payload is not None
        else None
    )

    return load_http_news_feed_result(
        config,
        payload=resolved_payload,
        fetcher=fetcher,
    )


def load_gdelt_news_provider_result(
    *,
    query: GdeltNewsQuery | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load GDELT generic news provider result."""
    config = build_gdelt_http_config(query=query)

    resolved_payload = (
        normalize_gdelt_payload(payload, payload_key="articles")
        if payload is not None
        else None
    )

    return load_http_news_provider_result(
        config,
        payload=resolved_payload,
        fetcher=fetcher,
    )