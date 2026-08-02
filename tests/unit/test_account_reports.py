from __future__ import annotations

import json
from datetime import datetime

import pytest

from aqos.account_analytics.metrics import (
    AccountTradeRecord,
    calculate_reason_metrics,
    calculate_signal_metrics,
    calculate_trade_metrics,
)
from aqos.account_analytics.models import AccountAnalytics, AnalyticsScope
from aqos.account_reports.artifacts import (
    CSV_SUMMARY_COLUMNS,
    compute_checksum,
    read_report_json,
    render_report_json,
    verify_report_artifact,
    write_report_json,
    write_report_summary_csv,
)
from aqos.account_reports.builder import (
    available_report_types,
    build_account_performance_report,
    build_risk_summary,
)
from aqos.account_reports.contracts import (
    AQOS_ACCOUNT_REPORTS_VERSION,
    AccountPerformanceReport,
    AccountReportError,
    ReportFormat,
    ReportType,
    rank_reason_counts,
)
from aqos.accounts.models import AccountStatus, AccountType, BrokerKind, TradingAccount
from aqos.execution_policy.modes import ExecutionMode
from aqos.funded_rules.models import FundedAccountRules, FundedRuleStatus
from aqos.signals.models import SignalStatus
from aqos.signal_reasons.models import SignalReason
from aqos.signal_reasons.taxonomy import SignalReasonCode


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_account(**overrides) -> TradingAccount:
    payload = {
        "account_id": "account_1",
        "user_id": "user_1",
        "name": "Funded 100k",
        "account_type": AccountType.FUNDED,
        "broker": BrokerKind.MT5,
        "status": AccountStatus.ACTIVE,
        "execution_mode": ExecutionMode.SIGNAL_ONLY,
        "currency": "USD",
        "initial_balance": 100_000.0,
        "current_balance": 100_000.0,
        "equity": 100_000.0,
        "leverage": 1,
    }
    payload.update(overrides)

    return TradingAccount(**payload)


def build_reason(code: SignalReasonCode, status: SignalStatus, index: int):
    return SignalReason(
        reason_id=f"reason_{index}",
        signal_id=f"signal_{index}",
        user_id="user_1",
        account_id="account_1",
        signal_status=status,
        reason_code=code,
        created_at_utc=FIXED_NOW,
    )


def build_analytics(
    trade_source: list[AccountTradeRecord] | None = None,
    **overrides,
) -> AccountAnalytics:
    reasons = [
        build_reason(SignalReasonCode.SPREAD_TOO_HIGH, SignalStatus.REJECTED, 0),
        build_reason(SignalReasonCode.SPREAD_TOO_HIGH, SignalStatus.REJECTED, 1),
        build_reason(SignalReasonCode.SYMBOL_BLOCKED, SignalStatus.REJECTED, 2),
        build_reason(SignalReasonCode.APPROVAL_TIMEOUT, SignalStatus.MISSED, 3),
    ]

    payload = {
        "scope": AnalyticsScope.ACCOUNT,
        "user_id": "user_1",
        "account_id": "account_1",
        "calculated_at_utc": FIXED_NOW,
        "signal_metrics": calculate_signal_metrics(
            {
                "generated": 2,
                "approved": 1,
                "rejected": 3,
                "missed": 1,
                "expired": 1,
                "executed": 4,
                "failed": 1,
            }
        ),
        "reason_metrics": calculate_reason_metrics(reasons),
    }

    if trade_source is not None:
        payload["trade_metrics"] = calculate_trade_metrics(
            trade_source,
            starting_balance=100_000.0,
        )

    payload.update(overrides)

    return AccountAnalytics(**payload)


def build_funded_rules(**overrides) -> FundedAccountRules:
    payload = {
        "rules_id": "rules_1",
        "account_id": "account_1",
        "status": FundedRuleStatus.ACTIVE,
        "max_daily_loss_fraction": 0.05,
        "max_total_drawdown_fraction": 0.10,
        "profit_target_fraction": 0.10,
        "max_risk_per_trade_fraction": 0.01,
        "min_trading_days": 5,
    }
    payload.update(overrides)

    return FundedAccountRules(**payload)


def build_report(**overrides) -> AccountPerformanceReport:
    analytics = overrides.pop("analytics", None) or build_analytics()

    return build_account_performance_report(
        analytics=analytics,
        account=overrides.pop("account", None) or build_account(),
        report_id=overrides.pop("report_id", "report_1"),
        generated_at_utc=overrides.pop("generated_at_utc", FIXED_NOW),
        **overrides,
    )


def test_reports_version_is_exposed() -> None:
    assert AQOS_ACCOUNT_REPORTS_VERSION == "1.0"


def test_all_required_report_types_exist() -> None:
    assert {item.value for item in ReportType} == {
        "account_summary",
        "signal_performance",
        "rejection_analysis",
        "missed_signal_analysis",
        "funded_rule_summary",
        "trade_performance",
    }


def test_rank_reason_counts_orders_by_count_then_code() -> None:
    ranked = rank_reason_counts({"b": 2, "a": 2, "c": 5}, limit=3)

    assert [entry.reason_code for entry in ranked] == ["c", "a", "b"]
    assert ranked[0].to_dict() == {"reason_code": "c", "count": 5}


def test_rank_reason_counts_respects_the_limit() -> None:
    ranked = rank_reason_counts({"a": 3, "b": 2, "c": 1}, limit=2)

    assert len(ranked) == 2

    with pytest.raises(AccountReportError, match="limit must be at least 1"):
        rank_reason_counts({"a": 1}, limit=0)


def test_report_requires_identity_fields() -> None:
    analytics = build_analytics()
    account = build_account()

    with pytest.raises(AccountReportError, match="report_id cannot be empty"):
        build_account_performance_report(
            analytics=analytics,
            account=account,
            report_id="   ",
        )


def test_report_rejects_mismatched_analytics_and_account() -> None:
    with pytest.raises(AccountReportError, match="different accounts"):
        build_account_performance_report(
            analytics=build_analytics(),
            account=build_account(account_id="account_other"),
        )


def test_report_rejects_mismatched_users() -> None:
    with pytest.raises(AccountReportError, match="different users"):
        build_account_performance_report(
            analytics=build_analytics(),
            account=build_account(user_id="user_other"),
        )


def test_report_requires_account_scoped_analytics() -> None:
    user_analytics = AccountAnalytics(
        scope=AnalyticsScope.USER,
        user_id="user_1",
        calculated_at_utc=FIXED_NOW,
    )

    with pytest.raises(AccountReportError, match="account scoped analytics"):
        build_account_performance_report(
            analytics=user_analytics,
            account=build_account(),
        )


def test_report_rejects_funded_rules_from_another_account() -> None:
    with pytest.raises(AccountReportError, match="different account"):
        build_account_performance_report(
            analytics=build_analytics(),
            account=build_account(),
            funded_rules=build_funded_rules(account_id="account_other"),
        )


def test_report_rejects_a_reversed_period() -> None:
    """The report guards its own period, independently of the analytics guard."""

    with pytest.raises(AccountReportError, match="cannot be before"):
        AccountPerformanceReport(
            report_id="report_1",
            report_type=ReportType.ACCOUNT_SUMMARY,
            user_id="user_1",
            account_id="account_1",
            account_type=AccountType.FUNDED,
            generated_at_utc=FIXED_NOW,
            period_start_utc=datetime(2026, 2, 1),
            period_end_utc=datetime(2026, 1, 1),
        )


def test_report_defaults_to_unavailable_trade_metrics() -> None:
    report = build_report()

    assert report.trade_metrics_available is False
    assert report.trade_metrics.total_trades is None
    assert report.trade_metrics.net_pnl is None


def test_trade_performance_report_needs_trade_metrics() -> None:
    """The rule this sprint turns on: no trade source, no trade report."""

    with pytest.raises(AccountReportError, match="cannot be produced without"):
        build_report(report_type=ReportType.TRADE_PERFORMANCE)


def test_trade_performance_report_is_allowed_with_a_trade_source() -> None:
    report = build_report(
        analytics=build_analytics(
            trade_source=[
                AccountTradeRecord(
                    trade_id="t1",
                    net_pnl=500.0,
                    closed_at_utc=datetime(2026, 1, 2),
                ),
                AccountTradeRecord(
                    trade_id="t2",
                    net_pnl=-200.0,
                    closed_at_utc=datetime(2026, 1, 3),
                ),
            ]
        ),
        report_type=ReportType.TRADE_PERFORMANCE,
    )

    assert report.trade_metrics_available is True
    assert report.trade_metrics.total_trades == 2
    assert report.trade_metrics.net_pnl == pytest.approx(300.0)


def test_funded_rule_summary_needs_funded_rules() -> None:
    with pytest.raises(AccountReportError, match="requires a funded rule set"):
        build_report(report_type=ReportType.FUNDED_RULE_SUMMARY)


def test_funded_rule_summary_report() -> None:
    report = build_report(
        report_type=ReportType.FUNDED_RULE_SUMMARY,
        funded_rules=build_funded_rules(),
    )

    assert report.risk_summary is not None
    assert report.risk_summary.rules_status == "active"
    assert report.risk_summary.execution_ceiling == "signal_only"
    assert report.risk_summary.is_breached is False


def test_risk_summary_reports_a_breach() -> None:
    summary = build_risk_summary(
        build_funded_rules(
            status=FundedRuleStatus.BREACHED,
            breached_at_utc=FIXED_NOW,
            breach_reason="Maximum daily loss exceeded.",
        )
    )

    assert summary.is_breached is True
    assert summary.execution_ceiling == "disabled"
    assert summary.breach_reason == "Maximum daily loss exceeded."
    assert summary.to_dict()["breached_at_utc"] == "2026-01-01T00:00:00"


def test_available_report_types_without_trades_or_funded_rules() -> None:
    types = available_report_types(build_analytics())

    assert ReportType.TRADE_PERFORMANCE not in types
    assert ReportType.FUNDED_RULE_SUMMARY not in types
    assert ReportType.ACCOUNT_SUMMARY in types
    assert ReportType.REJECTION_ANALYSIS in types


def test_available_report_types_with_trades_and_funded_rules() -> None:
    types = available_report_types(
        build_analytics(
            trade_source=[
                AccountTradeRecord(
                    trade_id="t1",
                    net_pnl=10.0,
                    closed_at_utc=FIXED_NOW,
                )
            ]
        ),
        funded_rules=build_funded_rules(),
    )

    assert ReportType.TRADE_PERFORMANCE in types
    assert ReportType.FUNDED_RULE_SUMMARY in types


def test_signal_section_carries_every_required_metric() -> None:
    section = build_report().signal_section()

    for key in (
        "signals_received",
        "signals_approved",
        "signals_rejected",
        "signals_missed",
        "signals_expired",
        "signals_executed",
        "signals_failed",
        "execution_rate",
        "rejection_rate",
        "missed_rate",
    ):
        assert key in section

    assert section["signals_received"] == 13
    assert section["signals_executed"] == 4
    assert section["execution_rate"] == pytest.approx(4 / 13)


def test_reason_section_carries_every_required_breakdown() -> None:
    section = build_report().reason_section()

    assert section["rejected_by_reason_code"] == {
        "spread_too_high": 2,
        "symbol_blocked": 1,
    }
    assert section["missed_by_reason_code"] == {"approval_timeout": 1}
    assert section["by_category"] == {
        "account_rule": 1,
        "market_condition": 2,
        "user_action": 1,
    }
    assert section["by_severity"] == {"blocking": 1, "warning": 3}
    assert section["top_rejection_reasons"][0] == {
        "reason_code": "spread_too_high",
        "count": 2,
    }
    assert section["top_missed_reasons"][0]["reason_code"] == "approval_timeout"


def test_top_reason_limit_is_configurable() -> None:
    report = build_report(top_reason_limit=1)

    assert len(report.top_rejection_reasons) == 1


def test_report_dict_structure() -> None:
    payload = build_report().to_dict()

    for key in (
        "report_version",
        "report_id",
        "report_type",
        "user_id",
        "account_id",
        "account_type",
        "generated_at_utc",
        "period_start_utc",
        "period_end_utc",
        "analytics_snapshot_id",
        "trade_metrics_available",
        "signal_metrics",
        "reason_metrics",
        "trade_metrics",
        "risk_summary",
        "metadata",
    ):
        assert key in payload

    assert payload["report_type"] == "account_summary"
    assert payload["account_type"] == "funded"
    assert payload["trade_metrics_available"] is False
    assert payload["trade_metrics"]["net_pnl"] is None
    assert payload["risk_summary"] is None


def test_report_json_is_deterministic() -> None:
    report = build_report()

    first = render_report_json(report)
    second = render_report_json(report)

    assert first == second
    assert compute_checksum(first) == compute_checksum(second)
    assert json.loads(first)["report_id"] == "report_1"


def test_write_and_read_json_artifact(tmp_path) -> None:
    report = build_report()

    artifact = write_report_json(tmp_path / "nested" / "report.json", report)

    assert artifact.path.exists()
    assert artifact.artifact_format == ReportFormat.JSON
    assert len(artifact.checksum) == 64
    assert artifact.size_bytes > 0
    assert verify_report_artifact(artifact) is True

    payload = read_report_json(artifact.path)

    assert payload["report_id"] == "report_1"
    assert payload["trade_metrics_available"] is False


def test_verify_artifact_detects_tampering(tmp_path) -> None:
    artifact = write_report_json(tmp_path / "report.json", build_report())

    artifact.path.write_text("{}", encoding="utf-8")

    assert verify_report_artifact(artifact) is False


def test_verify_artifact_detects_a_missing_file(tmp_path) -> None:
    artifact = write_report_json(tmp_path / "report.json", build_report())

    artifact.path.unlink()

    assert verify_report_artifact(artifact) is False


def test_read_json_artifact_rejects_a_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        read_report_json(tmp_path / "missing.json")


def test_csv_summary_leaves_unknown_values_empty(tmp_path) -> None:
    """The CSV must carry the same unknown-versus-zero distinction as the JSON."""

    artifact = write_report_summary_csv(
        tmp_path / "summary.csv",
        [build_report()],
    )

    lines = artifact.path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    values = dict(zip(header, lines[1].split(",")))

    assert header == list(CSV_SUMMARY_COLUMNS)
    assert values["trade_metrics_available"] == "false"
    assert values["total_trades"] == ""
    assert values["win_rate"] == ""
    assert values["net_pnl"] == ""
    assert values["signals_received"] == "13"


def test_csv_summary_writes_trade_values_when_available(tmp_path) -> None:
    report = build_report(
        analytics=build_analytics(
            trade_source=[
                AccountTradeRecord(
                    trade_id="t1",
                    net_pnl=250.0,
                    closed_at_utc=FIXED_NOW,
                )
            ]
        ),
    )

    artifact = write_report_summary_csv(tmp_path / "summary.csv", [report])

    lines = artifact.path.read_text(encoding="utf-8").splitlines()
    values = dict(zip(lines[0].split(","), lines[1].split(",")))

    assert values["trade_metrics_available"] == "true"
    assert values["total_trades"] == "1"
    assert values["net_pnl"] == "250.0"


def test_csv_summary_covers_several_reports(tmp_path) -> None:
    reports = [
        build_report(report_id="report_1"),
        build_report(
            report_id="report_2",
            report_type=ReportType.REJECTION_ANALYSIS,
        ),
    ]

    artifact = write_report_summary_csv(tmp_path / "summary.csv", reports)
    lines = artifact.path.read_text(encoding="utf-8").splitlines()

    assert len(lines) == 3
    assert verify_report_artifact(artifact) is True


def test_csv_summary_requires_at_least_one_report(tmp_path) -> None:
    with pytest.raises(AccountReportError, match="At least one report"):
        write_report_summary_csv(tmp_path / "summary.csv", [])


def test_summary_row_keeps_unknown_trade_values_as_none() -> None:
    row = build_report().summary_row()

    assert row["trade_metrics_available"] is False
    assert row["total_trades"] is None
    assert row["win_rate"] is None
    assert row["net_pnl"] is None


@pytest.mark.parametrize(
    "account_type",
    [AccountType.FUNDED, AccountType.LIVE, AccountType.DEMO, AccountType.PAPER],
)
def test_reports_work_for_every_account_type(account_type: AccountType) -> None:
    report = build_report(account=build_account(account_type=account_type))

    assert report.account_type == account_type
    assert report.to_dict()["account_type"] == account_type.value
