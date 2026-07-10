from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import math
import pandas as pd


REQUIRED_OHLCV_COLUMNS = ("open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class OHLCVFeatureBuilderConfig:
    timestamp_column: str = "timestamp"
    include_time_features: bool = True
    fill_missing_values: bool = True


def load_ohlcv_csv(path: str | Path) -> pd.DataFrame:
    csv_path = Path(path)

    if not csv_path.exists():
        raise FileNotFoundError(f"OHLCV CSV file does not exist: {csv_path}")

    if csv_path.suffix.lower() != ".csv":
        raise ValueError("OHLCV input must be a CSV file.")

    dataframe = pd.read_csv(csv_path)

    if dataframe.empty:
        raise ValueError("OHLCV CSV file is empty.")

    return dataframe


def validate_ohlcv_dataframe(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        raise ValueError("OHLCV dataframe cannot be empty.")

    missing_columns = [
        column for column in REQUIRED_OHLCV_COLUMNS if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(f"Missing required OHLCV columns: {missing_columns}")

    for column in REQUIRED_OHLCV_COLUMNS:
        if not pd.api.types.is_numeric_dtype(dataframe[column]):
            raise ValueError(f"OHLCV column must be numeric: {column}")

        if dataframe[column].isna().any():
            raise ValueError(f"OHLCV column contains null values: {column}")

    invalid_price_rows = dataframe[
        (dataframe["high"] < dataframe["low"])
        | (dataframe["high"] < dataframe["open"])
        | (dataframe["high"] < dataframe["close"])
        | (dataframe["low"] > dataframe["open"])
        | (dataframe["low"] > dataframe["close"])
    ]

    if not invalid_price_rows.empty:
        raise ValueError("OHLCV dataframe contains invalid high/low price relationships.")

    if (dataframe["volume"] < 0).any():
        raise ValueError("OHLCV volume cannot be negative.")


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    clean_denominator = denominator.replace(0, pd.NA)
    return numerator / clean_denominator


def add_price_return_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    output = dataframe.copy()

    close_ratio = output["close"] / output["close"].shift(1)
    close_ratio = close_ratio.where(close_ratio > 0)

    output["return_1"] = output["close"].pct_change(1, fill_method=None)
    output["return_3"] = output["close"].pct_change(3, fill_method=None)
    output["return_5"] = output["close"].pct_change(5, fill_method=None)
    output["log_return_1"] = close_ratio.map(
        lambda value: float("nan") if pd.isna(value) else math.log(float(value))
    )

    output["log_return_1"] = pd.to_numeric(
        output["log_return_1"],
        errors="coerce",
    )

    return output


def add_candle_structure_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    output = dataframe.copy()

    candle_range = output["high"] - output["low"]
    candle_body = output["close"] - output["open"]
    absolute_body = candle_body.abs()

    output["high_low_range"] = candle_range
    output["candle_body"] = candle_body
    output["candle_body_ratio"] = safe_divide(absolute_body, candle_range)
    output["upper_wick"] = output["high"] - output[["open", "close"]].max(axis=1)
    output["lower_wick"] = output[["open", "close"]].min(axis=1) - output["low"]
    output["upper_wick_ratio"] = safe_divide(output["upper_wick"], candle_range)
    output["lower_wick_ratio"] = safe_divide(output["lower_wick"], candle_range)
    output["close_position_in_range"] = safe_divide(output["close"] - output["low"], candle_range)

    return output


def add_volatility_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    output = dataframe.copy()

    previous_close = output["close"].shift(1)

    true_range = pd.concat(
        [
            output["high"] - output["low"],
            (output["high"] - previous_close).abs(),
            (output["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    output["true_range"] = true_range
    output["atr_proxy_14"] = true_range.rolling(window=14, min_periods=1).mean()
    output["rolling_volatility_5"] = output["return_1"].rolling(
        window=5,
        min_periods=1,
    ).std()
    output["rolling_volatility_14"] = output["return_1"].rolling(
        window=14,
        min_periods=1,
    ).std()

    return output


def add_trend_distance_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    output = dataframe.copy()

    sma_5 = output["close"].rolling(window=5, min_periods=1).mean()
    sma_20 = output["close"].rolling(window=20, min_periods=1).mean()

    output["sma_5"] = sma_5
    output["sma_20"] = sma_20
    output["sma_distance_5"] = safe_divide(output["close"] - sma_5, sma_5)
    output["sma_distance_20"] = safe_divide(output["close"] - sma_20, sma_20)

    return output


def add_volume_features(dataframe: pd.DataFrame) -> pd.DataFrame:
    output = dataframe.copy()

    rolling_volume_mean = output["volume"].rolling(window=20, min_periods=1).mean()
    rolling_volume_std = output["volume"].rolling(window=20, min_periods=1).std()

    output["volume_change_1"] = output["volume"].pct_change(1)
    output["volume_zscore_20"] = safe_divide(
        output["volume"] - rolling_volume_mean,
        rolling_volume_std,
    )

    return output


def resolve_session(hour: int) -> str:
    if 0 <= hour < 7:
        return "asia"

    if 7 <= hour < 13:
        return "london"

    if 13 <= hour < 21:
        return "new_york"

    return "off_hours"


def add_time_features(
    dataframe: pd.DataFrame,
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    output = dataframe.copy()

    if timestamp_column not in output.columns:
        return output

    timestamps = pd.to_datetime(output[timestamp_column], errors="coerce", utc=True)

    output["hour"] = timestamps.dt.hour
    output["day_of_week"] = timestamps.dt.dayofweek

    sessions = output["hour"].fillna(-1).astype(int).map(resolve_session)

    output["session_asia"] = (sessions == "asia").astype(int)
    output["session_london"] = (sessions == "london").astype(int)
    output["session_new_york"] = (sessions == "new_york").astype(int)
    output["session_off_hours"] = (sessions == "off_hours").astype(int)

    return output


def clean_feature_values(dataframe: pd.DataFrame) -> pd.DataFrame:
    output = dataframe.copy()
    numeric_columns = output.select_dtypes(include="number").columns

    output[numeric_columns] = output[numeric_columns].replace(
        [float("inf"), float("-inf")],
        pd.NA,
    )
    output[numeric_columns] = output[numeric_columns].fillna(0.0)

    return output


def build_ohlcv_ml_features(
    dataframe: pd.DataFrame,
    config: OHLCVFeatureBuilderConfig | None = None,
) -> pd.DataFrame:
    active_config = config or OHLCVFeatureBuilderConfig()

    validate_ohlcv_dataframe(dataframe)

    output = dataframe.copy()
    output = add_price_return_features(output)
    output = add_candle_structure_features(output)
    output = add_volatility_features(output)
    output = add_trend_distance_features(output)
    output = add_volume_features(output)

    if active_config.include_time_features:
        output = add_time_features(output, active_config.timestamp_column)

    if active_config.fill_missing_values:
        output = clean_feature_values(output)

    return output


def build_ohlcv_ml_features_from_csv(
    input_path: str | Path,
    output_path: str | Path,
    config: OHLCVFeatureBuilderConfig | None = None,
) -> Path:
    dataframe = load_ohlcv_csv(input_path)
    features = build_ohlcv_ml_features(dataframe, config=config)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(path, index=False)

    return path


__all__ = [
    "OHLCVFeatureBuilderConfig",
    "REQUIRED_OHLCV_COLUMNS",
    "add_candle_structure_features",
    "add_price_return_features",
    "add_time_features",
    "add_trend_distance_features",
    "add_volatility_features",
    "add_volume_features",
    "build_ohlcv_ml_features",
    "build_ohlcv_ml_features_from_csv",
    "clean_feature_values",
    "load_ohlcv_csv",
    "resolve_session",
    "safe_divide",
    "validate_ohlcv_dataframe",
]