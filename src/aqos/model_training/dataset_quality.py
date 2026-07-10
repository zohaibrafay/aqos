from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.model_training.feature_schema import (
    DatasetValidationResult,
    validate_signal_training_dataset,
)
from aqos.model_training.leakage_guard import check_feature_columns_for_leakage


class DatasetQualitySeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class DatasetQualityConfig:
    target_column: str = "target"
    min_rows: int = 8
    min_target_classes: int = 2
    max_majority_class_ratio: float = 0.8

    def __post_init__(self) -> None:
        if not self.target_column.strip():
            raise ValueError("target_column cannot be empty.")

        if self.min_rows < 1:
            raise ValueError("min_rows must be positive.")

        if self.min_target_classes < 2:
            raise ValueError("min_target_classes must be at least 2.")

        if not 0 < self.max_majority_class_ratio <= 1:
            raise ValueError("max_majority_class_ratio must be between 0 and 1.")


@dataclass(frozen=True)
class DatasetQualityIssue:
    severity: DatasetQualitySeverity
    code: str
    message: str
    column: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "column": self.column,
        }


@dataclass(frozen=True)
class FeatureQualitySummary:
    column: str
    missing_count: int
    missing_ratio: float
    unique_count: int
    is_constant: bool
    min_value: float | None
    max_value: float | None
    mean_value: float | None
    std_value: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "missing_count": self.missing_count,
            "missing_ratio": self.missing_ratio,
            "unique_count": self.unique_count,
            "is_constant": self.is_constant,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "mean_value": self.mean_value,
            "std_value": self.std_value,
        }


@dataclass(frozen=True)
class DatasetQualityReport:
    valid: bool
    rows: int
    columns: tuple[str, ...]
    feature_columns: tuple[str, ...]
    target_column: str | None
    target_distribution: dict[str, int]
    target_ratios: dict[str, float]
    majority_class: str | None
    majority_class_ratio: float | None
    leakage_columns: tuple[str, ...]
    constant_feature_columns: tuple[str, ...]
    feature_summaries: tuple[FeatureQualitySummary, ...]
    validation: DatasetValidationResult
    issues: tuple[DatasetQualityIssue, ...] = field(default_factory=tuple)

    @property
    def errors(self) -> tuple[DatasetQualityIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == DatasetQualitySeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[DatasetQualityIssue, ...]:
        return tuple(
            issue
            for issue in self.issues
            if issue.severity == DatasetQualitySeverity.WARNING
        )

    def raise_if_invalid(self) -> None:
        if self.valid:
            return

        messages = "; ".join(issue.message for issue in self.errors)
        raise ValueError(f"Dataset quality check failed: {messages}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "rows": self.rows,
            "columns": list(self.columns),
            "feature_columns": list(self.feature_columns),
            "target_column": self.target_column,
            "target_distribution": self.target_distribution,
            "target_ratios": self.target_ratios,
            "majority_class": self.majority_class,
            "majority_class_ratio": self.majority_class_ratio,
            "leakage_columns": list(self.leakage_columns),
            "constant_feature_columns": list(self.constant_feature_columns),
            "feature_summaries": [
                summary.to_dict() for summary in self.feature_summaries
            ],
            "validation": self.validation.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def optional_float(value: object) -> float | None:
    if pd.isna(value):
        return None

    return float(value)


def build_target_distribution(
    dataframe: pd.DataFrame,
    target_column: str,
) -> dict[str, int]:
    if target_column not in dataframe.columns:
        return {}

    counts = dataframe[target_column].astype(str).str.lower().value_counts()

    return {
        str(label): int(count)
        for label, count in counts.sort_index().items()
    }


def build_target_ratios(
    target_distribution: dict[str, int],
) -> dict[str, float]:
    total = sum(target_distribution.values())

    if total == 0:
        return {}

    return {
        label: count / total
        for label, count in target_distribution.items()
    }


def summarize_feature_quality(
    dataframe: pd.DataFrame,
    feature_columns: tuple[str, ...],
) -> tuple[FeatureQualitySummary, ...]:
    summaries: list[FeatureQualitySummary] = []

    for column in feature_columns:
        numeric_series = pd.to_numeric(dataframe[column], errors="coerce")
        missing_count = int(numeric_series.isna().sum())
        missing_ratio = missing_count / len(dataframe) if len(dataframe) else 0.0
        non_null_series = numeric_series.dropna()
        unique_count = int(non_null_series.nunique())
        is_constant = unique_count <= 1

        summaries.append(
            FeatureQualitySummary(
                column=column,
                missing_count=missing_count,
                missing_ratio=missing_ratio,
                unique_count=unique_count,
                is_constant=is_constant,
                min_value=optional_float(non_null_series.min())
                if not non_null_series.empty
                else None,
                max_value=optional_float(non_null_series.max())
                if not non_null_series.empty
                else None,
                mean_value=optional_float(non_null_series.mean())
                if not non_null_series.empty
                else None,
                std_value=optional_float(non_null_series.std())
                if len(non_null_series) > 1
                else None,
            )
        )

    return tuple(summaries)


def build_dataset_quality_report(
    dataframe: pd.DataFrame,
    config: DatasetQualityConfig | None = None,
) -> DatasetQualityReport:
    active_config = config or DatasetQualityConfig()
    issues: list[DatasetQualityIssue] = []

    validation = validate_signal_training_dataset(dataframe)

    for validation_issue in validation.errors:
        issues.append(
            DatasetQualityIssue(
                severity=DatasetQualitySeverity.ERROR,
                code=f"schema_{validation_issue.code}",
                message=validation_issue.message,
                column=validation_issue.column,
            )
        )

    if len(dataframe) < active_config.min_rows:
        issues.append(
            DatasetQualityIssue(
                severity=DatasetQualitySeverity.ERROR,
                code="quality_not_enough_rows",
                message=(
                    f"Dataset must contain at least {active_config.min_rows} rows. "
                    f"Received {len(dataframe)} rows."
                ),
            )
        )

    target_distribution = build_target_distribution(
        dataframe,
        active_config.target_column,
    )
    target_ratios = build_target_ratios(target_distribution)

    majority_class = None
    majority_class_ratio = None

    if target_distribution:
        majority_class = max(target_distribution, key=target_distribution.get)
        majority_class_ratio = target_ratios[majority_class]

        if len(target_distribution) < active_config.min_target_classes:
            issues.append(
                DatasetQualityIssue(
                    severity=DatasetQualitySeverity.ERROR,
                    code="quality_not_enough_target_classes",
                    message=(
                        f"Target column must contain at least "
                        f"{active_config.min_target_classes} classes."
                    ),
                    column=active_config.target_column,
                )
            )

        if majority_class_ratio > active_config.max_majority_class_ratio:
            issues.append(
                DatasetQualityIssue(
                    severity=DatasetQualitySeverity.WARNING,
                    code="quality_class_imbalance",
                    message=(
                        f"Majority class {majority_class} ratio is "
                        f"{majority_class_ratio:.4f}."
                    ),
                    column=active_config.target_column,
                )
            )

    leakage_result = check_feature_columns_for_leakage(validation.feature_columns)

    if not leakage_result.valid:
        issues.append(
            DatasetQualityIssue(
                severity=DatasetQualitySeverity.ERROR,
                code="quality_feature_leakage",
                message=(
                    "Feature columns contain future/outcome leakage columns: "
                    f"{list(leakage_result.leaked_columns)}"
                ),
            )
        )

    feature_summaries = summarize_feature_quality(
        dataframe,
        validation.feature_columns,
    )

    constant_feature_columns = tuple(
        summary.column for summary in feature_summaries if summary.is_constant
    )

    for column in constant_feature_columns:
        issues.append(
            DatasetQualityIssue(
                severity=DatasetQualitySeverity.WARNING,
                code="quality_constant_feature",
                message=f"Feature column is constant: {column}",
                column=column,
            )
        )

    for summary in feature_summaries:
        if summary.missing_count > 0:
            issues.append(
                DatasetQualityIssue(
                    severity=DatasetQualitySeverity.WARNING,
                    code="quality_feature_missing_values",
                    message=(
                        f"Feature column {summary.column} has "
                        f"{summary.missing_count} missing values."
                    ),
                    column=summary.column,
                )
            )

    valid = not any(
        issue.severity == DatasetQualitySeverity.ERROR for issue in issues
    )

    return DatasetQualityReport(
        valid=valid,
        rows=len(dataframe),
        columns=tuple(str(column) for column in dataframe.columns),
        feature_columns=validation.feature_columns,
        target_column=validation.target_column,
        target_distribution=target_distribution,
        target_ratios=target_ratios,
        majority_class=majority_class,
        majority_class_ratio=majority_class_ratio,
        leakage_columns=leakage_result.leaked_columns,
        constant_feature_columns=constant_feature_columns,
        feature_summaries=feature_summaries,
        validation=validation,
        issues=tuple(issues),
    )


def write_dataset_quality_report(
    path: str | Path,
    report: DatasetQualityReport,
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )

    return output_path


__all__ = [
    "DatasetQualityConfig",
    "DatasetQualityIssue",
    "DatasetQualityReport",
    "DatasetQualitySeverity",
    "FeatureQualitySummary",
    "build_dataset_quality_report",
    "build_target_distribution",
    "build_target_ratios",
    "summarize_feature_quality",
    "write_dataset_quality_report",
]