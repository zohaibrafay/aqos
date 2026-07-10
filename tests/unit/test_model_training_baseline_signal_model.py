from __future__ import annotations

import pandas as pd
import pytest

from aqos.model_training import BaselineSignalModel, SignalModelTrainingConfig


def build_training_dataset() -> pd.DataFrame:
    rows = []

    for index in range(30):
        rows.append(
            {
                "rsi_14": 20 + index,
                "macd_histogram": 0.5 + index * 0.01,
                "atr_14": 1.5 + index * 0.02,
                "return_5": 0.01 + index * 0.001,
                "target": "buy",
            }
        )

    for index in range(30):
        rows.append(
            {
                "rsi_14": 80 - index,
                "macd_histogram": -0.5 - index * 0.01,
                "atr_14": 1.8 + index * 0.02,
                "return_5": -0.01 - index * 0.001,
                "target": "sell",
            }
        )

    for index in range(30):
        rows.append(
            {
                "rsi_14": 45 + (index % 5),
                "macd_histogram": 0.01 * ((index % 3) - 1),
                "atr_14": 1.0 + index * 0.005,
                "return_5": 0.0,
                "target": "hold",
            }
        )

    return pd.DataFrame(rows)


def test_baseline_signal_model_trains_and_returns_metrics() -> None:
    dataset = build_training_dataset()
    model = BaselineSignalModel(
        SignalModelTrainingConfig(
            target_column="target",
            test_size=0.25,
            random_state=7,
            n_estimators=20,
            max_depth=4,
        )
    )

    result = model.train(dataset)

    assert model.is_trained is True
    assert result.model_name == "baseline_random_forest_signal_model"
    assert result.target_column == "target"
    assert result.train_rows > 0
    assert result.test_rows > 0
    assert set(result.labels) == {"buy", "sell", "hold"}
    assert 0.0 <= result.accuracy <= 1.0
    assert result.feature_columns == ("rsi_14", "macd_histogram", "atr_14", "return_5")
    assert "accuracy" in result.to_dict()


def test_baseline_signal_model_predicts_signals_and_probabilities() -> None:
    dataset = build_training_dataset()
    model = BaselineSignalModel(
        SignalModelTrainingConfig(
            n_estimators=20,
            random_state=11,
        )
    )
    model.train(dataset)

    features = dataset.drop(columns=["target"]).head(5)

    predictions = model.predict(features)
    probabilities = model.predict_proba(features)

    assert len(predictions) == 5
    assert set(predictions.unique()).issubset({"buy", "sell", "hold"})
    assert probabilities.shape[0] == 5
    assert all(column.startswith("probability_") for column in probabilities.columns)


def test_baseline_signal_model_saves_and_loads(tmp_path) -> None:
    dataset = build_training_dataset()
    model = BaselineSignalModel(
        SignalModelTrainingConfig(
            n_estimators=20,
            random_state=13,
        )
    )
    model.train(dataset)

    output_path = tmp_path / "baseline_signal_model.joblib"
    saved_path = model.save(output_path)

    loaded = BaselineSignalModel.load(saved_path)

    features = dataset.drop(columns=["target"]).head(3)

    original_predictions = model.predict(features).tolist()
    loaded_predictions = loaded.predict(features).tolist()

    assert saved_path.exists()
    assert loaded.is_trained is True
    assert loaded.feature_columns == model.feature_columns
    assert loaded_predictions == original_predictions


def test_baseline_signal_model_rejects_invalid_dataset() -> None:
    model = BaselineSignalModel()

    with pytest.raises(ValueError, match="target column"):
        model.train(pd.DataFrame({"rsi_14": [30, 40, 50, 60, 70, 80, 45, 55]}))

    with pytest.raises(ValueError, match="at least two signal classes"):
        model.train(
            pd.DataFrame(
                {
                    "rsi_14": [30, 31, 32, 33, 34, 35, 36, 37],
                    "target": ["buy"] * 8,
                }
            )
        )


def test_baseline_signal_model_rejects_prediction_before_training() -> None:
    model = BaselineSignalModel()

    with pytest.raises(RuntimeError, match="trained or loaded"):
        model.predict(pd.DataFrame({"rsi_14": [30]}))