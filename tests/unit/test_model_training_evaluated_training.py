from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    ModelPromotionStage,
    SignalTrainingRunConfig,
    build_training_model_evaluation_thresholds,
    read_model_evaluation_report,
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


def test_training_runner_writes_model_evaluation_report(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=251,
            evaluation_min_accuracy=0.0,
            evaluation_allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        )
    )

    assert output.model_evaluation_report_path is not None
    assert output.model_evaluation_report_path.exists()
    assert output.model_evaluation_report is not None

    payload = read_model_evaluation_report(output.model_evaluation_report_path)

    assert payload["metadata_version"] == "1.0"
    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert payload["model_id"] == output.model_version_metadata.model_id
    assert payload["model_version"] == output.model_version_metadata.model_version
    assert payload["experiment_run_id"] == output.experiment_run.run_id
    assert payload["promotion_stage"] == "paper_trading"
    assert payload["is_promotion_ready"] is True
    assert payload["metrics"]["accuracy"] == output.training_result.accuracy


def test_training_runner_can_disable_model_evaluation_report(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=253,
            enable_model_evaluation=False,
        )
    )

    assert output.model_evaluation_report_path is None
    assert output.model_evaluation_report is None
    assert not (output_dir / "model_evaluation_report.json").exists()


def test_training_runner_supports_custom_model_evaluation_report_filename(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=257,
            evaluation_min_accuracy=0.0,
            model_evaluation_report_filename="custom_model_evaluation_report.json",
        )
    )

    assert output.model_evaluation_report_path is not None
    assert output.model_evaluation_report_path.name == (
        "custom_model_evaluation_report.json"
    )
    assert output.model_evaluation_report_path.exists()


def test_training_runner_model_evaluation_can_fail_without_raising(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=259,
            evaluation_min_accuracy=1.0,
            fail_on_model_evaluation_error=False,
        )
    )

    assert output.model_evaluation_report is not None
    assert output.model_evaluation_report.status.value == "failed"
    assert output.model_evaluation_report.is_promotion_ready is False
    assert output.model_evaluation_report.promotion_stage == ModelPromotionStage.BLOCKED


def test_training_runner_model_evaluation_can_raise_on_failure(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="Model evaluation failed"):
        train_baseline_signal_model_from_csv(
            SignalTrainingRunConfig(
                dataset_path=dataset_path,
                output_dir=output_dir,
                n_estimators=20,
                random_state=263,
                evaluation_min_accuracy=1.0,
                fail_on_model_evaluation_error=True,
            )
        )

    assert (output_dir / "model_evaluation_report.json").exists()


def test_training_output_dict_contains_model_evaluation_report(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=267,
            evaluation_min_accuracy=0.0,
        )
    )

    payload = output.to_dict()

    assert payload["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )
    assert payload["model_evaluation_report"]["model_name"] == (
        "baseline_random_forest_signal_model"
    )
    assert payload["model_evaluation_report"]["metrics"]["accuracy"] == (
        output.training_result.accuracy
    )


def test_training_model_evaluation_thresholds_builder(tmp_path) -> None:
    config = SignalTrainingRunConfig(
        dataset_path=tmp_path / "dataset.csv",
        evaluation_min_accuracy=0.6,
        evaluation_min_macro_f1=0.5,
        evaluation_max_log_loss=0.9,
        evaluation_min_test_samples=50,
        evaluation_required_classes=("buy", "sell", "hold"),
        evaluation_allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
    )

    thresholds = build_training_model_evaluation_thresholds(config)

    assert thresholds.min_accuracy == 0.6
    assert thresholds.min_macro_f1 == 0.5
    assert thresholds.max_log_loss == 0.9
    assert thresholds.min_test_samples == 50
    assert thresholds.required_classes == ("buy", "sell", "hold")
    assert thresholds.allowed_promotion_stage == ModelPromotionStage.PAPER_TRADING


def test_model_evaluation_report_file_is_valid_json(tmp_path) -> None:
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=269,
            evaluation_min_accuracy=0.0,
        )
    )

    payload = json.loads(
        output.model_evaluation_report_path.read_text(encoding="utf-8")
    )

    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert "thresholds" in payload
    assert "metrics" in payload