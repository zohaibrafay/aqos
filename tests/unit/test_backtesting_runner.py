from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.backtesting import (
    BACKTEST_RUNNER_VERSION,
    BacktestRunnerConfig,
    BacktestSignalAction,
    build_backtest_signals_from_dataframe,
    parse_backtest_signal_action,
    run_backtest_from_csv,
)


def build_backtest_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2300.0,
                "high": 2306.0,
                "low": 2298.0,
                "close": 2304.0,
                "volume": 1000,
                "signal": "buy",
                "confidence": 0.8,
                "stop_loss": 2290.0,
                "take_profit": 2310.0,
            },
            {
                "timestamp": "2026-01-01T01:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2304.0,
                "high": 2312.0,
                "low": 2301.0,
                "close": 2310.0,
                "volume": 1100,
                "signal": "hold",
                "confidence": None,
                "stop_loss": None,
                "take_profit": None,
            },
            {
                "timestamp": "2026-01-01T02:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2310.0,
                "high": 2314.0,
                "low": 2308.0,
                "close": 2312.0,
                "volume": 1200,
                "signal": "hold",
                "confidence": None,
                "stop_loss": None,
                "take_profit": None,
            },
        ]
    )


def test_parse_backtest_signal_action_aliases() -> None:
    assert parse_backtest_signal_action("buy") == BacktestSignalAction.BUY
    assert parse_backtest_signal_action("long") == BacktestSignalAction.BUY
    assert parse_backtest_signal_action("sell") == BacktestSignalAction.SELL
    assert parse_backtest_signal_action("short") == BacktestSignalAction.SELL
    assert parse_backtest_signal_action("exit") == BacktestSignalAction.EXIT
    assert parse_backtest_signal_action("") == BacktestSignalAction.HOLD
    assert parse_backtest_signal_action(None) == BacktestSignalAction.HOLD


def test_parse_backtest_signal_action_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unsupported backtest signal action"):
        parse_backtest_signal_action("wait-for-magic")


def test_build_backtest_signals_from_dataframe() -> None:
    dataframe = build_backtest_dataframe()
    signals = build_backtest_signals_from_dataframe(
        dataframe,
        BacktestRunnerConfig(data_path="data.csv"),
    )

    assert len(signals) == 3
    assert signals[0].action == BacktestSignalAction.BUY
    assert signals[0].confidence == 0.8
    assert signals[0].stop_loss == 2290.0
    assert signals[0].take_profit == 2310.0
    assert signals[1].action == BacktestSignalAction.HOLD


def test_run_backtest_from_csv_writes_report_trades_orders_and_equity(tmp_path) -> None:
    data_path = tmp_path / "signals.csv"
    output_dir = tmp_path / "backtest"

    build_backtest_dataframe().to_csv(data_path, index=False)

    output = run_backtest_from_csv(
        BacktestRunnerConfig(
            data_path=data_path,
            output_dir=output_dir,
            strategy_name="unit_test_strategy",
            fixed_quantity=1.0,
        )
    )

    assert output.report_path.exists()
    assert output.trades_path.exists()
    assert output.equity_curve_path.exists()
    assert output.orders_path.exists()

    assert output.final_state.open_position_count == 0
    assert output.metrics.total_trades == 1
    assert output.metrics.winning_trades == 1
    assert output.metrics.final_balance == 10_010.0
    assert output.metrics.net_profit == 10.0

    report = json.loads(output.report_path.read_text(encoding="utf-8"))

    assert report["metrics"]["total_trades"] == 1
    assert report["metrics"]["net_profit"] == 10.0
    assert report["data_load"]["loaded_rows"] == 3

    trades = pd.read_csv(output.trades_path)
    equity = pd.read_csv(output.equity_curve_path)
    orders = pd.read_csv(output.orders_path)

    assert len(trades) == 1
    assert len(equity) >= 3
    assert len(orders) == 1


def test_run_backtest_from_csv_closes_open_position_at_end_of_data(tmp_path) -> None:
    data_path = tmp_path / "signals.csv"
    output_dir = tmp_path / "backtest"

    dataframe = build_backtest_dataframe()
    dataframe.loc[0, "take_profit"] = 2400.0
    dataframe.loc[0, "stop_loss"] = 2200.0
    dataframe.to_csv(data_path, index=False)

    output = run_backtest_from_csv(
        BacktestRunnerConfig(
            data_path=data_path,
            output_dir=output_dir,
            fixed_quantity=1.0,
        )
    )

    assert output.final_state.open_position_count == 0
    assert output.metrics.total_trades == 1
    assert output.final_state.trades[0].exit_reason.value == "end_of_data"


def test_run_backtest_from_csv_rejects_missing_signal_column(tmp_path) -> None:
    data_path = tmp_path / "signals.csv"
    dataframe = build_backtest_dataframe().drop(columns=["signal"])
    dataframe.to_csv(data_path, index=False)

    with pytest.raises(ValueError, match="Signal column is missing"):
        run_backtest_from_csv(
            BacktestRunnerConfig(
                data_path=data_path,
                output_dir=tmp_path / "backtest",
            )
        )


def test_backtest_runner_version_exported() -> None:
    assert BACKTEST_RUNNER_VERSION == "1.0"