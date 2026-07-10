from __future__ import annotations

import pandas as pd
import pytest

from aqos.model_training import (
    SignalPredictionRunConfig,
    SignalTrainingRunConfig,
    train_baseline_signal_model_from_csv,
    validate_prediction_features_for_run,
    validate_training_dataset_for_run,
)


def build_valid_dataset() -> pd.DataFrame:
    rows = []
    targets = ["buy", "sell", "hold"] * 8

    for index, target in enumerate(targets):
        rows.append(
            {
                "open": 2300.0 + index,
                "high": 2302.0 + index,
                "low": 2298.0 + index,
                "close": 2301.0 + index,
                "volume": 1000 + index,
                "rsi_14": 35.0 + index,
                "macd_histogram": 0.05 * index,
                "atr_14": 1.2 + index * 0.01,
                "return_5": 0.001 * index,
                "target": target,
            }
        )

    return pd.DataFrame(rows)


def test_training_runner_rejects_dataset_that_fails_schema(tmp_path) -> None:
    dataset = build_valid_dataset().drop(columns=["close"])
    dataset_path = tmp_path / "weak_training.csv"
    dataset.to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="Dataset validation failed"):
        train_baseline_signal_model_from_csv(
            SignalTrainingRunConfig(
                dataset_path=dataset_path,
                output_dir=tmp_path / "artifacts",
                n_estimators=20,
            )
        )


def test_training_runner_uses_schema_feature_columns_when_not_explicit(tmp_path) -> None:
    dataset = build_valid_dataset()
    dataset_path = tmp_path / "training.csv"
    dataset.to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=tmp_path / "artifacts",
            n_estimators=20,
            random_state=41,
        )
    )

    assert output.training_result.feature_columns == (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "rsi_14",
        "macd_histogram",
        "atr_14",
        "return_5",
    )


def test_training_validation_can_be_disabled_for_legacy_experiments() -> None:
    weak_dataset = pd.DataFrame(
        {
            "rsi_14": [30, 40, 50, 60, 70, 80, 45, 55],
            "target": ["buy", "sell", "buy", "sell", "hold", "hold", "buy", "sell"],
        }
    )

    validate_training_dataset_for_run(
        weak_dataset,
        SignalTrainingRunConfig(
            dataset_path="unused.csv",
            validate_schema=False,
        ),
    )


def test_prediction_runner_rejects_features_that_fail_schema() -> None:
    weak_features = build_valid_dataset().drop(columns=["close", "target"])

    with pytest.raises(ValueError, match="Dataset validation failed"):
        validate_prediction_features_for_run(
            weak_features,
            SignalPredictionRunConfig(
                model_path="unused.joblib",
                features_path="unused.csv",
            ),
        )


def test_prediction_validation_can_be_disabled_for_legacy_experiments() -> None:
    weak_features = pd.DataFrame({"rsi_14": [30, 40, 50]})

    validate_prediction_features_for_run(
        weak_features,
        SignalPredictionRunConfig(
            model_path="unused.joblib",
            features_path="unused.csv",
            validate_schema=False,
        ),
    )