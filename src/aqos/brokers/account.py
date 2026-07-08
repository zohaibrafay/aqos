"""
AQOS broker account and position contracts.

This module contains dependency-free account, position, and portfolio-state
helpers for paper brokers, exchange adapters, and execution integration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.brokers.base import (
    BrokerConfig,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_string,
)
from aqos.brokers.orders import (
    BrokerTrade,
    OrderSide,
    normalize_order_side,
    validate_order_symbol,
)


class PositionSide(str, Enum):
    """Supported broker position sides."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


@dataclass(frozen=True)
class BrokerAccount:
    """Broker account state."""

    broker_id: str
    account_id: str
    currency: str = "USD"
    cash_balance: float = 0.0
    equity: float = 0.0
    buying_power: float = 0.0
    margin_used: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_non_empty_string(self.account_id, "Account ID")
        validate_account_currency(self.currency)
        validate_non_negative_float(self.cash_balance, "Cash balance")
        validate_non_negative_float(self.equity, "Equity")
        validate_non_negative_float(self.buying_power, "Buying power")
        validate_non_negative_float(self.margin_used, "Margin used")
        validate_number(self.realized_pnl, "Realized PnL")
        validate_number(self.unrealized_pnl, "Unrealized PnL")
        validate_non_empty_string(self.updated_at, "Updated at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def available_cash(self) -> float:
        """Return available cash after margin."""
        return round(max(0.0, float(self.cash_balance) - float(self.margin_used)), 6)

    @property
    def total_pnl(self) -> float:
        """Return total PnL."""
        return round(float(self.realized_pnl) + float(self.unrealized_pnl), 6)

    def to_dict(self) -> dict[str, Any]:
        """Convert account into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "account_id": self.account_id.strip(),
            "currency": validate_account_currency(self.currency),
            "cash_balance": float(self.cash_balance),
            "equity": float(self.equity),
            "buying_power": float(self.buying_power),
            "margin_used": float(self.margin_used),
            "available_cash": self.available_cash,
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
            "total_pnl": self.total_pnl,
            "updated_at": self.updated_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerPosition:
    """Broker position state."""

    position_id: str
    broker_id: str
    symbol: str
    side: PositionSide | str
    quantity: float
    average_price: float
    market_price: float = 0.0
    realized_pnl: float = 0.0
    fees: float = 0.0
    opened_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.position_id, "Position ID")
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_order_symbol(self.symbol)
        normalized_side = normalize_position_side(self.side)
        validate_non_negative_float(self.quantity, "Quantity")
        validate_non_negative_float(self.average_price, "Average price")
        validate_non_negative_float(self.market_price, "Market price")
        validate_number(self.realized_pnl, "Realized PnL")
        validate_non_negative_float(self.fees, "Fees")
        validate_non_empty_string(self.opened_at, "Opened at")
        validate_non_empty_string(self.updated_at, "Updated at")
        validate_metadata(self.metadata, "Metadata")

        if normalized_side != PositionSide.FLAT and self.quantity <= 0:
            raise ValueError("Long and short positions require positive quantity.")

        if normalized_side == PositionSide.FLAT and self.quantity != 0:
            raise ValueError("Flat positions must have zero quantity.")

    @property
    def open(self) -> bool:
        """Return whether position is open."""
        return normalize_position_side(self.side) != PositionSide.FLAT and self.quantity > 0

    @property
    def notional(self) -> float:
        """Return average-price notional."""
        return round(float(self.quantity) * float(self.average_price), 6)

    @property
    def market_value(self) -> float:
        """Return signed market value."""
        side = normalize_position_side(self.side)

        if side == PositionSide.FLAT:
            return 0.0

        value = float(self.quantity) * float(self.current_price)

        if side == PositionSide.SHORT:
            return round(-value, 6)

        return round(value, 6)

    @property
    def current_price(self) -> float:
        """Return market price if available, otherwise average price."""
        return float(self.market_price) if self.market_price > 0 else float(self.average_price)

    @property
    def unrealized_pnl(self) -> float:
        """Return unrealized PnL."""
        side = normalize_position_side(self.side)

        if side == PositionSide.FLAT:
            return 0.0

        if side == PositionSide.LONG:
            return round((self.current_price - self.average_price) * self.quantity, 6)

        return round((self.average_price - self.current_price) * self.quantity, 6)

    @property
    def total_pnl(self) -> float:
        """Return realized plus unrealized PnL minus fees."""
        return round(float(self.realized_pnl) + self.unrealized_pnl - float(self.fees), 6)

    def to_dict(self) -> dict[str, Any]:
        """Convert position into dictionary."""
        return {
            "position_id": self.position_id.strip(),
            "broker_id": self.broker_id.strip(),
            "symbol": validate_order_symbol(self.symbol),
            "side": normalize_position_side(self.side).value,
            "quantity": float(self.quantity),
            "average_price": float(self.average_price),
            "market_price": float(self.market_price),
            "current_price": self.current_price,
            "notional": self.notional,
            "market_value": self.market_value,
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": self.unrealized_pnl,
            "fees": float(self.fees),
            "total_pnl": self.total_pnl,
            "open": self.open,
            "opened_at": self.opened_at.strip(),
            "updated_at": self.updated_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class BrokerAccountSnapshot:
    """Broker account snapshot."""

    account: BrokerAccount
    positions: list[BrokerPosition] = field(default_factory=list)
    trades: list[BrokerTrade] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.account, BrokerAccount):
            raise ValueError("Account must be BrokerAccount.")

        validate_broker_positions(self.positions)
        validate_broker_trades(self.trades)
        validate_metadata(self.metadata, "Metadata")

    @property
    def position_count(self) -> int:
        """Return position count."""
        return len(self.positions)

    @property
    def open_position_count(self) -> int:
        """Return open position count."""
        return len([position for position in self.positions if position.open])

    @property
    def trade_count(self) -> int:
        """Return trade count."""
        return len(self.trades)

    @property
    def total_market_value(self) -> float:
        """Return total signed market value."""
        return round(sum(position.market_value for position in self.positions), 6)

    @property
    def total_unrealized_pnl(self) -> float:
        """Return total unrealized PnL."""
        return round(sum(position.unrealized_pnl for position in self.positions), 6)

    def to_dict(self) -> dict[str, Any]:
        """Convert account snapshot into dictionary."""
        return {
            "account": self.account.to_dict(),
            "positions": [position.to_dict() for position in self.positions],
            "trades": [trade.to_dict() for trade in self.trades],
            "position_count": self.position_count,
            "open_position_count": self.open_position_count,
            "trade_count": self.trade_count,
            "total_market_value": self.total_market_value,
            "total_unrealized_pnl": self.total_unrealized_pnl,
            "metadata": dict(self.metadata),
        }


@dataclass
class PositionAccountAdapter:
    """In-memory account and position adapter."""

    broker_config: BrokerConfig
    account: BrokerAccount
    positions: dict[str, BrokerPosition] = field(default_factory=dict)
    trades: dict[str, BrokerTrade] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.broker_config, BrokerConfig):
            raise ValueError("Broker config must be BrokerConfig.")

        if not isinstance(self.account, BrokerAccount):
            raise ValueError("Account must be BrokerAccount.")

        if self.account.broker_id.strip() != self.broker_config.broker_id.strip():
            raise ValueError("Account broker ID must match broker config broker ID.")

        validate_position_dict(self.positions)
        validate_trade_dict(self.trades)
        validate_metadata(self.metadata, "Metadata")

    @property
    def broker_id(self) -> str:
        """Return broker ID."""
        return self.broker_config.broker_id.strip()

    @property
    def account_id(self) -> str:
        """Return account ID."""
        return self.account.account_id.strip()

    def get_position(self, symbol: str) -> BrokerPosition | None:
        """Get position by symbol."""
        return self.positions.get(validate_order_symbol(symbol))

    def list_positions(self) -> list[BrokerPosition]:
        """List all positions."""
        return list(self.positions.values())

    def open_positions(self) -> list[BrokerPosition]:
        """List open positions."""
        return [position for position in self.positions.values() if position.open]

    def list_trades(self) -> list[BrokerTrade]:
        """List trades."""
        return list(self.trades.values())

    def update_market_price(self, *, symbol: str, market_price: float) -> BrokerPosition | None:
        """Update market price for an existing position."""
        validate_positive_float(market_price, "Market price")
        position = self.get_position(symbol)

        if position is None:
            return None

        updated = build_broker_position(
            position_id=position.position_id,
            broker_id=position.broker_id,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            average_price=position.average_price,
            market_price=market_price,
            realized_pnl=position.realized_pnl,
            fees=position.fees,
            opened_at=position.opened_at,
            metadata=position.metadata,
        )

        self.positions[validate_order_symbol(symbol)] = updated
        self.refresh_account()
        return updated

    def apply_trade(self, trade: BrokerTrade) -> BrokerPosition:
        """Apply broker trade to positions."""
        if not isinstance(trade, BrokerTrade):
            raise ValueError("Trade must be BrokerTrade.")

        if trade.broker_id.strip() != self.broker_id:
            raise ValueError("Trade broker ID must match adapter broker ID.")

        symbol = validate_order_symbol(trade.symbol)
        existing = self.positions.get(symbol)
        updated = apply_trade_to_position(
            existing_position=existing,
            trade=trade,
        )

        if updated.open:
            self.positions[symbol] = updated
        else:
            self.positions.pop(symbol, None)

        self.trades[trade.trade_id.strip()] = trade
        self.refresh_account()
        return updated

    def refresh_account(self) -> BrokerAccount:
        """Refresh derived account values."""
        unrealized_pnl = round(
            sum(position.unrealized_pnl for position in self.positions.values()),
            6,
        )
        realized_pnl = round(
            sum(position.realized_pnl for position in self.positions.values()),
            6,
        )
        market_value = round(
            sum(abs(position.market_value) for position in self.positions.values()),
            6,
        )
        equity = round(self.account.cash_balance + unrealized_pnl + realized_pnl, 6)
        buying_power = round(max(0.0, equity - self.account.margin_used), 6)

        self.account = build_broker_account(
            broker_id=self.account.broker_id,
            account_id=self.account.account_id,
            currency=self.account.currency,
            cash_balance=self.account.cash_balance,
            equity=max(0.0, equity),
            buying_power=buying_power,
            margin_used=self.account.margin_used,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            metadata={
                **self.account.metadata,
                "gross_market_value": market_value,
            },
        )

        return self.account

    def snapshot(self) -> BrokerAccountSnapshot:
        """Return account snapshot."""
        self.refresh_account()

        return build_broker_account_snapshot(
            account=self.account,
            positions=self.list_positions(),
            trades=self.list_trades(),
            metadata=dict(self.metadata),
        )

    def reset_positions(self) -> None:
        """Reset positions and trades."""
        self.positions.clear()
        self.trades.clear()
        self.refresh_account()


def validate_number(value: float | int, field_name: str) -> float:
    """Validate numeric value."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    return float(value)


def validate_account_currency(currency: str) -> str:
    """Validate account currency."""
    normalized = validate_non_empty_string(currency, "Currency").upper()

    if not normalized.isalpha() or len(normalized) != 3:
        raise ValueError("Currency must be a 3-letter ISO-style code.")

    return normalized


def normalize_position_side(side: PositionSide | str) -> PositionSide:
    """Normalize position side."""
    if isinstance(side, PositionSide):
        return side

    normalized = validate_non_empty_string(side, "Position side").lower()

    try:
        return PositionSide(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PositionSide)
        raise ValueError(
            f"Invalid position side '{side}'. Valid sides: {valid}.",
        ) from exc


def validate_broker_positions(
    positions: list[BrokerPosition],
) -> list[BrokerPosition]:
    """Validate broker position list."""
    if not isinstance(positions, list):
        raise ValueError("Positions must be a list.")

    for position in positions:
        if not isinstance(position, BrokerPosition):
            raise ValueError("Positions must contain BrokerPosition objects.")

    return positions


def validate_broker_trades(trades: list[BrokerTrade]) -> list[BrokerTrade]:
    """Validate broker trade list."""
    if not isinstance(trades, list):
        raise ValueError("Trades must be a list.")

    for trade in trades:
        if not isinstance(trade, BrokerTrade):
            raise ValueError("Trades must contain BrokerTrade objects.")

    return trades


def validate_position_dict(
    positions: dict[str, BrokerPosition],
) -> dict[str, BrokerPosition]:
    """Validate position dictionary."""
    if not isinstance(positions, dict):
        raise ValueError("Positions must be a dictionary.")

    for symbol, position in positions.items():
        validate_order_symbol(symbol)

        if not isinstance(position, BrokerPosition):
            raise ValueError("Positions must contain BrokerPosition objects.")

    return positions


def validate_trade_dict(trades: dict[str, BrokerTrade]) -> dict[str, BrokerTrade]:
    """Validate trade dictionary."""
    if not isinstance(trades, dict):
        raise ValueError("Trades must be a dictionary.")

    for trade_id, trade in trades.items():
        validate_non_empty_string(trade_id, "Trade ID")

        if not isinstance(trade, BrokerTrade):
            raise ValueError("Trades must contain BrokerTrade objects.")

    return trades


def build_broker_account(
    *,
    broker_id: str,
    account_id: str,
    currency: str = "USD",
    cash_balance: float = 0.0,
    equity: float | None = None,
    buying_power: float | None = None,
    margin_used: float = 0.0,
    realized_pnl: float = 0.0,
    unrealized_pnl: float = 0.0,
    updated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerAccount:
    """Build broker account."""
    resolved_equity = cash_balance if equity is None else equity
    resolved_buying_power = resolved_equity if buying_power is None else buying_power

    account_kwargs: dict[str, Any] = {
        "broker_id": broker_id,
        "account_id": account_id,
        "currency": currency,
        "cash_balance": cash_balance,
        "equity": resolved_equity,
        "buying_power": resolved_buying_power,
        "margin_used": margin_used,
        "realized_pnl": realized_pnl,
        "unrealized_pnl": unrealized_pnl,
        "metadata": metadata or {},
    }

    if updated_at is not None:
        account_kwargs["updated_at"] = updated_at

    return BrokerAccount(**account_kwargs)


def build_broker_position(
    *,
    position_id: str,
    broker_id: str,
    symbol: str,
    side: PositionSide | str,
    quantity: float,
    average_price: float,
    market_price: float = 0.0,
    realized_pnl: float = 0.0,
    fees: float = 0.0,
    opened_at: str | None = None,
    updated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerPosition:
    """Build broker position."""
    position_kwargs: dict[str, Any] = {
        "position_id": position_id,
        "broker_id": broker_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "average_price": average_price,
        "market_price": market_price,
        "realized_pnl": realized_pnl,
        "fees": fees,
        "metadata": metadata or {},
    }

    if opened_at is not None:
        position_kwargs["opened_at"] = opened_at

    if updated_at is not None:
        position_kwargs["updated_at"] = updated_at

    return BrokerPosition(**position_kwargs)


def build_broker_account_snapshot(
    *,
    account: BrokerAccount,
    positions: list[BrokerPosition] | None = None,
    trades: list[BrokerTrade] | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerAccountSnapshot:
    """Build broker account snapshot."""
    return BrokerAccountSnapshot(
        account=account,
        positions=positions or [],
        trades=trades or [],
        metadata=metadata or {},
    )


def build_position_account_adapter(
    *,
    broker_config: BrokerConfig,
    account: BrokerAccount | None = None,
    account_id: str = "paper-account",
    cash_balance: float = 100_000.0,
    metadata: dict[str, Any] | None = None,
) -> PositionAccountAdapter:
    """Build position account adapter."""
    if not isinstance(broker_config, BrokerConfig):
        raise ValueError("Broker config must be BrokerConfig.")

    resolved_account = account or build_broker_account(
        broker_id=broker_config.broker_id,
        account_id=account_id,
        cash_balance=cash_balance,
        metadata={
            "source": "position_account_adapter",
        },
    )

    return PositionAccountAdapter(
        broker_config=broker_config,
        account=resolved_account,
        metadata=metadata or {},
    )


def position_id_for_symbol(*, broker_id: str, symbol: str) -> str:
    """Build deterministic position ID for broker/symbol."""
    return f"{validate_non_empty_string(broker_id, 'Broker ID')}-position-{validate_order_symbol(symbol)}"


def position_side_from_trade_side(side: OrderSide | str) -> PositionSide:
    """Convert order side into position side."""
    normalized_side = normalize_order_side(side)

    if normalized_side == OrderSide.BUY:
        return PositionSide.LONG

    return PositionSide.SHORT


def opposite_position_side(side: PositionSide | str) -> PositionSide:
    """Return opposite position side."""
    normalized_side = normalize_position_side(side)

    if normalized_side == PositionSide.LONG:
        return PositionSide.SHORT

    if normalized_side == PositionSide.SHORT:
        return PositionSide.LONG

    return PositionSide.FLAT


def calculate_realized_pnl(
    *,
    position: BrokerPosition,
    exit_quantity: float,
    exit_price: float,
) -> float:
    """Calculate realized PnL for closing quantity."""
    if not isinstance(position, BrokerPosition):
        raise ValueError("Position must be BrokerPosition.")

    validate_positive_float(exit_quantity, "Exit quantity")
    validate_positive_float(exit_price, "Exit price")

    if exit_quantity > position.quantity:
        raise ValueError("Exit quantity cannot exceed position quantity.")

    side = normalize_position_side(position.side)

    if side == PositionSide.LONG:
        return round((exit_price - position.average_price) * exit_quantity, 6)

    if side == PositionSide.SHORT:
        return round((position.average_price - exit_price) * exit_quantity, 6)

    return 0.0


def apply_trade_to_position(
    *,
    existing_position: BrokerPosition | None,
    trade: BrokerTrade,
) -> BrokerPosition:
    """Apply trade to existing position and return updated position."""
    if existing_position is not None and not isinstance(existing_position, BrokerPosition):
        raise ValueError("Existing position must be BrokerPosition or None.")

    if not isinstance(trade, BrokerTrade):
        raise ValueError("Trade must be BrokerTrade.")

    trade_side = position_side_from_trade_side(trade.side)
    symbol = validate_order_symbol(trade.symbol)
    timestamp = trade.executed_at

    if existing_position is None:
        return build_broker_position(
            position_id=position_id_for_symbol(
                broker_id=trade.broker_id,
                symbol=symbol,
            ),
            broker_id=trade.broker_id,
            symbol=symbol,
            side=trade_side,
            quantity=trade.quantity,
            average_price=trade.price,
            market_price=trade.price,
            realized_pnl=0.0,
            fees=trade.fee,
            opened_at=timestamp,
            updated_at=timestamp,
            metadata={
                "created_from_trade_id": trade.trade_id,
            },
        )

    existing_side = normalize_position_side(existing_position.side)

    if existing_side == trade_side:
        new_quantity = round(existing_position.quantity + trade.quantity, 6)
        weighted_notional = (
            existing_position.quantity * existing_position.average_price
        ) + (
            trade.quantity * trade.price
        )
        average_price = round(weighted_notional / new_quantity, 6)

        return build_broker_position(
            position_id=existing_position.position_id,
            broker_id=existing_position.broker_id,
            symbol=existing_position.symbol,
            side=existing_side,
            quantity=new_quantity,
            average_price=average_price,
            market_price=trade.price,
            realized_pnl=existing_position.realized_pnl,
            fees=round(existing_position.fees + trade.fee, 6),
            opened_at=existing_position.opened_at,
            updated_at=timestamp,
            metadata=existing_position.metadata,
        )

    close_quantity = min(existing_position.quantity, trade.quantity)
    realized_delta = calculate_realized_pnl(
        position=existing_position,
        exit_quantity=close_quantity,
        exit_price=trade.price,
    )
    remaining_quantity = round(existing_position.quantity - trade.quantity, 6)

    if remaining_quantity > 0:
        return build_broker_position(
            position_id=existing_position.position_id,
            broker_id=existing_position.broker_id,
            symbol=existing_position.symbol,
            side=existing_side,
            quantity=remaining_quantity,
            average_price=existing_position.average_price,
            market_price=trade.price,
            realized_pnl=round(existing_position.realized_pnl + realized_delta, 6),
            fees=round(existing_position.fees + trade.fee, 6),
            opened_at=existing_position.opened_at,
            updated_at=timestamp,
            metadata=existing_position.metadata,
        )

    if remaining_quantity == 0:
        return build_broker_position(
            position_id=existing_position.position_id,
            broker_id=existing_position.broker_id,
            symbol=existing_position.symbol,
            side=PositionSide.FLAT,
            quantity=0.0,
            average_price=0.0,
            market_price=trade.price,
            realized_pnl=round(existing_position.realized_pnl + realized_delta, 6),
            fees=round(existing_position.fees + trade.fee, 6),
            opened_at=existing_position.opened_at,
            updated_at=timestamp,
            metadata=existing_position.metadata,
        )

    flipped_quantity = abs(remaining_quantity)

    return build_broker_position(
        position_id=existing_position.position_id,
        broker_id=existing_position.broker_id,
        symbol=existing_position.symbol,
        side=opposite_position_side(existing_side),
        quantity=flipped_quantity,
        average_price=trade.price,
        market_price=trade.price,
        realized_pnl=round(existing_position.realized_pnl + realized_delta, 6),
        fees=round(existing_position.fees + trade.fee, 6),
        opened_at=existing_position.opened_at,
        updated_at=timestamp,
        metadata={
            **existing_position.metadata,
            "flipped_by_trade_id": trade.trade_id,
        },
    )