from __future__ import annotations

from aqos.backtesting import (
    BacktestBar,
    BacktestExecutionConfig,
    BacktestExitReason,
    BacktestIntrabarExitPolicy,
    BacktestSide,
    BacktestSignal,
    BacktestSignalAction,
    apply_backtest_signal,
    apply_position_lifecycle_on_bar,
    build_initial_backtest_state,
    is_position_stop_loss_hit,
    is_position_take_profit_hit,
    resolve_position_exit_decision,
)


def build_bar(
    timestamp: str = "2026-01-01T01:00:00",
    open_price: float = 2300.0,
    high_price: float = 2310.0,
    low_price: float = 2290.0,
    close_price: float = 2305.0,
) -> BacktestBar:
    return BacktestBar(
        timestamp=timestamp,
        symbol="XAUUSD",
        timeframe="H1",
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=1000.0,
    )


def build_entry_signal(
    action: BacktestSignalAction,
    stop_loss: float,
    take_profit: float,
    timestamp: str = "2026-01-01T00:00:00",
) -> BacktestSignal:
    return BacktestSignal(
        timestamp=timestamp,
        symbol="XAUUSD",
        action=action,
        confidence=0.8,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )


def open_test_position(
    action: BacktestSignalAction,
    stop_loss: float,
    take_profit: float,
):
    config = BacktestExecutionConfig(fixed_quantity=1.0)
    state = build_initial_backtest_state(config)

    state = apply_backtest_signal(
        state=state,
        signal=build_entry_signal(
            action=action,
            stop_loss=stop_loss,
            take_profit=take_profit,
        ),
        bar=build_bar(
            timestamp="2026-01-01T00:00:00",
            open_price=2300.0,
            high_price=2305.0,
            low_price=2295.0,
            close_price=2302.0,
        ),
        execution_config=config,
        order_index=1,
    )

    return config, state.open_positions[0], state


def test_long_position_stop_loss_hit() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    bar = build_bar(low_price=2288.0, high_price=2305.0)

    assert is_position_stop_loss_hit(position, bar) is True
    assert is_position_take_profit_hit(position, bar) is False

    decision = resolve_position_exit_decision(position, bar)

    assert decision.should_exit is True
    assert decision.exit_reason == BacktestExitReason.STOP_LOSS
    assert decision.exit_price == 2290.0


def test_long_position_take_profit_hit() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    bar = build_bar(low_price=2299.0, high_price=2321.0)

    decision = resolve_position_exit_decision(position, bar)

    assert decision.should_exit is True
    assert decision.exit_reason == BacktestExitReason.TAKE_PROFIT
    assert decision.exit_price == 2320.0


def test_short_position_stop_loss_hit() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.SELL,
        stop_loss=2310.0,
        take_profit=2280.0,
    )

    bar = build_bar(low_price=2290.0, high_price=2315.0)

    assert position.side == BacktestSide.SHORT

    decision = resolve_position_exit_decision(position, bar)

    assert decision.should_exit is True
    assert decision.exit_reason == BacktestExitReason.STOP_LOSS
    assert decision.exit_price == 2310.0


def test_short_position_take_profit_hit() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.SELL,
        stop_loss=2310.0,
        take_profit=2280.0,
    )

    bar = build_bar(low_price=2278.0, high_price=2306.0)

    decision = resolve_position_exit_decision(position, bar)

    assert decision.should_exit is True
    assert decision.exit_reason == BacktestExitReason.TAKE_PROFIT
    assert decision.exit_price == 2280.0


def test_no_lifecycle_exit_when_no_stop_or_take_profit_hit() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    bar = build_bar(low_price=2295.0, high_price=2310.0)

    decision = resolve_position_exit_decision(position, bar)

    assert decision.should_exit is False
    assert decision.exit_price is None
    assert decision.exit_reason is None


def test_both_stop_loss_and_take_profit_hit_uses_stop_loss_first_by_default() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    bar = build_bar(low_price=2288.0, high_price=2322.0)

    decision = resolve_position_exit_decision(position, bar)

    assert decision.should_exit is True
    assert decision.stop_loss_hit is True
    assert decision.take_profit_hit is True
    assert decision.exit_reason == BacktestExitReason.STOP_LOSS
    assert decision.exit_price == 2290.0


def test_both_stop_loss_and_take_profit_hit_can_use_take_profit_first() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    bar = build_bar(low_price=2288.0, high_price=2322.0)

    decision = resolve_position_exit_decision(
        position,
        bar,
        intrabar_exit_policy=BacktestIntrabarExitPolicy.TAKE_PROFIT_FIRST,
    )

    assert decision.exit_reason == BacktestExitReason.TAKE_PROFIT
    assert decision.exit_price == 2320.0


def test_apply_position_lifecycle_closes_long_stop_loss() -> None:
    config, _, state = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    closed_state = apply_position_lifecycle_on_bar(
        state=state,
        bar=build_bar(low_price=2288.0, high_price=2305.0),
        execution_config=config,
    )

    assert closed_state.open_position_count == 0
    assert len(closed_state.trades) == 1
    assert closed_state.trades[0].exit_reason == BacktestExitReason.STOP_LOSS
    assert closed_state.trades[0].net_pnl == -10.0
    assert closed_state.balance == 9990.0


def test_apply_position_lifecycle_closes_long_take_profit() -> None:
    config, _, state = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    closed_state = apply_position_lifecycle_on_bar(
        state=state,
        bar=build_bar(low_price=2299.0, high_price=2325.0),
        execution_config=config,
    )

    assert closed_state.open_position_count == 0
    assert len(closed_state.trades) == 1
    assert closed_state.trades[0].exit_reason == BacktestExitReason.TAKE_PROFIT
    assert closed_state.trades[0].net_pnl == 20.0
    assert closed_state.balance == 10020.0


def test_apply_position_lifecycle_keeps_position_open_when_no_exit_hit() -> None:
    config, _, state = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    next_state = apply_position_lifecycle_on_bar(
        state=state,
        bar=build_bar(low_price=2295.0, high_price=2310.0),
        execution_config=config,
    )

    assert next_state.open_position_count == 1
    assert len(next_state.trades) == 0


def test_exit_decision_to_dict() -> None:
    _, position, _ = open_test_position(
        BacktestSignalAction.BUY,
        stop_loss=2290.0,
        take_profit=2320.0,
    )

    decision = resolve_position_exit_decision(
        position,
        build_bar(low_price=2288.0, high_price=2305.0),
    )

    payload = decision.to_dict()

    assert payload["should_exit"] is True
    assert payload["exit_reason"] == "stop_loss"
    assert payload["exit_price"] == 2290.0