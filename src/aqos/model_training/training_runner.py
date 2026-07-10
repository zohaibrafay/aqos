from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from aqos.model_training.baseline_signal_model import (
    BaselineSignalModel,
    SignalModelTrainingConfig,
    SignalModelTrainingResult,
)


@dataclass(frozen=True)
class SignalTrainingRunConfig:
    dataset_path: str | Path
    output_dir: str | Path = "tmp/model_training"
    target_column: str = "target"
    feature_columns: tuple[str, ...] | None = None
    test_size: float = 0.25
    random_state: int = 42
    n_estimators: int = 100
    max_depth: int | None = 6
    min_samples_leaf: int = 1
    model_filename: str = "baseline_signal_model.joblib"
    metrics_filename: str = "baseline_signal_model_metrics.json"


@dataclass(frozen=True)
class SignalTrainingRunOutput:
    model_path: Path
    metrics_path: Path
    training_result: SignalModelTrainingResult

    def to_dict(self) -> dict[str, object]:
        return {
            "model_path": self.model_path.as_posix(),
            "metrics_path": self.metrics_path.as_posix(),
            "training_result": self.training_result.to_dict(),
        }


def load_signal_training_dataset(dataset_path: str | Path) -> pd.DataFrame:
    path = Path(dataset_path)

    if not path.exists():
        raise FileNotFoundError(f"Training dataset does not exist: {path}")

    if path.suffix.lower() != ".csv":
        raise ValueError("Signal training dataset must be a CSV file.")

    dataset = pd.read_csv(path)

    if dataset.empty:
        raise ValueError("Signal training dataset CSV is empty.")

    return dataset


def build_signal_model_training_config(
    run_config: SignalTrainingRunConfig,
) -> SignalModelTrainingConfig:
    return SignalModelTrainingConfig(
        target_column=run_config.target_column,
        test_size=run_config.test_size,
        random_state=run_config.random_state,
        n_estimators=run_config.n_estimators,
        max_depth=run_config.max_depth,
        min_samples_leaf=run_config.min_samples_leaf,
    )


def write_training_metrics(
    path: str | Path,
    output: SignalTrainingRunOutput,
) -> Path:
    metrics_path = Path(path)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_path.write_text(
        json.dumps(output.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return metrics_path


def train_baseline_signal_model_from_csv(
    run_config: SignalTrainingRunConfig,
) -> SignalTrainingRunOutput:
    dataset = load_signal_training_dataset(run_config.dataset_path)

    output_dir = Path(run_config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / run_config.model_filename
    metrics_path = output_dir / run_config.metrics_filename

    model = BaselineSignalModel(
        config=build_signal_model_training_config(run_config)
    )

    result = model.train(
        dataset=dataset,
        feature_columns=run_config.feature_columns,
    )

    saved_model_path = model.save(model_path)

    output = SignalTrainingRunOutput(
        model_path=saved_model_path,
        metrics_path=metrics_path,
        training_result=result,
    )

    write_training_metrics(metrics_path, output)

    return output


__all__ = [
    "SignalTrainingRunConfig",
    "SignalTrainingRunOutput",
    "build_signal_model_training_config",
    "load_signal_training_dataset",
    "train_baseline_signal_model_from_csv",
    "write_training_metrics",
]