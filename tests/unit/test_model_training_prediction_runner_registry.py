from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    SignalPredictionRunConfig,
    SignalTrainingRunConfig,
    predict_signals_from_csv,
    read_prediction_registry,
    train_baseline_signal_model_from_csv,
)


def build_training_dataset() -> pd.DataFrame:
    rows = []
    targets = ["buy", "sell", "hold"] * 12

    for index, target in enumerate(targets):
        rows.append(
            {
                "open": 2300.0 + index,
                "high": 2302.0 + index,
                "low": 2298.0 + index,
                "close": 2301.0 + index,
                "volume": 1000 + index,
                "rsi_14": 40.0 + index,
                "macd_histogram": 0.01 * index,
                "atr_14": 1.2 + index * 0.01,
                "return_5": 0.001 * index,
                "target": target,
            }
        )

    return pd.DataFrame(rows)


def train_test_model(tmp_path):
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=191,
        )
    )

    return dataset, training_output


def test_prediction_runner_writes_prediction_registry(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    assert output.prediction_metadata_path is not None
    assert output.prediction_registry_path is not None
    assert output.prediction_registry_path.exists()

    registry = read_prediction_registry(output.prediction_registry_path)

    assert registry["registry_version"] == "1.0"
    assert len(registry["runs"]) == 1
    assert registry["runs"][0]["prediction_id"] == output.prediction_metadata.prediction_id
    assert registry["runs"][0]["model_id"] == training_output.model_version_metadata.model_id
    assert registry["runs"][0]["model_version"] == (
        training_output.model_version_metadata.model_version
    )
    assert registry["runs"][0]["rows"] == 8
    assert registry["runs"][0]["metadata_path"].endswith("prediction_run_metadata.json")
    assert registry["runs"][0]["prediction_path"].endswith("signals.csv")


def test_prediction_runner_can_disable_prediction_registry(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
            enable_prediction_registry=False,
        )
    )

    assert output.prediction_metadata_path is not None
    assert output.prediction_metadata_path.exists()
    assert output.prediction_registry_path is None
    assert not (prediction_path.parent / "prediction_registry.json").exists()


def test_prediction_runner_registry_disabled_when_versioning_disabled(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            enable_prediction_versioning=False,
        )
    )

    assert output.prediction_metadata_path is None
    assert output.prediction_registry_path is None
    assert output.prediction_metadata is None
    assert not (prediction_path.parent / "prediction_run_metadata.json").exists()
    assert not (prediction_path.parent / "prediction_registry.json").exists()


def test_prediction_runner_supports_custom_prediction_registry_filename(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
            prediction_registry_filename="custom_prediction_registry.json",
        )
    )

    assert output.prediction_registry_path is not None
    assert output.prediction_registry_path.name == "custom_prediction_registry.json"
    assert output.prediction_registry_path.exists()


def test_prediction_output_dict_contains_prediction_registry_path(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    payload = output.to_dict()

    assert payload["prediction_metadata_path"].endswith("prediction_run_metadata.json")
    assert payload["prediction_registry_path"].endswith("prediction_registry.json")
    assert payload["prediction_metadata"]["rows"] == 8


def test_cli_prediction_output_contains_prediction_registry_path(tmp_path, capsys) -> None:
    from aqos.model_training.cli import run_model_training_cli

    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    train_exit_code = run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--random-state",
            "193",
        ]
    )
    capsys.readouterr()

    predict_exit_code = run_model_training_cli(
        [
            "predict",
            "--model-path",
            str(output_dir / "baseline_signal_model.joblib"),
            "--features-path",
            str(features_path),
            "--output-path",
            str(predictions_path),
            "--model-version-metadata-path",
            str(output_dir / "model_version_metadata.json"),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert train_exit_code == 0
    assert predict_exit_code == 0
    assert payload["prediction_registry_path"].endswith("prediction_registry.json")
    assert (predictions_path.parent / "prediction_registry.json").exists()