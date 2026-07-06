"""
Unit tests for PortfolioRiskManager.
"""

import pytest

from aqos.risk import PortfolioPosition, PortfolioRiskManager


def test_create_buy_position():
    manager = PortfolioRiskManager()

    position = manager.create_position(
        symbol="XAUUSD",
        side="buy",
        quantity=2.0,
        entry_price=2000.0,
        current_price=2010.0,
    )

    assert isinstance(position, PortfolioPosition)
    assert position.value == 4020.0
    assert position.unrealized_pnl == 20.0


def test_create_sell_position():
    manager = PortfolioRiskManager()

    position = manager.create_position(
        symbol="XAUUSD",
        side="sell",
        quantity=2.0,
        entry_price=2000.0,
        current_price=1990.0,
    )

    assert position.value == 3980.0
    assert position.unrealized_pnl == 20.0


def test_total_value():
    manager = PortfolioRiskManager()

    positions = [
        manager.create_position("XAUUSD", "buy", 1.0, 2000.0, 2010.0),
        manager.create_position("EURUSD", "buy", 1000.0, 1.1, 1.2),
    ]

    assert manager.total_value(positions) == 3210.0


def test_total_unrealized_pnl():
    manager = PortfolioRiskManager()

    positions = [
        manager.create_position("XAUUSD", "buy", 1.0, 2000.0, 2010.0),
        manager.create_position("EURUSD", "sell", 1000.0, 1.2, 1.1),
    ]

    assert manager.total_unrealized_pnl(positions) == pytest.approx(110.0)


def test_exposure_by_symbol():
    manager = PortfolioRiskManager()

    positions = [
        manager.create_position("XAUUSD", "buy", 1.0, 2000.0, 2010.0),
        manager.create_position("XAUUSD", "buy", 1.0, 2000.0, 2020.0),
    ]

    exposure = manager.exposure_by_symbol(positions)

    assert exposure["XAUUSD"] == 4030.0


def test_symbol_exposure_within_limit_true():
    manager = PortfolioRiskManager(max_symbol_exposure_percent=0.5)

    positions = [
        manager.create_position("XAUUSD", "buy", 1.0, 2000.0, 2000.0),
    ]

    result = manager.is_symbol_exposure_within_limit(
        positions=positions,
        symbol="XAUUSD",
        account_balance=10_000.0,
    )

    assert result is True


def test_symbol_exposure_within_limit_false():
    manager = PortfolioRiskManager(max_symbol_exposure_percent=0.1)

    positions = [
        manager.create_position("XAUUSD", "buy", 1.0, 2000.0, 2000.0),
    ]

    result = manager.is_symbol_exposure_within_limit(
        positions=positions,
        symbol="XAUUSD",
        account_balance=10_000.0,
    )

    assert result is False


def test_largest_symbol_exposure_percent():
    manager = PortfolioRiskManager()

    positions = [
        manager.create_position("XAUUSD", "buy", 1.0, 2000.0, 2000.0),
        manager.create_position("EURUSD", "buy", 1000.0, 1.0, 1.0),
    ]

    result = manager.largest_symbol_exposure_percent(
        positions=positions,
        account_balance=10_000.0,
    )

    assert result == 0.2


def test_invalid_max_symbol_exposure_percent():
    with pytest.raises(ValueError):
        PortfolioRiskManager(max_symbol_exposure_percent=0)


def test_invalid_symbol():
    manager = PortfolioRiskManager()

    with pytest.raises(ValueError):
        manager.create_position("", "buy", 1.0, 2000.0, 2000.0)


def test_invalid_side():
    manager = PortfolioRiskManager()

    with pytest.raises(ValueError):
        manager.create_position("XAUUSD", "hold", 1.0, 2000.0, 2000.0)


def test_invalid_quantity():
    manager = PortfolioRiskManager()

    with pytest.raises(ValueError):
        manager.create_position("XAUUSD", "buy", 0, 2000.0, 2000.0)