from __future__ import annotations

import json

import pandas as pd
import pytest

from aqos.model_training import (
    OHLCVFeatureBuilderConfig,
    SignalMLDatasetBuildConfig,
    SignalTargetLabelConfig,
    build_signal_ml_training_dataset,
    build_signal_ml_training_dataset_from_csv,
    train_baseline_signal_model_from_csv,
    SignalTrainingRunConfig,
    validate_signal_ml_training_dataset,
)


def build_raw_ohlcv_dataset(rows: int = 40) -> pd.DataFrame:
    records = []

    for index in range(rows):
        phase = index % 12

        if phase <= 4:
            close_price = 2300.0 + phase
        elif phase <= 7:
            close_price = 2304.0 - (phase - 4)
        else:
            close_price = 2300.0 + (0.02 if phase % 2 else 0.0)

        open_price = close_price - 0.2
        high_price = max(open_price, close_price) + 1.2
        low_price = min(open_price, close_price) - 1.2

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
            }
        )

    return pd.DataFrame(records)


def test_build_signal_ml_training_dataset_creates_labels_and_features() -> None:
    dataset = build_signal_ml_training_dataset(
        build_raw_ohlcv_dataset(),
        config=SignalMLDatasetBuildConfig(
            label_config=SignalTargetLabelConfig(
                horizon_bars=3,
                min_signal_return=0.0002,
            )
        ),
    )

    expected_columns = {
        "target",
        "future_return",
        "trade_quality_score",
        "return_1",
        "return_5",
        "candle_body_ratio",
        "rolling_volatility_14",
        "sma_distance_20",
        "volume_zscore_20",
    }

    assert expected_columns.issubset(set(dataset.columns))
    assert len(dataset) == 37
    assert set(dataset["target"].unique()).issubset({"buy", "sell", "hold"})


def test_signal_ml_training_dataset_is_schema_valid_and_leakage_safe() -> None:
    dataset = build_signal_ml_training_dataset(
        build_raw_ohlcv_dataset(),
        config=SignalMLDatasetBuildConfig(
            label_config=SignalTargetLabelConfig(
                horizon_bars=3,
                min_signal_return=0.0002,
            )
        ),
    )

    validation = validate_signal_ml_training_dataset(dataset)

    assert validation.valid is True
    assert "future_return" not in validation.feature_columns
    assert "trade_quality_score" not in validation.feature_columns
    assert "return_1" in validation.feature_columns
    assert validation.target_column == "target"


def test_build_signal_ml_training_dataset_can_disable_time_features() -> None:
    dataset = build_signal_ml_training_dataset(
        build_raw_ohlcv_dataset(),
        config=SignalMLDatasetBuildConfig(
            label_config=SignalTargetLabelConfig(horizon_bars=3),
            feature_config=OHLCVFeatureBuilderConfig(include_time_features=False),
        ),
    )

    assert "hour" not in dataset.columns
    assert "session_london" not in dataset.columns


def test_build_signal_ml_training_dataset_from_csv_writes_dataset_and_metadata(tmp_path) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    output_path = tmp_path / "training" / "signal_ml_dataset.csv"

    build_raw_ohlcv_dataset().to_csv(input_path, index=False)

    output = build_signal_ml_training_dataset_from_csv(
        input_path,
        output_path,
        config=SignalMLDatasetBuildConfig(
            label_config=SignalTargetLabelConfig(
                horizon_bars=3,
                min_signal_return=0.0002,
            )
        ),
    )

    dataset = pd.read_csv(output.dataset_path)
    metadata = json.loads(output.metadata_path.read_text(encoding="utf-8"))
    quality = json.loads(output.quality_report_path.read_text(encoding="utf-8"))

    assert output.quality_report_path.exists()
    assert quality["valid"] is True
    assert quality["target_column"] == "target"
    assert metadata["quality_report_path"].endswith("signal_ml_dataset_quality.json")
    assert output.dataset_path == output_path
    assert output.dataset_path.exists()
    assert output.metadata_path.exists()
    assert output.rows == 37
    assert "target" in dataset.columns
    assert "return_1" in dataset.columns
    assert metadata["rows"] == 37
    assert metadata["validation"]["valid"] is True


def test_built_signal_ml_dataset_can_train_baseline_model(tmp_path) -> None:
    input_path = tmp_path / "raw_ohlcv.csv"
    dataset_path = tmp_path / "training" / "signal_ml_dataset.csv"
    artifacts_dir = tmp_path / "artifacts"

    build_raw_ohlcv_dataset(rows=60).to_csv(input_path, index=False)

    build_signal_ml_training_dataset_from_csv(
        input_path,
        dataset_path,
        config=SignalMLDatasetBuildConfig(
            label_config=SignalTargetLabelConfig(
                horizon_bars=5,
                min_signal_return=0.0002,
            )
        ),
    )

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=artifacts_dir,
            n_estimators=20,
            random_state=71,
        )
    )

    assert output.model_path.exists()
    assert output.metrics_path.exists()
    assert "future_return" not in output.training_result.feature_columns
    assert "trade_quality_score" not in output.training_result.feature_columns
    assert "return_1" in output.training_result.feature_columns


def test_build_signal_ml_training_dataset_rejects_invalid_raw_ohlcv() -> None:
    dataset = build_raw_ohlcv_dataset().drop(columns=["close"])

    with pytest.raises(ValueError, match="Missing required OHLCV columns"):
        build_signal_ml_training_dataset(dataset)