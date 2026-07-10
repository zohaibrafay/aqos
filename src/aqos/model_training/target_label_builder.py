from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from aqos.model_training.ohlcv_feature_builder import (
    load_ohlcv_csv,
    safe_divide,
    validate_ohlcv_dataframe,
)


@dataclass(frozen=True)
class SignalTargetLabelConfig:
    horizon_bars: int = 5
    min_signal_return: float = 0.001
    take_profit_return: float = 0.002
    stop_loss_return: float = 0.001
    target_column: str = "target"
    drop_incomplete_horizon: bool = True

    def __post_init__(self) -> None:
        if self.horizon_bars < 1:
            raise ValueError("horizon_bars must be at least 1.")

        if self.min_signal_return <= 0:
            raise ValueError("min_signal_return must be positive.")

        if self.take_profit_return <= 0:
            raise ValueError("take_profit_return must be positive.")

        if self.stop_loss_return <= 0:
            raise ValueError("stop_loss_return must be positive.")

        if not self.target_column.strip():
            raise ValueError("target_column cannot be empty.")


def future_rolling_max(series: pd.Series, horizon_bars: int) -> pd.Series:
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be at least 1.")

    future_values = [
        series.shift(-step)
        for step in range(1, horizon_bars + 1)
    ]

    return pd.concat(future_values, axis=1).max(axis=1)


def future_rolling_min(series: pd.Series, horizon_bars: int) -> pd.Series:
    if horizon_bars < 1:
        raise ValueError("horizon_bars must be at least 1.")

    future_values = [
        series.shift(-step)
        for step in range(1, horizon_bars + 1)
    ]

    return pd.concat(future_values, axis=1).min(axis=1)


def assign_signal_target(
    future_return: float,
    min_signal_return: float,
) -> str:
    if pd.isna(future_return):
        return "hold"

    if future_return >= min_signal_return:
        return "buy"

    if future_return <= -min_signal_return:
        return "sell"

    return "hold"


def add_future_movement_columns(
    dataframe: pd.DataFrame,
    config: SignalTargetLabelConfig,
) -> pd.DataFrame:
    output = dataframe.copy()

    future_close = output["close"].shift(-config.horizon_bars)
    future_high = future_rolling_max(output["high"], config.horizon_bars)
    future_low = future_rolling_min(output["low"], config.horizon_bars)

    output["future_close"] = future_close
    output["future_return"] = safe_divide(future_close - output["close"], output["close"])
    output["future_max_high_return"] = safe_divide(
        future_high - output["close"],
        output["close"],
    )
    output["future_max_low_return"] = safe_divide(
        future_low - output["close"],
        output["close"],
    )

    return output


def add_signal_targets(
    dataframe: pd.DataFrame,
    config: SignalTargetLabelConfig,
) -> pd.DataFrame:
    output = dataframe.copy()

    output[config.target_column] = output["future_return"].map(
        lambda value: assign_signal_target(value, config.min_signal_return)
    )

    return output


def add_trade_outcome_columns(
    dataframe: pd.DataFrame,
    config: SignalTargetLabelConfig,
) -> pd.DataFrame:
    output = dataframe.copy()

    buy_take_profit_hit = output["future_max_high_return"] >= config.take_profit_return
    buy_stop_loss_hit = output["future_max_low_return"] <= -config.stop_loss_return

    sell_take_profit_hit = output["future_max_low_return"] <= -config.take_profit_return
    sell_stop_loss_hit = output["future_max_high_return"] >= config.stop_loss_return

    output["buy_take_profit_hit"] = buy_take_profit_hit.astype(int)
    output["buy_stop_loss_hit"] = buy_stop_loss_hit.astype(int)
    output["sell_take_profit_hit"] = sell_take_profit_hit.astype(int)
    output["sell_stop_loss_hit"] = sell_stop_loss_hit.astype(int)

    output["take_profit_hit"] = (
        (
            (output[config.target_column] == "buy")
            & buy_take_profit_hit
        )
        | (
            (output[config.target_column] == "sell")
            & sell_take_profit_hit
        )
    ).astype(int)

    output["stop_loss_hit"] = (
        (
            (output[config.target_column] == "buy")
            & buy_stop_loss_hit
        )
        | (
            (output[config.target_column] == "sell")
            & sell_stop_loss_hit
        )
    ).astype(int)

    return output


def add_trade_quality_score(
    dataframe: pd.DataFrame,
    config: SignalTargetLabelConfig,
) -> pd.DataFrame:
    output = dataframe.copy()

    buy_quality = (
        output["future_max_high_return"]
        - output["future_max_low_return"].abs()
    )

    sell_quality = (
        output["future_max_low_return"].abs()
        - output["future_max_high_return"]
    )

    hold_quality = -output["future_return"].abs()

    output["trade_quality_score"] = 0.0
    output.loc[output[config.target_column] == "buy", "trade_quality_score"] = buy_quality
    output.loc[output[config.target_column] == "sell", "trade_quality_score"] = sell_quality
    output.loc[output[config.target_column] == "hold", "trade_quality_score"] = hold_quality

    output["trade_quality_score"] = pd.to_numeric(
        output["trade_quality_score"],
        errors="coerce",
    ).fillna(0.0)

    return output


def build_signal_target_labels(
    dataframe: pd.DataFrame,
    config: SignalTargetLabelConfig | None = None,
) -> pd.DataFrame:
    active_config = config or SignalTargetLabelConfig()

    validate_ohlcv_dataframe(dataframe)

    if len(dataframe) <= active_config.horizon_bars:
        raise ValueError(
            "Dataset must contain more rows than horizon_bars to build target labels."
        )

    output = dataframe.copy()
    output = add_future_movement_columns(output, active_config)
    output = add_signal_targets(output, active_config)
    output = add_trade_outcome_columns(output, active_config)
    output = add_trade_quality_score(output, active_config)

    if active_config.drop_incomplete_horizon:
        output = output.iloc[:-active_config.horizon_bars].copy()

    return output.reset_index(drop=True)


def build_signal_target_labels_from_csv(
    input_path: str | Path,
    output_path: str | Path,
    config: SignalTargetLabelConfig | None = None,
) -> Path:
    dataframe = load_ohlcv_csv(input_path)
    labeled = build_signal_target_labels(dataframe, config=config)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    labeled.to_csv(path, index=False)

    return path


__all__ = [
    "SignalTargetLabelConfig",
    "add_future_movement_columns",
    "add_signal_targets",
    "add_trade_outcome_columns",
    "add_trade_quality_score",
    "assign_signal_target",
    "build_signal_target_labels",
    "build_signal_target_labels_from_csv",
    "future_rolling_max",
    "future_rolling_min",
]