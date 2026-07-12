from __future__ import annotations

import json

import pandas as pd

from aqos.model_training.cli import run_model_training_cli


def build_raw_ohlcv_dataset(rows: int = 96) -> pd.DataFrame:
    records = []

    for index in range(rows):
        phase = index % 16

        if phase <= 5:
            close_price = 2300.0 + phase * 0.8
        elif phase <= 10:
            close_price = 2304.0 - (phase - 5) * 0.7
        else:
            close_price = 2300.0 + (0.08 if phase % 2 else -0.08)

        open_price = close_price - 0.15
        high_price = max(open_price, close_price) + 1.1
        low_price = min(open_price, close_price) - 1.1

        records.append(
            {
                "timestamp": f"2026-01-01 00:{index:02d}:00",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": 1000 + index,
            }
        )

    return pd.DataFrame(records)


def test_model_training_evaluation_end_to_end_smoke(tmp_path, capsys) -> None:
    raw_path = tmp_path / "raw_ohlcv.csv"
    dataset_path = tmp_path / "training" / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    build_raw_ohlcv_dataset().to_csv(raw_path, index=False)

    build_exit_code = run_model_training_cli(
        [
            "build-dataset",
            "--input-path",
            str(raw_path),
            "--output-path",
            str(dataset_path),
            "--horizon-bars",
            "3",
            "--min-signal-return",
            "0.0002",
        ]
    )

    capsys.readouterr()

    train_exit_code = run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "30",
            "--random-state",
            "331",
            "--evaluation-min-accuracy",
            "0.0",
            "--evaluation-allowed-promotion-stage",
            "paper_trading",
            "--model-evaluation-notes",
            "Sprint 033 smoke test.",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    model_path = output_dir / "baseline_signal_model.joblib"
    metrics_path = output_dir / "baseline_signal_model_metrics.json"
    evaluation_report_path = output_dir / "model_evaluation_report.json"
    model_version_path = output_dir / "model_version_metadata.json"
    experiment_run_path = output_dir / "experiment_run_metadata.json"
    experiment_registry_path = output_dir / "experiment_registry.json"

    assert build_exit_code == 0
    assert train_exit_code == 0

    assert dataset_path.exists()
    assert model_path.exists()
    assert metrics_path.exists()
    assert evaluation_report_path.exists()
    assert model_version_path.exists()
    assert experiment_run_path.exists()
    assert experiment_registry_path.exists()

    assert payload["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )
    assert payload["model_evaluation_report"]["promotion_stage"] == "paper_trading"
    assert payload["model_evaluation_report"]["is_promotion_ready"] is True
    assert payload["model_evaluation_report"]["notes"] == "Sprint 033 smoke test."

    assert payload["model_version_metadata"]["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )
    assert payload["model_version_metadata"]["promotion_stage"] == "paper_trading"
    assert payload["model_version_metadata"]["is_promotion_ready"] is True

    run_payload = json.loads(experiment_run_path.read_text(encoding="utf-8"))

    artifact_types = {
        artifact["artifact_type"]
        for artifact in run_payload["artifacts"]
    }

    assert "training_dataset" in artifact_types
    assert "model" in artifact_types
    assert "metrics" in artifact_types
    assert "quality_report" in artifact_types
    assert "model_version_metadata" in artifact_types
    assert "model_evaluation_report" in artifact_types