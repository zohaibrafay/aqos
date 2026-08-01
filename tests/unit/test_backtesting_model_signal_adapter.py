from __future__ import annotations

from typing import Any

import pandas as pd
import pytest

from aqos.backtesting.contracts import BacktestBar, BacktestSignalAction
from aqos.backtesting.model_signal_adapter import (
    BACKTEST_MODEL_SIGNAL_ADAPTER_VERSION,
    ModelBacktestSignalAdapter,
    ModelSignalAdapterConfig,
    bars_to_ohlcv_dataframe,
    build_model_feature_frame,
    build_model_feature_row,
    build_model_probability_payload,
    build_model_signal_metadata,
    extract_model_confidence,
    load_model_backtest_signal_adapter,
    resolve_model_exit_prices,
    resolve_model_signal_action,
    select_model_features,
)
from aqos.backtesting.signal_adapter import (
    BacktestSignalAdapterContext,
    BacktestSignalAdapterStatus,
    BacktestSignalAdapterType,
)
from aqos.model_training.ohlcv_feature_builder import build_ohlcv_ml_features


class BrokenSignalModel:
    model_name = "broken_signal_model"
    feature_columns = ("return_1",)

    def predict(self, features: pd.DataFrame) -> pd.Series:
        raise RuntimeError("Model inference failed.")

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        raise RuntimeError("Model inference failed.")


class StubSignalModel:
    """Fixed-output model used to exercise confidence thresholds precisely."""

    model_name = "stub_signal_model"
    feature_columns = ("return_1",)

    def __init__(
        self,
        label: str = "buy",
        probabilities: dict[str, float] | None = None,
    ) -> None:
        self.label = label
        self.probabilities = probabilities or {
            "probability_buy": 0.6,
            "probability_sell": 0.4,
        }

    def predict(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series(
            [self.label] * len(features),
            index=features.index,
            name="predicted_signal",
        )

    def predict_proba(self, features: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            [self.probabilities] * len(features),
            index=features.index,
        )


def build_context(
    bars: tuple[BacktestBar, ...],
    index: int,
) -> BacktestSignalAdapterContext:
    return BacktestSignalAdapterContext(
        bar=bars[index],
        history=bars[:index],
        index=index,
    )


def test_adapter_version_is_exposed() -> None:
    assert BACKTEST_MODEL_SIGNAL_ADAPTER_VERSION == "1.0"


def test_bars_to_ohlcv_dataframe_maps_all_fields(backtest_model_bars) -> None:
    frame = bars_to_ohlcv_dataframe(backtest_model_bars[:3])

    assert list(frame.columns) == [
        "timestamp",
        "symbol",
        "timeframe",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert len(frame) == 3
    assert frame.iloc[0]["close"] == backtest_model_bars[0].close


def test_bars_to_ohlcv_dataframe_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="bars cannot be empty"):
        bars_to_ohlcv_dataframe(())


def test_feature_row_is_causal(backtest_model_bars, backtest_model_ohlcv) -> None:
    """A feature row built from a prefix must match the full-history value."""

    full_features = build_ohlcv_ml_features(backtest_model_ohlcv)

    for index in (5, 17, 40):
        row = build_model_feature_row(build_context(backtest_model_bars, index))

        for column in ("return_1", "return_3", "sma_distance_5", "candle_body_ratio"):
            assert row.iloc[0][column] == pytest.approx(
                full_features.iloc[index][column]
            )


def test_feature_frame_has_one_row_per_bar(backtest_model_bars) -> None:
    frame = build_model_feature_frame(backtest_model_bars[:10])

    assert len(frame) == 10


def test_select_model_features_rejects_missing_columns(backtest_model_bars) -> None:
    frame = build_model_feature_frame(backtest_model_bars[:5])

    with pytest.raises(ValueError, match="missing from bar features"):
        select_model_features(frame, ("does_not_exist",))


def test_select_model_features_rejects_empty_columns(backtest_model_bars) -> None:
    frame = build_model_feature_frame(backtest_model_bars[:5])

    with pytest.raises(ValueError, match="feature_columns cannot be empty"):
        select_model_features(frame, ())


def test_select_model_features_returns_requested_order(backtest_model_bars) -> None:
    frame = build_model_feature_frame(backtest_model_bars[:5])

    selected = select_model_features(frame, ("return_3", "return_1"))

    assert list(selected.columns) == ["return_3", "return_1"]


def test_extract_model_confidence_reads_matching_column() -> None:
    probabilities = pd.DataFrame([{"probability_buy": 0.8, "probability_sell": 0.2}])

    assert extract_model_confidence(probabilities, "buy") == pytest.approx(0.8)
    assert extract_model_confidence(probabilities, "hold") is None
    assert extract_model_confidence(None, "buy") is None


def test_build_model_probability_payload() -> None:
    probabilities = pd.DataFrame([{"probability_buy": 0.75, "probability_sell": 0.25}])

    assert build_model_probability_payload(probabilities) == {
        "probability_buy": 0.75,
        "probability_sell": 0.25,
    }
    assert build_model_probability_payload(None) == {}


def test_resolve_model_signal_action_maps_labels() -> None:
    assert resolve_model_signal_action("buy", True) == BacktestSignalAction.BUY
    assert resolve_model_signal_action("sell", True) == BacktestSignalAction.SELL
    assert resolve_model_signal_action("hold", True) == BacktestSignalAction.HOLD


def test_resolve_model_signal_action_blocks_shorts_when_disabled() -> None:
    assert resolve_model_signal_action("sell", False) == BacktestSignalAction.HOLD


def test_resolve_model_signal_action_rejects_unknown_label() -> None:
    with pytest.raises(ValueError, match="Unsupported backtest signal action"):
        resolve_model_signal_action("moon", True)


def test_resolve_model_exit_prices_for_long() -> None:
    stop_loss, take_profit = resolve_model_exit_prices(
        action=BacktestSignalAction.BUY,
        close=100.0,
        stop_loss_points=5.0,
        take_profit_points=10.0,
    )

    assert stop_loss == 95.0
    assert take_profit == 110.0


def test_resolve_model_exit_prices_for_short() -> None:
    stop_loss, take_profit = resolve_model_exit_prices(
        action=BacktestSignalAction.SELL,
        close=100.0,
        stop_loss_points=5.0,
        take_profit_points=10.0,
    )

    assert stop_loss == 105.0
    assert take_profit == 90.0


def test_resolve_model_exit_prices_drops_non_positive_targets() -> None:
    stop_loss, take_profit = resolve_model_exit_prices(
        action=BacktestSignalAction.SELL,
        close=5.0,
        stop_loss_points=1.0,
        take_profit_points=10.0,
    )

    assert stop_loss == 6.0
    assert take_profit is None


def test_resolve_model_exit_prices_for_hold() -> None:
    assert resolve_model_exit_prices(
        action=BacktestSignalAction.HOLD,
        close=100.0,
        stop_loss_points=5.0,
        take_profit_points=10.0,
    ) == (None, None)


def test_adapter_config_validation() -> None:
    with pytest.raises(ValueError, match="adapter_name cannot be empty"):
        ModelSignalAdapterConfig(adapter_name="  ")

    with pytest.raises(ValueError, match="min_confidence must be between"):
        ModelSignalAdapterConfig(min_confidence=1.5)

    with pytest.raises(ValueError, match="warmup_bars cannot be negative"):
        ModelSignalAdapterConfig(warmup_bars=-1)

    with pytest.raises(ValueError, match="stop_loss_points must be positive"):
        ModelSignalAdapterConfig(stop_loss_points=0.0)

    with pytest.raises(ValueError, match="take_profit_points must be positive"):
        ModelSignalAdapterConfig(take_profit_points=-2.0)


def test_adapter_config_serialization() -> None:
    config = ModelSignalAdapterConfig(
        min_confidence=0.6,
        warmup_bars=3,
        stop_loss_points=4.0,
        take_profit_points=8.0,
        model_identity={"model_id": "abc"},
    )

    payload = config.to_dict()

    assert payload["min_confidence"] == 0.6
    assert payload["warmup_bars"] == 3
    assert payload["stop_loss_points"] == 4.0
    assert payload["model_identity"] == {"model_id": "abc"}


def test_build_model_signal_metadata_includes_identity(backtest_model_bars) -> None:
    config = ModelSignalAdapterConfig(model_identity={"model_id": "model_abc"})
    context = build_context(backtest_model_bars, 4)

    metadata = build_model_signal_metadata(
        config=config,
        context=context,
        predicted_label="buy",
        probabilities={"probability_buy": 0.9},
        reason="unit test",
    )

    assert metadata["adapter_type"] == "ml_model"
    assert metadata["predicted_label"] == "buy"
    assert metadata["bar_index"] == 4
    assert metadata["model_id"] == "model_abc"
    assert metadata["probabilities"] == {"probability_buy": 0.9}
    assert metadata["reason"] == "unit test"


def test_adapter_skips_until_warmup_is_reached(
    trained_backtest_model,
    backtest_model_bars,
) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=trained_backtest_model,
        config=ModelSignalAdapterConfig(warmup_bars=5),
    )

    result = adapter.generate_signal(build_context(backtest_model_bars, 2))

    assert result.status == BacktestSignalAdapterStatus.SKIPPED
    assert result.signal.action == BacktestSignalAction.HOLD
    assert result.reason == "Insufficient history for model warmup."
    assert result.metadata["warmup_bars"] == 5


def test_adapter_generates_traceable_model_signal(
    trained_backtest_model,
    backtest_model_bars,
) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=trained_backtest_model,
        config=ModelSignalAdapterConfig(
            warmup_bars=5,
            stop_loss_points=4.0,
            take_profit_points=6.0,
            model_identity={
                "model_id": "backtest_signal_model_abc",
                "model_version": "v1",
                "promotion_stage": "paper_trading",
            },
        ),
    )

    result = adapter.generate_signal(build_context(backtest_model_bars, 20))

    assert adapter.adapter_type == BacktestSignalAdapterType.ML_MODEL
    assert result.status == BacktestSignalAdapterStatus.GENERATED
    assert result.signal.action in {
        BacktestSignalAction.BUY,
        BacktestSignalAction.SELL,
    }
    assert result.signal.source == "model_backtest_signal_adapter"
    assert result.signal.confidence is not None
    assert 0.0 <= result.signal.confidence <= 1.0
    assert result.signal.stop_loss is not None
    assert result.signal.take_profit is not None
    assert result.signal.metadata["model_id"] == "backtest_signal_model_abc"
    assert result.signal.metadata["model_version"] == "v1"
    assert result.signal.metadata["promotion_stage"] == "paper_trading"
    assert result.signal.metadata["probabilities"]


def test_adapter_predicts_next_bar_direction(
    trained_backtest_model,
    backtest_model_bars,
) -> None:
    """The fixture series alternates, so the model must alternate its calls."""

    adapter = ModelBacktestSignalAdapter(
        model=trained_backtest_model,
        config=ModelSignalAdapterConfig(warmup_bars=5),
    )

    actions = [
        adapter.generate_signal(build_context(backtest_model_bars, index)).signal.action
        for index in range(20, 26)
    ]

    assert actions == [
        BacktestSignalAction.SELL,
        BacktestSignalAction.BUY,
        BacktestSignalAction.SELL,
        BacktestSignalAction.BUY,
        BacktestSignalAction.SELL,
        BacktestSignalAction.BUY,
    ]


def test_adapter_holds_when_confidence_is_below_threshold(
    backtest_model_bars,
) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=StubSignalModel(),  # type: ignore[arg-type]
        config=ModelSignalAdapterConfig(
            warmup_bars=5,
            min_confidence=0.7,
            stop_loss_points=4.0,
        ),
    )

    result = adapter.generate_signal(build_context(backtest_model_bars, 20))

    assert result.status == BacktestSignalAdapterStatus.SKIPPED
    assert result.signal.action == BacktestSignalAction.HOLD
    assert result.signal.stop_loss is None
    assert result.signal.confidence == pytest.approx(0.6)
    assert result.reason == "Model confidence below configured threshold."
    assert result.signal.metadata["predicted_label"] == "buy"


def test_adapter_accepts_confidence_equal_to_threshold(backtest_model_bars) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=StubSignalModel(),  # type: ignore[arg-type]
        config=ModelSignalAdapterConfig(warmup_bars=5, min_confidence=0.6),
    )

    result = adapter.generate_signal(build_context(backtest_model_bars, 20))

    assert result.status == BacktestSignalAdapterStatus.GENERATED
    assert result.signal.action == BacktestSignalAction.BUY


def test_adapter_blocks_shorts_when_configured(
    trained_backtest_model,
    backtest_model_bars,
) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=trained_backtest_model,
        config=ModelSignalAdapterConfig(warmup_bars=5, allow_short=False),
    )

    result = adapter.generate_signal(build_context(backtest_model_bars, 20))

    assert result.signal.metadata["predicted_label"] == "sell"
    assert result.signal.action == BacktestSignalAction.HOLD


def test_adapter_fails_closed_on_model_error(backtest_model_bars) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=BrokenSignalModel(),  # type: ignore[arg-type]
        config=ModelSignalAdapterConfig(warmup_bars=1),
    )

    result = adapter.generate_signal(build_context(backtest_model_bars, 5))

    assert result.status == BacktestSignalAdapterStatus.FAILED
    assert result.signal.action == BacktestSignalAction.HOLD
    assert result.reason == "Model inference failed."
    assert result.metadata["model_name"] == "broken_signal_model"


def test_adapter_fail_open_raises_model_error(backtest_model_bars) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=BrokenSignalModel(),  # type: ignore[arg-type]
        config=ModelSignalAdapterConfig(warmup_bars=1, fail_closed=False),
    )

    with pytest.raises(RuntimeError, match="Model inference failed"):
        adapter.generate_signal(build_context(backtest_model_bars, 5))


def test_adapter_without_probabilities_has_no_confidence(
    trained_backtest_model,
    backtest_model_bars,
) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=trained_backtest_model,
        config=ModelSignalAdapterConfig(warmup_bars=5, include_probabilities=False),
    )

    result = adapter.generate_signal(build_context(backtest_model_bars, 20))

    assert result.signal.confidence is None
    assert "probabilities" not in result.signal.metadata


def test_load_adapter_from_artifact(trained_backtest_model_path) -> None:
    adapter = load_model_backtest_signal_adapter(trained_backtest_model_path)

    assert adapter.adapter_name == "model_backtest_signal_adapter"
    assert adapter.model.is_trained is True


def test_load_adapter_rejects_missing_artifact(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_model_backtest_signal_adapter(tmp_path / "missing_model.joblib")


def test_adapter_result_serialization_carries_model_metadata(
    trained_backtest_model,
    backtest_model_bars,
) -> None:
    adapter = ModelBacktestSignalAdapter(
        model=trained_backtest_model,
        config=ModelSignalAdapterConfig(
            warmup_bars=5,
            model_identity={"model_id": "traced_model"},
        ),
    )

    payload: dict[str, Any] = adapter.generate_signal(
        build_context(backtest_model_bars, 20)
    ).to_dict()

    assert payload["adapter_type"] == "ml_model"
    assert payload["generated"] is True
    assert payload["signal"]["metadata"]["model_id"] == "traced_model"
