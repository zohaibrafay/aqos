"""
Unit tests for BrokerService.
"""

import pytest

from aqos.services import (
    BrokerOrder,
    BrokerPosition,
    BrokerService,
)


def test_place_market_order():
    service = BrokerService()

    order = service.place_order(
        order_id="order-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1.0,
    )

    assert isinstance(order, BrokerOrder)
    assert order.order_id == "order-1"
    assert order.symbol == "XAUUSD"
    assert order.side == "buy"
    assert order.quantity == 1.0
    assert order.order_type == "market"
    assert order.status == "open"
    assert service.count_orders() == 1


def test_place_limit_order():
    service = BrokerService()

    order = service.place_order(
        order_id="order-1",
        symbol="XAUUSD",
        side="sell",
        quantity=2.0,
        order_type="limit",
        price=2050.0,
        metadata={"strategy": "breakout"},
    )

    assert order.order_type == "limit"
    assert order.price == 2050.0
    assert order.metadata["strategy"] == "breakout"


def test_get_order():
    service = BrokerService()

    service.place_order(
        order_id="order-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1.0,
    )

    order = service.get_order("order-1")

    assert order is not None
    assert order.order_id == "order-1"


def test_get_missing_order():
    service = BrokerService()

    order = service.get_order("missing")

    assert order is None


def test_get_required_missing_order():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.get_required_order("missing")


def test_exists_order_true():
    service = BrokerService()

    service.place_order(
        order_id="order-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1.0,
    )

    assert service.exists_order("order-1") is True


def test_exists_order_false():
    service = BrokerService()

    assert service.exists_order("order-1") is False


def test_list_orders():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)
    service.place_order("order-2", "EURUSD", "sell", 2.0)

    assert len(service.list_orders()) == 2


def test_list_order_ids():
    service = BrokerService()

    service.place_order("order-b", "XAUUSD", "buy", 1.0)
    service.place_order("order-a", "EURUSD", "sell", 2.0)

    assert service.list_order_ids() == [
        "order-a",
        "order-b",
    ]


def test_cancel_order():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)

    order = service.cancel_order("order-1")

    assert order.status == "cancelled"
    assert len(service.cancelled_orders()) == 1
    assert len(service.open_orders()) == 0


def test_fill_order():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)

    order = service.fill_order(
        order_id="order-1",
        fill_price=2000.0,
    )

    assert order.status == "filled"
    assert order.fill_price == 2000.0
    assert len(service.filled_orders()) == 1
    assert service.count_positions() == 1


def test_fill_order_creates_position():
    service = BrokerService()

    service.place_order(
        order_id="order-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1.0,
        metadata={"strategy": "trend"},
    )

    service.fill_order(
        order_id="order-1",
        fill_price=2000.0,
    )

    position = service.get_position("position-order-1")

    assert isinstance(position, BrokerPosition)
    assert position.symbol == "XAUUSD"
    assert position.side == "buy"
    assert position.entry_price == 2000.0
    assert position.status == "open"
    assert position.metadata["strategy"] == "trend"


def test_close_buy_position_profit():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 2.0)
    service.fill_order("order-1", 2000.0)

    position = service.close_position(
        position_id="position-order-1",
        exit_price=2010.0,
    )

    assert position.status == "closed"
    assert position.exit_price == 2010.0
    assert position.profit == 20.0
    assert service.realized_profit() == 20.0


def test_close_sell_position_profit():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "sell", 2.0)
    service.fill_order("order-1", 2000.0)

    position = service.close_position(
        position_id="position-order-1",
        exit_price=1990.0,
    )

    assert position.status == "closed"
    assert position.profit == 20.0
    assert service.realized_profit() == 20.0


def test_open_and_closed_positions():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)
    service.fill_order("order-1", 2000.0)

    assert len(service.open_positions()) == 1
    assert len(service.closed_positions()) == 0

    service.close_position("position-order-1", 2010.0)

    assert len(service.open_positions()) == 0
    assert len(service.closed_positions()) == 1


def test_clear_broker_state():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)
    service.fill_order("order-1", 2000.0)

    service.clear()

    assert service.count_orders() == 0
    assert service.count_positions() == 0


def test_duplicate_order_id():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)

    with pytest.raises(ValueError):
        service.place_order("order-1", "XAUUSD", "buy", 1.0)


def test_empty_order_id():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.place_order("", "XAUUSD", "buy", 1.0)


def test_empty_symbol():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.place_order("order-1", "", "buy", 1.0)


def test_invalid_side():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.place_order("order-1", "XAUUSD", "hold", 1.0)


def test_invalid_quantity():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.place_order("order-1", "XAUUSD", "buy", 0)


def test_invalid_order_type():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.place_order(
            order_id="order-1",
            symbol="XAUUSD",
            side="buy",
            quantity=1.0,
            order_type="invalid",
        )


def test_limit_order_requires_price():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.place_order(
            order_id="order-1",
            symbol="XAUUSD",
            side="buy",
            quantity=1.0,
            order_type="limit",
        )


def test_invalid_order_price():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.place_order(
            order_id="order-1",
            symbol="XAUUSD",
            side="buy",
            quantity=1.0,
            order_type="limit",
            price=0,
        )


def test_cannot_cancel_filled_order():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)
    service.fill_order("order-1", 2000.0)

    with pytest.raises(ValueError):
        service.cancel_order("order-1")


def test_cannot_fill_cancelled_order():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)
    service.cancel_order("order-1")

    with pytest.raises(ValueError):
        service.fill_order("order-1", 2000.0)


def test_invalid_fill_price():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)

    with pytest.raises(ValueError):
        service.fill_order("order-1", 0)


def test_missing_position():
    service = BrokerService()

    with pytest.raises(ValueError):
        service.get_required_position("missing")


def test_invalid_exit_price():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)
    service.fill_order("order-1", 2000.0)

    with pytest.raises(ValueError):
        service.close_position("position-order-1", 0)


def test_cannot_close_closed_position():
    service = BrokerService()

    service.place_order("order-1", "XAUUSD", "buy", 1.0)
    service.fill_order("order-1", 2000.0)
    service.close_position("position-order-1", 2010.0)

    with pytest.raises(ValueError):
        service.close_position("position-order-1", 2020.0)