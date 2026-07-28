from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestExecutionConfig,
    BacktestExitReason,
    BacktestOrder,
    BacktestOrderStatus,
    BacktestOrderType,
    BacktestPosition,
    BacktestSide,
    BacktestSignal,
    BacktestSignalAction,
    BacktestTrade,
    build_backtest_trade,
)


BACKTEST_SIMULATOR_VERSION = "1.0"


class BacktestIntrabarExitPolicy(str, Enum):
    STOP_LOSS_FIRST = "stop_loss_first"
    TAKE_PROFIT_FIRST = "take_profit_first"


@dataclass(frozen=True)
class BacktestPositionExitDecision:
    should_exit: bool
    position_id: str
    timestamp: str
    exit_price: float | None = None
    exit_reason: BacktestExitReason | None = None
    stop_loss_hit: bool = False
    take_profit_hit: bool = False

    def __post_init__(self) -> None:
        if not self.position_id.strip():
            raise ValueError("position_id cannot be empty.")

        if not self.timestamp.strip():
            raise ValueError("timestamp cannot be empty.")

        if self.should_exit:
            if self.exit_price is None:
                raise ValueError("exit_price is required when should_exit is True.")

            if self.exit_reason is None:
                raise ValueError("exit_reason is required when should_exit is True.")

        if self.exit_price is not None and self.exit_price <= 0:
            raise ValueError("exit_price must be positive.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "should_exit": self.should_exit,
            "position_id": self.position_id,
            "timestamp": self.timestamp,
            "exit_price": self.exit_price,
            "exit_reason": (
                self.exit_reason.value if self.exit_reason is not None else None
            ),
            "stop_loss_hit": self.stop_loss_hit,
            "take_profit_hit": self.take_profit_hit,
        }


@dataclass(frozen=True)
class BacktestSimulationState:
    balance: float
    open_positions: tuple[BacktestPosition, ...] = ()
    orders: tuple[BacktestOrder, ...] = ()
    trades: tuple[BacktestTrade, ...] = ()
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.balance < 0:
            raise ValueError("balance cannot be negative.")

    @property
    def open_position_count(self) -> int:
        return len(self.open_positions)

    @property
    def total_net_pnl(self) -> float:
        return sum(trade.net_pnl for trade in self.trades)

    def to_dict(self) -> dict[str, Any]:
        return {
            "balance": self.balance,
            "open_position_count": self.open_position_count,
            "open_positions": [
                position.to_dict() for position in self.open_positions
            ],
            "orders": [order.to_dict() for order in self.orders],
            "trades": [trade.to_dict() for trade in self.trades],
            "total_net_pnl": self.total_net_pnl,
            "metadata": self.metadata or {},
        }


def build_initial_backtest_state(
    execution_config: BacktestExecutionConfig,
) -> BacktestSimulationState:
    return BacktestSimulationState(balance=execution_config.initial_balance)


def build_backtest_order_id(
    timestamp: str,
    symbol: str,
    order_index: int,
) -> str:
    clean_timestamp = (
        timestamp.replace("-", "")
        .replace(":", "")
        .replace("T", "_")
        .replace(" ", "_")
    )
    clean_symbol = symbol.replace("/", "").replace("-", "").replace(" ", "_").lower()

    return f"order_{clean_symbol}_{clean_timestamp}_{order_index:06d}"


def build_backtest_position_id(order_id: str) -> str:
    if not order_id.strip():
        raise ValueError("order_id cannot be empty.")

    return f"position_{order_id}"


def calculate_market_execution_price(
    side: BacktestSide,
    base_price: float,
    execution_config: BacktestExecutionConfig,
    *,
    is_entry: bool,
) -> float:
    if base_price <= 0:
        raise ValueError("base_price must be positive.")

    half_spread = execution_config.spread_points / 2.0
    adverse_cost = half_spread + execution_config.slippage_points

    if is_entry:
        if side == BacktestSide.LONG:
            price = base_price + adverse_cost
        else:
            price = base_price - adverse_cost
    else:
        if side == BacktestSide.LONG:
            price = base_price - adverse_cost
        else:
            price = base_price + adverse_cost

    if price <= 0:
        raise ValueError("Calculated execution price must be positive.")

    return price


def resolve_bar_execution_price(
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
) -> float:
    if execution_config.execution_timing.value == "current_close":
        return bar.close

    return bar.open


def calculate_backtest_position_quantity(
    balance: float,
    entry_price: float,
    signal: BacktestSignal,
    execution_config: BacktestExecutionConfig,
) -> float:
    if balance <= 0:
        raise ValueError("balance must be positive.")

    if entry_price <= 0:
        raise ValueError("entry_price must be positive.")

    if execution_config.fixed_quantity is not None:
        return execution_config.fixed_quantity

    risk_amount = balance * execution_config.risk_fraction

    if signal.stop_loss is not None:
        stop_distance = abs(entry_price - signal.stop_loss)

        if stop_distance <= 0:
            raise ValueError("stop_loss distance must be greater than 0.")

        return risk_amount / (stop_distance * execution_config.point_value)

    return risk_amount / (entry_price * execution_config.point_value)


def can_open_backtest_position(
    state: BacktestSimulationState,
    execution_config: BacktestExecutionConfig,
) -> bool:
    return state.open_position_count < execution_config.max_open_positions


def is_position_stop_loss_hit(
    position: BacktestPosition,
    bar: BacktestBar,
) -> bool:
    if position.stop_loss is None:
        return False

    if position.side == BacktestSide.LONG:
        return bar.low <= position.stop_loss

    return bar.high >= position.stop_loss


def is_position_take_profit_hit(
    position: BacktestPosition,
    bar: BacktestBar,
) -> bool:
    if position.take_profit is None:
        return False

    if position.side == BacktestSide.LONG:
        return bar.high >= position.take_profit

    return bar.low <= position.take_profit


def resolve_position_exit_decision(
    position: BacktestPosition,
    bar: BacktestBar,
    intrabar_exit_policy: BacktestIntrabarExitPolicy = (
        BacktestIntrabarExitPolicy.STOP_LOSS_FIRST
    ),
) -> BacktestPositionExitDecision:
    stop_loss_hit = is_position_stop_loss_hit(position, bar)
    take_profit_hit = is_position_take_profit_hit(position, bar)

    if not stop_loss_hit and not take_profit_hit:
        return BacktestPositionExitDecision(
            should_exit=False,
            position_id=position.position_id,
            timestamp=bar.timestamp,
            stop_loss_hit=False,
            take_profit_hit=False,
        )

    if stop_loss_hit and take_profit_hit:
        if intrabar_exit_policy == BacktestIntrabarExitPolicy.TAKE_PROFIT_FIRST:
            return BacktestPositionExitDecision(
                should_exit=True,
                position_id=position.position_id,
                timestamp=bar.timestamp,
                exit_price=position.take_profit,
                exit_reason=BacktestExitReason.TAKE_PROFIT,
                stop_loss_hit=True,
                take_profit_hit=True,
            )

        return BacktestPositionExitDecision(
            should_exit=True,
            position_id=position.position_id,
            timestamp=bar.timestamp,
            exit_price=position.stop_loss,
            exit_reason=BacktestExitReason.STOP_LOSS,
            stop_loss_hit=True,
            take_profit_hit=True,
        )

    if stop_loss_hit:
        return BacktestPositionExitDecision(
            should_exit=True,
            position_id=position.position_id,
            timestamp=bar.timestamp,
            exit_price=position.stop_loss,
            exit_reason=BacktestExitReason.STOP_LOSS,
            stop_loss_hit=True,
            take_profit_hit=False,
        )

    return BacktestPositionExitDecision(
        should_exit=True,
        position_id=position.position_id,
        timestamp=bar.timestamp,
        exit_price=position.take_profit,
        exit_reason=BacktestExitReason.TAKE_PROFIT,
        stop_loss_hit=False,
        take_profit_hit=True,
    )


def build_rejected_backtest_order(
    signal: BacktestSignal,
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
    order_index: int,
    reason: str,
) -> BacktestOrder:
    side = signal.side or BacktestSide.LONG
    requested_price = resolve_bar_execution_price(bar, execution_config)

    return BacktestOrder(
        order_id=build_backtest_order_id(signal.timestamp, signal.symbol, order_index),
        timestamp=signal.timestamp,
        symbol=signal.symbol,
        side=side,
        order_type=BacktestOrderType.MARKET,
        requested_price=requested_price,
        quantity=1.0,
        status=BacktestOrderStatus.REJECTED,
        filled_price=None,
        reason=reason,
    )


def fill_market_order_from_signal(
    signal: BacktestSignal,
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
    balance: float,
    order_index: int,
) -> BacktestOrder:
    side = signal.side

    if side is None:
        return build_rejected_backtest_order(
            signal=signal,
            bar=bar,
            execution_config=execution_config,
            order_index=order_index,
            reason="Signal action is not an entry action.",
        )

    if side == BacktestSide.SHORT and not execution_config.allow_short:
        return build_rejected_backtest_order(
            signal=signal,
            bar=bar,
            execution_config=execution_config,
            order_index=order_index,
            reason="Short entries are disabled.",
        )

    requested_price = resolve_bar_execution_price(bar, execution_config)
    filled_price = calculate_market_execution_price(
        side=side,
        base_price=requested_price,
        execution_config=execution_config,
        is_entry=True,
    )
    quantity = calculate_backtest_position_quantity(
        balance=balance,
        entry_price=filled_price,
        signal=signal,
        execution_config=execution_config,
    )

    return BacktestOrder(
        order_id=build_backtest_order_id(signal.timestamp, signal.symbol, order_index),
        timestamp=signal.timestamp,
        symbol=signal.symbol,
        side=side,
        order_type=BacktestOrderType.MARKET,
        requested_price=requested_price,
        quantity=quantity,
        status=BacktestOrderStatus.FILLED,
        filled_price=filled_price,
        reason=None,
    )


def open_position_from_filled_order(
    order: BacktestOrder,
    signal: BacktestSignal,
) -> BacktestPosition:
    if order.status != BacktestOrderStatus.FILLED:
        raise ValueError("Only filled orders can open positions.")

    if order.filled_price is None:
        raise ValueError("Filled order must have filled_price.")

    return BacktestPosition(
        position_id=build_backtest_position_id(order.order_id),
        symbol=order.symbol,
        side=order.side,
        entry_timestamp=order.timestamp,
        entry_price=order.filled_price,
        quantity=order.quantity,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
    )


def close_position_at_price(
    position: BacktestPosition,
    exit_timestamp: str,
    requested_exit_price: float,
    execution_config: BacktestExecutionConfig,
    exit_reason: BacktestExitReason,
) -> BacktestTrade:
    exit_price = calculate_market_execution_price(
        side=position.side,
        base_price=requested_exit_price,
        execution_config=execution_config,
        is_entry=False,
    )

    return build_backtest_trade(
        position=position,
        exit_timestamp=exit_timestamp,
        exit_price=exit_price,
        exit_reason=exit_reason,
        commission_per_trade=execution_config.commission_per_trade,
        point_value=execution_config.point_value,
    )


def close_position_at_market(
    position: BacktestPosition,
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
    exit_reason: BacktestExitReason,
) -> BacktestTrade:
    requested_exit_price = resolve_bar_execution_price(bar, execution_config)

    return close_position_at_price(
        position=position,
        exit_timestamp=bar.timestamp,
        requested_exit_price=requested_exit_price,
        execution_config=execution_config,
        exit_reason=exit_reason,
    )


def close_backtest_position_at_price(
    state: BacktestSimulationState,
    position: BacktestPosition,
    exit_timestamp: str,
    requested_exit_price: float,
    execution_config: BacktestExecutionConfig,
    exit_reason: BacktestExitReason,
) -> BacktestSimulationState:
    trade = close_position_at_price(
        position=position,
        exit_timestamp=exit_timestamp,
        requested_exit_price=requested_exit_price,
        execution_config=execution_config,
        exit_reason=exit_reason,
    )

    remaining_positions = tuple(
        open_position
        for open_position in state.open_positions
        if open_position.position_id != position.position_id
    )

    return BacktestSimulationState(
        balance=state.balance + trade.net_pnl,
        open_positions=remaining_positions,
        orders=state.orders,
        trades=state.trades + (trade,),
        metadata=state.metadata,
    )


def close_backtest_position(
    state: BacktestSimulationState,
    position: BacktestPosition,
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
    exit_reason: BacktestExitReason,
) -> BacktestSimulationState:
    requested_exit_price = resolve_bar_execution_price(bar, execution_config)

    return close_backtest_position_at_price(
        state=state,
        position=position,
        exit_timestamp=bar.timestamp,
        requested_exit_price=requested_exit_price,
        execution_config=execution_config,
        exit_reason=exit_reason,
    )


def apply_position_lifecycle_on_bar(
    state: BacktestSimulationState,
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
    intrabar_exit_policy: BacktestIntrabarExitPolicy = (
        BacktestIntrabarExitPolicy.STOP_LOSS_FIRST
    ),
) -> BacktestSimulationState:
    next_state = state

    for position in state.open_positions:
        decision = resolve_position_exit_decision(
            position=position,
            bar=bar,
            intrabar_exit_policy=intrabar_exit_policy,
        )

        if not decision.should_exit:
            continue

        if decision.exit_price is None or decision.exit_reason is None:
            raise ValueError("Exit decision is missing exit price or reason.")

        next_state = close_backtest_position_at_price(
            state=next_state,
            position=position,
            exit_timestamp=bar.timestamp,
            requested_exit_price=decision.exit_price,
            execution_config=execution_config,
            exit_reason=decision.exit_reason,
        )

    return next_state


def close_all_backtest_positions(
    state: BacktestSimulationState,
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
    exit_reason: BacktestExitReason,
    symbol: str | None = None,
) -> BacktestSimulationState:
    next_state = state

    for position in state.open_positions:
        if symbol is not None and position.symbol != symbol:
            continue

        next_state = close_backtest_position(
            state=next_state,
            position=position,
            bar=bar,
            execution_config=execution_config,
            exit_reason=exit_reason,
        )

    return next_state


def apply_backtest_signal(
    state: BacktestSimulationState,
    signal: BacktestSignal,
    bar: BacktestBar,
    execution_config: BacktestExecutionConfig,
    order_index: int,
) -> BacktestSimulationState:
    if signal.action == BacktestSignalAction.HOLD:
        return state

    if signal.action == BacktestSignalAction.EXIT:
        return close_all_backtest_positions(
            state=state,
            bar=bar,
            execution_config=execution_config,
            exit_reason=BacktestExitReason.SIGNAL_EXIT,
            symbol=signal.symbol,
        )

    if not can_open_backtest_position(state, execution_config):
        rejected_order = build_rejected_backtest_order(
            signal=signal,
            bar=bar,
            execution_config=execution_config,
            order_index=order_index,
            reason="Maximum open positions reached.",
        )

        return BacktestSimulationState(
            balance=state.balance,
            open_positions=state.open_positions,
            orders=state.orders + (rejected_order,),
            trades=state.trades,
            metadata=state.metadata,
        )

    order = fill_market_order_from_signal(
        signal=signal,
        bar=bar,
        execution_config=execution_config,
        balance=state.balance,
        order_index=order_index,
    )

    if order.status != BacktestOrderStatus.FILLED:
        return BacktestSimulationState(
            balance=state.balance,
            open_positions=state.open_positions,
            orders=state.orders + (order,),
            trades=state.trades,
            metadata=state.metadata,
        )

    position = open_position_from_filled_order(order, signal)

    return BacktestSimulationState(
        balance=state.balance,
        open_positions=state.open_positions + (position,),
        orders=state.orders + (order,),
        trades=state.trades,
        metadata=state.metadata,
    )


__all__ = [
    "BACKTEST_SIMULATOR_VERSION",
    "BacktestIntrabarExitPolicy",
    "BacktestPositionExitDecision",
    "BacktestSimulationState",
    "apply_backtest_signal",
    "apply_position_lifecycle_on_bar",
    "build_backtest_order_id",
    "build_backtest_position_id",
    "build_initial_backtest_state",
    "build_rejected_backtest_order",
    "calculate_backtest_position_quantity",
    "calculate_market_execution_price",
    "can_open_backtest_position",
    "close_all_backtest_positions",
    "close_backtest_position",
    "close_backtest_position_at_price",
    "close_position_at_market",
    "close_position_at_price",
    "fill_market_order_from_signal",
    "is_position_stop_loss_hit",
    "is_position_take_profit_hit",
    "open_position_from_filled_order",
    "resolve_bar_execution_price",
    "resolve_position_exit_decision",
]