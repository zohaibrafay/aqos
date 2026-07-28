from __future__ import annotations

import json

import pandas as pd

from aqos.model_training.cli import run_model_training_cli


def build_raw_ohlcv_dataset(rows: int = 120) -> pd.DataFrame:
    records = []

    for index in range(rows):
        phase = index % 20

        if phase <= 6:
            close_price = 2300.0 + phase * 0.9
        elif phase <= 13:
            close_price = 2306.0 - (phase - 6) * 0.8
        else:
            close_price = 2300.0 + (0.12 if phase % 2 else -0.12)

        open_price = close_price - 0.2
        high_price = max(open_price, close_price) + 1.2
        low_price = min(open_price, close_price) - 1.2

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


def test_model_training_promotion_gated_prediction_end_to_end_smoke(
    tmp_path,
    capsys,
) -> None:
    raw_path = tmp_path / "raw_ohlcv.csv"
    dataset_path = tmp_path / "training" / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"
    features_path = tmp_path / "features.csv"
    predictions_path = tmp_path / "predictions" / "signals.csv"

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

    built_dataset = pd.read_csv(dataset_path)
    built_dataset.drop(columns=["target"]).head(12).to_csv(
        features_path,
        index=False,
    )

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
            "347",
            "--evaluation-min-accuracy",
            "0.0",
            "--evaluation-allowed-promotion-stage",
            "paper_trading",
            "--model-evaluation-notes",
            "Sprint 034 promotion smoke test.",
        ]
    )
    capsys.readouterr()

    promote_exit_code = run_model_training_cli(
        [
            "promote-model",
            "--model-version-metadata-path",
            str(output_dir / "model_version_metadata.json"),
            "--target-stage",
            "paper_trading",
            "--promotion-notes",
            "Sprint 034 smoke promotion.",
            "--promotion-tags",
            "aqos,paper,smoke",
        ]
    )
    capsys.readouterr()

    predict_exit_code = run_model_training_cli(
        [
            "predict",
            "--model-path",
            str(output_dir / "baseline_signal_model.joblib"),
            "--features-path",
            str(features_path),
            "--output-path",
            str(predictions_path),
            "--model-version-metadata-path",
            str(output_dir / "model_version_metadata.json"),
            "--require-model-promotion",
            "--promotion-registry-path",
            str(output_dir / "model_promotion_registry.json"),
            "--required-promotion-stage",
            "paper_trading",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert build_exit_code == 0
    assert train_exit_code == 0
    assert promote_exit_code == 0
    assert predict_exit_code == 0

    assert dataset_path.exists()
    assert output_dir.joinpath("baseline_signal_model.joblib").exists()
    assert output_dir.joinpath("model_evaluation_report.json").exists()
    assert output_dir.joinpath("model_version_metadata.json").exists()
    assert output_dir.joinpath("model_promotion_review.json").exists()
    assert output_dir.joinpath("model_promotion_registry.json").exists()
    assert predictions_path.exists()

    promotion_review = json.loads(
        output_dir.joinpath("model_promotion_review.json").read_text(
            encoding="utf-8"
        )
    )
    promotion_registry = json.loads(
        output_dir.joinpath("model_promotion_registry.json").read_text(
            encoding="utf-8"
        )
    )

    assert promotion_review["approved"] is True
    assert promotion_review["target_stage"] == "paper_trading"

    assert len(promotion_registry["promotions"]) == 1
    assert promotion_registry["promotions"][0]["approved"] is True
    assert promotion_registry["promotions"][0]["target_stage"] == "paper_trading"

    assert payload["model_promotion_gate_decision"]["approved"] is True
    assert payload["model_promotion_gate_decision"]["required_stage"] == (
        "paper_trading"
    )
    assert payload["rows"] == 12