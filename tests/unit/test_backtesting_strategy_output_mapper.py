from __future__ import annotations

from dataclasses import dataclass

import pytest

from aqos.backtesting import (
    BACKTEST_STRATEGY_OUTPUT_MAPPER_VERSION,
    BacktestBar,
    BacktestSignal,
    BacktestSignalAction,
    StrategyOutputMappingConfig,
    map_strategy_output_to_backtest_signal,
)


def build_bar() -> BacktestBar:
    return BacktestBar(
        timestamp="2026-01-01T01:00:00",
        symbol="XAUUSD",
        timeframe="H1",
        open=2300.0,
        high=2310.0,
        low=2290.0,
        close=2305.0,
        volume=1000.0,
    )


@dataclass(frozen=True)
class ObjectStrategySignal:
    direction: str
    score: float
    sl: float
    tp: float
    strategy_name: str
    metadata: dict


def test_mapper_accepts_backtest_signal() -> None:
    signal = BacktestSignal(
        timestamp="2026-01-01T01:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.BUY,
        confidence=0.8,
        source="already_backtest_signal",
    )

    result = map_strategy_output_to_backtest_signal(signal, build_bar())

    assert result.signal == signal
    assert result.source_type == "backtest_signal"


def test_mapper_converts_none_to_hold_signal() -> None:
    result = map_strategy_output_to_backtest_signal(None, build_bar())

    assert result.signal.action == BacktestSignalAction.HOLD
    assert result.signal.source == "strategy_output_mapper"
    assert result.source_type == "none"
    assert result.signal.metadata["reason"] == "Strategy output was None."


def test_mapper_converts_string_action() -> None:
    result = map_strategy_output_to_backtest_signal(
        "buy",
        build_bar(),
        StrategyOutputMappingConfig(default_confidence=0.55),
    )

    assert result.signal.action == BacktestSignalAction.BUY
    assert result.signal.confidence == 0.55
    assert result.source_type == "string"
    assert result.mapped_fields["action"] == "string_value"


def test_mapper_converts_mapping_with_common_fields() -> None:
    result = map_strategy_output_to_backtest_signal(
        {
            "direction": "sell",
            "score": 0.71,
            "sl": 2315.0,
            "tp": 2285.0,
            "strategy_name": "close_reversal_strategy",
            "metadata": {"setup": "bearish_close_reversal"},
        },
        build_bar(),
    )

    assert result.signal.action == BacktestSignalAction.SELL
    assert result.signal.confidence == 0.71
    assert result.signal.stop_loss == 2315.0
    assert result.signal.take_profit == 2285.0
    assert result.signal.source == "close_reversal_strategy"
    assert result.signal.metadata["setup"] == "bearish_close_reversal"
    assert result.mapped_fields["action"] == "direction"
    assert result.mapped_fields["confidence"] == "score"


def test_mapper_converts_object_with_common_attributes() -> None:
    output = ObjectStrategySignal(
        direction="buy",
        score=0.69,
        sl=2295.0,
        tp=2325.0,
        strategy_name="object_strategy",
        metadata={"reason": "object attrs"},
    )

    result = map_strategy_output_to_backtest_signal(output, build_bar())

    assert result.signal.action == BacktestSignalAction.BUY
    assert result.signal.confidence == 0.69
    assert result.signal.stop_loss == 2295.0
    assert result.signal.take_profit == 2325.0
    assert result.signal.source == "object_strategy"
    assert result.signal.metadata["reason"] == "object attrs"
    assert result.source_type == "object"


def test_mapper_uses_custom_config_fields() -> None:
    config = StrategyOutputMappingConfig(
        action_fields=("trade",),
        confidence_fields=("quality",),
        stop_loss_fields=("risk_price",),
        take_profit_fields=("reward_price",),
        default_source="custom_mapper",
    )

    result = map_strategy_output_to_backtest_signal(
        {
            "trade": "long",
            "quality": 0.77,
            "risk_price": 2298.0,
            "reward_price": 2322.0,
        },
        build_bar(),
        config,
    )

    assert result.signal.action == BacktestSignalAction.BUY
    assert result.signal.confidence == 0.77
    assert result.signal.stop_loss == 2298.0
    assert result.signal.take_profit == 2322.0
    assert result.signal.source == "custom_mapper"


def test_mapper_rejects_invalid_metadata() -> None:
    with pytest.raises(ValueError, match="metadata"):
        map_strategy_output_to_backtest_signal(
            {
                "action": "buy",
                "metadata": "not-a-dict",
            },
            build_bar(),
        )


def test_mapper_rejects_unknown_action() -> None:
    with pytest.raises(ValueError, match="Unsupported backtest signal action"):
        map_strategy_output_to_backtest_signal("wait", build_bar())


def test_strategy_output_mapping_result_to_dict() -> None:
    result = map_strategy_output_to_backtest_signal(
        {
            "action": "buy",
            "confidence": 0.8,
        },
        build_bar(),
    )

    payload = result.to_dict()

    assert payload["signal"]["action"] == "buy"
    assert payload["source_type"] == "mapping"
    assert payload["mapped_fields"]["action"] == "action"


def test_backtest_strategy_output_mapper_version_exported() -> None:
    assert BACKTEST_STRATEGY_OUTPUT_MAPPER_VERSION == "1.0"