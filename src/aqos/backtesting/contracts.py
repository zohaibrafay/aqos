from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


BACKTESTING_CONTRACTS_VERSION = "1.0"


class BacktestSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class BacktestSignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    EXIT = "exit"


class BacktestOrderType(str, Enum):
    MARKET = "market"


class BacktestOrderStatus(str, Enum):
    CREATED = "created"
    FILLED = "filled"
    REJECTED = "rejected"


class BacktestPositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class BacktestExitReason(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    SIGNAL_EXIT = "signal_exit"
    END_OF_DATA = "end_of_data"


class BacktestExecutionTiming(str, Enum):
    CURRENT_CLOSE = "current_close"
    NEXT_OPEN = "next_open"


@dataclass(frozen=True)
class BacktestBar:
    timestamp: str
    symbol: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp.strip():
            raise ValueError("timestamp cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty.")

        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            raise ValueError("OHLC prices must be positive.")

        if self.high < max(self.open, self.close):
            raise ValueError("high must be greater than or equal to open and close.")

        if self.low > min(self.open, self.close):
            raise ValueError("low must be less than or equal to open and close.")

        if self.volume < 0:
            raise ValueError("volume cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestSignal:
    timestamp: str
    symbol: str
    action: BacktestSignalAction
    confidence: float | None = None
    source: str = "unknown"
    stop_loss: float | None = None
    take_profit: float | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp.strip():
            raise ValueError("timestamp cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")

        if self.stop_loss is not None and self.stop_loss <= 0:
            raise ValueError("stop_loss must be positive.")

        if self.take_profit is not None and self.take_profit <= 0:
            raise ValueError("take_profit must be positive.")

    @property
    def side(self) -> BacktestSide | None:
        if self.action == BacktestSignalAction.BUY:
            return BacktestSide.LONG

        if self.action == BacktestSignalAction.SELL:
            return BacktestSide.SHORT

        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "action": self.action.value,
            "side": self.side.value if self.side is not None else None,
            "confidence": self.confidence,
            "source": self.source,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestExecutionConfig:
    initial_balance: float = 10_000.0
    risk_fraction: float = 0.01
    fixed_quantity: float | None = None
    spread_points: float = 0.0
    slippage_points: float = 0.0
    commission_per_trade: float = 0.0
    point_value: float = 1.0
    execution_timing: BacktestExecutionTiming = BacktestExecutionTiming.NEXT_OPEN
    allow_short: bool = True
    max_open_positions: int = 1

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive.")

        if not 0.0 < self.risk_fraction <= 1.0:
            raise ValueError("risk_fraction must be greater than 0 and less than or equal to 1.")

        if self.fixed_quantity is not None and self.fixed_quantity <= 0:
            raise ValueError("fixed_quantity must be positive.")

        if self.spread_points < 0:
            raise ValueError("spread_points cannot be negative.")

        if self.slippage_points < 0:
            raise ValueError("slippage_points cannot be negative.")

        if self.commission_per_trade < 0:
            raise ValueError("commission_per_trade cannot be negative.")

        if self.point_value <= 0:
            raise ValueError("point_value must be positive.")

        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_balance": self.initial_balance,
            "risk_fraction": self.risk_fraction,
            "fixed_quantity": self.fixed_quantity,
            "spread_points": self.spread_points,
            "slippage_points": self.slippage_points,
            "commission_per_trade": self.commission_per_trade,
            "point_value": self.point_value,
            "execution_timing": self.execution_timing.value,
            "allow_short": self.allow_short,
            "max_open_positions": self.max_open_positions,
        }


@dataclass(frozen=True)
class BacktestRunConfig:
    symbol: str
    timeframe: str
    strategy_name: str
    execution: BacktestExecutionConfig = dataclass_field(
        default_factory=BacktestExecutionConfig
    )
    start_timestamp: str | None = None
    end_timestamp: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty.")

        if not self.strategy_name.strip():
            raise ValueError("strategy_name cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "execution": self.execution.to_dict(),
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestOrder:
    order_id: str
    timestamp: str
    symbol: str
    side: BacktestSide
    order_type: BacktestOrderType
    requested_price: float
    quantity: float
    status: BacktestOrderStatus = BacktestOrderStatus.CREATED
    filled_price: float | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if not self.order_id.strip():
            raise ValueError("order_id cannot be empty.")

        if not self.timestamp.strip():
            raise ValueError("timestamp cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if self.requested_price <= 0:
            raise ValueError("requested_price must be positive.")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive.")

        if self.filled_price is not None and self.filled_price <= 0:
            raise ValueError("filled_price must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "requested_price": self.requested_price,
            "quantity": self.quantity,
            "status": self.status.value,
            "filled_price": self.filled_price,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BacktestPosition:
    position_id: str
    symbol: str
    side: BacktestSide
    entry_timestamp: str
    entry_price: float
    quantity: float
    stop_loss: float | None = None
    take_profit: float | None = None
    status: BacktestPositionStatus = BacktestPositionStatus.OPEN

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("position_id cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if not self.entry_timestamp.strip():
            raise ValueError("entry_timestamp cannot be empty.")

        if self.entry_price <= 0:
            raise ValueError("entry_price must be positive.")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive.")

        if self.stop_loss is not None and self.stop_loss <= 0:
            raise ValueError("stop_loss must be positive.")

        if self.take_profit is not None and self.take_profit <= 0:
            raise ValueError("take_profit must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_timestamp": self.entry_timestamp,
            "entry_price": self.entry_price,
            "quantity": self.quantity,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "status": self.status.value,
        }


@dataclass(frozen=True)
class BacktestTrade:
    trade_id: str
    position_id: str
    symbol: str
    side: BacktestSide
    entry_timestamp: str
    exit_timestamp: str
    entry_price: float
    exit_price: float
    quantity: float
    gross_pnl: float
    fees: float
    net_pnl: float
    return_fraction: float
    exit_reason: BacktestExitReason

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id cannot be empty.")

        if not self.position_id.strip():
            raise ValueError("position_id cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if not self.entry_timestamp.strip():
            raise ValueError("entry_timestamp cannot be empty.")

        if not self.exit_timestamp.strip():
            raise ValueError("exit_timestamp cannot be empty.")

        if self.entry_price <= 0 or self.exit_price <= 0:
            raise ValueError("entry_price and exit_price must be positive.")

        if self.quantity <= 0:
            raise ValueError("quantity must be positive.")

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "position_id": self.position_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_timestamp": self.entry_timestamp,
            "exit_timestamp": self.exit_timestamp,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "gross_pnl": self.gross_pnl,
            "fees": self.fees,
            "net_pnl": self.net_pnl,
            "return_fraction": self.return_fraction,
            "exit_reason": self.exit_reason.value,
            "is_win": self.is_win,
        }


@dataclass(frozen=True)
class BacktestEquityPoint:
    timestamp: str
    balance: float
    equity: float
    open_pnl: float = 0.0
    drawdown: float = 0.0

    def __post_init__(self) -> None:
        if not self.timestamp.strip():
            raise ValueError("timestamp cannot be empty.")

        if self.balance < 0:
            raise ValueError("balance cannot be negative.")

        if self.equity < 0:
            raise ValueError("equity cannot be negative.")

        if self.drawdown < 0:
            raise ValueError("drawdown cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "balance": self.balance,
            "equity": self.equity,
            "open_pnl": self.open_pnl,
            "drawdown": self.drawdown,
        }


def backtesting_utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def calculate_trade_gross_pnl(
    side: BacktestSide,
    entry_price: float,
    exit_price: float,
    quantity: float,
    point_value: float = 1.0,
) -> float:
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("entry_price and exit_price must be positive.")

    if quantity <= 0:
        raise ValueError("quantity must be positive.")

    if point_value <= 0:
        raise ValueError("point_value must be positive.")

    price_delta = exit_price - entry_price

    if side == BacktestSide.SHORT:
        price_delta = -price_delta

    return price_delta * quantity * point_value


def calculate_trade_return_fraction(
    side: BacktestSide,
    entry_price: float,
    exit_price: float,
) -> float:
    if entry_price <= 0 or exit_price <= 0:
        raise ValueError("entry_price and exit_price must be positive.")

    if side == BacktestSide.LONG:
        return (exit_price - entry_price) / entry_price

    return (entry_price - exit_price) / entry_price


def calculate_trade_fees(
    commission_per_trade: float,
) -> float:
    if commission_per_trade < 0:
        raise ValueError("commission_per_trade cannot be negative.")

    return commission_per_trade * 2.0


def calculate_net_pnl(
    gross_pnl: float,
    fees: float,
) -> float:
    if fees < 0:
        raise ValueError("fees cannot be negative.")

    return gross_pnl - fees


def calculate_drawdown(
    equity: float,
    peak_equity: float,
) -> float:
    if equity < 0:
        raise ValueError("equity cannot be negative.")

    if peak_equity <= 0:
        raise ValueError("peak_equity must be positive.")

    if equity >= peak_equity:
        return 0.0

    return (peak_equity - equity) / peak_equity


def build_backtest_trade(
    position: BacktestPosition,
    exit_timestamp: str,
    exit_price: float,
    exit_reason: BacktestExitReason,
    commission_per_trade: float = 0.0,
    point_value: float = 1.0,
) -> BacktestTrade:
    gross_pnl = calculate_trade_gross_pnl(
        side=position.side,
        entry_price=position.entry_price,
        exit_price=exit_price,
        quantity=position.quantity,
        point_value=point_value,
    )
    fees = calculate_trade_fees(commission_per_trade)
    net_pnl = calculate_net_pnl(gross_pnl, fees)

    return BacktestTrade(
        trade_id=f"trade_{position.position_id}",
        position_id=position.position_id,
        symbol=position.symbol,
        side=position.side,
        entry_timestamp=position.entry_timestamp,
        exit_timestamp=exit_timestamp,
        entry_price=position.entry_price,
        exit_price=exit_price,
        quantity=position.quantity,
        gross_pnl=gross_pnl,
        fees=fees,
        net_pnl=net_pnl,
        return_fraction=calculate_trade_return_fraction(
            position.side,
            position.entry_price,
            exit_price,
        ),
        exit_reason=exit_reason,
    )


__all__ = [
    "BACKTESTING_CONTRACTS_VERSION",
    "BacktestBar",
    "BacktestEquityPoint",
    "BacktestExecutionConfig",
    "BacktestExecutionTiming",
    "BacktestExitReason",
    "BacktestOrder",
    "BacktestOrderStatus",
    "BacktestOrderType",
    "BacktestPosition",
    "BacktestPositionStatus",
    "BacktestRunConfig",
    "BacktestSide",
    "BacktestSignal",
    "BacktestSignalAction",
    "BacktestTrade",
    "backtesting_utc_now_iso",
    "build_backtest_trade",
    "calculate_drawdown",
    "calculate_net_pnl",
    "calculate_trade_fees",
    "calculate_trade_gross_pnl",
    "calculate_trade_return_fraction",
]