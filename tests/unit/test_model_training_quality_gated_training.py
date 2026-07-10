from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    SignalTrainingRunConfig,
    build_training_dataset_quality_report,
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


def test_training_runner_writes_quality_report_before_training(tmp_path) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=81,
        )
    )

    assert output.model_path.exists()
    assert output.metrics_path.exists()
    assert output.quality_report_path is not None
    assert output.quality_report_path.exists()
    assert output.quality_report is not None
    assert output.quality_report.valid is True

    metrics = json.loads(output.metrics_path.read_text(encoding="utf-8"))

    assert metrics["quality_report_path"].endswith("training_dataset_quality.json")
    assert metrics["quality_report"]["valid"] is True


def test_training_quality_report_can_be_disabled(tmp_path) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    build_valid_training_dataset().to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            validate_quality=False,
            n_estimators=20,
        )
    )

    assert output.model_path.exists()
    assert output.quality_report_path is None
    assert output.quality_report is None


def test_training_runner_rejects_quality_invalid_dataset(tmp_path) -> None:
    dataset = build_valid_training_dataset()
    dataset["target"] = "buy"

    dataset_path = tmp_path / "bad_training.csv"
    dataset.to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="Dataset validation failed|Dataset quality check failed"):
        train_baseline_signal_model_from_csv(
            SignalTrainingRunConfig(
                dataset_path=dataset_path,
                output_dir=tmp_path / "artifacts",
                n_estimators=20,
            )
        )


def test_build_training_dataset_quality_report_returns_report() -> None:
    report = build_training_dataset_quality_report(
        build_valid_training_dataset(),
        SignalTrainingRunConfig(dataset_path="unused.csv"),
    )

    assert report is not None
    assert report.valid is True
    assert report.target_column == "target"
    assert report.target_distribution == {
        "buy": 12,
        "hold": 12,
        "sell": 12,
    }