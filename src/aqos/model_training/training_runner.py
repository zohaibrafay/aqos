from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.model_training.model_evaluation import (
    ModelEvaluationReport,
    ModelEvaluationThresholds,
    ModelPromotionStage,
    build_model_evaluation_report,
    write_model_evaluation_report,
)

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
from aqos.model_training.dataset_versioning import read_dataset_version_metadata
from aqos.model_training.experiment_registry import (
    ExperimentArtifact,
    ExperimentArtifactType,
    ExperimentRunMetadata,
    append_experiment_run_to_registry,
    build_experiment_artifact,
    build_experiment_run_metadata,
    write_experiment_run_metadata,
)
from aqos.model_training.feature_schema import (
    select_model_feature_columns,
    validate_signal_training_dataset,
)
from aqos.model_training.leakage_guard import raise_if_feature_columns_have_leakage
from aqos.model_training.model_versioning import (
    ModelVersionMetadata,
    build_model_version_metadata,
    write_model_version_metadata,
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
    validate_schema: bool = True
    validate_quality: bool = True
    quality_report_filename: str = "training_dataset_quality.json"
    max_majority_class_ratio: float = 0.8
    enable_experiment_registry: bool = True
    experiment_name: str = "aqos_baseline_signal_model"
    experiment_tags: tuple[str, ...] = (
        "aqos",
        "model-training",
        "baseline-signal-model",
    )
    experiment_notes: str | None = None
    experiment_run_metadata_filename: str = "experiment_run_metadata.json"
    experiment_registry_filename: str = "experiment_registry.json"
    dataset_version_metadata_path: str | Path | None = None
    enable_model_versioning: bool = True
    model_version_metadata_filename: str = "model_version_metadata.json"
    model_version_description: str = "AQOS trained baseline signal model."
    model_version_tags: tuple[str, ...] = (
        "aqos",
        "model-training",
        "baseline-signal-model",
        
    )
    enable_model_evaluation: bool = True
    model_evaluation_report_filename: str = "model_evaluation_report.json"
    fail_on_model_evaluation_error: bool = False
    evaluation_min_accuracy: float = 0.45
    evaluation_min_macro_f1: float | None = None
    evaluation_max_log_loss: float | None = None
    evaluation_min_test_samples: int = 20
    evaluation_required_classes: tuple[str, ...] = ()
    evaluation_allowed_promotion_stage: ModelPromotionStage = (
        ModelPromotionStage.RESEARCH
    )
    model_evaluation_notes: str | None = None


@dataclass(frozen=True)
class SignalTrainingRunOutput:
    model_path: Path
    metrics_path: Path
    quality_report_path: Path | None
    experiment_run_metadata_path: Path | None
    experiment_registry_path: Path | None
    model_version_metadata_path: Path | None
    training_result: SignalModelTrainingResult
    quality_report: DatasetQualityReport | None = None
    experiment_run: ExperimentRunMetadata | None = None
    model_version_metadata: ModelVersionMetadata | None = None
    model_evaluation_report_path: Path | None = None
    model_evaluation_report: ModelEvaluationReport | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "model_path": self.model_path.as_posix(),
            "metrics_path": self.metrics_path.as_posix(),
            "quality_report_path": (
                self.quality_report_path.as_posix()
                if self.quality_report_path is not None
                else None
            ),
            "experiment_run_metadata_path": (
                self.experiment_run_metadata_path.as_posix()
                if self.experiment_run_metadata_path is not None
                else None
            ),
            "experiment_registry_path": (
                self.experiment_registry_path.as_posix()
                if self.experiment_registry_path is not None
                else None
            ),
            "model_version_metadata_path": (
                self.model_version_metadata_path.as_posix()
                if self.model_version_metadata_path is not None
                else None
            ),
            "model_evaluation_report_path": (
                self.model_evaluation_report_path.as_posix()
                if self.model_evaluation_report_path is not None
                else None
            ),
            "training_result": self.training_result.to_dict(),
            "quality_report": (
                self.quality_report.to_dict()
                if self.quality_report is not None
                else None
            ),
            "experiment_run": (
                self.experiment_run.to_dict()
                if self.experiment_run is not None
                else None
            ),
            "model_version_metadata": (
                self.model_version_metadata.to_dict()
                if self.model_version_metadata is not None
                else None
            ),
            "model_evaluation_report": (
                self.model_evaluation_report.to_dict()
                if self.model_evaluation_report is not None
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


def discover_dataset_version_metadata_path(
    dataset_path: str | Path,
    run_config: SignalTrainingRunConfig,
) -> Path | None:
    if run_config.dataset_version_metadata_path is not None:
        explicit_path = Path(run_config.dataset_version_metadata_path)
        if explicit_path.exists():
            return explicit_path
        raise FileNotFoundError(
            f"Dataset version metadata file does not exist: {explicit_path}"
        )

    default_path = Path(dataset_path).parent / "signal_ml_dataset_version.json"

    if default_path.exists():
        return default_path

    return None


def extract_dataset_version_reference(
    dataset_version_metadata_path: str | Path | None,
) -> tuple[str | None, str | None]:
    if dataset_version_metadata_path is None:
        return None, None

    payload = read_dataset_version_metadata(dataset_version_metadata_path)

    return (
        payload.get("dataset_id"),
        payload.get("dataset_version"),
    )


def build_training_experiment_parameters(
    run_config: SignalTrainingRunConfig,
) -> dict[str, Any]:
    return {
        "target_column": run_config.target_column,
        "feature_columns": list(run_config.feature_columns)
        if run_config.feature_columns is not None
        else None,
        "test_size": run_config.test_size,
        "random_state": run_config.random_state,
        "n_estimators": run_config.n_estimators,
        "max_depth": run_config.max_depth,
        "min_samples_leaf": run_config.min_samples_leaf,
        "validate_schema": run_config.validate_schema,
        "validate_quality": run_config.validate_quality,
        "max_majority_class_ratio": run_config.max_majority_class_ratio,
    }


def build_training_experiment_artifacts(
    run_config: SignalTrainingRunConfig,
    model_path: Path,
    metrics_path: Path,
    quality_report_path: Path | None,
    dataset_version_metadata_path: Path | None,
    model_version_metadata_path: Path | None = None,
    model_evaluation_report_path: Path | None = None,
) -> tuple[ExperimentArtifact, ...]:
    artifacts: list[ExperimentArtifact] = [
        build_experiment_artifact(
            run_config.dataset_path,
            ExperimentArtifactType.TRAINING_DATASET,
            name="training_dataset",
        ),
        build_experiment_artifact(
            model_path,
            ExperimentArtifactType.MODEL,
            name="trained_model",
        ),
        build_experiment_artifact(
            metrics_path,
            ExperimentArtifactType.METRICS,
            name="training_metrics",
        ),
    ]

    if quality_report_path is not None:
        artifacts.append(
            build_experiment_artifact(
                quality_report_path,
                ExperimentArtifactType.QUALITY_REPORT,
                name="training_quality_report",
            )
        )

    if dataset_version_metadata_path is not None:
        artifacts.append(
            build_experiment_artifact(
                dataset_version_metadata_path,
                ExperimentArtifactType.DATASET_VERSION_METADATA,
                name="dataset_version_metadata",
            )
        )
    if model_version_metadata_path is not None:
        artifacts.append(
            build_experiment_artifact(
                model_version_metadata_path,
                ExperimentArtifactType.MODEL_VERSION_METADATA,
                name="model_version_metadata",
            )
        )
    if model_evaluation_report_path is not None:
        artifacts.append(
            build_experiment_artifact(
                model_evaluation_report_path,
                ExperimentArtifactType.MODEL_EVALUATION_REPORT,
                name="model_evaluation_report",
            )
        )

    return tuple(artifacts)


def build_training_experiment_run(
    run_config: SignalTrainingRunConfig,
    output_dir: Path,
    model_path: Path,
    metrics_path: Path,
    quality_report_path: Path | None,
    training_result: SignalModelTrainingResult,
) -> tuple[Path | None, Path | None, ExperimentRunMetadata | None]:
    if not run_config.enable_experiment_registry:
        return None, None, None

    dataset_version_metadata_path = discover_dataset_version_metadata_path(
        run_config.dataset_path,
        run_config,
    )
    dataset_id, dataset_version = extract_dataset_version_reference(
        dataset_version_metadata_path
    )

    artifacts = build_training_experiment_artifacts(
        run_config=run_config,
        model_path=model_path,
        metrics_path=metrics_path,
        quality_report_path=quality_report_path,
        dataset_version_metadata_path=dataset_version_metadata_path,
    )

    experiment_run = build_experiment_run_metadata(
        experiment_name=run_config.experiment_name,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        model_name=training_result.model_name,
        parameters=build_training_experiment_parameters(run_config),
        metrics=training_result.to_dict(),
        artifacts=artifacts,
        tags=run_config.experiment_tags,
        notes=run_config.experiment_notes,
    )

    experiment_run_metadata_path = output_dir / run_config.experiment_run_metadata_filename
    experiment_registry_path = output_dir / run_config.experiment_registry_filename

    write_experiment_run_metadata(
        experiment_run_metadata_path,
        experiment_run,
    )
    append_experiment_run_to_registry(
        experiment_registry_path,
        experiment_run,
    )

    return experiment_run_metadata_path, experiment_registry_path, experiment_run


def build_training_model_version_metadata(
    run_config: SignalTrainingRunConfig,
    model_path: Path,
    training_result: SignalModelTrainingResult,
    experiment_run: ExperimentRunMetadata | None,
) -> ModelVersionMetadata | None:
    if not run_config.enable_model_versioning:
        return None

    dataset_version_metadata_path = discover_dataset_version_metadata_path(
        run_config.dataset_path,
        run_config,
    )
    dataset_id, dataset_version = extract_dataset_version_reference(
        dataset_version_metadata_path
    )

    return build_model_version_metadata(
        model_name=training_result.model_name,
        model_path=model_path,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        experiment_run_id=experiment_run.run_id if experiment_run is not None else None,
        training_parameters=build_training_experiment_parameters(run_config),
        training_metrics=training_result.to_dict(),
        description=run_config.model_version_description,
        tags=run_config.model_version_tags,
    )


def build_training_model_evaluation_thresholds(
    run_config: SignalTrainingRunConfig,
) -> ModelEvaluationThresholds:
    return ModelEvaluationThresholds(
        min_accuracy=run_config.evaluation_min_accuracy,
        min_macro_f1=run_config.evaluation_min_macro_f1,
        max_log_loss=run_config.evaluation_max_log_loss,
        min_test_samples=run_config.evaluation_min_test_samples,
        required_classes=run_config.evaluation_required_classes,
        allowed_promotion_stage=run_config.evaluation_allowed_promotion_stage,
    )


def build_training_model_evaluation_report(
    run_config: SignalTrainingRunConfig,
    training_result: SignalModelTrainingResult,
    model_version_metadata: ModelVersionMetadata | None,
    experiment_run: ExperimentRunMetadata | None,
) -> ModelEvaluationReport | None:
    if not run_config.enable_model_evaluation:
        return None

    model_id = None
    model_version = None
    dataset_id = None
    dataset_version = None

    if model_version_metadata is not None:
        model_id = model_version_metadata.model_id
        model_version = model_version_metadata.model_version
        dataset_id = model_version_metadata.dataset_id
        dataset_version = model_version_metadata.dataset_version

    return build_model_evaluation_report(
        model_name=training_result.model_name,
        model_id=model_id,
        model_version=model_version,
        dataset_id=dataset_id,
        dataset_version=dataset_version,
        experiment_run_id=experiment_run.run_id if experiment_run is not None else None,
        metrics=training_result.to_dict(),
        thresholds=build_training_model_evaluation_thresholds(run_config),
        notes=run_config.model_evaluation_notes,
    )


def write_and_maybe_raise_model_evaluation_report(
    run_config: SignalTrainingRunConfig,
    output_dir: Path,
    report: ModelEvaluationReport | None,
) -> Path | None:
    if report is None:
        return None

    report_path = output_dir / run_config.model_evaluation_report_filename

    write_model_evaluation_report(report_path, report)

    if run_config.fail_on_model_evaluation_error:
        report.raise_if_invalid()

    return report_path

def train_baseline_signal_model_from_csv(
    run_config: SignalTrainingRunConfig,
) -> SignalTrainingRunOutput:
    dataset = load_signal_training_dataset(run_config.dataset_path)
    validate_training_dataset_for_run(dataset, run_config)

    output_dir = Path(run_config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / run_config.model_filename
    metrics_path = output_dir / run_config.metrics_filename
    quality_report_path: Path | None = output_dir / run_config.quality_report_filename
    model_version_metadata_path: Path | None = (
        output_dir / run_config.model_version_metadata_filename
    )

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

    dataset_version_metadata_path = (
        discover_dataset_version_metadata_path(run_config.dataset_path, run_config)
        if run_config.enable_experiment_registry or run_config.enable_model_versioning
        else None
    )
    dataset_id, dataset_version = extract_dataset_version_reference(
        dataset_version_metadata_path
    )

    preliminary_experiment_run: ExperimentRunMetadata | None = None

    if run_config.enable_experiment_registry:
        preliminary_experiment_run = build_experiment_run_metadata(
            experiment_name=run_config.experiment_name,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            model_name=result.model_name,
            parameters=build_training_experiment_parameters(run_config),
            metrics=result.to_dict(),
            artifacts=(),
            tags=run_config.experiment_tags,
            notes=run_config.experiment_notes,
        )

    model_version_metadata = build_training_model_version_metadata(
        run_config=run_config,
        model_path=saved_model_path,
        training_result=result,
        experiment_run=preliminary_experiment_run,
    )

    if model_version_metadata is not None:
        write_model_version_metadata(
            model_version_metadata_path,
            model_version_metadata,
        )
    else:
        model_version_metadata_path = None

    metrics_output = SignalTrainingRunOutput(
        model_path=saved_model_path,
        metrics_path=metrics_path,
        quality_report_path=quality_report_path,
        experiment_run_metadata_path=None,
        experiment_registry_path=None,
        model_version_metadata_path=model_version_metadata_path,
        model_evaluation_report_path=None,
        training_result=result,
        quality_report=quality_report,
        experiment_run=None,
        model_version_metadata=model_version_metadata,
        model_evaluation_report=None,
    )

    write_training_metrics(metrics_path, metrics_output)

    experiment_run_metadata_path: Path | None = None
    experiment_registry_path: Path | None = None
    experiment_run: ExperimentRunMetadata | None = None

    model_evaluation_report = build_training_model_evaluation_report(
        run_config=run_config,
        training_result=result,
        model_version_metadata=model_version_metadata,
        experiment_run=preliminary_experiment_run,
    )

    model_evaluation_report_path = write_and_maybe_raise_model_evaluation_report(
        run_config=run_config,
        output_dir=output_dir,
        report=model_evaluation_report,
    )

    if model_version_metadata is not None and model_evaluation_report is not None:
        model_version_metadata = build_model_version_metadata(
            model_name=result.model_name,
            model_path=saved_model_path,
            dataset_id=model_version_metadata.dataset_id,
            dataset_version=model_version_metadata.dataset_version,
            experiment_run_id=(
                preliminary_experiment_run.run_id
                if preliminary_experiment_run is not None
                else None
            ),
            training_parameters=build_training_experiment_parameters(run_config),
            training_metrics=result.to_dict(),
            description=run_config.model_version_description,
            tags=run_config.model_version_tags,
            model_evaluation_report_path=model_evaluation_report_path,
            promotion_stage=model_evaluation_report.promotion_stage.value,
            is_promotion_ready=model_evaluation_report.is_promotion_ready,
        )

        write_model_version_metadata(
            model_version_metadata_path,
            model_version_metadata,
        )

    metrics_with_evaluation_output = SignalTrainingRunOutput(
        model_path=saved_model_path,
        metrics_path=metrics_path,
        quality_report_path=quality_report_path,
        experiment_run_metadata_path=None,
        experiment_registry_path=None,
        model_version_metadata_path=model_version_metadata_path,
        model_evaluation_report_path=model_evaluation_report_path,
        training_result=result,
        quality_report=quality_report,
        experiment_run=None,
        model_version_metadata=model_version_metadata,
        model_evaluation_report=model_evaluation_report,
    )

    write_training_metrics(metrics_path, metrics_with_evaluation_output)

    if preliminary_experiment_run is not None:
        artifacts = build_training_experiment_artifacts(
            run_config=run_config,
            model_path=saved_model_path,
            metrics_path=metrics_path,
            quality_report_path=quality_report_path,
            dataset_version_metadata_path=dataset_version_metadata_path,
            model_version_metadata_path=model_version_metadata_path,
            model_evaluation_report_path=model_evaluation_report_path,
        )

        experiment_run = build_experiment_run_metadata(
            experiment_name=run_config.experiment_name,
            created_at_utc=preliminary_experiment_run.created_at_utc,
            dataset_id=dataset_id,
            dataset_version=dataset_version,
            model_name=result.model_name,
            parameters=build_training_experiment_parameters(run_config),
            metrics=result.to_dict(),
            artifacts=artifacts,
            tags=run_config.experiment_tags,
            notes=run_config.experiment_notes,
        )

        experiment_run_metadata_path = output_dir / run_config.experiment_run_metadata_filename
        experiment_registry_path = output_dir / run_config.experiment_registry_filename

        write_experiment_run_metadata(
            experiment_run_metadata_path,
            experiment_run,
        )
        append_experiment_run_to_registry(
            experiment_registry_path,
            experiment_run,
        )

    final_output = SignalTrainingRunOutput(
        model_path=saved_model_path,
        metrics_path=metrics_path,
        quality_report_path=quality_report_path,
        experiment_run_metadata_path=experiment_run_metadata_path,
        experiment_registry_path=experiment_registry_path,
        model_version_metadata_path=model_version_metadata_path,
        model_evaluation_report_path=model_evaluation_report_path,
        training_result=result,
        quality_report=quality_report,
        experiment_run=experiment_run,
        model_version_metadata=model_version_metadata,
        model_evaluation_report=model_evaluation_report,
    )

    return final_output
  


__all__ = [
    "SignalTrainingRunConfig",
    "SignalTrainingRunOutput",
    "build_signal_model_training_config",
    "build_training_dataset_quality_report",
    "build_training_experiment_artifacts",
    "build_training_experiment_parameters",
    "build_training_experiment_run",
    "build_training_model_version_metadata",
    "discover_dataset_version_metadata_path",
    "extract_dataset_version_reference",
    "load_signal_training_dataset",
    "resolve_training_feature_columns",
    "train_baseline_signal_model_from_csv",
    "validate_training_dataset_for_run",
    "write_training_metrics",
    "build_training_model_evaluation_report",
    "build_training_model_evaluation_thresholds",
    "write_and_maybe_raise_model_evaluation_report",
]