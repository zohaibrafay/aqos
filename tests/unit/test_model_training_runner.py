from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    SignalTrainingRunConfig,
    load_signal_training_dataset,
    train_baseline_signal_model_from_csv,
)


def build_training_dataset() -> pd.DataFrame:
    rows = []

    for index in range(24):
        rows.append(
            {
                "open": 2300.0 + index,
                "high": 2302.0 + index,
                "low": 2298.0 + index,
                "close": 2301.0 + index,
                "volume": 1000 + index,
                "rsi_14": 22 + index,
                "macd_histogram": 0.4 + index * 0.01,
                "atr_14": 1.2 + index * 0.02,
                "return_5": 0.01 + index * 0.001,
                "target": "buy",
            }
        )

    for index in range(24):
        rows.append(
            {
                "open": 2350.0 - index,
                "high": 2352.0 - index,
                "low": 2348.0 - index,
                "close": 2349.0 - index,
                "volume": 1200 + index,
                "rsi_14": 78 - index,
                "macd_histogram": -0.4 - index * 0.01,
                "atr_14": 1.4 + index * 0.02,
                "return_5": -0.01 - index * 0.001,
                "target": "sell",
            }
        )

    for index in range(24):
        rows.append(
            {
                "open": 2320.0 + (index % 3),
                "high": 2321.0 + (index % 3),
                "low": 2319.0 + (index % 3),
                "close": 2320.5 + (index % 3),
                "volume": 900 + index,
                "rsi_14": 48 + (index % 4),
                "macd_histogram": 0.0,
                "atr_14": 1.0 + index * 0.01,
                "return_5": 0.0,
                "target": "hold",
            }
        )

    return pd.DataFrame(rows)


def test_load_signal_training_dataset_reads_csv(tmp_path) -> None:
    dataset_path = tmp_path / "training.csv"
    build_training_dataset().to_csv(dataset_path, index=False)

    dataset = load_signal_training_dataset(dataset_path)

    assert dataset.shape[0] == 72
    assert "target" in dataset.columns


def test_load_signal_training_dataset_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_signal_training_dataset(tmp_path / "missing.csv")


def test_load_signal_training_dataset_rejects_non_csv(tmp_path) -> None:
    path = tmp_path / "training.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV"):
        load_signal_training_dataset(path)


def test_train_baseline_signal_model_from_csv_saves_artifacts(tmp_path) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"
    build_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            target_column="target",
            test_size=0.25,
            random_state=17,
            n_estimators=20,
            max_depth=4,
        )
    )

    assert output.model_path.exists()
    assert output.metrics_path.exists()
    assert output.training_result.train_rows > 0
    assert output.training_result.test_rows > 0
    assert set(output.training_result.labels) == {"buy", "sell", "hold"}

    metrics = json.loads(output.metrics_path.read_text(encoding="utf-8"))

    assert metrics["model_path"].endswith("baseline_signal_model.joblib")
    assert metrics["metrics_path"].endswith("baseline_signal_model_metrics.json")
    assert metrics["training_result"]["model_name"] == "baseline_random_forest_signal_model"
    assert metrics["training_result"]["target_column"] == "target"


def test_train_baseline_signal_model_from_csv_supports_selected_features(tmp_path) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"
    build_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            feature_columns=("rsi_14", "macd_histogram"),
            n_estimators=20,
        )
    )

    assert output.training_result.feature_columns == ("rsi_14", "macd_histogram")