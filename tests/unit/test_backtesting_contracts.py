from __future__ import annotations

import pytest

from aqos.backtesting import (
    BACKTESTING_CONTRACTS_VERSION,
    BacktestBar,
    BacktestExecutionConfig,
    BacktestExecutionTiming,
    BacktestExitReason,
    BacktestPosition,
    BacktestRunConfig,
    BacktestSide,
    BacktestSignal,
    BacktestSignalAction,
    build_backtest_trade,
    calculate_drawdown,
    calculate_net_pnl,
    calculate_trade_fees,
    calculate_trade_gross_pnl,
    calculate_trade_return_fraction,
)


def test_backtest_bar_to_dict() -> None:
    bar = BacktestBar(
        timestamp="2026-01-01T00:00:00",
        symbol="XAUUSD",
        timeframe="H1",
        open=2300.0,
        high=2310.0,
        low=2290.0,
        close=2305.0,
        volume=1000.0,
    )

    assert bar.to_dict() == {
        "timestamp": "2026-01-01T00:00:00",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "open": 2300.0,
        "high": 2310.0,
        "low": 2290.0,
        "close": 2305.0,
        "volume": 1000.0,
        "metadata": {},
    }


def test_backtest_bar_rejects_invalid_ohlc() -> None:
    with pytest.raises(ValueError, match="high"):
        BacktestBar(
            timestamp="2026-01-01T00:00:00",
            symbol="XAUUSD",
            timeframe="H1",
            open=2300.0,
            high=2299.0,
            low=2290.0,
            close=2305.0,
        )

    with pytest.raises(ValueError, match="low"):
        BacktestBar(
            timestamp="2026-01-01T00:00:00",
            symbol="XAUUSD",
            timeframe="H1",
            open=2300.0,
            high=2310.0,
            low=2301.0,
            close=2299.0,
        )


def test_backtest_signal_resolves_side() -> None:
    buy_signal = BacktestSignal(
        timestamp="2026-01-01T00:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.BUY,
        confidence=0.8,
    )
    sell_signal = BacktestSignal(
        timestamp="2026-01-01T01:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.SELL,
        confidence=0.7,
    )
    hold_signal = BacktestSignal(
        timestamp="2026-01-01T02:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.HOLD,
    )

    assert buy_signal.side == BacktestSide.LONG
    assert sell_signal.side == BacktestSide.SHORT
    assert hold_signal.side is None
    assert buy_signal.to_dict()["side"] == "long"


def test_backtest_signal_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        BacktestSignal(
            timestamp="2026-01-01T00:00:00",
            symbol="XAUUSD",
            action=BacktestSignalAction.BUY,
            confidence=1.5,
        )


def test_execution_config_to_dict() -> None:
    config = BacktestExecutionConfig(
        initial_balance=5000.0,
        risk_fraction=0.02,
        fixed_quantity=1.5,
        spread_points=0.2,
        slippage_points=0.1,
        commission_per_trade=3.5,
        point_value=10.0,
        execution_timing=BacktestExecutionTiming.CURRENT_CLOSE,
        allow_short=False,
        max_open_positions=2,
    )

    assert config.to_dict() == {
        "initial_balance": 5000.0,
        "risk_fraction": 0.02,
        "fixed_quantity": 1.5,
        "spread_points": 0.2,
        "slippage_points": 0.1,
        "commission_per_trade": 3.5,
        "point_value": 10.0,
        "execution_timing": "current_close",
        "allow_short": False,
        "max_open_positions": 2,
    }


def test_execution_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="initial_balance"):
        BacktestExecutionConfig(initial_balance=0)

    with pytest.raises(ValueError, match="risk_fraction"):
        BacktestExecutionConfig(risk_fraction=0)

    with pytest.raises(ValueError, match="max_open_positions"):
        BacktestExecutionConfig(max_open_positions=0)


def test_backtest_run_config_to_dict() -> None:
    config = BacktestRunConfig(
        symbol="XAUUSD",
        timeframe="H1",
        strategy_name="baseline_ml_signal",
        start_timestamp="2026-01-01T00:00:00",
        end_timestamp="2026-02-01T00:00:00",
    )

    payload = config.to_dict()

    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "H1"
    assert payload["strategy_name"] == "baseline_ml_signal"
    assert payload["execution"]["initial_balance"] == 10000.0
    assert payload["start_timestamp"] == "2026-01-01T00:00:00"
    assert payload["end_timestamp"] == "2026-02-01T00:00:00"


def test_calculate_trade_gross_pnl_long_and_short() -> None:
    assert calculate_trade_gross_pnl(
        BacktestSide.LONG,
        entry_price=2300.0,
        exit_price=2310.0,
        quantity=2.0,
        point_value=1.0,
    ) == 20.0

    assert calculate_trade_gross_pnl(
        BacktestSide.SHORT,
        entry_price=2300.0,
        exit_price=2290.0,
        quantity=2.0,
        point_value=1.0,
    ) == 20.0


def test_calculate_trade_return_fraction_long_and_short() -> None:
    assert calculate_trade_return_fraction(
        BacktestSide.LONG,
        entry_price=100.0,
        exit_price=110.0,
    ) == 0.1

    assert calculate_trade_return_fraction(
        BacktestSide.SHORT,
        entry_price=100.0,
        exit_price=90.0,
    ) == 0.1


def test_calculate_trade_fees_and_net_pnl() -> None:
    assert calculate_trade_fees(3.5) == 7.0
    assert calculate_net_pnl(gross_pnl=20.0, fees=7.0) == 13.0


def test_calculate_drawdown() -> None:
    assert calculate_drawdown(equity=10000.0, peak_equity=10000.0) == 0.0
    assert calculate_drawdown(equity=9000.0, peak_equity=10000.0) == 0.1


def test_build_backtest_trade_from_position() -> None:
    position = BacktestPosition(
        position_id="position_1",
        symbol="XAUUSD",
        side=BacktestSide.LONG,
        entry_timestamp="2026-01-01T00:00:00",
        entry_price=2300.0,
        quantity=2.0,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    trade = build_backtest_trade(
        position=position,
        exit_timestamp="2026-01-01T04:00:00",
        exit_price=2310.0,
        exit_reason=BacktestExitReason.TAKE_PROFIT,
        commission_per_trade=2.0,
        point_value=1.0,
    )

    assert trade.trade_id == "trade_position_1"
    assert trade.gross_pnl == 20.0
    assert trade.fees == 4.0
    assert trade.net_pnl == 16.0
    assert trade.is_win is True
    assert trade.to_dict()["exit_reason"] == "take_profit"


def test_backtesting_contracts_version_exported() -> None:
    assert BACKTESTING_CONTRACTS_VERSION == "1.0"