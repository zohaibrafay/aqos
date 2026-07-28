from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any

from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestEquityPoint,
    BacktestPosition,
    BacktestSide,
    BacktestTrade,
    calculate_drawdown,
    calculate_trade_gross_pnl,
)
from aqos.backtesting.simulator import BacktestSimulationState


BACKTEST_METRICS_VERSION = "1.0"


@dataclass(frozen=True)
class BacktestPerformanceMetrics:
    initial_balance: float
    final_balance: float
    net_profit: float
    return_fraction: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate: float
    loss_rate: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    average_trade_pnl: float
    best_trade_pnl: float | None
    worst_trade_pnl: float | None
    total_fees: float
    max_drawdown: float
    max_drawdown_amount: float
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive.")

        if self.final_balance < 0:
            raise ValueError("final_balance cannot be negative.")

        if self.total_trades < 0:
            raise ValueError("total_trades cannot be negative.")

        if self.winning_trades < 0:
            raise ValueError("winning_trades cannot be negative.")

        if self.losing_trades < 0:
            raise ValueError("losing_trades cannot be negative.")

        if self.breakeven_trades < 0:
            raise ValueError("breakeven_trades cannot be negative.")

        if not 0.0 <= self.win_rate <= 1.0:
            raise ValueError("win_rate must be between 0 and 1.")

        if not 0.0 <= self.loss_rate <= 1.0:
            raise ValueError("loss_rate must be between 0 and 1.")

        if self.gross_loss > 0:
            raise ValueError("gross_loss must be zero or negative.")

        if self.total_fees < 0:
            raise ValueError("total_fees cannot be negative.")

        if self.max_drawdown < 0:
            raise ValueError("max_drawdown cannot be negative.")

        if self.max_drawdown_amount < 0:
            raise ValueError("max_drawdown_amount cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "net_profit": self.net_profit,
            "return_fraction": self.return_fraction,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "win_rate": self.win_rate,
            "loss_rate": self.loss_rate,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "profit_factor": self.profit_factor,
            "average_trade_pnl": self.average_trade_pnl,
            "best_trade_pnl": self.best_trade_pnl,
            "worst_trade_pnl": self.worst_trade_pnl,
            "total_fees": self.total_fees,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_amount": self.max_drawdown_amount,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestEquityCurve:
    points: tuple[BacktestEquityPoint, ...]
    initial_balance: float
    final_balance: float
    max_drawdown: float
    max_drawdown_amount: float

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive.")

        if self.final_balance < 0:
            raise ValueError("final_balance cannot be negative.")

        if self.max_drawdown < 0:
            raise ValueError("max_drawdown cannot be negative.")

        if self.max_drawdown_amount < 0:
            raise ValueError("max_drawdown_amount cannot be negative.")

    @property
    def rows(self) -> int:
        return len(self.points)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [point.to_dict() for point in self.points],
            "rows": self.rows,
            "initial_balance": self.initial_balance,
            "final_balance": self.final_balance,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_amount": self.max_drawdown_amount,
        }


def calculate_position_unrealized_pnl(
    position: BacktestPosition,
    current_price: float,
    point_value: float = 1.0,
) -> float:
    return calculate_trade_gross_pnl(
        side=position.side,
        entry_price=position.entry_price,
        exit_price=current_price,
        quantity=position.quantity,
        point_value=point_value,
    )


def calculate_open_positions_unrealized_pnl(
    positions: tuple[BacktestPosition, ...],
    bar: BacktestBar,
    point_value: float = 1.0,
) -> float:
    return sum(
        calculate_position_unrealized_pnl(
            position=position,
            current_price=bar.close,
            point_value=point_value,
        )
        for position in positions
    )


def calculate_equity(
    balance: float,
    open_pnl: float = 0.0,
) -> float:
    if balance < 0:
        raise ValueError("balance cannot be negative.")

    return balance + open_pnl


def build_backtest_equity_point(
    timestamp: str,
    balance: float,
    open_pnl: float,
    peak_equity: float,
) -> BacktestEquityPoint:
    equity = calculate_equity(balance, open_pnl)

    return BacktestEquityPoint(
        timestamp=timestamp,
        balance=balance,
        equity=equity,
        open_pnl=open_pnl,
        drawdown=calculate_drawdown(equity=equity, peak_equity=peak_equity),
    )


def build_backtest_equity_point_from_state(
    state: BacktestSimulationState,
    bar: BacktestBar,
    peak_equity: float,
    point_value: float = 1.0,
) -> BacktestEquityPoint:
    open_pnl = calculate_open_positions_unrealized_pnl(
        positions=state.open_positions,
        bar=bar,
        point_value=point_value,
    )

    return build_backtest_equity_point(
        timestamp=bar.timestamp,
        balance=state.balance,
        open_pnl=open_pnl,
        peak_equity=peak_equity,
    )


def build_backtest_equity_curve(
    points: tuple[BacktestEquityPoint, ...],
    initial_balance: float,
) -> BacktestEquityCurve:
    if initial_balance <= 0:
        raise ValueError("initial_balance must be positive.")

    if not points:
        initial_point = BacktestEquityPoint(
            timestamp="start",
            balance=initial_balance,
            equity=initial_balance,
            open_pnl=0.0,
            drawdown=0.0,
        )
        points = (initial_point,)

    peak_equity = initial_balance
    max_drawdown = 0.0
    max_drawdown_amount = 0.0

    for point in points:
        peak_equity = max(peak_equity, point.equity)
        drawdown_amount = peak_equity - point.equity
        max_drawdown_amount = max(max_drawdown_amount, drawdown_amount)
        max_drawdown = max(max_drawdown, point.drawdown)

    return BacktestEquityCurve(
        points=points,
        initial_balance=initial_balance,
        final_balance=points[-1].balance,
        max_drawdown=max_drawdown,
        max_drawdown_amount=max_drawdown_amount,
    )


def calculate_gross_profit(trades: tuple[BacktestTrade, ...]) -> float:
    return sum(trade.net_pnl for trade in trades if trade.net_pnl > 0)


def calculate_gross_loss(trades: tuple[BacktestTrade, ...]) -> float:
    return sum(trade.net_pnl for trade in trades if trade.net_pnl < 0)


def calculate_profit_factor(
    gross_profit: float,
    gross_loss: float,
) -> float | None:
    if gross_profit < 0:
        raise ValueError("gross_profit cannot be negative.")

    if gross_loss > 0:
        raise ValueError("gross_loss must be zero or negative.")

    if gross_loss == 0:
        return None if gross_profit == 0 else float("inf")

    return gross_profit / abs(gross_loss)


def calculate_backtest_performance_metrics(
    initial_balance: float,
    final_balance: float,
    trades: tuple[BacktestTrade, ...],
    equity_curve: BacktestEquityCurve | None = None,
    metadata: dict[str, Any] | None = None,
) -> BacktestPerformanceMetrics:
    if initial_balance <= 0:
        raise ValueError("initial_balance must be positive.")

    if final_balance < 0:
        raise ValueError("final_balance cannot be negative.")

    total_trades = len(trades)
    winning_trades = sum(1 for trade in trades if trade.net_pnl > 0)
    losing_trades = sum(1 for trade in trades if trade.net_pnl < 0)
    breakeven_trades = total_trades - winning_trades - losing_trades

    gross_profit = calculate_gross_profit(trades)
    gross_loss = calculate_gross_loss(trades)
    profit_factor = calculate_profit_factor(gross_profit, gross_loss)

    net_profit = final_balance - initial_balance
    total_fees = sum(trade.fees for trade in trades)

    trade_pnls = tuple(trade.net_pnl for trade in trades)

    return BacktestPerformanceMetrics(
        initial_balance=initial_balance,
        final_balance=final_balance,
        net_profit=net_profit,
        return_fraction=net_profit / initial_balance,
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        breakeven_trades=breakeven_trades,
        win_rate=winning_trades / total_trades if total_trades else 0.0,
        loss_rate=losing_trades / total_trades if total_trades else 0.0,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        profit_factor=profit_factor,
        average_trade_pnl=sum(trade_pnls) / total_trades if total_trades else 0.0,
        best_trade_pnl=max(trade_pnls) if trade_pnls else None,
        worst_trade_pnl=min(trade_pnls) if trade_pnls else None,
        total_fees=total_fees,
        max_drawdown=equity_curve.max_drawdown if equity_curve is not None else 0.0,
        max_drawdown_amount=(
            equity_curve.max_drawdown_amount if equity_curve is not None else 0.0
        ),
        metadata=metadata or {},
    )


__all__ = [
    "BACKTEST_METRICS_VERSION",
    "BacktestEquityCurve",
    "BacktestPerformanceMetrics",
    "build_backtest_equity_curve",
    "build_backtest_equity_point",
    "build_backtest_equity_point_from_state",
    "calculate_backtest_performance_metrics",
    "calculate_equity",
    "calculate_gross_loss",
    "calculate_gross_profit",
    "calculate_open_positions_unrealized_pnl",
    "calculate_position_unrealized_pnl",
    "calculate_profit_factor",
]