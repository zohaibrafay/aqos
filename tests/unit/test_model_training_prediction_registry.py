from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    PREDICTION_METADATA_VERSION,
    PREDICTION_REGISTRY_VERSION,
    append_prediction_run_to_registry,
    build_prediction_registry_entry,
    build_prediction_run_metadata,
    find_prediction_registry_run,
    list_prediction_registry_runs,
    read_prediction_registry,
)


def build_input_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [2300.0, 2301.0, 2302.0],
            "high": [2302.0, 2303.0, 2304.0],
            "low": [2298.0, 2299.0, 2300.0],
            "close": [2301.0, 2302.0, 2303.0],
            "volume": [1000, 1001, 1002],
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


def build_prediction_metadata(tmp_path, created_at_utc: str = "2026-01-01T00:00:00+00:00"):
    safe_timestamp = (
    created_at_utc.replace("-", "")
    .replace(":", "")
    .replace("+", "Z")
    .replace("T", "_")
)

    prediction_path = tmp_path / f"predictions_{safe_timestamp}.csv"
    features_path = tmp_path / f"features_{safe_timestamp}.csv"

    predictions = build_predictions()
    features = build_input_features()

    predictions.to_csv(prediction_path, index=False)
    features.to_csv(features_path, index=False)

    return build_prediction_run_metadata(
        predictions=predictions,
        prediction_path=prediction_path,
        input_features=features,
        input_features_path=features_path,
        created_at_utc=created_at_utc,
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
    )


def test_read_prediction_registry_returns_empty_registry_when_missing(tmp_path) -> None:
    registry = read_prediction_registry(tmp_path / "prediction_registry.json")

    assert registry == {
        "registry_version": PREDICTION_REGISTRY_VERSION,
        "prediction_metadata_version": PREDICTION_METADATA_VERSION,
        "runs": [],
    }


def test_build_prediction_registry_entry_contains_trace_fields(tmp_path) -> None:
    metadata = build_prediction_metadata(tmp_path)
    metadata_path = tmp_path / "prediction_run_metadata.json"

    entry = build_prediction_registry_entry(metadata, metadata_path)

    assert entry["prediction_id"] == metadata.prediction_id
    assert entry["created_at_utc"] == metadata.created_at_utc
    assert entry["metadata_path"].endswith("prediction_run_metadata.json")
    assert entry["prediction_path"].endswith(".csv")
    assert entry["prediction_sha256"] == metadata.prediction_artifact.sha256
    assert entry["input_features_sha256"] == (
        metadata.input_features_fingerprint.content_sha256
    )
    assert entry["input_features_rows"] == 3
    assert entry["input_features_columns_count"] == 5
    assert entry["probability_columns"] == [
        "probability_buy",
        "probability_hold",
        "probability_sell",
    ]


def test_append_prediction_run_to_registry_writes_registry_file(tmp_path) -> None:
    registry_path = tmp_path / "prediction_registry.json"
    metadata_path = tmp_path / "prediction_run_metadata.json"
    metadata = build_prediction_metadata(tmp_path)

    written_path = append_prediction_run_to_registry(
        registry_path,
        metadata,
        metadata_path,
    )

    registry = json.loads(written_path.read_text(encoding="utf-8"))

    assert written_path == registry_path
    assert registry["registry_version"] == PREDICTION_REGISTRY_VERSION
    assert registry["prediction_metadata_version"] == PREDICTION_METADATA_VERSION
    assert len(registry["runs"]) == 1
    assert registry["runs"][0]["prediction_id"] == metadata.prediction_id


def test_append_prediction_run_to_registry_sorts_runs_by_created_at(tmp_path) -> None:
    registry_path = tmp_path / "prediction_registry.json"

    newer = build_prediction_metadata(
        tmp_path,
        created_at_utc="2026-01-02T00:00:00+00:00",
    )
    older = build_prediction_metadata(
        tmp_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    append_prediction_run_to_registry(
        registry_path,
        newer,
        tmp_path / "newer_metadata.json",
    )
    append_prediction_run_to_registry(
        registry_path,
        older,
        tmp_path / "older_metadata.json",
    )

    registry = read_prediction_registry(registry_path)

    assert [run["prediction_id"] for run in registry["runs"]] == [
        older.prediction_id,
        newer.prediction_id,
    ]


def test_append_prediction_run_to_registry_replaces_existing_prediction_id(tmp_path) -> None:
    registry_path = tmp_path / "prediction_registry.json"
    metadata = build_prediction_metadata(tmp_path)

    append_prediction_run_to_registry(
        registry_path,
        metadata,
        tmp_path / "first_metadata.json",
    )
    append_prediction_run_to_registry(
        registry_path,
        metadata,
        tmp_path / "second_metadata.json",
    )

    registry = read_prediction_registry(registry_path)

    assert len(registry["runs"]) == 1
    assert registry["runs"][0]["metadata_path"].endswith("second_metadata.json")


def test_list_prediction_registry_runs_returns_tuple(tmp_path) -> None:
    registry_path = tmp_path / "prediction_registry.json"
    metadata = build_prediction_metadata(tmp_path)

    append_prediction_run_to_registry(
        registry_path,
        metadata,
        tmp_path / "prediction_run_metadata.json",
    )

    runs = list_prediction_registry_runs(registry_path)

    assert isinstance(runs, tuple)
    assert len(runs) == 1
    assert runs[0]["prediction_id"] == metadata.prediction_id


def test_find_prediction_registry_run_returns_matching_run(tmp_path) -> None:
    registry_path = tmp_path / "prediction_registry.json"
    metadata = build_prediction_metadata(tmp_path)

    append_prediction_run_to_registry(
        registry_path,
        metadata,
        tmp_path / "prediction_run_metadata.json",
    )

    found = find_prediction_registry_run(registry_path, metadata.prediction_id)
    missing = find_prediction_registry_run(registry_path, "missing")

    assert found is not None
    assert found["prediction_id"] == metadata.prediction_id
    assert missing is None