from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    PREDICTION_VALIDATION_VERSION,
    PredictionValidationRule,
    PredictionValidationSeverity,
    PredictionValidationStatus,
    build_prediction_validation_issue,
    build_prediction_validation_report,
    read_prediction_validation_report,
    validate_prediction_input_output,
    validate_prediction_model_reference,
    validate_probability_columns,
    write_prediction_validation_report,
    extract_trained_feature_columns,
    validate_prediction_feature_columns_against_model,
    build_prediction_confidence_scores,
    validate_prediction_confidence,
)


def build_input_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [2300.0, 2301.0, 2302.0],
            "high": [2302.0, 2303.0, 2304.0],
            "low": [2298.0, 2299.0, 2300.0],
            "close": [2301.0, 2302.0, 2303.0],
            "volume": [1000, 1001, 1002],
        }
    )


def build_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "predicted_signal": ["buy", "hold", "sell"],
            "probability_buy": [0.8, 0.1, 0.1],
            "probability_hold": [0.1, 0.8, 0.1],
            "probability_sell": [0.1, 0.1, 0.8],
        }
    )


def test_prediction_validation_issue_to_dict() -> None:
    issue = build_prediction_validation_issue(
        rule=PredictionValidationRule.PREDICTION_COLUMN_PRESENT,
        severity=PredictionValidationSeverity.ERROR,
        message="Missing prediction column.",
        field="predicted_signal",
        details={"column": "predicted_signal"},
    )

    payload = issue.to_dict()

    assert payload == {
        "rule": "prediction_column_present",
        "severity": "error",
        "message": "Missing prediction column.",
        "field": "predicted_signal",
        "details": {"column": "predicted_signal"},
    }


def test_prediction_validation_report_passes_without_issues() -> None:
    report = build_prediction_validation_report(
        checked_rows=3,
        prediction_column="predicted_signal",
        probability_columns=("probability_buy",),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.PASSED
    assert report.is_valid is True
    assert report.error_count == 0
    assert report.warning_count == 0
    report.raise_if_invalid()


def test_prediction_validation_report_fails_with_error_issue() -> None:
    issue = build_prediction_validation_issue(
        rule=PredictionValidationRule.PREDICTIONS_NOT_EMPTY,
        severity=PredictionValidationSeverity.ERROR,
        message="Prediction output is empty.",
    )

    report = build_prediction_validation_report(
        issues=(issue,),
        checked_rows=0,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.FAILED
    assert report.is_valid is False
    assert report.error_count == 1

    with pytest.raises(ValueError, match="Prediction validation failed"):
        report.raise_if_invalid()


def test_validate_prediction_input_output_accepts_valid_predictions() -> None:
    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=build_predictions(),
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
        require_probability_columns=True,
        model_id="model_123",
        model_version="model_v1",
        require_model_version=True,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.PASSED
    assert report.is_valid is True
    assert report.checked_rows == 3
    assert report.issues == ()


def test_validate_prediction_input_output_rejects_empty_input() -> None:
    report = validate_prediction_input_output(
        input_features=pd.DataFrame(),
        predictions=build_predictions(),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.FAILED
    assert any(
        issue.rule == PredictionValidationRule.INPUT_FEATURES_NOT_EMPTY
        for issue in report.issues
    )


def test_validate_prediction_input_output_rejects_empty_predictions() -> None:
    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=pd.DataFrame(),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.FAILED
    assert any(
        issue.rule == PredictionValidationRule.PREDICTIONS_NOT_EMPTY
        for issue in report.issues
    )


def test_validate_prediction_input_output_rejects_row_count_mismatch() -> None:
    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=build_predictions().head(2),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.FAILED
    assert any(
        issue.rule == PredictionValidationRule.ROW_COUNT_MATCH
        for issue in report.issues
    )


def test_validate_prediction_input_output_rejects_missing_prediction_column() -> None:
    predictions = build_predictions().drop(columns=["predicted_signal"])

    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=predictions,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.FAILED
    assert any(
        issue.rule == PredictionValidationRule.PREDICTION_COLUMN_PRESENT
        for issue in report.issues
    )


def test_validate_prediction_input_output_rejects_blank_prediction_values() -> None:
    predictions = build_predictions()
    predictions.loc[1, "predicted_signal"] = ""

    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=predictions,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.FAILED
    assert any(
        issue.rule == PredictionValidationRule.PREDICTION_VALUES_PRESENT
        for issue in report.issues
    )


def test_validate_probability_columns_requires_columns_when_enabled() -> None:
    issues = validate_probability_columns(
        predictions=build_predictions(),
        probability_columns=(),
        require_probability_columns=True,
    )

    assert len(issues) == 1
    assert issues[0].rule == PredictionValidationRule.PROBABILITY_COLUMNS_PRESENT
    assert issues[0].severity == PredictionValidationSeverity.ERROR


def test_validate_probability_columns_rejects_missing_probability_column() -> None:
    issues = validate_probability_columns(
        predictions=build_predictions(),
        probability_columns=("probability_buy", "probability_missing"),
    )

    assert any(
        issue.rule == PredictionValidationRule.PROBABILITY_COLUMNS_PRESENT
        for issue in issues
    )


def test_validate_probability_columns_rejects_non_numeric_probability_column() -> None:
    predictions = build_predictions()
    predictions["probability_buy"] = ["high", "low", "medium"]

    issues = validate_probability_columns(
        predictions=predictions,
        probability_columns=("probability_buy",),
    )

    assert any(
        issue.rule == PredictionValidationRule.PROBABILITY_COLUMNS_NUMERIC
        for issue in issues
    )


def test_validate_probability_columns_rejects_probability_out_of_range() -> None:
    predictions = build_predictions()
    predictions.loc[0, "probability_buy"] = 1.5

    issues = validate_probability_columns(
        predictions=predictions,
        probability_columns=("probability_buy",),
    )

    assert any(
        issue.rule == PredictionValidationRule.PROBABILITY_VALUES_IN_RANGE
        for issue in issues
    )


def test_validate_probability_columns_warns_when_rows_do_not_sum_to_one() -> None:
    predictions = build_predictions()
    predictions["probability_buy"] = [0.5, 0.5, 0.5]
    predictions["probability_hold"] = [0.5, 0.5, 0.5]
    predictions["probability_sell"] = [0.5, 0.5, 0.5]

    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=predictions,
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.PASSED_WITH_WARNINGS
    assert report.is_valid is True
    assert any(
        issue.rule == PredictionValidationRule.PROBABILITY_ROWS_SUM_TO_ONE
        for issue in report.issues
    )


def test_validate_prediction_model_reference_requires_model_version() -> None:
    issues = validate_prediction_model_reference(
        model_id=None,
        model_version=None,
        require_model_version=True,
    )

    assert len(issues) == 1
    assert issues[0].rule == PredictionValidationRule.MODEL_VERSION_PRESENT


def test_write_and_read_prediction_validation_report_roundtrip(tmp_path) -> None:
    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=build_predictions(),
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    output_path = tmp_path / "reports" / "prediction_validation_report.json"
    written_path = write_prediction_validation_report(output_path, report)
    payload = read_prediction_validation_report(written_path)

    assert written_path == output_path
    assert payload["metadata_version"] == PREDICTION_VALIDATION_VERSION
    assert payload["status"] == "passed"
    assert payload["checked_rows"] == 3


def test_read_prediction_validation_report_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        read_prediction_validation_report(tmp_path / "missing_report.json")


def test_prediction_validation_report_is_json_serializable() -> None:
    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=build_predictions(),
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    payload = json.dumps(report.to_dict(), sort_keys=True)

    assert "prediction_column" in payload
    assert "predicted_signal" in payload
    
    
def test_extract_trained_feature_columns_reads_common_model_attributes() -> None:
    class Model:
        feature_columns = ("open", "high", "low", "close")

    assert extract_trained_feature_columns(Model()) == (
        "open",
        "high",
        "low",
        "close",
    )


def test_extract_trained_feature_columns_reads_metadata_dict() -> None:
    class Model:
        metadata = {"feature_columns": ["open", "close", "volume"]}

    assert extract_trained_feature_columns(Model()) == (
        "open",
        "close",
        "volume",
    )


def test_validate_prediction_feature_columns_against_model_passes_matching_columns() -> None:
    issues = validate_prediction_feature_columns_against_model(
        input_features=build_input_features(),
        trained_feature_columns=("open", "high", "low", "close", "volume"),
    )

    assert issues == ()


def test_validate_prediction_feature_columns_against_model_rejects_missing_columns() -> None:
    features = build_input_features().drop(columns=["volume"])

    issues = validate_prediction_feature_columns_against_model(
        input_features=features,
        trained_feature_columns=("open", "high", "low", "close", "volume"),
    )

    assert any(
        issue.rule == PredictionValidationRule.INPUT_FEATURE_COLUMNS_COMPATIBLE
        and issue.severity == PredictionValidationSeverity.ERROR
        for issue in issues
    )
    assert issues[0].details["missing_columns"] == ["volume"]


def test_validate_prediction_feature_columns_against_model_warns_extra_columns() -> None:
    features = build_input_features()
    features["unused_extra"] = 1

    issues = validate_prediction_feature_columns_against_model(
        input_features=features,
        trained_feature_columns=("open", "high", "low", "close", "volume"),
    )

    assert any(
        issue.rule == PredictionValidationRule.INPUT_FEATURE_COLUMNS_COMPATIBLE
        and issue.severity == PredictionValidationSeverity.WARNING
        for issue in issues
    )
    assert issues[0].details["extra_columns"] == ["unused_extra"]


def test_validate_prediction_feature_columns_against_model_rejects_missing_trained_columns() -> None:
    issues = validate_prediction_feature_columns_against_model(
        input_features=build_input_features(),
        trained_feature_columns=(),
        require_trained_feature_columns=True,
    )

    assert len(issues) == 1
    assert issues[0].rule == PredictionValidationRule.TRAINED_FEATURE_COLUMNS_PRESENT
    assert issues[0].severity == PredictionValidationSeverity.ERROR


def test_validate_prediction_feature_columns_against_model_allows_missing_trained_columns_when_not_required() -> None:
    issues = validate_prediction_feature_columns_against_model(
        input_features=build_input_features(),
        trained_feature_columns=(),
        require_trained_feature_columns=False,
    )

    assert issues == ()
    
def test_build_prediction_confidence_scores_uses_probability_max() -> None:
    scores = build_prediction_confidence_scores(
        predictions=build_predictions(),
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
    )

    assert scores.tolist() == [0.8, 0.8, 0.8]


def test_build_prediction_confidence_scores_uses_explicit_confidence_column() -> None:
    predictions = build_predictions()
    predictions["confidence"] = [0.9, 0.7, 0.6]

    scores = build_prediction_confidence_scores(
        predictions=predictions,
        confidence_column="confidence",
    )

    assert scores.tolist() == [0.9, 0.7, 0.6]


def test_validate_prediction_confidence_accepts_good_confidence() -> None:
    issues = validate_prediction_confidence(
        predictions=build_predictions(),
        probability_columns=(
            "probability_buy",
            "probability_hold",
            "probability_sell",
        ),
        min_confidence=0.55,
        max_low_confidence_ratio=0.5,
        require_confidence=True,
    )

    assert issues == ()


def test_validate_prediction_confidence_requires_confidence_when_enabled() -> None:
    issues = validate_prediction_confidence(
        predictions=build_predictions(),
        probability_columns=(),
        require_confidence=True,
    )

    assert len(issues) == 1
    assert issues[0].rule == PredictionValidationRule.CONFIDENCE_VALUES_PRESENT
    assert issues[0].severity == PredictionValidationSeverity.ERROR


def test_validate_prediction_confidence_rejects_non_numeric_confidence_column() -> None:
    predictions = build_predictions()
    predictions["confidence"] = ["high", "medium", "low"]

    issues = validate_prediction_confidence(
        predictions=predictions,
        confidence_column="confidence",
        require_confidence=True,
    )

    assert len(issues) == 1
    assert issues[0].rule == PredictionValidationRule.CONFIDENCE_VALUES_NUMERIC
    assert issues[0].severity == PredictionValidationSeverity.ERROR


def test_validate_prediction_confidence_rejects_out_of_range_confidence() -> None:
    predictions = build_predictions()
    predictions["confidence"] = [0.9, 1.2, 0.7]

    issues = validate_prediction_confidence(
        predictions=predictions,
        confidence_column="confidence",
    )

    assert any(
        issue.rule == PredictionValidationRule.CONFIDENCE_VALUES_IN_RANGE
        and issue.severity == PredictionValidationSeverity.ERROR
        for issue in issues
    )


def test_validate_prediction_confidence_warns_low_confidence_rows() -> None:
    predictions = build_predictions()
    predictions["confidence"] = [0.9, 0.4, 0.8]

    issues = validate_prediction_confidence(
        predictions=predictions,
        confidence_column="confidence",
        min_confidence=0.55,
        max_low_confidence_ratio=0.5,
    )

    assert any(
        issue.rule == PredictionValidationRule.MIN_CONFIDENCE_THRESHOLD
        and issue.severity == PredictionValidationSeverity.WARNING
        for issue in issues
    )


def test_validate_prediction_confidence_errors_when_too_many_low_confidence_rows() -> None:
    predictions = build_predictions()
    predictions["confidence"] = [0.4, 0.3, 0.8]

    issues = validate_prediction_confidence(
        predictions=predictions,
        confidence_column="confidence",
        min_confidence=0.55,
        max_low_confidence_ratio=0.5,
    )

    assert any(
        issue.rule == PredictionValidationRule.LOW_CONFIDENCE_RATIO
        and issue.severity == PredictionValidationSeverity.ERROR
        for issue in issues
    )


def test_validate_prediction_input_output_includes_confidence_checks() -> None:
    predictions = build_predictions()
    predictions["confidence"] = [0.4, 0.3, 0.8]

    report = validate_prediction_input_output(
        input_features=build_input_features(),
        predictions=predictions,
        confidence_column="confidence",
        min_confidence=0.55,
        max_low_confidence_ratio=0.5,
        require_confidence=True,
        created_at_utc="2026-01-01T00:00:00+00:00",
    )

    assert report.status == PredictionValidationStatus.FAILED
    assert any(
        issue.rule == PredictionValidationRule.LOW_CONFIDENCE_RATIO
        for issue in report.issues
    )


def test_validate_prediction_confidence_rejects_invalid_thresholds() -> None:
    with pytest.raises(ValueError, match="min_confidence"):
        validate_prediction_confidence(
            predictions=build_predictions(),
            min_confidence=1.5,
        )

    with pytest.raises(ValueError, match="max_low_confidence_ratio"):
        validate_prediction_confidence(
            predictions=build_predictions(),
            max_low_confidence_ratio=-0.1,
        )