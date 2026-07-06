"""
Unit tests for Backtester.
"""

import pytest

from aqos.evaluation import Backtester, BacktestResult, BacktestTrade


def test_run_backtest():
    backtester = Backtester()

    result = backtester.run(
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
    )

    assert isinstance(result, BacktestResult)
    assert result.initial_balance == 10_000.0
    assert result.final_balance == 10_075.0
    assert result.total_profit == 75.0
    assert result.return_percent == pytest.approx(0.0075)
    assert result.win_rate == pytest.approx(2 / 3)
    assert len(result.trades) == 3


def test_backtest_trade_records():
    backtester = Backtester()

    result = backtester.run(
        profits=[100.0, -50.0],
        initial_balance=10_000.0,
    )

    first_trade = result.trades[0]
    second_trade = result.trades[1]

    assert isinstance(first_trade, BacktestTrade)
    assert first_trade.index == 0
    assert first_trade.profit == 100.0
    assert first_trade.balance == 10_100.0

    assert second_trade.index == 1
    assert second_trade.profit == -50.0
    assert second_trade.balance == 10_050.0


def test_equity_curve():
    backtester = Backtester()

    curve = backtester.equity_curve(
        profits=[100.0, -50.0, 25.0],
        initial_balance=10_000.0,
    )

    assert curve == [
        10_000.0,
        10_100.0,
        10_050.0,
        10_075.0,
    ]


def test_win_rate():
    backtester = Backtester()

    result = backtester.win_rate(
        profits=[100.0, -50.0, 25.0, 0.0],
    )

    assert result == 0.5


def test_max_drawdown():
    backtester = Backtester()

    result = backtester.max_drawdown(
        equity_curve=[
            10_000.0,
            11_000.0,
            10_500.0,
            9_900.0,
            12_000.0,
        ]
    )

    assert result == pytest.approx(0.1)


def test_max_drawdown_without_loss():
    backtester = Backtester()

    result = backtester.max_drawdown(
        equity_curve=[
            10_000.0,
            11_000.0,
            12_000.0,
        ]
    )

    assert result == 0.0


def test_empty_profits_for_run():
    backtester = Backtester()

    with pytest.raises(ValueError):
        backtester.run(
            profits=[],
            initial_balance=10_000.0,
        )


def test_invalid_initial_balance_for_run():
    backtester = Backtester()

    with pytest.raises(ValueError):
        backtester.run(
            profits=[100.0],
            initial_balance=0,
        )


def test_empty_profits_for_equity_curve():
    backtester = Backtester()

    with pytest.raises(ValueError):
        backtester.equity_curve(
            profits=[],
            initial_balance=10_000.0,
        )


def test_empty_equity_curve():
    backtester = Backtester()

    with pytest.raises(ValueError):
        backtester.max_drawdown([])


def test_negative_equity_value():
    backtester = Backtester()

    with pytest.raises(ValueError):
        backtester.max_drawdown(
            equity_curve=[
                10_000.0,
                -1.0,
            ]
        )


def test_invalid_initial_equity():
    backtester = Backtester()

    with pytest.raises(ValueError):
        backtester.max_drawdown(
            equity_curve=[
                0.0,
                10_000.0,
            ]
        )