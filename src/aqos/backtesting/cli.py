from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from aqos.backtesting.builtin_strategies import (
    build_builtin_rule_strategy,
    list_builtin_rule_strategy_names,
)
from aqos.backtesting.rule_based_adapter import (
    RuleBasedBacktestSignalAdapter,
    RuleBasedSignalAdapterConfig,
)
from aqos.backtesting.runner import BacktestRunnerConfig, run_backtest_from_csv
from aqos.backtesting.simulator import BacktestIntrabarExitPolicy
from aqos.backtesting.strategy_runner import (
    StrategyBacktestRunnerConfig,
    run_backtest_with_signal_adapter,
)


def add_common_backtest_arguments(
    parser: argparse.ArgumentParser,
) -> None:
    parser.add_argument("--data-path", required=True)
    parser.add_argument("--output-dir", default="tmp/backtesting")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--timeframe", default=None)
    parser.add_argument("--strategy-name", default="csv_signal_strategy")
    parser.add_argument("--timestamp-column", default="timestamp")
    parser.add_argument("--initial-balance", type=float, default=10_000.0)
    parser.add_argument("--risk-fraction", type=float, default=0.01)
    parser.add_argument("--fixed-quantity", type=float, default=1.0)
    parser.add_argument("--spread-points", type=float, default=0.0)
    parser.add_argument("--slippage-points", type=float, default=0.0)
    parser.add_argument("--commission-per-trade", type=float, default=0.0)
    parser.add_argument("--point-value", type=float, default=1.0)
    parser.add_argument("--max-open-positions", type=int, default=1)
    parser.add_argument("--start-timestamp", default=None)
    parser.add_argument("--end-timestamp", default=None)
    parser.add_argument(
        "--intrabar-exit-policy",
        default=BacktestIntrabarExitPolicy.STOP_LOSS_FIRST.value,
        choices=[
            BacktestIntrabarExitPolicy.STOP_LOSS_FIRST.value,
            BacktestIntrabarExitPolicy.TAKE_PROFIT_FIRST.value,
        ],
    )
    parser.add_argument(
        "--no-short",
        action="store_true",
        help="Disable short entries.",
    )
    parser.add_argument(
        "--use-risk-quantity",
        action="store_true",
        help="Use risk_fraction sizing instead of fixed quantity.",
    )


def build_backtesting_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aqos-backtesting",
        description="AQOS backtesting CLI.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    backtest_parser = subparsers.add_parser(
        "backtest",
        help="Run a CSV-signal backtest.",
    )
    add_common_backtest_arguments(backtest_parser)
    backtest_parser.add_argument("--signal-column", default="signal")
    backtest_parser.add_argument("--confidence-column", default="confidence")
    backtest_parser.add_argument("--stop-loss-column", default="stop_loss")
    backtest_parser.add_argument("--take-profit-column", default="take_profit")
    backtest_parser.add_argument(
        "--report-filename",
        default="backtest_report.json",
    )
    backtest_parser.add_argument(
        "--trades-filename",
        default="backtest_trades.csv",
    )
    backtest_parser.add_argument(
        "--equity-curve-filename",
        default="backtest_equity_curve.csv",
    )
    backtest_parser.add_argument(
        "--orders-filename",
        default="backtest_orders.csv",
    )

    strategy_backtest_parser = subparsers.add_parser(
        "strategy-backtest",
        help="Run a built-in rule-strategy backtest.",
    )
    add_common_backtest_arguments(strategy_backtest_parser)
    strategy_backtest_parser.set_defaults(strategy_name="adapter_strategy")
    strategy_backtest_parser.add_argument(
        "--rule-strategy",
        default="close_momentum",
        choices=list_builtin_rule_strategy_names(),
        help="Built-in rule strategy to backtest.",
    )
    strategy_backtest_parser.add_argument("--lookback-bars", type=int, default=1)
    strategy_backtest_parser.add_argument(
        "--min-return-fraction",
        type=float,
        default=0.001,
    )
    strategy_backtest_parser.add_argument(
        "--stop-loss-points",
        type=float,
        default=10.0,
    )
    strategy_backtest_parser.add_argument(
        "--take-profit-points",
        type=float,
        default=20.0,
    )
    strategy_backtest_parser.add_argument("--confidence", type=float, default=0.65)
    strategy_backtest_parser.add_argument(
        "--adapter-name",
        default="rule_based_signal_adapter",
    )
    strategy_backtest_parser.add_argument(
        "--adapter-fail-open",
        action="store_true",
        help="Raise strategy errors instead of converting them into failed hold signals.",
    )
    strategy_backtest_parser.add_argument(
        "--report-filename",
        default="strategy_backtest_report.json",
    )
    strategy_backtest_parser.add_argument(
        "--trades-filename",
        default="strategy_backtest_trades.csv",
    )
    strategy_backtest_parser.add_argument(
        "--equity-curve-filename",
        default="strategy_backtest_equity_curve.csv",
    )
    strategy_backtest_parser.add_argument(
        "--orders-filename",
        default="strategy_backtest_orders.csv",
    )
    strategy_backtest_parser.add_argument(
        "--signals-filename",
        default="strategy_backtest_signals.csv",
    )
    strategy_backtest_parser.add_argument(
        "--adapter-results-filename",
        default="strategy_backtest_adapter_results.json",
    )

    return parser


def build_backtest_runner_config_from_args(
    args: argparse.Namespace,
) -> BacktestRunnerConfig:
    return BacktestRunnerConfig(
        data_path=Path(args.data_path),
        output_dir=Path(args.output_dir),
        symbol=args.symbol,
        timeframe=args.timeframe,
        strategy_name=args.strategy_name,
        signal_column=args.signal_column,
        confidence_column=args.confidence_column,
        stop_loss_column=args.stop_loss_column,
        take_profit_column=args.take_profit_column,
        timestamp_column=args.timestamp_column,
        initial_balance=args.initial_balance,
        risk_fraction=args.risk_fraction,
        fixed_quantity=None if args.use_risk_quantity else args.fixed_quantity,
        spread_points=args.spread_points,
        slippage_points=args.slippage_points,
        commission_per_trade=args.commission_per_trade,
        point_value=args.point_value,
        allow_short=not args.no_short,
        max_open_positions=args.max_open_positions,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
        intrabar_exit_policy=BacktestIntrabarExitPolicy(
            args.intrabar_exit_policy
        ),
        report_filename=args.report_filename,
        trades_filename=args.trades_filename,
        equity_curve_filename=args.equity_curve_filename,
        orders_filename=args.orders_filename,
    )


def build_strategy_backtest_runner_config_from_args(
    args: argparse.Namespace,
) -> StrategyBacktestRunnerConfig:
    return StrategyBacktestRunnerConfig(
        data_path=Path(args.data_path),
        output_dir=Path(args.output_dir),
        symbol=args.symbol,
        timeframe=args.timeframe,
        strategy_name=args.strategy_name,
        timestamp_column=args.timestamp_column,
        initial_balance=args.initial_balance,
        risk_fraction=args.risk_fraction,
        fixed_quantity=None if args.use_risk_quantity else args.fixed_quantity,
        spread_points=args.spread_points,
        slippage_points=args.slippage_points,
        commission_per_trade=args.commission_per_trade,
        point_value=args.point_value,
        allow_short=not args.no_short,
        max_open_positions=args.max_open_positions,
        start_timestamp=args.start_timestamp,
        end_timestamp=args.end_timestamp,
        intrabar_exit_policy=BacktestIntrabarExitPolicy(
            args.intrabar_exit_policy
        ),
        report_filename=args.report_filename,
        trades_filename=args.trades_filename,
        equity_curve_filename=args.equity_curve_filename,
        orders_filename=args.orders_filename,
        signals_filename=args.signals_filename,
        adapter_results_filename=args.adapter_results_filename,
        metadata={"rule_strategy": args.rule_strategy},
    )


def build_rule_based_adapter_from_args(
    args: argparse.Namespace,
) -> RuleBasedBacktestSignalAdapter:
    strategy = build_builtin_rule_strategy(
        args.rule_strategy,
        lookback_bars=args.lookback_bars,
        min_return_fraction=args.min_return_fraction,
        stop_loss_points=args.stop_loss_points,
        take_profit_points=args.take_profit_points,
        confidence=args.confidence,
    )

    return RuleBasedBacktestSignalAdapter(
        strategy=strategy,
        config=RuleBasedSignalAdapterConfig(
            adapter_name=args.adapter_name,
            fail_closed=not args.adapter_fail_open,
            metadata={"rule_strategy": args.rule_strategy},
        ),
    )


def run_backtesting_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_backtesting_cli_parser()
    args = parser.parse_args(argv)

    if args.command == "backtest":
        output = run_backtest_from_csv(build_backtest_runner_config_from_args(args))
        print(json.dumps(output.to_dict(), indent=2, sort_keys=True))
        return 0

    if args.command == "strategy-backtest":
        output = run_backtest_with_signal_adapter(
            config=build_strategy_backtest_runner_config_from_args(args),
            adapter=build_rule_based_adapter_from_args(args),
        )
        print(json.dumps(output.to_dict(), indent=2, sort_keys=True))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def main() -> None:
    raise SystemExit(run_backtesting_cli())


if __name__ == "__main__":
    main()


__all__ = [
    "add_common_backtest_arguments",
    "build_backtest_runner_config_from_args",
    "build_backtesting_cli_parser",
    "build_rule_based_adapter_from_args",
    "build_strategy_backtest_runner_config_from_args",
    "main",
    "run_backtesting_cli",
]