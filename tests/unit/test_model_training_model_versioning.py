from __future__ import annotations

import json

import pytest

from aqos.model_training import (
    MODEL_METADATA_VERSION,
    ModelArtifactFormat,
    build_model_artifact_reference,
    build_model_version_metadata,
    build_model_version_string,
    compute_file_sha256,
    infer_model_artifact_format,
    normalize_model_name,
    read_model_version_metadata,
    write_model_version_metadata,
)


def test_normalize_model_name_creates_safe_name() -> None:
    assert normalize_model_name(" AQOS Signal Model ") == "aqos_signal_model"
    assert normalize_model_name("Baseline-RF@Model!") == "baseline_rfmodel"


def test_infer_model_artifact_format_detects_known_extensions() -> None:
    assert infer_model_artifact_format("model.joblib") == ModelArtifactFormat.JOBLIB
    assert infer_model_artifact_format("model.pkl") == ModelArtifactFormat.PICKLE
    assert infer_model_artifact_format("model.pickle") == ModelArtifactFormat.PICKLE
    assert infer_model_artifact_format("model.onnx") == ModelArtifactFormat.ONNX
    assert infer_model_artifact_format("model.bin") == ModelArtifactFormat.UNKNOWN


def test_build_model_artifact_reference_hashes_file(tmp_path) -> None:
    model_path = tmp_path / "baseline_signal_model.joblib"
    model_path.write_bytes(b"model-bytes")

    artifact = build_model_artifact_reference(model_path)

    assert artifact.path.endswith("baseline_signal_model.joblib")
    assert artifact.sha256 == compute_file_sha256(model_path)
    assert artifact.size_bytes == len(b"model-bytes")
    assert artifact.artifact_format == ModelArtifactFormat.JOBLIB


def test_build_model_artifact_reference_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        build_model_artifact_reference(tmp_path / "missing.joblib")


def test_build_model_version_string_is_stable_for_same_inputs(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"model-bytes")

    artifact = build_model_artifact_reference(model_path)

    first = build_model_version_string(
        model_name="baseline_random_forest_signal_model",
        model_artifact=artifact,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )
    second = build_model_version_string(
        model_name="baseline_random_forest_signal_model",
        model_artifact=artifact,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert first == second
    assert first.startswith("baseline_random_forest_signal_model_v20260101_000000Z0000_")


def test_build_model_version_metadata_creates_traceable_payload(tmp_path) -> None:
    model_path = tmp_path / "baseline_signal_model.joblib"
    model_path.write_bytes(b"model-bytes")

    metadata = build_model_version_metadata(
        model_name="baseline_random_forest_signal_model",
        model_path=model_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_id="dataset_abc",
        dataset_version="dataset_v1",
        experiment_run_id="run_123",
        training_parameters={"n_estimators": 20},
        training_metrics={"accuracy": 0.91},
        description="Sprint 030 model version test.",
        tags=("sprint-030", "unit-test"),
    )

    payload = metadata.to_dict()

    assert payload["metadata_version"] == MODEL_METADATA_VERSION
    assert payload["model_id"].startswith("baseline_random_forest_signal_model_")
    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert payload["dataset_id"] == "dataset_abc"
    assert payload["dataset_version"] == "dataset_v1"
    assert payload["experiment_run_id"] == "run_123"
    assert payload["training_parameters"]["n_estimators"] == 20
    assert payload["training_metrics"]["accuracy"] == 0.91
    assert payload["tags"] == ["sprint-030", "unit-test"]
    assert payload["model_artifact"]["sha256"] == compute_file_sha256(model_path)


def test_write_and_read_model_version_metadata_roundtrip(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"model-bytes")

    metadata = build_model_version_metadata(
        model_name="baseline_random_forest_signal_model",
        model_path=model_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    output_path = tmp_path / "metadata" / "model_version.json"
    written_path = write_model_version_metadata(output_path, metadata)
    payload = read_model_version_metadata(written_path)

    assert written_path == output_path
    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert payload["model_version"] == metadata.model_version
    assert payload["model_artifact"]["sha256"] == metadata.model_artifact.sha256


def test_read_model_version_metadata_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_model_version_metadata(tmp_path / "missing_model_version.json")


def test_model_version_metadata_json_is_serializable(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"model-bytes")

    metadata = build_model_version_metadata(
        model_name="baseline_random_forest_signal_model",
        model_path=model_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    payload = json.dumps(metadata.to_dict(), sort_keys=True)

    assert "baseline_random_forest_signal_model" in payload