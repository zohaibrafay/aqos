from __future__ import annotations

import json

import pandas as pd

from aqos.backtesting.cli import run_backtesting_cli


def build_strategy_smoke_dataset() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2300.0,
                "high": 2305.0,
                "low": 2298.0,
                "close": 2300.0,
                "volume": 1000,
            },
            {
                "timestamp": "2026-01-01T01:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2301.0,
                "high": 2312.0,
                "low": 2300.0,
                "close": 2310.0,
                "volume": 1100,
            },
            {
                "timestamp": "2026-01-01T02:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2310.0,
                "high": 2335.0,
                "low": 2308.0,
                "close": 2310.0,
                "volume": 1200,
            },
        ]
    )


def test_strategy_backtesting_cli_end_to_end_smoke(
    tmp_path,
    capsys,
) -> None:
    data_path = tmp_path / "xauusd_bars.csv"
    output_dir = tmp_path / "strategy_backtest_output"

    build_strategy_smoke_dataset().to_csv(data_path, index=False)

    exit_code = run_backtesting_cli(
        [
            "strategy-backtest",
            "--data-path",
            str(data_path),
            "--output-dir",
            str(output_dir),
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--strategy-name",
            "sprint_036_close_momentum_smoke",
            "--rule-strategy",
            "close_momentum",
            "--lookback-bars",
            "1",
            "--min-return-fraction",
            "0.001",
            "--stop-loss-points",
            "10",
            "--take-profit-points",
            "20",
            "--confidence",
            "0.72",
            "--fixed-quantity",
            "1",
            "--spread-points",
            "0",
            "--slippage-points",
            "0",
            "--commission-per-trade",
            "0",
            "--point-value",
            "1",
            "--max-open-positions",
            "1",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    report_path = output_dir / "strategy_backtest_report.json"
    trades_path = output_dir / "strategy_backtest_trades.csv"
    equity_path = output_dir / "strategy_backtest_equity_curve.csv"
    orders_path = output_dir / "strategy_backtest_orders.csv"
    signals_path = output_dir / "strategy_backtest_signals.csv"
    adapter_results_path = output_dir / "strategy_backtest_adapter_results.json"

    assert exit_code == 0

    assert report_path.exists()
    assert trades_path.exists()
    assert equity_path.exists()
    assert orders_path.exists()
    assert signals_path.exists()
    assert adapter_results_path.exists()

    assert payload["data_load"]["loaded_rows"] == 3
    assert payload["run_config"]["strategy_name"] == (
        "sprint_036_close_momentum_smoke"
    )
    assert payload["metrics"]["metadata"]["adapter_type"] == "rule_based"
    assert payload["metrics"]["metadata"]["adapter_name"] == (
        "rule_based_signal_adapter"
    )
    assert payload["metrics"]["total_trades"] == 1
    assert payload["metrics"]["winning_trades"] == 1
    assert payload["metrics"]["net_profit"] == 29.0
    assert payload["metrics"]["final_balance"] == 10029.0
    assert payload["final_state"]["open_position_count"] == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    adapter_results = json.loads(adapter_results_path.read_text(encoding="utf-8"))
    trades = pd.read_csv(trades_path)
    equity = pd.read_csv(equity_path)
    orders = pd.read_csv(orders_path)
    signals = pd.read_csv(signals_path)

    assert report["metrics"]["total_trades"] == 1
    assert report["metrics"]["profit_factor"] == float("inf")

    assert len(adapter_results) == 3
    assert adapter_results[0]["signal"]["action"] == "hold"
    assert adapter_results[1]["signal"]["action"] == "buy"
    assert adapter_results[2]["signal"]["action"] == "hold"

    assert len(signals) == 3
    assert signals.iloc[1]["action"] == "buy"
    assert signals.iloc[1]["confidence"] == 0.72
    assert signals.iloc[1]["take_profit"] == 2330.0

    assert len(orders) == 1
    assert orders.iloc[0]["status"] == "filled"
    assert orders.iloc[0]["side"] == "long"

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "take_profit"
    assert trades.iloc[0]["net_pnl"] == 29.0

    assert len(equity) >= 3
    assert equity.iloc[-1]["balance"] == 10029.0