from __future__ import annotations

import json

import pytest

from aqos.backtesting.analytics import (
    BACKTEST_ANALYTICS_VERSION,
    BacktestPeriodGranularity,
    build_backtest_advanced_report,
    build_duration_stats,
    build_exit_reason_breakdowns,
    build_period_performance,
    build_risk_stats,
    build_side_breakdown,
    build_side_breakdowns,
    build_streak_stats,
    calculate_equity_returns,
    calculate_sharpe_like_ratio,
    calculate_trade_duration_seconds,
    parse_backtest_timestamp,
    resolve_period_key,
    write_backtest_advanced_report,
)
from aqos.backtesting.contracts import (
    BacktestEquityPoint,
    BacktestExitReason,
    BacktestSide,
    BacktestTrade,
)
from aqos.backtesting.metrics import (
    build_backtest_equity_curve,
    calculate_backtest_performance_metrics,
)


def build_trade(
    trade_id: str,
    side: BacktestSide,
    net_pnl: float,
    entry_timestamp: str = "2026-01-01T00:00:00",
    exit_timestamp: str = "2026-01-01T02:00:00",
    exit_reason: BacktestExitReason = BacktestExitReason.TAKE_PROFIT,
) -> BacktestTrade:
    return BacktestTrade(
        trade_id=trade_id,
        position_id=f"position_{trade_id}",
        symbol="XAUUSD",
        side=side,
        entry_timestamp=entry_timestamp,
        exit_timestamp=exit_timestamp,
        entry_price=2000.0,
        exit_price=2000.0 + net_pnl,
        quantity=1.0,
        gross_pnl=net_pnl,
        fees=0.0,
        net_pnl=net_pnl,
        return_fraction=net_pnl / 2000.0,
        exit_reason=exit_reason,
    )


def build_sample_trades() -> tuple[BacktestTrade, ...]:
    return (
        build_trade(
            "t1",
            BacktestSide.LONG,
            100.0,
            "2026-01-01T00:00:00",
            "2026-01-01T02:00:00",
        ),
        build_trade(
            "t2",
            BacktestSide.LONG,
            -40.0,
            "2026-01-05T00:00:00",
            "2026-01-05T01:00:00",
            BacktestExitReason.STOP_LOSS,
        ),
        build_trade(
            "t3",
            BacktestSide.SHORT,
            -20.0,
            "2026-02-01T00:00:00",
            "2026-02-01T03:00:00",
            BacktestExitReason.STOP_LOSS,
        ),
        build_trade(
            "t4",
            BacktestSide.SHORT,
            60.0,
            "2026-02-10T00:00:00",
            "2026-02-10T04:00:00",
        ),
        build_trade(
            "t5",
            BacktestSide.LONG,
            30.0,
            "2026-02-20T00:00:00",
            "2026-02-20T01:00:00",
            BacktestExitReason.END_OF_DATA,
        ),
    )


def build_sample_equity_curve():
    points = tuple(
        BacktestEquityPoint(
            timestamp=f"2026-01-0{index + 1}T00:00:00",
            balance=balance,
            equity=balance,
            drawdown=0.0 if index == 0 else max(0.0, (10_100.0 - balance) / 10_100.0),
        )
        for index, balance in enumerate([10_000.0, 10_100.0, 10_060.0, 10_130.0])
    )

    return build_backtest_equity_curve(points=points, initial_balance=10_000.0)


def build_sample_metrics(trades: tuple[BacktestTrade, ...]):
    return calculate_backtest_performance_metrics(
        initial_balance=10_000.0,
        final_balance=10_130.0,
        trades=trades,
        equity_curve=build_sample_equity_curve(),
    )


def test_analytics_version_is_exposed() -> None:
    assert BACKTEST_ANALYTICS_VERSION == "1.0"


def test_parse_backtest_timestamp() -> None:
    assert parse_backtest_timestamp("2026-01-01T00:00:00") is not None
    assert parse_backtest_timestamp("2026-01-01T00:00:00Z") is not None
    assert parse_backtest_timestamp("not-a-timestamp") is None
    assert parse_backtest_timestamp("   ") is None


def test_resolve_period_key_granularities() -> None:
    timestamp = "2026-02-17T13:45:00"

    assert resolve_period_key(timestamp, BacktestPeriodGranularity.DAILY) == (
        "2026-02-17"
    )
    assert resolve_period_key(timestamp, BacktestPeriodGranularity.MONTHLY) == (
        "2026-02"
    )
    assert resolve_period_key(timestamp, BacktestPeriodGranularity.YEARLY) == "2026"
    assert resolve_period_key("bad") == "unknown"


def test_calculate_trade_duration_seconds() -> None:
    trade = build_trade(
        "t1",
        BacktestSide.LONG,
        10.0,
        "2026-01-01T00:00:00",
        "2026-01-01T02:30:00",
    )

    assert calculate_trade_duration_seconds(trade) == 9000.0


def test_calculate_trade_duration_rejects_mixed_timezones() -> None:
    trade = build_trade(
        "t1",
        BacktestSide.LONG,
        10.0,
        "2026-01-01T00:00:00",
        "2026-01-01T02:00:00+00:00",
    )

    assert calculate_trade_duration_seconds(trade) is None


def test_calculate_trade_duration_handles_unparsable_timestamp() -> None:
    trade = build_trade("t1", BacktestSide.LONG, 10.0, "start", "end")

    assert calculate_trade_duration_seconds(trade) is None


def test_side_breakdown_for_long_trades() -> None:
    breakdown = build_side_breakdown(BacktestSide.LONG, build_sample_trades())

    assert breakdown.side == "long"
    assert breakdown.trades == 3
    assert breakdown.winning_trades == 2
    assert breakdown.losing_trades == 1
    assert breakdown.net_pnl == pytest.approx(90.0)
    assert breakdown.gross_profit == pytest.approx(130.0)
    assert breakdown.gross_loss == pytest.approx(-40.0)
    assert breakdown.win_rate == pytest.approx(2 / 3)
    assert breakdown.average_pnl == pytest.approx(30.0)
    assert breakdown.profit_factor == pytest.approx(3.25)


def test_side_breakdowns_cover_both_sides() -> None:
    breakdowns = build_side_breakdowns(build_sample_trades())

    assert [breakdown.side for breakdown in breakdowns] == ["long", "short"]
    assert breakdowns[1].trades == 2
    assert breakdowns[1].net_pnl == pytest.approx(40.0)


def test_side_breakdown_with_no_trades() -> None:
    breakdown = build_side_breakdown(BacktestSide.SHORT, ())

    assert breakdown.trades == 0
    assert breakdown.win_rate == 0.0
    assert breakdown.average_pnl == 0.0
    assert breakdown.profit_factor is None


def test_exit_reason_breakdowns_only_include_used_reasons() -> None:
    breakdowns = build_exit_reason_breakdowns(build_sample_trades())
    by_reason = {breakdown.exit_reason: breakdown for breakdown in breakdowns}

    assert set(by_reason) == {"stop_loss", "take_profit", "end_of_data"}
    assert by_reason["stop_loss"].trades == 2
    assert by_reason["stop_loss"].net_pnl == pytest.approx(-60.0)
    assert by_reason["take_profit"].winning_trades == 2
    assert by_reason["take_profit"].share_of_trades == pytest.approx(0.4)


def test_exit_reason_breakdowns_for_no_trades() -> None:
    assert build_exit_reason_breakdowns(()) == ()


def test_period_performance_is_sorted_by_period() -> None:
    periods = build_period_performance(build_sample_trades())

    assert [period.period for period in periods] == ["2026-01", "2026-02"]
    assert periods[0].trades == 2
    assert periods[0].net_pnl == pytest.approx(60.0)
    assert periods[1].trades == 3
    assert periods[1].net_pnl == pytest.approx(70.0)
    assert periods[1].win_rate == pytest.approx(2 / 3)


def test_period_performance_daily_granularity() -> None:
    periods = build_period_performance(
        build_sample_trades(),
        BacktestPeriodGranularity.DAILY,
    )

    assert len(periods) == 5
    assert periods[0].period == "2026-01-01"


def test_streak_stats() -> None:
    streaks = build_streak_stats(build_sample_trades())

    assert streaks.max_consecutive_wins == 2
    assert streaks.max_consecutive_losses == 2
    assert streaks.final_streak == 2
    assert streaks.final_streak_kind == "win"


def test_streak_stats_resets_on_breakeven() -> None:
    trades = (
        build_trade("t1", BacktestSide.LONG, 10.0),
        build_trade("t2", BacktestSide.LONG, 0.0),
        build_trade("t3", BacktestSide.LONG, -5.0),
    )

    streaks = build_streak_stats(trades)

    assert streaks.max_consecutive_wins == 1
    assert streaks.final_streak == 1
    assert streaks.final_streak_kind == "loss"


def test_streak_stats_for_no_trades() -> None:
    streaks = build_streak_stats(())

    assert streaks.max_consecutive_wins == 0
    assert streaks.final_streak == 0
    assert streaks.final_streak_kind is None


def test_duration_stats() -> None:
    durations = build_duration_stats(build_sample_trades())

    assert durations.measured_trades == 5
    assert durations.min_seconds == 3600.0
    assert durations.max_seconds == 14400.0
    assert durations.median_seconds == 7200.0
    assert durations.average_seconds == pytest.approx(7920.0)


def test_duration_stats_without_parsable_timestamps() -> None:
    durations = build_duration_stats(
        (build_trade("t1", BacktestSide.LONG, 5.0, "start", "end"),)
    )

    assert durations.measured_trades == 0
    assert durations.average_seconds is None
    assert durations.median_seconds is None


def test_calculate_equity_returns() -> None:
    returns = calculate_equity_returns(build_sample_equity_curve())

    assert len(returns) == 3
    assert returns[0] == pytest.approx(0.01)


def test_calculate_equity_returns_needs_two_points() -> None:
    assert calculate_equity_returns(None) == ()


def test_calculate_sharpe_like_ratio() -> None:
    stdev, ratio = calculate_sharpe_like_ratio((0.01, -0.01, 0.02))

    assert stdev is not None and stdev > 0
    assert ratio is not None


def test_calculate_sharpe_like_ratio_for_flat_returns() -> None:
    stdev, ratio = calculate_sharpe_like_ratio((0.0, 0.0, 0.0))

    assert stdev == 0.0
    assert ratio is None


def test_calculate_sharpe_like_ratio_needs_two_returns() -> None:
    assert calculate_sharpe_like_ratio((0.01,)) == (None, None)


def test_risk_stats() -> None:
    trades = build_sample_trades()
    metrics = build_sample_metrics(trades)

    risk = build_risk_stats(metrics, trades, build_sample_equity_curve())

    assert risk.average_win == pytest.approx(190.0 / 3)
    assert risk.average_loss == pytest.approx(-30.0)
    assert risk.payoff_ratio == pytest.approx((190.0 / 3) / 30.0)
    assert risk.expectancy == pytest.approx(
        0.6 * (190.0 / 3) + 0.4 * -30.0
    )
    assert risk.recovery_factor is not None
    assert risk.return_to_drawdown is not None
    assert risk.sharpe_like_ratio is not None


def test_risk_stats_without_trades() -> None:
    metrics = calculate_backtest_performance_metrics(
        initial_balance=10_000.0,
        final_balance=10_000.0,
        trades=(),
    )

    risk = build_risk_stats(metrics, ())

    assert risk.average_win is None
    assert risk.average_loss is None
    assert risk.payoff_ratio is None
    assert risk.expectancy == 0.0
    assert risk.recovery_factor is None
    assert risk.return_to_drawdown is None
    assert risk.sharpe_like_ratio is None


def test_build_advanced_report_payload() -> None:
    trades = build_sample_trades()
    metrics = build_sample_metrics(trades)

    report = build_backtest_advanced_report(
        metrics=metrics,
        trades=trades,
        equity_curve=build_sample_equity_curve(),
        metadata={"strategy_name": "unit_test"},
        created_at_utc="2026-03-01T00:00:00+00:00",
    )

    payload = report.to_dict()

    assert payload["report_version"] == "1.0"
    assert payload["created_at_utc"] == "2026-03-01T00:00:00+00:00"
    assert payload["period_granularity"] == "monthly"
    assert payload["metrics"]["total_trades"] == 5
    assert len(payload["side_breakdowns"]) == 2
    assert len(payload["period_performance"]) == 2
    assert payload["streaks"]["max_consecutive_wins"] == 2
    assert payload["durations"]["measured_trades"] == 5
    assert payload["risk"]["expectancy"] is not None
    assert payload["metadata"] == {"strategy_name": "unit_test"}


def test_write_advanced_report(tmp_path) -> None:
    trades = build_sample_trades()

    report = build_backtest_advanced_report(
        metrics=build_sample_metrics(trades),
        trades=trades,
        equity_curve=build_sample_equity_curve(),
    )

    path = write_backtest_advanced_report(
        tmp_path / "nested" / "analytics.json",
        report,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.exists()
    assert payload["metrics"]["total_trades"] == 5
