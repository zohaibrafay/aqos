"""
Unit tests for TakeProfitManager.
"""

import pytest

from aqos.risk import TakeProfitManager, TakeProfitRecord


def test_calculate_buy_take_profit():
    manager = TakeProfitManager(reward_risk_ratio=2.0)

    take_profit = manager.calculate(
        entry_price=2000.0,
        stop_loss_price=1990.0,
        side="buy",
    )

    assert take_profit == 2020.0


def test_calculate_sell_take_profit():
    manager = TakeProfitManager(reward_risk_ratio=2.0)

    take_profit = manager.calculate(
        entry_price=2000.0,
        stop_loss_price=2010.0,
        side="sell",
    )

    assert take_profit == 1980.0


def test_buy_take_profit_hit():
    manager = TakeProfitManager()

    result = manager.is_hit(
        current_price=2020.0,
        take_profit_price=2020.0,
        side="buy",
    )

    assert result is True


def test_sell_take_profit_hit():
    manager = TakeProfitManager()

    result = manager.is_hit(
        current_price=1980.0,
        take_profit_price=1980.0,
        side="sell",
    )

    assert result is True


def test_create_take_profit_record():
    manager = TakeProfitManager(reward_risk_ratio=2.0)

    record = manager.create_record(
        entry_price=2000.0,
        stop_loss_price=1990.0,
        side="buy",
    )

    assert isinstance(record, TakeProfitRecord)
    assert record.take_profit_price == 2020.0
    assert record.reward_per_unit == 20.0
    assert record.reward_risk_ratio == 2.0


def test_invalid_reward_risk_ratio():
    with pytest.raises(ValueError):
        TakeProfitManager(reward_risk_ratio=0)


def test_invalid_side():
    manager = TakeProfitManager()

    with pytest.raises(ValueError):
        manager.calculate(
            entry_price=2000.0,
            stop_loss_price=1990.0,
            side="hold",
        )


def test_invalid_entry_price():
    manager = TakeProfitManager()

    with pytest.raises(ValueError):
        manager.calculate(
            entry_price=0,
            stop_loss_price=1990.0,
            side="buy",
        )


def test_equal_entry_and_stop_loss():
    manager = TakeProfitManager()

    with pytest.raises(ValueError):
        manager.calculate(
            entry_price=2000.0,
            stop_loss_price=2000.0,
            side="buy",
        )