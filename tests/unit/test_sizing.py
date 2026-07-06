"""
Unit tests for PositionSizer.
"""

import pytest

from aqos.risk import PositionSizer


def test_calculate_position_size():
    sizer = PositionSizer(risk_percent=0.01)

    position_size = sizer.calculate(
        account_balance=10_000.0,
        entry_price=2_000.0,
        stop_loss_price=1_990.0,
    )

    assert position_size == 10.0


def test_calculate_position_size_for_sell_trade():
    sizer = PositionSizer(risk_percent=0.02)

    position_size = sizer.calculate(
        account_balance=5_000.0,
        entry_price=2_000.0,
        stop_loss_price=2_010.0,
    )

    assert position_size == 10.0


def test_risk_amount():
    sizer = PositionSizer(risk_percent=0.01)

    risk_amount = sizer.risk_amount(
        account_balance=10_000.0,
    )

    assert risk_amount == 100.0


def test_max_position_size_limit():
    sizer = PositionSizer(
        risk_percent=0.01,
        max_position_size=5.0,
    )

    position_size = sizer.calculate(
        account_balance=10_000.0,
        entry_price=2_000.0,
        stop_loss_price=1_990.0,
    )

    assert position_size == 5.0


def test_invalid_risk_percent_zero():
    with pytest.raises(ValueError):
        PositionSizer(risk_percent=0)


def test_invalid_risk_percent_negative():
    with pytest.raises(ValueError):
        PositionSizer(risk_percent=-0.01)


def test_invalid_risk_percent_above_one():
    with pytest.raises(ValueError):
        PositionSizer(risk_percent=1.5)


def test_invalid_max_position_size():
    with pytest.raises(ValueError):
        PositionSizer(
            risk_percent=0.01,
            max_position_size=0,
        )


def test_invalid_account_balance():
    sizer = PositionSizer()

    with pytest.raises(ValueError):
        sizer.calculate(
            account_balance=0,
            entry_price=2_000.0,
            stop_loss_price=1_990.0,
        )


def test_invalid_entry_price():
    sizer = PositionSizer()

    with pytest.raises(ValueError):
        sizer.calculate(
            account_balance=10_000.0,
            entry_price=0,
            stop_loss_price=1_990.0,
        )


def test_invalid_stop_loss_price():
    sizer = PositionSizer()

    with pytest.raises(ValueError):
        sizer.calculate(
            account_balance=10_000.0,
            entry_price=2_000.0,
            stop_loss_price=0,
        )


def test_entry_price_and_stop_loss_price_cannot_be_equal():
    sizer = PositionSizer()

    with pytest.raises(ValueError):
        sizer.calculate(
            account_balance=10_000.0,
            entry_price=2_000.0,
            stop_loss_price=2_000.0,
        )


def test_invalid_account_balance_for_risk_amount():
    sizer = PositionSizer()

    with pytest.raises(ValueError):
        sizer.risk_amount(account_balance=0)