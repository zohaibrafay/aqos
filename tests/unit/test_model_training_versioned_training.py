from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    DatasetArtifactType,
    SignalTrainingRunConfig,
    build_dataset_version_metadata,
    build_training_model_version_metadata,
    compute_file_sha256,
    read_model_version_metadata,
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


def test_training_runner_writes_model_version_metadata(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=121,
        )
    )

    assert output.model_version_metadata_path is not None
    assert output.model_version_metadata_path.exists()
    assert output.model_version_metadata is not None

    payload = read_model_version_metadata(output.model_version_metadata_path)

    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert payload["model_id"].startswith("baseline_random_forest_signal_model_")
    assert payload["model_artifact"]["path"].endswith("baseline_signal_model.joblib")
    assert payload["model_artifact"]["sha256"] == compute_file_sha256(output.model_path)
    assert payload["experiment_run_id"] == output.experiment_run.run_id
    assert payload["training_parameters"]["n_estimators"] == 20
    assert payload["training_metrics"]["accuracy"] == output.training_result.accuracy


def test_training_runner_can_disable_model_versioning(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            enable_model_versioning=False,
            n_estimators=20,
        )
    )

    assert output.model_version_metadata_path is None
    assert output.model_version_metadata is None
    assert not (output_dir / "model_version_metadata.json").exists()


def test_training_runner_model_version_uses_dataset_version_reference(tmp_path) -> None:
    dataset = build_valid_training_dataset()
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    version_metadata_path = tmp_path / "signal_ml_dataset_version.json"

    dataset.to_csv(dataset_path, index=False)

    dataset_version_metadata = build_dataset_version_metadata(
        dataframe=dataset,
        dataset_name="signal_ml_training_dataset",
        dataset_path=dataset_path,
        artifact_type=DatasetArtifactType.TRAINING_DATASET,
        source_file_path=dataset_path,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )
    write_dataset_version_metadata(version_metadata_path, dataset_version_metadata)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=tmp_path / "artifacts",
            n_estimators=20,
            random_state=127,
        )
    )

    assert output.model_version_metadata is not None
    assert output.model_version_metadata.dataset_id == dataset_version_metadata.dataset_id
    assert output.model_version_metadata.dataset_version == (
        dataset_version_metadata.dataset_version
    )


def test_training_metrics_file_contains_model_version_metadata(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=131,
        )
    )

    metrics = json.loads(output.metrics_path.read_text(encoding="utf-8"))

    assert metrics["model_version_metadata_path"].endswith("model_version_metadata.json")
    assert metrics["model_version_metadata"]["model_name"] == (
        "baseline_random_forest_signal_model"
    )
    assert metrics["model_version_metadata"]["model_artifact"]["sha256"] == (
        compute_file_sha256(output.model_path)
    )


def test_build_training_model_version_metadata_returns_none_when_disabled(tmp_path) -> None:
    model_path = tmp_path / "model.joblib"
    model_path.write_bytes(b"model")

    class TrainingResult:
        model_name = "baseline_random_forest_signal_model"

        def to_dict(self):
            return {"model_name": self.model_name, "accuracy": 0.9}

    metadata = build_training_model_version_metadata(
        run_config=SignalTrainingRunConfig(
            dataset_path="unused.csv",
            enable_model_versioning=False,
        ),
        model_path=model_path,
        training_result=TrainingResult(),
        experiment_run=None,
    )

    assert metadata is None