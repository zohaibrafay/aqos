from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from aqos.backtesting.contracts import (
    BacktestExitReason,
    BacktestSide,
    BacktestTrade,
    backtesting_utc_now_iso,
)
from aqos.backtesting.metrics import (
    BacktestEquityCurve,
    BacktestPerformanceMetrics,
    calculate_gross_loss,
    calculate_gross_profit,
    calculate_profit_factor,
)


BACKTEST_ANALYTICS_VERSION = "1.0"


class BacktestPeriodGranularity(str, Enum):
    DAILY = "daily"
    MONTHLY = "monthly"
    YEARLY = "yearly"


@dataclass(frozen=True)
class BacktestSideBreakdown:
    side: str
    trades: int
    winning_trades: int
    losing_trades: int
    net_pnl: float
    gross_profit: float
    gross_loss: float
    win_rate: float
    average_pnl: float
    profit_factor: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "side": self.side,
            "trades": self.trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "net_pnl": self.net_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "win_rate": self.win_rate,
            "average_pnl": self.average_pnl,
            "profit_factor": self.profit_factor,
        }


@dataclass(frozen=True)
class BacktestExitReasonBreakdown:
    exit_reason: str
    trades: int
    winning_trades: int
    net_pnl: float
    share_of_trades: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "exit_reason": self.exit_reason,
            "trades": self.trades,
            "winning_trades": self.winning_trades,
            "net_pnl": self.net_pnl,
            "share_of_trades": self.share_of_trades,
        }


@dataclass(frozen=True)
class BacktestPeriodPerformance:
    period: str
    trades: int
    winning_trades: int
    losing_trades: int
    net_pnl: float
    win_rate: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "period": self.period,
            "trades": self.trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "net_pnl": self.net_pnl,
            "win_rate": self.win_rate,
        }


@dataclass(frozen=True)
class BacktestStreakStats:
    max_consecutive_wins: int
    max_consecutive_losses: int
    final_streak: int
    final_streak_kind: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "final_streak": self.final_streak,
            "final_streak_kind": self.final_streak_kind,
        }


@dataclass(frozen=True)
class BacktestDurationStats:
    measured_trades: int
    average_seconds: float | None
    median_seconds: float | None
    min_seconds: float | None
    max_seconds: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "measured_trades": self.measured_trades,
            "average_seconds": self.average_seconds,
            "median_seconds": self.median_seconds,
            "min_seconds": self.min_seconds,
            "max_seconds": self.max_seconds,
        }


@dataclass(frozen=True)
class BacktestRiskStats:
    expectancy: float
    average_win: float | None
    average_loss: float | None
    payoff_ratio: float | None
    recovery_factor: float | None
    return_to_drawdown: float | None
    equity_return_stdev: float | None
    sharpe_like_ratio: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "expectancy": self.expectancy,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "payoff_ratio": self.payoff_ratio,
            "recovery_factor": self.recovery_factor,
            "return_to_drawdown": self.return_to_drawdown,
            "equity_return_stdev": self.equity_return_stdev,
            "sharpe_like_ratio": self.sharpe_like_ratio,
        }


@dataclass(frozen=True)
class BacktestAdvancedReport:
    metrics: BacktestPerformanceMetrics
    side_breakdowns: tuple[BacktestSideBreakdown, ...]
    exit_reason_breakdowns: tuple[BacktestExitReasonBreakdown, ...]
    period_performance: tuple[BacktestPeriodPerformance, ...]
    streaks: BacktestStreakStats
    durations: BacktestDurationStats
    risk: BacktestRiskStats
    period_granularity: BacktestPeriodGranularity = (
        BacktestPeriodGranularity.MONTHLY
    )
    report_version: str = BACKTEST_ANALYTICS_VERSION
    created_at_utc: str = dataclass_field(default_factory=backtesting_utc_now_iso)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_version": self.report_version,
            "created_at_utc": self.created_at_utc,
            "period_granularity": self.period_granularity.value,
            "metrics": self.metrics.to_dict(),
            "side_breakdowns": [
                breakdown.to_dict() for breakdown in self.side_breakdowns
            ],
            "exit_reason_breakdowns": [
                breakdown.to_dict() for breakdown in self.exit_reason_breakdowns
            ],
            "period_performance": [
                period.to_dict() for period in self.period_performance
            ],
            "streaks": self.streaks.to_dict(),
            "durations": self.durations.to_dict(),
            "risk": self.risk.to_dict(),
            "metadata": self.metadata,
        }


def parse_backtest_timestamp(value: str) -> datetime | None:
    clean_value = value.strip()

    if not clean_value:
        return None

    try:
        return datetime.fromisoformat(clean_value.replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_period_key(
    timestamp: str,
    granularity: BacktestPeriodGranularity = BacktestPeriodGranularity.MONTHLY,
) -> str:
    parsed = parse_backtest_timestamp(timestamp)

    if parsed is None:
        return "unknown"

    if granularity == BacktestPeriodGranularity.DAILY:
        return parsed.strftime("%Y-%m-%d")

    if granularity == BacktestPeriodGranularity.YEARLY:
        return parsed.strftime("%Y")

    return parsed.strftime("%Y-%m")


def calculate_trade_duration_seconds(trade: BacktestTrade) -> float | None:
    entry = parse_backtest_timestamp(trade.entry_timestamp)
    exit_time = parse_backtest_timestamp(trade.exit_timestamp)

    if entry is None or exit_time is None:
        return None

    if (entry.tzinfo is None) != (exit_time.tzinfo is None):
        return None

    return (exit_time - entry).total_seconds()


def build_side_breakdown(
    side: BacktestSide,
    trades: tuple[BacktestTrade, ...],
) -> BacktestSideBreakdown:
    side_trades = tuple(trade for trade in trades if trade.side == side)
    total = len(side_trades)

    winning = sum(1 for trade in side_trades if trade.net_pnl > 0)
    losing = sum(1 for trade in side_trades if trade.net_pnl < 0)

    gross_profit = calculate_gross_profit(side_trades)
    gross_loss = calculate_gross_loss(side_trades)
    net_pnl = sum(trade.net_pnl for trade in side_trades)

    return BacktestSideBreakdown(
        side=side.value,
        trades=total,
        winning_trades=winning,
        losing_trades=losing,
        net_pnl=net_pnl,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        win_rate=winning / total if total else 0.0,
        average_pnl=net_pnl / total if total else 0.0,
        profit_factor=calculate_profit_factor(gross_profit, gross_loss),
    )


def build_side_breakdowns(
    trades: tuple[BacktestTrade, ...],
) -> tuple[BacktestSideBreakdown, ...]:
    return tuple(
        build_side_breakdown(side, trades)
        for side in (BacktestSide.LONG, BacktestSide.SHORT)
    )


def build_exit_reason_breakdowns(
    trades: tuple[BacktestTrade, ...],
) -> tuple[BacktestExitReasonBreakdown, ...]:
    total = len(trades)
    breakdowns: list[BacktestExitReasonBreakdown] = []

    for exit_reason in BacktestExitReason:
        reason_trades = tuple(
            trade for trade in trades if trade.exit_reason == exit_reason
        )

        if not reason_trades:
            continue

        breakdowns.append(
            BacktestExitReasonBreakdown(
                exit_reason=exit_reason.value,
                trades=len(reason_trades),
                winning_trades=sum(
                    1 for trade in reason_trades if trade.net_pnl > 0
                ),
                net_pnl=sum(trade.net_pnl for trade in reason_trades),
                share_of_trades=len(reason_trades) / total if total else 0.0,
            )
        )

    return tuple(breakdowns)


def build_period_performance(
    trades: tuple[BacktestTrade, ...],
    granularity: BacktestPeriodGranularity = BacktestPeriodGranularity.MONTHLY,
) -> tuple[BacktestPeriodPerformance, ...]:
    grouped: dict[str, list[BacktestTrade]] = {}

    for trade in trades:
        period = resolve_period_key(trade.exit_timestamp, granularity)
        grouped.setdefault(period, []).append(trade)

    periods: list[BacktestPeriodPerformance] = []

    for period in sorted(grouped):
        period_trades = tuple(grouped[period])
        total = len(period_trades)
        winning = sum(1 for trade in period_trades if trade.net_pnl > 0)
        losing = sum(1 for trade in period_trades if trade.net_pnl < 0)

        periods.append(
            BacktestPeriodPerformance(
                period=period,
                trades=total,
                winning_trades=winning,
                losing_trades=losing,
                net_pnl=sum(trade.net_pnl for trade in period_trades),
                win_rate=winning / total if total else 0.0,
            )
        )

    return tuple(periods)


def build_streak_stats(trades: tuple[BacktestTrade, ...]) -> BacktestStreakStats:
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for trade in trades:
        if trade.net_pnl > 0:
            current_wins += 1
            current_losses = 0
        elif trade.net_pnl < 0:
            current_losses += 1
            current_wins = 0
        else:
            current_wins = 0
            current_losses = 0

        max_wins = max(max_wins, current_wins)
        max_losses = max(max_losses, current_losses)

    if current_wins:
        final_streak, final_kind = current_wins, "win"
    elif current_losses:
        final_streak, final_kind = current_losses, "loss"
    else:
        final_streak, final_kind = 0, None

    return BacktestStreakStats(
        max_consecutive_wins=max_wins,
        max_consecutive_losses=max_losses,
        final_streak=final_streak,
        final_streak_kind=final_kind,
    )


def build_duration_stats(
    trades: tuple[BacktestTrade, ...],
) -> BacktestDurationStats:
    durations = [
        duration
        for duration in (calculate_trade_duration_seconds(trade) for trade in trades)
        if duration is not None
    ]

    if not durations:
        return BacktestDurationStats(
            measured_trades=0,
            average_seconds=None,
            median_seconds=None,
            min_seconds=None,
            max_seconds=None,
        )

    return BacktestDurationStats(
        measured_trades=len(durations),
        average_seconds=sum(durations) / len(durations),
        median_seconds=float(statistics.median(durations)),
        min_seconds=min(durations),
        max_seconds=max(durations),
    )


def calculate_equity_returns(
    equity_curve: BacktestEquityCurve | None,
) -> tuple[float, ...]:
    if equity_curve is None or len(equity_curve.points) < 2:
        return ()

    returns: list[float] = []

    for previous, current in zip(equity_curve.points, equity_curve.points[1:]):
        if previous.equity <= 0:
            continue

        returns.append((current.equity - previous.equity) / previous.equity)

    return tuple(returns)


def calculate_sharpe_like_ratio(returns: tuple[float, ...]) -> tuple[float | None, float | None]:
    """Return ``(stdev, mean / stdev)`` for the supplied period returns."""

    if len(returns) < 2:
        return None, None

    stdev = float(statistics.pstdev(returns))

    if stdev == 0:
        return stdev, None

    return stdev, float(statistics.fmean(returns)) / stdev


def build_risk_stats(
    metrics: BacktestPerformanceMetrics,
    trades: tuple[BacktestTrade, ...],
    equity_curve: BacktestEquityCurve | None = None,
) -> BacktestRiskStats:
    wins = [trade.net_pnl for trade in trades if trade.net_pnl > 0]
    losses = [trade.net_pnl for trade in trades if trade.net_pnl < 0]

    average_win = sum(wins) / len(wins) if wins else None
    average_loss = sum(losses) / len(losses) if losses else None

    payoff_ratio = (
        average_win / abs(average_loss)
        if average_win is not None and average_loss not in (None, 0)
        else None
    )

    expectancy = (
        metrics.win_rate * (average_win or 0.0)
        + metrics.loss_rate * (average_loss or 0.0)
    )

    recovery_factor = (
        metrics.net_profit / metrics.max_drawdown_amount
        if metrics.max_drawdown_amount > 0
        else None
    )

    return_to_drawdown = (
        metrics.return_fraction / metrics.max_drawdown
        if metrics.max_drawdown > 0
        else None
    )

    equity_return_stdev, sharpe_like_ratio = calculate_sharpe_like_ratio(
        calculate_equity_returns(equity_curve)
    )

    return BacktestRiskStats(
        expectancy=expectancy,
        average_win=average_win,
        average_loss=average_loss,
        payoff_ratio=payoff_ratio,
        recovery_factor=recovery_factor,
        return_to_drawdown=return_to_drawdown,
        equity_return_stdev=equity_return_stdev,
        sharpe_like_ratio=sharpe_like_ratio,
    )


def build_backtest_advanced_report(
    metrics: BacktestPerformanceMetrics,
    trades: tuple[BacktestTrade, ...],
    equity_curve: BacktestEquityCurve | None = None,
    period_granularity: BacktestPeriodGranularity = (
        BacktestPeriodGranularity.MONTHLY
    ),
    metadata: dict[str, Any] | None = None,
    created_at_utc: str | None = None,
) -> BacktestAdvancedReport:
    return BacktestAdvancedReport(
        metrics=metrics,
        side_breakdowns=build_side_breakdowns(trades),
        exit_reason_breakdowns=build_exit_reason_breakdowns(trades),
        period_performance=build_period_performance(trades, period_granularity),
        streaks=build_streak_stats(trades),
        durations=build_duration_stats(trades),
        risk=build_risk_stats(metrics, trades, equity_curve),
        period_granularity=period_granularity,
        created_at_utc=created_at_utc or backtesting_utc_now_iso(),
        metadata=metadata or {},
    )


def write_backtest_advanced_report(
    path: str | Path,
    report: BacktestAdvancedReport,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


__all__ = [
    "BACKTEST_ANALYTICS_VERSION",
    "BacktestAdvancedReport",
    "BacktestDurationStats",
    "BacktestExitReasonBreakdown",
    "BacktestPeriodGranularity",
    "BacktestPeriodPerformance",
    "BacktestRiskStats",
    "BacktestSideBreakdown",
    "BacktestStreakStats",
    "build_backtest_advanced_report",
    "build_duration_stats",
    "build_exit_reason_breakdowns",
    "build_period_performance",
    "build_risk_stats",
    "build_side_breakdown",
    "build_side_breakdowns",
    "build_streak_stats",
    "calculate_equity_returns",
    "calculate_sharpe_like_ratio",
    "calculate_trade_duration_seconds",
    "parse_backtest_timestamp",
    "resolve_period_key",
    "write_backtest_advanced_report",
]
