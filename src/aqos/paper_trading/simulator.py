from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from aqos.paper_trading.contracts import (
    PaperAction,
    PaperPosition,
    PaperSide,
    PaperTradingError,
)


AQOS_PAPER_SIMULATOR_VERSION = "1.0"


class PaperExitReason(str, Enum):
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    MANUAL_CLOSE = "manual_close"
    END_OF_DATA = "end_of_data"


class IntrabarExitPolicy(str, Enum):
    """
    Which side wins when a bar contains both the stop and the target.

    A single bar has no ordering inside it, so the policy has to be stated.
    ``STOP_LOSS_FIRST`` is the default because assuming the favourable fill
    would quietly overstate every result.
    """

    STOP_LOSS_FIRST = "stop_loss_first"
    TAKE_PROFIT_FIRST = "take_profit_first"


@dataclass(frozen=True)
class PaperMarketBar:
    """
    One OHLCV bar the simulator prices against.

    Paper trading keeps its own bar type rather than importing the backtesting
    one: the research and product paths must be free to evolve separately.
    """

    symbol: str
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise PaperTradingError("bar symbol cannot be empty.")

        for name in ("open", "high", "low", "close"):
            if getattr(self, name) <= 0:
                raise PaperTradingError(f"bar {name} must be positive.")

        if self.high < max(self.open, self.close):
            raise PaperTradingError("bar high must cover open and close.")

        if self.low > min(self.open, self.close):
            raise PaperTradingError("bar low must cover open and close.")

        if self.volume < 0:
            raise PaperTradingError("bar volume cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
        }


@dataclass(frozen=True)
class PaperSimulatorConfig:
    """Execution costs and conventions applied to every simulated fill."""

    spread_points: float = 0.0
    slippage_points: float = 0.0
    commission_per_fill: float = 0.0
    point_size: float = 1.0
    contract_size: float = 1.0
    intrabar_exit_policy: IntrabarExitPolicy = IntrabarExitPolicy.STOP_LOSS_FIRST
    fill_on_bar_open: bool = True

    def __post_init__(self) -> None:
        if self.spread_points < 0:
            raise PaperTradingError("spread_points cannot be negative.")

        if self.slippage_points < 0:
            raise PaperTradingError("slippage_points cannot be negative.")

        if self.commission_per_fill < 0:
            raise PaperTradingError("commission_per_fill cannot be negative.")

        if self.point_size <= 0:
            raise PaperTradingError("point_size must be positive.")

        if self.contract_size <= 0:
            raise PaperTradingError("contract_size must be positive.")

    @property
    def cost_per_side(self) -> float:
        """Price adjustment applied to one side of a fill."""

        return (self.spread_points + self.slippage_points) * self.point_size

    def to_dict(self) -> dict[str, Any]:
        return {
            "spread_points": self.spread_points,
            "slippage_points": self.slippage_points,
            "commission_per_fill": self.commission_per_fill,
            "point_size": self.point_size,
            "contract_size": self.contract_size,
            "intrabar_exit_policy": self.intrabar_exit_policy.value,
            "fill_on_bar_open": self.fill_on_bar_open,
        }


@dataclass(frozen=True)
class PositionExitDecision:
    should_exit: bool
    exit_reason: PaperExitReason | None = None
    exit_price: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_exit": self.should_exit,
            "exit_reason": self.exit_reason.value if self.exit_reason else None,
            "exit_price": self.exit_price,
        }


def is_buy_fill(
    action: PaperAction,
    position_side: PaperSide | None = None,
) -> bool:
    """
    Whether a fill buys or sells.

    Closing a long sells; closing a short buys. Getting this backwards would
    apply the spread in the wrong direction and flatter every result.
    """

    if action == PaperAction.BUY:
        return True

    if action == PaperAction.SELL:
        return False

    if position_side is None:
        raise PaperTradingError(
            "Closing a position requires the side being closed."
        )

    return position_side == PaperSide.SHORT


def calculate_fill_price(
    reference_price: float,
    is_buy: bool,
    config: PaperSimulatorConfig,
) -> float:
    """
    Apply spread and slippage to a reference price.

    Costs always move against the trader: a buy pays more, a sell receives less.
    """

    if reference_price <= 0:
        raise PaperTradingError("reference_price must be positive.")

    adjustment = config.cost_per_side
    price = reference_price + adjustment if is_buy else reference_price - adjustment

    if price <= 0:
        raise PaperTradingError(
            "Execution costs would push the fill price to zero or below."
        )

    return price


def resolve_reference_price(
    bar: PaperMarketBar,
    config: PaperSimulatorConfig,
) -> float:
    return bar.open if config.fill_on_bar_open else bar.close


def is_stop_loss_hit(position: PaperPosition, bar: PaperMarketBar) -> bool:
    if position.stop_loss is None:
        return False

    if position.side == PaperSide.LONG:
        return bar.low <= position.stop_loss

    return bar.high >= position.stop_loss


def is_take_profit_hit(position: PaperPosition, bar: PaperMarketBar) -> bool:
    if position.take_profit is None:
        return False

    if position.side == PaperSide.LONG:
        return bar.high >= position.take_profit

    return bar.low <= position.take_profit


def resolve_position_exit(
    position: PaperPosition,
    bar: PaperMarketBar,
    config: PaperSimulatorConfig,
) -> PositionExitDecision:
    """
    Decide whether a bar closes a position on its stop or its target.

    When a bar reaches both levels the configured policy decides, defaulting to
    the stop so results are never flattered by an assumption.
    """

    if not position.is_open:
        return PositionExitDecision(should_exit=False)

    if position.symbol != bar.symbol:
        return PositionExitDecision(should_exit=False)

    stop_hit = is_stop_loss_hit(position, bar)
    target_hit = is_take_profit_hit(position, bar)

    if not stop_hit and not target_hit:
        return PositionExitDecision(should_exit=False)

    if stop_hit and target_hit:
        prefer_stop = (
            config.intrabar_exit_policy == IntrabarExitPolicy.STOP_LOSS_FIRST
        )
    else:
        prefer_stop = stop_hit

    if prefer_stop:
        return PositionExitDecision(
            should_exit=True,
            exit_reason=PaperExitReason.STOP_LOSS,
            exit_price=position.stop_loss,
        )

    return PositionExitDecision(
        should_exit=True,
        exit_reason=PaperExitReason.TAKE_PROFIT,
        exit_price=position.take_profit,
    )


def calculate_gross_pnl(
    side: PaperSide,
    entry_price: float,
    exit_price: float,
    quantity: float,
    point_value: float = 1.0,
) -> float:
    if entry_price <= 0 or exit_price <= 0:
        raise PaperTradingError("prices must be positive.")

    if quantity <= 0:
        raise PaperTradingError("quantity must be positive.")

    if point_value <= 0:
        raise PaperTradingError("point_value must be positive.")

    direction = 1.0 if side == PaperSide.LONG else -1.0

    return (exit_price - entry_price) * quantity * point_value * direction


__all__ = [
    "AQOS_PAPER_SIMULATOR_VERSION",
    "IntrabarExitPolicy",
    "PaperExitReason",
    "PaperMarketBar",
    "PaperSimulatorConfig",
    "PositionExitDecision",
    "calculate_fill_price",
    "calculate_gross_pnl",
    "is_buy_fill",
    "is_stop_loss_hit",
    "is_take_profit_hit",
    "resolve_position_exit",
    "resolve_reference_price",
]
