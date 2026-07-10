from __future__ import annotations
from unittest import result

import pandas as pd
import pytest

from aqos.model_training import (
    SignalTargetLabelConfig,
    assign_signal_target,
    build_ohlcv_ml_features,
    build_signal_target_labels,
    build_signal_target_labels_from_csv,
    future_rolling_max,
    future_rolling_min,
    validate_signal_training_dataset,
)


def build_mixed_ohlcv_dataset() -> pd.DataFrame:
    close_values = [
        100.0,
        101.0,
        102.0,
        103.0,
        104.0,
        105.0,
        104.0,
        103.0,
        102.0,
        101.0,
        100.0,
        100.1,
        100.0,
        100.1,
        100.0,
        100.1,
        100.0,
        101.0,
        102.0,
        103.0,
    ]

    rows = []

    for index, close_price in enumerate(close_values):
        open_price = close_price - 0.2
        high_price = close_price + 0.6
        low_price = close_price - 0.6

        rows.append(
            {
                "timestamp": f"2026-01-01 00:{index:02d}:00",
                "symbol": "XAUUSD",
                "timeframe": "M15",
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": 1000 + index,
            }
        )

    return pd.DataFrame(rows)


def test_assign_signal_target_maps_future_returns_to_labels() -> None:
    assert assign_signal_target(0.01, 0.001) == "buy"
    assert assign_signal_target(-0.01, 0.001) == "sell"
    assert assign_signal_target(0.0001, 0.001) == "hold"
    assert assign_signal_target(float("nan"), 0.001) == "hold"


def test_future_rolling_max_and_min_use_only_future_bars() -> None:
    series = pd.Series([10, 11, 9, 15, 8])

    assert future_rolling_max(series, horizon_bars=2).tolist()[:3] == [11.0, 15.0, 15.0]
    assert future_rolling_min(series, horizon_bars=2).tolist()[:3] == [9.0, 9.0, 8.0]


def test_signal_target_label_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="horizon_bars"):
        SignalTargetLabelConfig(horizon_bars=0)

    with pytest.raises(ValueError, match="min_signal_return"):
        SignalTargetLabelConfig(min_signal_return=0)


def test_build_signal_target_labels_adds_future_and_outcome_columns() -> None:
    labeled = build_signal_target_labels(
        build_mixed_ohlcv_dataset(),
        config=SignalTargetLabelConfig(
            horizon_bars=3,
            min_signal_return=0.005,
            take_profit_return=0.006,
            stop_loss_return=0.006,
        ),
    )

    expected_columns = {
        "future_close",
        "future_return",
        "future_max_high_return",
        "future_max_low_return",
        "target",
        "buy_take_profit_hit",
        "buy_stop_loss_hit",
        "sell_take_profit_hit",
        "sell_stop_loss_hit",
        "take_profit_hit",
        "stop_loss_hit",
        "trade_quality_score",
    }

    assert expected_columns.issubset(set(labeled.columns))
    assert len(labeled) == len(build_mixed_ohlcv_dataset()) - 3
    assert set(labeled["target"].unique()).issubset({"buy", "sell", "hold"})


def test_build_signal_target_labels_creates_multiple_target_classes() -> None:
    labeled = build_signal_target_labels(
        build_mixed_ohlcv_dataset(),
        config=SignalTargetLabelConfig(
            horizon_bars=3,
            min_signal_return=0.005,
        ),
    )

    assert len(set(labeled["target"].unique())) >= 2


def test_build_signal_target_labels_can_keep_incomplete_horizon_rows() -> None:
    source = build_mixed_ohlcv_dataset()

    labeled = build_signal_target_labels(
        source,
        config=SignalTargetLabelConfig(
            horizon_bars=3,
            drop_incomplete_horizon=False,
        ),
    )

    assert len(labeled) == len(source)


def test_labeled_feature_dataset_passes_signal_training_schema() -> None:
    labeled = build_signal_target_labels(
        build_mixed_ohlcv_dataset(),
        config=SignalTargetLabelConfig(
            horizon_bars=3,
            min_signal_return=0.005,
        ),
    )

    features = build_ohlcv_ml_features(labeled)
    result = validate_signal_training_dataset(features)

    assert result.valid is True
    assert "future_return" not in result.feature_columns
    assert "trade_quality_score" not in result.feature_columns
    assert "return_1" in result.feature_columns
    assert "candle_body_ratio" in result.feature_columns
    assert result.target_column == "target"


def test_build_signal_target_labels_rejects_dataset_shorter_than_horizon() -> None:
    dataset = build_mixed_ohlcv_dataset().head(3)

    with pytest.raises(ValueError, match="more rows than horizon_bars"):
        build_signal_target_labels(
            dataset,
            config=SignalTargetLabelConfig(horizon_bars=3),
        )


def test_build_signal_target_labels_from_csv_writes_output_file(tmp_path) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    output_path = tmp_path / "labels" / "signal_labels.csv"

    build_mixed_ohlcv_dataset().to_csv(input_path, index=False)

    written_path = build_signal_target_labels_from_csv(
        input_path,
        output_path,
        config=SignalTargetLabelConfig(horizon_bars=3),
    )
    labeled = pd.read_csv(written_path)

    assert written_path == output_path
    assert output_path.exists()
    assert "target" in labeled.columns
    assert "future_return" in labeled.columns