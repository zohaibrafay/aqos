from __future__ import annotations

from datetime import datetime
from typing import Any

from aqos.account_analytics.models import AccountAnalytics, AnalyticsScope
from aqos.account_reports.contracts import (
    AccountPerformanceReport,
    AccountReportError,
    DEFAULT_TOP_REASON_LIMIT,
    ReportType,
    RiskSummary,
)
from aqos.accounts.models import TradingAccount
from aqos.database.types import database_utc_now
from aqos.funded_rules.models import FundedAccountRules, as_fraction
from aqos.users.repositories import build_entity_id


AQOS_ACCOUNT_REPORT_BUILDER_VERSION = "1.0"


def build_risk_summary(rules: FundedAccountRules) -> RiskSummary:
    """Summarise a funded rule set as it stands right now."""

    return RiskSummary(
        rules_status=rules.status.value,
        execution_ceiling=rules.execution_ceiling().value,
        max_daily_loss_fraction=as_fraction(rules.max_daily_loss_fraction),
        max_total_drawdown_fraction=as_fraction(rules.max_total_drawdown_fraction),
        profit_target_fraction=as_fraction(rules.profit_target_fraction),
        max_risk_per_trade_fraction=as_fraction(rules.max_risk_per_trade_fraction),
        min_trading_days=rules.min_trading_days,
        is_breached=rules.is_breached,
        breach_reason=rules.breach_reason,
        breached_at_utc=(
            rules.breached_at_utc.isoformat() if rules.breached_at_utc else None
        ),
    )


def build_account_performance_report(
    analytics: AccountAnalytics,
    account: TradingAccount,
    report_type: ReportType = ReportType.ACCOUNT_SUMMARY,
    funded_rules: FundedAccountRules | None = None,
    analytics_snapshot_id: str | None = None,
    report_id: str | None = None,
    generated_at_utc: datetime | None = None,
    top_reason_limit: int = DEFAULT_TOP_REASON_LIMIT,
    metadata: dict[str, Any] | None = None,
) -> AccountPerformanceReport:
    """
    Build a report from analytics that were already calculated.

    Nothing is recalculated or filled in here: whatever the analytics say about
    trade availability is what the report says.
    """

    if analytics.scope != AnalyticsScope.ACCOUNT:
        raise AccountReportError(
            "Account performance reports need account scoped analytics."
        )

    if analytics.account_id is None:
        raise AccountReportError("Analytics are missing an account id.")

    if analytics.account_id != account.account_id:
        raise AccountReportError(
            "Analytics and account refer to different accounts: "
            f"{analytics.account_id} and {account.account_id}."
        )

    if analytics.user_id != account.user_id:
        raise AccountReportError(
            "Analytics and account refer to different users."
        )

    if funded_rules is not None and funded_rules.account_id != account.account_id:
        raise AccountReportError(
            "Funded rules belong to a different account."
        )

    return AccountPerformanceReport(
        report_id=report_id or build_entity_id("report"),
        report_type=report_type,
        user_id=analytics.user_id,
        account_id=account.account_id,
        account_type=account.account_type,
        generated_at_utc=generated_at_utc or database_utc_now(),
        period_start_utc=analytics.period_start_utc,
        period_end_utc=analytics.period_end_utc,
        analytics_snapshot_id=analytics_snapshot_id,
        signal_metrics=analytics.signal_metrics,
        reason_metrics=analytics.reason_metrics,
        trade_metrics=analytics.trade_metrics,
        risk_summary=(
            build_risk_summary(funded_rules) if funded_rules is not None else None
        ),
        top_reason_limit=top_reason_limit,
        extra_metadata=metadata or {},
    )


def available_report_types(
    analytics: AccountAnalytics,
    funded_rules: FundedAccountRules | None = None,
) -> tuple[ReportType, ...]:
    """
    Report types that can honestly be produced from what is available.

    Trade performance is excluded without a trade source, and the funded rule
    summary is excluded without a funded rule set.
    """

    types = [
        ReportType.ACCOUNT_SUMMARY,
        ReportType.SIGNAL_PERFORMANCE,
        ReportType.REJECTION_ANALYSIS,
        ReportType.MISSED_SIGNAL_ANALYSIS,
    ]

    if funded_rules is not None:
        types.append(ReportType.FUNDED_RULE_SUMMARY)

    if analytics.trade_metrics.is_available:
        types.append(ReportType.TRADE_PERFORMANCE)

    return tuple(types)


__all__ = [
    "AQOS_ACCOUNT_REPORT_BUILDER_VERSION",
    "available_report_types",
    "build_account_performance_report",
    "build_risk_summary",
]
