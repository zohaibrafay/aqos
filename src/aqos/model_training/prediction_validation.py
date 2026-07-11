from __future__ import annotations

import json
from dataclasses import dataclass, field as dataclass_field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd


PREDICTION_VALIDATION_VERSION = "1.0"


class PredictionValidationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class PredictionValidationStatus(str, Enum):
    PASSED = "passed"
    PASSED_WITH_WARNINGS = "passed_with_warnings"
    FAILED = "failed"


class PredictionValidationRule(str, Enum):
    INPUT_FEATURES_NOT_EMPTY = "input_features_not_empty"
    PREDICTIONS_NOT_EMPTY = "predictions_not_empty"
    ROW_COUNT_MATCH = "row_count_match"
    PREDICTION_COLUMN_PRESENT = "prediction_column_present"
    PREDICTION_VALUES_PRESENT = "prediction_values_present"
    PROBABILITY_COLUMNS_PRESENT = "probability_columns_present"
    PROBABILITY_COLUMNS_NUMERIC = "probability_columns_numeric"
    PROBABILITY_VALUES_PRESENT = "probability_values_present"
    PROBABILITY_VALUES_IN_RANGE = "probability_values_in_range"
    PROBABILITY_ROWS_SUM_TO_ONE = "probability_rows_sum_to_one"
    MODEL_VERSION_PRESENT = "model_version_present"
    TRAINED_FEATURE_COLUMNS_PRESENT = "trained_feature_columns_present"
    INPUT_FEATURE_COLUMNS_COMPATIBLE = "input_feature_columns_compatible"
    CONFIDENCE_VALUES_PRESENT = "confidence_values_present"
    CONFIDENCE_VALUES_NUMERIC = "confidence_values_numeric"
    CONFIDENCE_VALUES_IN_RANGE = "confidence_values_in_range"
    MIN_CONFIDENCE_THRESHOLD = "min_confidence_threshold"
    LOW_CONFIDENCE_RATIO = "low_confidence_ratio"


@dataclass(frozen=True)
class PredictionValidationIssue:
    rule: PredictionValidationRule
    severity: PredictionValidationSeverity
    message: str
    field: str | None = None
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("Prediction validation issue message cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule.value,
            "severity": self.severity.value,
            "message": self.message,
            "field": self.field,
            "details": self.details,
        }


@dataclass(frozen=True)
class PredictionValidationReport:
    created_at_utc: str
    status: PredictionValidationStatus
    checked_rows: int
    prediction_column: str
    probability_columns: tuple[str, ...]
    issues: tuple[PredictionValidationIssue, ...] = ()
    metadata_version: str = PREDICTION_VALIDATION_VERSION

    def __post_init__(self) -> None:
        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if self.checked_rows < 0:
            raise ValueError("checked_rows cannot be negative.")

        if not self.prediction_column.strip():
            raise ValueError("prediction_column cannot be empty.")

    @property
    def is_valid(self) -> bool:
        return self.status != PredictionValidationStatus.FAILED

    @property
    def error_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == PredictionValidationSeverity.ERROR
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == PredictionValidationSeverity.WARNING
        )

    @property
    def info_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == PredictionValidationSeverity.INFO
        )

    def raise_if_invalid(self) -> None:
        if self.is_valid:
            return

        messages = [
            issue.message
            for issue in self.issues
            if issue.severity == PredictionValidationSeverity.ERROR
        ]

        raise ValueError(
            "Prediction validation failed: " + "; ".join(messages)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata_version": self.metadata_version,
            "created_at_utc": self.created_at_utc,
            "status": self.status.value,
            "is_valid": self.is_valid,
            "checked_rows": self.checked_rows,
            "prediction_column": self.prediction_column,
            "probability_columns": list(self.probability_columns),
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


def prediction_validation_utc_now_iso() -> str:
    return datetime.now(tz=UTC).replace(microsecond=0).isoformat()


def build_prediction_validation_issue(
    rule: PredictionValidationRule,
    severity: PredictionValidationSeverity,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> PredictionValidationIssue:
    return PredictionValidationIssue(
        rule=rule,
        severity=severity,
        message=message,
        field=field,
        details=details or {},
    )


def build_prediction_validation_status(
    issues: tuple[PredictionValidationIssue, ...],
) -> PredictionValidationStatus:
    if any(issue.severity == PredictionValidationSeverity.ERROR for issue in issues):
        return PredictionValidationStatus.FAILED

    if any(issue.severity == PredictionValidationSeverity.WARNING for issue in issues):
        return PredictionValidationStatus.PASSED_WITH_WARNINGS

    return PredictionValidationStatus.PASSED


def build_prediction_validation_report(
    issues: tuple[PredictionValidationIssue, ...] = (),
    checked_rows: int = 0,
    prediction_column: str = "predicted_signal",
    probability_columns: tuple[str, ...] = (),
    created_at_utc: str | None = None,
) -> PredictionValidationReport:
    return PredictionValidationReport(
        created_at_utc=created_at_utc or prediction_validation_utc_now_iso(),
        status=build_prediction_validation_status(issues),
        checked_rows=checked_rows,
        prediction_column=prediction_column,
        probability_columns=probability_columns,
        issues=issues,
    )


def validate_prediction_model_reference(
    model_id: str | None,
    model_version: str | None,
    require_model_version: bool = True,
) -> tuple[PredictionValidationIssue, ...]:
    if not require_model_version:
        return ()

    if model_id and model_version:
        return ()

    return (
        build_prediction_validation_issue(
            rule=PredictionValidationRule.MODEL_VERSION_PRESENT,
            severity=PredictionValidationSeverity.ERROR,
            message="Prediction run is missing model version reference.",
            field="model_version",
            details={
                "model_id_present": bool(model_id),
                "model_version_present": bool(model_version),
            },
        ),
    )


def validate_probability_columns(
    predictions: pd.DataFrame,
    probability_columns: tuple[str, ...],
    require_probability_columns: bool = False,
    probability_sum_tolerance: float = 0.01,
) -> tuple[PredictionValidationIssue, ...]:
    issues: list[PredictionValidationIssue] = []

    if require_probability_columns and not probability_columns:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.PROBABILITY_COLUMNS_PRESENT,
                severity=PredictionValidationSeverity.ERROR,
                message="Prediction probabilities are required but no probability columns were provided.",
                field="probability_columns",
            )
        )
        return tuple(issues)

    numeric_probability_columns: list[str] = []

    for column in probability_columns:
        if column not in predictions.columns:
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.PROBABILITY_COLUMNS_PRESENT,
                    severity=PredictionValidationSeverity.ERROR,
                    message=f"Probability column is missing: {column}",
                    field=column,
                )
            )
            continue

        series = predictions[column]

        if series.isna().any():
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.PROBABILITY_VALUES_PRESENT,
                    severity=PredictionValidationSeverity.ERROR,
                    message=f"Probability column contains null values: {column}",
                    field=column,
                    details={"null_count": int(series.isna().sum())},
                )
            )

        if not pd.api.types.is_numeric_dtype(series):
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.PROBABILITY_COLUMNS_NUMERIC,
                    severity=PredictionValidationSeverity.ERROR,
                    message=f"Probability column must be numeric: {column}",
                    field=column,
                )
            )
            continue

        numeric_probability_columns.append(column)

        invalid_range_mask = (series < 0.0) | (series > 1.0)
        invalid_range_count = int(invalid_range_mask.sum())

        if invalid_range_count:
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.PROBABILITY_VALUES_IN_RANGE,
                    severity=PredictionValidationSeverity.ERROR,
                    message=f"Probability values must be between 0 and 1: {column}",
                    field=column,
                    details={"invalid_range_count": invalid_range_count},
                )
            )

    if numeric_probability_columns:
        probability_sums = predictions[numeric_probability_columns].sum(axis=1)
        bad_sum_count = int(
            (probability_sums.sub(1.0).abs() > probability_sum_tolerance).sum()
        )

        if bad_sum_count:
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.PROBABILITY_ROWS_SUM_TO_ONE,
                    severity=PredictionValidationSeverity.WARNING,
                    message="Prediction probability rows do not sum close to 1.",
                    field="probability_columns",
                    details={
                        "bad_sum_count": bad_sum_count,
                        "tolerance": probability_sum_tolerance,
                    },
                )
            )

    return tuple(issues)


def validate_prediction_input_output(
    input_features: pd.DataFrame,
    predictions: pd.DataFrame,
    prediction_column: str = "predicted_signal",
    probability_columns: tuple[str, ...] = (),
    require_probability_columns: bool = False,
    probability_sum_tolerance: float = 0.01,
    confidence_column: str | None = None,
    min_confidence: float = 0.55,
    max_low_confidence_ratio: float = 0.5,
    require_confidence: bool = False,
    model_id: str | None = None,
    model_version: str | None = None,
    require_model_version: bool = False,
    created_at_utc: str | None = None,
    
) -> PredictionValidationReport:
    issues: list[PredictionValidationIssue] = []

    if input_features.empty:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.INPUT_FEATURES_NOT_EMPTY,
                severity=PredictionValidationSeverity.ERROR,
                message="Prediction input features are empty.",
                field="input_features",
            )
        )

    if predictions.empty:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.PREDICTIONS_NOT_EMPTY,
                severity=PredictionValidationSeverity.ERROR,
                message="Prediction output is empty.",
                field="predictions",
            )
        )

    if not input_features.empty and not predictions.empty:
        if len(input_features) != len(predictions):
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.ROW_COUNT_MATCH,
                    severity=PredictionValidationSeverity.ERROR,
                    message="Prediction output row count does not match input feature row count.",
                    field="rows",
                    details={
                        "input_rows": len(input_features),
                        "prediction_rows": len(predictions),
                    },
                )
            )

    if prediction_column not in predictions.columns:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.PREDICTION_COLUMN_PRESENT,
                severity=PredictionValidationSeverity.ERROR,
                message=f"Prediction column is missing: {prediction_column}",
                field=prediction_column,
            )
        )
    else:
        prediction_values = predictions[prediction_column]
        null_count = int(prediction_values.isna().sum())

        blank_count = 0
        if pd.api.types.is_object_dtype(prediction_values) or pd.api.types.is_string_dtype(
            prediction_values
        ):
            blank_count = int(prediction_values.astype(str).str.strip().eq("").sum())

        if null_count or blank_count:
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.PREDICTION_VALUES_PRESENT,
                    severity=PredictionValidationSeverity.ERROR,
                    message="Prediction column contains missing or blank values.",
                    field=prediction_column,
                    details={
                        "null_count": null_count,
                        "blank_count": blank_count,
                    },
                )
            )

    issues.extend(
        validate_probability_columns(
            predictions=predictions,
            probability_columns=probability_columns,
            require_probability_columns=require_probability_columns,
            probability_sum_tolerance=probability_sum_tolerance,
        )
    )
    if require_confidence or confidence_column is not None:
        issues.extend(
            validate_prediction_confidence(
                predictions=predictions,
                probability_columns=probability_columns,
                confidence_column=confidence_column,
                min_confidence=min_confidence,
                max_low_confidence_ratio=max_low_confidence_ratio,
                require_confidence=require_confidence,
            )
        )

    issues.extend(
        validate_prediction_model_reference(
            model_id=model_id,
            model_version=model_version,
            require_model_version=require_model_version,
        )
    )

    return build_prediction_validation_report(
        issues=tuple(issues),
        checked_rows=len(predictions),
        prediction_column=prediction_column,
        probability_columns=probability_columns,
        created_at_utc=created_at_utc,
    )

def extract_trained_feature_columns(model: Any) -> tuple[str, ...]:
    for attribute_name in (
        "feature_columns",
        "_feature_columns",
        "trained_feature_columns",
        "model_feature_columns",
    ):
        value = getattr(model, attribute_name, None)

        if value:
            return tuple(str(column) for column in value)

    metadata = getattr(model, "metadata", None)

    if isinstance(metadata, dict):
        for key in (
            "feature_columns",
            "trained_feature_columns",
            "model_feature_columns",
        ):
            value = metadata.get(key)

            if value:
                return tuple(str(column) for column in value)

    training_result = getattr(model, "training_result", None)

    if training_result is not None:
        value = getattr(training_result, "feature_columns", None)

        if value:
            return tuple(str(column) for column in value)

    return ()


def validate_prediction_feature_columns_against_model(
    input_features: pd.DataFrame,
    trained_feature_columns: tuple[str, ...],
    require_trained_feature_columns: bool = True,
) -> tuple[PredictionValidationIssue, ...]:
    issues: list[PredictionValidationIssue] = []

    if require_trained_feature_columns and not trained_feature_columns:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.TRAINED_FEATURE_COLUMNS_PRESENT,
                severity=PredictionValidationSeverity.ERROR,
                message="Trained model feature columns are missing.",
                field="trained_feature_columns",
            )
        )
        return tuple(issues)

    if not trained_feature_columns:
        return tuple(issues)

    input_columns = tuple(str(column) for column in input_features.columns)
    input_column_set = set(input_columns)
    trained_column_set = set(trained_feature_columns)

    missing_columns = tuple(
        column
        for column in trained_feature_columns
        if column not in input_column_set
    )
    extra_columns = tuple(
        column
        for column in input_columns
        if column not in trained_column_set
    )

    if missing_columns:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.INPUT_FEATURE_COLUMNS_COMPATIBLE,
                severity=PredictionValidationSeverity.ERROR,
                message="Prediction input is missing trained model feature columns.",
                field="features",
                details={
                    "missing_columns": list(missing_columns),
                    "trained_feature_columns": list(trained_feature_columns),
                    "input_columns": list(input_columns),
                },
            )
        )

    if extra_columns:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.INPUT_FEATURE_COLUMNS_COMPATIBLE,
                severity=PredictionValidationSeverity.WARNING,
                message="Prediction input contains extra columns not used by the trained model.",
                field="features",
                details={
                    "extra_columns": list(extra_columns),
                    "trained_feature_columns": list(trained_feature_columns),
                    "input_columns": list(input_columns),
                },
            )
        )

    return tuple(issues)

def build_prediction_confidence_scores(
    predictions: pd.DataFrame,
    probability_columns: tuple[str, ...] = (),
    confidence_column: str | None = None,
) -> pd.Series:
    if confidence_column:
        if confidence_column not in predictions.columns:
            return pd.Series(dtype="float64")

        series = predictions[confidence_column]

        if not pd.api.types.is_numeric_dtype(series):
            return pd.Series(dtype="float64")

        return series.astype(float)

    available_probability_columns = [
        column
        for column in probability_columns
        if column in predictions.columns
        and pd.api.types.is_numeric_dtype(predictions[column])
    ]

    if not available_probability_columns:
        return pd.Series(dtype="float64")

    return predictions[available_probability_columns].max(axis=1).astype(float)


def validate_prediction_confidence(
    predictions: pd.DataFrame,
    probability_columns: tuple[str, ...] = (),
    confidence_column: str | None = None,
    min_confidence: float = 0.55,
    max_low_confidence_ratio: float = 0.5,
    require_confidence: bool = False,
) -> tuple[PredictionValidationIssue, ...]:
    issues: list[PredictionValidationIssue] = []

    if not 0.0 <= min_confidence <= 1.0:
        raise ValueError("min_confidence must be between 0 and 1.")

    if not 0.0 <= max_low_confidence_ratio <= 1.0:
        raise ValueError("max_low_confidence_ratio must be between 0 and 1.")

    if confidence_column and confidence_column not in predictions.columns:
        if require_confidence:
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.CONFIDENCE_VALUES_PRESENT,
                    severity=PredictionValidationSeverity.ERROR,
                    message=f"Confidence column is missing: {confidence_column}",
                    field=confidence_column,
                )
            )
        return tuple(issues)

    if confidence_column and confidence_column in predictions.columns:
        confidence_series = predictions[confidence_column]

        if confidence_series.isna().any():
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.CONFIDENCE_VALUES_PRESENT,
                    severity=PredictionValidationSeverity.ERROR,
                    message=f"Confidence column contains null values: {confidence_column}",
                    field=confidence_column,
                    details={"null_count": int(confidence_series.isna().sum())},
                )
            )

        if not pd.api.types.is_numeric_dtype(confidence_series):
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.CONFIDENCE_VALUES_NUMERIC,
                    severity=PredictionValidationSeverity.ERROR,
                    message=f"Confidence column must be numeric: {confidence_column}",
                    field=confidence_column,
                )
            )
            return tuple(issues)

    confidence_scores = build_prediction_confidence_scores(
        predictions=predictions,
        probability_columns=probability_columns,
        confidence_column=confidence_column,
    )

    if confidence_scores.empty:
        if require_confidence:
            issues.append(
                build_prediction_validation_issue(
                    rule=PredictionValidationRule.CONFIDENCE_VALUES_PRESENT,
                    severity=PredictionValidationSeverity.ERROR,
                    message="Prediction confidence is required but no confidence values were available.",
                    field=confidence_column or "probability_columns",
                    details={
                        "confidence_column": confidence_column,
                        "probability_columns": list(probability_columns),
                    },
                )
            )
        return tuple(issues)

    null_count = int(confidence_scores.isna().sum())

    if null_count:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.CONFIDENCE_VALUES_PRESENT,
                severity=PredictionValidationSeverity.ERROR,
                message="Prediction confidence contains null values.",
                field=confidence_column or "probability_columns",
                details={"null_count": null_count},
            )
        )

    invalid_range_count = int(((confidence_scores < 0.0) | (confidence_scores > 1.0)).sum())

    if invalid_range_count:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.CONFIDENCE_VALUES_IN_RANGE,
                severity=PredictionValidationSeverity.ERROR,
                message="Prediction confidence values must be between 0 and 1.",
                field=confidence_column or "probability_columns",
                details={"invalid_range_count": invalid_range_count},
            )
        )

    low_confidence_mask = confidence_scores < min_confidence
    low_confidence_count = int(low_confidence_mask.sum())
    total_count = int(len(confidence_scores))
    low_confidence_ratio = (
        low_confidence_count / total_count
        if total_count > 0
        else 0.0
    )

    if low_confidence_count:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.MIN_CONFIDENCE_THRESHOLD,
                severity=PredictionValidationSeverity.WARNING,
                message="Some predictions are below the minimum confidence threshold.",
                field=confidence_column or "probability_columns",
                details={
                    "min_confidence": min_confidence,
                    "low_confidence_count": low_confidence_count,
                    "total_count": total_count,
                    "low_confidence_ratio": low_confidence_ratio,
                },
            )
        )

    if low_confidence_ratio > max_low_confidence_ratio:
        issues.append(
            build_prediction_validation_issue(
                rule=PredictionValidationRule.LOW_CONFIDENCE_RATIO,
                severity=PredictionValidationSeverity.ERROR,
                message="Too many predictions are below the minimum confidence threshold.",
                field=confidence_column or "probability_columns",
                details={
                    "min_confidence": min_confidence,
                    "max_low_confidence_ratio": max_low_confidence_ratio,
                    "low_confidence_count": low_confidence_count,
                    "total_count": total_count,
                    "low_confidence_ratio": low_confidence_ratio,
                },
            )
        )

    return tuple(issues)

def write_prediction_validation_report(
    path: str | Path,
    report: PredictionValidationReport,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


def read_prediction_validation_report(path: str | Path) -> dict[str, Any]:
    report_path = Path(path)

    if not report_path.exists():
        raise FileNotFoundError(
            f"Prediction validation report does not exist: {report_path}"
        )

    return json.loads(report_path.read_text(encoding="utf-8"))


__all__ = [
    "PREDICTION_VALIDATION_VERSION",
    "PredictionValidationIssue",
    "PredictionValidationReport",
    "PredictionValidationRule",
    "PredictionValidationSeverity",
    "PredictionValidationStatus",
    "build_prediction_validation_issue",
    "build_prediction_validation_report",
    "build_prediction_validation_status",
    "prediction_validation_utc_now_iso",
    "read_prediction_validation_report",
    "validate_prediction_input_output",
    "validate_prediction_model_reference",
    "validate_probability_columns",
    "write_prediction_validation_report",
    "extract_trained_feature_columns",
    "validate_prediction_feature_columns_against_model",
    "build_prediction_confidence_scores",
    "validate_prediction_confidence",
]

# __all__ = sorted(__all__)