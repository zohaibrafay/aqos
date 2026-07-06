"""
Unit tests for SignalEngine.
"""

from aqos.strategy.signal import SignalEngine


def test_buy_signal():
    engine = SignalEngine()

    assert (
        engine.generate(
            regime="bull",
            trend="uptrend",
        )
        == "buy"
    )


def test_sell_signal():
    engine = SignalEngine()

    assert (
        engine.generate(
            regime="bear",
            trend="downtrend",
        )
        == "sell"
    )


def test_hold_signal_sideways():
    engine = SignalEngine()

    assert (
        engine.generate(
            regime="sideways",
            trend="sideways",
        )
        == "hold"
    )


def test_hold_signal_mixed():
    engine = SignalEngine()

    assert (
        engine.generate(
            regime="bull",
            trend="downtrend",
        )
        == "hold"
    )


def test_case_insensitive():
    engine = SignalEngine()

    assert (
        engine.generate(
            regime="BULL",
            trend="UPTREND",
        )
        == "buy"
    )