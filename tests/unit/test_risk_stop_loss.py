"""
Unit tests for StopLossManager.
"""

import pytest

from aqos.risk import StopLossManager, StopLossRecord


def test_calculate_buy_stop_loss():
    manager = StopLossManager(max_loss_percent=0.02)

    stop_loss = manager.calculate(
        entry_price=2000.0,
        side="buy",
    )

    assert stop_loss == 1960.0


def test_calculate_sell_stop_loss():
    manager = StopLossManager(max_loss_percent=0.02)

    stop_loss = manager.calculate(
        entry_price=2000.0,
        side="sell",
    )

    assert stop_loss == 2040.0


def test_calculate_from_amount_buy():
    manager = StopLossManager()

    stop_loss = manager.calculate_from_amount(
        entry_price=2000.0,
        risk_per_unit=10.0,
        side="buy",
    )

    assert stop_loss == 1990.0


def test_calculate_from_amount_sell():
    manager = StopLossManager()

    stop_loss = manager.calculate_from_amount(
        entry_price=2000.0,
        risk_per_unit=10.0,
        side="sell",
    )

    assert stop_loss == 2010.0


def test_buy_stop_loss_triggered():
    manager = StopLossManager()

    result = manager.is_triggered(
        current_price=1990.0,
        stop_loss_price=1990.0,
        side="buy",
    )

    assert result is True


def test_sell_stop_loss_triggered():
    manager = StopLossManager()

    result = manager.is_triggered(
        current_price=2010.0,
        stop_loss_price=2010.0,
        side="sell",
    )

    assert result is True


def test_create_stop_loss_record():
    manager = StopLossManager()

    record = manager.create_record(
        entry_price=2000.0,
        stop_loss_price=1990.0,
        side="buy",
    )

    assert isinstance(record, StopLossRecord)
    assert record.risk_per_unit == 10.0


def test_invalid_max_loss_percent():
    with pytest.raises(ValueError):
        StopLossManager(max_loss_percent=0)


def test_invalid_side():
    manager = StopLossManager()

    with pytest.raises(ValueError):
        manager.calculate(
            entry_price=2000.0,
            side="hold",
        )


def test_invalid_entry_price():
    manager = StopLossManager()

    with pytest.raises(ValueError):
        manager.calculate(
            entry_price=0,
            side="buy",
        )


def test_equal_entry_and_stop_loss():
    manager = StopLossManager()

    with pytest.raises(ValueError):
        manager.create_record(
            entry_price=2000.0,
            stop_loss_price=2000.0,
            side="buy",
        )