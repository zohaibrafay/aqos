from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    DatasetArtifactType,
    SignalTrainingRunConfig,
    build_dataset_version_metadata,
    build_training_experiment_parameters,
    compute_file_sha256,
    read_experiment_registry,
    train_baseline_signal_model_from_csv,
    write_dataset_version_metadata,
)


def build_valid_training_dataset() -> pd.DataFrame:
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
                "return_1": 0.001 * index,
                "candle_body_ratio": 0.5,
                "target": target,
            }
        )

    return pd.DataFrame(rows)


def test_training_runner_writes_experiment_metadata_and_registry(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=101,
        )
    )

    assert output.experiment_run_metadata_path is not None
    assert output.experiment_registry_path is not None
    assert output.experiment_run is not None
    assert output.experiment_run_metadata_path.exists()
    assert output.experiment_registry_path.exists()

    run_payload = json.loads(
        output.experiment_run_metadata_path.read_text(encoding="utf-8")
    )
    registry = read_experiment_registry(output.experiment_registry_path)

    artifact_types = {
        artifact["artifact_type"]
        for artifact in run_payload["artifacts"]
    }

    assert run_payload["experiment_name"] == "aqos_baseline_signal_model"
    assert run_payload["status"] == "completed"
    assert run_payload["model_name"] == "baseline_random_forest_signal_model"
    assert run_payload["metrics"]["accuracy"] == output.training_result.accuracy
    assert run_payload["parameters"]["n_estimators"] == 20
    assert "training_dataset" in artifact_types
    assert "model" in artifact_types
    assert "metrics" in artifact_types
    assert "quality_report" in artifact_types
    assert "model_version_metadata" in artifact_types
    assert registry["runs"][0]["run_id"] == run_payload["run_id"]


def test_training_runner_can_disable_experiment_registry(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            enable_experiment_registry=False,
            n_estimators=20,
        )
    )

    assert output.experiment_run_metadata_path is None
    assert output.experiment_registry_path is None
    assert output.experiment_run is None
    assert not (output_dir / "experiment_run_metadata.json").exists()
    assert not (output_dir / "experiment_registry.json").exists()


def test_training_runner_auto_discovers_dataset_version_metadata(tmp_path) -> None:
    dataset = build_valid_training_dataset()
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"
    version_metadata_path = tmp_path / "signal_ml_dataset_version.json"

    dataset.to_csv(dataset_path, index=False)

    version_metadata = build_dataset_version_metadata(
        dataframe=dataset,
        dataset_name="signal_ml_training_dataset",
        dataset_path=dataset_path,
        artifact_type=DatasetArtifactType.TRAINING_DATASET,
        source_file_path=dataset_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )
    write_dataset_version_metadata(version_metadata_path, version_metadata)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=103,
        )
    )

    assert output.experiment_run is not None
    assert output.experiment_run.dataset_id == version_metadata.dataset_id
    assert output.experiment_run.dataset_version == version_metadata.dataset_version

    run_payload = json.loads(
        output.experiment_run_metadata_path.read_text(encoding="utf-8")
    )

    artifact_types = {
        artifact["artifact_type"]
        for artifact in run_payload["artifacts"]
    }

    assert "dataset_version_metadata" in artifact_types
    assert run_payload["dataset_id"] == version_metadata.dataset_id
    assert run_payload["dataset_version"] == version_metadata.dataset_version


def test_training_runner_supports_explicit_dataset_version_metadata_path(tmp_path) -> None:
    dataset = build_valid_training_dataset()
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    version_metadata_path = tmp_path / "metadata" / "custom_dataset_version.json"

    dataset.to_csv(dataset_path, index=False)

    version_metadata = build_dataset_version_metadata(
        dataframe=dataset,
        dataset_name="custom_signal_dataset",
        dataset_path=dataset_path,
        artifact_type=DatasetArtifactType.TRAINING_DATASET,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )
    write_dataset_version_metadata(version_metadata_path, version_metadata)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=tmp_path / "artifacts",
            dataset_version_metadata_path=version_metadata_path,
            n_estimators=20,
            random_state=107,
        )
    )

    assert output.experiment_run is not None
    assert output.experiment_run.dataset_id == version_metadata.dataset_id


def test_training_experiment_artifact_hashes_match_files(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=109,
        )
    )

    run_payload = json.loads(
        output.experiment_run_metadata_path.read_text(encoding="utf-8")
    )

    for artifact in run_payload["artifacts"]:
        assert artifact["sha256"] == compute_file_sha256(artifact["path"])
        assert artifact["size_bytes"] > 0


def test_build_training_experiment_parameters_are_serializable() -> None:
    parameters = build_training_experiment_parameters(
        SignalTrainingRunConfig(
            dataset_path="training.csv",
            feature_columns=("open", "close"),
            n_estimators=50,
            max_depth=8,
            validate_schema=True,
            validate_quality=True,
        )
    )

    assert parameters["feature_columns"] == ["open", "close"]
    assert parameters["n_estimators"] == 50
    assert parameters["max_depth"] == 8
    assert parameters["validate_quality"] is True