from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    SignalPredictionRunConfig,
    SignalTrainingRunConfig,
    build_dataset_version_metadata,
    compute_file_sha256,
    read_prediction_run_metadata,
    train_baseline_signal_model_from_csv,
    write_dataset_version_metadata,
    predict_signals_from_csv,
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


def test_prediction_runner_writes_prediction_metadata(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    dataset_version = build_dataset_version_metadata(
        dataframe=dataset,
        dataset_name="signal_ml_training_dataset",
        dataset_path=dataset_path,
        source_file_path=dataset_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )
    write_dataset_version_metadata(
        tmp_path / "signal_ml_dataset_version.json",
        dataset_version,
    )

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=163,
        )
    )

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    prediction_output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    assert prediction_output.output_path.exists()
    assert prediction_output.prediction_metadata_path is not None
    assert prediction_output.prediction_metadata_path.exists()
    assert prediction_output.prediction_metadata is not None

    payload = read_prediction_run_metadata(prediction_output.prediction_metadata_path)

    assert payload["metadata_version"] == "1.0"
    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert payload["model_id"] == training_output.model_version_metadata.model_id
    assert payload["model_version"] == training_output.model_version_metadata.model_version
    assert payload["rows"] == 8
    assert payload["prediction_column"] == "predicted_signal"
    assert payload["prediction_artifact"]["path"].endswith("signals.csv")
    assert payload["prediction_artifact"]["sha256"] == compute_file_sha256(
        prediction_path
    )
    assert payload["input_features_artifact"]["sha256"] == compute_file_sha256(
        features_path
    )
    assert payload["model_version_metadata_artifact"]["sha256"] == compute_file_sha256(
        training_output.model_version_metadata_path
    )
    assert payload["input_features_fingerprint"]["rows"] == 8
    assert payload["parameters"]["include_probabilities"] is True


def test_prediction_runner_metadata_can_be_disabled(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=167,
        )
    )

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    prediction_output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            enable_prediction_versioning=False,
        )
    )

    assert prediction_output.output_path.exists()
    assert prediction_output.prediction_metadata_path is None
    assert prediction_output.prediction_metadata is None
    assert not (prediction_path.parent / "prediction_run_metadata.json").exists()


def test_prediction_runner_supports_custom_prediction_metadata_filename(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=171,
        )
    )

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    prediction_output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
            prediction_metadata_filename="custom_prediction_metadata.json",
        )
    )

    assert prediction_output.prediction_metadata_path is not None
    assert prediction_output.prediction_metadata_path.name == (
        "custom_prediction_metadata.json"
    )
    assert prediction_output.prediction_metadata_path.exists()


def test_prediction_output_dict_contains_prediction_metadata(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=173,
        )
    )

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    prediction_output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    payload = prediction_output.to_dict()

    assert payload["prediction_metadata_path"].endswith("prediction_run_metadata.json")
    assert payload["prediction_metadata"]["model_name"] == (
        "baseline_random_forest_signal_model"
    )
    assert payload["prediction_metadata"]["prediction_artifact"]["path"].endswith(
        "signals.csv"
    )


def test_prediction_metadata_file_is_valid_json(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=179,
        )
    )

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    prediction_output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    payload = json.loads(
        prediction_output.prediction_metadata_path.read_text(encoding="utf-8")
    )

    assert payload["prediction_id"].startswith("prediction_v")
    assert payload["rows"] == 8