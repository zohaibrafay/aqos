"""
Unit tests for StopLossEngine.
"""

import pytest

from aqos.strategy.stop_loss import StopLossEngine


def test_buy_stop_loss():
    engine = StopLossEngine()

    stop = engine.calculate(
        entry_price=100.0,
        side="buy",
    )

    assert stop == pytest.approx(98.0)


def test_sell_stop_loss():
    engine = StopLossEngine()

    stop = engine.calculate(
        entry_price=100.0,
        side="sell",
    )

    assert stop == pytest.approx(102.0)


def test_custom_percentage():
    engine = StopLossEngine(percentage=0.05)

    stop = engine.calculate(
        entry_price=100.0,
        side="buy",
    )

    assert stop == pytest.approx(95.0)


def test_case_insensitive():
    engine = StopLossEngine()

    stop = engine.calculate(
        entry_price=100.0,
        side="BUY",
    )

    assert stop == pytest.approx(98.0)


def test_invalid_side():
    engine = StopLossEngine()

    with pytest.raises(ValueError):
        engine.calculate(
            entry_price=100.0,
            side="hold",
        )


def test_invalid_entry_price():
    engine = StopLossEngine()

    with pytest.raises(ValueError):
        engine.calculate(
            entry_price=0,
            side="buy",
        )