"""
Unit tests for DrawdownManager.
"""

import pytest

from aqos.risk import DrawdownManager, DrawdownRecord


def test_calculate_drawdown():
    manager = DrawdownManager()

    drawdown = manager.calculate(
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert drawdown == 1_000.0


def test_calculate_drawdown_when_equity_is_above_peak():
    manager = DrawdownManager()

    drawdown = manager.calculate(
        peak_equity=10_000.0,
        current_equity=11_000.0,
    )

    assert drawdown == 0.0


def test_calculate_drawdown_percent():
    manager = DrawdownManager()

    percent = manager.calculate_percent(
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert percent == 0.1


def test_is_within_limit_true():
    manager = DrawdownManager(max_drawdown_percent=0.2)

    result = manager.is_within_limit(
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert result is True


def test_is_within_limit_false():
    manager = DrawdownManager(max_drawdown_percent=0.05)

    result = manager.is_within_limit(
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert result is False


def test_create_drawdown_record():
    manager = DrawdownManager()

    record = manager.create_record(
        peak_equity=10_000.0,
        current_equity=9_000.0,
    )

    assert isinstance(record, DrawdownRecord)
    assert record.peak_equity == 10_000.0
    assert record.current_equity == 9_000.0
    assert record.drawdown == 1_000.0
    assert record.drawdown_percent == 0.1


def test_max_drawdown():
    manager = DrawdownManager()

    result = manager.max_drawdown(
        equity_curve=[
            10_000.0,
            11_000.0,
            10_500.0,
            9_900.0,
            12_000.0,
        ]
    )

    assert result == pytest.approx(0.1)


def test_max_drawdown_without_loss():
    manager = DrawdownManager()

    result = manager.max_drawdown(
        equity_curve=[
            10_000.0,
            11_000.0,
            12_000.0,
        ]
    )

    assert result == 0.0


def test_invalid_max_drawdown_percent_zero():
    with pytest.raises(ValueError):
        DrawdownManager(max_drawdown_percent=0)


def test_invalid_max_drawdown_percent_negative():
    with pytest.raises(ValueError):
        DrawdownManager(max_drawdown_percent=-0.1)


def test_invalid_max_drawdown_percent_above_one():
    with pytest.raises(ValueError):
        DrawdownManager(max_drawdown_percent=1.5)


def test_invalid_peak_equity():
    manager = DrawdownManager()

    with pytest.raises(ValueError):
        manager.calculate(
            peak_equity=0,
            current_equity=9_000.0,
        )


def test_invalid_current_equity():
    manager = DrawdownManager()

    with pytest.raises(ValueError):
        manager.calculate(
            peak_equity=10_000.0,
            current_equity=-1.0,
        )


def test_empty_equity_curve():
    manager = DrawdownManager()

    with pytest.raises(ValueError):
        manager.max_drawdown([])


def test_negative_equity_curve_value():
    manager = DrawdownManager()

    with pytest.raises(ValueError):
        manager.max_drawdown(
            [
                10_000.0,
                -1.0,
            ]
        )


def test_invalid_initial_equity():
    manager = DrawdownManager()

    with pytest.raises(ValueError):
        manager.max_drawdown(
            [
                0.0,
                10_000.0,
            ]
        )