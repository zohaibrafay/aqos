"""
Unit tests for StrategyInterface.
"""

from typing import Any

import pytest

from aqos.interfaces import (
    StrategyInterface,
    StrategyInterfaceDecision,
)


class DummyStrategy(StrategyInterface):
    """
    Test implementation of StrategyInterface.
    """

    @property
    def name(self) -> str:
        return "dummy-strategy"

    def generate_signal(
        self,
        market_state: dict[str, Any],
    ) -> str:
        self.validate_market_state(market_state)

        trend = self.get_required_state_value(
            market_state=market_state,
            key="trend",
        )

        if trend == "uptrend":
            return "buy"

        if trend == "downtrend":
            return "sell"

        return "hold"

    def should_enter(
        self,
        signal: str,
        market_state: dict[str, Any] | None = None,
    ) -> bool:
        self.validate_signal(signal)

        return signal in {"buy", "sell"}

    def should_exit(
        self,
        signal: str,
        market_state: dict[str, Any] | None = None,
    ) -> bool:
        self.validate_signal(signal)

        return signal == "hold"


def test_strategy_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        StrategyInterface()


def test_dummy_strategy_is_interface_instance():
    strategy = DummyStrategy()

    assert isinstance(strategy, StrategyInterface)


def test_strategy_name():
    strategy = DummyStrategy()

    assert strategy.name == "dummy-strategy"


def test_generate_buy_signal():
    strategy = DummyStrategy()

    signal = strategy.generate_signal(
        market_state={
            "trend": "uptrend",
        }
    )

    assert signal == "buy"


def test_generate_sell_signal():
    strategy = DummyStrategy()

    signal = strategy.generate_signal(
        market_state={
            "trend": "downtrend",
        }
    )

    assert signal == "sell"


def test_generate_hold_signal():
    strategy = DummyStrategy()

    signal = strategy.generate_signal(
        market_state={
            "trend": "sideways",
        }
    )

    assert signal == "hold"


def test_should_enter_buy():
    strategy = DummyStrategy()

    assert strategy.should_enter("buy") is True


def test_should_enter_sell():
    strategy = DummyStrategy()

    assert strategy.should_enter("sell") is True


def test_should_not_enter_hold():
    strategy = DummyStrategy()

    assert strategy.should_enter("hold") is False


def test_should_exit_hold():
    strategy = DummyStrategy()

    assert strategy.should_exit("hold") is True


def test_should_not_exit_buy():
    strategy = DummyStrategy()

    assert strategy.should_exit("buy") is False


def test_decide_buy():
    strategy = DummyStrategy()

    decision = strategy.decide(
        market_state={
            "trend": "uptrend",
        },
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert isinstance(decision, StrategyInterfaceDecision)
    assert decision.signal == "buy"
    assert decision.should_enter is True
    assert decision.should_exit is False
    assert decision.metadata["symbol"] == "XAUUSD"


def test_decide_hold():
    strategy = DummyStrategy()

    decision = strategy.decide(
        market_state={
            "trend": "sideways",
        }
    )

    assert decision.signal == "hold"
    assert decision.should_enter is False
    assert decision.should_exit is True


def test_validate_market_state():
    strategy = DummyStrategy()

    strategy.validate_market_state(
        {
            "trend": "uptrend",
        }
    )


def test_validate_market_state_rejects_non_dict():
    strategy = DummyStrategy()

    with pytest.raises(TypeError):
        strategy.validate_market_state(["not", "a", "dict"])


def test_validate_market_state_rejects_empty_dict():
    strategy = DummyStrategy()

    with pytest.raises(ValueError):
        strategy.validate_market_state({})


def test_validate_signal():
    strategy = DummyStrategy()

    strategy.validate_signal("buy")
    strategy.validate_signal("sell")
    strategy.validate_signal("hold")


def test_validate_signal_rejects_invalid_signal():
    strategy = DummyStrategy()

    with pytest.raises(ValueError):
        strategy.validate_signal("invalid")


def test_get_required_state_value():
    strategy = DummyStrategy()

    value = strategy.get_required_state_value(
        market_state={
            "trend": "uptrend",
        },
        key="trend",
    )

    assert value == "uptrend"


def test_get_required_state_value_rejects_empty_key():
    strategy = DummyStrategy()

    with pytest.raises(ValueError):
        strategy.get_required_state_value(
            market_state={
                "trend": "uptrend",
            },
            key="",
        )


def test_get_required_state_value_rejects_missing_key():
    strategy = DummyStrategy()

    with pytest.raises(ValueError):
        strategy.get_required_state_value(
            market_state={
                "trend": "uptrend",
            },
            key="regime",
        )


def test_generate_signal_rejects_missing_trend():
    strategy = DummyStrategy()

    with pytest.raises(ValueError):
        strategy.generate_signal(
            market_state={
                "regime": "bullish",
            }
        )


def test_should_enter_rejects_invalid_signal():
    strategy = DummyStrategy()

    with pytest.raises(ValueError):
        strategy.should_enter("invalid")


def test_should_exit_rejects_invalid_signal():
    strategy = DummyStrategy()

    with pytest.raises(ValueError):
        strategy.should_exit("invalid")