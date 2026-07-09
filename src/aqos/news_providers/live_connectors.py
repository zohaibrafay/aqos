"""
AQOS live news provider connector scaffold.

This module defines provider-specific connector contracts used by real-world
news and macro integrations such as GDELT, Finnhub, Trading Economics,
NewsAPI-style providers, MarketAux-style providers, and CryptoPanic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsProviderAuthType,
    NewsProviderCapability,
    NewsProviderCredentials,
    NewsProviderType,
    normalize_news_provider_auth_type,
    normalize_news_provider_capability,
    normalize_news_provider_type,
    normalize_news_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_positive_integer,
    validate_string,
)
from aqos.news_providers.http_provider import (
    HttpNewsProviderConfig,
    build_http_news_provider_config,
    build_http_news_url,
)


class LiveNewsConnectorId(str, Enum):
    """Supported live news connector identifiers."""

    GDELT = "gdelt"
    HACKER_NEWS = "hacker_news"
    NEWS_API = "news_api"
    MARKETAUX = "marketaux"
    FINNHUB = "finnhub"
    FMP = "financial_modeling_prep"
    TRADING_ECONOMICS = "trading_economics"
    CRYPTOPANIC = "cryptopanic"
    CUSTOM_HTTP = "custom_http"
    UNKNOWN = "unknown"


class LiveNewsConnectorCategory(str, Enum):
    """Supported connector categories."""

    GLOBAL_NEWS = "global_news"
    FINANCIAL_NEWS = "financial_news"
    MACRO_CALENDAR = "macro_calendar"
    CRYPTO_NEWS = "crypto_news"
    PUBLIC_JSON = "public_json"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class LiveNewsConnectorStatus(str, Enum):
    """Supported live connector statuses."""

    READY = "ready"
    NEEDS_API_KEY = "needs_api_key"
    DISABLED = "disabled"
    EXPERIMENTAL = "experimental"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class LiveNewsConnectorEndpoint:
    """Live news connector endpoint definition."""

    base_url: str
    endpoint: str = ""
    method: str = "GET"
    payload_key: str = ""
    default_query_params: dict[str, Any] = field(default_factory=dict)
    default_headers: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.base_url, "Base URL")
        validate_string(self.endpoint, "Endpoint")
        validate_non_empty_string(self.method, "Method")
        validate_string(self.payload_key, "Payload key")
        validate_metadata(self.default_query_params, "Default query params")
        validate_string_mapping(self.default_headers, "Default headers")
        validate_positive_integer(self.timeout_seconds, "Timeout seconds")
        validate_metadata(self.metadata, "Metadata")

    @property
    def url(self) -> str:
        """Return full endpoint URL."""
        return build_http_news_url(
            base_url=self.base_url,
            endpoint=self.endpoint,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert endpoint to dictionary."""
        return {
            "base_url": self.base_url.strip(),
            "endpoint": self.endpoint.strip(),
            "url": self.url,
            "method": self.method.strip().upper(),
            "payload_key": self.payload_key.strip(),
            "default_query_params": dict(self.default_query_params),
            "default_headers": dict(self.default_headers),
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LiveNewsConnectorDefinition:
    """Live news connector definition."""

    connector_id: LiveNewsConnectorId | str
    name: str
    category: LiveNewsConnectorCategory | str
    provider_type: NewsProviderType | str = NewsProviderType.HTTP
    auth_type: NewsProviderAuthType | str = NewsProviderAuthType.NONE
    status: LiveNewsConnectorStatus | str = LiveNewsConnectorStatus.EXPERIMENTAL
    endpoint: LiveNewsConnectorEndpoint = field(
        default_factory=lambda: LiveNewsConnectorEndpoint(base_url="https://example.com"),
    )
    capabilities: list[NewsProviderCapability | str] = field(default_factory=list)
    api_key_header: str = ""
    api_key_query_param: str = ""
    symbol_query_param: str = ""
    keyword_query_param: str = ""
    country_query_param: str = ""
    currency_query_param: str = ""
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_live_news_connector_id(self.connector_id)
        validate_non_empty_string(self.name, "Connector name")
        normalize_live_news_connector_category(self.category)
        normalize_news_provider_type(self.provider_type)
        normalize_news_provider_auth_type(self.auth_type)
        normalize_live_news_connector_status(self.status)

        if not isinstance(self.endpoint, LiveNewsConnectorEndpoint):
            raise ValueError("Endpoint must be LiveNewsConnectorEndpoint.")

        validate_news_provider_capability_list(self.capabilities)
        validate_string(self.api_key_header, "API key header")
        validate_string(self.api_key_query_param, "API key query param")
        validate_string(self.symbol_query_param, "Symbol query param")
        validate_string(self.keyword_query_param, "Keyword query param")
        validate_string(self.country_query_param, "Country query param")
        validate_string(self.currency_query_param, "Currency query param")
        validate_string(self.description, "Description")
        validate_metadata(self.metadata, "Metadata")

    @property
    def requires_api_key(self) -> bool:
        """Return whether connector requires API key."""
        return normalize_news_provider_auth_type(self.auth_type) == NewsProviderAuthType.API_KEY

    @property
    def ready_without_credentials(self) -> bool:
        """Return whether connector can run without credentials."""
        return normalize_news_provider_auth_type(self.auth_type) == NewsProviderAuthType.NONE

    def to_dict(self) -> dict[str, Any]:
        """Convert definition to dictionary."""
        return {
            "connector_id": normalize_live_news_connector_id(self.connector_id).value,
            "name": self.name.strip(),
            "category": normalize_live_news_connector_category(self.category).value,
            "provider_type": normalize_news_provider_type(self.provider_type).value,
            "auth_type": normalize_news_provider_auth_type(self.auth_type).value,
            "status": normalize_live_news_connector_status(self.status).value,
            "endpoint": self.endpoint.to_dict(),
            "capabilities": [
                normalize_news_provider_capability(capability).value
                for capability in self.capabilities
            ],
            "api_key_header": self.api_key_header.strip(),
            "api_key_query_param": self.api_key_query_param.strip(),
            "symbol_query_param": self.symbol_query_param.strip(),
            "keyword_query_param": self.keyword_query_param.strip(),
            "country_query_param": self.country_query_param.strip(),
            "currency_query_param": self.currency_query_param.strip(),
            "requires_api_key": self.requires_api_key,
            "ready_without_credentials": self.ready_without_credentials,
            "description": self.description.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LiveNewsConnectorRuntimeConfig:
    """Runtime configuration for one connector execution."""

    connector: LiveNewsConnectorDefinition
    credentials: NewsProviderCredentials = field(default_factory=NewsProviderCredentials)
    symbol: str = ""
    keywords: list[str] = field(default_factory=list)
    country: str = ""
    currency: str = ""
    query_params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    payload_key: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.connector, LiveNewsConnectorDefinition):
            raise ValueError("Connector must be LiveNewsConnectorDefinition.")

        if not isinstance(self.credentials, NewsProviderCredentials):
            raise ValueError("Credentials must be NewsProviderCredentials.")

        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_string_list(self.keywords, "Keywords")
        validate_string(self.country, "Country")
        validate_string(self.currency, "Currency")
        validate_metadata(self.query_params, "Query params")
        validate_string_mapping(self.headers, "Headers")
        validate_string(self.payload_key, "Payload key")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert runtime config to dictionary."""
        return {
            "connector": self.connector.to_dict(),
            "credentials": self.credentials.to_safe_dict(),
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "keywords": [keyword.strip().lower() for keyword in self.keywords],
            "country": self.country.strip().upper(),
            "currency": self.currency.strip().upper(),
            "query_params": dict(self.query_params),
            "headers": dict(self.headers),
            "payload_key": self.payload_key.strip(),
            "metadata": dict(self.metadata),
        }


def normalize_live_news_connector_id(
    value: LiveNewsConnectorId | str,
) -> LiveNewsConnectorId:
    """Normalize live news connector ID."""
    if isinstance(value, LiveNewsConnectorId):
        return value

    normalized = validate_non_empty_string(value, "Live news connector ID").lower()

    try:
        return LiveNewsConnectorId(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in LiveNewsConnectorId)
        raise ValueError(
            f"Invalid live news connector ID '{value}'. Valid IDs: {valid}.",
        ) from exc


def normalize_live_news_connector_category(
    value: LiveNewsConnectorCategory | str,
) -> LiveNewsConnectorCategory:
    """Normalize live news connector category."""
    if isinstance(value, LiveNewsConnectorCategory):
        return value

    normalized = validate_non_empty_string(value, "Live news connector category").lower()

    try:
        return LiveNewsConnectorCategory(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in LiveNewsConnectorCategory)
        raise ValueError(
            f"Invalid live news connector category '{value}'. Valid categories: {valid}.",
        ) from exc


def normalize_live_news_connector_status(
    value: LiveNewsConnectorStatus | str,
) -> LiveNewsConnectorStatus:
    """Normalize live news connector status."""
    if isinstance(value, LiveNewsConnectorStatus):
        return value

    normalized = validate_non_empty_string(value, "Live news connector status").lower()

    try:
        return LiveNewsConnectorStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in LiveNewsConnectorStatus)
        raise ValueError(
            f"Invalid live news connector status '{value}'. Valid statuses: {valid}.",
        ) from exc


def validate_string_mapping(value: dict[str, str], field_name: str) -> dict[str, str]:
    """Validate dictionary with string keys and string values."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    for key, item in value.items():
        validate_non_empty_string(key, field_name)
        validate_string(item, field_name)

    return value


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_news_provider_capability_list(
    capabilities: list[NewsProviderCapability | str],
) -> list[NewsProviderCapability | str]:
    """Validate news provider capability list."""
    if not isinstance(capabilities, list):
        raise ValueError("Capabilities must be a list.")

    for capability in capabilities:
        normalize_news_provider_capability(capability)

    return capabilities


def build_live_news_connector_endpoint(
    *,
    base_url: str,
    endpoint: str = "",
    method: str = "GET",
    payload_key: str = "",
    default_query_params: dict[str, Any] | None = None,
    default_headers: dict[str, str] | None = None,
    timeout_seconds: int = 30,
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorEndpoint:
    """Build live news connector endpoint."""
    return LiveNewsConnectorEndpoint(
        base_url=base_url,
        endpoint=endpoint,
        method=method,
        payload_key=payload_key,
        default_query_params=default_query_params or {},
        default_headers=default_headers or {},
        timeout_seconds=timeout_seconds,
        metadata=metadata or {},
    )


def build_live_news_connector_definition(
    *,
    connector_id: LiveNewsConnectorId | str,
    name: str,
    category: LiveNewsConnectorCategory | str,
    endpoint: LiveNewsConnectorEndpoint,
    provider_type: NewsProviderType | str = NewsProviderType.HTTP,
    auth_type: NewsProviderAuthType | str = NewsProviderAuthType.NONE,
    status: LiveNewsConnectorStatus | str = LiveNewsConnectorStatus.EXPERIMENTAL,
    capabilities: list[NewsProviderCapability | str] | None = None,
    api_key_header: str = "",
    api_key_query_param: str = "",
    symbol_query_param: str = "",
    keyword_query_param: str = "",
    country_query_param: str = "",
    currency_query_param: str = "",
    description: str = "",
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorDefinition:
    """Build live news connector definition."""
    return LiveNewsConnectorDefinition(
        connector_id=connector_id,
        name=name,
        category=category,
        provider_type=provider_type,
        auth_type=auth_type,
        status=status,
        endpoint=endpoint,
        capabilities=capabilities or [],
        api_key_header=api_key_header,
        api_key_query_param=api_key_query_param,
        symbol_query_param=symbol_query_param,
        keyword_query_param=keyword_query_param,
        country_query_param=country_query_param,
        currency_query_param=currency_query_param,
        description=description,
        metadata=metadata or {},
    )


def build_live_news_connector_runtime_config(
    *,
    connector: LiveNewsConnectorDefinition,
    credentials: NewsProviderCredentials | None = None,
    symbol: str = "",
    keywords: list[str] | None = None,
    country: str = "",
    currency: str = "",
    query_params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    payload_key: str = "",
    metadata: dict[str, Any] | None = None,
) -> LiveNewsConnectorRuntimeConfig:
    """Build live news connector runtime config."""
    return LiveNewsConnectorRuntimeConfig(
        connector=connector,
        credentials=credentials or NewsProviderCredentials(),
        symbol=symbol,
        keywords=keywords or [],
        country=country,
        currency=currency,
        query_params=query_params or {},
        headers=headers or {},
        payload_key=payload_key,
        metadata=metadata or {},
    )


def build_live_connector_query_params(
    runtime_config: LiveNewsConnectorRuntimeConfig,
) -> dict[str, Any]:
    """Build final query params for connector execution."""
    if not isinstance(runtime_config, LiveNewsConnectorRuntimeConfig):
        raise ValueError("Runtime config must be LiveNewsConnectorRuntimeConfig.")

    connector = runtime_config.connector
    endpoint = connector.endpoint

    params: dict[str, Any] = {
        **endpoint.default_query_params,
        **runtime_config.query_params,
    }

    if connector.symbol_query_param.strip() and runtime_config.symbol.strip():
        params[connector.symbol_query_param.strip()] = normalize_news_symbol(runtime_config.symbol)

    if connector.keyword_query_param.strip() and runtime_config.keywords:
        params[connector.keyword_query_param.strip()] = " OR ".join(
            keyword.strip()
            for keyword in runtime_config.keywords
        )

    if connector.country_query_param.strip() and runtime_config.country.strip():
        params[connector.country_query_param.strip()] = runtime_config.country.strip().upper()

    if connector.currency_query_param.strip() and runtime_config.currency.strip():
        params[connector.currency_query_param.strip()] = runtime_config.currency.strip().upper()

    return params


def build_live_connector_headers(
    runtime_config: LiveNewsConnectorRuntimeConfig,
) -> dict[str, str]:
    """Build final headers for connector execution."""
    if not isinstance(runtime_config, LiveNewsConnectorRuntimeConfig):
        raise ValueError("Runtime config must be LiveNewsConnectorRuntimeConfig.")

    return {
        **runtime_config.connector.endpoint.default_headers,
        **runtime_config.headers,
    }


def live_connector_runtime_to_http_config(
    runtime_config: LiveNewsConnectorRuntimeConfig,
) -> HttpNewsProviderConfig:
    """Convert live connector runtime config to HTTP provider config."""
    if not isinstance(runtime_config, LiveNewsConnectorRuntimeConfig):
        raise ValueError("Runtime config must be LiveNewsConnectorRuntimeConfig.")

    connector = runtime_config.connector
    endpoint = connector.endpoint
    payload_key = runtime_config.payload_key or endpoint.payload_key

    return build_http_news_provider_config(
        provider_id=normalize_live_news_connector_id(connector.connector_id).value,
        name=connector.name,
        base_url=endpoint.base_url,
        endpoint=endpoint.endpoint,
        credentials=runtime_config.credentials,
        api_key_header=connector.api_key_header,
        api_key_query_param=connector.api_key_query_param,
        default_headers=build_live_connector_headers(runtime_config),
        default_query_params=build_live_connector_query_params(runtime_config),
        timeout_seconds=endpoint.timeout_seconds,
        payload_key=payload_key,
        symbol=runtime_config.symbol,
        metadata={
            **connector.metadata,
            **runtime_config.metadata,
            "connector_category": normalize_live_news_connector_category(connector.category).value,
            "connector_status": normalize_live_news_connector_status(connector.status).value,
        },
    )


def connector_definition_requires_credentials(
    definition: LiveNewsConnectorDefinition,
) -> bool:
    """Return whether connector definition requires credentials."""
    if not isinstance(definition, LiveNewsConnectorDefinition):
        raise ValueError("Definition must be LiveNewsConnectorDefinition.")

    return definition.requires_api_key


def connector_runtime_has_required_credentials(
    runtime_config: LiveNewsConnectorRuntimeConfig,
) -> bool:
    """Return whether runtime config has required credentials."""
    if not isinstance(runtime_config, LiveNewsConnectorRuntimeConfig):
        raise ValueError("Runtime config must be LiveNewsConnectorRuntimeConfig.")

    definition = runtime_config.connector

    if not definition.requires_api_key:
        return True

    credentials = runtime_config.credentials

    return bool(credentials.api_key.strip())


def list_default_live_connector_capabilities(
    *,
    category: LiveNewsConnectorCategory | str,
) -> list[NewsProviderCapability]:
    """Return default capabilities for connector category."""
    normalized = normalize_live_news_connector_category(category)

    if normalized == LiveNewsConnectorCategory.MACRO_CALENDAR:
        return [
            NewsProviderCapability.LIVE_NEWS,
            NewsProviderCapability.HISTORICAL_NEWS,
            NewsProviderCapability.ECONOMIC_CALENDAR,
            NewsProviderCapability.MACRO_EVENTS,
            NewsProviderCapability.COUNTRY_FILTERING,
            NewsProviderCapability.CURRENCY_FILTERING,
        ]

    if normalized == LiveNewsConnectorCategory.CRYPTO_NEWS:
        return [
            NewsProviderCapability.LIVE_NEWS,
            NewsProviderCapability.HISTORICAL_NEWS,
            NewsProviderCapability.KEYWORD_FILTERING,
            NewsProviderCapability.SENTIMENT,
        ]

    if normalized in {
        LiveNewsConnectorCategory.GLOBAL_NEWS,
        LiveNewsConnectorCategory.FINANCIAL_NEWS,
        LiveNewsConnectorCategory.PUBLIC_JSON,
    }:
        return [
            NewsProviderCapability.LIVE_NEWS,
            NewsProviderCapability.HISTORICAL_NEWS,
            NewsProviderCapability.KEYWORD_FILTERING,
            NewsProviderCapability.SYMBOL_MAPPING,
            NewsProviderCapability.SENTIMENT,
            NewsProviderCapability.IMPACT_CLASSIFICATION,
        ]

    return [
        NewsProviderCapability.LIVE_NEWS,
        NewsProviderCapability.HISTORICAL_NEWS,
    ]