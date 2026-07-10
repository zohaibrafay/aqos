from __future__ import annotations

import pandas as pd
import pytest

from aqos.model_training import (
    OHLCVFeatureBuilderConfig,
    build_ohlcv_ml_features,
    build_ohlcv_ml_features_from_csv,
    load_ohlcv_csv,
    validate_ohlcv_dataframe,
    validate_signal_training_dataset,
)


def build_ohlcv_dataset(rows: int = 30) -> pd.DataFrame:
    records = []

    for index in range(rows):
        open_price = 2300.0 + index
        close_price = open_price + (0.5 if index % 2 == 0 else -0.25)
        high_price = max(open_price, close_price) + 1.0
        low_price = min(open_price, close_price) - 1.0

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
                "target": "buy" if index % 3 == 0 else "sell" if index % 3 == 1 else "hold",
            }
        )

    return pd.DataFrame(records)


def test_validate_ohlcv_dataframe_accepts_valid_ohlcv_data() -> None:
    validate_ohlcv_dataframe(build_ohlcv_dataset())


def test_validate_ohlcv_dataframe_rejects_missing_required_column() -> None:
    dataset = build_ohlcv_dataset().drop(columns=["close"])

    with pytest.raises(ValueError, match="Missing required OHLCV columns"):
        validate_ohlcv_dataframe(dataset)


def test_validate_ohlcv_dataframe_rejects_invalid_high_low_relationships() -> None:
    dataset = build_ohlcv_dataset()
    dataset.loc[0, "high"] = dataset.loc[0, "low"] - 1

    with pytest.raises(ValueError, match="invalid high/low"):
        validate_ohlcv_dataframe(dataset)


def test_validate_ohlcv_dataframe_rejects_negative_volume() -> None:
    dataset = build_ohlcv_dataset()
    dataset.loc[0, "volume"] = -1

    with pytest.raises(ValueError, match="volume cannot be negative"):
        validate_ohlcv_dataframe(dataset)


def test_build_ohlcv_ml_features_adds_price_and_candle_features() -> None:
    features = build_ohlcv_ml_features(build_ohlcv_dataset())

    expected_columns = {
        "return_1",
        "return_3",
        "return_5",
        "log_return_1",
        "high_low_range",
        "candle_body",
        "candle_body_ratio",
        "upper_wick",
        "lower_wick",
        "upper_wick_ratio",
        "lower_wick_ratio",
        "close_position_in_range",
    }

    assert expected_columns.issubset(set(features.columns))
    assert features["high_low_range"].min() > 0


def test_build_ohlcv_ml_features_adds_volatility_trend_and_volume_features() -> None:
    features = build_ohlcv_ml_features(build_ohlcv_dataset())

    expected_columns = {
        "true_range",
        "atr_proxy_14",
        "rolling_volatility_5",
        "rolling_volatility_14",
        "sma_5",
        "sma_20",
        "sma_distance_5",
        "sma_distance_20",
        "volume_change_1",
        "volume_zscore_20",
    }

    assert expected_columns.issubset(set(features.columns))


def test_build_ohlcv_ml_features_adds_time_features_when_timestamp_exists() -> None:
    features = build_ohlcv_ml_features(build_ohlcv_dataset())

    expected_columns = {
        "hour",
        "day_of_week",
        "session_asia",
        "session_london",
        "session_new_york",
        "session_off_hours",
    }

    assert expected_columns.issubset(set(features.columns))


def test_build_ohlcv_ml_features_can_skip_time_features() -> None:
    features = build_ohlcv_ml_features(
        build_ohlcv_dataset(),
        config=OHLCVFeatureBuilderConfig(include_time_features=False),
    )

    assert "hour" not in features.columns
    assert "session_london" not in features.columns


def test_build_ohlcv_ml_features_output_passes_signal_training_schema() -> None:
    features = build_ohlcv_ml_features(build_ohlcv_dataset())

    result = validate_signal_training_dataset(features)

    assert result.valid is True
    assert "return_1" in result.feature_columns
    assert "candle_body_ratio" in result.feature_columns
    assert "rolling_volatility_14" in result.feature_columns


def test_build_ohlcv_ml_features_from_csv_writes_output_file(tmp_path) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    output_path = tmp_path / "features" / "ml_features.csv"

    build_ohlcv_dataset().to_csv(input_path, index=False)

    written_path = build_ohlcv_ml_features_from_csv(input_path, output_path)
    features = pd.read_csv(written_path)

    assert written_path == output_path
    assert output_path.exists()
    assert "return_1" in features.columns
    assert "candle_body_ratio" in features.columns


def test_load_ohlcv_csv_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_ohlcv_csv(tmp_path / "missing.csv")


def test_load_ohlcv_csv_rejects_non_csv_file(tmp_path) -> None:
    path = tmp_path / "raw.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="CSV"):
        load_ohlcv_csv(path)