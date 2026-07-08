"""
AQOS exchange HTTP broker adapter.

This module provides dependency-free HTTP helpers for live/exchange broker APIs.
It uses injectable transports for tests and urllib for simple JSON HTTP calls.
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

from aqos.brokers.account import (
    BrokerAccount,
    BrokerPosition,
    build_broker_account,
    build_broker_position,
    validate_broker_positions,
)
from aqos.brokers.base import (
    BrokerCapability,
    BrokerConfig,
    BrokerResult,
    BrokerType,
    broker_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_string,
)
from aqos.brokers.orders import (
    BrokerOrder,
    BrokerOrderRequest,
    BrokerTrade,
    OrderStatus,
    OrderType,
    build_broker_order,
    build_broker_trade,
    order_error_result,
    order_to_broker_result,
    trade_to_broker_result,
    validate_order_symbol,
)


class ExchangeHttpMethod(str, Enum):
    """Supported exchange HTTP methods."""

    GET = "GET"
    POST = "POST"
    DELETE = "DELETE"


@dataclass(frozen=True)
class ExchangeHttpRequest:
    """Exchange HTTP request."""

    broker_id: str
    method: ExchangeHttpMethod | str
    url: str
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    body: dict[str, Any] | None = None
    timeout_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        normalize_exchange_http_method(self.method)
        validate_exchange_http_url(self.url)
        validate_exchange_http_params(self.params)
        validate_exchange_http_headers(self.headers)

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
        """Convert request into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "method": normalize_exchange_http_method(self.method).value,
            "url": self.url.strip(),
            "resolved_url": self.resolved_url(),
            "params": dict(self.params),
            "headers": dict(self.headers),
            "body": dict(self.body) if self.body is not None else None,
            "timeout_seconds": float(self.timeout_seconds),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ExchangeHttpResponse:
    """Exchange HTTP response."""

    broker_id: str
    status_code: int
    payload: dict[str, Any] | list[Any]
    headers: dict[str, str] = field(default_factory=dict)
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_exchange_http_status_code(self.status_code)

        if not isinstance(self.payload, dict | list):
            raise ValueError("Payload must be a dictionary or list.")

        validate_exchange_http_headers(self.headers)
        validate_non_negative_float(self.elapsed_ms, "Elapsed milliseconds")
        validate_metadata(self.metadata, "Metadata")

    @property
    def success(self) -> bool:
        """Return whether HTTP response is successful."""
        return is_success_exchange_http_status(self.status_code)

    @property
    def failed(self) -> bool:
        """Return whether HTTP response failed."""
        return not self.success

    def to_dict(self) -> dict[str, Any]:
        """Convert response into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "status_code": self.status_code,
            "success": self.success,
            "failed": self.failed,
            "payload": self.payload,
            "headers": dict(self.headers),
            "elapsed_ms": float(self.elapsed_ms),
            "metadata": dict(self.metadata),
        }


ExchangeHttpTransport = Callable[[ExchangeHttpRequest], ExchangeHttpResponse]


@dataclass
class ExchangeHttpBrokerAdapter:
    """Exchange HTTP broker adapter."""

    broker_config: BrokerConfig
    transport: ExchangeHttpTransport | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_exchange_http_broker_config(self.broker_config)

        if self.transport is not None and not callable(self.transport):
            raise ValueError("Transport must be callable.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def broker_id(self) -> str:
        """Return broker ID."""
        return self.broker_config.broker_id.strip()

    @property
    def active(self) -> bool:
        """Return whether broker is active."""
        return self.broker_config.active

    @property
    def base_url(self) -> str:
        """Return broker base URL."""
        return self.broker_config.base_url.strip()

    def request(self, request: ExchangeHttpRequest) -> ExchangeHttpResponse:
        """Execute exchange HTTP request."""
        if not isinstance(request, ExchangeHttpRequest):
            raise ValueError("Request must be an ExchangeHttpRequest.")

        if request.broker_id.strip() != self.broker_id:
            raise ValueError("Request broker ID must match exchange broker ID.")

        resolved_transport = self.transport or default_exchange_http_transport
        return resolved_transport(request)

    def submit_order(
        self,
        request: BrokerOrderRequest,
        *,
        endpoint: str = "/orders",
        order_key: str = "order",
        field_map: dict[str, str] | None = None,
    ) -> BrokerResult:
        """Submit broker order to exchange HTTP API."""
        if not isinstance(request, BrokerOrderRequest):
            raise ValueError("Request must be a BrokerOrderRequest.")

        if request.broker_id.strip() != self.broker_id:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error="Request broker ID does not match exchange broker ID.",
                operation="submit_order",
            )

        if not self.active:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error="Exchange broker is not active.",
                operation="submit_order",
            )

        if not (
            self.broker_config.supports(BrokerCapability.LIVE_TRADING)
            or self.broker_config.supports(BrokerCapability.MARKET_ORDERS)
        ):
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error="Exchange broker does not support order execution.",
                operation="submit_order",
            )

        response = self.request(
            build_exchange_http_request(
                broker_id=self.broker_id,
                method=ExchangeHttpMethod.POST,
                url=join_exchange_http_url(self.base_url, endpoint),
                body=request.to_dict(),
                timeout_seconds=self.broker_config.timeout_seconds,
            ),
        )

        if response.failed:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error=f"Exchange HTTP request failed with status {response.status_code}.",
                operation="submit_order",
                metadata={
                    "status_code": response.status_code,
                },
            )

        order = json_payload_to_broker_order(
            broker_id=self.broker_id,
            payload=response.payload,
            order_key=order_key,
            field_map=field_map,
            fallback_request=request,
        )

        return order_to_broker_result(
            order,
            message="Exchange order submitted.",
        )

    def cancel_order(
        self,
        *,
        order_id: str,
        endpoint: str = "/orders/{order_id}",
        order_key: str = "order",
        field_map: dict[str, str] | None = None,
    ) -> BrokerResult:
        """Cancel order through exchange HTTP API."""
        normalized_order_id = validate_non_empty_string(order_id, "Order ID")

        if not self.active:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error="Exchange broker is not active.",
                operation="cancel_order",
            )

        resolved_endpoint = endpoint.format(order_id=urllib.parse.quote(normalized_order_id))
        response = self.request(
            build_exchange_http_request(
                broker_id=self.broker_id,
                method=ExchangeHttpMethod.DELETE,
                url=join_exchange_http_url(self.base_url, resolved_endpoint),
                timeout_seconds=self.broker_config.timeout_seconds,
            ),
        )

        if response.failed:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error=f"Exchange HTTP request failed with status {response.status_code}.",
                operation="cancel_order",
                metadata={
                    "order_id": normalized_order_id,
                    "status_code": response.status_code,
                },
            )

        order = json_payload_to_broker_order(
            broker_id=self.broker_id,
            payload=response.payload,
            order_key=order_key,
            field_map=field_map,
        )

        return order_to_broker_result(
            order,
            message="Exchange order cancelled.",
        )

    def fetch_account(
        self,
        *,
        endpoint: str = "/account",
        account_key: str = "account",
        field_map: dict[str, str] | None = None,
    ) -> BrokerResult:
        """Fetch exchange account."""
        if not self.broker_config.supports(BrokerCapability.ACCOUNT_INFO):
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error="Exchange broker does not support account info.",
                operation="fetch_account",
            )

        response = self.request(
            build_exchange_http_request(
                broker_id=self.broker_id,
                method=ExchangeHttpMethod.GET,
                url=join_exchange_http_url(self.base_url, endpoint),
                timeout_seconds=self.broker_config.timeout_seconds,
            ),
        )

        if response.failed:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error=f"Exchange HTTP request failed with status {response.status_code}.",
                operation="fetch_account",
                metadata={
                    "status_code": response.status_code,
                },
            )

        account = json_payload_to_broker_account(
            broker_id=self.broker_id,
            payload=response.payload,
            account_key=account_key,
            field_map=field_map,
        )

        return broker_success(
            broker_id=self.broker_id,
            data={
                "account": account.to_dict(),
            },
            message="Exchange account fetched.",
            metadata={
                "operation": "fetch_account",
            },
        )

    def fetch_positions(
        self,
        *,
        endpoint: str = "/positions",
        records_key: str = "positions",
        field_map: dict[str, str] | None = None,
    ) -> BrokerResult:
        """Fetch exchange positions."""
        if not self.broker_config.supports(BrokerCapability.POSITION_TRACKING):
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error="Exchange broker does not support position tracking.",
                operation="fetch_positions",
            )

        response = self.request(
            build_exchange_http_request(
                broker_id=self.broker_id,
                method=ExchangeHttpMethod.GET,
                url=join_exchange_http_url(self.base_url, endpoint),
                timeout_seconds=self.broker_config.timeout_seconds,
            ),
        )

        if response.failed:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error=f"Exchange HTTP request failed with status {response.status_code}.",
                operation="fetch_positions",
                metadata={
                    "status_code": response.status_code,
                },
            )

        positions = json_payload_to_broker_positions(
            broker_id=self.broker_id,
            payload=response.payload,
            records_key=records_key,
            field_map=field_map,
        )

        return broker_success(
            broker_id=self.broker_id,
            data={
                "positions": [position.to_dict() for position in positions],
                "count": len(positions),
            },
            message="Exchange positions fetched.",
            metadata={
                "operation": "fetch_positions",
            },
        )

    def fetch_trade(
        self,
        *,
        trade_id: str,
        endpoint: str = "/trades/{trade_id}",
        trade_key: str = "trade",
        field_map: dict[str, str] | None = None,
    ) -> BrokerResult:
        """Fetch exchange trade."""
        normalized_trade_id = validate_non_empty_string(trade_id, "Trade ID")

        response = self.request(
            build_exchange_http_request(
                broker_id=self.broker_id,
                method=ExchangeHttpMethod.GET,
                url=join_exchange_http_url(
                    self.base_url,
                    endpoint.format(trade_id=urllib.parse.quote(normalized_trade_id)),
                ),
                timeout_seconds=self.broker_config.timeout_seconds,
            ),
        )

        if response.failed:
            return exchange_http_error_result(
                broker_id=self.broker_id,
                error=f"Exchange HTTP request failed with status {response.status_code}.",
                operation="fetch_trade",
                metadata={
                    "trade_id": normalized_trade_id,
                    "status_code": response.status_code,
                },
            )

        trade = json_payload_to_broker_trade(
            broker_id=self.broker_id,
            payload=response.payload,
            trade_key=trade_key,
            field_map=field_map,
        )

        return trade_to_broker_result(
            trade,
            message="Exchange trade fetched.",
        )


def normalize_exchange_http_method(
    method: ExchangeHttpMethod | str,
) -> ExchangeHttpMethod:
    """Normalize exchange HTTP method."""
    if isinstance(method, ExchangeHttpMethod):
        return method

    normalized = validate_non_empty_string(method, "HTTP method").upper()

    try:
        return ExchangeHttpMethod(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ExchangeHttpMethod)
        raise ValueError(
            f"Invalid exchange HTTP method '{method}'. Valid methods: {valid}.",
        ) from exc


def validate_exchange_http_url(url: str) -> str:
    """Validate HTTP URL."""
    normalized = validate_non_empty_string(url, "URL")

    if not normalized.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://.")

    return normalized


def validate_exchange_http_status_code(status_code: int) -> int:
    """Validate HTTP status code."""
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise ValueError("Status code must be an integer.")

    if status_code < 100 or status_code > 599:
        raise ValueError("Status code must be between 100 and 599.")

    return status_code


def validate_exchange_http_params(params: dict[str, Any]) -> dict[str, Any]:
    """Validate HTTP params."""
    if not isinstance(params, dict):
        raise ValueError("Params must be a dictionary.")

    for key in params:
        validate_non_empty_string(str(key), "Param key")

    return params


def validate_exchange_http_headers(headers: dict[str, str]) -> dict[str, str]:
    """Validate HTTP headers."""
    if not isinstance(headers, dict):
        raise ValueError("Headers must be a dictionary.")

    for key, value in headers.items():
        validate_non_empty_string(str(key), "Header key")
        validate_string(value, "Header value")

    return headers


def validate_exchange_http_broker_config(config: BrokerConfig) -> BrokerConfig:
    """Validate exchange HTTP broker config."""
    if not isinstance(config, BrokerConfig):
        raise ValueError("Broker config must be BrokerConfig.")

    if config.broker_type != BrokerType.EXCHANGE and str(config.broker_type) != BrokerType.EXCHANGE.value:
        raise ValueError("Exchange HTTP adapter requires an exchange broker config.")

    if config.paper_mode:
        raise ValueError("Exchange HTTP adapter requires live mode.")

    validate_exchange_http_url(config.base_url)

    if not (
        config.supports(BrokerCapability.LIVE_TRADING)
        or config.supports(BrokerCapability.MARKET_ORDERS)
        or config.supports(BrokerCapability.ACCOUNT_INFO)
        or config.supports(BrokerCapability.POSITION_TRACKING)
    ):
        raise ValueError("Exchange HTTP broker must support exchange capabilities.")

    return config


def is_success_exchange_http_status(status_code: int) -> bool:
    """Return whether HTTP status is successful."""
    validate_exchange_http_status_code(status_code)
    return 200 <= status_code <= 299


def join_exchange_http_url(base_url: str, endpoint: str) -> str:
    """Join exchange base URL and endpoint."""
    normalized_base_url = validate_exchange_http_url(base_url).rstrip("/")
    normalized_endpoint = validate_non_empty_string(endpoint, "Endpoint")

    if normalized_endpoint.startswith(("http://", "https://")):
        return validate_exchange_http_url(normalized_endpoint)

    return f"{normalized_base_url}/{normalized_endpoint.lstrip('/')}"


def build_exchange_http_request(
    *,
    broker_id: str,
    method: ExchangeHttpMethod | str,
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
    metadata: dict[str, Any] | None = None,
) -> ExchangeHttpRequest:
    """Build exchange HTTP request."""
    return ExchangeHttpRequest(
        broker_id=broker_id,
        method=method,
        url=url,
        params=params or {},
        headers=headers or {},
        body=body,
        timeout_seconds=timeout_seconds,
        metadata=metadata or {},
    )


def build_exchange_http_response(
    *,
    broker_id: str,
    status_code: int,
    payload: dict[str, Any] | list[Any],
    headers: dict[str, str] | None = None,
    elapsed_ms: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> ExchangeHttpResponse:
    """Build exchange HTTP response."""
    return ExchangeHttpResponse(
        broker_id=broker_id,
        status_code=status_code,
        payload=payload,
        headers=headers or {},
        elapsed_ms=elapsed_ms,
        metadata=metadata or {},
    )


def build_exchange_http_broker_adapter(
    *,
    broker_config: BrokerConfig | None = None,
    broker_id: str = "exchange-http",
    name: str = "Exchange HTTP Broker",
    base_url: str = "https://example.com/api",
    transport: ExchangeHttpTransport | None = None,
    capabilities: list[BrokerCapability | str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> ExchangeHttpBrokerAdapter:
    """Build exchange HTTP broker adapter."""
    from aqos.brokers.base import build_broker_config

    resolved_config = broker_config or build_broker_config(
        broker_id=broker_id,
        name=name,
        broker_type=BrokerType.EXCHANGE,
        base_url=base_url,
        capabilities=capabilities
        or [
            BrokerCapability.LIVE_TRADING,
            BrokerCapability.MARKET_ORDERS,
            BrokerCapability.LIMIT_ORDERS,
            BrokerCapability.ACCOUNT_INFO,
            BrokerCapability.POSITION_TRACKING,
            BrokerCapability.TRADE_HISTORY,
        ],
        paper_mode=False,
    )

    return ExchangeHttpBrokerAdapter(
        broker_config=resolved_config,
        transport=transport,
        metadata=metadata or {},
    )


def default_exchange_http_transport(
    request: ExchangeHttpRequest,
) -> ExchangeHttpResponse:
    """Default urllib JSON HTTP transport."""
    if not isinstance(request, ExchangeHttpRequest):
        raise ValueError("Request must be an ExchangeHttpRequest.")

    start = time.perf_counter()
    method = normalize_exchange_http_method(request.method).value
    body_bytes = None

    if request.body is not None:
        body_bytes = json.dumps(request.body).encode("utf-8")

    urllib_request = urllib.request.Request(
        url=request.resolved_url(),
        data=body_bytes,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            **request.headers,
        },
        method=method,
    )

    with urllib.request.urlopen(urllib_request, timeout=request.timeout_seconds) as response:
        raw_payload = response.read().decode("utf-8")
        payload = json.loads(raw_payload) if raw_payload else {}
        elapsed_ms = round((time.perf_counter() - start) * 1000, 4)

        return build_exchange_http_response(
            broker_id=request.broker_id,
            status_code=int(response.status),
            payload=payload,
            headers=dict(response.headers.items()),
            elapsed_ms=elapsed_ms,
        )


def json_record_from_payload(
    *,
    payload: dict[str, Any] | list[Any],
    record_key: str,
) -> dict[str, Any]:
    """Extract one record from JSON payload."""
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a dictionary.")

    record = payload.get(record_key, payload) if record_key else payload
    validate_metadata(record, "JSON record")
    return record


def json_records_from_payload(
    *,
    payload: dict[str, Any] | list[Any],
    records_key: str,
) -> list[dict[str, Any]]:
    """Extract records from JSON payload."""
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


def json_payload_to_broker_order(
    *,
    broker_id: str,
    payload: dict[str, Any] | list[Any],
    order_key: str = "order",
    field_map: dict[str, str] | None = None,
    fallback_request: BrokerOrderRequest | None = None,
) -> BrokerOrder:
    """Convert exchange JSON payload into broker order."""
    validate_non_empty_string(broker_id, "Broker ID")
    record = json_record_from_payload(payload=payload, record_key=order_key)

    fields = {
        "order_id": "order_id",
        "symbol": "symbol",
        "side": "side",
        "order_type": "order_type",
        "quantity": "quantity",
        "status": "status",
        "price": "price",
        "stop_price": "stop_price",
        "filled_quantity": "filled_quantity",
        "average_fill_price": "average_fill_price",
        "fee": "fee",
        "client_order_id": "client_order_id",
        "created_at": "created_at",
        "updated_at": "updated_at",
        **(field_map or {}),
    }

    if fallback_request is not None and not isinstance(fallback_request, BrokerOrderRequest):
        raise ValueError("Fallback request must be BrokerOrderRequest.")

    return build_broker_order(
        order_id=str(record[fields["order_id"]]),
        broker_id=broker_id,
        symbol=str(record.get(fields["symbol"], fallback_request.symbol if fallback_request else "")),
        side=str(record.get(fields["side"], fallback_request.side if fallback_request else "")),
        order_type=str(record.get(fields["order_type"], fallback_request.order_type if fallback_request else OrderType.MARKET)),
        quantity=float(record.get(fields["quantity"], fallback_request.quantity if fallback_request else 0.0)),
        status=str(record.get(fields["status"], OrderStatus.ACCEPTED.value)),
        price=float(record.get(fields["price"], fallback_request.price if fallback_request else 0.0) or 0.0),
        stop_price=float(record.get(fields["stop_price"], fallback_request.stop_price if fallback_request else 0.0) or 0.0),
        filled_quantity=float(record.get(fields["filled_quantity"], 0.0) or 0.0),
        average_fill_price=float(record.get(fields["average_fill_price"], 0.0) or 0.0),
        fee=float(record.get(fields["fee"], 0.0) or 0.0),
        client_order_id=str(record.get(fields["client_order_id"], fallback_request.client_order_id if fallback_request else "")),
        created_at=str(record[fields["created_at"]]) if fields["created_at"] in record else None,
        updated_at=str(record[fields["updated_at"]]) if fields["updated_at"] in record else None,
        metadata=dict(record.get("metadata", {})),
    )


def json_payload_to_broker_trade(
    *,
    broker_id: str,
    payload: dict[str, Any] | list[Any],
    trade_key: str = "trade",
    field_map: dict[str, str] | None = None,
) -> BrokerTrade:
    """Convert exchange JSON payload into broker trade."""
    validate_non_empty_string(broker_id, "Broker ID")
    record = json_record_from_payload(payload=payload, record_key=trade_key)

    fields = {
        "trade_id": "trade_id",
        "order_id": "order_id",
        "symbol": "symbol",
        "side": "side",
        "quantity": "quantity",
        "price": "price",
        "fee": "fee",
        "status": "status",
        "executed_at": "executed_at",
        **(field_map or {}),
    }

    return build_broker_trade(
        trade_id=str(record[fields["trade_id"]]),
        order_id=str(record[fields["order_id"]]),
        broker_id=broker_id,
        symbol=str(record[fields["symbol"]]),
        side=str(record[fields["side"]]),
        quantity=float(record[fields["quantity"]]),
        price=float(record[fields["price"]]),
        fee=float(record.get(fields["fee"], 0.0) or 0.0),
        status=str(record.get(fields["status"], "open")),
        executed_at=str(record[fields["executed_at"]]) if fields["executed_at"] in record else None,
        metadata=dict(record.get("metadata", {})),
    )


def json_payload_to_broker_account(
    *,
    broker_id: str,
    payload: dict[str, Any] | list[Any],
    account_key: str = "account",
    field_map: dict[str, str] | None = None,
) -> BrokerAccount:
    """Convert exchange JSON payload into broker account."""
    validate_non_empty_string(broker_id, "Broker ID")
    record = json_record_from_payload(payload=payload, record_key=account_key)

    fields = {
        "account_id": "account_id",
        "currency": "currency",
        "cash_balance": "cash_balance",
        "equity": "equity",
        "buying_power": "buying_power",
        "margin_used": "margin_used",
        "realized_pnl": "realized_pnl",
        "unrealized_pnl": "unrealized_pnl",
        "updated_at": "updated_at",
        **(field_map or {}),
    }

    cash_balance = float(record.get(fields["cash_balance"], 0.0) or 0.0)
    equity = float(record.get(fields["equity"], cash_balance) or cash_balance)

    return build_broker_account(
        broker_id=broker_id,
        account_id=str(record[fields["account_id"]]),
        currency=str(record.get(fields["currency"], "USD")),
        cash_balance=cash_balance,
        equity=equity,
        buying_power=float(record.get(fields["buying_power"], equity) or equity),
        margin_used=float(record.get(fields["margin_used"], 0.0) or 0.0),
        realized_pnl=float(record.get(fields["realized_pnl"], 0.0) or 0.0),
        unrealized_pnl=float(record.get(fields["unrealized_pnl"], 0.0) or 0.0),
        updated_at=str(record[fields["updated_at"]]) if fields["updated_at"] in record else None,
        metadata=dict(record.get("metadata", {})),
    )


def json_payload_to_broker_position(
    *,
    broker_id: str,
    payload: dict[str, Any],
    field_map: dict[str, str] | None = None,
) -> BrokerPosition:
    """Convert JSON record into broker position."""
    validate_non_empty_string(broker_id, "Broker ID")
    validate_metadata(payload, "Position payload")

    fields = {
        "position_id": "position_id",
        "symbol": "symbol",
        "side": "side",
        "quantity": "quantity",
        "average_price": "average_price",
        "market_price": "market_price",
        "realized_pnl": "realized_pnl",
        "fees": "fees",
        "opened_at": "opened_at",
        "updated_at": "updated_at",
        **(field_map or {}),
    }

    symbol = validate_order_symbol(str(payload[fields["symbol"]]))

    return build_broker_position(
        position_id=str(payload.get(fields["position_id"], f"{broker_id}-position-{symbol}")),
        broker_id=broker_id,
        symbol=symbol,
        side=str(payload[fields["side"]]),
        quantity=float(payload[fields["quantity"]]),
        average_price=float(payload[fields["average_price"]]),
        market_price=float(payload.get(fields["market_price"], 0.0) or 0.0),
        realized_pnl=float(payload.get(fields["realized_pnl"], 0.0) or 0.0),
        fees=float(payload.get(fields["fees"], 0.0) or 0.0),
        opened_at=str(payload[fields["opened_at"]]) if fields["opened_at"] in payload else None,
        updated_at=str(payload[fields["updated_at"]]) if fields["updated_at"] in payload else None,
        metadata=dict(payload.get("metadata", {})),
    )


def json_payload_to_broker_positions(
    *,
    broker_id: str,
    payload: dict[str, Any] | list[Any],
    records_key: str = "positions",
    field_map: dict[str, str] | None = None,
) -> list[BrokerPosition]:
    """Convert exchange JSON payload into broker positions."""
    records = json_records_from_payload(
        payload=payload,
        records_key=records_key,
    )
    positions = [
        json_payload_to_broker_position(
            broker_id=broker_id,
            payload=record,
            field_map=field_map,
        )
        for record in records
    ]

    validate_broker_positions(positions)
    return positions


def exchange_http_error_result(
    *,
    broker_id: str,
    error: str,
    operation: str,
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build exchange HTTP error result."""
    return order_error_result(
        broker_id=broker_id,
        error=error,
        operation=operation,
        metadata={
            "broker_type": "exchange_http",
            **(metadata or {}),
        },
    )


def submit_exchange_http_order(
    *,
    adapter: ExchangeHttpBrokerAdapter,
    request: BrokerOrderRequest,
) -> BrokerResult:
    """Submit exchange HTTP order through adapter."""
    if not isinstance(adapter, ExchangeHttpBrokerAdapter):
        raise ValueError("Adapter must be an ExchangeHttpBrokerAdapter.")

    return adapter.submit_order(request)


def cancel_exchange_http_order(
    *,
    adapter: ExchangeHttpBrokerAdapter,
    order_id: str,
) -> BrokerResult:
    """Cancel exchange HTTP order through adapter."""
    if not isinstance(adapter, ExchangeHttpBrokerAdapter):
        raise ValueError("Adapter must be an ExchangeHttpBrokerAdapter.")

    return adapter.cancel_order(order_id=order_id)


def fetch_exchange_http_account(
    *,
    adapter: ExchangeHttpBrokerAdapter,
) -> BrokerResult:
    """Fetch exchange HTTP account through adapter."""
    if not isinstance(adapter, ExchangeHttpBrokerAdapter):
        raise ValueError("Adapter must be an ExchangeHttpBrokerAdapter.")

    return adapter.fetch_account()


def fetch_exchange_http_positions(
    *,
    adapter: ExchangeHttpBrokerAdapter,
) -> BrokerResult:
    """Fetch exchange HTTP positions through adapter."""
    if not isinstance(adapter, ExchangeHttpBrokerAdapter):
        raise ValueError("Adapter must be an ExchangeHttpBrokerAdapter.")

    return adapter.fetch_positions()