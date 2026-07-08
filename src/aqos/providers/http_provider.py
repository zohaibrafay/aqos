"""
AQOS HTTP market data provider.

This module provides dependency-free HTTP adapter helpers for provider APIs.
It uses injectable transports for tests and can use urllib for simple real HTTP
GET/POST requests.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.providers.base import (
    ProviderCapability,
    ProviderConfig,
    ProviderResult,
    ProviderStatus,
    ProviderType,
    build_provider_config,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_string,
)
from aqos.providers.market_data import (
    HistoricalOhlcvRequest,
    LiveQuoteRequest,
    MarketDataBatch,
    MarketQuote,
    MarketTick,
    TickDataRequest,
    build_market_data_batch,
    build_market_quote,
    build_market_tick,
    market_data_batch_to_provider_result,
    market_data_error_result,
    market_quote_to_provider_result,
    market_ticks_to_provider_result,
    ohlcv_rows_to_candles,
    validate_market_symbol,
    validate_market_ticks,
)


class HttpProviderMethod(str, Enum):
    """Supported HTTP provider methods."""

    GET = "GET"
    POST = "POST"


@dataclass(frozen=True)
class HttpProviderRequest:
    """HTTP provider request."""

    provider_id: str
    method: HttpProviderMethod | str
    url: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        normalize_http_provider_method(self.method)
        validate_http_url(self.url)
        validate_http_params(self.params)
        validate_http_headers(self.headers)

        if self.body is not None:
            validate_metadata(self.body, "Body")

        validate_positive_float(self.timeout_seconds, "Timeout seconds")
        validate_metadata(self.metadata, "Metadata")

    def resolved_url(self) -> str:
        """Return URL with encoded query params."""
        if not self.params:
            return self.url.strip()

        query = urllib.parse.urlencode(
            {
                key: value
                for key, value in self.params.items()
                if value is not None and value != ""
            },
        )
        separator = "&" if "?" in self.url else "?"
        return f"{self.url.strip()}{separator}{query}" if query else self.url.strip()

    def to_dict(self) -> dict[str, Any]:
        """Convert HTTP request into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "method": normalize_http_provider_method(self.method).value,
            "url": self.url.strip(),
            "resolved_url": self.resolved_url(),
            "params": dict(self.params),
            "headers": dict(self.headers),
            "body": dict(self.body) if self.body is not None else None,
            "timeout_seconds": float(self.timeout_seconds),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HttpProviderResponse:
    """HTTP provider response."""

    provider_id: str
    status_code: int
    payload: dict[str, Any] | list[Any]
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_http_status_code(self.status_code)

        if not isinstance(self.payload, dict | list):
            raise ValueError("Payload must be a dictionary or list.")

        validate_http_headers(self.headers)
        validate_non_negative_float(self.elapsed_ms, "Elapsed milliseconds")
        validate_metadata(self.metadata, "Metadata")

    @property
    def success(self) -> bool:
        """Return whether HTTP response is successful."""
        return is_success_http_status(self.status_code)

    @property
    def failed(self) -> bool:
        """Return whether HTTP response failed."""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Convert HTTP response into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "status_code": self.status_code,
            "success": self.success,
            "failed": self.failed,
            "payload": self.payload,
            "headers": dict(self.headers),
            "elapsed_ms": float(self.elapsed_ms),
            "metadata": dict(self.metadata),
        }


HttpTransport = Callable[[HttpProviderRequest], HttpProviderResponse]


@dataclass
class HttpMarketDataProvider:
    """HTTP market data provider adapter."""

    provider_config: ProviderConfig
    transport: HttpTransport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_http_provider_config(self.provider_config)

        if self.transport is not None and not callable(self.transport):
            raise ValueError("Transport must be callable.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def provider_id(self) -> str:
        """Return provider ID."""
        return self.provider_config.provider_id.strip()

    @property
    def active(self) -> bool:
        """Return whether provider is active."""
        return self.provider_config.active

    @property
    def base_url(self) -> str:
        """Return provider base URL."""
        return self.provider_config.base_url.strip()

    def request(self, request: HttpProviderRequest) -> HttpProviderResponse:
        """Execute HTTP provider request."""
        if not isinstance(request, HttpProviderRequest):
            raise ValueError("Request must be a HttpProviderRequest.")

        if request.provider_id.strip() != self.provider_id:
            raise ValueError("Request provider ID must match HTTP provider ID.")

        resolved_transport = self.transport or default_http_transport
        return resolved_transport(request)

    def fetch_historical_ohlcv(
        self,
        request: HistoricalOhlcvRequest,
        *,
        endpoint: str = "/ohlcv",
        records_key: str = "data",
        field_map: dict[str, str] | None = None,
    ) -> ProviderResult:
        """Fetch historical OHLCV from HTTP provider."""
        if not isinstance(request, HistoricalOhlcvRequest):
            raise ValueError("Request must be a HistoricalOhlcvRequest.")

        if request.provider_id.strip() != self.provider_id:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="Request provider ID does not match HTTP provider ID.",
                request_type="historical_ohlcv",
            )

        if not self.active:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="HTTP provider is not active.",
                request_type="historical_ohlcv",
            )

        if not self.provider_config.supports(ProviderCapability.HISTORICAL_OHLCV):
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="HTTP provider does not support historical OHLCV.",
                request_type="historical_ohlcv",
            )

        response = self.request(
            build_http_provider_request(
                provider_id=self.provider_id,
                method=HttpProviderMethod.GET,
                url=join_http_url(self.base_url, endpoint),
                params={
                    "symbol": validate_market_symbol(request.symbol),
                    "timeframe": str(request.timeframe).strip(),
                    "start": request.start,
                    "end": request.end,
                    "limit": request.limit,
                },
                timeout_seconds=self.provider_config.timeout_seconds,
            ),
        )

        if response.failed:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error=f"HTTP request failed with status {response.status_code}.",
                request_type="historical_ohlcv",
                metadata={
                    "status_code": response.status_code,
                },
            )

        rows = json_payload_to_ohlcv_rows(
            payload=response.payload,
            records_key=records_key,
            field_map=field_map,
        )
        candles = ohlcv_rows_to_candles(
            rows=rows,
            symbol=request.symbol,
            timeframe=request.timeframe,
            quality="validated",
        )
        batch = build_market_data_batch(
            provider_id=self.provider_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            candles=candles,
            quality="validated",
            metadata={
                "source": "http",
                "endpoint": endpoint,
                "status_code": response.status_code,
                "elapsed_ms": response.elapsed_ms,
            },
        )

        return market_data_batch_to_provider_result(batch)

    def fetch_live_quote(
        self,
        request: LiveQuoteRequest,
        *,
        endpoint: str = "/quote",
        quote_key: str = "quote",
        field_map: dict[str, str] | None = None,
    ) -> ProviderResult:
        """Fetch live quote from HTTP provider."""
        if not isinstance(request, LiveQuoteRequest):
            raise ValueError("Request must be a LiveQuoteRequest.")

        if request.provider_id.strip() != self.provider_id:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="Request provider ID does not match HTTP provider ID.",
                request_type="live_quote",
            )

        if not self.active:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="HTTP provider is not active.",
                request_type="live_quote",
            )

        if not self.provider_config.supports(ProviderCapability.LIVE_QUOTES):
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="HTTP provider does not support live quotes.",
                request_type="live_quote",
            )

        response = self.request(
            build_http_provider_request(
                provider_id=self.provider_id,
                method=HttpProviderMethod.GET,
                url=join_http_url(self.base_url, endpoint),
                params={
                    "symbol": validate_market_symbol(request.symbol),
                    "price_type": str(request.price_type).strip(),
                },
                timeout_seconds=self.provider_config.timeout_seconds,
            ),
        )

        if response.failed:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error=f"HTTP request failed with status {response.status_code}.",
                request_type="live_quote",
                metadata={
                    "status_code": response.status_code,
                },
            )

        quote = json_payload_to_market_quote(
            provider_id=self.provider_id,
            payload=response.payload,
            quote_key=quote_key,
            field_map=field_map,
        )

        return market_quote_to_provider_result(quote)

    def fetch_ticks(
        self,
        request: TickDataRequest,
        *,
        endpoint: str = "/ticks",
        records_key: str = "ticks",
        field_map: dict[str, str] | None = None,
    ) -> ProviderResult:
        """Fetch market ticks from HTTP provider."""
        if not isinstance(request, TickDataRequest):
            raise ValueError("Request must be a TickDataRequest.")

        if request.provider_id.strip() != self.provider_id:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="Request provider ID does not match HTTP provider ID.",
                request_type="ticks",
            )

        if not self.active:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="HTTP provider is not active.",
                request_type="ticks",
            )

        if not self.provider_config.supports(ProviderCapability.TICKS):
            return http_provider_error_result(
                provider_id=self.provider_id,
                error="HTTP provider does not support ticks.",
                request_type="ticks",
            )

        response = self.request(
            build_http_provider_request(
                provider_id=self.provider_id,
                method=HttpProviderMethod.GET,
                url=join_http_url(self.base_url, endpoint),
                params={
                    "symbol": validate_market_symbol(request.symbol),
                    "limit": request.limit,
                },
                timeout_seconds=self.provider_config.timeout_seconds,
            ),
        )

        if response.failed:
            return http_provider_error_result(
                provider_id=self.provider_id,
                error=f"HTTP request failed with status {response.status_code}.",
                request_type="ticks",
                metadata={
                    "status_code": response.status_code,
                },
            )

        ticks = json_payload_to_market_ticks(
            provider_id=self.provider_id,
            payload=response.payload,
            records_key=records_key,
            field_map=field_map,
        )

        return market_ticks_to_provider_result(
            provider_id=self.provider_id,
            ticks=ticks[: request.limit],
        )


def normalize_http_provider_method(method: HttpProviderMethod | str) -> HttpProviderMethod:
    """Normalize HTTP provider method."""
    if isinstance(method, HttpProviderMethod):
        return method

    normalized = validate_non_empty_string(method, "HTTP method").upper()

    try:
        return HttpProviderMethod(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in HttpProviderMethod)
        raise ValueError(
            f"Invalid HTTP method '{method}'. Valid methods: {valid}.",
        ) from exc


def validate_http_url(url: str) -> str:
    """Validate HTTP URL."""
    normalized = validate_non_empty_string(url, "URL")

    if not normalized.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://.")

    return normalized


def validate_http_status_code(status_code: int) -> int:
    """Validate HTTP status code."""
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise ValueError("Status code must be an integer.")

    if status_code < 100 or status_code > 599:
        raise ValueError("Status code must be between 100 and 599.")

    return status_code


def validate_http_params(params: dict[str, Any]) -> dict[str, Any]:
    """Validate HTTP params."""
    if not isinstance(params, dict):
        raise ValueError("Params must be a dictionary.")

    for key in params:
        validate_non_empty_string(str(key), "Param key")

    return params


def validate_http_headers(headers: dict[str, str]) -> dict[str, str]:
    """Validate HTTP headers."""
    if not isinstance(headers, dict):
        raise ValueError("Headers must be a dictionary.")

    for key, value in headers.items():
        validate_non_empty_string(str(key), "Header key")
        validate_string(value, "Header value")

    return headers


def validate_http_provider_config(config: ProviderConfig) -> ProviderConfig:
    """Validate HTTP market data provider config."""
    if not isinstance(config, ProviderConfig):
        raise ValueError("Provider config must be ProviderConfig.")

    if (
        config.provider_type != ProviderType.MARKET_DATA
        and str(config.provider_type) != ProviderType.MARKET_DATA.value
    ):
        raise ValueError("HTTP provider requires a market data provider config.")

    validate_http_url(config.base_url)

    if not (
        config.supports(ProviderCapability.HISTORICAL_OHLCV)
        or config.supports(ProviderCapability.LIVE_QUOTES)
        or config.supports(ProviderCapability.TICKS)
    ):
        raise ValueError("HTTP provider must support market data capabilities.")

    return config


def is_success_http_status(status_code: int) -> bool:
    """Return whether HTTP status code is success."""
    validate_http_status_code(status_code)
    return 200 <= status_code <= 299


def join_http_url(base_url: str, endpoint: str) -> str:
    """Join HTTP base URL and endpoint."""
    normalized_base_url = validate_http_url(base_url).rstrip("/")
    normalized_endpoint = validate_non_empty_string(endpoint, "Endpoint")

    if normalized_endpoint.startswith("http://") or normalized_endpoint.startswith("https://"):
        return validate_http_url(normalized_endpoint)

    return f"{normalized_base_url}/{normalized_endpoint.lstrip('/')}"


def build_http_provider_request(
    *,
    provider_id: str,
    method: HttpProviderMethod | str,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
    metadata: dict[str, Any] | None = None,
) -> HttpProviderRequest:
    """Build HTTP provider request."""
    return HttpProviderRequest(
        provider_id=provider_id,
        method=method,
        url=url,
        params=params or {},
        headers=headers or {},
        body=body,
        timeout_seconds=timeout_seconds,
        metadata=metadata or {},
    )


def build_http_provider_response(
    *,
    provider_id: str,
    status_code: int,
    payload: dict[str, Any] | list[Any],
    headers: dict[str, str] | None = None,
    elapsed_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> HttpProviderResponse:
    """Build HTTP provider response."""
    return HttpProviderResponse(
        provider_id=provider_id,
        status_code=status_code,
        payload=payload,
        headers=headers or {},
        elapsed_ms=elapsed_ms,
        metadata=metadata or {},
    )


def build_http_market_data_provider(
    *,
    provider_config: ProviderConfig | None = None,
    provider_id: str = "http-market-data",
    name: str = "HTTP Market Data Provider",
    base_url: str = "https://example.com",
    transport: HttpTransport | None = None,
    capabilities: list[ProviderCapability | str] | None = None,
    status: ProviderStatus | str = ProviderStatus.ACTIVE,
    metadata: dict[str, Any] | None = None,
) -> HttpMarketDataProvider:
    """Build HTTP market data provider."""
    resolved_config = provider_config or build_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=ProviderType.MARKET_DATA,
        base_url=base_url,
        status=status,
        capabilities=capabilities
        or [
            ProviderCapability.HISTORICAL_OHLCV,
            ProviderCapability.LIVE_QUOTES,
            ProviderCapability.TICKS,
        ],
    )

    return HttpMarketDataProvider(
        provider_config=resolved_config,
        transport=transport,
        metadata=metadata or {},
    )


def default_http_transport(request: HttpProviderRequest) -> HttpProviderResponse:
    """Default urllib-based HTTP transport."""
    if not isinstance(request, HttpProviderRequest):
        raise ValueError("Request must be a HttpProviderRequest.")

    start = time.perf_counter()
    method = normalize_http_provider_method(request.method).value
    body_bytes = None

    if request.body is not None:
        body_bytes = json.dumps(request.body).encode("utf-8")

    urllib_request = urllib.request.Request(
        url=request.resolved_url(),
        data=body_bytes,
        headers={
            "Accept": "application/json",
            **request.headers,
        },
        method=method,
    )

    with urllib.request.urlopen(urllib_request, timeout=request.timeout_seconds) as response:
        raw_payload = response.read().decode("utf-8")
        payload = json.loads(raw_payload) if raw_payload else {}
        elapsed_ms = round((time.perf_counter() - start) * 1000, 4)

        return build_http_provider_response(
            provider_id=request.provider_id,
            status_code=int(response.status),
            payload=payload,
            headers=dict(response.headers.items()),
            elapsed_ms=elapsed_ms,
        )


def json_records_from_payload(
    *,
    payload: dict[str, Any] | list[Any],
    records_key: str,
) -> list[dict[str, Any]]:
    """Extract records from JSON payload."""
    validate_string(records_key, "Records key")

    if isinstance(payload, list):
        records = payload
    elif records_key:
        records = payload.get(records_key, [])
    else:
        records = payload

    if not isinstance(records, list):
        raise ValueError("JSON records must be a list.")

    for record in records:
        validate_metadata(record, "JSON record")

    return records


def json_payload_to_ohlcv_rows(
    *,
    payload: dict[str, Any] | list[Any],
    records_key: str = "data",
    field_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Convert JSON payload into normalized OHLCV rows."""
    fields = {
        "timestamp": "timestamp",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        **(field_map or {}),
    }
    records = json_records_from_payload(payload=payload, records_key=records_key)

    return [
        {
            "timestamp": str(record[fields["timestamp"]]),
            "open": float(record[fields["open"]]),
            "high": float(record[fields["high"]]),
            "low": float(record[fields["low"]]),
            "close": float(record[fields["close"]]),
            "volume": float(record.get(fields["volume"], 0.0) or 0.0),
        }
        for record in records
    ]


def json_payload_to_market_quote(
    *,
    provider_id: str,
    payload: dict[str, Any] | list[Any],
    quote_key: str = "quote",
    field_map: dict[str, str] | None = None,
) -> MarketQuote:
    """Convert JSON payload into market quote."""
    validate_non_empty_string(provider_id, "Provider ID")

    if not isinstance(payload, dict):
        raise ValueError("Quote payload must be a dictionary.")

    fields = {
        "symbol": "symbol",
        "bid": "bid",
        "ask": "ask",
        "last": "last",
        "timestamp": "timestamp",
        **(field_map or {}),
    }

    quote_payload = payload.get(quote_key, payload) if quote_key else payload
    validate_metadata(quote_payload, "Quote payload")

    return build_market_quote(
        provider_id=provider_id,
        symbol=str(quote_payload[fields["symbol"]]),
        bid=float(quote_payload[fields["bid"]]),
        ask=float(quote_payload[fields["ask"]]),
        last=float(quote_payload.get(fields["last"], 0.0) or 0.0),
        timestamp=str(quote_payload[fields["timestamp"]])
        if fields["timestamp"] in quote_payload
        else None,
        metadata=dict(quote_payload.get("metadata", {})),
    )


def json_payload_to_market_ticks(
    *,
    provider_id: str,
    payload: dict[str, Any] | list[Any],
    records_key: str = "ticks",
    field_map: dict[str, str] | None = None,
) -> list[MarketTick]:
    """Convert JSON payload into market ticks."""
    validate_non_empty_string(provider_id, "Provider ID")

    fields = {
        "symbol": "symbol",
        "price": "price",
        "volume": "volume",
        "price_type": "price_type",
        "timestamp": "timestamp",
        **(field_map or {}),
    }
    records = json_records_from_payload(payload=payload, records_key=records_key)

    ticks = [
        build_market_tick(
            provider_id=provider_id,
            symbol=str(record[fields["symbol"]]),
            price=float(record[fields["price"]]),
            volume=float(record.get(fields["volume"], 0.0) or 0.0),
            price_type=str(record.get(fields["price_type"], "last")),
            timestamp=str(record[fields["timestamp"]])
            if fields["timestamp"] in record
            else None,
            metadata=dict(record.get("metadata", {})),
        )
        for record in records
    ]

    validate_market_ticks(ticks)
    return ticks


def http_provider_error_result(
    *,
    provider_id: str,
    error: str,
    request_type: str,
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    """Build HTTP provider error result."""
    return market_data_error_result(
        provider_id=provider_id,
        error=error,
        request_type=request_type,
        metadata={
            "transport": "http",
            **(metadata or {}),
        },
    )


def fetch_http_historical_ohlcv(
    *,
    provider: HttpMarketDataProvider,
    request: HistoricalOhlcvRequest,
) -> ProviderResult:
    """Fetch HTTP historical OHLCV via provider."""
    if not isinstance(provider, HttpMarketDataProvider):
        raise ValueError("Provider must be a HttpMarketDataProvider.")

    return provider.fetch_historical_ohlcv(request)


def fetch_http_live_quote(
    *,
    provider: HttpMarketDataProvider,
    request: LiveQuoteRequest,
) -> ProviderResult:
    """Fetch HTTP live quote via provider."""
    if not isinstance(provider, HttpMarketDataProvider):
        raise ValueError("Provider must be a HttpMarketDataProvider.")

    return provider.fetch_live_quote(request)


def fetch_http_market_ticks(
    *,
    provider: HttpMarketDataProvider,
    request: TickDataRequest,
) -> ProviderResult:
    """Fetch HTTP market ticks via provider."""
    if not isinstance(provider, HttpMarketDataProvider):
        raise ValueError("Provider must be a HttpMarketDataProvider.")

    return provider.fetch_ticks(request)