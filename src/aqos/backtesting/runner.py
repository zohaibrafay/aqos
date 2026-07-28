from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestExecutionConfig,
    BacktestExitReason,
    BacktestRunConfig,
    BacktestSignal,
    BacktestSignalAction,
)
from aqos.backtesting.data_loader import (
    BacktestDataLoadConfig,
    BacktestDataLoadResult,
    load_backtest_bars_from_csv,
    read_backtest_csv_dataframe,
)
from aqos.backtesting.metrics import (
    BacktestEquityCurve,
    BacktestPerformanceMetrics,
    build_backtest_equity_curve,
    build_backtest_equity_point_from_state,
    calculate_backtest_performance_metrics,
)
from aqos.backtesting.simulator import (
    BacktestIntrabarExitPolicy,
    BacktestSimulationState,
    apply_backtest_signal,
    apply_position_lifecycle_on_bar,
    build_initial_backtest_state,
    close_all_backtest_positions,
)


BACKTEST_RUNNER_VERSION = "1.0"


@dataclass(frozen=True)
class BacktestRunnerConfig:
    data_path: str | Path
    output_dir: str | Path = "tmp/backtesting"
    symbol: str | None = None
    timeframe: str | None = None
    strategy_name: str = "csv_signal_strategy"
    signal_column: str = "signal"
    confidence_column: str | None = "confidence"
    stop_loss_column: str | None = "stop_loss"
    take_profit_column: str | None = "take_profit"
    timestamp_column: str = "timestamp"
    initial_balance: float = 10_000.0
    risk_fraction: float = 0.01
    fixed_quantity: float | None = 1.0
    spread_points: float = 0.0
    slippage_points: float = 0.0
    commission_per_trade: float = 0.0
    point_value: float = 1.0
    allow_short: bool = True
    max_open_positions: int = 1
    start_timestamp: str | None = None
    end_timestamp: str | None = None
    intrabar_exit_policy: BacktestIntrabarExitPolicy = (
        BacktestIntrabarExitPolicy.STOP_LOSS_FIRST
    )
    report_filename: str = "backtest_report.json"
    trades_filename: str = "backtest_trades.csv"
    equity_curve_filename: str = "backtest_equity_curve.csv"
    orders_filename: str = "backtest_orders.csv"
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.data_path).strip():
            raise ValueError("data_path cannot be empty.")

        if not self.strategy_name.strip():
            raise ValueError("strategy_name cannot be empty.")

        if not self.signal_column.strip():
            raise ValueError("signal_column cannot be empty.")

        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive.")

        if not 0.0 < self.risk_fraction <= 1.0:
            raise ValueError("risk_fraction must be greater than 0 and <= 1.")

        if self.fixed_quantity is not None and self.fixed_quantity <= 0:
            raise ValueError("fixed_quantity must be positive.")

    def execution_config(self) -> BacktestExecutionConfig:
        return BacktestExecutionConfig(
            initial_balance=self.initial_balance,
            risk_fraction=self.risk_fraction,
            fixed_quantity=self.fixed_quantity,
            spread_points=self.spread_points,
            slippage_points=self.slippage_points,
            commission_per_trade=self.commission_per_trade,
            point_value=self.point_value,
            allow_short=self.allow_short,
            max_open_positions=self.max_open_positions,
        )

    def data_load_config(self) -> BacktestDataLoadConfig:
        return BacktestDataLoadConfig(
            csv_path=Path(self.data_path),
            symbol=self.symbol,
            timeframe=self.timeframe,
            timestamp_column=self.timestamp_column,
            start_timestamp=self.start_timestamp,
            end_timestamp=self.end_timestamp,
        )

    def run_config(self) -> BacktestRunConfig:
        loaded_symbol = self.symbol or "unknown"
        loaded_timeframe = self.timeframe or "unknown"

        return BacktestRunConfig(
            symbol=loaded_symbol,
            timeframe=loaded_timeframe,
            strategy_name=self.strategy_name,
            execution=self.execution_config(),
            start_timestamp=self.start_timestamp,
            end_timestamp=self.end_timestamp,
            metadata=self.metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "data_path": Path(self.data_path).as_posix(),
            "output_dir": Path(self.output_dir).as_posix(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "strategy_name": self.strategy_name,
            "signal_column": self.signal_column,
            "confidence_column": self.confidence_column,
            "stop_loss_column": self.stop_loss_column,
            "take_profit_column": self.take_profit_column,
            "timestamp_column": self.timestamp_column,
            "initial_balance": self.initial_balance,
            "risk_fraction": self.risk_fraction,
            "fixed_quantity": self.fixed_quantity,
            "spread_points": self.spread_points,
            "slippage_points": self.slippage_points,
            "commission_per_trade": self.commission_per_trade,
            "point_value": self.point_value,
            "allow_short": self.allow_short,
            "max_open_positions": self.max_open_positions,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "intrabar_exit_policy": self.intrabar_exit_policy.value,
            "report_filename": self.report_filename,
            "trades_filename": self.trades_filename,
            "equity_curve_filename": self.equity_curve_filename,
            "orders_filename": self.orders_filename,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestRunOutput:
    report_path: Path
    trades_path: Path
    equity_curve_path: Path
    orders_path: Path
    config: BacktestRunnerConfig
    data_load_result: BacktestDataLoadResult
    run_config: BacktestRunConfig
    final_state: BacktestSimulationState
    equity_curve: BacktestEquityCurve
    metrics: BacktestPerformanceMetrics

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_path": self.report_path.as_posix(),
            "trades_path": self.trades_path.as_posix(),
            "equity_curve_path": self.equity_curve_path.as_posix(),
            "orders_path": self.orders_path.as_posix(),
            "config": self.config.to_dict(),
            "data_load": {
                "source_rows": self.data_load_result.source_rows,
                "loaded_rows": self.data_load_result.loaded_rows,
                "metadata": self.data_load_result.metadata,
            },
            "run_config": self.run_config.to_dict(),
            "final_state": self.final_state.to_dict(),
            "equity_curve": self.equity_curve.to_dict(),
            "metrics": self.metrics.to_dict(),
        }


def parse_backtest_signal_action(value: Any) -> BacktestSignalAction:
    if value is None or pd.isna(value):
        return BacktestSignalAction.HOLD

    clean_value = str(value).strip().lower()

    if clean_value in {"", "none", "nan"}:
        return BacktestSignalAction.HOLD

    aliases = {
        "long": BacktestSignalAction.BUY,
        "buy": BacktestSignalAction.BUY,
        "bullish": BacktestSignalAction.BUY,
        "short": BacktestSignalAction.SELL,
        "sell": BacktestSignalAction.SELL,
        "bearish": BacktestSignalAction.SELL,
        "flat": BacktestSignalAction.HOLD,
        "hold": BacktestSignalAction.HOLD,
        "neutral": BacktestSignalAction.HOLD,
        "exit": BacktestSignalAction.EXIT,
        "close": BacktestSignalAction.EXIT,
    }

    if clean_value not in aliases:
        raise ValueError(f"Unsupported backtest signal action: {value}")

    return aliases[clean_value]


def optional_float_from_row(
    row: pd.Series,
    column: str | None,
) -> float | None:
    if column is None or column not in row.index:
        return None

    value = row[column]

    if value is None or pd.isna(value):
        return None

    return float(value)


def build_backtest_signals_from_dataframe(
    dataframe: pd.DataFrame,
    config: BacktestRunnerConfig,
) -> tuple[BacktestSignal, ...]:
    if config.signal_column not in dataframe.columns:
        raise ValueError(f"Signal column is missing: {config.signal_column}")

    signals: list[BacktestSignal] = []

    for _, row in dataframe.iterrows():
        symbol = config.symbol if config.symbol is not None else str(row.get("symbol", "unknown"))

        signals.append(
            BacktestSignal(
                timestamp=str(row[config.timestamp_column]),
                symbol=symbol,
                action=parse_backtest_signal_action(row[config.signal_column]),
                confidence=optional_float_from_row(row, config.confidence_column),
                source=config.strategy_name,
                stop_loss=optional_float_from_row(row, config.stop_loss_column),
                take_profit=optional_float_from_row(row, config.take_profit_column),
            )
        )

    return tuple(signals)


def align_signals_to_bars(
    bars: tuple[BacktestBar, ...],
    signals: tuple[BacktestSignal, ...],
) -> dict[str, BacktestSignal]:
    signal_by_timestamp = {signal.timestamp: signal for signal in signals}

    return {
        bar.timestamp: signal_by_timestamp.get(
            bar.timestamp,
            BacktestSignal(
                timestamp=bar.timestamp,
                symbol=bar.symbol,
                action=BacktestSignalAction.HOLD,
                source="missing_signal_default_hold",
            ),
        )
        for bar in bars
    }


def write_backtest_report(
    output: BacktestRunOutput,
) -> Path:
    output.report_path.parent.mkdir(parents=True, exist_ok=True)
    output.report_path.write_text(
        json.dumps(output.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output.report_path


def write_backtest_trades_csv(
    path: str | Path,
    state: BacktestSimulationState,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([trade.to_dict() for trade in state.trades]).to_csv(
        output_path,
        index=False,
    )

    return output_path


def write_backtest_orders_csv(
    path: str | Path,
    state: BacktestSimulationState,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([order.to_dict() for order in state.orders]).to_csv(
        output_path,
        index=False,
    )

    return output_path


def write_backtest_equity_curve_csv(
    path: str | Path,
    equity_curve: BacktestEquityCurve,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame([point.to_dict() for point in equity_curve.points]).to_csv(
        output_path,
        index=False,
    )

    return output_path


def run_backtest_from_csv(
    config: BacktestRunnerConfig,
) -> BacktestRunOutput:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data_load_result = load_backtest_bars_from_csv(config.data_load_config())
    bars = data_load_result.bars

    source_dataframe = read_backtest_csv_dataframe(config.data_path)
    source_dataframe = source_dataframe[
        source_dataframe[config.timestamp_column].astype(str).isin(
            {bar.timestamp for bar in bars}
        )
    ].copy()

    signals = build_backtest_signals_from_dataframe(source_dataframe, config)
    signal_by_timestamp = align_signals_to_bars(bars, signals)

    execution_config = config.execution_config()
    state = build_initial_backtest_state(execution_config)

    equity_points = []
    peak_equity = execution_config.initial_balance

    for index, bar in enumerate(bars, start=1):
        state = apply_position_lifecycle_on_bar(
            state=state,
            bar=bar,
            execution_config=execution_config,
            intrabar_exit_policy=config.intrabar_exit_policy,
        )

        signal = signal_by_timestamp[bar.timestamp]
        state = apply_backtest_signal(
            state=state,
            signal=signal,
            bar=bar,
            execution_config=execution_config,
            order_index=index,
        )

        equity_point = build_backtest_equity_point_from_state(
            state=state,
            bar=bar,
            peak_equity=peak_equity,
            point_value=execution_config.point_value,
        )
        peak_equity = max(peak_equity, equity_point.equity)
        equity_points.append(equity_point)

    if bars and state.open_positions:
        state = close_all_backtest_positions(
            state=state,
            bar=bars[-1],
            execution_config=execution_config,
            exit_reason=BacktestExitReason.END_OF_DATA,
        )

        final_equity_point = build_backtest_equity_point_from_state(
            state=state,
            bar=bars[-1],
            peak_equity=peak_equity,
            point_value=execution_config.point_value,
        )
        equity_points.append(final_equity_point)

    equity_curve = build_backtest_equity_curve(
        points=tuple(equity_points),
        initial_balance=execution_config.initial_balance,
    )

    metrics = calculate_backtest_performance_metrics(
        initial_balance=execution_config.initial_balance,
        final_balance=state.balance,
        trades=state.trades,
        equity_curve=equity_curve,
        metadata={
            "strategy_name": config.strategy_name,
            "symbol": data_load_result.metadata.get("symbol"),
            "timeframe": data_load_result.metadata.get("timeframe"),
        },
    )

    output = BacktestRunOutput(
        report_path=output_dir / config.report_filename,
        trades_path=output_dir / config.trades_filename,
        equity_curve_path=output_dir / config.equity_curve_filename,
        orders_path=output_dir / config.orders_filename,
        config=config,
        data_load_result=data_load_result,
        run_config=config.run_config(),
        final_state=state,
        equity_curve=equity_curve,
        metrics=metrics,
    )

    write_backtest_trades_csv(output.trades_path, state)
    write_backtest_orders_csv(output.orders_path, state)
    write_backtest_equity_curve_csv(output.equity_curve_path, equity_curve)
    write_backtest_report(output)

    return output


__all__ = [
    "BACKTEST_RUNNER_VERSION",
    "BacktestRunOutput",
    "BacktestRunnerConfig",
    "align_signals_to_bars",
    "build_backtest_signals_from_dataframe",
    "optional_float_from_row",
    "parse_backtest_signal_action",
    "run_backtest_from_csv",
    "write_backtest_equity_curve_csv",
    "write_backtest_orders_csv",
    "write_backtest_report",
    "write_backtest_trades_csv",
]