from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    SignalTrainingRunConfig,
    compute_file_sha256,
    train_baseline_signal_model_from_csv,
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


def test_experiment_registry_links_model_version_metadata_artifact(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=137,
        )
    )

    run_payload = json.loads(
        output.experiment_run_metadata_path.read_text(encoding="utf-8")
    )

    model_version_artifacts = [
        artifact
        for artifact in run_payload["artifacts"]
        if artifact["artifact_type"] == "model_version_metadata"
    ]

    assert output.model_version_metadata_path is not None
    assert output.model_version_metadata_path.exists()
    assert len(model_version_artifacts) == 1

    artifact = model_version_artifacts[0]

    assert artifact["name"] == "model_version_metadata"
    assert artifact["path"].endswith("model_version_metadata.json")
    assert artifact["sha256"] == compute_file_sha256(output.model_version_metadata_path)

    model_version_payload = json.loads(
        output.model_version_metadata_path.read_text(encoding="utf-8")
    )

    assert model_version_payload["experiment_run_id"] == run_payload["run_id"]
    assert model_version_payload["model_artifact"]["path"].endswith(
        "baseline_signal_model.joblib"
    )