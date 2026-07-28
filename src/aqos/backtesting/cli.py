from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from aqos.backtesting.runner import BacktestRunnerConfig, run_backtest_from_csv
from aqos.backtesting.simulator import BacktestIntrabarExitPolicy


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
    backtest_parser.add_argument("--data-path", required=True)
    backtest_parser.add_argument("--output-dir", default="tmp/backtesting")
    backtest_parser.add_argument("--symbol", default=None)
    backtest_parser.add_argument("--timeframe", default=None)
    backtest_parser.add_argument("--strategy-name", default="csv_signal_strategy")
    backtest_parser.add_argument("--signal-column", default="signal")
    backtest_parser.add_argument("--confidence-column", default="confidence")
    backtest_parser.add_argument("--stop-loss-column", default="stop_loss")
    backtest_parser.add_argument("--take-profit-column", default="take_profit")
    backtest_parser.add_argument("--timestamp-column", default="timestamp")
    backtest_parser.add_argument("--initial-balance", type=float, default=10_000.0)
    backtest_parser.add_argument("--risk-fraction", type=float, default=0.01)
    backtest_parser.add_argument("--fixed-quantity", type=float, default=1.0)
    backtest_parser.add_argument("--spread-points", type=float, default=0.0)
    backtest_parser.add_argument("--slippage-points", type=float, default=0.0)
    backtest_parser.add_argument("--commission-per-trade", type=float, default=0.0)
    backtest_parser.add_argument("--point-value", type=float, default=1.0)
    backtest_parser.add_argument("--max-open-positions", type=int, default=1)
    backtest_parser.add_argument("--start-timestamp", default=None)
    backtest_parser.add_argument("--end-timestamp", default=None)
    backtest_parser.add_argument(
        "--intrabar-exit-policy",
        default=BacktestIntrabarExitPolicy.STOP_LOSS_FIRST.value,
        choices=[
            BacktestIntrabarExitPolicy.STOP_LOSS_FIRST.value,
            BacktestIntrabarExitPolicy.TAKE_PROFIT_FIRST.value,
        ],
    )
    backtest_parser.add_argument(
        "--no-short",
        action="store_true",
        help="Disable short entries.",
    )
    backtest_parser.add_argument(
        "--use-risk-quantity",
        action="store_true",
        help="Use risk_fraction sizing instead of fixed quantity.",
    )
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


def run_backtesting_cli(argv: Sequence[str] | None = None) -> int:
    parser = build_backtesting_cli_parser()
    args = parser.parse_args(argv)

    if args.command == "backtest":
        output = run_backtest_from_csv(build_backtest_runner_config_from_args(args))
        print(json.dumps(output.to_dict(), indent=2, sort_keys=True))
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def main() -> None:
    raise SystemExit(run_backtesting_cli())


if __name__ == "__main__":
    main()


__all__ = [
    "build_backtest_runner_config_from_args",
    "build_backtesting_cli_parser",
    "main",
    "run_backtesting_cli",
]