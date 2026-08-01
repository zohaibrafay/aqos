from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field, replace
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.backtesting.artifacts import (
    BacktestArtifactKind,
    BacktestArtifactManifest,
    build_backtest_artifact_manifest,
    write_backtest_artifact_manifest,
)
from aqos.backtesting.model_promotion_guard import (
    BacktestModelGateConfig,
    BacktestModelGateDecision,
    evaluate_backtest_model_gate,
)
from aqos.backtesting.model_signal_adapter import (
    ModelBacktestSignalAdapter,
    ModelSignalAdapterConfig,
    load_model_backtest_signal_adapter,
)
from aqos.backtesting.registry import register_backtest_report
from aqos.backtesting.signal_adapter import BacktestSignalAdapterResult
from aqos.backtesting.strategy_runner import (
    StrategyBacktestRunnerConfig,
    StrategyBacktestRunOutput,
    run_backtest_with_signal_adapter,
)


BACKTEST_MODEL_RUNNER_VERSION = "1.0"


@dataclass(frozen=True)
class ModelBacktestRunnerConfig:
    model_path: str | Path
    strategy_config: StrategyBacktestRunnerConfig
    gate_config: BacktestModelGateConfig = dataclass_field(
        default_factory=lambda: BacktestModelGateConfig(
            enabled=False,
            allow_unpromoted_model=True,
        )
    )
    adapter_config: ModelSignalAdapterConfig = dataclass_field(
        default_factory=ModelSignalAdapterConfig
    )
    model_report_filename: str = "model_backtest_report.json"
    predictions_filename: str = "model_backtest_predictions.csv"
    manifest_filename: str = "model_backtest_manifest.json"
    result_registry_path: str | Path | None = None
    enable_artifact_manifest: bool = True

    def __post_init__(self) -> None:
        if not str(self.model_path).strip():
            raise ValueError("model_path cannot be empty.")

        if not self.model_report_filename.strip():
            raise ValueError("model_report_filename cannot be empty.")

        if not self.predictions_filename.strip():
            raise ValueError("predictions_filename cannot be empty.")

    @property
    def output_dir(self) -> Path:
        return Path(self.strategy_config.output_dir)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_path": Path(self.model_path).as_posix(),
            "strategy_config": self.strategy_config.to_dict(),
            "gate_config": self.gate_config.to_dict(),
            "adapter_config": self.adapter_config.to_dict(),
            "model_report_filename": self.model_report_filename,
            "predictions_filename": self.predictions_filename,
            "manifest_filename": self.manifest_filename,
            "enable_artifact_manifest": self.enable_artifact_manifest,
            "result_registry_path": (
                Path(self.result_registry_path).as_posix()
                if self.result_registry_path is not None
                else None
            ),
        }


@dataclass(frozen=True)
class ModelBacktestRunOutput:
    model_report_path: Path
    predictions_path: Path
    config: ModelBacktestRunnerConfig
    gate_decision: BacktestModelGateDecision
    strategy_output: StrategyBacktestRunOutput
    manifest_path: Path | None = None
    manifest: BacktestArtifactManifest | None = None

    @property
    def prediction_rows(self) -> int:
        return len(self.strategy_output.adapter_results)

    @property
    def run_id(self) -> str:
        return self.strategy_output.run_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_report_path": self.model_report_path.as_posix(),
            "predictions_path": self.predictions_path.as_posix(),
            "manifest_path": (
                self.manifest_path.as_posix()
                if self.manifest_path is not None
                else None
            ),
            "run_id": self.run_id,
            "prediction_rows": self.prediction_rows,
            "config": self.config.to_dict(),
            "gate_decision": self.gate_decision.to_dict(),
            "model_identity": self.gate_decision.model_identity(),
            "strategy_backtest": self.strategy_output.to_dict(),
        }


def build_model_prediction_rows(
    adapter_results: tuple[BacktestSignalAdapterResult, ...],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for index, adapter_result in enumerate(adapter_results):
        signal = adapter_result.signal
        metadata = signal.metadata
        probabilities = metadata.get("probabilities", {})

        row: dict[str, Any] = {
            "bar_index": index,
            "timestamp": signal.timestamp,
            "symbol": signal.symbol,
            "predicted_label": metadata.get("predicted_label"),
            "action": signal.action.value,
            "confidence": signal.confidence,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "adapter_status": adapter_result.status.value,
            "adapter_reason": adapter_result.reason,
            "model_id": metadata.get("model_id"),
            "model_version": metadata.get("model_version"),
            "promotion_stage": metadata.get("promotion_stage"),
        }

        if isinstance(probabilities, dict):
            for column, value in probabilities.items():
                row[str(column)] = value

        rows.append(row)

    return rows


def write_model_backtest_predictions_csv(
    path: str | Path,
    adapter_results: tuple[BacktestSignalAdapterResult, ...],
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(build_model_prediction_rows(adapter_results)).to_csv(
        output_path,
        index=False,
    )

    return output_path


def write_model_backtest_report(output: ModelBacktestRunOutput) -> Path:
    output.model_report_path.parent.mkdir(parents=True, exist_ok=True)
    output.model_report_path.write_text(
        json.dumps(output.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output.model_report_path


def build_traced_model_adapter_config(
    adapter_config: ModelSignalAdapterConfig,
    gate_decision: BacktestModelGateDecision,
) -> ModelSignalAdapterConfig:
    """
    Merge model identity from the gate decision into the adapter config so every
    generated signal carries model traceability.
    """

    return replace(
        adapter_config,
        model_identity={
            **gate_decision.model_identity(),
            **adapter_config.model_identity,
        },
    )


def build_model_backtest_adapter(
    config: ModelBacktestRunnerConfig,
    gate_decision: BacktestModelGateDecision,
) -> ModelBacktestSignalAdapter:
    return load_model_backtest_signal_adapter(
        model_path=config.model_path,
        config=build_traced_model_adapter_config(
            adapter_config=config.adapter_config,
            gate_decision=gate_decision,
        ),
    )


def run_model_backtest(
    config: ModelBacktestRunnerConfig,
) -> ModelBacktestRunOutput:
    gate_decision = evaluate_backtest_model_gate(config.gate_config)
    gate_decision.raise_if_blocked()

    adapter = build_model_backtest_adapter(config, gate_decision)

    strategy_output = run_backtest_with_signal_adapter(
        config=config.strategy_config,
        adapter=adapter,
    )

    output_dir = config.output_dir

    output = ModelBacktestRunOutput(
        model_report_path=output_dir / config.model_report_filename,
        predictions_path=output_dir / config.predictions_filename,
        config=config,
        gate_decision=gate_decision,
        strategy_output=strategy_output,
        manifest_path=(
            output_dir / config.manifest_filename
            if config.enable_artifact_manifest
            else None
        ),
    )

    write_model_backtest_predictions_csv(
        output.predictions_path,
        strategy_output.adapter_results,
    )
    write_model_backtest_report(output)

    if output.manifest_path is not None:
        manifest = build_model_backtest_manifest(output)
        write_backtest_artifact_manifest(output.manifest_path, manifest)
        output = replace(output, manifest=manifest)

    if config.result_registry_path is not None:
        register_backtest_report(
            registry_path=config.result_registry_path,
            report_path=output.model_report_path,
        )

    return output


def build_model_backtest_manifest(
    output: ModelBacktestRunOutput,
) -> BacktestArtifactManifest:
    strategy_output = output.strategy_output

    artifact_paths: dict[BacktestArtifactKind, Path] = {
        BacktestArtifactKind.REPORT: output.model_report_path,
        BacktestArtifactKind.PREDICTIONS: output.predictions_path,
        BacktestArtifactKind.TRADES: strategy_output.trades_path,
        BacktestArtifactKind.ORDERS: strategy_output.orders_path,
        BacktestArtifactKind.EQUITY_CURVE: strategy_output.equity_curve_path,
        BacktestArtifactKind.SIGNALS: strategy_output.signals_path,
        BacktestArtifactKind.ADAPTER_RESULTS: strategy_output.adapter_results_path,
    }

    if strategy_output.analytics_path is not None:
        artifact_paths[BacktestArtifactKind.ANALYTICS] = (
            strategy_output.analytics_path
        )

    return build_backtest_artifact_manifest(
        run_id=output.run_id,
        artifact_paths=artifact_paths,
        metadata={
            **output.gate_decision.model_identity(),
            "strategy_name": strategy_output.config.strategy_name,
            "prediction_rows": output.prediction_rows,
        },
    )


__all__ = [
    "BACKTEST_MODEL_RUNNER_VERSION",
    "ModelBacktestRunOutput",
    "ModelBacktestRunnerConfig",
    "build_model_backtest_adapter",
    "build_model_backtest_manifest",
    "build_model_prediction_rows",
    "build_traced_model_adapter_config",
    "run_model_backtest",
    "write_model_backtest_predictions_csv",
    "write_model_backtest_report",
]
