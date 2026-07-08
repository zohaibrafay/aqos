"""
Unit tests for AQOS broker order and trade contracts.
"""

import pytest

from aqos.brokers import (
    BrokerOrder,
    BrokerOrderRequest,
    BrokerTrade,
    OrderSide,
    OrderStatus,
    OrderType,
    TimeInForce,
    TradeStatus,
    build_broker_order,
    build_broker_order_request,
    build_broker_trade,
    cancel_broker_order,
    fill_broker_order,
    normalize_order_side,
    normalize_order_status,
    normalize_order_type,
    normalize_time_in_force,
    normalize_trade_status,
    order_error_result,
    order_request_to_order,
    order_to_broker_result,
    reject_broker_order,
    trade_to_broker_result,
    validate_order_symbol,
)


def test_order_enum_values():
    assert OrderSide.BUY.value == "buy"
    assert OrderSide.SELL.value == "sell"

    assert OrderType.MARKET.value == "market"
    assert OrderType.LIMIT.value == "limit"
    assert OrderType.STOP.value == "stop"
    assert OrderType.STOP_LIMIT.value == "stop_limit"

    assert OrderStatus.PENDING.value == "pending"
    assert OrderStatus.ACCEPTED.value == "accepted"
    assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert OrderStatus.FILLED.value == "filled"
    assert OrderStatus.CANCELLED.value == "cancelled"
    assert OrderStatus.REJECTED.value == "rejected"

    assert TimeInForce.GTC.value == "gtc"
    assert TimeInForce.IOC.value == "ioc"
    assert TimeInForce.FOK.value == "fok"
    assert TimeInForce.DAY.value == "day"

    assert TradeStatus.OPEN.value == "open"
    assert TradeStatus.CLOSED.value == "closed"


def test_order_normalizers_accept_enum_and_string():
    assert normalize_order_side(OrderSide.BUY) == OrderSide.BUY
    assert normalize_order_side(" SELL ") == OrderSide.SELL
    assert normalize_order_type(OrderType.MARKET) == OrderType.MARKET
    assert normalize_order_type(" LIMIT ") == OrderType.LIMIT
    assert normalize_order_status(OrderStatus.ACCEPTED) == OrderStatus.ACCEPTED
    assert normalize_order_status(" FILLED ") == OrderStatus.FILLED
    assert normalize_time_in_force(TimeInForce.GTC) == TimeInForce.GTC
    assert normalize_time_in_force(" IOC ") == TimeInForce.IOC
    assert normalize_trade_status(TradeStatus.OPEN) == TradeStatus.OPEN
    assert normalize_trade_status(" CLOSED ") == TradeStatus.CLOSED


def test_order_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_order_side("bad")

    with pytest.raises(ValueError):
        normalize_order_type("bad")

    with pytest.raises(ValueError):
        normalize_order_status("bad")

    with pytest.raises(ValueError):
        normalize_time_in_force("bad")

    with pytest.raises(ValueError):
        normalize_trade_status("bad")


def test_validate_order_symbol():
    assert validate_order_symbol("xauusd") == "XAUUSD"
    assert validate_order_symbol("btc/usdt") == "BTC/USDT"
    assert validate_order_symbol("eth-usdt") == "ETH-USDT"

    with pytest.raises(ValueError):
        validate_order_symbol("")

    with pytest.raises(ValueError):
        validate_order_symbol("BAD SYMBOL")

    with pytest.raises(ValueError):
        validate_order_symbol("BTC_USDT")


def test_broker_order_request_to_dict_market_order():
    request = BrokerOrderRequest(
        broker_id=" broker-1 ",
        symbol=" xauusd ",
        side=" BUY ",
        order_type=" MARKET ",
        quantity=2,
        time_in_force=" IOC ",
        client_order_id=" client-1 ",
        metadata={
            "source": "test",
        },
    )

    assert request.estimated_notional == 0.0
    assert request.to_dict() == {
        "broker_id": "broker-1",
        "symbol": "XAUUSD",
        "side": "buy",
        "order_type": "market",
        "quantity": 2.0,
        "price": 0.0,
        "stop_price": 0.0,
        "time_in_force": "ioc",
        "client_order_id": "client-1",
        "estimated_notional": 0.0,
        "metadata": {
            "source": "test",
        },
    }


def test_broker_order_request_limit_and_stop_orders():
    limit_request = build_broker_order_request(
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="limit",
        quantity=2,
        price=2000,
    )
    stop_request = build_broker_order_request(
        broker_id="broker-1",
        symbol="XAUUSD",
        side="sell",
        order_type="stop",
        quantity=2,
        stop_price=1990,
    )
    stop_limit_request = build_broker_order_request(
        broker_id="broker-1",
        symbol="XAUUSD",
        side="sell",
        order_type="stop_limit",
        quantity=2,
        price=1988,
        stop_price=1990,
    )

    assert limit_request.estimated_notional == 4000.0
    assert stop_request.estimated_notional == 3980.0
    assert stop_limit_request.estimated_notional == 3976.0


def test_broker_order_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="", symbol="XAUUSD", side="buy", order_type="market", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="bad symbol", side="buy", order_type="market", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="bad", order_type="market", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="bad", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=0)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, price=-1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, stop_price=-1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="limit", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="stop", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, time_in_force="bad")

    with pytest.raises(ValueError):
        BrokerOrderRequest(broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, metadata=[])


def test_broker_order_to_dict():
    order = BrokerOrder(
        order_id=" order-1 ",
        broker_id=" broker-1 ",
        symbol=" xauusd ",
        side=" BUY ",
        order_type=" MARKET ",
        quantity=2,
        status=" FILLED ",
        filled_quantity=2,
        average_fill_price=2001,
        fee=1.5,
        client_order_id=" client-1 ",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:01+00:00",
        metadata={
            "source": "test",
        },
    )

    payload = order.to_dict()

    assert order.remaining_quantity == 0.0
    assert order.filled is True
    assert order.open is False
    assert order.filled_notional == 4002.0
    assert payload["order_id"] == "order-1"
    assert payload["broker_id"] == "broker-1"
    assert payload["symbol"] == "XAUUSD"
    assert payload["status"] == "filled"
    assert payload["filled"] is True
    assert payload["open"] is False
    assert payload["fee"] == 1.5


def test_broker_order_properties():
    pending = build_broker_order(
        order_id="order-1",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=2,
        status="pending",
    )
    cancelled = build_broker_order(
        order_id="order-2",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=2,
        status="cancelled",
    )
    rejected = build_broker_order(
        order_id="order-3",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=2,
        status="rejected",
    )

    assert pending.open is True
    assert pending.filled is False
    assert cancelled.cancelled is True
    assert rejected.rejected is True


def test_broker_order_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerOrder(order_id="", broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="", symbol="XAUUSD", side="buy", order_type="market", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="bad symbol", side="buy", order_type="market", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="bad", order_type="market", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="bad", quantity=1)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=0)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, status="bad")

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, filled_quantity=2)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, fee=-1)

    with pytest.raises(ValueError):
        BrokerOrder(order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", order_type="market", quantity=1, metadata=[])


def test_broker_trade_to_dict():
    trade = BrokerTrade(
        trade_id=" trade-1 ",
        order_id=" order-1 ",
        broker_id=" broker-1 ",
        symbol=" xauusd ",
        side=" BUY ",
        quantity=2,
        price=2001,
        fee=1.5,
        status=" CLOSED ",
        executed_at="2026-01-01T00:00:01+00:00",
        metadata={
            "source": "test",
        },
    )

    payload = trade.to_dict()

    assert trade.notional == 4002.0
    assert trade.closed is True
    assert payload["trade_id"] == "trade-1"
    assert payload["order_id"] == "order-1"
    assert payload["symbol"] == "XAUUSD"
    assert payload["side"] == "buy"
    assert payload["status"] == "closed"


def test_broker_trade_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerTrade(trade_id="", order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", quantity=1, price=1)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="", broker_id="broker-1", symbol="XAUUSD", side="buy", quantity=1, price=1)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="", symbol="XAUUSD", side="buy", quantity=1, price=1)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="broker-1", symbol="bad symbol", side="buy", quantity=1, price=1)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="bad", quantity=1, price=1)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", quantity=0, price=1)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", quantity=1, price=0)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", quantity=1, price=1, fee=-1)

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", quantity=1, price=1, status="bad")

    with pytest.raises(ValueError):
        BrokerTrade(trade_id="trade-1", order_id="order-1", broker_id="broker-1", symbol="XAUUSD", side="buy", quantity=1, price=1, metadata=[])


def test_order_request_to_order():
    request = build_broker_order_request(
        broker_id="broker-1",
        symbol="xauusd",
        side="buy",
        order_type="market",
        quantity=2,
        client_order_id="client-1",
        metadata={
            "source": "request",
        },
    )

    order = order_request_to_order(
        request,
        order_id="order-1",
        created_at="2026-01-01T00:00:00+00:00",
        metadata={
            "accepted_by": "paper",
        },
    )

    assert isinstance(order, BrokerOrder)
    assert order.order_id == "order-1"
    assert order.status == OrderStatus.ACCEPTED
    assert order.metadata == {
        "source": "request",
        "accepted_by": "paper",
    }

    with pytest.raises(ValueError):
        order_request_to_order("bad", order_id="order-1")


def test_fill_broker_order_partial_and_full():
    order = build_broker_order(
        order_id="order-1",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=2,
        status="accepted",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )

    partially_filled, trade_1 = fill_broker_order(
        order,
        trade_id="trade-1",
        fill_quantity=1,
        fill_price=2000,
        fee=1,
        executed_at="2026-01-01T00:00:01+00:00",
    )

    filled, trade_2 = fill_broker_order(
        partially_filled,
        trade_id="trade-2",
        fill_quantity=1,
        fill_price=2002,
        fee=1,
        executed_at="2026-01-01T00:00:02+00:00",
    )

    assert partially_filled.status == OrderStatus.PARTIALLY_FILLED
    assert partially_filled.filled_quantity == 1
    assert partially_filled.average_fill_price == 2000
    assert partially_filled.fee == 1
    assert trade_1.notional == 2000

    assert filled.status == OrderStatus.FILLED
    assert filled.filled_quantity == 2
    assert filled.average_fill_price == 2001
    assert filled.fee == 2
    assert filled.remaining_quantity == 0
    assert trade_2.notional == 2002


def test_fill_broker_order_rejects_invalid_values():
    order = build_broker_order(
        order_id="order-1",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    with pytest.raises(ValueError):
        fill_broker_order("bad", trade_id="trade-1", fill_quantity=1, fill_price=1)

    with pytest.raises(ValueError):
        fill_broker_order(order, trade_id="trade-1", fill_quantity=0, fill_price=1)

    with pytest.raises(ValueError):
        fill_broker_order(order, trade_id="trade-1", fill_quantity=1, fill_price=0)

    with pytest.raises(ValueError):
        fill_broker_order(order, trade_id="trade-1", fill_quantity=1, fill_price=1, fee=-1)

    with pytest.raises(ValueError):
        fill_broker_order(order, trade_id="trade-1", fill_quantity=2, fill_price=1)


def test_cancel_and_reject_order():
    order = build_broker_order(
        order_id="order-1",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
        status="accepted",
    )

    cancelled = cancel_broker_order(
        order,
        updated_at="2026-01-01T00:00:01+00:00",
        metadata={
            "cancelled_by": "test",
        },
    )
    rejected = reject_broker_order(
        order,
        reason="Risk rejected",
        updated_at="2026-01-01T00:00:02+00:00",
    )

    assert cancelled.status == OrderStatus.CANCELLED
    assert cancelled.cancelled is True
    assert cancelled.metadata["cancelled_by"] == "test"

    assert rejected.status == OrderStatus.REJECTED
    assert rejected.rejected is True
    assert rejected.metadata["rejection_reason"] == "Risk rejected"

    filled_order = build_broker_order(
        order_id="order-2",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
        status="filled",
        filled_quantity=1,
        average_fill_price=2000,
    )

    with pytest.raises(ValueError):
        cancel_broker_order("bad")

    with pytest.raises(ValueError):
        cancel_broker_order(filled_order)

    with pytest.raises(ValueError):
        reject_broker_order("bad", reason="bad")

    with pytest.raises(ValueError):
        reject_broker_order(order, reason="")


def test_order_and_trade_result_helpers():
    order = build_broker_order(
        order_id="order-1",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )
    trade = build_broker_trade(
        trade_id="trade-1",
        order_id="order-1",
        broker_id="broker-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        price=2000,
    )

    order_result = order_to_broker_result(order)
    trade_result = trade_to_broker_result(trade)
    error_result = order_error_result(
        broker_id="broker-1",
        error="failed",
        operation="submit_order",
    )

    assert order_result.success is True
    assert order_result.data["order"]["order_id"] == "order-1"
    assert trade_result.success is True
    assert trade_result.data["trade"]["trade_id"] == "trade-1"
    assert error_result.success is False
    assert error_result.metadata["operation"] == "submit_order"

    with pytest.raises(ValueError):
        order_to_broker_result("bad")

    with pytest.raises(ValueError):
        trade_to_broker_result("bad")

    with pytest.raises(ValueError):
        order_error_result(broker_id="broker-1", error="failed", operation="")


def test_broker_order_exports_exist():
    import aqos.brokers as brokers

    expected_exports = [
        "BrokerOrder",
        "BrokerOrderRequest",
        "BrokerTrade",
        "OrderSide",
        "OrderStatus",
        "OrderType",
        "TimeInForce",
        "TradeStatus",
        "build_broker_order",
        "build_broker_order_request",
        "build_broker_trade",
        "cancel_broker_order",
        "fill_broker_order",
        "normalize_order_side",
        "normalize_order_status",
        "normalize_order_type",
        "normalize_time_in_force",
        "normalize_trade_status",
        "order_error_result",
        "order_request_to_order",
        "order_to_broker_result",
        "reject_broker_order",
        "trade_to_broker_result",
        "validate_order_symbol",
    ]

    for export_name in expected_exports:
        assert hasattr(brokers, export_name), export_name