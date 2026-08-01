from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field, replace
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.backtesting.analytics import (
    BacktestAdvancedReport,
    BacktestPeriodGranularity,
    build_backtest_advanced_report,
    write_backtest_advanced_report,
)
from aqos.backtesting.artifacts import (
    BacktestArtifactKind,
    BacktestArtifactManifest,
    build_backtest_artifact_manifest,
    build_backtest_run_id,
    write_backtest_artifact_manifest,
)
from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestExecutionConfig,
    BacktestExitReason,
    BacktestRunConfig,
)
from aqos.backtesting.data_loader import (
    BacktestDataLoadConfig,
    BacktestDataLoadResult,
    load_backtest_bars_from_csv,
)
from aqos.backtesting.metrics import (
    BacktestEquityCurve,
    BacktestPerformanceMetrics,
    build_backtest_equity_curve,
    build_backtest_equity_point_from_state,
    calculate_backtest_performance_metrics,
)
from aqos.backtesting.runner import (
    write_backtest_equity_curve_csv,
    write_backtest_orders_csv,
    write_backtest_trades_csv,
)
from aqos.backtesting.signal_adapter import (
    BacktestSignalAdapter,
    BacktestSignalAdapterContext,
    BacktestSignalAdapterResult,
)
from aqos.backtesting.simulator import (
    BacktestIntrabarExitPolicy,
    BacktestSimulationState,
    apply_backtest_signal,
    apply_position_lifecycle_on_bar,
    build_initial_backtest_state,
    close_all_backtest_positions,
)


BACKTEST_STRATEGY_RUNNER_VERSION = "1.0"


@dataclass(frozen=True)
class StrategyBacktestRunnerConfig:
    data_path: str | Path
    output_dir: str | Path = "tmp/backtesting"
    symbol: str | None = None
    timeframe: str | None = None
    strategy_name: str = "adapter_strategy"
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
    report_filename: str = "strategy_backtest_report.json"
    trades_filename: str = "strategy_backtest_trades.csv"
    equity_curve_filename: str = "strategy_backtest_equity_curve.csv"
    orders_filename: str = "strategy_backtest_orders.csv"
    signals_filename: str = "strategy_backtest_signals.csv"
    adapter_results_filename: str = "strategy_backtest_adapter_results.json"
    analytics_filename: str = "strategy_backtest_analytics.json"
    manifest_filename: str = "strategy_backtest_manifest.json"
    enable_analytics_report: bool = True
    enable_artifact_manifest: bool = True
    period_granularity: BacktestPeriodGranularity = BacktestPeriodGranularity.MONTHLY
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not str(self.data_path).strip():
            raise ValueError("data_path cannot be empty.")

        if not self.strategy_name.strip():
            raise ValueError("strategy_name cannot be empty.")

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
        return BacktestRunConfig(
            symbol=self.symbol or "unknown",
            timeframe=self.timeframe or "unknown",
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
            "signals_filename": self.signals_filename,
            "adapter_results_filename": self.adapter_results_filename,
            "analytics_filename": self.analytics_filename,
            "manifest_filename": self.manifest_filename,
            "enable_analytics_report": self.enable_analytics_report,
            "enable_artifact_manifest": self.enable_artifact_manifest,
            "period_granularity": self.period_granularity.value,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class StrategyBacktestRunOutput:
    report_path: Path
    trades_path: Path
    equity_curve_path: Path
    orders_path: Path
    signals_path: Path
    adapter_results_path: Path
    config: StrategyBacktestRunnerConfig
    data_load_result: BacktestDataLoadResult
    run_config: BacktestRunConfig
    final_state: BacktestSimulationState
    equity_curve: BacktestEquityCurve
    metrics: BacktestPerformanceMetrics
    adapter_results: tuple[BacktestSignalAdapterResult, ...]
    run_id: str = "strategy_backtest"
    analytics_path: Path | None = None
    manifest_path: Path | None = None
    analytics: BacktestAdvancedReport | None = None
    manifest: BacktestArtifactManifest | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "analytics_path": (
                self.analytics_path.as_posix()
                if self.analytics_path is not None
                else None
            ),
            "manifest_path": (
                self.manifest_path.as_posix()
                if self.manifest_path is not None
                else None
            ),
            "analytics": (
                self.analytics.to_dict() if self.analytics is not None else None
            ),
            "report_path": self.report_path.as_posix(),
            "trades_path": self.trades_path.as_posix(),
            "equity_curve_path": self.equity_curve_path.as_posix(),
            "orders_path": self.orders_path.as_posix(),
            "signals_path": self.signals_path.as_posix(),
            "adapter_results_path": self.adapter_results_path.as_posix(),
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
            "adapter_results": [
                adapter_result.to_dict()
                for adapter_result in self.adapter_results
            ],
        }


def build_strategy_adapter_context(
    bar: BacktestBar,
    history: tuple[BacktestBar, ...],
    index: int,
    config: StrategyBacktestRunnerConfig,
) -> BacktestSignalAdapterContext:
    return BacktestSignalAdapterContext(
        bar=bar,
        history=history,
        index=index,
        metadata={
            "strategy_name": config.strategy_name,
            "bar_index": index,
            **config.metadata,
        },
    )


def write_strategy_backtest_report(
    output: StrategyBacktestRunOutput,
) -> Path:
    output.report_path.parent.mkdir(parents=True, exist_ok=True)
    output.report_path.write_text(
        json.dumps(output.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output.report_path


def write_strategy_backtest_signals_csv(
    path: str | Path,
    adapter_results: tuple[BacktestSignalAdapterResult, ...],
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []

    for adapter_result in adapter_results:
        signal_payload = adapter_result.signal.to_dict()
        rows.append(
            {
                **signal_payload,
                "adapter_status": adapter_result.status.value,
                "adapter_type": adapter_result.adapter_type.value,
                "adapter_name": adapter_result.adapter_name,
                "adapter_reason": adapter_result.reason,
                "generated": adapter_result.generated,
            }
        )

    pd.DataFrame(rows).to_csv(output_path, index=False)

    return output_path


def write_strategy_backtest_adapter_results_json(
    path: str | Path,
    adapter_results: tuple[BacktestSignalAdapterResult, ...],
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            [adapter_result.to_dict() for adapter_result in adapter_results],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return output_path


def run_backtest_with_signal_adapter(
    config: StrategyBacktestRunnerConfig,
    adapter: BacktestSignalAdapter,
) -> StrategyBacktestRunOutput:
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data_load_result = load_backtest_bars_from_csv(config.data_load_config())
    bars = data_load_result.bars

    execution_config = config.execution_config()
    state = build_initial_backtest_state(execution_config)

    history: list[BacktestBar] = []
    adapter_results: list[BacktestSignalAdapterResult] = []
    equity_points = []
    peak_equity = execution_config.initial_balance

    for index, bar in enumerate(bars):
        state = apply_position_lifecycle_on_bar(
            state=state,
            bar=bar,
            execution_config=execution_config,
            intrabar_exit_policy=config.intrabar_exit_policy,
        )

        context = build_strategy_adapter_context(
            bar=bar,
            history=tuple(history),
            index=index,
            config=config,
        )

        adapter_result = adapter.generate_signal(context)
        adapter_results.append(adapter_result)

        state = apply_backtest_signal(
            state=state,
            signal=adapter_result.signal,
            bar=bar,
            execution_config=execution_config,
            order_index=index + 1,
        )

        equity_point = build_backtest_equity_point_from_state(
            state=state,
            bar=bar,
            peak_equity=peak_equity,
            point_value=execution_config.point_value,
        )
        peak_equity = max(peak_equity, equity_point.equity)
        equity_points.append(equity_point)

        history.append(bar)

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
            "adapter_name": adapter.adapter_name,
            "adapter_type": adapter.adapter_type.value,
            "symbol": data_load_result.metadata.get("symbol"),
            "timeframe": data_load_result.metadata.get("timeframe"),
        },
    )

    analytics = (
        build_backtest_advanced_report(
            metrics=metrics,
            trades=state.trades,
            equity_curve=equity_curve,
            period_granularity=config.period_granularity,
            metadata={
                "strategy_name": config.strategy_name,
                "adapter_name": adapter.adapter_name,
                "adapter_type": adapter.adapter_type.value,
            },
        )
        if config.enable_analytics_report
        else None
    )

    output = StrategyBacktestRunOutput(
        report_path=output_dir / config.report_filename,
        trades_path=output_dir / config.trades_filename,
        equity_curve_path=output_dir / config.equity_curve_filename,
        orders_path=output_dir / config.orders_filename,
        signals_path=output_dir / config.signals_filename,
        adapter_results_path=output_dir / config.adapter_results_filename,
        config=config,
        data_load_result=data_load_result,
        run_config=config.run_config(),
        final_state=state,
        equity_curve=equity_curve,
        metrics=metrics,
        adapter_results=tuple(adapter_results),
        run_id=build_backtest_run_id(
            strategy_name=config.strategy_name,
            symbol=config.symbol,
            timeframe=config.timeframe,
        ),
        analytics_path=(
            output_dir / config.analytics_filename if analytics is not None else None
        ),
        manifest_path=(
            output_dir / config.manifest_filename
            if config.enable_artifact_manifest
            else None
        ),
        analytics=analytics,
    )

    write_backtest_trades_csv(output.trades_path, state)
    write_backtest_orders_csv(output.orders_path, state)
    write_backtest_equity_curve_csv(output.equity_curve_path, equity_curve)
    write_strategy_backtest_signals_csv(output.signals_path, output.adapter_results)
    write_strategy_backtest_adapter_results_json(
        output.adapter_results_path,
        output.adapter_results,
    )

    if analytics is not None and output.analytics_path is not None:
        write_backtest_advanced_report(output.analytics_path, analytics)

    write_strategy_backtest_report(output)

    if output.manifest_path is None:
        return output

    manifest = build_strategy_backtest_manifest(output)
    write_backtest_artifact_manifest(output.manifest_path, manifest)

    return replace(output, manifest=manifest)


def build_strategy_backtest_manifest(
    output: StrategyBacktestRunOutput,
) -> BacktestArtifactManifest:
    artifact_paths: dict[BacktestArtifactKind, Path] = {
        BacktestArtifactKind.REPORT: output.report_path,
        BacktestArtifactKind.TRADES: output.trades_path,
        BacktestArtifactKind.ORDERS: output.orders_path,
        BacktestArtifactKind.EQUITY_CURVE: output.equity_curve_path,
        BacktestArtifactKind.SIGNALS: output.signals_path,
        BacktestArtifactKind.ADAPTER_RESULTS: output.adapter_results_path,
    }

    if output.analytics_path is not None:
        artifact_paths[BacktestArtifactKind.ANALYTICS] = output.analytics_path

    return build_backtest_artifact_manifest(
        run_id=output.run_id,
        artifact_paths=artifact_paths,
        metadata={
            "strategy_name": output.config.strategy_name,
            "symbol": output.run_config.symbol,
            "timeframe": output.run_config.timeframe,
            "total_trades": output.metrics.total_trades,
        },
    )


__all__ = [
    "BACKTEST_STRATEGY_RUNNER_VERSION",
    "StrategyBacktestRunnerConfig",
    "StrategyBacktestRunOutput",
    "build_strategy_adapter_context",
    "build_strategy_backtest_manifest",
    "run_backtest_with_signal_adapter",
    "write_strategy_backtest_adapter_results_json",
    "write_strategy_backtest_report",
    "write_strategy_backtest_signals_csv",
]