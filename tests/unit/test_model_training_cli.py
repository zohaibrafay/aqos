from __future__ import annotations

import json

import pandas as pd
import pytest
from aqos.model_training.cli import (
    build_model_training_cli_parser,
    build_training_run_config_from_args,
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
            "artifacts",
            "--target-column",
            "target",
            "--test-size",
            "0.2",
            "--random-state",
            "123",
            "--n-estimators",
            "20",
            "--max-depth",
            "4",
            "--min-samples-leaf",
            "2",
            "--model-filename",
            "model.joblib",
            "--metrics-filename",
            "metrics.json",
            "--no-schema-validation",
            "--no-quality-validation",
            "--no-experiment-registry",
            "--no-model-evaluation",
            "--model-evaluation-report-filename",
            "custom_model_evaluation_report.json",
            "--fail-on-model-evaluation-error",
            "--evaluation-min-accuracy",
            "0.6",
            "--evaluation-min-macro-f1",
            "0.5",
            "--evaluation-max-log-loss",
            "0.9",
            "--evaluation-min-test-samples",
            "50",
            "--evaluation-required-classes",
            "buy,sell,hold",
            "--evaluation-allowed-promotion-stage",
            "paper_trading",
            "--model-evaluation-notes",
            "CLI evaluation test",
        ]
    )

    assert args.command == "train"
    assert args.dataset_path == "dataset.csv"
    assert args.output_dir == "artifacts"
    assert args.target_column == "target"
    assert args.test_size == 0.2
    assert args.random_state == 123
    assert args.n_estimators == 20
    assert args.max_depth == 4
    assert args.min_samples_leaf == 2
    assert args.model_filename == "model.joblib"
    assert args.metrics_filename == "metrics.json"
    assert args.no_schema_validation is True
    assert args.no_quality_validation is True
    assert args.no_experiment_registry is True
    assert args.no_model_evaluation is True
    assert args.model_evaluation_report_filename == "custom_model_evaluation_report.json"
    assert args.fail_on_model_evaluation_error is True
    assert args.evaluation_min_accuracy == 0.6
    assert args.evaluation_min_macro_f1 == 0.5
    assert args.evaluation_max_log_loss == 0.9
    assert args.evaluation_min_test_samples == 50
    assert args.evaluation_required_classes == "buy,sell,hold"
    assert args.evaluation_allowed_promotion_stage == "paper_trading"
    assert args.model_evaluation_notes == "CLI evaluation test"

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
            "--model-version-metadata-path",
            "model_version_metadata.json",
            "--prediction-metadata-filename",
            "custom_prediction_metadata.json",
            "--prediction-registry-filename",
            "custom_prediction_registry.json",
            "--prediction-validation-report-filename",
            "custom_validation_report.json",
            "--confidence-column",
            "confidence",
            "--min-confidence",
            "0.7",
            "--max-low-confidence-ratio",
            "0.25",
            "--probability-sum-tolerance",
            "0.02",
            "--no-probabilities",
            "--no-prediction-versioning",
            "--no-prediction-registry",
            "--no-prediction-validation",
            "--no-fail-on-prediction-validation-error",
            "--require-model-version",
            "--require-probability-columns",
            "--require-confidence",
            "--no-require-trained-feature-columns",
            "--keep-invalid-prediction-artifact",
        ]
    )

    assert args.command == "predict"
    assert args.model_path == "model.joblib"
    assert args.features_path == "features.csv"
    assert args.output_path == "predictions.csv"
    assert args.model_version_metadata_path == "model_version_metadata.json"
    assert args.prediction_metadata_filename == "custom_prediction_metadata.json"
    assert args.prediction_registry_filename == "custom_prediction_registry.json"
    assert args.prediction_validation_report_filename == "custom_validation_report.json"
    assert args.confidence_column == "confidence"
    assert args.min_confidence == 0.7
    assert args.max_low_confidence_ratio == 0.25
    assert args.probability_sum_tolerance == 0.02
    assert args.no_probabilities is True
    assert args.no_prediction_versioning is True
    assert args.no_prediction_registry is True
    assert args.no_prediction_validation is True
    assert args.no_fail_on_prediction_validation_error is True
    assert args.require_model_version is True
    assert args.require_probability_columns is True
    assert args.require_confidence is True
    assert args.no_require_trained_feature_columns is True
    assert args.keep_invalid_prediction_artifact is True


def test_model_training_cli_parser_accepts_list_predictions_command() -> None:
    parser = build_model_training_cli_parser()

    args = parser.parse_args(
        [
            "list-predictions",
            "--registry-path",
            "prediction_registry.json",
        ]
    )

    assert args.command == "list-predictions"
    assert args.registry_path == "prediction_registry.json"

def test_run_model_training_cli_predict_writes_prediction_metadata(tmp_path, capsys) -> None:
    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

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
            "181",
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
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    prediction_metadata_path = predictions_path.parent / "prediction_run_metadata.json"

    assert train_exit_code == 0
    assert predict_exit_code == 0
    assert predictions_path.exists()
    assert prediction_metadata_path.exists()
    assert payload["prediction_metadata_path"].endswith("prediction_run_metadata.json")
    assert payload["prediction_metadata"]["model_name"] == (
        "baseline_random_forest_signal_model"
    )
    assert payload["prediction_metadata"]["model_version"] is not None
    assert payload["prediction_metadata"]["rows"] == 8

def test_run_model_training_cli_predict_can_disable_prediction_metadata(tmp_path, capsys) -> None:
    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--random-state",
            "183",
        ]
    )
    capsys.readouterr()

    exit_code = run_model_training_cli(
        [
            "predict",
            "--model-path",
            str(output_dir / "baseline_signal_model.joblib"),
            "--features-path",
            str(features_path),
            "--output-path",
            str(predictions_path),
            "--no-prediction-versioning",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert predictions_path.exists()
    assert payload["prediction_metadata_path"] is None
    assert payload["prediction_metadata"] is None
    assert not (predictions_path.parent / "prediction_run_metadata.json").exists()

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
    
def test_run_model_training_cli_list_predictions_prints_prediction_registry(
    tmp_path,
    capsys,
) -> None:
    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

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
            "197",
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
        ]
    )
    capsys.readouterr()

    list_exit_code = run_model_training_cli(
        [
            "list-predictions",
            "--registry-path",
            str(predictions_path.parent / "prediction_registry.json"),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert train_exit_code == 0
    assert predict_exit_code == 0
    assert list_exit_code == 0
    assert payload["registry_version"] == "1.0"
    assert len(payload["runs"]) == 1
    assert payload["runs"][0]["model_name"] == "baseline_random_forest_signal_model"
    assert payload["runs"][0]["rows"] == 8
    assert payload["runs"][0]["prediction_path"].endswith("signals.csv")
    assert payload["runs"][0]["metadata_path"].endswith("prediction_run_metadata.json")
    
def test_run_model_training_cli_predict_writes_validation_report(tmp_path, capsys) -> None:
    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

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
            "223",
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
            "--require-model-version",
            "--require-probability-columns",
            "--require-confidence",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    validation_report_path = predictions_path.parent / "prediction_validation_report.json"

    assert train_exit_code == 0
    assert predict_exit_code == 0
    assert predictions_path.exists()
    assert validation_report_path.exists()
    assert payload["prediction_validation_report_path"].endswith(
        "prediction_validation_report.json"
    )
    assert payload["prediction_validation_report"]["is_valid"] is True
    assert payload["prediction_metadata_path"].endswith("prediction_run_metadata.json")
    assert payload["prediction_registry_path"].endswith("prediction_registry.json")


def test_run_model_training_cli_predict_can_disable_validation_report(
    tmp_path,
    capsys,
) -> None:
    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--random-state",
            "227",
        ]
    )
    capsys.readouterr()

    exit_code = run_model_training_cli(
        [
            "predict",
            "--model-path",
            str(output_dir / "baseline_signal_model.joblib"),
            "--features-path",
            str(features_path),
            "--output-path",
            str(predictions_path),
            "--no-prediction-validation",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert predictions_path.exists()
    assert payload["prediction_validation_report_path"] is None
    assert payload["prediction_validation_report"] is None
    assert not (predictions_path.parent / "prediction_validation_report.json").exists()


def test_run_model_training_cli_predict_can_keep_invalid_artifact_when_configured(
    tmp_path,
    capsys,
) -> None:
    dataset_path = tmp_path / "training.csv"
    features_path = tmp_path / "features.csv"
    output_dir = tmp_path / "artifacts"
    predictions_path = tmp_path / "predictions" / "signals.csv"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)
    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--random-state",
            "229",
        ]
    )
    capsys.readouterr()

    exit_code = run_model_training_cli(
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
            "--require-confidence",
            "--min-confidence",
            "0.99",
            "--max-low-confidence-ratio",
            "0.0",
            "--no-fail-on-prediction-validation-error",
            "--keep-invalid-prediction-artifact",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert predictions_path.exists()
    assert payload["prediction_validation_report"]["status"] == "failed"
    assert payload["prediction_metadata_path"].endswith("prediction_run_metadata.json")
    assert payload["prediction_registry_path"].endswith("prediction_registry.json")
    
def test_build_training_run_config_from_args_includes_model_evaluation_options() -> None:
    parser = build_model_training_cli_parser()

    args = parser.parse_args(
        [
            "train",
            "--dataset-path",
            "dataset.csv",
            "--evaluation-min-accuracy",
            "0.6",
            "--evaluation-min-macro-f1",
            "0.5",
            "--evaluation-max-log-loss",
            "0.9",
            "--evaluation-min-test-samples",
            "50",
            "--evaluation-required-classes",
            "buy, sell, hold",
            "--evaluation-allowed-promotion-stage",
            "paper_trading",
            "--model-evaluation-notes",
            "Ready for paper trading.",
        ]
    )

    config = build_training_run_config_from_args(args)

    assert config.enable_model_evaluation is True
    assert config.model_evaluation_report_filename == "model_evaluation_report.json"
    assert config.fail_on_model_evaluation_error is False
    assert config.evaluation_min_accuracy == 0.6
    assert config.evaluation_min_macro_f1 == 0.5
    assert config.evaluation_max_log_loss == 0.9
    assert config.evaluation_min_test_samples == 50
    assert config.evaluation_required_classes == ("buy", "sell", "hold")
    assert config.evaluation_allowed_promotion_stage.value == "paper_trading"
    assert config.model_evaluation_notes == "Ready for paper trading."
    
def test_run_model_training_cli_train_writes_model_evaluation_report(
    tmp_path,
    capsys,
) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    exit_code = run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--random-state",
            "283",
            "--evaluation-min-accuracy",
            "0.0",
            "--evaluation-required-classes",
            "buy,sell,hold",
            "--evaluation-allowed-promotion-stage",
            "paper_trading",
            "--model-evaluation-notes",
            "CLI generated evaluation report.",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    evaluation_report_path = output_dir / "model_evaluation_report.json"

    assert exit_code == 0
    assert evaluation_report_path.exists()
    assert payload["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )
    assert payload["model_evaluation_report"]["promotion_stage"] == "paper_trading"
    assert payload["model_evaluation_report"]["notes"] == (
        "CLI generated evaluation report."
    )
    assert payload["model_version_metadata"]["model_evaluation_report_path"].endswith(
        "model_evaluation_report.json"
    )


def test_run_model_training_cli_train_can_disable_model_evaluation(
    tmp_path,
    capsys,
) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    exit_code = run_model_training_cli(
        [
            "train",
            "--dataset-path",
            str(dataset_path),
            "--output-dir",
            str(output_dir),
            "--n-estimators",
            "20",
            "--random-state",
            "287",
            "--no-model-evaluation",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["model_evaluation_report_path"] is None
    assert payload["model_evaluation_report"] is None
    assert not (output_dir / "model_evaluation_report.json").exists()


def test_run_model_training_cli_train_fails_on_model_evaluation_error(
    tmp_path,
    capsys,
) -> None:
    dataset_path = tmp_path / "training.csv"
    output_dir = tmp_path / "artifacts"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="Model evaluation failed"):
        run_model_training_cli(
            [
                "train",
                "--dataset-path",
                str(dataset_path),
                "--output-dir",
                str(output_dir),
                "--n-estimators",
                "20",
                "--random-state",
                "289",
                "--evaluation-required-classes",
                "buy,sell,hold,missing_class",
                "--fail-on-model-evaluation-error",
            ]
        )

    capsys.readouterr()

    assert (output_dir / "model_evaluation_report.json").exists()