"""
Unit tests for ExposureManager.
"""

import pytest

from aqos.risk import ExposureManager, ExposureRecord


def test_calculate_exposure():
    manager = ExposureManager()

    exposure = manager.calculate(
        position_size=2.0,
        price=2000.0,
    )

    assert exposure == 4000.0


def test_exposure_percent():
    manager = ExposureManager()

    percent = manager.exposure_percent(
        exposure=4000.0,
        account_balance=10_000.0,
    )

    assert percent == 0.4


def test_is_within_limit_true():
    manager = ExposureManager(max_exposure_percent=0.5)

    result = manager.is_within_limit(
        exposure=4000.0,
        account_balance=10_000.0,
    )

    assert result is True


def test_is_within_limit_false():
    manager = ExposureManager(max_exposure_percent=0.3)

    result = manager.is_within_limit(
        exposure=4000.0,
        account_balance=10_000.0,
    )

    assert result is False


def test_create_exposure_record():
    manager = ExposureManager()

    record = manager.create_record(
        symbol="XAUUSD",
        position_size=2.0,
        price=2000.0,
    )

    assert isinstance(record, ExposureRecord)
    assert record.symbol == "XAUUSD"
    assert record.position_size == 2.0
    assert record.price == 2000.0
    assert record.exposure == 4000.0


def test_total_exposure():
    manager = ExposureManager()

    records = [
        manager.create_record("XAUUSD", 2.0, 2000.0),
        manager.create_record("EURUSD", 10_000.0, 1.1),
    ]

    total = manager.total_exposure(records)

    assert total == 15_000.0


def test_total_exposure_empty_records():
    manager = ExposureManager()

    total = manager.total_exposure([])

    assert total == 0.0


def test_invalid_max_exposure_percent_zero():
    with pytest.raises(ValueError):
        ExposureManager(max_exposure_percent=0)


def test_invalid_max_exposure_percent_negative():
    with pytest.raises(ValueError):
        ExposureManager(max_exposure_percent=-0.1)


def test_invalid_max_exposure_percent_above_one():
    with pytest.raises(ValueError):
        ExposureManager(max_exposure_percent=1.5)


def test_invalid_position_size():
    manager = ExposureManager()

    with pytest.raises(ValueError):
        manager.calculate(
            position_size=0,
            price=2000.0,
        )


def test_invalid_price():
    manager = ExposureManager()

    with pytest.raises(ValueError):
        manager.calculate(
            position_size=2.0,
            price=0,
        )


def test_invalid_exposure_percent_negative_exposure():
    manager = ExposureManager()

    with pytest.raises(ValueError):
        manager.exposure_percent(
            exposure=-1.0,
            account_balance=10_000.0,
        )


def test_invalid_account_balance():
    manager = ExposureManager()

    with pytest.raises(ValueError):
        manager.exposure_percent(
            exposure=4000.0,
            account_balance=0,
        )


def test_empty_symbol():
    manager = ExposureManager()

    with pytest.raises(ValueError):
        manager.create_record(
            symbol="",
            position_size=2.0,
            price=2000.0,
        )