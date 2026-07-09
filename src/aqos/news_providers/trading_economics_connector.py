"""
AQOS Trading Economics macro calendar connector.

This module provides a named connector for Trading Economics-style macro
calendar data such as CPI, NFP, GDP, PMI, interest rates, speeches, and other
country/currency-level economic events.
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
from aqos.news_providers.economic_calendar import (
    EconomicCalendarProviderResult,
    economic_calendar_result_to_news_provider_result,
)
from aqos.news_providers.http_provider import (
    HttpNewsFetcher,
    HttpNewsProviderConfig,
    extract_rows_from_http_news_payload,
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


class TradingEconomicsCalendarEndpoint(str, Enum):
    """Supported Trading Economics macro calendar endpoints."""

    CALENDAR = "calendar"
    COUNTRY_CALENDAR = "country_calendar"
    INDICATOR_CALENDAR = "indicator_calendar"


class TradingEconomicsImportance(str, Enum):
    """Trading Economics event importance levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TradingEconomicsMacroQuery:
    """Trading Economics macro calendar query."""

    endpoint: TradingEconomicsCalendarEndpoint | str = TradingEconomicsCalendarEndpoint.CALENDAR
    countries: list[str] = field(default_factory=list)
    indicators: list[str] = field(default_factory=list)
    importance: TradingEconomicsImportance | str = TradingEconomicsImportance.UNKNOWN
    from_date: str = ""
    to_date: str = ""
    limit: int = 50
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_trading_economics_calendar_endpoint(self.endpoint)
        validate_trading_economics_string_list(self.countries, "Countries")
        validate_trading_economics_string_list(self.indicators, "Indicators")
        normalize_trading_economics_importance(self.importance)
        validate_string(self.from_date, "From date")
        validate_string(self.to_date, "To date")
        validate_positive_integer(self.limit, "Limit")
        validate_metadata(self.metadata, "Metadata")

    @property
    def country_expression(self) -> str:
        """Return comma-separated country expression."""
        return ",".join(country.strip() for country in self.countries if country.strip())

    @property
    def indicator_expression(self) -> str:
        """Return comma-separated indicator expression."""
        return ",".join(indicator.strip() for indicator in self.indicators if indicator.strip())

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "endpoint": normalize_trading_economics_calendar_endpoint(self.endpoint).value,
            "countries": [country.strip() for country in self.countries],
            "country_expression": self.country_expression,
            "indicators": [indicator.strip() for indicator in self.indicators],
            "indicator_expression": self.indicator_expression,
            "importance": normalize_trading_economics_importance(self.importance).value,
            "from_date": self.from_date.strip(),
            "to_date": self.to_date.strip(),
            "limit": self.limit,
            "metadata": dict(self.metadata),
        }


def normalize_trading_economics_calendar_endpoint(
    value: TradingEconomicsCalendarEndpoint | str,
) -> TradingEconomicsCalendarEndpoint:
    """Normalize Trading Economics calendar endpoint."""
    if isinstance(value, TradingEconomicsCalendarEndpoint):
        return value

    normalized = validate_non_empty_string(
        value,
        "Trading Economics calendar endpoint",
    ).lower()

    try:
        return TradingEconomicsCalendarEndpoint(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TradingEconomicsCalendarEndpoint)
        raise ValueError(
            f"Invalid Trading Economics calendar endpoint '{value}'. "
            f"Valid endpoints: {valid}.",
        ) from exc


def normalize_trading_economics_importance(
    value: TradingEconomicsImportance | str,
) -> TradingEconomicsImportance:
    """Normalize Trading Economics importance."""
    if isinstance(value, TradingEconomicsImportance):
        return value

    normalized = validate_non_empty_string(
        value,
        "Trading Economics importance",
    ).lower()

    try:
        return TradingEconomicsImportance(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TradingEconomicsImportance)
        raise ValueError(
            f"Invalid Trading Economics importance '{value}'. "
            f"Valid values: {valid}.",
        ) from exc


def validate_trading_economics_string_list(
    values: list[str],
    field_name: str = "Values",
) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def build_trading_economics_macro_query(
    *,
    endpoint: TradingEconomicsCalendarEndpoint | str = TradingEconomicsCalendarEndpoint.CALENDAR,
    countries: list[str] | None = None,
    indicators: list[str] | None = None,
    importance: TradingEconomicsImportance | str = TradingEconomicsImportance.UNKNOWN,
    from_date: str = "",
    to_date: str = "",
    limit: int = 50,
    metadata: dict[str, Any] | None = None,
) -> TradingEconomicsMacroQuery:
    """Build Trading Economics macro query."""
    return TradingEconomicsMacroQuery(
        endpoint=endpoint,
        countries=countries or [],
        indicators=indicators or [],
        importance=importance,
        from_date=from_date,
        to_date=to_date,
        limit=limit,
        metadata=metadata or {},
    )


def trading_economics_query_to_query_params(
    query: TradingEconomicsMacroQuery,
) -> dict[str, Any]:
    """Convert Trading Economics query to HTTP query params."""
    if not isinstance(query, TradingEconomicsMacroQuery):
        raise ValueError("Query must be TradingEconomicsMacroQuery.")

    params: dict[str, Any] = {
        "format": "json",
        "limit": query.limit,
    }

    if query.country_expression:
        params["country"] = query.country_expression

    if query.indicator_expression:
        params["indicator"] = query.indicator_expression

    if query.from_date.strip():
        params["d1"] = query.from_date.strip()

    if query.to_date.strip():
        params["d2"] = query.to_date.strip()

    importance = normalize_trading_economics_importance(query.importance)

    if importance != TradingEconomicsImportance.UNKNOWN:
        params["importance"] = importance.value

    return params


def build_trading_economics_connector_definition(
    *,
    endpoint: TradingEconomicsCalendarEndpoint | str = TradingEconomicsCalendarEndpoint.CALENDAR,
) -> LiveNewsConnectorDefinition:
    """Build Trading Economics connector definition."""
    normalized_endpoint = normalize_trading_economics_calendar_endpoint(endpoint)

    endpoint_path = "/calendar"

    connector_endpoint = build_live_news_connector_endpoint(
        base_url="https://api.tradingeconomics.com",
        endpoint=endpoint_path,
        payload_key="data",
        default_query_params={
            "format": "json",
        },
        default_headers={
            "Accept": "application/json",
            "User-Agent": "AQOS/0.27 TradingEconomics connector",
        },
        timeout_seconds=30,
        metadata={
            "trading_economics_endpoint": normalized_endpoint.value,
        },
    )

    return build_live_news_connector_definition(
        connector_id="trading_economics",
        name="Trading Economics Calendar",
        category="macro_calendar",
        endpoint=connector_endpoint,
        auth_type="api_key",
        status="needs_api_key",
        capabilities=list_default_live_connector_capabilities(category="macro_calendar"),
        api_key_query_param="c",
        country_query_param="country",
        description="Trading Economics-style macro calendar connector requiring credentials.",
        metadata={
            "official": True,
            "requires_api_key": True,
            "endpoint": normalized_endpoint.value,
            "payload_key": "data",
        },
    )


def build_trading_economics_runtime_config(
    *,
    query: TradingEconomicsMacroQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorRuntimeConfig:
    """Build Trading Economics runtime config."""
    query = query or build_trading_economics_macro_query()

    if not isinstance(query, TradingEconomicsMacroQuery):
        raise ValueError("Query must be TradingEconomicsMacroQuery.")

    return build_live_news_connector_runtime_config(
        connector=build_trading_economics_connector_definition(endpoint=query.endpoint),
        credentials=credentials or NewsProviderCredentials(auth_type="api_key"),
        country="",
        query_params=trading_economics_query_to_query_params(query),
        headers=headers or {},
        payload_key="data",
        metadata={
            **query.metadata,
            **(metadata or {}),
        },
    )


def build_trading_economics_http_config(
    *,
    query: TradingEconomicsMacroQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    headers: dict[str, str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderConfig:
    """Build HTTP config for Trading Economics."""
    runtime_config = build_trading_economics_runtime_config(
        query=query,
        credentials=credentials,
        headers=headers,
        metadata=metadata,
    )

    return live_connector_runtime_to_http_config(runtime_config)


def trading_economics_importance_to_impact(value: Any) -> str:
    """Map Trading Economics importance to AQOS impact."""
    raw = str(value or "").strip().lower()

    if raw in {"3", "high", "important"}:
        return "high"

    if raw in {"2", "medium", "moderate"}:
        return "medium"

    if raw in {"1", "low"}:
        return "low"

    return "unknown"


def trading_economics_surprise_to_sentiment(
    *,
    actual: Any,
    forecast: Any,
    previous: Any = None,
) -> str:
    """Infer simple sentiment from actual versus forecast/previous."""
    actual_number = safe_float(actual)
    reference_number = safe_float(forecast)

    if reference_number is None:
        reference_number = safe_float(previous)

    if actual_number is None or reference_number is None:
        return "unknown"

    if actual_number > reference_number:
        return "bullish"

    if actual_number < reference_number:
        return "bearish"

    return "neutral"


def safe_float(value: Any) -> float | None:
    """Safely convert value to float."""
    if value is None:
        return None

    try:
        cleaned = str(value).replace("%", "").replace(",", "").strip()

        if not cleaned:
            return None

        return float(cleaned)
    except (TypeError, ValueError):
        return None


def trading_economics_raw_row_to_normalized_macro_row(
    row: dict[str, Any],
) -> dict[str, Any]:
    """Normalize one Trading Economics row into AQOS-compatible news row."""
    validate_metadata(row, "Trading Economics row")

    title = str(
        row.get("Event")
        or row.get("event")
        or row.get("Calendar")
        or row.get("calendar")
        or row.get("Indicator")
        or row.get("indicator")
        or "Economic calendar event"
    )
    timestamp = str(
        row.get("Date")
        or row.get("date")
        or row.get("DateTime")
        or row.get("datetime")
        or row.get("LastUpdate")
        or row.get("last_update")
        or ""
    )
    country = str(row.get("Country") or row.get("country") or "")
    currency = str(row.get("Currency") or row.get("currency") or "")
    category = str(row.get("Category") or row.get("category") or row.get("Indicator") or "")
    importance = row.get("Importance") or row.get("importance") or ""
    actual = row.get("Actual") or row.get("actual")
    forecast = row.get("Forecast") or row.get("forecast")
    previous = row.get("Previous") or row.get("previous")
    impact = trading_economics_importance_to_impact(importance)
    sentiment = trading_economics_surprise_to_sentiment(
        actual=actual,
        forecast=forecast,
        previous=previous,
    )

    event_id = str(
        row.get("Id")
        or row.get("id")
        or row.get("Ticker")
        or row.get("ticker")
        or f"{timestamp}-{country}-{title}"
    )

    description = (
        f"{country} {title}. "
        f"Actual={actual or ''}, Forecast={forecast or ''}, Previous={previous or ''}."
    ).strip()

    return {
        "event_id": event_id,
        "article_id": event_id,
        "timestamp": timestamp,
        "published_at": timestamp,
        "title": title,
        "source": "Trading Economics",
        "source_type": "economic_calendar",
        "url": str(row.get("URL") or row.get("url") or ""),
        "description": description,
        "content": description,
        "language": "en",
        "country": country,
        "currency": currency,
        "symbol": currency,
        "topics": ["macro"],
        "event_type": "economic_calendar",
        "impact": impact,
        "sentiment": sentiment,
        "relevance_score": 1.0 if impact in {"high", "critical"} else 0.5,
        "provider_id": "trading_economics",
        "metadata": {
            "category": category,
            "importance": importance,
            "actual": actual,
            "forecast": forecast,
            "previous": previous,
            "unit": row.get("Unit") or row.get("unit") or "",
            "ticker": row.get("Ticker") or row.get("ticker") or "",
        },
        "raw_payload": dict(row),
    }


def normalize_trading_economics_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    payload_key: str = "data",
) -> dict[str, list[dict[str, Any]]]:
    """Normalize Trading Economics payload rows."""
    rows = extract_rows_from_http_news_payload(payload, key=payload_key)

    normalized_rows = []

    for row in rows:
        normalized_row = trading_economics_raw_row_to_normalized_macro_row(row)

        # Generic HTTP feed conversion only accepts known feed source types.
        # Keep raw TE normalization as economic_calendar, but use news_api
        # when passing through the generic HTTP news conversion layer.
        normalized_row["source_type"] = "news_api"

        normalized_rows.append(normalized_row)

    return {
        payload_key: normalized_rows,
    }


def load_trading_economics_news_provider_result(
    *,
    query: TradingEconomicsMacroQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load Trading Economics generic news provider result."""
    config = build_trading_economics_http_config(
        query=query,
        credentials=credentials,
    )

    resolved_payload = (
        normalize_trading_economics_payload(payload, payload_key="data")
        if payload is not None
        else None
    )

    resolved_fetcher = None

    if fetcher is not None:
        def resolved_fetcher(request):
            raw_payload = fetcher(request)
            return normalize_trading_economics_payload(
                raw_payload,
                payload_key="data",
            )

    return load_http_news_provider_result(
        config,
        payload=resolved_payload,
        fetcher=resolved_fetcher,
    )


def trading_economics_provider_result_to_calendar_result(
    provider_result: NewsProviderResult,
) -> EconomicCalendarProviderResult:
    """Convert Trading Economics provider result into calendar-style result."""
    if not isinstance(provider_result, NewsProviderResult):
        raise ValueError("Provider result must be NewsProviderResult.")

    import inspect

    from aqos.news_providers.economic_calendar import (
        build_economic_calendar_event,
        build_economic_calendar_provider_result,
    )

    def metadata_value(metadata: dict[str, Any], key: str, *fallback_keys: str) -> Any:
        """Read value from flat/nested Trading Economics metadata."""
        keys = (key, *fallback_keys)

        for lookup_key in keys:
            if lookup_key in metadata and metadata.get(lookup_key) not in {None, ""}:
                return metadata.get(lookup_key)

        nested_metadata = metadata.get("metadata", {})
        if isinstance(nested_metadata, dict):
            for lookup_key in keys:
                if lookup_key in nested_metadata and nested_metadata.get(lookup_key) not in {None, ""}:
                    return nested_metadata.get(lookup_key)

        raw_payload = metadata.get("raw_payload", {})
        if isinstance(raw_payload, dict):
            for lookup_key in keys:
                if lookup_key in raw_payload and raw_payload.get(lookup_key) not in {None, ""}:
                    return raw_payload.get(lookup_key)

        return ""

    events = []
    event_signature = inspect.signature(build_economic_calendar_event)

    for record in provider_result.records:
        metadata = dict(record.metadata or {})

        actual_raw = metadata_value(metadata, "actual", "Actual")
        forecast_raw = metadata_value(metadata, "forecast", "Forecast")
        previous_raw = metadata_value(metadata, "previous", "Previous")

        actual_value = safe_float(actual_raw)
        forecast_value = safe_float(forecast_raw)
        previous_value = safe_float(previous_raw)

        event_kwargs = {
            "event_id": record.event_id,
            "timestamp": record.timestamp,
            "country": record.country,
            "currency": record.currency,
            "title": record.title,
            "name": record.title,
            "event_name": record.title,
            "category": metadata_value(metadata, "category", "Category") or "unknown",
            "importance": record.impact,
            "actual": actual_raw,
            "actual_value": actual_value if actual_value is not None else 0.0,
            "forecast": forecast_raw,
            "forecast_value": forecast_value if forecast_value is not None else 0.0,
            "previous": previous_raw,
            "previous_value": previous_value if previous_value is not None else 0.0,
            "impact": record.impact,
            "sentiment": record.sentiment,
            "source": record.source,
            "url": record.url,
            "metadata": metadata,
        }

        filtered_event_kwargs = {
            key: value
            for key, value in event_kwargs.items()
            if key in event_signature.parameters
        }

        events.append(build_economic_calendar_event(**filtered_event_kwargs))

    result_signature = inspect.signature(build_economic_calendar_provider_result)

    result_kwargs = {
        "provider_id": "trading_economics",
        "name": "Trading Economics Calendar",
        "events": events,
        "success": provider_result.success,
        "message": provider_result.message,
        "metadata": provider_result.metadata,
    }

    filtered_result_kwargs = {
        key: value
        for key, value in result_kwargs.items()
        if key in result_signature.parameters
    }

    return build_economic_calendar_provider_result(**filtered_result_kwargs)


def load_trading_economics_calendar_result(
    *,
    query: TradingEconomicsMacroQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> EconomicCalendarProviderResult:
    """Load Trading Economics economic calendar provider result."""
    provider_result = load_trading_economics_news_provider_result(
        query=query,
        credentials=credentials,
        payload=payload,
        fetcher=fetcher,
    )

    return trading_economics_provider_result_to_calendar_result(provider_result)


def load_trading_economics_macro_provider_result(
    *,
    query: TradingEconomicsMacroQuery | None = None,
    credentials: NewsProviderCredentials | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load Trading Economics macro provider result."""
    calendar_result = load_trading_economics_calendar_result(
        query=query,
        credentials=credentials,
        payload=payload,
        fetcher=fetcher,
    )

    return economic_calendar_result_to_news_provider_result(calendar_result)