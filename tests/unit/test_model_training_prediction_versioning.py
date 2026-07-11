from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    PREDICTION_METADATA_VERSION,
    PredictionArtifactType,
    build_model_version_metadata,
    build_prediction_artifact_reference,
    build_prediction_run_id,
    build_prediction_run_metadata,
    compute_file_sha256,
    extract_model_version_reference,
    normalize_prediction_name,
    read_prediction_run_metadata,
    write_model_version_metadata,
    write_prediction_run_metadata,
)


def build_input_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [2300.0, 2301.0, 2302.0],
            "high": [2302.0, 2303.0, 2304.0],
            "low": [2298.0, 2299.0, 2300.0],
            "close": [2301.0, 2302.0, 2303.0],
            "volume": [1000, 1001, 1002],
            "return_1": [0.0, 0.001, 0.002],
        }
    )


def build_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [2300.0, 2301.0, 2302.0],
            "close": [2301.0, 2302.0, 2303.0],
            "predicted_signal": ["buy", "hold", "sell"],
            "probability_buy": [0.8, 0.2, 0.1],
            "probability_hold": [0.1, 0.7, 0.2],
            "probability_sell": [0.1, 0.1, 0.7],
        }
    )


def test_normalize_prediction_name_creates_safe_name() -> None:
    assert normalize_prediction_name(" AQOS Prediction Run ") == "aqos_prediction_run"
    assert normalize_prediction_name("XAUUSD-M15@Run!") == "xauusd_m15run"


def test_build_prediction_artifact_reference_hashes_file(tmp_path) -> None:
    prediction_path = tmp_path / "predictions.csv"
    prediction_path.write_text("predicted_signal\nbuy\n", encoding="utf-8")

    artifact = build_prediction_artifact_reference(
        prediction_path,
        PredictionArtifactType.PREDICTIONS,
    )

    assert artifact.name == "predictions.csv"
    assert artifact.artifact_type == PredictionArtifactType.PREDICTIONS
    assert artifact.sha256 == compute_file_sha256(prediction_path)
    assert artifact.size_bytes > 0


def test_build_prediction_artifact_reference_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        build_prediction_artifact_reference(
            tmp_path / "missing.csv",
            PredictionArtifactType.PREDICTIONS,
        )


def test_extract_model_version_reference_reads_model_metadata(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"model-bytes")

    model_metadata = build_model_version_metadata(
        model_name="baseline_random_forest_signal_model",
        model_path=model_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    metadata_path = tmp_path / "model_version_metadata.json"
    write_model_version_metadata(metadata_path, model_metadata)

    model_name, model_id, model_version = extract_model_version_reference(metadata_path)

    assert model_name == "baseline_random_forest_signal_model"
    assert model_id == model_metadata.model_id
    assert model_version == model_metadata.model_version


def test_build_prediction_run_id_is_stable_for_same_inputs(tmp_path) -> None:
    predictions_path = tmp_path / "predictions.csv"
    input_path = tmp_path / "features.csv"

    build_predictions().to_csv(predictions_path, index=False)
    features = build_input_features()
    features.to_csv(input_path, index=False)

    metadata = build_prediction_run_metadata(
        predictions=build_predictions(),
        prediction_path=predictions_path,
        input_features=features,
        input_features_path=input_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    first = build_prediction_run_id(
        model_version=metadata.model_version,
        input_features_fingerprint=metadata.input_features_fingerprint,
        prediction_artifact=metadata.prediction_artifact,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )
    second = build_prediction_run_id(
        model_version=metadata.model_version,
        input_features_fingerprint=metadata.input_features_fingerprint,
        prediction_artifact=metadata.prediction_artifact,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert first == second
    assert first.startswith("prediction_v20260101_000000Z0000_")


def test_build_prediction_run_metadata_creates_traceable_payload(tmp_path) -> None:
    prediction_path = tmp_path / "predictions.csv"
    input_path = tmp_path / "features.csv"
    model_path = tmp_path / "model.joblib"
    model_metadata_path = tmp_path / "model_version_metadata.json"

    predictions = build_predictions()
    features = build_input_features()

    predictions.to_csv(prediction_path, index=False)
    features.to_csv(input_path, index=False)
    model_path.write_bytes(b"model-bytes")

    model_metadata = build_model_version_metadata(
        model_name="baseline_random_forest_signal_model",
        model_path=model_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_id="dataset_123",
        dataset_version="dataset_v1",
        experiment_run_id="run_123",
    )
    write_model_version_metadata(model_metadata_path, model_metadata)

    metadata = build_prediction_run_metadata(
        predictions=predictions,
        prediction_path=prediction_path,
        input_features=features,
        input_features_path=input_path,
        model_version_metadata_path=model_metadata_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
        parameters={"include_probabilities": True},
    )

    payload = metadata.to_dict()

    assert payload["metadata_version"] == PREDICTION_METADATA_VERSION
    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert payload["model_id"] == model_metadata.model_id
    assert payload["model_version"] == model_metadata.model_version
    assert payload["rows"] == 3
    assert payload["prediction_column"] == "predicted_signal"
    assert payload["probability_columns"] == [
        "probability_buy",
        "probability_hold",
        "probability_sell",
    ]
    assert payload["parameters"]["include_probabilities"] is True
    assert payload["prediction_artifact"]["sha256"] == compute_file_sha256(prediction_path)
    assert payload["input_features_artifact"]["sha256"] == compute_file_sha256(input_path)
    assert payload["model_version_metadata_artifact"]["sha256"] == (
        compute_file_sha256(model_metadata_path)
    )
    assert payload["input_features_fingerprint"]["rows"] == 3


def test_build_prediction_run_metadata_rejects_empty_predictions(tmp_path) -> None:
    prediction_path = tmp_path / "predictions.csv"
    input_path = tmp_path / "features.csv"

    pd.DataFrame(columns=["predicted_signal"]).to_csv(prediction_path, index=False)
    build_input_features().to_csv(input_path, index=False)

    with pytest.raises(ValueError, match="empty predictions"):
        build_prediction_run_metadata(
            predictions=pd.DataFrame(),
            prediction_path=prediction_path,
            input_features=build_input_features(),
            input_features_path=input_path,
        )


def test_write_and_read_prediction_run_metadata_roundtrip(tmp_path) -> None:
    prediction_path = tmp_path / "predictions.csv"
    input_path = tmp_path / "features.csv"

    predictions = build_predictions()
    features = build_input_features()

    predictions.to_csv(prediction_path, index=False)
    features.to_csv(input_path, index=False)

    metadata = build_prediction_run_metadata(
        predictions=predictions,
        prediction_path=prediction_path,
        input_features=features,
        input_features_path=input_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    output_path = tmp_path / "metadata" / "prediction_metadata.json"
    written_path = write_prediction_run_metadata(output_path, metadata)
    payload = read_prediction_run_metadata(written_path)

    assert written_path == output_path
    assert payload["prediction_id"] == metadata.prediction_id
    assert payload["rows"] == 3
    assert payload["prediction_artifact"]["sha256"] == metadata.prediction_artifact.sha256


def test_read_prediction_run_metadata_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_prediction_run_metadata(tmp_path / "missing_prediction_metadata.json")


def test_prediction_metadata_json_is_serializable(tmp_path) -> None:
    prediction_path = tmp_path / "predictions.csv"

    predictions = build_predictions()
    features = build_input_features()

    predictions.to_csv(prediction_path, index=False)

    metadata = build_prediction_run_metadata(
        predictions=predictions,
        prediction_path=prediction_path,
        input_features=features,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    payload = json.dumps(metadata.to_dict(), sort_keys=True)

    assert "prediction_id" in payload
    assert "predicted_signal" in payload