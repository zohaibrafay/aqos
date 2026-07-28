from __future__ import annotations

import pytest

from aqos.backtesting import (
    BACKTEST_SIMULATOR_VERSION,
    BacktestBar,
    BacktestExecutionConfig,
    BacktestExitReason,
    BacktestOrderStatus,
    BacktestSide,
    BacktestSignal,
    BacktestSignalAction,
    apply_backtest_signal,
    build_initial_backtest_state,
    calculate_backtest_position_quantity,
    calculate_market_execution_price,
    close_backtest_position,
    fill_market_order_from_signal,
    open_position_from_filled_order,
)


def build_bar(
    timestamp: str = "2026-01-01T00:00:00",
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


def build_buy_signal(
    timestamp: str = "2026-01-01T00:00:00",
) -> BacktestSignal:
    return BacktestSignal(
        timestamp=timestamp,
        symbol="XAUUSD",
        action=BacktestSignalAction.BUY,
        confidence=0.8,
        stop_loss=2290.0,
        take_profit=2320.0,
    )


def test_calculate_market_execution_price_applies_adverse_costs() -> None:
    config = BacktestExecutionConfig(
        spread_points=0.4,
        slippage_points=0.1,
    )

    assert calculate_market_execution_price(
        BacktestSide.LONG,
        base_price=2300.0,
        execution_config=config,
        is_entry=True,
    ) == 2300.3

    assert calculate_market_execution_price(
        BacktestSide.SHORT,
        base_price=2300.0,
        execution_config=config,
        is_entry=True,
    ) == 2299.7

    assert calculate_market_execution_price(
        BacktestSide.LONG,
        base_price=2300.0,
        execution_config=config,
        is_entry=False,
    ) == 2299.7

    assert calculate_market_execution_price(
        BacktestSide.SHORT,
        base_price=2300.0,
        execution_config=config,
        is_entry=False,
    ) == 2300.3


def test_calculate_backtest_position_quantity_uses_fixed_quantity() -> None:
    config = BacktestExecutionConfig(fixed_quantity=2.5)
    signal = build_buy_signal()

    quantity = calculate_backtest_position_quantity(
        balance=10_000.0,
        entry_price=2300.0,
        signal=signal,
        execution_config=config,
    )

    assert quantity == 2.5


def test_calculate_backtest_position_quantity_uses_risk_and_stop_loss() -> None:
    config = BacktestExecutionConfig(
        initial_balance=10_000.0,
        risk_fraction=0.01,
        fixed_quantity=None,
        point_value=1.0,
    )
    signal = build_buy_signal()

    quantity = calculate_backtest_position_quantity(
        balance=10_000.0,
        entry_price=2300.0,
        signal=signal,
        execution_config=config,
    )

    assert quantity == 10.0


def test_fill_market_order_from_signal_fills_buy_order() -> None:
    config = BacktestExecutionConfig(
        fixed_quantity=1.0,
        spread_points=0.2,
        slippage_points=0.1,
    )
    signal = build_buy_signal()
    bar = build_bar(open_price=2300.0)

    order = fill_market_order_from_signal(
        signal=signal,
        bar=bar,
        execution_config=config,
        balance=10_000.0,
        order_index=1,
    )

    assert order.status == BacktestOrderStatus.FILLED
    assert order.side == BacktestSide.LONG
    assert order.requested_price == 2300.0
    assert order.filled_price == 2300.2
    assert order.quantity == 1.0


def test_fill_market_order_rejects_short_when_disabled() -> None:
    config = BacktestExecutionConfig(allow_short=False)
    signal = BacktestSignal(
        timestamp="2026-01-01T00:00:00",
        symbol="XAUUSD",
        action=BacktestSignalAction.SELL,
    )

    order = fill_market_order_from_signal(
        signal=signal,
        bar=build_bar(),
        execution_config=config,
        balance=10_000.0,
        order_index=1,
    )

    assert order.status == BacktestOrderStatus.REJECTED
    assert order.reason == "Short entries are disabled."


def test_open_position_from_filled_order() -> None:
    config = BacktestExecutionConfig(fixed_quantity=1.0)
    signal = build_buy_signal()

    order = fill_market_order_from_signal(
        signal=signal,
        bar=build_bar(),
        execution_config=config,
        balance=10_000.0,
        order_index=1,
    )

    position = open_position_from_filled_order(order, signal)

    assert position.symbol == "XAUUSD"
    assert position.side == BacktestSide.LONG
    assert position.entry_price == order.filled_price
    assert position.stop_loss == 2290.0
    assert position.take_profit == 2320.0


def test_apply_backtest_signal_opens_position() -> None:
    config = BacktestExecutionConfig(fixed_quantity=1.0)
    state = build_initial_backtest_state(config)

    next_state = apply_backtest_signal(
        state=state,
        signal=build_buy_signal(),
        bar=build_bar(),
        execution_config=config,
        order_index=1,
    )

    assert next_state.balance == 10_000.0
    assert next_state.open_position_count == 1
    assert len(next_state.orders) == 1
    assert next_state.orders[0].status == BacktestOrderStatus.FILLED


def test_apply_backtest_signal_ignores_hold_signal() -> None:
    config = BacktestExecutionConfig(fixed_quantity=1.0)
    state = build_initial_backtest_state(config)

    next_state = apply_backtest_signal(
        state=state,
        signal=BacktestSignal(
            timestamp="2026-01-01T00:00:00",
            symbol="XAUUSD",
            action=BacktestSignalAction.HOLD,
        ),
        bar=build_bar(),
        execution_config=config,
        order_index=1,
    )

    assert next_state == state


def test_apply_backtest_signal_rejects_when_max_open_positions_reached() -> None:
    config = BacktestExecutionConfig(
        fixed_quantity=1.0,
        max_open_positions=1,
    )
    state = build_initial_backtest_state(config)

    state = apply_backtest_signal(
        state=state,
        signal=build_buy_signal(),
        bar=build_bar(),
        execution_config=config,
        order_index=1,
    )

    rejected_state = apply_backtest_signal(
        state=state,
        signal=build_buy_signal(timestamp="2026-01-01T01:00:00"),
        bar=build_bar(timestamp="2026-01-01T01:00:00"),
        execution_config=config,
        order_index=2,
    )

    assert rejected_state.open_position_count == 1
    assert len(rejected_state.orders) == 2
    assert rejected_state.orders[-1].status == BacktestOrderStatus.REJECTED
    assert rejected_state.orders[-1].reason == "Maximum open positions reached."


def test_close_backtest_position_creates_trade_and_updates_balance() -> None:
    config = BacktestExecutionConfig(
        fixed_quantity=2.0,
        commission_per_trade=1.0,
    )
    state = build_initial_backtest_state(config)

    state = apply_backtest_signal(
        state=state,
        signal=build_buy_signal(),
        bar=build_bar(open_price=2300.0),
        execution_config=config,
        order_index=1,
    )

    closed_state = close_backtest_position(
        state=state,
        position=state.open_positions[0],
        bar=build_bar(
            timestamp="2026-01-01T04:00:00",
            open_price=2310.0,
            close_price=2312.0,
        ),
        execution_config=config,
        exit_reason=BacktestExitReason.SIGNAL_EXIT,
    )

    assert closed_state.open_position_count == 0
    assert len(closed_state.trades) == 1
    assert closed_state.trades[0].exit_reason == BacktestExitReason.SIGNAL_EXIT
    assert closed_state.trades[0].net_pnl == 18.0
    assert closed_state.balance == 10_018.0


def test_apply_exit_signal_closes_matching_symbol_positions() -> None:
    config = BacktestExecutionConfig(fixed_quantity=1.0)
    state = build_initial_backtest_state(config)

    state = apply_backtest_signal(
        state=state,
        signal=build_buy_signal(),
        bar=build_bar(open_price=2300.0),
        execution_config=config,
        order_index=1,
    )

    exited_state = apply_backtest_signal(
        state=state,
        signal=BacktestSignal(
            timestamp="2026-01-01T03:00:00",
            symbol="XAUUSD",
            action=BacktestSignalAction.EXIT,
        ),
        bar=build_bar(
            timestamp="2026-01-01T03:00:00",
            open_price=2310.0,
        ),
        execution_config=config,
        order_index=2,
    )

    assert exited_state.open_position_count == 0
    assert len(exited_state.trades) == 1
    assert exited_state.trades[0].exit_reason == BacktestExitReason.SIGNAL_EXIT


def test_backtest_simulator_version_exported() -> None:
    assert BACKTEST_SIMULATOR_VERSION == "1.0"


def test_simulation_state_to_dict() -> None:
    config = BacktestExecutionConfig(fixed_quantity=1.0)
    state = build_initial_backtest_state(config)

    payload = state.to_dict()

    assert payload["balance"] == 10_000.0
    assert payload["open_position_count"] == 0
    assert payload["orders"] == []
    assert payload["trades"] == []
    assert payload["total_net_pnl"] == 0