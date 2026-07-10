from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.model_training.dataset_quality import (
    DatasetQualityReport,
    build_dataset_quality_report,
    write_dataset_quality_report,
)
from aqos.model_training.dataset_versioning import (
    DatasetArtifactType,
    DatasetVersionMetadata,
    build_dataset_version_metadata,
    write_dataset_version_metadata,
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
    version_metadata_filename: str = "signal_ml_dataset_version.json"
    dataset_name: str = "signal_ml_training_dataset"
    dataset_description: str = "AQOS leakage-safe ML signal training dataset."
    dataset_tags: tuple[str, ...] = ("aqos", "ml-training", "signal-dataset")

    def __post_init__(self) -> None:
        if not self.metadata_filename.strip():
            raise ValueError("metadata_filename cannot be empty.")

        if not self.quality_report_filename.strip():
            raise ValueError("quality_report_filename cannot be empty.")

        if not self.version_metadata_filename.strip():
            raise ValueError("version_metadata_filename cannot be empty.")

        if not self.dataset_name.strip():
            raise ValueError("dataset_name cannot be empty.")


@dataclass(frozen=True)
class SignalMLDatasetBuildOutput:
    dataset_path: Path
    metadata_path: Path
    quality_report_path: Path
    version_metadata_path: Path
    rows: int
    columns: tuple[str, ...]
    feature_columns: tuple[str, ...]
    target_column: str | None
    validation: DatasetValidationResult
    quality_report: DatasetQualityReport
    version_metadata: DatasetVersionMetadata

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_path": self.dataset_path.as_posix(),
            "metadata_path": self.metadata_path.as_posix(),
            "quality_report_path": self.quality_report_path.as_posix(),
            "version_metadata_path": self.version_metadata_path.as_posix(),
            "rows": self.rows,
            "columns": list(self.columns),
            "feature_columns": list(self.feature_columns),
            "target_column": self.target_column,
            "validation": self.validation.to_dict(),
            "quality_report": self.quality_report.to_dict(),
            "version_metadata": self.version_metadata.to_dict(),
        }


def build_signal_dataset_version_parameters(
    config: SignalMLDatasetBuildConfig,
) -> dict[str, Any]:
    return {
        "label_config": asdict(config.label_config),
        "feature_config": asdict(config.feature_config),
        "validate_schema": config.validate_schema,
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
    version_metadata_path = dataset_path.parent / active_config.version_metadata_filename

    quality_report = build_dataset_quality_report(training_dataset)

    version_metadata = build_dataset_version_metadata(
        dataframe=training_dataset,
        dataset_name=active_config.dataset_name,
        dataset_path=dataset_path,
        artifact_type=DatasetArtifactType.TRAINING_DATASET,
        source_file_path=input_path,
        quality_report_path=quality_report_path,
        description=active_config.dataset_description,
        tags=active_config.dataset_tags,
        parameters=build_signal_dataset_version_parameters(active_config),
    )

    output = SignalMLDatasetBuildOutput(
        dataset_path=dataset_path,
        metadata_path=metadata_path,
        quality_report_path=quality_report_path,
        version_metadata_path=version_metadata_path,
        rows=len(training_dataset),
        columns=tuple(str(column) for column in training_dataset.columns),
        feature_columns=feature_columns,
        target_column=validation.target_column,
        validation=validation,
        quality_report=quality_report,
        version_metadata=version_metadata,
    )

    write_dataset_quality_report(quality_report_path, quality_report)
    write_dataset_version_metadata(version_metadata_path, version_metadata)
    write_signal_ml_dataset_metadata(metadata_path, output)

    return output


__all__ = [
    "SignalMLDatasetBuildConfig",
    "SignalMLDatasetBuildOutput",
    "build_signal_dataset_version_parameters",
    "build_signal_ml_training_dataset",
    "build_signal_ml_training_dataset_from_csv",
    "validate_signal_ml_training_dataset",
    "write_signal_ml_dataset_metadata",
]