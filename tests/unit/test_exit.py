"""
Unit tests for ExitEngine.
"""

from aqos.strategy.exit import ExitEngine


def test_hold_should_exit():
    engine = ExitEngine()

    assert engine.should_exit("hold") is True


def test_buy_should_not_exit():
    engine = ExitEngine()

    assert engine.should_exit("buy") is False


def test_sell_should_not_exit():
    engine = ExitEngine()

    assert engine.should_exit("sell") is False


def test_case_insensitive():
    engine = ExitEngine()

    assert engine.should_exit("HOLD") is True


def test_invalid_signal():
    engine = ExitEngine()

    assert engine.should_exit("invalid") is False