from __future__ import annotations

from datetime import datetime

import pytest

from aqos.account_analytics.metrics import (
    AQOS_ACCOUNT_ANALYTICS_METRICS_VERSION,
    AccountTradeRecord,
    ReasonMetrics,
    SignalMetrics,
    TradeMetrics,
    TradeMetricsAvailability,
    build_equity_curve,
    calculate_drawdowns,
    calculate_profit_factor,
    calculate_reason_metrics,
    calculate_signal_metrics,
    calculate_trade_metrics,
)
from aqos.account_analytics.models import (
    AccountAnalytics,
    AccountAnalyticsError,
    AccountAnalyticsSnapshot,
    AnalyticsScope,
)
from aqos.signals.models import SignalStatus
from aqos.signal_reasons.models import SignalReason
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonSeverity,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_trade(
    trade_id: str,
    net_pnl: float,
    day: int = 1,
    **overrides,
) -> AccountTradeRecord:
    payload = {
        "trade_id": trade_id,
        "net_pnl": net_pnl,
        "closed_at_utc": datetime(2026, 1, day),
    }
    payload.update(overrides)

    return AccountTradeRecord(**payload)


def build_reason(
    code: SignalReasonCode,
    status: SignalStatus = SignalStatus.REJECTED,
    index: int = 0,
) -> SignalReason:
    return SignalReason(
        reason_id=f"reason_{index}",
        signal_id=f"signal_{index}",
        user_id="user_1",
        signal_status=status,
        reason_code=code,
        created_at_utc=FIXED_NOW,
    )


def test_metrics_version_is_exposed() -> None:
    assert AQOS_ACCOUNT_ANALYTICS_METRICS_VERSION == "1.0"


def test_trade_record_validation() -> None:
    with pytest.raises(ValueError, match="trade_id cannot be empty"):
        build_trade("  ", 10.0)

    with pytest.raises(ValueError, match="risk_amount cannot be negative"):
        build_trade("t1", 10.0, risk_amount=-1.0)

    with pytest.raises(ValueError, match="balance_after cannot be negative"):
        build_trade("t1", 10.0, balance_after=-1.0)


def test_trade_record_helpers() -> None:
    win = build_trade("t1", 10.0, risk_amount=100.0, reward_amount=250.0)

    assert win.is_win is True
    assert win.is_loss is False
    assert win.reward_to_risk == pytest.approx(2.5)

    assert build_trade("t2", -5.0).is_loss is True
    assert build_trade("t3", 0.0).is_win is False
    assert build_trade("t4", 1.0).reward_to_risk is None
    assert build_trade(
        "t5",
        1.0,
        risk_amount=0.0,
        reward_amount=5.0,
    ).reward_to_risk is None


def test_unavailable_trade_metrics_report_nothing_measured() -> None:
    """The distinction this sprint depends on: unknown is not zero."""

    metrics = TradeMetrics.unavailable("No trade source yet.")

    assert metrics.is_available is False
    assert metrics.availability == TradeMetricsAvailability.NO_TRADE_SOURCE
    assert metrics.total_trades is None
    assert metrics.net_pnl is None
    assert metrics.win_rate is None
    assert metrics.profit_factor is None
    assert metrics.max_drawdown is None

    payload = metrics.to_dict()

    assert payload["is_available"] is False
    assert payload["unavailable_reason"] == "No trade source yet."


def test_empty_trade_list_is_available_with_zero_counts() -> None:
    """A connected source with no trades differs from having no source."""

    metrics = calculate_trade_metrics([])

    assert metrics.is_available is True
    assert metrics.total_trades == 0
    assert metrics.winning_trades == 0
    assert metrics.net_pnl == 0
    assert metrics.win_rate is None
    assert metrics.profit_factor is None


def test_calculate_profit_factor() -> None:
    assert calculate_profit_factor(300.0, -100.0) == pytest.approx(3.0)
    assert calculate_profit_factor(0.0, 0.0) is None
    assert calculate_profit_factor(100.0, 0.0) == float("inf")


def test_trade_metrics_from_real_trades() -> None:
    trades = [
        build_trade("t1", 100.0, day=1),
        build_trade("t2", -40.0, day=2),
        build_trade("t3", 60.0, day=3),
        build_trade("t4", -20.0, day=4),
        build_trade("t5", 0.0, day=5),
    ]

    metrics = calculate_trade_metrics(trades, starting_balance=1_000.0)

    assert metrics.is_available is True
    assert metrics.total_trades == 5
    assert metrics.winning_trades == 2
    assert metrics.losing_trades == 2
    assert metrics.breakeven_trades == 1
    assert metrics.win_rate == pytest.approx(0.4)
    assert metrics.gross_profit == pytest.approx(160.0)
    assert metrics.gross_loss == pytest.approx(-60.0)
    assert metrics.net_pnl == pytest.approx(100.0)
    assert metrics.profit_factor == pytest.approx(160.0 / 60.0)
    assert metrics.average_win == pytest.approx(80.0)
    assert metrics.average_loss == pytest.approx(-30.0)
    assert metrics.largest_win == pytest.approx(100.0)
    assert metrics.largest_loss == pytest.approx(-40.0)
    assert metrics.starting_balance == pytest.approx(1_000.0)
    assert metrics.ending_balance == pytest.approx(1_100.0)


def test_average_reward_to_risk_uses_only_complete_records() -> None:
    trades = [
        build_trade("t1", 100.0, risk_amount=100.0, reward_amount=200.0),
        build_trade("t2", 50.0, risk_amount=100.0, reward_amount=400.0),
        build_trade("t3", 10.0),
    ]

    metrics = calculate_trade_metrics(trades)

    assert metrics.average_reward_to_risk == pytest.approx(3.0)


def test_average_reward_to_risk_is_none_without_data() -> None:
    metrics = calculate_trade_metrics([build_trade("t1", 10.0)])

    assert metrics.average_reward_to_risk is None


def test_build_equity_curve_prefers_reported_balances() -> None:
    trades = [
        build_trade("t1", 100.0, day=1, balance_after=1_100.0),
        build_trade("t2", -50.0, day=2, balance_after=1_050.0),
    ]

    assert build_equity_curve(trades) == (1_100.0, 1_050.0)


def test_build_equity_curve_accumulates_when_balances_are_missing() -> None:
    trades = [build_trade("t1", 100.0, day=1), build_trade("t2", -50.0, day=2)]

    assert build_equity_curve(trades, starting_balance=1_000.0) == (
        1_100.0,
        1_050.0,
    )
    assert build_equity_curve(trades) == ()
    assert build_equity_curve([]) == ()


def test_calculate_drawdowns() -> None:
    max_drawdown, amount, current = calculate_drawdowns(
        (1_100.0, 1_050.0, 1_200.0, 1_020.0),
        starting_balance=1_000.0,
    )

    assert amount == pytest.approx(180.0)
    assert max_drawdown == pytest.approx(180.0 / 1_200.0)
    assert current == pytest.approx(180.0 / 1_200.0)


def test_calculate_drawdowns_for_an_empty_curve() -> None:
    assert calculate_drawdowns(()) == (None, None, None)


def test_drawdown_is_zero_when_equity_only_rises() -> None:
    max_drawdown, amount, current = calculate_drawdowns(
        (1_100.0, 1_200.0),
        starting_balance=1_000.0,
    )

    assert max_drawdown == pytest.approx(0.0)
    assert amount == pytest.approx(0.0)
    assert current == pytest.approx(0.0)


def test_trades_are_ordered_by_close_time() -> None:
    trades = [
        build_trade("t2", -100.0, day=2),
        build_trade("t1", 200.0, day=1),
    ]

    metrics = calculate_trade_metrics(trades, starting_balance=1_000.0)

    assert metrics.ending_balance == pytest.approx(1_100.0)
    assert metrics.max_drawdown_amount == pytest.approx(100.0)


def test_signal_metrics_from_status_counts() -> None:
    metrics = calculate_signal_metrics(
        {
            "generated": 2,
            "approved": 1,
            "rejected": 3,
            "missed": 2,
            "expired": 1,
            "executed": 4,
            "failed": 1,
            "cancelled": 1,
            "pending_approval": 1,
        }
    )

    assert metrics.signals_received == 16
    assert metrics.signals_executed == 4
    assert metrics.signals_rejected == 3
    assert metrics.signals_missed == 2
    assert metrics.signals_pending == 1
    assert metrics.execution_rate == pytest.approx(4 / 16)
    assert metrics.rejection_rate == pytest.approx(3 / 16)
    assert metrics.missed_rate == pytest.approx(2 / 16)
    assert metrics.failure_rate == pytest.approx(1 / 16)
    assert metrics.unfilled_signals == 8


def test_signal_metrics_accept_enum_keys() -> None:
    metrics = calculate_signal_metrics(
        {SignalStatus.EXECUTED: 2, SignalStatus.REJECTED: 2}
    )

    assert metrics.signals_received == 4
    assert metrics.execution_rate == pytest.approx(0.5)


def test_signal_rates_are_none_without_signals() -> None:
    """No signals means no rate, not a rate of zero."""

    metrics = calculate_signal_metrics({})

    assert metrics.signals_received == 0
    assert metrics.execution_rate is None
    assert metrics.rejection_rate is None
    assert metrics.missed_rate is None
    assert metrics.to_dict()["execution_rate"] is None


def test_signal_metrics_reject_bad_input() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        calculate_signal_metrics({"executed": -1})

    with pytest.raises(ValueError, match="Unknown signal statuses"):
        calculate_signal_metrics({"teleported": 1})


def test_reason_metrics_aggregate_by_code_category_and_severity() -> None:
    reasons = [
        build_reason(SignalReasonCode.SPREAD_TOO_HIGH, index=0),
        build_reason(SignalReasonCode.SPREAD_TOO_HIGH, index=1),
        build_reason(SignalReasonCode.FUNDED_RULE_BREACHED, index=2),
        build_reason(
            SignalReasonCode.APPROVAL_TIMEOUT,
            status=SignalStatus.MISSED,
            index=3,
        ),
    ]

    metrics = calculate_reason_metrics(reasons)

    assert metrics.total == 4
    assert metrics.top_reason is not None
    assert metrics.top_reason.reason_code == SignalReasonCode.SPREAD_TOO_HIGH
    assert metrics.top_reason.count == 2
    assert metrics.rejection_counts == {
        "spread_too_high": 2,
        "funded_rule_breached": 1,
    }
    assert metrics.missed_counts == {"approval_timeout": 1}
    assert metrics.by_category == {
        "funded_rule": 1,
        "market_condition": 2,
        "user_action": 1,
    }
    assert metrics.by_severity == {"critical": 1, "warning": 3}
    assert metrics.blocking_total == 1
    assert metrics.critical_total == 1


def test_reason_metrics_for_no_reasons() -> None:
    metrics = calculate_reason_metrics([])

    assert metrics.total == 0
    assert metrics.top_reason is None
    assert metrics.rejection_counts == {}
    assert metrics.by_category == {}
    assert metrics.to_dict()["blocking_total"] == 0


def test_analytics_requires_an_account_for_account_scope() -> None:
    with pytest.raises(AccountAnalyticsError, match="account_id is required"):
        AccountAnalytics(
            scope=AnalyticsScope.ACCOUNT,
            user_id="user_1",
            calculated_at_utc=FIXED_NOW,
        )


def test_analytics_requires_a_user() -> None:
    with pytest.raises(AccountAnalyticsError, match="user_id cannot be empty"):
        AccountAnalytics(
            scope=AnalyticsScope.USER,
            user_id="   ",
            calculated_at_utc=FIXED_NOW,
        )


def test_analytics_rejects_a_reversed_period() -> None:
    with pytest.raises(AccountAnalyticsError, match="cannot be before"):
        AccountAnalytics(
            scope=AnalyticsScope.USER,
            user_id="user_1",
            calculated_at_utc=FIXED_NOW,
            period_start_utc=datetime(2026, 2, 1),
            period_end_utc=datetime(2026, 1, 1),
        )


def test_analytics_defaults_to_unavailable_trade_metrics() -> None:
    analytics = AccountAnalytics(
        scope=AnalyticsScope.USER,
        user_id="user_1",
        calculated_at_utc=FIXED_NOW,
    )

    assert analytics.has_trade_metrics is False

    payload = analytics.to_dict()

    assert payload["has_trade_metrics"] is False
    assert payload["trade_metrics"]["net_pnl"] is None
    assert payload["signal_metrics"]["signals_received"] == 0


def test_snapshot_refuses_trade_metrics_without_a_source() -> None:
    """A zero here would be indistinguishable from a measured break-even."""

    snapshot = AccountAnalyticsSnapshot(
        snapshot_id="snapshot_1",
        user_id="user_1",
        scope=AnalyticsScope.USER,
        calculated_at_utc=FIXED_NOW,
        trade_metrics_available=False,
        net_pnl=0.0,
    )

    with pytest.raises(AccountAnalyticsError, match="must stay unset"):
        snapshot.assert_trade_metrics_are_honest()


def test_snapshot_allows_trade_metrics_with_a_source() -> None:
    snapshot = AccountAnalyticsSnapshot(
        snapshot_id="snapshot_1",
        user_id="user_1",
        scope=AnalyticsScope.USER,
        calculated_at_utc=FIXED_NOW,
        trade_metrics_available=True,
        total_trades=5,
        win_rate=0.4,
        net_pnl=100.0,
    )

    snapshot.assert_trade_metrics_are_honest()

    assert snapshot.to_dict()["trade_metrics_available"] is True


def test_snapshot_validates_fractions() -> None:
    with pytest.raises(AccountAnalyticsError, match="must be between 0 and 1"):
        AccountAnalyticsSnapshot(
            snapshot_id="snapshot_1",
            user_id="user_1",
            scope=AnalyticsScope.USER,
            calculated_at_utc=FIXED_NOW,
            execution_rate=1.5,
        )

    with pytest.raises(AccountAnalyticsError, match="must be between 0 and 1"):
        AccountAnalyticsSnapshot(
            snapshot_id="snapshot_1",
            user_id="user_1",
            scope=AnalyticsScope.USER,
            calculated_at_utc=FIXED_NOW,
            trade_metrics_available=True,
            win_rate=-0.1,
        )


def test_snapshot_repr_and_defaults() -> None:
    snapshot = AccountAnalyticsSnapshot(
        snapshot_id="snapshot_1",
        user_id="user_1",
        scope=AnalyticsScope.ACCOUNT,
        account_id="account_1",
        calculated_at_utc=FIXED_NOW,
    )

    assert snapshot.trade_metrics_available is False
    assert snapshot.payload_json == {}
    assert snapshot.extra_metadata == {}
    assert "snapshot_1" in repr(snapshot)
