from __future__ import annotations

import json

import pandas as pd

from aqos.backtesting.cli import (
    build_backtest_runner_config_from_args,
    build_backtesting_cli_parser,
    run_backtesting_cli,
    build_rule_based_adapter_from_args,
    build_strategy_backtest_runner_config_from_args,
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
        ]
    )


def test_backtesting_cli_parser_accepts_backtest_command() -> None:
    parser = build_backtesting_cli_parser()

    args = parser.parse_args(
        [
            "backtest",
            "--data-path",
            "signals.csv",
            "--output-dir",
            "tmp/backtest",
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--strategy-name",
            "test_strategy",
            "--signal-column",
            "signal",
            "--initial-balance",
            "5000",
            "--risk-fraction",
            "0.02",
            "--fixed-quantity",
            "2",
            "--spread-points",
            "0.2",
            "--slippage-points",
            "0.1",
            "--commission-per-trade",
            "1.5",
            "--point-value",
            "1",
            "--max-open-positions",
            "2",
            "--intrabar-exit-policy",
            "take_profit_first",
            "--no-short",
        ]
    )

    assert args.command == "backtest"
    assert args.data_path == "signals.csv"
    assert args.symbol == "XAUUSD"
    assert args.timeframe == "H1"
    assert args.strategy_name == "test_strategy"
    assert args.initial_balance == 5000.0
    assert args.risk_fraction == 0.02
    assert args.fixed_quantity == 2.0
    assert args.no_short is True


def test_build_backtest_runner_config_from_args() -> None:
    parser = build_backtesting_cli_parser()
    args = parser.parse_args(
        [
            "backtest",
            "--data-path",
            "signals.csv",
            "--output-dir",
            "tmp/backtest",
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--use-risk-quantity",
        ]
    )

    config = build_backtest_runner_config_from_args(args)

    assert config.data_path.name == "signals.csv"
    assert config.output_dir.name == "backtest"
    assert config.symbol == "XAUUSD"
    assert config.timeframe == "H1"
    assert config.fixed_quantity is None


def test_run_backtesting_cli_backtest_writes_outputs(
    tmp_path,
    capsys,
) -> None:
    data_path = tmp_path / "signals.csv"
    output_dir = tmp_path / "backtest"

    build_backtest_dataframe().to_csv(data_path, index=False)

    exit_code = run_backtesting_cli(
        [
            "backtest",
            "--data-path",
            str(data_path),
            "--output-dir",
            str(output_dir),
            "--strategy-name",
            "cli_test_strategy",
            "--fixed-quantity",
            "1",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["metrics"]["total_trades"] == 1
    assert payload["metrics"]["net_profit"] == 10.0
    assert output_dir.joinpath("backtest_report.json").exists()
    assert output_dir.joinpath("backtest_trades.csv").exists()
    assert output_dir.joinpath("backtest_equity_curve.csv").exists()
    assert output_dir.joinpath("backtest_orders.csv").exists()
    
    
def test_backtesting_cli_parser_accepts_strategy_backtest_command() -> None:
    parser = build_backtesting_cli_parser()

    args = parser.parse_args(
        [
            "strategy-backtest",
            "--data-path",
            "bars.csv",
            "--output-dir",
            "tmp/strategy-backtest",
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--strategy-name",
            "close_momentum_test",
            "--rule-strategy",
            "close_momentum",
            "--lookback-bars",
            "2",
            "--min-return-fraction",
            "0.002",
            "--stop-loss-points",
            "8",
            "--take-profit-points",
            "16",
            "--confidence",
            "0.7",
            "--adapter-name",
            "momentum_adapter",
        ]
    )

    assert args.command == "strategy-backtest"
    assert args.data_path == "bars.csv"
    assert args.rule_strategy == "close_momentum"
    assert args.lookback_bars == 2
    assert args.min_return_fraction == 0.002
    assert args.stop_loss_points == 8.0
    assert args.take_profit_points == 16.0
    assert args.confidence == 0.7
    assert args.adapter_name == "momentum_adapter"


def test_build_strategy_backtest_runner_config_from_args() -> None:
    parser = build_backtesting_cli_parser()
    args = parser.parse_args(
        [
            "strategy-backtest",
            "--data-path",
            "bars.csv",
            "--output-dir",
            "tmp/strategy-backtest",
            "--symbol",
            "XAUUSD",
            "--timeframe",
            "H1",
            "--rule-strategy",
            "close_momentum",
            "--use-risk-quantity",
        ]
    )

    config = build_strategy_backtest_runner_config_from_args(args)

    assert config.data_path.name == "bars.csv"
    assert config.output_dir.name == "strategy-backtest"
    assert config.symbol == "XAUUSD"
    assert config.timeframe == "H1"
    assert config.fixed_quantity is None
    assert config.metadata["rule_strategy"] == "close_momentum"


def test_build_rule_based_adapter_from_args() -> None:
    parser = build_backtesting_cli_parser()
    args = parser.parse_args(
        [
            "strategy-backtest",
            "--data-path",
            "bars.csv",
            "--rule-strategy",
            "close_momentum",
            "--lookback-bars",
            "1",
            "--adapter-name",
            "cli_rule_adapter",
        ]
    )

    adapter = build_rule_based_adapter_from_args(args)

    assert adapter.adapter_name == "cli_rule_adapter"
    assert adapter.config.metadata["rule_strategy"] == "close_momentum"


def test_run_backtesting_cli_strategy_backtest_writes_outputs(
    tmp_path,
    capsys,
) -> None:
    data_path = tmp_path / "bars.csv"
    output_dir = tmp_path / "strategy_backtest"

    dataframe = pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2300.0,
                "high": 2306.0,
                "low": 2298.0,
                "close": 2300.0,
                "volume": 1000,
            },
            {
                "timestamp": "2026-01-01T01:00:00",
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "open": 2300.0,
                "high": 2322.0,
                "low": 2299.0,
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
                "close": 2330.0,
                "volume": 1200,
            },
        ]
    )
    dataframe.to_csv(data_path, index=False)

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
            "cli_close_momentum",
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
            "0.7",
            "--fixed-quantity",
            "1",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["metrics"]["total_trades"] >= 1
    assert payload["metrics"]["metadata"]["adapter_type"] == "rule_based"
    assert output_dir.joinpath("strategy_backtest_report.json").exists()
    assert output_dir.joinpath("strategy_backtest_trades.csv").exists()
    assert output_dir.joinpath("strategy_backtest_equity_curve.csv").exists()
    assert output_dir.joinpath("strategy_backtest_orders.csv").exists()
    assert output_dir.joinpath("strategy_backtest_signals.csv").exists()
    assert output_dir.joinpath("strategy_backtest_adapter_results.json").exists()