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
from aqos.model_training.dataset_quality import (
    DatasetQualityConfig,
    DatasetQualityReport,
    build_dataset_quality_report,
    write_dataset_quality_report,
)
from aqos.model_training.feature_schema import (
    select_model_feature_columns,
    validate_signal_training_dataset,
)
from aqos.model_training.leakage_guard import raise_if_feature_columns_have_leakage


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
    validate_schema: bool = True
    validate_quality: bool = True
    quality_report_filename: str = "training_dataset_quality.json"
    max_majority_class_ratio: float = 0.8


@dataclass(frozen=True)
class SignalTrainingRunOutput:
    model_path: Path
    metrics_path: Path
    quality_report_path: Path | None
    training_result: SignalModelTrainingResult
    quality_report: DatasetQualityReport | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_path": self.model_path.as_posix(),
            "metrics_path": self.metrics_path.as_posix(),
            "quality_report_path": (
                self.quality_report_path.as_posix()
                if self.quality_report_path is not None
                else None
            ),
            "training_result": self.training_result.to_dict(),
            "quality_report": (
                self.quality_report.to_dict()
                if self.quality_report is not None
                else None
            ),
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


def resolve_training_feature_columns(
    dataset: pd.DataFrame,
    run_config: SignalTrainingRunConfig,
) -> tuple[str, ...] | None:
    if run_config.feature_columns is not None:
        raise_if_feature_columns_have_leakage(run_config.feature_columns)
        return run_config.feature_columns

    if not run_config.validate_schema:
        return None

    feature_columns = select_model_feature_columns(dataset)
    raise_if_feature_columns_have_leakage(feature_columns)

    return feature_columns


def validate_training_dataset_for_run(
    dataset: pd.DataFrame,
    run_config: SignalTrainingRunConfig,
) -> None:
    if not run_config.validate_schema:
        return

    result = validate_signal_training_dataset(dataset)
    result.raise_if_invalid()


def build_training_dataset_quality_report(
    dataset: pd.DataFrame,
    run_config: SignalTrainingRunConfig,
) -> DatasetQualityReport | None:
    if not run_config.validate_quality:
        return None

    report = build_dataset_quality_report(
        dataset,
        config=DatasetQualityConfig(
            target_column=run_config.target_column,
            max_majority_class_ratio=run_config.max_majority_class_ratio,
        ),
    )
    report.raise_if_invalid()

    return report


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
    validate_training_dataset_for_run(dataset, run_config)

    output_dir = Path(run_config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / run_config.model_filename
    metrics_path = output_dir / run_config.metrics_filename
    quality_report_path = output_dir / run_config.quality_report_filename

    quality_report = build_training_dataset_quality_report(dataset, run_config)

    if quality_report is not None:
        write_dataset_quality_report(quality_report_path, quality_report)
    else:
        quality_report_path = None

    model = BaselineSignalModel(
        config=build_signal_model_training_config(run_config)
    )

    result = model.train(
        dataset=dataset,
        feature_columns=resolve_training_feature_columns(dataset, run_config),
    )

    saved_model_path = model.save(model_path)

    output = SignalTrainingRunOutput(
        model_path=saved_model_path,
        metrics_path=metrics_path,
        quality_report_path=quality_report_path,
        training_result=result,
        quality_report=quality_report,
    )

    write_training_metrics(metrics_path, output)

    return output


__all__ = [
    "SignalTrainingRunConfig",
    "SignalTrainingRunOutput",
    "build_signal_model_training_config",
    "build_training_dataset_quality_report",
    "load_signal_training_dataset",
    "resolve_training_feature_columns",
    "train_baseline_signal_model_from_csv",
    "validate_training_dataset_for_run",
    "write_training_metrics",
]