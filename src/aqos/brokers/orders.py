"""
AQOS broker order and trade contracts.

This module contains dependency-free order, fill, and trade contracts for paper
brokers, exchange adapters, and execution integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.brokers.base import (
    BrokerResult,
    broker_failure,
    broker_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_string,
)


class OrderSide(str, Enum):
    """Supported order sides."""

    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    """Supported order types."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderStatus(str, Enum):
    """Supported order statuses."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TimeInForce(str, Enum):
    """Supported time-in-force values."""

    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    DAY = "day"


class TradeStatus(str, Enum):
    """Supported trade statuses."""

    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class BrokerOrderRequest:
    """Broker order request."""

    broker_id: str
    symbol: str
    side: OrderSide | str
    order_type: OrderType | str
    quantity: float
    price: float = 0.0
    stop_price: float = 0.0
    time_in_force: TimeInForce | str = TimeInForce.GTC
    client_order_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_order_symbol(self.symbol)
        normalize_order_side(self.side)
        normalized_order_type = normalize_order_type(self.order_type)
        validate_positive_float(self.quantity, "Quantity")
        validate_non_negative_float(self.price, "Price")
        validate_non_negative_float(self.stop_price, "Stop price")
        normalize_time_in_force(self.time_in_force)
        validate_string(self.client_order_id, "Client order ID")
        validate_metadata(self.metadata, "Metadata")

        if normalized_order_type in {OrderType.LIMIT, OrderType.STOP_LIMIT} and self.price <= 0:
            raise ValueError("Limit and stop-limit orders require a positive price.")

        if normalized_order_type in {OrderType.STOP, OrderType.STOP_LIMIT} and self.stop_price <= 0:
            raise ValueError("Stop and stop-limit orders require a positive stop price.")

    @property
    def estimated_notional(self) -> float:
        """Return estimated notional value."""
        execution_price = self.price if self.price > 0 else self.stop_price
        return round(float(self.quantity) * float(execution_price), 6)

    def to_dict(self) -> dict[str, Any]:
        """Convert order request into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "symbol": validate_order_symbol(self.symbol),
            "side": normalize_order_side(self.side).value,
            "order_type": normalize_order_type(self.order_type).value,
            "quantity": float(self.quantity),
            "price": float(self.price),
            "stop_price": float(self.stop_price),
            "time_in_force": normalize_time_in_force(self.time_in_force).value,
            "client_order_id": self.client_order_id.strip(),
            "estimated_notional": self.estimated_notional,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerOrder:
    """Broker order state."""

    order_id: str
    broker_id: str
    symbol: str
    side: OrderSide | str
    order_type: OrderType | str
    quantity: float
    status: OrderStatus | str = OrderStatus.PENDING
    price: float = 0.0
    stop_price: float = 0.0
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    fee: float = 0.0
    client_order_id: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.order_id, "Order ID")
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_order_symbol(self.symbol)
        normalize_order_side(self.side)
        normalize_order_type(self.order_type)
        validate_positive_float(self.quantity, "Quantity")
        normalize_order_status(self.status)
        validate_non_negative_float(self.price, "Price")
        validate_non_negative_float(self.stop_price, "Stop price")
        validate_non_negative_float(self.filled_quantity, "Filled quantity")
        validate_non_negative_float(self.average_fill_price, "Average fill price")
        validate_non_negative_float(self.fee, "Fee")
        validate_string(self.client_order_id, "Client order ID")
        validate_non_empty_string(self.created_at, "Created at")
        validate_non_empty_string(self.updated_at, "Updated at")
        validate_metadata(self.metadata, "Metadata")

        if float(self.filled_quantity) > float(self.quantity):
            raise ValueError("Filled quantity cannot exceed order quantity.")

    @property
    def remaining_quantity(self) -> float:
        """Return remaining quantity."""
        return round(float(self.quantity) - float(self.filled_quantity), 6)

    @property
    def filled(self) -> bool:
        """Return whether order is fully filled."""
        return normalize_order_status(self.status) == OrderStatus.FILLED

    @property
    def open(self) -> bool:
        """Return whether order is open."""
        return normalize_order_status(self.status) in {
            OrderStatus.PENDING,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
        }

    @property
    def cancelled(self) -> bool:
        """Return whether order is cancelled."""
        return normalize_order_status(self.status) == OrderStatus.CANCELLED

    @property
    def rejected(self) -> bool:
        """Return whether order is rejected."""
        return normalize_order_status(self.status) == OrderStatus.REJECTED

    @property
    def filled_notional(self) -> float:
        """Return filled notional value."""
        return round(float(self.filled_quantity) * float(self.average_fill_price), 6)

    def to_dict(self) -> dict[str, Any]:
        """Convert order into dictionary."""
        return {
            "order_id": self.order_id.strip(),
            "broker_id": self.broker_id.strip(),
            "symbol": validate_order_symbol(self.symbol),
            "side": normalize_order_side(self.side).value,
            "order_type": normalize_order_type(self.order_type).value,
            "quantity": float(self.quantity),
            "status": normalize_order_status(self.status).value,
            "price": float(self.price),
            "stop_price": float(self.stop_price),
            "filled_quantity": float(self.filled_quantity),
            "remaining_quantity": self.remaining_quantity,
            "average_fill_price": float(self.average_fill_price),
            "filled_notional": self.filled_notional,
            "fee": float(self.fee),
            "client_order_id": self.client_order_id.strip(),
            "created_at": self.created_at.strip(),
            "updated_at": self.updated_at.strip(),
            "open": self.open,
            "filled": self.filled,
            "cancelled": self.cancelled,
            "rejected": self.rejected,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerTrade:
    """Broker trade/fill record."""

    trade_id: str
    order_id: str
    broker_id: str
    symbol: str
    side: OrderSide | str
    quantity: float
    price: float
    fee: float = 0.0
    status: TradeStatus | str = TradeStatus.OPEN
    executed_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.trade_id, "Trade ID")
        validate_non_empty_string(self.order_id, "Order ID")
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_order_symbol(self.symbol)
        normalize_order_side(self.side)
        validate_positive_float(self.quantity, "Quantity")
        validate_positive_float(self.price, "Price")
        validate_non_negative_float(self.fee, "Fee")
        normalize_trade_status(self.status)
        validate_non_empty_string(self.executed_at, "Executed at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def notional(self) -> float:
        """Return trade notional."""
        return round(float(self.quantity) * float(self.price), 6)

    @property
    def closed(self) -> bool:
        """Return whether trade is closed."""
        return normalize_trade_status(self.status) == TradeStatus.CLOSED

    def to_dict(self) -> dict[str, Any]:
        """Convert trade into dictionary."""
        return {
            "trade_id": self.trade_id.strip(),
            "order_id": self.order_id.strip(),
            "broker_id": self.broker_id.strip(),
            "symbol": validate_order_symbol(self.symbol),
            "side": normalize_order_side(self.side).value,
            "quantity": float(self.quantity),
            "price": float(self.price),
            "notional": self.notional,
            "fee": float(self.fee),
            "status": normalize_trade_status(self.status).value,
            "closed": self.closed,
            "executed_at": self.executed_at.strip(),
            "metadata": dict(self.metadata),
        }


def validate_order_symbol(symbol: str) -> str:
    """Validate broker order symbol."""
    normalized = validate_non_empty_string(symbol, "Symbol").upper()

    if not normalized.replace("/", "").replace("-", "").isalnum():
        raise ValueError("Symbol must be alphanumeric and may include '/' or '-'.")

    return normalized


def normalize_order_side(side: OrderSide | str) -> OrderSide:
    """Normalize order side."""
    if isinstance(side, OrderSide):
        return side

    normalized = validate_non_empty_string(side, "Order side").lower()

    try:
        return OrderSide(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in OrderSide)
        raise ValueError(
            f"Invalid order side '{side}'. Valid sides: {valid}.",
        ) from exc


def normalize_order_type(order_type: OrderType | str) -> OrderType:
    """Normalize order type."""
    if isinstance(order_type, OrderType):
        return order_type

    normalized = validate_non_empty_string(order_type, "Order type").lower()

    try:
        return OrderType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in OrderType)
        raise ValueError(
            f"Invalid order type '{order_type}'. Valid order types: {valid}.",
        ) from exc


def normalize_order_status(status: OrderStatus | str) -> OrderStatus:
    """Normalize order status."""
    if isinstance(status, OrderStatus):
        return status

    normalized = validate_non_empty_string(status, "Order status").lower()

    try:
        return OrderStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in OrderStatus)
        raise ValueError(
            f"Invalid order status '{status}'. Valid statuses: {valid}.",
        ) from exc


def normalize_time_in_force(time_in_force: TimeInForce | str) -> TimeInForce:
    """Normalize time-in-force."""
    if isinstance(time_in_force, TimeInForce):
        return time_in_force

    normalized = validate_non_empty_string(time_in_force, "Time in force").lower()

    try:
        return TimeInForce(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TimeInForce)
        raise ValueError(
            f"Invalid time in force '{time_in_force}'. Valid values: {valid}.",
        ) from exc


def normalize_trade_status(status: TradeStatus | str) -> TradeStatus:
    """Normalize trade status."""
    if isinstance(status, TradeStatus):
        return status

    normalized = validate_non_empty_string(status, "Trade status").lower()

    try:
        return TradeStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TradeStatus)
        raise ValueError(
            f"Invalid trade status '{status}'. Valid statuses: {valid}.",
        ) from exc


def build_broker_order_request(
    *,
    broker_id: str,
    symbol: str,
    side: OrderSide | str,
    order_type: OrderType | str,
    quantity: float,
    price: float = 0.0,
    stop_price: float = 0.0,
    time_in_force: TimeInForce | str = TimeInForce.GTC,
    client_order_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> BrokerOrderRequest:
    """Build broker order request."""
    return BrokerOrderRequest(
        broker_id=broker_id,
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
        time_in_force=time_in_force,
        client_order_id=client_order_id,
        metadata=metadata or {},
    )


def build_broker_order(
    *,
    order_id: str,
    broker_id: str,
    symbol: str,
    side: OrderSide | str,
    order_type: OrderType | str,
    quantity: float,
    status: OrderStatus | str = OrderStatus.PENDING,
    price: float = 0.0,
    stop_price: float = 0.0,
    filled_quantity: float = 0.0,
    average_fill_price: float = 0.0,
    fee: float = 0.0,
    client_order_id: str = "",
    created_at: str | None = None,
    updated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerOrder:
    """Build broker order."""
    order_kwargs: dict[str, Any] = {
        "order_id": order_id,
        "broker_id": broker_id,
        "symbol": symbol,
        "side": side,
        "order_type": order_type,
        "quantity": quantity,
        "status": status,
        "price": price,
        "stop_price": stop_price,
        "filled_quantity": filled_quantity,
        "average_fill_price": average_fill_price,
        "fee": fee,
        "client_order_id": client_order_id,
        "metadata": metadata or {},
    }

    if created_at is not None:
        order_kwargs["created_at"] = created_at

    if updated_at is not None:
        order_kwargs["updated_at"] = updated_at

    return BrokerOrder(**order_kwargs)


def build_broker_trade(
    *,
    trade_id: str,
    order_id: str,
    broker_id: str,
    symbol: str,
    side: OrderSide | str,
    quantity: float,
    price: float,
    fee: float = 0.0,
    status: TradeStatus | str = TradeStatus.OPEN,
    executed_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerTrade:
    """Build broker trade."""
    trade_kwargs: dict[str, Any] = {
        "trade_id": trade_id,
        "order_id": order_id,
        "broker_id": broker_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "fee": fee,
        "status": status,
        "metadata": metadata or {},
    }

    if executed_at is not None:
        trade_kwargs["executed_at"] = executed_at

    return BrokerTrade(**trade_kwargs)


def order_request_to_order(
    request: BrokerOrderRequest,
    *,
    order_id: str,
    status: OrderStatus | str = OrderStatus.ACCEPTED,
    created_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerOrder:
    """Convert order request into broker order."""
    if not isinstance(request, BrokerOrderRequest):
        raise ValueError("Request must be a BrokerOrderRequest.")

    return build_broker_order(
        order_id=order_id,
        broker_id=request.broker_id,
        symbol=request.symbol,
        side=request.side,
        order_type=request.order_type,
        quantity=request.quantity,
        status=status,
        price=request.price,
        stop_price=request.stop_price,
        client_order_id=request.client_order_id,
        created_at=created_at,
        updated_at=created_at,
        metadata={
            **request.metadata,
            **(metadata or {}),
        },
    )


def fill_broker_order(
    order: BrokerOrder,
    *,
    trade_id: str,
    fill_quantity: float,
    fill_price: float,
    fee: float = 0.0,
    executed_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> tuple[BrokerOrder, BrokerTrade]:
    """Fill broker order and return updated order plus trade."""
    if not isinstance(order, BrokerOrder):
        raise ValueError("Order must be a BrokerOrder.")

    validate_positive_float(fill_quantity, "Fill quantity")
    validate_positive_float(fill_price, "Fill price")
    validate_non_negative_float(fee, "Fee")

    if fill_quantity > order.remaining_quantity:
        raise ValueError("Fill quantity cannot exceed remaining order quantity.")

    new_filled_quantity = round(order.filled_quantity + fill_quantity, 6)
    previous_notional = order.filled_quantity * order.average_fill_price
    new_notional = previous_notional + (fill_quantity * fill_price)
    average_fill_price = round(new_notional / new_filled_quantity, 6)

    status = (
        OrderStatus.FILLED
        if new_filled_quantity >= order.quantity
        else OrderStatus.PARTIALLY_FILLED
    )

    timestamp = executed_at or datetime.now(UTC).isoformat()

    updated_order = build_broker_order(
        order_id=order.order_id,
        broker_id=order.broker_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        status=status,
        price=order.price,
        stop_price=order.stop_price,
        filled_quantity=new_filled_quantity,
        average_fill_price=average_fill_price,
        fee=round(order.fee + fee, 6),
        client_order_id=order.client_order_id,
        created_at=order.created_at,
        updated_at=timestamp,
        metadata={
            **order.metadata,
            **(metadata or {}),
        },
    )

    trade = build_broker_trade(
        trade_id=trade_id,
        order_id=order.order_id,
        broker_id=order.broker_id,
        symbol=order.symbol,
        side=order.side,
        quantity=fill_quantity,
        price=fill_price,
        fee=fee,
        executed_at=timestamp,
        metadata=metadata or {},
    )

    return updated_order, trade


def cancel_broker_order(
    order: BrokerOrder,
    *,
    updated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerOrder:
    """Cancel broker order."""
    if not isinstance(order, BrokerOrder):
        raise ValueError("Order must be a BrokerOrder.")

    if order.filled:
        raise ValueError("Filled orders cannot be cancelled.")

    timestamp = updated_at or datetime.now(UTC).isoformat()

    return build_broker_order(
        order_id=order.order_id,
        broker_id=order.broker_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        status=OrderStatus.CANCELLED,
        price=order.price,
        stop_price=order.stop_price,
        filled_quantity=order.filled_quantity,
        average_fill_price=order.average_fill_price,
        fee=order.fee,
        client_order_id=order.client_order_id,
        created_at=order.created_at,
        updated_at=timestamp,
        metadata={
            **order.metadata,
            **(metadata or {}),
        },
    )


def reject_broker_order(
    order: BrokerOrder,
    *,
    reason: str,
    updated_at: str | None = None,
) -> BrokerOrder:
    """Reject broker order."""
    if not isinstance(order, BrokerOrder):
        raise ValueError("Order must be a BrokerOrder.")

    validate_non_empty_string(reason, "Reason")
    timestamp = updated_at or datetime.now(UTC).isoformat()

    return build_broker_order(
        order_id=order.order_id,
        broker_id=order.broker_id,
        symbol=order.symbol,
        side=order.side,
        order_type=order.order_type,
        quantity=order.quantity,
        status=OrderStatus.REJECTED,
        price=order.price,
        stop_price=order.stop_price,
        filled_quantity=order.filled_quantity,
        average_fill_price=order.average_fill_price,
        fee=order.fee,
        client_order_id=order.client_order_id,
        created_at=order.created_at,
        updated_at=timestamp,
        metadata={
            **order.metadata,
            "rejection_reason": reason.strip(),
        },
    )


def order_to_broker_result(
    order: BrokerOrder,
    *,
    message: str = "Broker order processed.",
) -> BrokerResult:
    """Convert order into broker result."""
    if not isinstance(order, BrokerOrder):
        raise ValueError("Order must be a BrokerOrder.")

    return broker_success(
        broker_id=order.broker_id,
        data={
            "order": order.to_dict(),
        },
        message=message,
    )


def trade_to_broker_result(
    trade: BrokerTrade,
    *,
    message: str = "Broker trade processed.",
) -> BrokerResult:
    """Convert trade into broker result."""
    if not isinstance(trade, BrokerTrade):
        raise ValueError("Trade must be a BrokerTrade.")

    return broker_success(
        broker_id=trade.broker_id,
        data={
            "trade": trade.to_dict(),
        },
        message=message,
    )


def order_error_result(
    *,
    broker_id: str,
    error: str,
    operation: str,
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build order error result."""
    return broker_failure(
        broker_id=broker_id,
        error=error,
        message="Broker order operation failed.",
        metadata={
            "operation": validate_non_empty_string(operation, "Operation"),
            **(metadata or {}),
        },
    )