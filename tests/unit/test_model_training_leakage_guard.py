from __future__ import annotations

import pandas as pd
import pytest

from aqos.model_training import (
    SignalTargetLabelConfig,
    SignalTrainingRunConfig,
    build_ohlcv_ml_features,
    build_signal_target_labels,
    check_feature_columns_for_leakage,
    drop_leakage_columns,
    find_leakage_columns,
    raise_if_feature_columns_have_leakage,
    resolve_training_feature_columns,
    train_baseline_signal_model_from_csv,
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
            }
        )

    return pd.DataFrame(records)


def build_labeled_feature_dataset() -> pd.DataFrame:
    labeled = build_signal_target_labels(
        build_ohlcv_dataset(),
        config=SignalTargetLabelConfig(horizon_bars=3),
    )

    return build_ohlcv_ml_features(labeled)


def test_find_leakage_columns_detects_future_and_outcome_columns() -> None:
    leaked = find_leakage_columns(
        [
            "open",
            "close",
            "future_return",
            "future_custom_alpha",
            "trade_quality_score",
        ]
    )

    assert leaked == (
        "future_return",
        "future_custom_alpha",
        "trade_quality_score",
    )


def test_check_feature_columns_for_leakage_returns_valid_result_for_safe_columns() -> None:
    result = check_feature_columns_for_leakage(
        ["open", "high", "low", "close", "volume", "return_1"]
    )

    assert result.valid is True
    assert result.leaked_columns == ()


def test_raise_if_feature_columns_have_leakage_raises_for_leaked_columns() -> None:
    with pytest.raises(ValueError, match="future/outcome leakage"):
        raise_if_feature_columns_have_leakage(["open", "future_return"])


def test_drop_leakage_columns_removes_outcome_columns_from_dataframe() -> None:
    dataframe = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "close": [1.1, 2.1],
            "future_return": [0.01, -0.01],
            "trade_quality_score": [0.4, 0.2],
        }
    )

    cleaned = drop_leakage_columns(dataframe)

    assert list(cleaned.columns) == ["open", "close"]


def test_signal_training_schema_keeps_label_columns_but_not_as_features() -> None:
    dataset = build_labeled_feature_dataset()

    result = validate_signal_training_dataset(dataset)

    assert result.valid is True
    assert "future_return" in dataset.columns
    assert "trade_quality_score" in dataset.columns
    assert "future_return" not in result.feature_columns
    assert "trade_quality_score" not in result.feature_columns


def test_resolve_training_feature_columns_excludes_leakage_columns() -> None:
    dataset = build_labeled_feature_dataset()

    feature_columns = resolve_training_feature_columns(
        dataset,
        SignalTrainingRunConfig(dataset_path="unused.csv"),
    )

    assert feature_columns is not None
    assert "future_return" not in feature_columns
    assert "trade_quality_score" not in feature_columns
    assert "return_1" in feature_columns


def test_training_runner_rejects_manual_leakage_feature_selection(tmp_path) -> None:
    dataset = build_labeled_feature_dataset()
    dataset_path = tmp_path / "leaky_training.csv"
    dataset.to_csv(dataset_path, index=False)

    with pytest.raises(ValueError, match="future/outcome leakage"):
        train_baseline_signal_model_from_csv(
            SignalTrainingRunConfig(
                dataset_path=dataset_path,
                output_dir=tmp_path / "artifacts",
                feature_columns=("open", "close", "future_return"),
                n_estimators=20,
            )
        )


def test_training_runner_trains_on_labeled_feature_dataset_without_leakage(tmp_path) -> None:
    dataset = build_labeled_feature_dataset()
    dataset_path = tmp_path / "safe_training.csv"
    dataset.to_csv(dataset_path, index=False)

    output = train_baseline_signal_model_from_csv(
        SignalTrainingRunConfig(
            dataset_path=dataset_path,
            output_dir=tmp_path / "artifacts",
            n_estimators=20,
            random_state=51,
        )
    )

    assert output.model_path.exists()
    assert "future_return" not in output.training_result.feature_columns
    assert "trade_quality_score" not in output.training_result.feature_columns
    assert "return_1" in output.training_result.feature_columns