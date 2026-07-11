from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.model_training.baseline_signal_model import BaselineSignalModel
from aqos.model_training.feature_schema import validate_signal_prediction_dataset
from aqos.model_training.prediction_registry import append_prediction_run_to_registry
from aqos.model_training.prediction_validation import (
    PredictionValidationIssue,
    PredictionValidationReport,
    build_prediction_validation_report,
    extract_trained_feature_columns,
    validate_prediction_feature_columns_against_model,
    validate_prediction_input_output,
    write_prediction_validation_report,
)
from aqos.model_training.prediction_versioning import (
    PredictionRunMetadata,
    build_prediction_run_metadata,
    extract_model_version_reference,
    write_prediction_run_metadata,
)


@dataclass(frozen=True)
class SignalPredictionRunConfig:
    model_path: str | Path
    features_path: str | Path
    output_path: str | Path = "tmp/model_training/baseline_signal_predictions.csv"
    include_probabilities: bool = True
    validate_schema: bool = True
    enable_prediction_versioning: bool = True
    prediction_metadata_filename: str = "prediction_run_metadata.json"
    enable_prediction_registry: bool = True
    prediction_registry_filename: str = "prediction_registry.json"
    model_version_metadata_path: str | Path | None = None
    enable_prediction_validation: bool = True
    prediction_validation_report_filename: str = "prediction_validation_report.json"
    fail_on_prediction_validation_error: bool = True
    require_model_version: bool = False
    require_probability_columns: bool = False
    require_confidence: bool = False
    confidence_column: str | None = None
    min_confidence: float = 0.55
    max_low_confidence_ratio: float = 0.5
    probability_sum_tolerance: float = 0.01
    require_trained_feature_columns: bool = True
    remove_invalid_prediction_artifact: bool = True


@dataclass(frozen=True)
class SignalPredictionRunOutput:
    output_path: Path
    rows: int
    prediction_column: str
    probability_columns: tuple[str, ...]
    prediction_metadata_path: Path | None = None
    prediction_registry_path: Path | None = None
    prediction_validation_report_path: Path | None = None
    prediction_metadata: PredictionRunMetadata | None = None
    prediction_validation_report: PredictionValidationReport | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "output_path": self.output_path.as_posix(),
            "rows": self.rows,
            "prediction_column": self.prediction_column,
            "probability_columns": list(self.probability_columns),
            "prediction_metadata_path": (
                self.prediction_metadata_path.as_posix()
                if self.prediction_metadata_path is not None
                else None
            ),
            "prediction_registry_path": (
                self.prediction_registry_path.as_posix()
                if self.prediction_registry_path is not None
                else None
            ),
            "prediction_validation_report_path": (
                self.prediction_validation_report_path.as_posix()
                if self.prediction_validation_report_path is not None
                else None
            ),
            "prediction_metadata": (
                self.prediction_metadata.to_dict()
                if self.prediction_metadata is not None
                else None
            ),
            "prediction_validation_report": (
                self.prediction_validation_report.to_dict()
                if self.prediction_validation_report is not None
                else None
            ),
        }


def load_signal_prediction_features(features_path: str | Path) -> pd.DataFrame:
    path = Path(features_path)

    if not path.exists():
        raise FileNotFoundError(f"Prediction features file does not exist: {path}")

    if path.suffix.lower() != ".csv":
        raise ValueError("Signal prediction features must be a CSV file.")

    features = pd.read_csv(path)

    if features.empty:
        raise ValueError("Signal prediction features CSV is empty.")

    return features


def validate_prediction_features_for_run(
    features: pd.DataFrame,
    run_config: SignalPredictionRunConfig,
) -> None:
    if not run_config.validate_schema:
        return

    result = validate_signal_prediction_dataset(features)
    result.raise_if_invalid()


def build_prediction_metadata_parameters(
    run_config: SignalPredictionRunConfig,
) -> dict[str, Any]:
    return {
        "model_path": Path(run_config.model_path).as_posix(),
        "features_path": Path(run_config.features_path).as_posix(),
        "include_probabilities": run_config.include_probabilities,
        "validate_schema": run_config.validate_schema,
        "enable_prediction_versioning": run_config.enable_prediction_versioning,
        "enable_prediction_registry": run_config.enable_prediction_registry,
        "enable_prediction_validation": run_config.enable_prediction_validation,
        "require_model_version": run_config.require_model_version,
        "require_probability_columns": run_config.require_probability_columns,
        "require_confidence": run_config.require_confidence,
        "confidence_column": run_config.confidence_column,
        "min_confidence": run_config.min_confidence,
        "max_low_confidence_ratio": run_config.max_low_confidence_ratio,
        "probability_sum_tolerance": run_config.probability_sum_tolerance,
        "remove_invalid_prediction_artifact": run_config.remove_invalid_prediction_artifact,
    }


def build_prediction_metadata_for_output(
    run_config: SignalPredictionRunConfig,
    features: pd.DataFrame,
    output: pd.DataFrame,
    output_path: Path,
    prediction_column: str,
    probability_columns: tuple[str, ...],
) -> tuple[Path | None, PredictionRunMetadata | None]:
    if not run_config.enable_prediction_versioning:
        return None, None

    metadata_path = output_path.parent / run_config.prediction_metadata_filename

    metadata = build_prediction_run_metadata(
        predictions=output,
        prediction_path=output_path,
        input_features=features,
        input_features_path=run_config.features_path,
        model_version_metadata_path=run_config.model_version_metadata_path,
        prediction_column=prediction_column,
        probability_columns=probability_columns,
        parameters=build_prediction_metadata_parameters(run_config),
    )

    write_prediction_run_metadata(metadata_path, metadata)

    return metadata_path, metadata


def append_prediction_metadata_to_registry(
    run_config: SignalPredictionRunConfig,
    output_path: Path,
    prediction_metadata_path: Path | None,
    prediction_metadata: PredictionRunMetadata | None,
) -> Path | None:
    if not run_config.enable_prediction_versioning:
        return None

    if not run_config.enable_prediction_registry:
        return None

    if prediction_metadata_path is None or prediction_metadata is None:
        return None

    registry_path = output_path.parent / run_config.prediction_registry_filename

    return append_prediction_run_to_registry(
        registry_path=registry_path,
        metadata=prediction_metadata,
        metadata_path=prediction_metadata_path,
    )


def build_prediction_feature_compatibility_report(
    model: BaselineSignalModel,
    features: pd.DataFrame,
    run_config: SignalPredictionRunConfig,
) -> PredictionValidationReport | None:
    if not run_config.enable_prediction_validation:
        return None

    trained_feature_columns = extract_trained_feature_columns(model)

    issues = validate_prediction_feature_columns_against_model(
        input_features=features,
        trained_feature_columns=trained_feature_columns,
        require_trained_feature_columns=run_config.require_trained_feature_columns,
    )

    if not issues:
        return None

    return build_prediction_validation_report(
        issues=issues,
        checked_rows=len(features),
        prediction_column="predicted_signal",
        probability_columns=(),
    )


def build_prediction_output_validation_report(
    run_config: SignalPredictionRunConfig,
    features: pd.DataFrame,
    output: pd.DataFrame,
    prediction_column: str,
    probability_columns: tuple[str, ...],
    extra_issues: tuple[PredictionValidationIssue, ...] = (),
) -> PredictionValidationReport | None:
    if not run_config.enable_prediction_validation:
        return None

    model_name, model_id, model_version = extract_model_version_reference(
        run_config.model_version_metadata_path
    )

    del model_name

    report = validate_prediction_input_output(
        input_features=features,
        predictions=output,
        prediction_column=prediction_column,
        probability_columns=probability_columns,
        require_probability_columns=run_config.require_probability_columns,
        probability_sum_tolerance=run_config.probability_sum_tolerance,
        confidence_column=run_config.confidence_column,
        min_confidence=run_config.min_confidence,
        max_low_confidence_ratio=run_config.max_low_confidence_ratio,
        require_confidence=run_config.require_confidence,
        model_id=model_id,
        model_version=model_version,
        require_model_version=run_config.require_model_version,
    )

    if not extra_issues:
        return report

    return build_prediction_validation_report(
        issues=tuple(report.issues) + extra_issues,
        checked_rows=report.checked_rows,
        prediction_column=report.prediction_column,
        probability_columns=report.probability_columns,
        created_at_utc=report.created_at_utc,
    )

def remove_invalid_prediction_artifact_if_needed(
    run_config: SignalPredictionRunConfig,
    output_path: Path,
    report: PredictionValidationReport | None,
) -> bool:
    if report is None:
        return False

    if report.is_valid:
        return False

    if not run_config.remove_invalid_prediction_artifact:
        return False

    if not output_path.exists():
        return False

    output_path.unlink()

    return True

def write_and_maybe_raise_prediction_validation_report(
    run_config: SignalPredictionRunConfig,
    output_path: Path,
    report: PredictionValidationReport | None,
) -> Path | None:
    if report is None:
        return None

    validation_report_path = output_path.parent / run_config.prediction_validation_report_filename

    write_prediction_validation_report(
        validation_report_path,
        report,
    )

    if report.is_valid:
        return validation_report_path

    remove_invalid_prediction_artifact_if_needed(
        run_config=run_config,
        output_path=output_path,
        report=report,
    )

    if run_config.fail_on_prediction_validation_error:
        report.raise_if_invalid()

    return validation_report_path


def predict_signals_from_csv(
    run_config: SignalPredictionRunConfig,
) -> SignalPredictionRunOutput:
    model = BaselineSignalModel.load(run_config.model_path)
    features = load_signal_prediction_features(run_config.features_path)
    validate_prediction_features_for_run(features, run_config)

    feature_compatibility_report = build_prediction_feature_compatibility_report(
        model=model,
        features=features,
        run_config=run_config,
    )

    output_path = Path(run_config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if feature_compatibility_report is not None and not feature_compatibility_report.is_valid:
        write_and_maybe_raise_prediction_validation_report(
            run_config=run_config,
            output_path=output_path,
            report=feature_compatibility_report,
        )

    predictions = model.predict(features)
    output = features.copy()
    output[predictions.name or "predicted_signal"] = predictions

    probability_columns: tuple[str, ...] = ()

    if run_config.include_probabilities:
        probabilities = model.predict_proba(features)
        probability_columns = tuple(probabilities.columns)
        output = pd.concat([output, probabilities], axis=1)

    output.to_csv(output_path, index=False)

    prediction_column = predictions.name or "predicted_signal"

    validation_report = build_prediction_output_validation_report(
        run_config=run_config,
        features=features,
        output=output,
        prediction_column=prediction_column,
        probability_columns=probability_columns,
        extra_issues=(
            feature_compatibility_report.issues
            if feature_compatibility_report is not None
            else ()
        ),
    )

    prediction_validation_report_path = write_and_maybe_raise_prediction_validation_report(
        run_config=run_config,
        output_path=output_path,
        report=validation_report,
    )

    if output_path.exists():
        prediction_metadata_path, prediction_metadata = build_prediction_metadata_for_output(
            run_config=run_config,
            features=features,
            output=output,
            output_path=output_path,
            prediction_column=prediction_column,
            probability_columns=probability_columns,
        )
    else:
        prediction_metadata_path, prediction_metadata = None, None

    prediction_registry_path = append_prediction_metadata_to_registry(
        run_config=run_config,
        output_path=output_path,
        prediction_metadata_path=prediction_metadata_path,
        prediction_metadata=prediction_metadata,
    )

    return SignalPredictionRunOutput(
        output_path=output_path,
        rows=len(output),
        prediction_column=prediction_column,
        probability_columns=probability_columns,
        prediction_metadata_path=prediction_metadata_path,
        prediction_registry_path=prediction_registry_path,
        prediction_validation_report_path=prediction_validation_report_path,
        prediction_metadata=prediction_metadata,
        prediction_validation_report=validation_report,
    )


__all__ = [
    "SignalPredictionRunConfig",
    "SignalPredictionRunOutput",
    "append_prediction_metadata_to_registry",
    "build_prediction_feature_compatibility_report",
    "build_prediction_metadata_for_output",
    "build_prediction_metadata_parameters",
    "build_prediction_output_validation_report",
    "load_signal_prediction_features",
    "predict_signals_from_csv",
    "validate_prediction_features_for_run",
    "write_and_maybe_raise_prediction_validation_report",
    "remove_invalid_prediction_artifact_if_needed",
]