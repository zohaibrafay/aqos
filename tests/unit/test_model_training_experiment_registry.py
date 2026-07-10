from __future__ import annotations

import json

import pytest

from aqos.model_training import (
    EXPERIMENT_REGISTRY_VERSION,
    ExperimentArtifactType,
    ExperimentRunStatus,
    append_experiment_run_to_registry,
    build_experiment_artifact,
    build_experiment_run_id,
    build_experiment_run_metadata,
    normalize_experiment_name,
    read_experiment_registry,
    read_experiment_run_metadata,
    sha256_text,
    write_experiment_run_metadata,
)


def test_normalize_experiment_name_creates_safe_name() -> None:
    assert normalize_experiment_name(" AQOS Signal Model ") == "aqos_signal_model"
    assert normalize_experiment_name("XAUUSD-M15@Model!") == "xauusd_m15model"


def test_build_experiment_run_id_is_stable_for_same_inputs() -> None:
    first = build_experiment_run_id(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
    )
    second = build_experiment_run_id(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
    )

    assert first == second
    assert first.startswith("aqos_signal_model_20260101_000000Z0000_")


def test_build_experiment_run_id_changes_when_dataset_changes() -> None:
    first = build_experiment_run_id(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
    )
    second = build_experiment_run_id(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v2",
        model_name="baseline_random_forest_signal_model",
    )

    assert first != second


def test_build_experiment_artifact_hashes_file(tmp_path) -> None:
    artifact_path = tmp_path / "metrics.json"
    artifact_path.write_text('{"accuracy": 1.0}', encoding="utf-8")

    artifact = build_experiment_artifact(
        artifact_path,
        ExperimentArtifactType.METRICS,
    )

    assert artifact.name == "metrics.json"
    assert artifact.artifact_type == ExperimentArtifactType.METRICS
    assert artifact.sha256 == sha256_text('{"accuracy": 1.0}')
    assert artifact.size_bytes > 0


def test_build_experiment_artifact_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        build_experiment_artifact(
            tmp_path / "missing.joblib",
            ExperimentArtifactType.MODEL,
        )


def test_build_experiment_run_metadata_creates_serializable_payload(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    metrics_path = tmp_path / "metrics.json"

    model_path.write_bytes(b"model-bytes")
    metrics_path.write_text('{"accuracy": 0.9}', encoding="utf-8")

    model_artifact = build_experiment_artifact(
        model_path,
        ExperimentArtifactType.MODEL,
    )
    metrics_artifact = build_experiment_artifact(
        metrics_path,
        ExperimentArtifactType.METRICS,
    )

    metadata = build_experiment_run_metadata(
        experiment_name="AQOS Signal Model",
        status=ExperimentRunStatus.COMPLETED,
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_id="dataset_123",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
        parameters={"n_estimators": 20},
        metrics={"accuracy": 0.9},
        artifacts=(model_artifact, metrics_artifact),
        tags=("sprint-030", "unit-test"),
        notes="registry test",
    )

    payload = metadata.to_dict()

    assert payload["registry_version"] == EXPERIMENT_REGISTRY_VERSION
    assert payload["experiment_name"] == "AQOS Signal Model"
    assert payload["status"] == "completed"
    assert payload["dataset_id"] == "dataset_123"
    assert payload["dataset_version"] == "dataset_v1"
    assert payload["parameters"]["n_estimators"] == 20
    assert payload["metrics"]["accuracy"] == 0.9
    assert len(payload["artifacts"]) == 2
    assert payload["tags"] == ["sprint-030", "unit-test"]


def test_write_and_read_experiment_run_metadata_roundtrip(tmp_path) -> None:
    metadata = build_experiment_run_metadata(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
    )

    output_path = tmp_path / "runs" / "run.json"
    written_path = write_experiment_run_metadata(output_path, metadata)
    payload = read_experiment_run_metadata(written_path)

    assert written_path == output_path
    assert payload["run_id"] == metadata.run_id
    assert payload["experiment_name"] == "AQOS Signal Model"


def test_read_experiment_run_metadata_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_experiment_run_metadata(tmp_path / "missing.json")


def test_read_experiment_registry_returns_empty_registry_when_missing(tmp_path) -> None:
    registry = read_experiment_registry(tmp_path / "registry.json")

    assert registry == {
        "registry_version": EXPERIMENT_REGISTRY_VERSION,
        "runs": [],
    }


def test_append_experiment_run_to_registry_writes_sorted_runs(tmp_path) -> None:
    registry_path = tmp_path / "experiment_registry.json"

    newer = build_experiment_run_metadata(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-02T00:00:00+00:00",
        dataset_version="dataset_v2",
        model_name="baseline_random_forest_signal_model",
    )
    older = build_experiment_run_metadata(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
    )

    append_experiment_run_to_registry(registry_path, newer)
    append_experiment_run_to_registry(registry_path, older)

    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    assert registry["registry_version"] == EXPERIMENT_REGISTRY_VERSION
    assert [run["run_id"] for run in registry["runs"]] == [
        older.run_id,
        newer.run_id,
    ]


def test_append_experiment_run_to_registry_replaces_existing_run(tmp_path) -> None:
    registry_path = tmp_path / "experiment_registry.json"

    original = build_experiment_run_metadata(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
        metrics={"accuracy": 0.8},
    )
    updated = build_experiment_run_metadata(
        experiment_name="AQOS Signal Model",
        created_at_utc="2026-01-01T00:00:00+00:00",
        dataset_version="dataset_v1",
        model_name="baseline_random_forest_signal_model",
        metrics={"accuracy": 0.95},
    )

    append_experiment_run_to_registry(registry_path, original)
    append_experiment_run_to_registry(registry_path, updated)

    registry = read_experiment_registry(registry_path)

    assert len(registry["runs"]) == 1
    assert registry["runs"][0]["metrics"]["accuracy"] == 0.95