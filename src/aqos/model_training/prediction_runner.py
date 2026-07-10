from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from aqos.model_training.baseline_signal_model import BaselineSignalModel
from aqos.model_training.feature_schema import validate_signal_prediction_dataset


@dataclass(frozen=True)
class SignalPredictionRunConfig:
    model_path: str | Path
    features_path: str | Path
    output_path: str | Path = "tmp/model_training/baseline_signal_predictions.csv"
    include_probabilities: bool = True
    validate_schema: bool = True


@dataclass(frozen=True)
class SignalPredictionRunOutput:
    output_path: Path
    rows: int
    prediction_column: str
    probability_columns: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "output_path": self.output_path.as_posix(),
            "rows": self.rows,
            "prediction_column": self.prediction_column,
            "probability_columns": list(self.probability_columns),
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

    return SignalPredictionRunOutput(
        output_path=output_path,
        rows=len(output),
        prediction_column=predictions.name or "predicted_signal",
        probability_columns=probability_columns,
    )


__all__ = [
    "SignalPredictionRunConfig",
    "SignalPredictionRunOutput",
    "load_signal_prediction_features",
    "predict_signals_from_csv",
    "validate_prediction_features_for_run",
]