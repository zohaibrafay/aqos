from __future__ import annotations

import math
from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from aqos.signals.models import SignalStatus
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonSeverity,
    severity_rank,
)


AQOS_ACCOUNT_ANALYTICS_METRICS_VERSION = "1.0"


class ProfitFactorState(str, Enum):
    """
    Why a profit factor reads the way it does.

    A numeric column cannot hold infinity, so the state carries what the number
    alone would lose. ``infinite_no_losses`` is a real result — the account won
    and never lost — which is not the same as having nothing to divide.
    """

    UNAVAILABLE = "unavailable"
    FINITE = "finite"
    INFINITE_NO_LOSSES = "infinite_no_losses"


def resolve_profit_factor_state(
    profit_factor: float | None,
) -> ProfitFactorState:
    if profit_factor is None:
        return ProfitFactorState.UNAVAILABLE

    if math.isinf(profit_factor):
        return ProfitFactorState.INFINITE_NO_LOSSES

    return ProfitFactorState.FINITE


def finite_profit_factor(profit_factor: float | None) -> float | None:
    """The value a numeric column may store; infinity becomes NULL."""

    if profit_factor is None or math.isinf(profit_factor):
        return None

    return profit_factor


class TradeMetricsAvailability(str, Enum):
    """
    Why trade metrics are or are not present.

    AQOS never reports a zero where it means "unknown": an account with no trade
    source looks different from an account that traded and broke even.
    """

    AVAILABLE = "available"
    NO_TRADE_SOURCE = "no_trade_source"


@dataclass(frozen=True)
class AccountTradeRecord:
    """
    One closed trade, as account analytics needs it.

    This is the contract a trade source must satisfy. Paper trading fills it
    from Sprint 048 onwards; live execution later. Nothing in this sprint
    produces these records, so nothing fabricates them either.
    """

    trade_id: str
    net_pnl: float
    closed_at_utc: datetime
    opened_at_utc: datetime | None = None
    symbol: str | None = None
    risk_amount: float | None = None
    reward_amount: float | None = None
    balance_after: float | None = None

    def __post_init__(self) -> None:
        if not self.trade_id.strip():
            raise ValueError("trade_id cannot be empty.")

        if self.risk_amount is not None and self.risk_amount < 0:
            raise ValueError("risk_amount cannot be negative.")

        if self.balance_after is not None and self.balance_after < 0:
            raise ValueError("balance_after cannot be negative.")

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0

    @property
    def is_loss(self) -> bool:
        return self.net_pnl < 0

    @property
    def reward_to_risk(self) -> float | None:
        if self.risk_amount is None or self.reward_amount is None:
            return None

        if self.risk_amount <= 0:
            return None

        return self.reward_amount / self.risk_amount


@dataclass(frozen=True)
class TradeMetrics:
    """
    Trading performance for one account over a period.

    Every ratio is ``None`` rather than ``0`` when it cannot be computed, so a
    missing measurement can never be mistaken for a measured zero.
    """

    availability: TradeMetricsAvailability = (
        TradeMetricsAvailability.NO_TRADE_SOURCE
    )
    unavailable_reason: str | None = None
    total_trades: int | None = None
    winning_trades: int | None = None
    losing_trades: int | None = None
    breakeven_trades: int | None = None
    win_rate: float | None = None
    gross_profit: float | None = None
    gross_loss: float | None = None
    net_pnl: float | None = None
    profit_factor: float | None = None
    average_win: float | None = None
    average_loss: float | None = None
    largest_win: float | None = None
    largest_loss: float | None = None
    average_reward_to_risk: float | None = None
    max_drawdown: float | None = None
    max_drawdown_amount: float | None = None
    current_drawdown: float | None = None
    starting_balance: float | None = None
    ending_balance: float | None = None

    @property
    def is_available(self) -> bool:
        return self.availability == TradeMetricsAvailability.AVAILABLE

    @property
    def profit_factor_state(self) -> ProfitFactorState:
        return resolve_profit_factor_state(self.profit_factor)

    @property
    def has_infinite_profit_factor(self) -> bool:
        return self.profit_factor_state == ProfitFactorState.INFINITE_NO_LOSSES

    @classmethod
    def unavailable(
        cls,
        reason: str = "No trade source is connected yet.",
    ) -> "TradeMetrics":
        return cls(
            availability=TradeMetricsAvailability.NO_TRADE_SOURCE,
            unavailable_reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "availability": self.availability.value,
            "is_available": self.is_available,
            "unavailable_reason": self.unavailable_reason,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": self.breakeven_trades,
            "win_rate": self.win_rate,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "net_pnl": self.net_pnl,
            # ``json.dumps`` renders infinity as the bare token ``Infinity``,
            # which is not valid JSON and which MySQL refuses outright. The
            # number is dropped and the state carries the meaning instead.
            "profit_factor": finite_profit_factor(self.profit_factor),
            "profit_factor_state": self.profit_factor_state.value,
            "has_infinite_profit_factor": self.has_infinite_profit_factor,
            "average_win": self.average_win,
            "average_loss": self.average_loss,
            "largest_win": self.largest_win,
            "largest_loss": self.largest_loss,
            "average_reward_to_risk": self.average_reward_to_risk,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_amount": self.max_drawdown_amount,
            "current_drawdown": self.current_drawdown,
            "starting_balance": self.starting_balance,
            "ending_balance": self.ending_balance,
        }


@dataclass(frozen=True)
class SignalMetrics:
    """Signal lifecycle counts and rates for one account or user."""

    signals_received: int = 0
    signals_approved: int = 0
    signals_rejected: int = 0
    signals_missed: int = 0
    signals_expired: int = 0
    signals_executed: int = 0
    signals_failed: int = 0
    signals_cancelled: int = 0
    signals_pending: int = 0
    status_counts: dict[str, int] = dataclass_field(default_factory=dict)

    @property
    def execution_rate(self) -> float | None:
        return self._rate(self.signals_executed)

    @property
    def rejection_rate(self) -> float | None:
        return self._rate(self.signals_rejected)

    @property
    def missed_rate(self) -> float | None:
        return self._rate(self.signals_missed)

    @property
    def failure_rate(self) -> float | None:
        return self._rate(self.signals_failed)

    @property
    def unfilled_signals(self) -> int:
        return (
            self.signals_rejected
            + self.signals_missed
            + self.signals_expired
            + self.signals_failed
            + self.signals_cancelled
        )

    def _rate(self, count: int) -> float | None:
        """No signals means no rate, not a rate of zero."""

        if self.signals_received <= 0:
            return None

        return count / self.signals_received

    def to_dict(self) -> dict[str, Any]:
        return {
            "signals_received": self.signals_received,
            "signals_approved": self.signals_approved,
            "signals_rejected": self.signals_rejected,
            "signals_missed": self.signals_missed,
            "signals_expired": self.signals_expired,
            "signals_executed": self.signals_executed,
            "signals_failed": self.signals_failed,
            "signals_cancelled": self.signals_cancelled,
            "signals_pending": self.signals_pending,
            "unfilled_signals": self.unfilled_signals,
            "execution_rate": self.execution_rate,
            "rejection_rate": self.rejection_rate,
            "missed_rate": self.missed_rate,
            "failure_rate": self.failure_rate,
            "status_counts": self.status_counts,
        }


@dataclass(frozen=True)
class ReasonCodeCount:
    reason_code: SignalReasonCode
    reason_category: SignalReasonCategory
    severity: SignalReasonSeverity
    signal_status: SignalStatus
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code.value,
            "reason_category": self.reason_category.value,
            "severity": self.severity.value,
            "signal_status": self.signal_status.value,
            "count": self.count,
        }


@dataclass(frozen=True)
class ReasonMetrics:
    """Why signals did not reach the market, aggregated for one account."""

    total: int = 0
    entries: tuple[ReasonCodeCount, ...] = ()

    def counts_for_status(self, status: SignalStatus) -> dict[str, int]:
        totals: dict[str, int] = {}

        for entry in self.entries:
            if entry.signal_status != status:
                continue

            key = entry.reason_code.value
            totals[key] = totals.get(key, 0) + entry.count

        return dict(sorted(totals.items(), key=lambda item: (-item[1], item[0])))

    @property
    def rejection_counts(self) -> dict[str, int]:
        return self.counts_for_status(SignalStatus.REJECTED)

    @property
    def missed_counts(self) -> dict[str, int]:
        return self.counts_for_status(SignalStatus.MISSED)

    @property
    def by_category(self) -> dict[str, int]:
        totals: dict[str, int] = {}

        for entry in self.entries:
            key = entry.reason_category.value
            totals[key] = totals.get(key, 0) + entry.count

        return dict(sorted(totals.items()))

    @property
    def by_severity(self) -> dict[str, int]:
        totals: dict[str, int] = {}

        for entry in self.entries:
            key = entry.severity.value
            totals[key] = totals.get(key, 0) + entry.count

        return dict(sorted(totals.items()))

    @property
    def blocking_total(self) -> int:
        return sum(
            entry.count
            for entry in self.entries
            if severity_rank(entry.severity)
            >= severity_rank(SignalReasonSeverity.BLOCKING)
        )

    @property
    def critical_total(self) -> int:
        return sum(
            entry.count
            for entry in self.entries
            if entry.severity == SignalReasonSeverity.CRITICAL
        )

    @property
    def top_reason(self) -> ReasonCodeCount | None:
        return self.entries[0] if self.entries else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "rejection_counts": self.rejection_counts,
            "missed_counts": self.missed_counts,
            "by_category": self.by_category,
            "by_severity": self.by_severity,
            "blocking_total": self.blocking_total,
            "critical_total": self.critical_total,
            "top_reason": (
                self.top_reason.to_dict() if self.top_reason is not None else None
            ),
            "entries": [entry.to_dict() for entry in self.entries],
        }


def calculate_profit_factor(
    gross_profit: float,
    gross_loss: float,
) -> float | None:
    """
    Gross profit divided by gross loss.

    Returns ``None`` when nothing was traded and ``inf`` when there were wins
    and no losses, so "undefined" and "unbounded" stay distinguishable.
    """

    if gross_loss == 0:
        return None if gross_profit == 0 else float("inf")

    return gross_profit / abs(gross_loss)


def build_equity_curve(
    trades: Sequence[AccountTradeRecord],
    starting_balance: float | None = None,
) -> tuple[float, ...]:
    """
    Running balance after each trade.

    ``balance_after`` is used when the trade source provides it; otherwise the
    curve is accumulated from ``starting_balance``.
    """

    if not trades:
        return ()

    if all(trade.balance_after is not None for trade in trades):
        return tuple(float(trade.balance_after) for trade in trades)

    if starting_balance is None:
        return ()

    balance = float(starting_balance)
    curve: list[float] = []

    for trade in trades:
        balance += trade.net_pnl
        curve.append(balance)

    return tuple(curve)


def calculate_drawdowns(
    equity_curve: Sequence[float],
    starting_balance: float | None = None,
) -> tuple[float | None, float | None, float | None]:
    """Return ``(max_drawdown, max_drawdown_amount, current_drawdown)``."""

    if not equity_curve:
        return None, None, None

    peak = float(starting_balance) if starting_balance is not None else equity_curve[0]
    peak = max(peak, equity_curve[0])

    max_drawdown = 0.0
    max_drawdown_amount = 0.0

    for value in equity_curve:
        peak = max(peak, value)
        amount = peak - value

        if amount > max_drawdown_amount:
            max_drawdown_amount = amount

        if peak > 0:
            max_drawdown = max(max_drawdown, amount / peak)

    final = equity_curve[-1]
    current = (peak - final) / peak if peak > 0 else 0.0

    return max_drawdown, max_drawdown_amount, max(0.0, current)


def calculate_trade_metrics(
    trades: Sequence[AccountTradeRecord],
    starting_balance: float | None = None,
) -> TradeMetrics:
    """
    Trading metrics from real closed trades.

    An empty sequence still returns available metrics with zero counts: that
    means "the source is connected and there were no trades", which is not the
    same as having no source at all.
    """

    ordered = tuple(sorted(trades, key=lambda trade: trade.closed_at_utc))

    winning = [trade for trade in ordered if trade.is_win]
    losing = [trade for trade in ordered if trade.is_loss]
    breakeven = [
        trade for trade in ordered if not trade.is_win and not trade.is_loss
    ]

    gross_profit = sum(trade.net_pnl for trade in winning)
    gross_loss = sum(trade.net_pnl for trade in losing)
    net_pnl = sum(trade.net_pnl for trade in ordered)

    reward_ratios = [
        trade.reward_to_risk
        for trade in ordered
        if trade.reward_to_risk is not None
    ]

    equity_curve = build_equity_curve(ordered, starting_balance)
    max_drawdown, max_drawdown_amount, current_drawdown = calculate_drawdowns(
        equity_curve,
        starting_balance,
    )

    return TradeMetrics(
        availability=TradeMetricsAvailability.AVAILABLE,
        total_trades=len(ordered),
        winning_trades=len(winning),
        losing_trades=len(losing),
        breakeven_trades=len(breakeven),
        win_rate=len(winning) / len(ordered) if ordered else None,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_pnl=net_pnl,
        profit_factor=(
            calculate_profit_factor(gross_profit, gross_loss) if ordered else None
        ),
        average_win=(
            sum(trade.net_pnl for trade in winning) / len(winning)
            if winning
            else None
        ),
        average_loss=(
            sum(trade.net_pnl for trade in losing) / len(losing) if losing else None
        ),
        largest_win=max((trade.net_pnl for trade in winning), default=None),
        largest_loss=min((trade.net_pnl for trade in losing), default=None),
        average_reward_to_risk=(
            sum(reward_ratios) / len(reward_ratios) if reward_ratios else None
        ),
        max_drawdown=max_drawdown,
        max_drawdown_amount=max_drawdown_amount,
        current_drawdown=current_drawdown,
        starting_balance=starting_balance,
        ending_balance=equity_curve[-1] if equity_curve else starting_balance,
    )


def calculate_signal_metrics(
    status_counts: dict[str, int] | dict[SignalStatus, int],
) -> SignalMetrics:
    """Signal metrics from lifecycle status counts."""

    normalized: dict[str, int] = {}

    for status, count in status_counts.items():
        key = status.value if isinstance(status, SignalStatus) else str(status)

        if count < 0:
            raise ValueError(f"Signal status count cannot be negative: {key}")

        normalized[key] = normalized.get(key, 0) + int(count)

    unknown = set(normalized) - {status.value for status in SignalStatus}

    if unknown:
        raise ValueError(
            "Unknown signal statuses in counts: " + ", ".join(sorted(unknown))
        )

    return SignalMetrics(
        signals_received=sum(normalized.values()),
        signals_approved=normalized.get(SignalStatus.APPROVED.value, 0),
        signals_rejected=normalized.get(SignalStatus.REJECTED.value, 0),
        signals_missed=normalized.get(SignalStatus.MISSED.value, 0),
        signals_expired=normalized.get(SignalStatus.EXPIRED.value, 0),
        signals_executed=normalized.get(SignalStatus.EXECUTED.value, 0),
        signals_failed=normalized.get(SignalStatus.FAILED.value, 0),
        signals_cancelled=normalized.get(SignalStatus.CANCELLED.value, 0),
        signals_pending=normalized.get(SignalStatus.PENDING_APPROVAL.value, 0),
        status_counts=dict(sorted(normalized.items())),
    )


def calculate_reason_metrics(
    reasons: Sequence[Any],
) -> ReasonMetrics:
    """
    Reason metrics from persisted ``SignalReason`` rows.

    Only the taxonomy fields are read, so any object carrying them works.
    """

    totals: dict[
        tuple[SignalReasonCode, SignalReasonCategory, SignalReasonSeverity, SignalStatus],
        int,
    ] = {}

    for reason in reasons:
        key = (
            reason.reason_code,
            reason.reason_category,
            reason.severity,
            reason.signal_status,
        )
        totals[key] = totals.get(key, 0) + 1

    ordered = sorted(
        totals.items(),
        key=lambda item: (-item[1], item[0][0].value, item[0][3].value),
    )

    return ReasonMetrics(
        total=sum(totals.values()),
        entries=tuple(
            ReasonCodeCount(
                reason_code=code,
                reason_category=category,
                severity=severity,
                signal_status=status,
                count=count,
            )
            for (code, category, severity, status), count in ordered
        ),
    )


__all__ = [
    "AQOS_ACCOUNT_ANALYTICS_METRICS_VERSION",
    "AccountTradeRecord",
    "ReasonCodeCount",
    "ReasonMetrics",
    "SignalMetrics",
    "TradeMetrics",
    "ProfitFactorState",
    "TradeMetricsAvailability",
    "build_equity_curve",
    "calculate_drawdowns",
    "calculate_profit_factor",
    "finite_profit_factor",
    "calculate_reason_metrics",
    "resolve_profit_factor_state",
    "calculate_signal_metrics",
    "calculate_trade_metrics",
]
