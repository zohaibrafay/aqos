from __future__ import annotations

import pytest

from aqos.backtesting import (
    BACKTEST_BUILTIN_STRATEGIES_VERSION,
    BacktestBar,
    CloseMomentumRuleStrategy,
    CloseMomentumStrategyConfig,
    build_builtin_rule_strategy,
    list_builtin_rule_strategy_names,
    normalize_builtin_rule_strategy_name,
)


def build_bar(
    timestamp: str,
    close_price: float,
) -> BacktestBar:
    return BacktestBar(
        timestamp=timestamp,
        symbol="XAUUSD",
        timeframe="H1",
        open=close_price - 1.0,
        high=close_price + 5.0,
        low=close_price - 5.0,
        close=close_price,
        volume=1000.0,
    )


def test_close_momentum_strategy_generates_buy_signal() -> None:
    strategy = CloseMomentumRuleStrategy(
        config=CloseMomentumStrategyConfig(
            min_return_fraction=0.001,
            stop_loss_points=10.0,
            take_profit_points=20.0,
            confidence=0.7,
        )
    )

    signal = strategy.generate_signal(
        bar=build_bar("2026-01-01T01:00:00", 2310.0),
        history=(build_bar("2026-01-01T00:00:00", 2300.0),),
    )

    assert signal["action"] == "buy"
    assert signal["confidence"] == 0.7
    assert signal["stop_loss"] == 2300.0
    assert signal["take_profit"] == 2330.0


def test_close_momentum_strategy_generates_sell_signal() -> None:
    strategy = CloseMomentumRuleStrategy(
        config=CloseMomentumStrategyConfig(
            min_return_fraction=0.001,
            stop_loss_points=10.0,
            take_profit_points=20.0,
            confidence=0.7,
        )
    )

    signal = strategy.generate_signal(
        bar=build_bar("2026-01-01T01:00:00", 2290.0),
        history=(build_bar("2026-01-01T00:00:00", 2300.0),),
    )

    assert signal["action"] == "sell"
    assert signal["stop_loss"] == 2300.0
    assert signal["take_profit"] == 2270.0


def test_close_momentum_strategy_holds_when_no_history() -> None:
    strategy = CloseMomentumRuleStrategy()

    signal = strategy.generate_signal(
        bar=build_bar("2026-01-01T01:00:00", 2300.0),
        history=(),
    )

    assert signal["action"] == "hold"
    assert signal["metadata"]["reason"] == "Not enough history."


def test_builtin_rule_strategy_registry() -> None:
    assert list_builtin_rule_strategy_names() == ("close_momentum",)
    assert normalize_builtin_rule_strategy_name("momentum") == "close_momentum"

    strategy = build_builtin_rule_strategy(
        "close-momentum",
        lookback_bars=2,
        min_return_fraction=0.002,
        stop_loss_points=8.0,
        take_profit_points=16.0,
        confidence=0.6,
    )

    assert isinstance(strategy, CloseMomentumRuleStrategy)
    assert strategy.config.lookback_bars == 2
    assert strategy.config.stop_loss_points == 8.0
    assert strategy.config.take_profit_points == 16.0


def test_builtin_rule_strategy_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="Unsupported built-in rule strategy"):
        build_builtin_rule_strategy("unknown")


def test_close_momentum_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="lookback_bars"):
        CloseMomentumStrategyConfig(lookback_bars=0)

    with pytest.raises(ValueError, match="confidence"):
        CloseMomentumStrategyConfig(confidence=1.5)


def test_backtest_builtin_strategies_version_exported() -> None:
    assert BACKTEST_BUILTIN_STRATEGIES_VERSION == "1.0"