from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    PredictionValidationStatus,
    SignalPredictionRunConfig,
    SignalTrainingRunConfig,
    predict_signals_from_csv,
    read_prediction_validation_report,
    train_baseline_signal_model_from_csv,
)


def build_training_dataset() -> pd.DataFrame:
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
                "rsi_14": 40.0 + index,
                "macd_histogram": 0.01 * index,
                "atr_14": 1.2 + index * 0.01,
                "return_5": 0.001 * index,
                "target": target,
            }
        )

    return pd.DataFrame(rows)


def train_test_model(tmp_path):
    dataset_path = tmp_path / "signal_ml_dataset.csv"
    output_dir = tmp_path / "artifacts"

    dataset = build_training_dataset()
    dataset.to_csv(dataset_path, index=False)

    training_output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=output_dir,
            n_estimators=20,
            random_state=211,
        )
    )

    return dataset, training_output


def test_prediction_runner_writes_validation_report(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    assert output.prediction_validation_report_path is not None
    assert output.prediction_validation_report_path.exists()
    assert output.prediction_validation_report is not None
    assert output.prediction_validation_report.status in {
        PredictionValidationStatus.PASSED,
        PredictionValidationStatus.PASSED_WITH_WARNINGS,
    }

    payload = read_prediction_validation_report(output.prediction_validation_report_path)

    assert payload["metadata_version"] == "1.0"
    assert payload["prediction_column"] == "predicted_signal"
    assert payload["checked_rows"] == 8
    assert payload["is_valid"] is True


def test_prediction_runner_output_dict_contains_validation_report(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    payload = output.to_dict()

    assert payload["prediction_validation_report_path"].endswith(
        "prediction_validation_report.json"
    )
    assert payload["prediction_validation_report"]["checked_rows"] == 8


def test_prediction_runner_can_disable_validation_report(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            enable_prediction_validation=False,
        )
    )

    assert output.prediction_validation_report_path is None
    assert output.prediction_validation_report is None
    assert not (prediction_path.parent / "prediction_validation_report.json").exists()


def test_prediction_runner_supports_custom_validation_report_filename(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            prediction_validation_report_filename="custom_validation_report.json",
        )
    )

    assert output.prediction_validation_report_path is not None
    assert output.prediction_validation_report_path.name == "custom_validation_report.json"


def test_prediction_runner_rejects_missing_trained_feature_columns(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target", "rsi_14"]).head(8).to_csv(features_path, index=False)

    with pytest.raises(ValueError, match="Prediction validation failed"):
        predict_signals_from_csv(
            SignalPredictionRunConfig(
                model_path=training_output.model_path,
                features_path=features_path,
                output_path=prediction_path,
            )
        )

    report_path = prediction_path.parent / "prediction_validation_report.json"
    assert report_path.exists()

    payload = read_prediction_validation_report(report_path)

    assert payload["status"] == "failed"
    assert any(
        issue["rule"] == "input_feature_columns_compatible"
        for issue in payload["issues"]
    )


def test_prediction_runner_can_write_failed_validation_without_raising(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target", "rsi_14"]).head(8).to_csv(features_path, index=False)

    with pytest.raises(Exception):
        predict_signals_from_csv(
            SignalPredictionRunConfig(
                model_path=training_output.model_path,
                features_path=features_path,
                output_path=prediction_path,
                fail_on_prediction_validation_error=False,
            )
        )

    report_path = prediction_path.parent / "prediction_validation_report.json"
    assert report_path.exists()


def test_prediction_runner_requires_model_version_when_enabled(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    with pytest.raises(ValueError, match="model version reference"):
        predict_signals_from_csv(
            SignalPredictionRunConfig(
                model_path=training_output.model_path,
                features_path=features_path,
                output_path=prediction_path,
                require_model_version=True,
            )
        )

    report_path = prediction_path.parent / "prediction_validation_report.json"
    assert report_path.exists()


def test_prediction_runner_confidence_gate_can_fail_prediction(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    with pytest.raises(ValueError, match="Too many predictions"):
        predict_signals_from_csv(
            SignalPredictionRunConfig(
                model_path=training_output.model_path,
                features_path=features_path,
                output_path=prediction_path,
                model_version_metadata_path=training_output.model_version_metadata_path,
                require_confidence=True,
                min_confidence=0.99,
                max_low_confidence_ratio=0.0,
            )
        )

    report_path = prediction_path.parent / "prediction_validation_report.json"
    payload = read_prediction_validation_report(report_path)

    assert payload["status"] == "failed"
    assert any(issue["rule"] == "low_confidence_ratio" for issue in payload["issues"])


def test_prediction_validation_report_file_is_valid_json(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
        )
    )

    payload = json.loads(
        output.prediction_validation_report_path.read_text(encoding="utf-8")
    )

    assert payload["prediction_column"] == "predicted_signal"
    assert "issues" in payload
    
def test_prediction_runner_removes_invalid_prediction_artifact_by_default(tmp_path) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    with pytest.raises(ValueError, match="Too many predictions"):
        predict_signals_from_csv(
            SignalPredictionRunConfig(
                model_path=training_output.model_path,
                features_path=features_path,
                output_path=prediction_path,
                model_version_metadata_path=training_output.model_version_metadata_path,
                require_confidence=True,
                min_confidence=0.99,
                max_low_confidence_ratio=0.0,
            )
        )

    assert not prediction_path.exists()
    assert (prediction_path.parent / "prediction_validation_report.json").exists()
    assert not (prediction_path.parent / "prediction_run_metadata.json").exists()
    assert not (prediction_path.parent / "prediction_registry.json").exists()


def test_prediction_runner_can_keep_invalid_prediction_artifact_when_configured(
    tmp_path,
) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    with pytest.raises(ValueError, match="Too many predictions"):
        predict_signals_from_csv(
            SignalPredictionRunConfig(
                model_path=training_output.model_path,
                features_path=features_path,
                output_path=prediction_path,
                model_version_metadata_path=training_output.model_version_metadata_path,
                require_confidence=True,
                min_confidence=0.99,
                max_low_confidence_ratio=0.0,
                remove_invalid_prediction_artifact=False,
            )
        )

    assert prediction_path.exists()
    assert (prediction_path.parent / "prediction_validation_report.json").exists()
    assert not (prediction_path.parent / "prediction_run_metadata.json").exists()
    assert not (prediction_path.parent / "prediction_registry.json").exists()


def test_prediction_runner_keeps_invalid_artifact_when_not_failing_and_removal_disabled(
    tmp_path,
) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
            require_confidence=True,
            min_confidence=0.99,
            max_low_confidence_ratio=0.0,
            fail_on_prediction_validation_error=False,
            remove_invalid_prediction_artifact=False,
        )
    )

    assert prediction_path.exists()
    assert output.prediction_validation_report is not None
    assert output.prediction_validation_report.status == PredictionValidationStatus.FAILED
    assert output.prediction_metadata_path is not None
    assert output.prediction_registry_path is not None


def test_prediction_runner_removes_invalid_artifact_when_not_failing_but_removal_enabled(
    tmp_path,
) -> None:
    dataset, training_output = train_test_model(tmp_path)

    features_path = tmp_path / "features.csv"
    prediction_path = tmp_path / "predictions" / "signals.csv"

    dataset.drop(columns=["target"]).head(8).to_csv(features_path, index=False)

    output = predict_signals_from_csv(
        SignalPredictionRunConfig(
            model_path=training_output.model_path,
            features_path=features_path,
            output_path=prediction_path,
            model_version_metadata_path=training_output.model_version_metadata_path,
            require_confidence=True,
            min_confidence=0.99,
            max_low_confidence_ratio=0.0,
            fail_on_prediction_validation_error=False,
            remove_invalid_prediction_artifact=True,
        )
    )

    assert not prediction_path.exists()
    assert output.prediction_validation_report is not None
    assert output.prediction_validation_report.status == PredictionValidationStatus.FAILED
    assert output.prediction_metadata_path is None
    assert output.prediction_registry_path is None