from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

import pandas as pd


VALID_SIGNAL_TARGETS = {"buy", "sell", "hold"}


class FeatureColumnRole(str, Enum):
    IDENTIFIER = "identifier"
    TIMESTAMP = "timestamp"
    NUMERIC_FEATURE = "numeric_feature"
    CATEGORICAL_FEATURE = "categorical_feature"
    TARGET = "target"
    IGNORED = "ignored"


class DatasetIssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class FeatureColumnSpec:
    name: str
    role: FeatureColumnRole
    required: bool = True
    allow_null: bool = False
    allowed_values: tuple[str, ...] = ()
    min_value: float | None = None
    max_value: float | None = None

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("Feature column name cannot be empty.")

        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                raise ValueError("Feature column min_value cannot exceed max_value.")


@dataclass(frozen=True)
class DatasetValidationIssue:
    severity: DatasetIssueSeverity
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
class DatasetValidationResult:
    schema_name: str
    valid: bool
    rows: int
    columns: tuple[str, ...]
    feature_columns: tuple[str, ...]
    target_column: str | None
    issues: tuple[DatasetValidationIssue, ...]

    @property
    def errors(self) -> tuple[DatasetValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == DatasetIssueSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[DatasetValidationIssue, ...]:
        return tuple(
            issue for issue in self.issues if issue.severity == DatasetIssueSeverity.WARNING
        )

    def raise_if_invalid(self) -> None:
        if self.valid:
            return

        messages = "; ".join(issue.message for issue in self.errors)
        raise ValueError(f"Dataset validation failed: {messages}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_name": self.schema_name,
            "valid": self.valid,
            "rows": self.rows,
            "columns": list(self.columns),
            "feature_columns": list(self.feature_columns),
            "target_column": self.target_column,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class MLFeatureSchema:
    name: str
    columns: tuple[FeatureColumnSpec, ...]
    min_rows: int = 8

    def __post_init__(self) -> None:
        if not self.name or not self.name.strip():
            raise ValueError("ML feature schema name cannot be empty.")

        if self.min_rows < 1:
            raise ValueError("ML feature schema min_rows must be positive.")

        names = [column.name for column in self.columns]
        duplicate_names = sorted({name for name in names if names.count(name) > 1})
        if duplicate_names:
            raise ValueError(f"Duplicate feature schema columns: {duplicate_names}")

        target_columns = [
            column.name for column in self.columns if column.role == FeatureColumnRole.TARGET
        ]
        if len(target_columns) > 1:
            raise ValueError("ML feature schema can only define one target column.")

    @property
    def target_column(self) -> str | None:
        for column in self.columns:
            if column.role == FeatureColumnRole.TARGET:
                return column.name
        return None

    @property
    def required_columns(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns if column.required)

    @property
    def numeric_feature_columns(self) -> tuple[str, ...]:
        return tuple(
            column.name
            for column in self.columns
            if column.role == FeatureColumnRole.NUMERIC_FEATURE
        )

    @property
    def categorical_feature_columns(self) -> tuple[str, ...]:
        return tuple(
            column.name
            for column in self.columns
            if column.role == FeatureColumnRole.CATEGORICAL_FEATURE
        )

    def available_feature_columns(
        self,
        dataframe: pd.DataFrame,
        include_categorical: bool = False,
    ) -> tuple[str, ...]:
        roles = {FeatureColumnRole.NUMERIC_FEATURE}

        if include_categorical:
            roles.add(FeatureColumnRole.CATEGORICAL_FEATURE)

        return tuple(
            column.name
            for column in self.columns
            if column.role in roles and column.name in dataframe.columns
        )

    def validate(
        self,
        dataframe: pd.DataFrame,
        require_target: bool = True,
    ) -> DatasetValidationResult:
        issues: list[DatasetValidationIssue] = []

        if dataframe.empty:
            issues.append(
                DatasetValidationIssue(
                    severity=DatasetIssueSeverity.ERROR,
                    code="empty_dataset",
                    message="ML dataset cannot be empty.",
                )
            )

        if len(dataframe) < self.min_rows:
            issues.append(
                DatasetValidationIssue(
                    severity=DatasetIssueSeverity.ERROR,
                    code="not_enough_rows",
                    message=(
                        f"ML dataset must contain at least {self.min_rows} rows. "
                        f"Received {len(dataframe)} rows."
                    ),
                )
            )

        dataframe_columns = tuple(str(column) for column in dataframe.columns)

        duplicate_dataframe_columns = sorted(
            {column for column in dataframe_columns if dataframe_columns.count(column) > 1}
        )
        if duplicate_dataframe_columns:
            issues.append(
                DatasetValidationIssue(
                    severity=DatasetIssueSeverity.ERROR,
                    code="duplicate_columns",
                    message=f"Dataset contains duplicate columns: {duplicate_dataframe_columns}",
                )
            )

        for column in self.columns:
            if column.role == FeatureColumnRole.TARGET and not require_target:
                continue

            if column.required and column.name not in dataframe.columns:
                issues.append(
                    DatasetValidationIssue(
                        severity=DatasetIssueSeverity.ERROR,
                        code="missing_required_column",
                        message=f"Required column is missing: {column.name}",
                        column=column.name,
                    )
                )
                continue

            if column.name not in dataframe.columns:
                continue

            series = dataframe[column.name]

            if not column.allow_null and series.isna().any():
                issues.append(
                    DatasetValidationIssue(
                        severity=DatasetIssueSeverity.ERROR,
                        code="null_values_not_allowed",
                        message=f"Column contains null values: {column.name}",
                        column=column.name,
                    )
                )

            if column.role == FeatureColumnRole.NUMERIC_FEATURE:
                if not pd.api.types.is_numeric_dtype(series):
                    issues.append(
                        DatasetValidationIssue(
                            severity=DatasetIssueSeverity.ERROR,
                            code="non_numeric_feature",
                            message=f"Feature column must be numeric: {column.name}",
                            column=column.name,
                        )
                    )
                else:
                    non_null_series = series.dropna()

                    if column.min_value is not None and (non_null_series < column.min_value).any():
                        issues.append(
                            DatasetValidationIssue(
                                severity=DatasetIssueSeverity.ERROR,
                                code="value_below_minimum",
                                message=(
                                    f"Column {column.name} contains values below "
                                    f"{column.min_value}."
                                ),
                                column=column.name,
                            )
                        )

                    if column.max_value is not None and (non_null_series > column.max_value).any():
                        issues.append(
                            DatasetValidationIssue(
                                severity=DatasetIssueSeverity.ERROR,
                                code="value_above_maximum",
                                message=(
                                    f"Column {column.name} contains values above "
                                    f"{column.max_value}."
                                ),
                                column=column.name,
                            )
                        )

            if column.role == FeatureColumnRole.TARGET:
                normalized_values = set(series.dropna().astype(str).str.lower().unique())

                if column.allowed_values:
                    allowed_values = set(column.allowed_values)
                    unsupported_values = sorted(normalized_values - allowed_values)
                    if unsupported_values:
                        issues.append(
                            DatasetValidationIssue(
                                severity=DatasetIssueSeverity.ERROR,
                                code="unsupported_target_values",
                                message=(
                                    f"Target column {column.name} contains unsupported "
                                    f"values: {unsupported_values}"
                                ),
                                column=column.name,
                            )
                        )

                if len(normalized_values) < 2:
                    issues.append(
                        DatasetValidationIssue(
                            severity=DatasetIssueSeverity.ERROR,
                            code="not_enough_target_classes",
                            message=(
                                f"Target column {column.name} must contain at least "
                                "two classes."
                            ),
                            column=column.name,
                        )
                    )

        feature_columns = self.available_feature_columns(dataframe)

        if not feature_columns:
            issues.append(
                DatasetValidationIssue(
                    severity=DatasetIssueSeverity.ERROR,
                    code="no_feature_columns",
                    message="Dataset does not contain any usable feature columns.",
                )
            )

        return DatasetValidationResult(
            schema_name=self.name,
            valid=not any(issue.severity == DatasetIssueSeverity.ERROR for issue in issues),
            rows=len(dataframe),
            columns=tuple(dataframe_columns),
            feature_columns=feature_columns,
            target_column=self.target_column,
            issues=tuple(issues),
        )


def build_default_signal_feature_schema() -> MLFeatureSchema:
    return MLFeatureSchema(
        name="aqos_default_signal_feature_schema",
        min_rows=8,
        columns=(
            FeatureColumnSpec("timestamp", FeatureColumnRole.TIMESTAMP, required=False),
            FeatureColumnSpec("symbol", FeatureColumnRole.IDENTIFIER, required=False),
            FeatureColumnSpec("timeframe", FeatureColumnRole.IDENTIFIER, required=False),
            FeatureColumnSpec("open", FeatureColumnRole.NUMERIC_FEATURE),
            FeatureColumnSpec("high", FeatureColumnRole.NUMERIC_FEATURE),
            FeatureColumnSpec("low", FeatureColumnRole.NUMERIC_FEATURE),
            FeatureColumnSpec("close", FeatureColumnRole.NUMERIC_FEATURE),
            FeatureColumnSpec("volume", FeatureColumnRole.NUMERIC_FEATURE, min_value=0),
            FeatureColumnSpec("rsi_14", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("macd_histogram", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("atr_14", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("return_5", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("return_1", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("return_3", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("log_return_1", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("high_low_range", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("candle_body", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("upper_wick", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("lower_wick", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("close_position_in_range", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("true_range", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("atr_proxy_14", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("rolling_volatility_5", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("rolling_volatility_14", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("sma_5", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("sma_20", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("sma_distance_5", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("sma_distance_20", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("volume_change_1", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("volume_zscore_20", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("hour", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("day_of_week", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("session_asia", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("session_london", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("session_new_york", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("session_off_hours", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("candle_body_ratio", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("upper_wick_ratio", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec("lower_wick_ratio", FeatureColumnRole.NUMERIC_FEATURE, required=False),
            FeatureColumnSpec(
                "target",
                FeatureColumnRole.TARGET,
                allowed_values=tuple(sorted(VALID_SIGNAL_TARGETS)),
            ),
            FeatureColumnSpec("future_close", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("future_return", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("future_max_high_return", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("future_max_low_return", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("buy_take_profit_hit", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("buy_stop_loss_hit", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("sell_take_profit_hit", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("sell_stop_loss_hit", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("take_profit_hit", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("stop_loss_hit", FeatureColumnRole.IGNORED, required=False),
            FeatureColumnSpec("trade_quality_score", FeatureColumnRole.IGNORED, required=False),
        ),
    )


def validate_signal_training_dataset(
    dataframe: pd.DataFrame,
    schema: MLFeatureSchema | None = None,
) -> DatasetValidationResult:
    active_schema = schema or build_default_signal_feature_schema()
    return active_schema.validate(dataframe, require_target=True)


def validate_signal_prediction_dataset(
    dataframe: pd.DataFrame,
    schema: MLFeatureSchema | None = None,
) -> DatasetValidationResult:
    active_schema = schema or build_default_signal_feature_schema()

    prediction_schema = replace(
        active_schema,
        min_rows=1,
    )

    return prediction_schema.validate(dataframe, require_target=False)


def select_model_feature_columns(
    dataframe: pd.DataFrame,
    schema: MLFeatureSchema | None = None,
) -> tuple[str, ...]:
    active_schema = schema or build_default_signal_feature_schema()
    result = active_schema.validate(
        dataframe,
        require_target=active_schema.target_column in dataframe.columns,
    )
    result.raise_if_invalid()
    return result.feature_columns


def select_model_features(
    dataframe: pd.DataFrame,
    schema: MLFeatureSchema | None = None,
) -> pd.DataFrame:
    columns = select_model_feature_columns(dataframe, schema=schema)
    return dataframe.loc[:, list(columns)]


__all__ = [
    "DatasetIssueSeverity",
    "DatasetValidationIssue",
    "DatasetValidationResult",
    "FeatureColumnRole",
    "FeatureColumnSpec",
    "MLFeatureSchema",
    "VALID_SIGNAL_TARGETS",
    "build_default_signal_feature_schema",
    "select_model_feature_columns",
    "select_model_features",
    "validate_signal_prediction_dataset",
    "validate_signal_training_dataset",
]