from __future__ import annotations

import pytest

from aqos.backtesting import (
    BACKTEST_SIGNAL_ADAPTER_VERSION,
    BacktestBar,
    BacktestSignal,
    BacktestSignalAction,
    BacktestSignalAdapter,
    BacktestSignalAdapterContext,
    BacktestSignalAdapterStatus,
    BacktestSignalAdapterType,
    NoOpBacktestSignalAdapter,
    build_adapter_result_from_signal,
    build_failed_adapter_result,
    build_hold_signal_for_bar,
    normalize_adapter_signal_action,
)


def build_bar(
    timestamp: str = "2026-01-01T01:00:00",
    close_price: float = 2305.0,
) -> BacktestBar:
    return BacktestBar(
        timestamp=timestamp,
        symbol="XAUUSD",
        timeframe="H1",
        open=2300.0,
        high=max(2310.0, close_price),
        low=min(2290.0, close_price),
        close=close_price,
        volume=1000.0,
    )


def test_signal_adapter_context_exposes_previous_bar() -> None:
    previous = build_bar(timestamp="2026-01-01T00:00:00", close_price=2300.0)
    current = build_bar(timestamp="2026-01-01T01:00:00", close_price=2305.0)

    context = BacktestSignalAdapterContext(
        bar=current,
        history=(previous,),
        index=1,
        metadata={"strategy": "test"},
    )

    payload = context.to_dict()

    assert context.previous_bar == previous
    assert context.history_size == 1
    assert payload["index"] == 1
    assert payload["previous_bar"]["timestamp"] == "2026-01-01T00:00:00"
    assert payload["metadata"]["strategy"] == "test"


def test_signal_adapter_context_rejects_negative_index() -> None:
    with pytest.raises(ValueError, match="index"):
        BacktestSignalAdapterContext(
            bar=build_bar(),
            index=-1,
        )


def test_normalize_adapter_signal_action_aliases() -> None:
    assert normalize_adapter_signal_action("buy") == BacktestSignalAction.BUY
    assert normalize_adapter_signal_action("long") == BacktestSignalAction.BUY
    assert normalize_adapter_signal_action("bullish") == BacktestSignalAction.BUY
    assert normalize_adapter_signal_action("sell") == BacktestSignalAction.SELL
    assert normalize_adapter_signal_action("short") == BacktestSignalAction.SELL
    assert normalize_adapter_signal_action("bearish") == BacktestSignalAction.SELL
    assert normalize_adapter_signal_action("hold") == BacktestSignalAction.HOLD
    assert normalize_adapter_signal_action("flat") == BacktestSignalAction.HOLD
    assert normalize_adapter_signal_action("neutral") == BacktestSignalAction.HOLD
    assert normalize_adapter_signal_action("exit") == BacktestSignalAction.EXIT
    assert normalize_adapter_signal_action("close") == BacktestSignalAction.EXIT
    assert normalize_adapter_signal_action(None) == BacktestSignalAction.HOLD
    assert normalize_adapter_signal_action("") == BacktestSignalAction.HOLD


def test_normalize_adapter_signal_action_rejects_unknown_value() -> None:
    with pytest.raises(ValueError, match="Unsupported backtest signal action"):
        normalize_adapter_signal_action("wait")


def test_build_hold_signal_for_bar() -> None:
    bar = build_bar()

    signal = build_hold_signal_for_bar(
        bar=bar,
        source="unit_test_adapter",
        reason="No setup.",
    )

    assert signal.timestamp == bar.timestamp
    assert signal.symbol == "XAUUSD"
    assert signal.action == BacktestSignalAction.HOLD
    assert signal.source == "unit_test_adapter"
    assert signal.metadata["reason"] == "No setup."


def test_build_adapter_result_from_buy_signal_is_generated() -> None:
    signal = BacktestSignal(
        timestamp="2026-01-01T01:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.BUY,
        confidence=0.8,
        source="unit_test_adapter",
    )

    result = build_adapter_result_from_signal(
        signal=signal,
        adapter_name="unit_test_adapter",
        adapter_type=BacktestSignalAdapterType.CUSTOM,
        reason="Generated buy signal.",
    )

    payload = result.to_dict()

    assert result.generated is True
    assert result.status == BacktestSignalAdapterStatus.GENERATED
    assert payload["signal"]["action"] == "buy"
    assert payload["adapter_type"] == "custom"


def test_build_adapter_result_from_hold_signal_is_skipped() -> None:
    signal = BacktestSignal(
        timestamp="2026-01-01T01:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.HOLD,
        source="unit_test_adapter",
    )

    result = build_adapter_result_from_signal(
        signal=signal,
        adapter_name="unit_test_adapter",
        adapter_type=BacktestSignalAdapterType.CUSTOM,
    )

    assert result.generated is False
    assert result.status == BacktestSignalAdapterStatus.SKIPPED


def test_build_failed_adapter_result_returns_hold_signal() -> None:
    context = BacktestSignalAdapterContext(bar=build_bar())

    result = build_failed_adapter_result(
        context=context,
        adapter_name="broken_adapter",
        adapter_type=BacktestSignalAdapterType.CUSTOM,
        reason="Adapter crashed.",
    )

    assert result.status == BacktestSignalAdapterStatus.FAILED
    assert result.generated is False
    assert result.reason == "Adapter crashed."
    assert result.signal.action == BacktestSignalAction.HOLD
    assert result.signal.metadata["reason"] == "Adapter crashed."


def test_failed_adapter_result_requires_reason() -> None:
    with pytest.raises(ValueError, match="reason"):
        build_failed_adapter_result(
            context=BacktestSignalAdapterContext(bar=build_bar()),
            adapter_name="broken_adapter",
            adapter_type=BacktestSignalAdapterType.CUSTOM,
            reason="",
        )


def test_noop_backtest_signal_adapter_returns_hold() -> None:
    adapter = NoOpBacktestSignalAdapter()
    context = BacktestSignalAdapterContext(bar=build_bar())

    result = adapter.generate_signal(context)

    assert isinstance(adapter, BacktestSignalAdapter)
    assert result.status == BacktestSignalAdapterStatus.SKIPPED
    assert result.adapter_type == BacktestSignalAdapterType.NOOP
    assert result.signal.action == BacktestSignalAction.HOLD
    assert result.signal.source == "noop_backtest_signal_adapter"


def test_backtest_signal_adapter_version_exported() -> None:
    assert BACKTEST_SIGNAL_ADAPTER_VERSION == "1.0"