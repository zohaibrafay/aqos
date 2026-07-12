from __future__ import annotations

import json

import pandas as pd

from aqos.model_training import (
    ExperimentArtifactType,
    ModelPromotionStage,
    SignalTrainingRunConfig,
    read_model_version_metadata,
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


def test_model_version_metadata_links_model_evaluation_report(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=271,
            evaluation_min_accuracy=0.0,
            evaluation_allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    payload = read_model_version_metadata(output.model_version_metadata_path)

    assert payload["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )
    assert payload["promotion_stage"] == "paper_trading"
    assert payload["is_promotion_ready"] is True
    assert output.model_evaluation_report_path.exists()


def test_experiment_registry_tracks_model_evaluation_artifact(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=273,
            evaluation_min_accuracy=0.0,
        )
    )

    run_payload = json.loads(
        output.experiment_run_metadata_path.read_text(encoding="utf-8")
    )

    artifact_types = {
        artifact["artifact_type"]
        for artifact in run_payload["artifacts"]
    }

    assert ExperimentArtifactType.MODEL_EVALUATION_REPORT.value in artifact_types

    evaluation_artifacts = [
        artifact
        for artifact in run_payload["artifacts"]
        if artifact["artifact_type"] == "model_evaluation_report"
    ]

    assert len(evaluation_artifacts) == 1
    assert evaluation_artifacts[0]["name"] == "model_evaluation_report"
    assert evaluation_artifacts[0]["path"].endswith("model_evaluation_report.json")


def test_training_metrics_file_contains_evaluation_traceability(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=277,
            evaluation_min_accuracy=0.0,
        )
    )

    payload = json.loads(output.metrics_path.read_text(encoding="utf-8"))

    assert payload["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )
    assert payload["model_evaluation_report"]["model_name"] == (
        "baseline_random_forest_signal_model"
    )
    assert payload["model_version_metadata"]["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )


def test_disabled_model_evaluation_does_not_add_evaluation_artifact(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=281,
            enable_model_evaluation=False,
        )
    )

    run_payload = json.loads(
        output.experiment_run_metadata_path.read_text(encoding="utf-8")
    )

    artifact_types = {
        artifact["artifact_type"]
        for artifact in run_payload["artifacts"]
    }

    model_version_payload = read_model_version_metadata(
        output.model_version_metadata_path
    )

    assert "model_evaluation_report" not in artifact_types
    assert output.model_evaluation_report_path is None
    assert output.model_evaluation_report is None
    assert model_version_payload["model_evaluation_report_path"] is None
    assert model_version_payload["promotion_stage"] is None
    assert model_version_payload["is_promotion_ready"] is None