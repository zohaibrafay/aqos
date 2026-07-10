from __future__ import annotations

import pandas as pd
import pytest

from aqos.model_training import (
    DatasetIssueSeverity,
    FeatureColumnRole,
    FeatureColumnSpec,
    MLFeatureSchema,
    build_default_signal_feature_schema,
    select_model_feature_columns,
    select_model_features,
    validate_signal_prediction_dataset,
    validate_signal_training_dataset,
)


def build_valid_training_dataset() -> pd.DataFrame:
    rows = []

    targets = ["buy", "sell", "hold", "buy", "sell", "hold", "buy", "sell"]

    for index, target in enumerate(targets):
        rows.append(
            {
                "timestamp": f"2026-01-01 00:{index:02d}:00",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "open": 2300.0 + index,
                "high": 2302.0 + index,
                "low": 2298.0 + index,
                "close": 2301.0 + index,
                "volume": 1000 + index,
                "rsi_14": 40.0 + index,
                "macd_histogram": 0.1 * index,
                "atr_14": 1.5 + index * 0.01,
                "return_5": 0.001 * index,
                "target": target,
            }
        )

    return pd.DataFrame(rows)


def test_default_signal_feature_schema_validates_training_dataset() -> None:
    dataset = build_valid_training_dataset()

    result = validate_signal_training_dataset(dataset)

    assert result.valid is True
    assert result.errors == ()
    assert result.rows == 8
    assert result.target_column == "target"
    assert result.feature_columns == (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "rsi_14",
        "macd_histogram",
        "atr_14",
        "return_5",
    )


def test_default_signal_feature_schema_validates_prediction_dataset_without_target() -> None:
    dataset = build_valid_training_dataset().drop(columns=["target"])

    result = validate_signal_prediction_dataset(dataset)

    assert result.valid is True
    assert result.target_column == "target"
    assert result.feature_columns[:5] == ("open", "high", "low", "close", "volume")


def test_signal_feature_schema_detects_missing_required_column() -> None:
    dataset = build_valid_training_dataset().drop(columns=["close"])

    result = validate_signal_training_dataset(dataset)

    assert result.valid is False
    assert any(issue.code == "missing_required_column" for issue in result.errors)


def test_signal_feature_schema_detects_unsupported_target_values() -> None:
    dataset = build_valid_training_dataset()
    dataset.loc[0, "target"] = "strong_buy"

    result = validate_signal_training_dataset(dataset)

    assert result.valid is False
    assert any(issue.code == "unsupported_target_values" for issue in result.errors)


def test_signal_feature_schema_detects_non_numeric_feature() -> None:
    dataset = build_valid_training_dataset()
    dataset["open"] = "bad"

    result = validate_signal_training_dataset(dataset)

    assert result.valid is False
    assert any(issue.code == "non_numeric_feature" for issue in result.errors)


def test_signal_feature_schema_detects_null_values() -> None:
    dataset = build_valid_training_dataset()
    dataset.loc[0, "volume"] = None

    result = validate_signal_training_dataset(dataset)

    assert result.valid is False
    assert any(issue.code == "null_values_not_allowed" for issue in result.errors)


def test_signal_feature_schema_detects_negative_volume() -> None:
    dataset = build_valid_training_dataset()
    dataset.loc[0, "volume"] = -1

    result = validate_signal_training_dataset(dataset)

    assert result.valid is False
    assert any(issue.code == "value_below_minimum" for issue in result.errors)


def test_select_model_feature_columns_returns_available_numeric_features() -> None:
    dataset = build_valid_training_dataset()

    columns = select_model_feature_columns(dataset)

    assert "target" not in columns
    assert "symbol" not in columns
    assert columns[:5] == ("open", "high", "low", "close", "volume")


def test_select_model_features_returns_feature_dataframe() -> None:
    dataset = build_valid_training_dataset()

    features = select_model_features(dataset)

    assert isinstance(features, pd.DataFrame)
    assert "target" not in features.columns
    assert list(features.columns[:5]) == ["open", "high", "low", "close", "volume"]


def test_validation_result_raise_if_invalid() -> None:
    dataset = build_valid_training_dataset().drop(columns=["target"])

    result = validate_signal_training_dataset(dataset)

    with pytest.raises(ValueError, match="Dataset validation failed"):
        result.raise_if_invalid()


def test_custom_schema_supports_optional_features() -> None:
    schema = MLFeatureSchema(
        name="custom_schema",
        min_rows=2,
        columns=(
            FeatureColumnSpec("close", FeatureColumnRole.NUMERIC_FEATURE),
            FeatureColumnSpec("target", FeatureColumnRole.TARGET, allowed_values=("buy", "sell")),
            FeatureColumnSpec("optional_atr", FeatureColumnRole.NUMERIC_FEATURE, required=False),
        ),
    )
    dataset = pd.DataFrame(
        {
            "close": [1.0, 2.0, 3.0, 4.0],
            "target": ["buy", "sell", "buy", "sell"],
        }
    )

    result = schema.validate(dataset)

    assert result.valid is True
    assert result.feature_columns == ("close",)


def test_dataset_issue_to_dict_contains_serializable_values() -> None:
    dataset = build_valid_training_dataset().drop(columns=["target"])

    result = validate_signal_training_dataset(dataset)
    payload = result.to_dict()

    assert payload["valid"] is False
    assert payload["issues"][0]["severity"] == DatasetIssueSeverity.ERROR.value