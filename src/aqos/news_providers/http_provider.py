"""
AQOS HTTP news provider adapter.

This module provides a safe HTTP adapter layer for API-based news providers
such as NewsAPI, Finnhub, MarketAux, FMP, GDELT-style feeds, and custom
HTTP JSON endpoints.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from aqos.news_providers.base import (
    NewsEventRecord,
    NewsProviderAuthType,
    NewsProviderCapability,
    NewsProviderConfig,
    NewsProviderCredentials,
    NewsProviderResult,
    NewsProviderStatus,
    NewsProviderType,
    build_news_provider_config,
    build_news_provider_result,
    news_provider_failure,
    normalize_news_provider_auth_type,
    normalize_news_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_positive_integer,
    validate_string,
)
from aqos.news_providers.local_json import (
    extract_rows_from_local_json_payload,
    raw_json_row_to_news_event_record,
    raw_json_row_to_news_feed_article,
)
from aqos.news_providers.news_feed import (
    NewsFeedArticle,
    NewsFeedProviderResult,
    NewsFeedQuery,
    build_news_feed_provider_result,
    filter_news_feed_articles,
    news_feed_articles_to_news_records,
)
from aqos.training_data.events import HistoricalEventImpact, HistoricalEventSentiment


class HttpNewsRequestMethod(str, Enum):
    """Supported HTTP request methods."""

    GET = "GET"
    POST = "POST"


class HttpNewsResponseStatus(str, Enum):
    """Supported HTTP response statuses."""

    OK = "ok"
    ERROR = "error"
    TIMEOUT = "timeout"
    INVALID_RESPONSE = "invalid_response"


@dataclass(frozen=True)
class HttpNewsProviderConfig:
    """HTTP news provider configuration."""

    provider_id: str
    name: str
    base_url: str
    endpoint: str = ""
    status: NewsProviderStatus | str = NewsProviderStatus.ACTIVE
    credentials: NewsProviderCredentials = field(default_factory=NewsProviderCredentials)
    api_key_header: str = ""
    api_key_query_param: str = ""
    default_headers: dict[str, str] = field(default_factory=dict)
    default_query_params: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    payload_key: str = ""
    symbol: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_non_empty_string(self.name, "Provider name")
        validate_non_empty_string(self.base_url, "Base URL")
        validate_string(self.endpoint, "Endpoint")

        if not isinstance(self.credentials, NewsProviderCredentials):
            raise ValueError("Credentials must be NewsProviderCredentials.")

        validate_string(self.api_key_header, "API key header")
        validate_string(self.api_key_query_param, "API key query param")
        validate_http_string_mapping(self.default_headers, "Default headers")
        validate_metadata(self.default_query_params, "Default query params")
        validate_positive_integer(self.timeout_seconds, "Timeout seconds")
        validate_string(self.payload_key, "Payload key")
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_metadata(self.metadata, "Metadata")

    @property
    def has_endpoint(self) -> bool:
        """Return whether config has endpoint."""
        return bool(self.endpoint.strip())

    @property
    def url(self) -> str:
        """Return resolved URL."""
        return build_http_news_url(
            base_url=self.base_url,
            endpoint=self.endpoint,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "name": self.name.strip(),
            "base_url": self.base_url.strip(),
            "endpoint": self.endpoint.strip(),
            "url": self.url,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status).strip(),
            "credentials": self.credentials.to_safe_dict(),
            "api_key_header": self.api_key_header.strip(),
            "api_key_query_param": self.api_key_query_param.strip(),
            "default_headers": dict(self.default_headers),
            "default_query_params": dict(self.default_query_params),
            "timeout_seconds": self.timeout_seconds,
            "payload_key": self.payload_key.strip(),
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "has_endpoint": self.has_endpoint,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HttpNewsProviderRequest:
    """HTTP news provider request."""

    method: HttpNewsRequestMethod | str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    query_params: dict[str, Any] = field(default_factory=dict)
    body: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 30
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_http_news_request_method(self.method)
        validate_non_empty_string(self.url, "URL")
        validate_http_string_mapping(self.headers, "Headers")
        validate_metadata(self.query_params, "Query params")
        validate_metadata(self.body, "Body")
        validate_positive_integer(self.timeout_seconds, "Timeout seconds")
        validate_metadata(self.metadata, "Metadata")

    @property
    def query_string(self) -> str:
        """Return URL query string."""
        return urlencode(self.query_params, doseq=True)

    @property
    def resolved_url(self) -> str:
        """Return URL with query params."""
        if not self.query_params:
            return self.url.strip()

        separator = "&" if "?" in self.url else "?"

        return f"{self.url.strip()}{separator}{self.query_string}"

    def to_dict(self) -> dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "method": normalize_http_news_request_method(self.method).value,
            "url": self.url.strip(),
            "resolved_url": self.resolved_url,
            "headers": dict(self.headers),
            "query_params": dict(self.query_params),
            "body": dict(self.body),
            "timeout_seconds": self.timeout_seconds,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HttpNewsProviderResponse:
    """HTTP news provider response."""

    status: HttpNewsResponseStatus | str
    status_code: int = 0
    payload: dict[str, Any] | list[dict[str, Any]] | None = None
    raw_text: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    message: str = ""
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_http_news_response_status(self.status)
        validate_non_negative_integer(self.status_code, "Status code")

        if self.payload is not None:
            validate_http_payload(self.payload)

        validate_string(self.raw_text, "Raw text")
        validate_http_string_mapping(self.headers, "Headers")
        validate_string(self.message, "Message")
        validate_non_negative_number(self.elapsed_ms, "Elapsed milliseconds")
        validate_metadata(self.metadata, "Metadata")

    @property
    def ok(self) -> bool:
        """Return whether response is successful."""
        return (
            normalize_http_news_response_status(self.status) == HttpNewsResponseStatus.OK
            and 200 <= self.status_code < 300
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "status": normalize_http_news_response_status(self.status).value,
            "status_code": self.status_code,
            "ok": self.ok,
            "payload": self.payload,
            "raw_text": self.raw_text,
            "headers": dict(self.headers),
            "message": self.message.strip(),
            "elapsed_ms": float(self.elapsed_ms),
            "metadata": dict(self.metadata),
        }


HttpNewsFetcher = Callable[[HttpNewsProviderRequest], HttpNewsProviderResponse | dict[str, Any] | list[dict[str, Any]] | str]


def normalize_http_news_request_method(value: HttpNewsRequestMethod | str) -> HttpNewsRequestMethod:
    """Normalize HTTP news request method."""
    if isinstance(value, HttpNewsRequestMethod):
        return value

    normalized = validate_non_empty_string(value, "HTTP method").upper()

    try:
        return HttpNewsRequestMethod(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HttpNewsRequestMethod)
        raise ValueError(f"Invalid HTTP method '{value}'. Valid methods: {valid}.") from exc


def normalize_http_news_response_status(
    value: HttpNewsResponseStatus | str,
) -> HttpNewsResponseStatus:
    """Normalize HTTP news response status."""
    if isinstance(value, HttpNewsResponseStatus):
        return value

    normalized = validate_non_empty_string(value, "HTTP response status").lower()

    try:
        return HttpNewsResponseStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HttpNewsResponseStatus)
        raise ValueError(
            f"Invalid HTTP response status '{value}'. Valid statuses: {valid}.",
        ) from exc


def validate_http_string_mapping(value: dict[str, str], field_name: str) -> dict[str, str]:
    """Validate string-to-string mapping."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    for key, item in value.items():
        validate_non_empty_string(key, field_name)
        validate_string(item, field_name)

    return value


def validate_non_negative_number(value: int | float, field_name: str) -> float:
    """Validate non-negative number."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    numeric = float(value)

    if numeric < 0:
        raise ValueError(f"{field_name} must be a non-negative number.")

    return numeric


def validate_http_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
) -> dict[str, Any] | list[dict[str, Any]]:
    """Validate HTTP payload."""
    if isinstance(payload, dict):
        return payload

    if isinstance(payload, list):
        for row in payload:
            validate_metadata(row, "Payload row")

        return payload

    raise ValueError("Payload must be a dictionary or list of dictionaries.")


def build_http_news_provider_config(
    *,
    provider_id: str,
    name: str,
    base_url: str,
    endpoint: str = "",
    status: NewsProviderStatus | str = NewsProviderStatus.ACTIVE,
    credentials: NewsProviderCredentials | None = None,
    api_key_header: str = "",
    api_key_query_param: str = "",
    default_headers: dict[str, str] | None = None,
    default_query_params: dict[str, Any] | None = None,
    timeout_seconds: int = 30,
    payload_key: str = "",
    symbol: str = "",
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderConfig:
    """Build HTTP news provider config."""
    return HttpNewsProviderConfig(
        provider_id=provider_id,
        name=name,
        base_url=base_url,
        endpoint=endpoint,
        status=status,
        credentials=credentials or NewsProviderCredentials(),
        api_key_header=api_key_header,
        api_key_query_param=api_key_query_param,
        default_headers=default_headers or {},
        default_query_params=default_query_params or {},
        timeout_seconds=timeout_seconds,
        payload_key=payload_key,
        symbol=symbol,
        metadata=metadata or {},
    )


def build_http_news_provider_base_config(
    *,
    provider_id: str,
    name: str,
    base_url: str = "",
    status: NewsProviderStatus | str = NewsProviderStatus.ACTIVE,
    metadata: dict[str, Any] | None = None,
) -> NewsProviderConfig:
    """Build generic news provider config for HTTP provider."""
    return build_news_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=NewsProviderType.HTTP,
        base_url=base_url,
        status=status,
        capabilities=[
            NewsProviderCapability.HISTORICAL_NEWS,
            NewsProviderCapability.LIVE_NEWS,
            NewsProviderCapability.KEYWORD_FILTERING,
            NewsProviderCapability.SYMBOL_MAPPING,
            NewsProviderCapability.COUNTRY_FILTERING,
            NewsProviderCapability.SENTIMENT,
            NewsProviderCapability.IMPACT_CLASSIFICATION,
        ],
        metadata=metadata or {},
    )


def build_http_news_url(*, base_url: str, endpoint: str = "") -> str:
    """Build HTTP provider URL."""
    base = validate_non_empty_string(base_url, "Base URL").strip()
    validate_string(endpoint, "Endpoint")

    if not endpoint.strip():
        return base

    if endpoint.strip().lower().startswith(("http://", "https://")):
        return endpoint.strip()

    return f"{base.rstrip('/')}/{endpoint.strip().lstrip('/')}"


def build_http_auth_headers(
    credentials: NewsProviderCredentials,
    *,
    api_key_header: str = "",
) -> dict[str, str]:
    """Build HTTP auth headers."""
    if not isinstance(credentials, NewsProviderCredentials):
        raise ValueError("Credentials must be NewsProviderCredentials.")

    auth_type = normalize_news_provider_auth_type(credentials.auth_type)
    headers: dict[str, str] = {}

    if auth_type == NewsProviderAuthType.API_KEY and api_key_header.strip() and credentials.api_key.strip():
        headers[api_key_header.strip()] = credentials.api_key.strip()

    if auth_type == NewsProviderAuthType.BEARER_TOKEN and credentials.bearer_token.strip():
        headers["Authorization"] = f"Bearer {credentials.bearer_token.strip()}"

    if auth_type == NewsProviderAuthType.OAUTH and credentials.bearer_token.strip():
        headers["Authorization"] = f"Bearer {credentials.bearer_token.strip()}"

    if auth_type == NewsProviderAuthType.BASIC and credentials.username.strip() and credentials.password.strip():
        token = f"{credentials.username.strip()}:{credentials.password.strip()}".encode("utf-8")
        headers["Authorization"] = f"Basic {base64.b64encode(token).decode('utf-8')}"

    return headers


def build_http_auth_query_params(
    credentials: NewsProviderCredentials,
    *,
    api_key_query_param: str = "",
) -> dict[str, Any]:
    """Build HTTP auth query params."""
    if not isinstance(credentials, NewsProviderCredentials):
        raise ValueError("Credentials must be NewsProviderCredentials.")

    auth_type = normalize_news_provider_auth_type(credentials.auth_type)

    if (
        auth_type == NewsProviderAuthType.API_KEY
        and api_key_query_param.strip()
        and credentials.api_key.strip()
    ):
        return {api_key_query_param.strip(): credentials.api_key.strip()}

    return {}


def build_http_news_headers(
    config: HttpNewsProviderConfig,
    *,
    headers: dict[str, str] | None = None,
) -> dict[str, str]:
    """Build merged HTTP headers."""
    if not isinstance(config, HttpNewsProviderConfig):
        raise ValueError("Config must be HttpNewsProviderConfig.")

    extra_headers = headers or {}
    validate_http_string_mapping(extra_headers, "Headers")

    return {
        **config.default_headers,
        **build_http_auth_headers(
            config.credentials,
            api_key_header=config.api_key_header,
        ),
        **extra_headers,
    }


def build_http_news_query_params(
    config: HttpNewsProviderConfig,
    *,
    query_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build merged HTTP query params."""
    if not isinstance(config, HttpNewsProviderConfig):
        raise ValueError("Config must be HttpNewsProviderConfig.")

    extra_query_params = query_params or {}
    validate_metadata(extra_query_params, "Query params")

    return {
        **config.default_query_params,
        **build_http_auth_query_params(
            config.credentials,
            api_key_query_param=config.api_key_query_param,
        ),
        **extra_query_params,
    }


def build_http_news_provider_request(
    config: HttpNewsProviderConfig,
    *,
    method: HttpNewsRequestMethod | str = HttpNewsRequestMethod.GET,
    endpoint: str = "",
    headers: dict[str, str] | None = None,
    query_params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderRequest:
    """Build HTTP news provider request from config."""
    if not isinstance(config, HttpNewsProviderConfig):
        raise ValueError("Config must be HttpNewsProviderConfig.")

    resolved_url = build_http_news_url(
        base_url=config.base_url,
        endpoint=endpoint or config.endpoint,
    )

    return HttpNewsProviderRequest(
        method=method,
        url=resolved_url,
        headers=build_http_news_headers(config, headers=headers),
        query_params=build_http_news_query_params(config, query_params=query_params),
        body=body or {},
        timeout_seconds=config.timeout_seconds,
        metadata={
            "provider_id": config.provider_id,
            **(metadata or {}),
        },
    )


def build_http_news_provider_response(
    *,
    status: HttpNewsResponseStatus | str,
    status_code: int = 0,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    raw_text: str = "",
    headers: dict[str, str] | None = None,
    message: str = "",
    elapsed_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> HttpNewsProviderResponse:
    """Build HTTP news provider response."""
    return HttpNewsProviderResponse(
        status=status,
        status_code=status_code,
        payload=payload,
        raw_text=raw_text,
        headers=headers or {},
        message=message,
        elapsed_ms=elapsed_ms,
        metadata=metadata or {},
    )


def parse_http_news_response_payload(
    response: HttpNewsProviderResponse,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Parse HTTP response payload."""
    if not isinstance(response, HttpNewsProviderResponse):
        raise ValueError("Response must be HttpNewsProviderResponse.")

    if response.payload is not None:
        return validate_http_payload(response.payload)

    if not response.raw_text.strip():
        raise ValueError("HTTP response has no payload.")

    try:
        payload = json.loads(response.raw_text)
    except json.JSONDecodeError as exc:
        preview = response.raw_text.strip().replace("\n", " ")[:200]
        raise ValueError(
            f"HTTP response raw text is not valid JSON. Preview: {preview}"
        ) from exc

    return validate_http_payload(payload)


def execute_http_news_request(
    request: HttpNewsProviderRequest,
    *,
    fetcher: HttpNewsFetcher | None = None,
) -> HttpNewsProviderResponse:
    """Execute HTTP news request."""
    if not isinstance(request, HttpNewsProviderRequest):
        raise ValueError("Request must be HttpNewsProviderRequest.")

    if fetcher is not None:
        fetched = fetcher(request)

        if isinstance(fetched, HttpNewsProviderResponse):
            return fetched

        if isinstance(fetched, dict | list):
            return build_http_news_provider_response(
                status=HttpNewsResponseStatus.OK,
                status_code=200,
                payload=fetched,
                message="Fetched HTTP payload.",
            )

        if isinstance(fetched, str):
            return build_http_news_provider_response(
                status=HttpNewsResponseStatus.OK,
                status_code=200,
                raw_text=fetched,
                message="Fetched HTTP raw text.",
            )

        raise ValueError("Fetcher must return HttpNewsProviderResponse, dict, list, or string.")

    data = None

    if normalize_http_news_request_method(request.method) == HttpNewsRequestMethod.POST:
        data = json.dumps(request.body).encode("utf-8")

    urllib_request = Request(
        request.resolved_url,
        data=data,
        headers=request.headers,
        method=normalize_http_news_request_method(request.method).value,
    )

    try:
        with urlopen(urllib_request, timeout=request.timeout_seconds) as response:  # nosec B310
            raw_text = response.read().decode("utf-8", errors="replace")

            return build_http_news_provider_response(
                status=HttpNewsResponseStatus.OK,
                status_code=int(response.status),
                raw_text=raw_text,
                headers=dict(response.headers),
                message="HTTP request completed.",
            )
    except HTTPError as exc:
        raw_text = ""

        try:
            raw_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            raw_text = ""

        return build_http_news_provider_response(
            status=HttpNewsResponseStatus.ERROR,
            status_code=int(exc.code),
            raw_text=raw_text,
            headers=dict(exc.headers or {}),
            message=f"HTTP request failed: {exc.code} {exc.reason}",
        )
    except TimeoutError as exc:
        return build_http_news_provider_response(
            status=HttpNewsResponseStatus.TIMEOUT,
            status_code=0,
            message=f"HTTP request timed out: {exc}",
        )
    except URLError as exc:
        return build_http_news_provider_response(
            status=HttpNewsResponseStatus.ERROR,
            status_code=0,
            message=f"HTTP request failed: {exc.reason}",
        )


def prepare_http_json_row(
    row: dict[str, Any],
    *,
    provider_id: str = "",
    default_symbol: str = "",
) -> dict[str, Any]:
    """Prepare HTTP JSON row for AQOS converters."""
    validate_metadata(row, "HTTP JSON row")

    prepared = dict(row)

    if not prepared.get("provider_id") and provider_id:
        prepared["provider_id"] = provider_id

    if not prepared.get("symbol") and default_symbol:
        prepared["symbol"] = default_symbol

    if not prepared.get("source_type"):
        prepared["source_type"] = "news_api"

    if not prepared.get("impact"):
        prepared["impact"] = HistoricalEventImpact.UNKNOWN.value

    if not prepared.get("sentiment"):
        prepared["sentiment"] = HistoricalEventSentiment.UNKNOWN.value

    return prepared


def extract_rows_from_http_news_payload(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    key: str = "",
) -> list[dict[str, Any]]:
    """Extract rows from HTTP news payload."""
    return extract_rows_from_local_json_payload(payload, key=key)


def http_json_rows_to_news_feed_articles(
    rows: list[dict[str, Any]],
    *,
    provider_id: str = "",
    default_symbol: str = "",
) -> list[NewsFeedArticle]:
    """Convert HTTP JSON rows to news feed articles."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    return [
        raw_json_row_to_news_feed_article(
            prepare_http_json_row(
                row,
                provider_id=provider_id,
                default_symbol=default_symbol,
            ),
            provider_id=provider_id,
            default_symbol=default_symbol,
        )
        for row in rows
    ]


def http_json_rows_to_news_event_records(
    rows: list[dict[str, Any]],
    *,
    provider_id: str = "",
    default_symbol: str = "",
) -> list[NewsEventRecord]:
    """Convert HTTP JSON rows to news event records."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    return [
        raw_json_row_to_news_event_record(
            prepare_http_json_row(
                row,
                provider_id=provider_id,
                default_symbol=default_symbol,
            ),
            provider_id=provider_id,
            default_symbol=default_symbol,
        )
        for row in rows
    ]


def http_news_payload_to_feed_result(
    payload: dict[str, Any] | list[dict[str, Any]],
    *,
    config: HttpNewsProviderConfig,
    query: NewsFeedQuery | None = None,
    payload_key: str = "",
) -> NewsFeedProviderResult:
    """Convert HTTP payload to news feed result."""
    if not isinstance(config, HttpNewsProviderConfig):
        raise ValueError("Config must be HttpNewsProviderConfig.")

    rows = extract_rows_from_http_news_payload(
        payload,
        key=payload_key or config.payload_key,
    )
    articles = http_json_rows_to_news_feed_articles(
        rows,
        provider_id=config.provider_id,
        default_symbol=config.symbol,
    )

    if query is not None:
        articles = filter_news_feed_articles(
            articles,
            query=query,
        )

    return build_news_feed_provider_result(
        success=True,
        articles=articles,
        query=query,
        message="Loaded HTTP news payload.",
        provider_id=config.provider_id,
        metadata={
            "row_count": len(rows),
            "source_result_type": "http",
        },
    )


def load_http_news_feed_result(
    config: HttpNewsProviderConfig,
    *,
    query: NewsFeedQuery | None = None,
    request: HttpNewsProviderRequest | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    payload_key: str = "",
    fetcher: HttpNewsFetcher | None = None,
) -> NewsFeedProviderResult:
    """Load HTTP news feed result."""
    if not isinstance(config, HttpNewsProviderConfig):
        raise ValueError("Config must be HttpNewsProviderConfig.")

    resolved_payload = payload

    if resolved_payload is None:
        resolved_request = request or build_http_news_provider_request(config)
        response = execute_http_news_request(
            resolved_request,
            fetcher=fetcher,
        )

        if not response.ok:
            raise ValueError(response.message or f"HTTP request failed with status {response.status_code}.")

        resolved_payload = parse_http_news_response_payload(response)

    return http_news_payload_to_feed_result(
        resolved_payload,
        config=config,
        query=query,
        payload_key=payload_key,
    )


def load_http_news_provider_result(
    config: HttpNewsProviderConfig,
    *,
    query: NewsFeedQuery | None = None,
    request: HttpNewsProviderRequest | None = None,
    payload: dict[str, Any] | list[dict[str, Any]] | None = None,
    payload_key: str = "",
    fetcher: HttpNewsFetcher | None = None,
) -> NewsProviderResult:
    """Load generic news provider result from HTTP source."""
    if not isinstance(config, HttpNewsProviderConfig):
        raise ValueError("Config must be HttpNewsProviderConfig.")

    try:
        feed_result = load_http_news_feed_result(
            config,
            query=query,
            request=request,
            payload=payload,
            payload_key=payload_key,
            fetcher=fetcher,
        )
    except ValueError as exc:
        return news_provider_failure(
            message=str(exc),
            code="http_news_provider_error",
            provider_id=config.provider_id,
            metadata={
                "url": config.url,
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
            "source_result_type": "http",
        },
    )