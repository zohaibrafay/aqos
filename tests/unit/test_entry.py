"""
Unit tests for EntryEngine.
"""

from aqos.strategy.entry import EntryEngine


def test_buy_entry():
    engine = EntryEngine()

    assert engine.should_enter("buy") is True


def test_sell_entry():
    engine = EntryEngine()

    assert engine.should_enter("sell") is True


def test_hold_no_entry():
    engine = EntryEngine()

    assert engine.should_enter("hold") is False


def test_case_insensitive():
    engine = EntryEngine()

    assert engine.should_enter("BUY") is True


def test_invalid_signal():
    engine = EntryEngine()

    assert engine.should_enter("invalid") is False