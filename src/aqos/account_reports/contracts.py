from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any

from aqos.account_analytics.metrics import (
    ReasonMetrics,
    SignalMetrics,
    TradeMetrics,
    finite_profit_factor,
)
from aqos.accounts.models import AccountType


AQOS_ACCOUNT_REPORTS_VERSION = "1.0"

DEFAULT_TOP_REASON_LIMIT = 5


class ReportType(str, Enum):
    ACCOUNT_SUMMARY = "account_summary"
    SIGNAL_PERFORMANCE = "signal_performance"
    REJECTION_ANALYSIS = "rejection_analysis"
    MISSED_SIGNAL_ANALYSIS = "missed_signal_analysis"
    FUNDED_RULE_SUMMARY = "funded_rule_summary"
    TRADE_PERFORMANCE = "trade_performance"


class ReportFormat(str, Enum):
    JSON = "json"
    CSV = "csv"


#: Report types that cannot be produced without real trade data.
TRADE_DEPENDENT_REPORT_TYPES = (ReportType.TRADE_PERFORMANCE,)

#: Report types that need a funded rule set to say anything.
FUNDED_DEPENDENT_REPORT_TYPES = (ReportType.FUNDED_RULE_SUMMARY,)


class AccountReportError(ValueError):
    """Raised when a report cannot be produced honestly."""


@dataclass(frozen=True)
class ReasonRank:
    """One entry in a ranked list of reasons."""

    reason_code: str
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {"reason_code": self.reason_code, "count": self.count}


def rank_reason_counts(
    counts: dict[str, int],
    limit: int = DEFAULT_TOP_REASON_LIMIT,
) -> tuple[ReasonRank, ...]:
    """Rank reason counts, highest first, breaking ties by code for stability."""

    if limit < 1:
        raise AccountReportError("limit must be at least 1.")

    ordered = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    return tuple(
        ReasonRank(reason_code=code, count=count) for code, count in ordered[:limit]
    )


@dataclass(frozen=True)
class RiskSummary:
    """
    Funded rule state at the moment the report was generated.

    Only present when the account actually has a funded rule set.
    """

    rules_status: str
    execution_ceiling: str
    max_daily_loss_fraction: float
    max_total_drawdown_fraction: float
    profit_target_fraction: float
    max_risk_per_trade_fraction: float
    min_trading_days: int
    is_breached: bool
    breach_reason: str | None = None
    breached_at_utc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_status": self.rules_status,
            "execution_ceiling": self.execution_ceiling,
            "max_daily_loss_fraction": self.max_daily_loss_fraction,
            "max_total_drawdown_fraction": self.max_total_drawdown_fraction,
            "profit_target_fraction": self.profit_target_fraction,
            "max_risk_per_trade_fraction": self.max_risk_per_trade_fraction,
            "min_trading_days": self.min_trading_days,
            "is_breached": self.is_breached,
            "breach_reason": self.breach_reason,
            "breached_at_utc": self.breached_at_utc,
        }


@dataclass(frozen=True)
class AccountPerformanceReport:
    """
    A machine readable account performance report.

    Trade metrics keep their availability flag all the way through, so a
    consumer can always tell an absent measurement from a measured zero.
    """

    report_id: str
    report_type: ReportType
    user_id: str
    account_id: str
    account_type: AccountType
    generated_at_utc: datetime
    period_start_utc: datetime | None = None
    period_end_utc: datetime | None = None
    analytics_snapshot_id: str | None = None
    signal_metrics: SignalMetrics = dataclass_field(default_factory=SignalMetrics)
    reason_metrics: ReasonMetrics = dataclass_field(default_factory=ReasonMetrics)
    trade_metrics: TradeMetrics = dataclass_field(
        default_factory=TradeMetrics.unavailable
    )
    risk_summary: RiskSummary | None = None
    top_reason_limit: int = DEFAULT_TOP_REASON_LIMIT
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)
    report_version: str = AQOS_ACCOUNT_REPORTS_VERSION

    def __post_init__(self) -> None:
        if not self.report_id.strip():
            raise AccountReportError("report_id cannot be empty.")

        if not self.user_id.strip():
            raise AccountReportError("user_id cannot be empty.")

        if not self.account_id.strip():
            raise AccountReportError("account_id cannot be empty.")

        if (
            self.period_start_utc is not None
            and self.period_end_utc is not None
            and self.period_end_utc < self.period_start_utc
        ):
            raise AccountReportError(
                "period_end_utc cannot be before period_start_utc."
            )

        if (
            self.report_type in TRADE_DEPENDENT_REPORT_TYPES
            and not self.trade_metrics.is_available
        ):
            raise AccountReportError(
                f"A {self.report_type.value} report cannot be produced without "
                "trade metrics. Connect a trade source first."
            )

        if (
            self.report_type in FUNDED_DEPENDENT_REPORT_TYPES
            and self.risk_summary is None
        ):
            raise AccountReportError(
                f"A {self.report_type.value} report requires a funded rule set."
            )

    @property
    def trade_metrics_available(self) -> bool:
        return self.trade_metrics.is_available

    @property
    def top_rejection_reasons(self) -> tuple[ReasonRank, ...]:
        return rank_reason_counts(
            self.reason_metrics.rejection_counts,
            self.top_reason_limit,
        )

    @property
    def top_missed_reasons(self) -> tuple[ReasonRank, ...]:
        return rank_reason_counts(
            self.reason_metrics.missed_counts,
            self.top_reason_limit,
        )

    def signal_section(self) -> dict[str, Any]:
        return self.signal_metrics.to_dict()

    def reason_section(self) -> dict[str, Any]:
        return {
            "total": self.reason_metrics.total,
            "rejected_by_reason_code": self.reason_metrics.rejection_counts,
            "missed_by_reason_code": self.reason_metrics.missed_counts,
            "by_category": self.reason_metrics.by_category,
            "by_severity": self.reason_metrics.by_severity,
            "blocking_total": self.reason_metrics.blocking_total,
            "critical_total": self.reason_metrics.critical_total,
            "top_rejection_reasons": [
                entry.to_dict() for entry in self.top_rejection_reasons
            ],
            "top_missed_reasons": [
                entry.to_dict() for entry in self.top_missed_reasons
            ],
        }

    def trade_section(self) -> dict[str, Any]:
        return self.trade_metrics.to_dict()

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_version": self.report_version,
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "account_type": self.account_type.value,
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "period_start_utc": (
                self.period_start_utc.isoformat() if self.period_start_utc else None
            ),
            "period_end_utc": (
                self.period_end_utc.isoformat() if self.period_end_utc else None
            ),
            "analytics_snapshot_id": self.analytics_snapshot_id,
            "trade_metrics_available": self.trade_metrics_available,
            "signal_metrics": self.signal_section(),
            "reason_metrics": self.reason_section(),
            "trade_metrics": self.trade_section(),
            "risk_summary": (
                self.risk_summary.to_dict() if self.risk_summary is not None else None
            ),
            "metadata": self.extra_metadata,
        }

    def summary_row(self) -> dict[str, Any]:
        """A single flat row, suitable for a CSV summary."""

        return {
            "report_id": self.report_id,
            "report_type": self.report_type.value,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "account_type": self.account_type.value,
            "generated_at_utc": self.generated_at_utc.isoformat(),
            "period_start_utc": (
                self.period_start_utc.isoformat() if self.period_start_utc else None
            ),
            "period_end_utc": (
                self.period_end_utc.isoformat() if self.period_end_utc else None
            ),
            "signals_received": self.signal_metrics.signals_received,
            "signals_executed": self.signal_metrics.signals_executed,
            "signals_rejected": self.signal_metrics.signals_rejected,
            "signals_missed": self.signal_metrics.signals_missed,
            "execution_rate": self.signal_metrics.execution_rate,
            "rejection_rate": self.signal_metrics.rejection_rate,
            "missed_rate": self.signal_metrics.missed_rate,
            "reason_total": self.reason_metrics.total,
            "reason_blocking_total": self.reason_metrics.blocking_total,
            "trade_metrics_available": self.trade_metrics_available,
            "total_trades": self.trade_metrics.total_trades,
            "win_rate": self.trade_metrics.win_rate,
            "net_pnl": self.trade_metrics.net_pnl,
            # Infinity is not valid JSON, so the state carries it here too.
            "profit_factor": finite_profit_factor(
                self.trade_metrics.profit_factor
            ),
            "profit_factor_state": self.trade_metrics.profit_factor_state.value,
            "has_infinite_profit_factor": (
                self.trade_metrics.has_infinite_profit_factor
            ),
            "max_drawdown": self.trade_metrics.max_drawdown,
        }


__all__ = [
    "AQOS_ACCOUNT_REPORTS_VERSION",
    "AccountPerformanceReport",
    "AccountReportError",
    "DEFAULT_TOP_REASON_LIMIT",
    "FUNDED_DEPENDENT_REPORT_TYPES",
    "ReasonRank",
    "ReportFormat",
    "ReportType",
    "RiskSummary",
    "TRADE_DEPENDENT_REPORT_TYPES",
    "rank_reason_counts",
]
