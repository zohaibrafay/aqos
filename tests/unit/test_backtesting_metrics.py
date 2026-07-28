from __future__ import annotations

import pytest

from aqos.backtesting import (
    BACKTEST_METRICS_VERSION,
    BacktestBar,
    BacktestEquityPoint,
    BacktestExecutionConfig,
    BacktestExitReason,
    BacktestPosition,
    BacktestSide,
    BacktestSignal,
    BacktestSignalAction,
    apply_backtest_signal,
    build_backtest_equity_curve,
    build_backtest_equity_point,
    build_backtest_equity_point_from_state,
    build_backtest_trade,
    build_initial_backtest_state,
    calculate_backtest_performance_metrics,
    calculate_equity,
    calculate_gross_loss,
    calculate_gross_profit,
    calculate_open_positions_unrealized_pnl,
    calculate_position_unrealized_pnl,
    calculate_profit_factor,
)


def build_bar(
    timestamp: str = "2026-01-01T01:00:00",
    open_price: float = 2300.0,
    high_price: float = 2310.0,
    low_price: float = 2290.0,
    close_price: float = 2305.0,
) -> BacktestBar:
    return BacktestBar(
        timestamp=timestamp,
        symbol="XAUUSD",
        timeframe="H1",
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=1000.0,
    )


def build_position(
    side: BacktestSide = BacktestSide.LONG,
    entry_price: float = 2300.0,
    quantity: float = 2.0,
) -> BacktestPosition:
    return BacktestPosition(
        position_id="position_1",
        symbol="XAUUSD",
        side=side,
        entry_timestamp="2026-01-01T00:00:00",
        entry_price=entry_price,
        quantity=quantity,
        stop_loss=2290.0 if side == BacktestSide.LONG else 2310.0,
        take_profit=2320.0 if side == BacktestSide.LONG else 2280.0,
    )


def build_trade(
    position: BacktestPosition,
    exit_price: float,
    exit_reason: BacktestExitReason = BacktestExitReason.SIGNAL_EXIT,
):
    return build_backtest_trade(
        position=position,
        exit_timestamp="2026-01-01T02:00:00",
        exit_price=exit_price,
        exit_reason=exit_reason,
        commission_per_trade=1.0,
        point_value=1.0,
    )


def test_calculate_position_unrealized_pnl_long_and_short() -> None:
    long_position = build_position(BacktestSide.LONG, entry_price=2300.0)
    short_position = build_position(BacktestSide.SHORT, entry_price=2300.0)

    assert calculate_position_unrealized_pnl(long_position, 2310.0) == 20.0
    assert calculate_position_unrealized_pnl(short_position, 2290.0) == 20.0


def test_calculate_open_positions_unrealized_pnl() -> None:
    positions = (
        build_position(BacktestSide.LONG, entry_price=2300.0, quantity=1.0),
        build_position(BacktestSide.SHORT, entry_price=2320.0, quantity=1.0),
    )
    bar = build_bar(close_price=2310.0)

    assert calculate_open_positions_unrealized_pnl(positions, bar) == 20.0


def test_calculate_equity() -> None:
    assert calculate_equity(balance=10_000.0, open_pnl=150.0) == 10_150.0

    with pytest.raises(ValueError, match="balance"):
        calculate_equity(balance=-1.0)


def test_build_backtest_equity_point() -> None:
    point = build_backtest_equity_point(
        timestamp="2026-01-01T01:00:00",
        balance=10_000.0,
        open_pnl=-500.0,
        peak_equity=10_000.0,
    )

    assert point.equity == 9500.0
    assert point.drawdown == 0.05
    assert point.to_dict()["open_pnl"] == -500.0


def test_build_backtest_equity_point_from_state() -> None:
    config = BacktestExecutionConfig(fixed_quantity=1.0)
    state = build_initial_backtest_state(config)

    state = apply_backtest_signal(
        state=state,
        signal=BacktestSignal(
            timestamp="2026-01-01T00:00:00",
            symbol="XAUUSD",
            action=BacktestSignalAction.BUY,
            stop_loss=2290.0,
            take_profit=2320.0,
        ),
        bar=build_bar(
            timestamp="2026-01-01T00:00:00",
            open_price=2300.0,
            close_price=2300.0,
        ),
        execution_config=config,
        order_index=1,
    )

    point = build_backtest_equity_point_from_state(
        state=state,
        bar=build_bar(close_price=2310.0),
        peak_equity=10_000.0,
    )

    assert point.balance == 10_000.0
    assert point.open_pnl == 10.0
    assert point.equity == 10_010.0


def test_build_backtest_equity_curve() -> None:
    points = (
        BacktestEquityPoint(
            timestamp="2026-01-01T00:00:00",
            balance=10_000.0,
            equity=10_000.0,
            open_pnl=0.0,
            drawdown=0.0,
        ),
        BacktestEquityPoint(
            timestamp="2026-01-01T01:00:00",
            balance=9500.0,
            equity=9500.0,
            open_pnl=0.0,
            drawdown=0.05,
        ),
        BacktestEquityPoint(
            timestamp="2026-01-01T02:00:00",
            balance=10_500.0,
            equity=10_500.0,
            open_pnl=0.0,
            drawdown=0.0,
        ),
    )

    curve = build_backtest_equity_curve(points, initial_balance=10_000.0)
    payload = curve.to_dict()

    assert curve.rows == 3
    assert curve.final_balance == 10_500.0
    assert curve.max_drawdown == 0.05
    assert curve.max_drawdown_amount == 500.0
    assert payload["rows"] == 3


def test_build_backtest_equity_curve_creates_initial_point_when_empty() -> None:
    curve = build_backtest_equity_curve((), initial_balance=10_000.0)

    assert curve.rows == 1
    assert curve.points[0].timestamp == "start"
    assert curve.points[0].equity == 10_000.0


def test_calculate_gross_profit_and_loss() -> None:
    winning_trade = build_trade(build_position(), exit_price=2310.0)
    losing_trade = build_trade(build_position(), exit_price=2290.0)

    trades = (winning_trade, losing_trade)

    assert calculate_gross_profit(trades) == 18.0
    assert calculate_gross_loss(trades) == -22.0


def test_calculate_profit_factor() -> None:
    assert calculate_profit_factor(100.0, -50.0) == 2.0
    assert calculate_profit_factor(100.0, 0.0) == float("inf")
    assert calculate_profit_factor(0.0, 0.0) is None

    with pytest.raises(ValueError, match="gross_profit"):
        calculate_profit_factor(-1.0, -50.0)

    with pytest.raises(ValueError, match="gross_loss"):
        calculate_profit_factor(100.0, 50.0)


def test_calculate_backtest_performance_metrics() -> None:
    winning_trade = build_trade(build_position(), exit_price=2310.0)
    losing_trade = build_trade(build_position(), exit_price=2290.0)

    curve = build_backtest_equity_curve(
        (
            BacktestEquityPoint(
                timestamp="2026-01-01T00:00:00",
                balance=10_000.0,
                equity=10_000.0,
                open_pnl=0.0,
                drawdown=0.0,
            ),
            BacktestEquityPoint(
                timestamp="2026-01-01T01:00:00",
                balance=9996.0,
                equity=9996.0,
                open_pnl=0.0,
                drawdown=0.0004,
            ),
        ),
        initial_balance=10_000.0,
    )

    metrics = calculate_backtest_performance_metrics(
        initial_balance=10_000.0,
        final_balance=9996.0,
        trades=(winning_trade, losing_trade),
        equity_curve=curve,
        metadata={"strategy": "test"},
    )

    payload = metrics.to_dict()

    assert metrics.total_trades == 2
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 1
    assert metrics.win_rate == 0.5
    assert metrics.gross_profit == 18.0
    assert metrics.gross_loss == -22.0
    assert metrics.profit_factor == pytest.approx(18.0 / 22.0)
    assert metrics.average_trade_pnl == -2.0
    assert metrics.best_trade_pnl == 18.0
    assert metrics.worst_trade_pnl == -22.0
    assert metrics.total_fees == 4.0
    assert metrics.max_drawdown == 0.0004
    assert payload["metadata"]["strategy"] == "test"


def test_calculate_backtest_performance_metrics_handles_no_trades() -> None:
    metrics = calculate_backtest_performance_metrics(
        initial_balance=10_000.0,
        final_balance=10_000.0,
        trades=(),
    )

    assert metrics.total_trades == 0
    assert metrics.win_rate == 0.0
    assert metrics.loss_rate == 0.0
    assert metrics.profit_factor is None
    assert metrics.best_trade_pnl is None
    assert metrics.worst_trade_pnl is None


def test_backtest_metrics_version_exported() -> None:
    assert BACKTEST_METRICS_VERSION == "1.0"