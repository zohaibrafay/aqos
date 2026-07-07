"""
Broker service.

Provides a lightweight broker/order/position simulation service.
This service is designed as a future adapter layer for real brokers
such as MetaTrader, OANDA, Alpaca, Binance, or Interactive Brokers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any


@dataclass(slots=True, frozen=True)
class BrokerOrder:
    """
    Represents a broker order.
    """

    order_id: str
    symbol: str
    side: str
    quantity: float
    order_type: str
    status: str
    price: float | None = None
    fill_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class BrokerPosition:
    """
    Represents a broker position.
    """

    position_id: str
    order_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    status: str
    exit_price: float | None = None
    profit: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class BrokerService:
    """
    Service layer for broker-style order and position handling.
    """

    VALID_SIDES = {
        "buy",
        "sell",
    }

    VALID_ORDER_TYPES = {
        "market",
        "limit",
        "stop",
    }

    def __init__(self) -> None:
        self._orders: dict[str, BrokerOrder] = {}
        self._positions: dict[str, BrokerPosition] = {}

    def place_order(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> BrokerOrder:
        """
        Place a broker order.
        """

        self._validate_order_id(order_id)
        self._validate_symbol(symbol)

        normalized_side = side.lower().strip()
        normalized_order_type = order_type.lower().strip()

        self._validate_side(normalized_side)
        self._validate_quantity(quantity)
        self._validate_order_type(normalized_order_type)

        if order_id in self._orders:
            raise ValueError("Order already exists.")

        if normalized_order_type in {"limit", "stop"} and price is None:
            raise ValueError("Limit and stop orders require a price.")

        if price is not None:
            self._validate_price(price)

        order = BrokerOrder(
            order_id=order_id,
            symbol=symbol,
            side=normalized_side,
            quantity=quantity,
            order_type=normalized_order_type,
            status="open",
            price=price,
            fill_price=None,
            metadata=metadata or {},
        )

        self._orders[order_id] = order

        return order

    def get_order(
        self,
        order_id: str,
    ) -> BrokerOrder | None:
        """
        Get an order by ID.
        """

        self._validate_order_id(order_id)

        return self._orders.get(order_id)

    def get_required_order(
        self,
        order_id: str,
    ) -> BrokerOrder:
        """
        Get an order or raise if it does not exist.
        """

        order = self.get_order(order_id)

        if order is None:
            raise ValueError("Order does not exist.")

        return order

    def exists_order(
        self,
        order_id: str,
    ) -> bool:
        """
        Check whether an order exists.
        """

        self._validate_order_id(order_id)

        return order_id in self._orders

    def list_orders(self) -> list[BrokerOrder]:
        """
        Return all broker orders.
        """

        return list(self._orders.values())

    def list_order_ids(self) -> list[str]:
        """
        Return order IDs.
        """

        return sorted(self._orders.keys())

    def open_orders(self) -> list[BrokerOrder]:
        """
        Return open orders.
        """

        return [
            order
            for order in self._orders.values()
            if order.status == "open"
        ]

    def filled_orders(self) -> list[BrokerOrder]:
        """
        Return filled orders.
        """

        return [
            order
            for order in self._orders.values()
            if order.status == "filled"
        ]

    def cancelled_orders(self) -> list[BrokerOrder]:
        """
        Return cancelled orders.
        """

        return [
            order
            for order in self._orders.values()
            if order.status == "cancelled"
        ]

    def cancel_order(
        self,
        order_id: str,
    ) -> BrokerOrder:
        """
        Cancel an open order.
        """

        order = self.get_required_order(order_id)

        if order.status != "open":
            raise ValueError("Only open orders can be cancelled.")

        cancelled = replace(
            order,
            status="cancelled",
        )

        self._orders[order_id] = cancelled

        return cancelled

    def fill_order(
        self,
        order_id: str,
        fill_price: float,
    ) -> BrokerOrder:
        """
        Fill an open order and create an open position.
        """

        self._validate_price(fill_price)

        order = self.get_required_order(order_id)

        if order.status != "open":
            raise ValueError("Only open orders can be filled.")

        filled = replace(
            order,
            status="filled",
            fill_price=fill_price,
        )

        self._orders[order_id] = filled

        position_id = f"position-{order_id}"

        position = BrokerPosition(
            position_id=position_id,
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            entry_price=fill_price,
            status="open",
            exit_price=None,
            profit=0.0,
            metadata=dict(order.metadata),
        )

        self._positions[position_id] = position

        return filled

    def get_position(
        self,
        position_id: str,
    ) -> BrokerPosition | None:
        """
        Get a position by ID.
        """

        self._validate_position_id(position_id)

        return self._positions.get(position_id)

    def get_required_position(
        self,
        position_id: str,
    ) -> BrokerPosition:
        """
        Get a position or raise if it does not exist.
        """

        position = self.get_position(position_id)

        if position is None:
            raise ValueError("Position does not exist.")

        return position

    def list_positions(self) -> list[BrokerPosition]:
        """
        Return all positions.
        """

        return list(self._positions.values())

    def open_positions(self) -> list[BrokerPosition]:
        """
        Return open positions.
        """

        return [
            position
            for position in self._positions.values()
            if position.status == "open"
        ]

    def closed_positions(self) -> list[BrokerPosition]:
        """
        Return closed positions.
        """

        return [
            position
            for position in self._positions.values()
            if position.status == "closed"
        ]

    def close_position(
        self,
        position_id: str,
        exit_price: float,
    ) -> BrokerPosition:
        """
        Close an open position.
        """

        self._validate_price(exit_price)

        position = self.get_required_position(position_id)

        if position.status != "open":
            raise ValueError("Only open positions can be closed.")

        profit = self._calculate_profit(
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            exit_price=exit_price,
        )

        closed = replace(
            position,
            status="closed",
            exit_price=exit_price,
            profit=profit,
        )

        self._positions[position_id] = closed

        return closed

    def realized_profit(self) -> float:
        """
        Return total realized profit from closed positions.
        """

        return sum(
            position.profit
            for position in self.closed_positions()
        )

    def count_orders(self) -> int:
        """
        Return number of orders.
        """

        return len(self._orders)

    def count_positions(self) -> int:
        """
        Return number of positions.
        """

        return len(self._positions)

    def clear(self) -> None:
        """
        Clear all broker orders and positions.
        """

        self._orders.clear()
        self._positions.clear()

    def _calculate_profit(
        self,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
    ) -> float:
        """
        Calculate position profit.
        """

        if side == "buy":
            return (exit_price - entry_price) * quantity

        return (entry_price - exit_price) * quantity

    def _validate_order_id(
        self,
        order_id: str,
    ) -> None:
        """
        Validate order ID.
        """

        if not order_id:
            raise ValueError("Order ID cannot be empty.")

    def _validate_position_id(
        self,
        position_id: str,
    ) -> None:
        """
        Validate position ID.
        """

        if not position_id:
            raise ValueError("Position ID cannot be empty.")

    def _validate_symbol(
        self,
        symbol: str,
    ) -> None:
        """
        Validate symbol.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

    def _validate_side(
        self,
        side: str,
    ) -> None:
        """
        Validate order side.
        """

        if side not in self.VALID_SIDES:
            raise ValueError("Side must be either buy or sell.")

    def _validate_order_type(
        self,
        order_type: str,
    ) -> None:
        """
        Validate order type.
        """

        if order_type not in self.VALID_ORDER_TYPES:
            raise ValueError("Order type must be market, limit, or stop.")

    def _validate_quantity(
        self,
        quantity: float,
    ) -> None:
        """
        Validate quantity.
        """

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

    def _validate_price(
        self,
        price: float,
    ) -> None:
        """
        Validate price.
        """

        if price <= 0:
            raise ValueError("Price must be greater than zero.")


__all__ = [
    "BrokerOrder",
    "BrokerPosition",
    "BrokerService",
]