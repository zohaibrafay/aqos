from __future__ import annotations

import json

import pandas as pd

from aqos.backtesting.cli import run_backtesting_cli


def build_backtesting_smoke_dataset() -> pd.DataFrame:
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
                "confidence": 0.82,
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
                "high": 2315.0,
                "low": 2308.0,
                "close": 2312.0,
                "volume": 1200,
                "signal": "sell",
                "confidence": 0.76,
                "stop_loss": 2320.0,
                "take_profit": 2300.0,
            },
            {
                "timestamp": "2026-01-01T03:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2312.0,
                "high": 2318.0,
                "low": 2308.0,
                "close": 2315.0,
                "volume": 1300,
                "signal": "hold",
                "confidence": None,
                "stop_loss": None,
                "take_profit": None,
            },
            {
                "timestamp": "2026-01-01T04:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2315.0,
                "high": 2322.0,
                "low": 2310.0,
                "close": 2320.0,
                "volume": 1400,
                "signal": "hold",
                "confidence": None,
                "stop_loss": None,
                "take_profit": None,
            },
        ]
    )


def test_backtesting_cli_end_to_end_smoke(
    tmp_path,
    capsys,
) -> None:
    data_path = tmp_path / "xauusd_signals.csv"
    output_dir = tmp_path / "backtest_output"

    build_backtesting_smoke_dataset().to_csv(data_path, index=False)

    exit_code = run_backtesting_cli(
        [
            "backtest",
            "--data-path",
            str(data_path),
            "--output-dir",
            str(output_dir),
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--strategy-name",
            "sprint_035_smoke_strategy",
            "--initial-balance",
            "10000",
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

    report_path = output_dir / "backtest_report.json"
    trades_path = output_dir / "backtest_trades.csv"
    equity_path = output_dir / "backtest_equity_curve.csv"
    orders_path = output_dir / "backtest_orders.csv"

    assert exit_code == 0

    assert report_path.exists()
    assert trades_path.exists()
    assert equity_path.exists()
    assert orders_path.exists()

    assert payload["data_load"]["loaded_rows"] == 5
    assert payload["metrics"]["total_trades"] == 2
    assert payload["metrics"]["winning_trades"] == 1
    assert payload["metrics"]["losing_trades"] == 1
    assert payload["metrics"]["net_profit"] == 0.0
    assert payload["metrics"]["final_balance"] == 10000.0
    assert payload["final_state"]["open_position_count"] == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    trades = pd.read_csv(trades_path)
    equity_curve = pd.read_csv(equity_path)
    orders = pd.read_csv(orders_path)

    assert report["run_config"]["strategy_name"] == "sprint_035_smoke_strategy"
    assert report["metrics"]["profit_factor"] == 1.0

    assert len(trades) == 2
    assert set(trades["exit_reason"].tolist()) == {"take_profit", "stop_loss"}

    assert len(equity_curve) >= 5
    assert equity_curve.iloc[-1]["balance"] == 10000.0

    assert len(orders) == 2
    assert orders.iloc[0]["status"] == "filled"
    assert orders.iloc[1]["status"] == "filled"