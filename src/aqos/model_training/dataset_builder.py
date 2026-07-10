from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.model_training.dataset_quality import (
    DatasetQualityReport,
    build_dataset_quality_report,
    write_dataset_quality_report,
)
from aqos.model_training.feature_schema import (
    DatasetValidationResult,
    select_model_feature_columns,
    validate_signal_training_dataset,
)
from aqos.model_training.leakage_guard import raise_if_feature_columns_have_leakage
from aqos.model_training.ohlcv_feature_builder import (
    OHLCVFeatureBuilderConfig,
    build_ohlcv_ml_features,
    load_ohlcv_csv,
)
from aqos.model_training.target_label_builder import (
    SignalTargetLabelConfig,
    build_signal_target_labels,
)


@dataclass(frozen=True)
class SignalMLDatasetBuildConfig:
    label_config: SignalTargetLabelConfig = field(default_factory=SignalTargetLabelConfig)
    feature_config: OHLCVFeatureBuilderConfig = field(default_factory=OHLCVFeatureBuilderConfig)
    validate_schema: bool = True
    metadata_filename: str = "signal_ml_dataset_metadata.json"
    quality_report_filename: str = "signal_ml_dataset_quality.json"

    def __post_init__(self) -> None:
        if not self.metadata_filename.strip():
            raise ValueError("metadata_filename cannot be empty.")

        if not self.quality_report_filename.strip():
            raise ValueError("quality_report_filename cannot be empty.")


@dataclass(frozen=True)
class SignalMLDatasetBuildOutput:
    dataset_path: Path
    metadata_path: Path
    quality_report_path: Path
    rows: int
    columns: tuple[str, ...]
    feature_columns: tuple[str, ...]
    target_column: str | None
    validation: DatasetValidationResult
    quality_report: DatasetQualityReport

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_path": self.dataset_path.as_posix(),
            "metadata_path": self.metadata_path.as_posix(),
            "quality_report_path": self.quality_report_path.as_posix(),
            "rows": self.rows,
            "columns": list(self.columns),
            "feature_columns": list(self.feature_columns),
            "target_column": self.target_column,
            "validation": self.validation.to_dict(),
            "quality_report": self.quality_report.to_dict(),
        }


def build_signal_ml_training_dataset(
    dataframe: pd.DataFrame,
    config: SignalMLDatasetBuildConfig | None = None,
) -> pd.DataFrame:
    active_config = config or SignalMLDatasetBuildConfig()

    labeled = build_signal_target_labels(
        dataframe,
        config=active_config.label_config,
    )

    features = build_ohlcv_ml_features(
        labeled,
        config=active_config.feature_config,
    )

    if active_config.validate_schema:
        validation = validate_signal_training_dataset(features)
        validation.raise_if_invalid()

        feature_columns = select_model_feature_columns(features)
        raise_if_feature_columns_have_leakage(feature_columns)

    return features


def validate_signal_ml_training_dataset(
    dataframe: pd.DataFrame,
) -> DatasetValidationResult:
    validation = validate_signal_training_dataset(dataframe)
    validation.raise_if_invalid()

    feature_columns = select_model_feature_columns(dataframe)
    raise_if_feature_columns_have_leakage(feature_columns)

    return validation


def write_signal_ml_dataset_metadata(
    path: str | Path,
    output: SignalMLDatasetBuildOutput,
) -> Path:
    metadata_path = Path(path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(
        json.dumps(output.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return metadata_path


def build_signal_ml_training_dataset_from_csv(
    input_path: str | Path,
    output_path: str | Path,
    config: SignalMLDatasetBuildConfig | None = None,
) -> SignalMLDatasetBuildOutput:
    active_config = config or SignalMLDatasetBuildConfig()

    raw_dataset = load_ohlcv_csv(input_path)
    training_dataset = build_signal_ml_training_dataset(
        raw_dataset,
        config=active_config,
    )

    dataset_path = Path(output_path)
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    training_dataset.to_csv(dataset_path, index=False)

    validation = validate_signal_ml_training_dataset(training_dataset)
    feature_columns = select_model_feature_columns(training_dataset)

    metadata_path = dataset_path.parent / active_config.metadata_filename
    quality_report_path = dataset_path.parent / active_config.quality_report_filename
    quality_report = build_dataset_quality_report(training_dataset)

    output = SignalMLDatasetBuildOutput(
        dataset_path=dataset_path,
        metadata_path=metadata_path,
        quality_report_path=quality_report_path,
        rows=len(training_dataset),
        columns=tuple(str(column) for column in training_dataset.columns),
        feature_columns=feature_columns,
        target_column=validation.target_column,
        validation=validation,
        quality_report=quality_report,
    )

    write_dataset_quality_report(quality_report_path, quality_report)
    write_signal_ml_dataset_metadata(metadata_path, output)

    return output


__all__ = [
    "SignalMLDatasetBuildConfig",
    "SignalMLDatasetBuildOutput",
    "build_signal_ml_training_dataset",
    "build_signal_ml_training_dataset_from_csv",
    "validate_signal_ml_training_dataset",
    "write_signal_ml_dataset_metadata",
]