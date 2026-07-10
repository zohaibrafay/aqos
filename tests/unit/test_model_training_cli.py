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
                "open": 2300.0 + index,
                "high": 2302.0 + index,
                "low": 2298.0 + index,
                "close": 2301.0 + index,
                "volume": 1000 + index,
                "rsi_14": 22 + index,
                "macd_histogram": 0.4 + index * 0.01,
                "atr_14": 1.2 + index * 0.02,
                "return_5": 0.01 + index * 0.001,
                "target": "buy",
            }
        )

    for index in range(24):
        rows.append(
            {
                "open": 2350.0 - index,
                "high": 2352.0 - index,
                "low": 2348.0 - index,
                "close": 2349.0 - index,
                "volume": 1200 + index,
                "rsi_14": 78 - index,
                "macd_histogram": -0.4 - index * 0.01,
                "atr_14": 1.4 + index * 0.02,
                "return_5": -0.01 - index * 0.001,
                "target": "sell",
            }
        )

    for index in range(24):
        rows.append(
            {
                "open": 2320.0 + (index % 3),
                "high": 2321.0 + (index % 3),
                "low": 2319.0 + (index % 3),
                "close": 2320.5 + (index % 3),
                "volume": 900 + index,
                "rsi_14": 48 + (index % 4),
                "macd_histogram": 0.0,
                "atr_14": 1.0 + index * 0.01,
                "return_5": 0.0,
                "target": "hold",
            }
        )

    return pd.DataFrame(rows)
def build_raw_ohlcv_dataset(rows: int = 48) -> pd.DataFrame:
    records = []

    for index in range(rows):
        phase = index % 12

        if phase <= 4:
            close_price = 2300.0 + phase
        elif phase <= 7:
            close_price = 2304.0 - (phase - 4)
        else:
            close_price = 2300.0 + (0.02 if phase % 2 else 0.0)

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



def test_parse_feature_columns_returns_none_for_empty_value() -> None:
    assert parse_feature_columns("") is None
    assert parse_feature_columns("   ") is None


def test_parse_feature_columns_parses_comma_separated_values() -> None:
    assert parse_feature_columns("rsi_14, macd_histogram, atr_14") == (
        "rsi_14",
        "macd_histogram",
        "atr_14",
    )
def test_model_training_cli_parser_accepts_build_dataset_command() -> None:
    parser = build_model_training_cli_parser()

    args = parser.parse_args(
        [
            "build-dataset",
            "--input-path",
            "raw_ohlcv.csv",
            "--output-path",
            "signal_ml_dataset.csv",
            "--horizon-bars",
            "3",
            "--min-signal-return",
            "0.0002",
            "--no-time-features",
        ]
    )

    assert args.command == "build-dataset"
    assert args.input_path == "raw_ohlcv.csv"
    assert args.output_path == "signal_ml_dataset.csv"
    assert args.horizon_bars == 3
    assert args.min_signal_return == 0.0002
    assert args.no_time_features is True

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

def test_run_model_training_cli_builds_dataset_from_raw_ohlcv_csv(tmp_path, capsys) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    output_path = tmp_path / "training" / "signal_ml_dataset.csv"

    build_raw_ohlcv_dataset().to_csv(input_path, index=False)

    exit_code = run_model_training_cli(
        [
            "build-dataset",
            "--input-path",
            str(input_path),
            "--output-path",
            str(output_path),
            "--horizon-bars",
            "3",
            "--min-signal-return",
            "0.0002",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    dataset = pd.read_csv(output_path)

    assert exit_code == 0
    assert output_path.exists()
    assert payload["dataset_path"].endswith("signal_ml_dataset.csv")
    assert payload["rows"] == 45
    assert payload["validation"]["valid"] is True
    assert "target" in dataset.columns
    assert "return_1" in dataset.columns
    assert "future_return" not in payload["feature_columns"]
    assert "trade_quality_score" not in payload["feature_columns"]


def test_model_training_cli_parser_accepts_quality_report_command() -> None:
    parser = build_model_training_cli_parser()

    args = parser.parse_args(
        [
            "quality-report",
            "--dataset-path",
            "signal_ml_dataset.csv",
            "--output-path",
            "quality.json",
            "--target-column",
            "target",
            "--max-majority-class-ratio",
            "0.9",
        ]
    )

    assert args.command == "quality-report"
    assert args.dataset_path == "signal_ml_dataset.csv"
    assert args.output_path == "quality.json"
    assert args.target_column == "target"
    assert args.max_majority_class_ratio == 0.9

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

def test_run_model_training_cli_writes_quality_report(tmp_path, capsys) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    dataset_path = tmp_path / "training" / "signal_ml_dataset.csv"
    quality_path = tmp_path / "reports" / "quality.json"

    build_raw_ohlcv_dataset().to_csv(input_path, index=False)

    build_exit_code = run_model_training_cli(
        [
            "build-dataset",
            "--input-path",
            str(input_path),
            "--output-path",
            str(dataset_path),
            "--horizon-bars",
            "3",
            "--min-signal-return",
            "0.0002",
        ]
    )
    capsys.readouterr()

    quality_exit_code = run_model_training_cli(
        [
            "quality-report",
            "--dataset-path",
            str(dataset_path),
            "--output-path",
            str(quality_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert build_exit_code == 0
    assert quality_exit_code == 0
    assert quality_path.exists()
    assert payload["report_path"].endswith("quality.json")
    assert payload["quality_report"]["valid"] is True
    assert payload["quality_report"]["target_column"] == "target"
    assert "future_return" not in payload["quality_report"]["feature_columns"]

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
    
def test_model_training_cli_parser_accepts_list_experiments_command() -> None:
    parser = build_model_training_cli_parser()

    args = parser.parse_args(
        [
            "list-experiments",
            "--registry-path",
            "experiment_registry.json",
        ]
    )

    assert args.command == "list-experiments"
    assert args.registry_path == "experiment_registry.json"
    
def test_run_model_training_cli_lists_experiment_registry(tmp_path, capsys) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"
    registry_path = output_dir / "experiment_registry.json"

    build_training_dataset().to_csv(dataset_path, index=False)

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
            "113",
        ]
    )
    capsys.readouterr()

    list_exit_code = run_model_training_cli(
        [
            "list-experiments",
            "--registry-path",
            str(registry_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert train_exit_code == 0
    assert list_exit_code == 0
    assert registry_path.exists()
    assert payload["registry_version"] == "1.0"
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["experiment_name"] == "aqos_baseline_signal_model"
    assert payload["runs"][0]["model_name"] == "baseline_random_forest_signal_model"