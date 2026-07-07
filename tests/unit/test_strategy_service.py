"""
Unit tests for StrategyService.
"""

import pytest

from aqos.services import StrategyDecision, StrategyService


def test_generate_buy_signal():
    service = StrategyService()

    signal = service.generate_signal(
        regime="bullish",
        trend="uptrend",
    )

    assert signal == "buy"


def test_generate_sell_signal():
    service = StrategyService()

    signal = service.generate_signal(
        regime="bearish",
        trend="downtrend",
    )

    assert signal == "sell"


def test_generate_hold_signal():
    service = StrategyService()

    signal = service.generate_signal(
        regime="sideways",
        trend="sideways",
    )

    assert signal == "hold"


def test_should_enter_buy():
    service = StrategyService()

    assert service.should_enter("buy") is True


def test_should_enter_sell():
    service = StrategyService()

    assert service.should_enter("sell") is True


def test_should_not_enter_hold():
    service = StrategyService()

    assert service.should_enter("hold") is False


def test_should_exit_hold():
    service = StrategyService()

    assert service.should_exit("hold") is True


def test_should_not_exit_buy():
    service = StrategyService()

    assert service.should_exit("buy") is False


def test_calculate_buy_stop_loss():
    service = StrategyService()

    stop_loss = service.calculate_stop_loss(
        entry_price=2000.0,
        side="buy",
    )

    assert stop_loss == 1960.0


def test_calculate_sell_stop_loss():
    service = StrategyService()

    stop_loss = service.calculate_stop_loss(
        entry_price=2000.0,
        side="sell",
    )

    assert stop_loss == 2040.0


def test_calculate_buy_take_profit():
    service = StrategyService()

    take_profit = service.calculate_take_profit(
        entry_price=2000.0,
        side="buy",
    )

    assert take_profit == 2080.0


def test_calculate_sell_take_profit():
    service = StrategyService()

    take_profit = service.calculate_take_profit(
        entry_price=2000.0,
        side="sell",
    )

    assert take_profit == 1920.0


def test_decide_buy_with_entry_price():
    service = StrategyService()

    decision = service.decide(
        regime="bullish",
        trend="uptrend",
        entry_price=2000.0,
        metadata={"symbol": "XAUUSD"},
    )

    assert isinstance(decision, StrategyDecision)
    assert decision.signal == "buy"
    assert decision.should_enter is True
    assert decision.should_exit is False
    assert decision.stop_loss_price == 1960.0
    assert decision.take_profit_price == 2080.0
    assert decision.metadata["symbol"] == "XAUUSD"


def test_decide_hold_without_trade_plan():
    service = StrategyService()

    decision = service.decide(
        regime="sideways",
        trend="sideways",
        entry_price=2000.0,
    )

    assert decision.signal == "hold"
    assert decision.should_enter is False
    assert decision.should_exit is True
    assert decision.stop_loss_price is None
    assert decision.take_profit_price is None


def test_decide_without_entry_price():
    service = StrategyService()

    decision = service.decide(
        regime="bullish",
        trend="uptrend",
    )

    assert decision.signal == "buy"
    assert decision.should_enter is True
    assert decision.stop_loss_price is None
    assert decision.take_profit_price is None


def test_empty_regime():
    service = StrategyService()

    with pytest.raises(ValueError):
        service.generate_signal(
            regime="",
            trend="uptrend",
        )


def test_empty_trend():
    service = StrategyService()

    with pytest.raises(ValueError):
        service.generate_signal(
            regime="bullish",
            trend="",
        )


def test_invalid_signal():
    service = StrategyService()

    with pytest.raises(ValueError):
        service.should_enter("invalid")


def test_invalid_side():
    service = StrategyService()

    with pytest.raises(ValueError):
        service.calculate_stop_loss(
            entry_price=2000.0,
            side="hold",
        )


def test_invalid_price():
    service = StrategyService()

    with pytest.raises(ValueError):
        service.calculate_take_profit(
            entry_price=0,
            side="buy",
        )