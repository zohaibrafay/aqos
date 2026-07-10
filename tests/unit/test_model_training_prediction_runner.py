from __future__ import annotations

import pandas as pd
import pytest

from aqos.model_training import (
    SignalPredictionRunConfig,
    SignalTrainingRunConfig,
    load_signal_prediction_features,
    predict_signals_from_csv,
    train_baseline_signal_model_from_csv,
)


def build_training_dataset() -> pd.DataFrame:
    rows = []

    for index in range(24):
        rows.append(
            {
                "rsi_14": 20 + index,
                "macd_histogram": 0.5 + index * 0.01,
                "atr_14": 1.2 + index * 0.02,
                "return_5": 0.01 + index * 0.001,
                "target": "buy",
            }
        )

    for index in range(24):
        rows.append(
            {
                "rsi_14": 80 - index,
                "macd_histogram": -0.5 - index * 0.01,
                "atr_14": 1.4 + index * 0.02,
                "return_5": -0.01 - index * 0.001,
                "target": "sell",
            }
        )

    for index in range(24):
        rows.append(
            {
                "rsi_14": 48 + (index % 4),
                "macd_histogram": 0.0,
                "atr_14": 1.0 + index * 0.01,
                "return_5": 0.0,
                "target": "hold",
            }
        )

    return pd.DataFrame(rows)


def train_test_model(tmp_path):
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    build_training_dataset().to_csv(dataset_path, index=False)

    return train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=19,
        )
    )


def test_load_signal_prediction_features_reads_csv(tmp_path) -> None:
    features_path = tmp_path / "features.csv"
    build_training_dataset().drop(columns=["target"]).head(5).to_csv(features_path, index=False)

    features = load_signal_prediction_features(features_path)

    assert features.shape[0] == 5
    assert "rsi_14" in features.columns


def test_load_signal_prediction_features_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_signal_prediction_features(tmp_path / "missing.csv")


def test_load_signal_prediction_features_rejects_non_csv(tmp_path) -> None:
    path = tmp_path / "features.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV"):
        load_signal_prediction_features(path)


def test_predict_signals_from_csv_writes_predictions_and_probabilities(tmp_path) -> None:
    training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    output_path = tmp_path / "predictions" / "signals.csv"

    build_training_dataset().drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    prediction_output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=output_path,
            include_probabilities=True,
        )
    )

    predictions = pd.read_csv(output_path)

    assert prediction_output.output_path.exists()
    assert prediction_output.rows == 8
    assert prediction_output.prediction_column == "predicted_signal"
    assert len(prediction_output.probability_columns) >= 2

    assert "predicted_signal" in predictions.columns
    assert set(predictions["predicted_signal"].unique()).issubset({"buy", "sell", "hold"})
    assert any(column.startswith("probability_") for column in predictions.columns)


def test_predict_signals_from_csv_can_skip_probabilities(tmp_path) -> None:
    training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    output_path = tmp_path / "predictions" / "signals.csv"

    build_training_dataset().drop(columns=["target"]).head(5).to_csv(features_path, index=False)

    prediction_output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=output_path,
            include_probabilities=False,
        )
    )

    predictions = pd.read_csv(output_path)

    assert prediction_output.probability_columns == ()
    assert "predicted_signal" in predictions.columns
    assert not any(column.startswith("probability_") for column in predictions.columns)