"""
AQOS paper broker adapter.

This module provides a deterministic in-memory paper broker for local execution
testing, strategy dry-runs, and broker integration tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.brokers.base import (
    BrokerCapability,
    BrokerConfig,
    BrokerResult,
    BrokerStatus,
    BrokerType,
    broker_failure,
    broker_success,
    build_broker_config,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
)
from aqos.brokers.orders import (
    BrokerOrder,
    BrokerOrderRequest,
    BrokerTrade,
    OrderStatus,
    OrderType,
    build_broker_order_request,
    cancel_broker_order,
    fill_broker_order,
    order_error_result,
    order_request_to_order,
    order_to_broker_result,
    validate_order_symbol,
)


class PaperFillPolicy(str, Enum):
    """Supported paper broker fill policies."""

    IMMEDIATE_MARKET = "immediate_market"
    MANUAL = "manual"


@dataclass(frozen=True)
class PaperBrokerSnapshot:
    """Paper broker state snapshot."""

    broker_id: str
    cash_balance: float
    orders: list[BrokerOrder] = field(default_factory=list)
    trades: list[BrokerTrade] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_non_negative_float(self.cash_balance, "Cash balance")
        validate_paper_orders(self.orders)
        validate_paper_trades(self.trades)
        validate_metadata(self.metadata, "Metadata")

    @property
    def order_count(self) -> int:
        """Return order count."""
        return len(self.orders)

    @property
    def trade_count(self) -> int:
        """Return trade count."""
        return len(self.trades)

    @property
    def open_order_count(self) -> int:
        """Return open order count."""
        return len([order for order in self.orders if order.open])

    @property
    def filled_order_count(self) -> int:
        """Return filled order count."""
        return len([order for order in self.orders if order.filled])

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "cash_balance": float(self.cash_balance),
            "order_count": self.order_count,
            "trade_count": self.trade_count,
            "open_order_count": self.open_order_count,
            "filled_order_count": self.filled_order_count,
            "orders": [order.to_dict() for order in self.orders],
            "trades": [trade.to_dict() for trade in self.trades],
            "metadata": dict(self.metadata),
        }


@dataclass
class PaperBrokerAdapter:
    """In-memory paper broker adapter."""

    broker_config: BrokerConfig
    cash_balance: float = 100_000.0
    fill_policy: PaperFillPolicy | str = PaperFillPolicy.IMMEDIATE_MARKET
    orders: dict[str, BrokerOrder] = field(default_factory=dict)
    trades: dict[str, BrokerTrade] = field(default_factory=dict)
    last_prices: dict[str, float] = field(default_factory=dict)
    order_sequence: int = 0
    trade_sequence: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_paper_broker_config(self.broker_config)
        validate_non_negative_float(self.cash_balance, "Cash balance")
        normalize_paper_fill_policy(self.fill_policy)
        validate_paper_order_dict(self.orders)
        validate_paper_trade_dict(self.trades)
        validate_paper_price_dict(self.last_prices)
        validate_non_negative_integer(self.order_sequence, "Order sequence")
        validate_non_negative_integer(self.trade_sequence, "Trade sequence")
        validate_metadata(self.metadata, "Metadata")

    @property
    def broker_id(self) -> str:
        """Return broker ID."""
        return self.broker_config.broker_id.strip()

    @property
    def active(self) -> bool:
        """Return whether paper broker is active."""
        return self.broker_config.active

    def update_price(self, *, symbol: str, price: float) -> float:
        """Update latest market price."""
        normalized_symbol = validate_order_symbol(symbol)
        validate_positive_float(price, "Price")
        self.last_prices[normalized_symbol] = float(price)
        return float(price)

    def get_price(self, symbol: str) -> float:
        """Get latest market price."""
        return self.last_prices.get(validate_order_symbol(symbol), 0.0)

    def next_order_id(self) -> str:
        """Return next paper order ID."""
        self.order_sequence += 1
        return f"{self.broker_id}-order-{self.order_sequence:06d}"

    def next_trade_id(self) -> str:
        """Return next paper trade ID."""
        self.trade_sequence += 1
        return f"{self.broker_id}-trade-{self.trade_sequence:06d}"

    def submit_order(
        self,
        request: BrokerOrderRequest,
        *,
        market_price: float = 0.0,
    ) -> BrokerResult:
        """Submit order to paper broker."""
        if not isinstance(request, BrokerOrderRequest):
            raise ValueError("Request must be a BrokerOrderRequest.")

        if request.broker_id.strip() != self.broker_id:
            return paper_broker_error_result(
                broker_id=self.broker_id,
                error="Request broker ID does not match paper broker ID.",
                operation="submit_order",
            )

        if not self.active:
            return paper_broker_error_result(
                broker_id=self.broker_id,
                error="Paper broker is not active.",
                operation="submit_order",
            )

        order = order_request_to_order(
            request,
            order_id=self.next_order_id(),
            status=OrderStatus.ACCEPTED,
            metadata={
                "broker_type": "paper",
            },
        )

        self.orders[order.order_id] = order

        if should_auto_fill_order(
            order=order,
            fill_policy=self.fill_policy,
        ):
            resolved_price = resolve_paper_fill_price(
                order=order,
                market_price=market_price,
                last_price=self.get_price(order.symbol),
            )

            if resolved_price <= 0:
                rejected = reject_paper_order(
                    order,
                    reason="Market price is required for paper market fill.",
                )
                self.orders[rejected.order_id] = rejected
                return order_to_broker_result(
                    rejected,
                    message="Paper order rejected.",
                )

            return self.fill_order(
                order_id=order.order_id,
                fill_quantity=order.quantity,
                fill_price=resolved_price,
            )

        return order_to_broker_result(
            order,
            message="Paper order accepted.",
        )

    def submit_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
        client_order_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BrokerResult:
        """Submit market order."""
        request = build_broker_order_request(
            broker_id=self.broker_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            client_order_id=client_order_id,
            metadata=metadata or {},
        )

        result = self.submit_order(
            request,
            market_price=market_price,
        )
        if result.failed:
            return result
        order_payload = result.data.get("order", {})
        order_id = order_payload.get("order_id", "")
        order_status = order_payload.get("status", "")
        if order_status == OrderStatus.ACCEPTED.value and market_price > 0:
            return self.fill_order(
                order_id=order_id,
                fill_quantity=quantity,
                fill_price=market_price,
            )
        return result  
    
    
    def fill_order(
        self,
        *,
        order_id: str,
        fill_quantity: float,
        fill_price: float,
        fee: float = 0.0,
    ) -> BrokerResult:
        """Fill existing paper order."""
        order = self.get_order(order_id)

        if order is None:
            return paper_broker_error_result(
                broker_id=self.broker_id,
                error="Order not found.",
                operation="fill_order",
                metadata={
                    "order_id": order_id,
                },
            )

        if not order.open:
            return paper_broker_error_result(
                broker_id=self.broker_id,
                error="Only open orders can be filled.",
                operation="fill_order",
                metadata={
                    "order_id": order.order_id,
                },
            )

        updated_order, trade = fill_broker_order(
            order,
            trade_id=self.next_trade_id(),
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            fee=fee,
        )

        self.orders[updated_order.order_id] = updated_order
        self.trades[trade.trade_id] = trade
        self.apply_cash_impact(trade)

        return broker_success(
            broker_id=self.broker_id,
            data={
                "order": updated_order.to_dict(),
                "trade": trade.to_dict(),
                "cash_balance": float(self.cash_balance),
            },
            message="Paper order filled.",
        )

    def cancel_order(self, order_id: str) -> BrokerResult:
        """Cancel paper order."""
        order = self.get_order(order_id)

        if order is None:
            return paper_broker_error_result(
                broker_id=self.broker_id,
                error="Order not found.",
                operation="cancel_order",
                metadata={
                    "order_id": order_id,
                },
            )

        try:
            cancelled = cancel_broker_order(order)
        except ValueError as exc:
            return paper_broker_error_result(
                broker_id=self.broker_id,
                error=str(exc),
                operation="cancel_order",
                metadata={
                    "order_id": order.order_id,
                },
            )

        self.orders[cancelled.order_id] = cancelled
        return order_to_broker_result(
            cancelled,
            message="Paper order cancelled.",
        )

    def get_order(self, order_id: str) -> BrokerOrder | None:
        """Get order by ID."""
        normalized_order_id = validate_non_empty_string(order_id, "Order ID")
        return self.orders.get(normalized_order_id)

    def get_trade(self, trade_id: str) -> BrokerTrade | None:
        """Get trade by ID."""
        normalized_trade_id = validate_non_empty_string(trade_id, "Trade ID")
        return self.trades.get(normalized_trade_id)

    def list_orders(self) -> list[BrokerOrder]:
        """List orders."""
        return list(self.orders.values())

    def list_trades(self) -> list[BrokerTrade]:
        """List trades."""
        return list(self.trades.values())

    def open_orders(self) -> list[BrokerOrder]:
        """List open orders."""
        return [order for order in self.orders.values() if order.open]

    def filled_orders(self) -> list[BrokerOrder]:
        """List filled orders."""
        return [order for order in self.orders.values() if order.filled]

    def trades_for_symbol(self, symbol: str) -> list[BrokerTrade]:
        """List trades for symbol."""
        normalized_symbol = validate_order_symbol(symbol)
        return [
            trade
            for trade in self.trades.values()
            if validate_order_symbol(trade.symbol) == normalized_symbol
        ]

    def apply_cash_impact(self, trade: BrokerTrade) -> float:
        """Apply trade cash impact."""
        if not isinstance(trade, BrokerTrade):
            raise ValueError("Trade must be a BrokerTrade.")

        if str(trade.side).lower().endswith("buy") or getattr(trade.side, "value", "") == "buy":
            self.cash_balance = round(
                self.cash_balance - trade.notional - trade.fee,
                6,
            )
        else:
            self.cash_balance = round(
                self.cash_balance + trade.notional - trade.fee,
                6,
            )

        return self.cash_balance

    def snapshot(self) -> PaperBrokerSnapshot:
        """Return paper broker snapshot."""
        return build_paper_broker_snapshot(
            broker_id=self.broker_id,
            cash_balance=self.cash_balance,
            orders=self.list_orders(),
            trades=self.list_trades(),
            metadata=dict(self.metadata),
        )

    def reset(self, *, cash_balance: float | None = None) -> None:
        """Reset paper broker state."""
        if cash_balance is not None:
            validate_non_negative_float(cash_balance, "Cash balance")
            self.cash_balance = float(cash_balance)

        self.orders.clear()
        self.trades.clear()
        self.last_prices.clear()
        self.order_sequence = 0
        self.trade_sequence = 0


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def normalize_paper_fill_policy(policy: PaperFillPolicy | str) -> PaperFillPolicy:
    """Normalize paper fill policy."""
    if isinstance(policy, PaperFillPolicy):
        return policy

    normalized = validate_non_empty_string(policy, "Paper fill policy").lower()

    try:
        return PaperFillPolicy(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PaperFillPolicy)
        raise ValueError(
            f"Invalid paper fill policy '{policy}'. Valid policies: {valid}.",
        ) from exc


def validate_paper_broker_config(config: BrokerConfig) -> BrokerConfig:
    """Validate paper broker config."""
    if not isinstance(config, BrokerConfig):
        raise ValueError("Broker config must be BrokerConfig.")

    if config.broker_type != BrokerType.PAPER and str(config.broker_type) != BrokerType.PAPER.value:
        raise ValueError("Paper broker requires a paper broker config.")

    if not config.paper_mode:
        raise ValueError("Paper broker config must use paper mode.")

    if not config.supports(BrokerCapability.PAPER_TRADING):
        raise ValueError("Broker config must support paper trading.")

    return config


def validate_paper_orders(orders: list[BrokerOrder]) -> list[BrokerOrder]:
    """Validate paper order list."""
    if not isinstance(orders, list):
        raise ValueError("Orders must be a list.")

    for order in orders:
        if not isinstance(order, BrokerOrder):
            raise ValueError("Orders must contain BrokerOrder objects.")

    return orders


def validate_paper_trades(trades: list[BrokerTrade]) -> list[BrokerTrade]:
    """Validate paper trade list."""
    if not isinstance(trades, list):
        raise ValueError("Trades must be a list.")

    for trade in trades:
        if not isinstance(trade, BrokerTrade):
            raise ValueError("Trades must contain BrokerTrade objects.")

    return trades


def validate_paper_order_dict(
    orders: dict[str, BrokerOrder],
) -> dict[str, BrokerOrder]:
    """Validate paper order dictionary."""
    if not isinstance(orders, dict):
        raise ValueError("Orders must be a dictionary.")

    for order_id, order in orders.items():
        validate_non_empty_string(order_id, "Order ID")

        if not isinstance(order, BrokerOrder):
            raise ValueError("Orders must contain BrokerOrder objects.")

    return orders


def validate_paper_trade_dict(
    trades: dict[str, BrokerTrade],
) -> dict[str, BrokerTrade]:
    """Validate paper trade dictionary."""
    if not isinstance(trades, dict):
        raise ValueError("Trades must be a dictionary.")

    for trade_id, trade in trades.items():
        validate_non_empty_string(trade_id, "Trade ID")

        if not isinstance(trade, BrokerTrade):
            raise ValueError("Trades must contain BrokerTrade objects.")

    return trades


def validate_paper_price_dict(prices: dict[str, float]) -> dict[str, float]:
    """Validate paper price dictionary."""
    if not isinstance(prices, dict):
        raise ValueError("Last prices must be a dictionary.")

    for symbol, price in prices.items():
        validate_order_symbol(symbol)
        validate_positive_float(price, "Price")

    return prices


def build_paper_broker_snapshot(
    *,
    broker_id: str,
    cash_balance: float,
    orders: list[BrokerOrder] | None = None,
    trades: list[BrokerTrade] | None = None,
    metadata: dict[str, Any] | None = None,
) -> PaperBrokerSnapshot:
    """Build paper broker snapshot."""
    return PaperBrokerSnapshot(
        broker_id=broker_id,
        cash_balance=cash_balance,
        orders=orders or [],
        trades=trades or [],
        metadata=metadata or {},
    )


def build_paper_broker_adapter(
    *,
    broker_config: BrokerConfig | None = None,
    broker_id: str = "paper-broker",
    name: str = "AQOS Paper Broker",
    cash_balance: float = 100_000.0,
    fill_policy: PaperFillPolicy | str = PaperFillPolicy.IMMEDIATE_MARKET,
    metadata: dict[str, Any] | None = None,
) -> PaperBrokerAdapter:
    """Build paper broker adapter."""
    resolved_config = broker_config or build_broker_config(
        broker_id=broker_id,
        name=name,
        broker_type=BrokerType.PAPER,
        status=BrokerStatus.ACTIVE,
        capabilities=[
            BrokerCapability.PAPER_TRADING,
            BrokerCapability.MARKET_ORDERS,
            BrokerCapability.LIMIT_ORDERS,
            BrokerCapability.STOP_ORDERS,
            BrokerCapability.ACCOUNT_INFO,
            BrokerCapability.POSITION_TRACKING,
            BrokerCapability.TRADE_HISTORY,
        ],
        paper_mode=True,
    )

    return PaperBrokerAdapter(
        broker_config=resolved_config,
        cash_balance=cash_balance,
        fill_policy=fill_policy,
        metadata=metadata or {},
    )


def should_auto_fill_order(
    *,
    order: BrokerOrder,
    fill_policy: PaperFillPolicy | str,
) -> bool:
    """Return whether order should auto-fill."""
    if not isinstance(order, BrokerOrder):
        raise ValueError("Order must be a BrokerOrder.")

    normalized_policy = normalize_paper_fill_policy(fill_policy)

    return (
        normalized_policy == PaperFillPolicy.IMMEDIATE_MARKET
        and order.order_type == OrderType.MARKET
    )


def resolve_paper_fill_price(
    *,
    order: BrokerOrder,
    market_price: float = 0.0,
    last_price: float = 0.0,
) -> float:
    """Resolve paper fill price."""
    if not isinstance(order, BrokerOrder):
        raise ValueError("Order must be a BrokerOrder.")

    validate_non_negative_float(market_price, "Market price")
    validate_non_negative_float(last_price, "Last price")

    if market_price > 0:
        return float(market_price)

    if last_price > 0:
        return float(last_price)

    if order.price > 0:
        return float(order.price)

    if order.stop_price > 0:
        return float(order.stop_price)

    return 0.0


def reject_paper_order(
    order: BrokerOrder,
    *,
    reason: str,
) -> BrokerOrder:
    """Reject paper order."""
    from aqos.brokers.orders import reject_broker_order

    return reject_broker_order(
        order,
        reason=reason,
    )


def submit_paper_order(
    *,
    adapter: PaperBrokerAdapter,
    request: BrokerOrderRequest,
    market_price: float = 0.0,
) -> BrokerResult:
    """Submit paper order through adapter."""
    if not isinstance(adapter, PaperBrokerAdapter):
        raise ValueError("Adapter must be a PaperBrokerAdapter.")

    return adapter.submit_order(
        request,
        market_price=market_price,
    )


def fill_paper_order(
    *,
    adapter: PaperBrokerAdapter,
    order_id: str,
    fill_quantity: float,
    fill_price: float,
    fee: float = 0.0,
) -> BrokerResult:
    """Fill paper order through adapter."""
    if not isinstance(adapter, PaperBrokerAdapter):
        raise ValueError("Adapter must be a PaperBrokerAdapter.")

    return adapter.fill_order(
        order_id=order_id,
        fill_quantity=fill_quantity,
        fill_price=fill_price,
        fee=fee,
    )


def cancel_paper_order(
    *,
    adapter: PaperBrokerAdapter,
    order_id: str,
) -> BrokerResult:
    """Cancel paper order through adapter."""
    if not isinstance(adapter, PaperBrokerAdapter):
        raise ValueError("Adapter must be a PaperBrokerAdapter.")

    return adapter.cancel_order(order_id)


def paper_broker_snapshot_result(adapter: PaperBrokerAdapter) -> BrokerResult:
    """Return paper broker snapshot as broker result."""
    if not isinstance(adapter, PaperBrokerAdapter):
        raise ValueError("Adapter must be a PaperBrokerAdapter.")

    return broker_success(
        broker_id=adapter.broker_id,
        data={
            "snapshot": adapter.snapshot().to_dict(),
        },
        message="Paper broker snapshot generated.",
    )


def paper_broker_error_result(
    *,
    broker_id: str,
    error: str,
    operation: str,
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build paper broker error result."""
    return order_error_result(
        broker_id=broker_id,
        error=error,
        operation=operation,
        metadata={
            "broker_type": "paper",
            **(metadata or {}),
        },
    )