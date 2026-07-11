from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.model_training.baseline_signal_model import BaselineSignalModel
from aqos.model_training.feature_schema import validate_signal_prediction_dataset
from aqos.model_training.prediction_registry import append_prediction_run_to_registry
from aqos.model_training.prediction_versioning import (
    PredictionRunMetadata,
    build_prediction_run_metadata,
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


@dataclass(frozen=True)
class SignalPredictionRunOutput:
    output_path: Path
    rows: int
    prediction_column: str
    probability_columns: tuple[str, ...]
    prediction_metadata_path: Path | None = None
    prediction_registry_path: Path | None = None
    prediction_metadata: PredictionRunMetadata | None = None

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
            "prediction_metadata": (
                self.prediction_metadata.to_dict()
                if self.prediction_metadata is not None
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


def predict_signals_from_csv(
    run_config: SignalPredictionRunConfig,
) -> SignalPredictionRunOutput:
    model = BaselineSignalModel.load(run_config.model_path)
    features = load_signal_prediction_features(run_config.features_path)
    validate_prediction_features_for_run(features, run_config)

    predictions = model.predict(features)
    output = features.copy()
    output[predictions.name or "predicted_signal"] = predictions

    probability_columns: tuple[str, ...] = ()

    if run_config.include_probabilities:
        probabilities = model.predict_proba(features)
        probability_columns = tuple(probabilities.columns)
        output = pd.concat([output, probabilities], axis=1)

    output_path = Path(run_config.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(output_path, index=False)

    prediction_column = predictions.name or "predicted_signal"

    prediction_metadata_path, prediction_metadata = build_prediction_metadata_for_output(
        run_config=run_config,
        features=features,
        output=output,
        output_path=output_path,
        prediction_column=prediction_column,
        probability_columns=probability_columns,
    )

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
        prediction_metadata=prediction_metadata,
    )


__all__ = [
    "SignalPredictionRunConfig",
    "SignalPredictionRunOutput",
    "append_prediction_metadata_to_registry",
    "build_prediction_metadata_for_output",
    "build_prediction_metadata_parameters",
    "load_signal_prediction_features",
    "predict_signals_from_csv",
    "validate_prediction_features_for_run",
]