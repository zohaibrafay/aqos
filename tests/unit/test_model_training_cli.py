from __future__ import annotations

import json

import pandas as pd

from aqos.model_training.cli import (
    build_model_training_cli_parser,
    parse_feature_columns,
    run_model_training_cli,
)


def build_training_dataset() -> pd.DataFrame:
    rows = []

    for index in range(24):
        rows.append(
            {
                "rsi_14": 20 + index,
                "macd_histogram": 0.5 + index * 0.01,
                "atr_14": 1.2 + index * 0.02,
                "return_5": 0.01 + index * 0.001,
                "target": "buy",
            }
        )

    for index in range(24):
        rows.append(
            {
                "rsi_14": 80 - index,
                "macd_histogram": -0.5 - index * 0.01,
                "atr_14": 1.4 + index * 0.02,
                "return_5": -0.01 - index * 0.001,
                "target": "sell",
            }
        )

    for index in range(24):
        rows.append(
            {
                "rsi_14": 48 + (index % 4),
                "macd_histogram": 0.0,
                "atr_14": 1.0 + index * 0.01,
                "return_5": 0.0,
                "target": "hold",
            }
        )

    return pd.DataFrame(rows)


def test_parse_feature_columns_returns_none_for_empty_value() -> None:
    assert parse_feature_columns("") is None
    assert parse_feature_columns("   ") is None


def test_parse_feature_columns_parses_comma_separated_values() -> None:
    assert parse_feature_columns("rsi_14, macd_histogram, atr_14") == (
        "rsi_14",
        "macd_histogram",
        "atr_14",
    )


def test_model_training_cli_parser_accepts_train_command() -> None:
    parser = build_model_training_cli_parser()

    args = parser.parse_args(
        [
            "train",
            "--dataset-path",
            "dataset.csv",
            "--output-dir",
            "tmp/model_training",
            "--feature-columns",
            "rsi_14,macd_histogram",
            "--n-estimators",
            "20",
        ]
    )

    assert args.command == "train"
    assert args.dataset_path == "dataset.csv"
    assert args.feature_columns == "rsi_14,macd_histogram"
    assert args.n_estimators == 20


def test_model_training_cli_parser_accepts_predict_command() -> None:
    parser = build_model_training_cli_parser()

    args = parser.parse_args(
        [
            "predict",
            "--model-path",
            "model.joblib",
            "--features-path",
            "features.csv",
            "--output-path",
            "predictions.csv",
            "--no-probabilities",
        ]
    )

    assert args.command == "predict"
    assert args.model_path == "model.joblib"
    assert args.features_path == "features.csv"
    assert args.output_path == "predictions.csv"
    assert args.no_probabilities is True


def test_run_model_training_cli_trains_model_from_csv(tmp_path, capsys) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    build_training_dataset().to_csv(dataset_path, index=False)

    exit_code = run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--max-depth",
            "4",
            "--random-state",
            "29",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert (output_dir / "baseline_signal_model.joblib").exists()
    assert (output_dir / "baseline_signal_model_metrics.json").exists()
    assert payload["model_path"].endswith("baseline_signal_model.joblib")
    assert payload["training_result"]["model_name"] == "baseline_random_forest_signal_model"


def test_run_model_training_cli_predicts_from_saved_model(tmp_path, capsys) -> None:
    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(6).to_csv(features_path, index=False)

    train_exit_code = run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--random-state",
            "31",
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
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    predictions = pd.read_csv(predictions_path)

    assert train_exit_code == 0
    assert predict_exit_code == 0
    assert predictions_path.exists()
    assert payload["rows"] == 6
    assert payload["prediction_column"] == "predicted_signal"
    assert "predicted_signal" in predictions.columns
    assert any(column.startswith("probability_") for column in predictions.columns)