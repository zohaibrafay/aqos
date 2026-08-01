from __future__ import annotations

import pytest

from aqos.backtesting import (
    BACKTEST_RULE_BASED_ADAPTER_VERSION,
    BacktestBar,
    BacktestSignal,
    BacktestSignalAction,
    BacktestSignalAdapterContext,
    BacktestSignalAdapterStatus,
    BacktestSignalAdapterType,
    RuleBasedBacktestSignalAdapter,
    RuleBasedSignalAdapterConfig,
    convert_rule_based_output_to_backtest_signal,
)


def build_bar(
    timestamp: str = "2026-01-01T01:00:00",
    open_price: float = 2300.0,
    close_price: float = 2305.0,
) -> BacktestBar:
    return BacktestBar(
        timestamp=timestamp,
        symbol="XAUUSD",
        timeframe="H1",
        open=open_price,
        high=max(open_price, close_price) + 5.0,
        low=min(open_price, close_price) - 5.0,
        close=close_price,
        volume=1000.0,
    )


class SimpleObjectStrategy:
    strategy_name = "simple_object_strategy"

    def generate_signal(self, bar, history, metadata=None):
        if not history:
            return None

        previous = history[-1]

        if bar.close > previous.close:
            return {
                "action": "buy",
                "confidence": 0.75,
                "stop_loss": bar.close - 10.0,
                "take_profit": bar.close + 20.0,
                "metadata": {"reason": "close above previous close"},
            }

        return "hold"


class BrokenStrategy:
    strategy_name = "broken_strategy"

    def generate_signal(self, bar, history, metadata=None):
        raise RuntimeError("strategy crashed")


def test_convert_rule_based_output_accepts_backtest_signal() -> None:
    context = BacktestSignalAdapterContext(bar=build_bar())
    signal = BacktestSignal(
        timestamp="2026-01-01T01:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.BUY,
        confidence=0.8,
        source="direct",
    )

    converted = convert_rule_based_output_to_backtest_signal(
        raw_signal=signal,
        context=context,
        source="adapter",
    )

    assert converted == signal


def test_convert_rule_based_output_none_returns_hold() -> None:
    context = BacktestSignalAdapterContext(bar=build_bar())

    signal = convert_rule_based_output_to_backtest_signal(
        raw_signal=None,
        context=context,
        source="adapter",
    )

    assert signal.action == BacktestSignalAction.HOLD
    assert signal.source == "adapter"
    assert signal.metadata["reason"] == "Rule-based strategy returned no signal."


def test_convert_rule_based_output_dict_to_signal() -> None:
    context = BacktestSignalAdapterContext(bar=build_bar())

    signal = convert_rule_based_output_to_backtest_signal(
        raw_signal={
            "signal": "buy",
            "confidence": 0.7,
            "stop_loss": 2295.0,
            "take_profit": 2320.0,
            "metadata": {"setup": "test"},
        },
        context=context,
        source="adapter",
        default_confidence=0.5,
    )

    assert signal.action == BacktestSignalAction.BUY
    assert signal.confidence == 0.7
    assert signal.stop_loss == 2295.0
    assert signal.take_profit == 2320.0
    assert signal.metadata["setup"] == "test"


def test_convert_rule_based_output_string_to_signal() -> None:
    context = BacktestSignalAdapterContext(bar=build_bar())

    signal = convert_rule_based_output_to_backtest_signal(
        raw_signal="sell",
        context=context,
        source="adapter",
        default_confidence=0.6,
    )

    assert signal.action == BacktestSignalAction.SELL
    assert signal.confidence == 0.6
    assert signal.source == "adapter"


def test_rule_based_adapter_generates_signal_from_object_strategy() -> None:
    previous = build_bar(
        timestamp="2026-01-01T00:00:00",
        close_price=2300.0,
    )
    current = build_bar(
        timestamp="2026-01-01T01:00:00",
        close_price=2308.0,
    )

    adapter = RuleBasedBacktestSignalAdapter(
        strategy=SimpleObjectStrategy(),
        config=RuleBasedSignalAdapterConfig(
            adapter_name="simple_rule_adapter",
        ),
    )

    result = adapter.generate_signal(
        BacktestSignalAdapterContext(
            bar=current,
            history=(previous,),
            index=1,
        )
    )

    assert result.status == BacktestSignalAdapterStatus.GENERATED
    assert result.adapter_type == BacktestSignalAdapterType.RULE_BASED
    assert result.adapter_name == "simple_rule_adapter"
    assert result.signal.action == BacktestSignalAction.BUY
    assert result.signal.confidence == 0.75
    assert result.signal.stop_loss == 2298.0
    assert result.signal.take_profit == 2328.0


def test_rule_based_adapter_supports_callable_strategy() -> None:
    def callable_strategy(bar, history, metadata=None):
        return {
            "action": "sell",
            "confidence": 0.66,
            "stop_loss": bar.close + 10.0,
            "take_profit": bar.close - 20.0,
        }

    adapter = RuleBasedBacktestSignalAdapter(
        strategy=callable_strategy,
        config=RuleBasedSignalAdapterConfig(
            adapter_name="callable_rule_adapter",
        ),
    )

    result = adapter.generate_signal(
        BacktestSignalAdapterContext(
            bar=build_bar(close_price=2305.0),
            history=(),
            index=0,
        )
    )

    assert result.status == BacktestSignalAdapterStatus.GENERATED
    assert result.signal.action == BacktestSignalAction.SELL
    assert result.signal.stop_loss == 2315.0
    assert result.signal.take_profit == 2285.0


def test_rule_based_adapter_returns_failed_result_when_strategy_errors() -> None:
    adapter = RuleBasedBacktestSignalAdapter(
        strategy=BrokenStrategy(),
        config=RuleBasedSignalAdapterConfig(
            adapter_name="broken_rule_adapter",
            fail_closed=True,
        ),
    )

    result = adapter.generate_signal(
        BacktestSignalAdapterContext(bar=build_bar())
    )

    assert result.status == BacktestSignalAdapterStatus.FAILED
    assert result.signal.action == BacktestSignalAction.HOLD
    assert result.reason == "strategy crashed"


def test_rule_based_adapter_can_raise_when_fail_closed_disabled() -> None:
    adapter = RuleBasedBacktestSignalAdapter(
        strategy=BrokenStrategy(),
        config=RuleBasedSignalAdapterConfig(
            adapter_name="broken_rule_adapter",
            fail_closed=False,
        ),
    )

    with pytest.raises(RuntimeError, match="strategy crashed"):
        adapter.generate_signal(BacktestSignalAdapterContext(bar=build_bar()))


def test_rule_based_adapter_config_rejects_invalid_default_confidence() -> None:
    with pytest.raises(ValueError, match="default_confidence"):
        RuleBasedSignalAdapterConfig(default_confidence=1.5)


def test_backtest_rule_based_adapter_version_exported() -> None:
    assert BACKTEST_RULE_BASED_ADAPTER_VERSION == "1.0"