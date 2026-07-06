"""
Unit tests for TakeProfitEngine.
"""

import pytest

from aqos.strategy.take_profit import TakeProfitEngine


def test_buy_take_profit():
    engine = TakeProfitEngine()

    target = engine.calculate(
        entry_price=100.0,
        side="buy",
    )

    assert target == 104.0


def test_sell_take_profit():
    engine = TakeProfitEngine()

    target = engine.calculate(
        entry_price=100.0,
        side="sell",
    )

    assert target == 96.0


def test_custom_percentage():
    engine = TakeProfitEngine(percentage=0.10)

    target = engine.calculate(
        entry_price=100.0,
        side="buy",
    )

    assert target == 110.0


def test_case_insensitive():
    engine = TakeProfitEngine()

    target = engine.calculate(
        entry_price=100.0,
        side="BUY",
    )

    assert target == 104.0


def test_invalid_side():
    engine = TakeProfitEngine()

    with pytest.raises(ValueError):
        engine.calculate(
            entry_price=100.0,
            side="hold",
        )


def test_invalid_entry_price():
    engine = TakeProfitEngine()

    with pytest.raises(ValueError):
        engine.calculate(
            entry_price=-1,
            side="buy",
        )