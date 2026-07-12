from __future__ import annotations

import json

import pytest

from aqos.model_training import (
    MODEL_EVALUATION_VERSION,
    ModelEvaluationRule,
    ModelEvaluationSeverity,
    ModelEvaluationStatus,
    ModelEvaluationThresholds,
    ModelPromotionStage,
    build_model_evaluation_issue,
    build_model_evaluation_report,
    build_model_evaluation_status,
    get_numeric_metric,
    get_sequence_metric,
    read_model_evaluation_report,
    resolve_promotion_stage,
    validate_model_evaluation_thresholds,
    validate_required_metric_present,
    write_model_evaluation_report,
)


def build_good_metrics() -> dict[str, object]:
    return {
        "accuracy": 0.72,
        "macro_f1": 0.68,
        "log_loss": 0.45,
        "test_samples": 120,
        "classes": ["buy", "sell", "hold"],
    }


def test_model_evaluation_thresholds_to_dict() -> None:
    thresholds = ModelEvaluationThresholds(
        min_accuracy=0.6,
        min_macro_f1=0.55,
        max_log_loss=0.8,
        min_test_samples=50,
        required_classes=("buy", "sell", "hold"),
        allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
    )

    assert thresholds.to_dict() == {
        "min_accuracy": 0.6,
        "min_macro_f1": 0.55,
        "max_log_loss": 0.8,
        "min_test_samples": 50,
        "required_classes": ["buy", "sell", "hold"],
        "allowed_promotion_stage": "paper_trading",
    }


def test_model_evaluation_thresholds_reject_invalid_values() -> None:
    with pytest.raises(ValueError, match="min_accuracy"):
        ModelEvaluationThresholds(min_accuracy=1.5)

    with pytest.raises(ValueError, match="min_macro_f1"):
        ModelEvaluationThresholds(min_macro_f1=-0.1)

    with pytest.raises(ValueError, match="max_log_loss"):
        ModelEvaluationThresholds(max_log_loss=-1.0)

    with pytest.raises(ValueError, match="min_test_samples"):
        ModelEvaluationThresholds(min_test_samples=-1)


def test_model_evaluation_issue_to_dict() -> None:
    issue = build_model_evaluation_issue(
        rule=ModelEvaluationRule.MIN_ACCURACY,
        severity=ModelEvaluationSeverity.ERROR,
        message="Accuracy too low.",
        metric_name="accuracy",
        details={"actual": 0.4, "minimum": 0.6},
    )

    assert issue.to_dict() == {
        "rule": "min_accuracy",
        "severity": "error",
        "message": "Accuracy too low.",
        "metric_name": "accuracy",
        "details": {"actual": 0.4, "minimum": 0.6},
    }


def test_build_model_evaluation_status() -> None:
    warning = build_model_evaluation_issue(
        rule=ModelEvaluationRule.MIN_TEST_SAMPLES,
        severity=ModelEvaluationSeverity.WARNING,
        message="Low samples.",
    )
    error = build_model_evaluation_issue(
        rule=ModelEvaluationRule.MIN_ACCURACY,
        severity=ModelEvaluationSeverity.ERROR,
        message="Low accuracy.",
    )

    assert build_model_evaluation_status(()) == ModelEvaluationStatus.PASSED
    assert build_model_evaluation_status((warning,)) == (
        ModelEvaluationStatus.PASSED_WITH_WARNINGS
    )
    assert build_model_evaluation_status((warning, error)) == (
        ModelEvaluationStatus.FAILED
    )


def test_get_numeric_metric_reads_first_available_metric() -> None:
    metrics = {"accuracy": None, "test_accuracy": "0.81"}

    assert get_numeric_metric(metrics, "accuracy", "test_accuracy") == 0.81
    assert get_numeric_metric(metrics, "missing") is None


def test_get_sequence_metric_reads_list_metric() -> None:
    metrics = {"classes": ["buy", "sell"]}

    assert get_sequence_metric(metrics, "classes") == ("buy", "sell")
    assert get_sequence_metric(metrics, "missing") == ()


def test_validate_required_metric_present() -> None:
    assert validate_required_metric_present({"accuracy": 0.5}, "accuracy") == ()

    issues = validate_required_metric_present({}, "accuracy")

    assert len(issues) == 1
    assert issues[0].rule == ModelEvaluationRule.METRIC_PRESENT
    assert issues[0].severity == ModelEvaluationSeverity.ERROR


def test_validate_model_evaluation_thresholds_passes_good_metrics() -> None:
    issues = validate_model_evaluation_thresholds(
        metrics=build_good_metrics(),
        thresholds=ModelEvaluationThresholds(
            min_accuracy=0.6,
            min_macro_f1=0.6,
            max_log_loss=0.8,
            min_test_samples=50,
            required_classes=("buy", "sell", "hold"),
        ),
    )

    assert issues == ()


def test_validate_model_evaluation_thresholds_rejects_low_accuracy() -> None:
    metrics = build_good_metrics()
    metrics["accuracy"] = 0.4

    issues = validate_model_evaluation_thresholds(
        metrics=metrics,
        thresholds=ModelEvaluationThresholds(min_accuracy=0.6),
    )

    assert any(issue.rule == ModelEvaluationRule.MIN_ACCURACY for issue in issues)


def test_validate_model_evaluation_thresholds_rejects_low_macro_f1() -> None:
    metrics = build_good_metrics()
    metrics["macro_f1"] = 0.3

    issues = validate_model_evaluation_thresholds(
        metrics=metrics,
        thresholds=ModelEvaluationThresholds(min_macro_f1=0.6),
    )

    assert any(issue.rule == ModelEvaluationRule.MIN_MACRO_F1 for issue in issues)


def test_validate_model_evaluation_thresholds_rejects_high_log_loss() -> None:
    metrics = build_good_metrics()
    metrics["log_loss"] = 1.2

    issues = validate_model_evaluation_thresholds(
        metrics=metrics,
        thresholds=ModelEvaluationThresholds(max_log_loss=0.8),
    )

    assert any(issue.rule == ModelEvaluationRule.MAX_LOG_LOSS for issue in issues)


def test_validate_model_evaluation_thresholds_warns_low_test_samples() -> None:
    metrics = build_good_metrics()
    metrics["test_samples"] = 5

    issues = validate_model_evaluation_thresholds(
        metrics=metrics,
        thresholds=ModelEvaluationThresholds(min_test_samples=50),
    )

    assert any(
        issue.rule == ModelEvaluationRule.MIN_TEST_SAMPLES
        and issue.severity == ModelEvaluationSeverity.WARNING
        for issue in issues
    )


def test_validate_model_evaluation_thresholds_rejects_missing_required_classes() -> None:
    metrics = build_good_metrics()
    metrics["classes"] = ["buy", "sell"]

    issues = validate_model_evaluation_thresholds(
        metrics=metrics,
        thresholds=ModelEvaluationThresholds(
            required_classes=("buy", "sell", "hold")
        ),
    )

    assert any(
        issue.rule == ModelEvaluationRule.REQUIRED_CLASSES_PRESENT
        for issue in issues
    )


def test_resolve_promotion_stage_blocks_failed_models() -> None:
    thresholds = ModelEvaluationThresholds(
        allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING
    )

    assert resolve_promotion_stage(ModelEvaluationStatus.FAILED, thresholds) == (
        ModelPromotionStage.BLOCKED
    )
    assert resolve_promotion_stage(ModelEvaluationStatus.PASSED, thresholds) == (
        ModelPromotionStage.PAPER_TRADING
    )


def test_build_model_evaluation_report_passed() -> None:
    report = build_model_evaluation_report(
        model_name="baseline_random_forest_signal_model",
        model_id="model_123",
        model_version="model_v1",
        dataset_id="dataset_123",
        dataset_version="dataset_v1",
        experiment_run_id="run_123",
        metrics=build_good_metrics(),
        thresholds=ModelEvaluationThresholds(
            min_accuracy=0.6,
            min_macro_f1=0.6,
            max_log_loss=0.8,
            min_test_samples=50,
            required_classes=("buy", "sell", "hold"),
            allowed_promotion_stage=ModelPromotionStage.PAPER_TRADING,
        ),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    payload = report.to_dict()

    assert report.status == ModelEvaluationStatus.PASSED
    assert report.is_valid is True
    assert report.is_promotion_ready is True
    assert report.promotion_stage == ModelPromotionStage.PAPER_TRADING
    assert payload["metadata_version"] == MODEL_EVALUATION_VERSION
    assert payload["model_id"] == "model_123"
    assert payload["dataset_id"] == "dataset_123"
    assert payload["error_count"] == 0


def test_build_model_evaluation_report_failed() -> None:
    metrics = build_good_metrics()
    metrics["accuracy"] = 0.2

    report = build_model_evaluation_report(
        model_name="baseline_random_forest_signal_model",
        metrics=metrics,
        thresholds=ModelEvaluationThresholds(min_accuracy=0.6),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == ModelEvaluationStatus.FAILED
    assert report.is_valid is False
    assert report.is_promotion_ready is False
    assert report.promotion_stage == ModelPromotionStage.BLOCKED

    with pytest.raises(ValueError, match="Model evaluation failed"):
        report.raise_if_invalid()


def test_write_and_read_model_evaluation_report_roundtrip(tmp_path) -> None:
    report = build_model_evaluation_report(
        model_name="baseline_random_forest_signal_model",
        metrics=build_good_metrics(),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    output_path = tmp_path / "reports" / "model_evaluation_report.json"
    written_path = write_model_evaluation_report(output_path, report)
    payload = read_model_evaluation_report(written_path)

    assert written_path == output_path
    assert payload["metadata_version"] == MODEL_EVALUATION_VERSION
    assert payload["model_name"] == "baseline_random_forest_signal_model"
    assert payload["status"] == "passed"


def test_read_model_evaluation_report_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_model_evaluation_report(tmp_path / "missing_report.json")


def test_model_evaluation_report_json_serializable() -> None:
    report = build_model_evaluation_report(
        model_name="baseline_random_forest_signal_model",
        metrics=build_good_metrics(),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    payload = json.dumps(report.to_dict(), sort_keys=True)

    assert "baseline_random_forest_signal_model" in payload
    assert "promotion_stage" in payload