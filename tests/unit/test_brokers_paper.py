"""
Unit tests for AQOS paper broker adapter.
"""

import pytest

from aqos.brokers import (
    BrokerCapability,
    BrokerStatus,
    BrokerType,
    OrderStatus,
    OrderType,
    PaperBrokerAdapter,
    PaperBrokerSnapshot,
    PaperFillPolicy,
    build_broker_config,
    build_broker_order,
    build_broker_order_request,
    build_broker_trade,
    build_paper_broker_adapter,
    build_paper_broker_snapshot,
    cancel_paper_order,
    fill_paper_order,
    normalize_paper_fill_policy,
    paper_broker_error_result,
    paper_broker_snapshot_result,
    reject_paper_order,
    resolve_paper_fill_price,
    should_auto_fill_order,
    submit_paper_order,
    validate_paper_broker_config,
    validate_paper_order_dict,
    validate_paper_orders,
    validate_paper_price_dict,
    validate_paper_trade_dict,
    validate_paper_trades,
)


def build_order():
    return build_broker_order(
        order_id="order-1",
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
        status="accepted",
    )


def build_trade():
    return build_broker_trade(
        trade_id="trade-1",
        order_id="order-1",
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        price=2000,
    )


def test_paper_fill_policy_normalizer():
    assert PaperFillPolicy.IMMEDIATE_MARKET.value == "immediate_market"
    assert PaperFillPolicy.MANUAL.value == "manual"
    assert normalize_paper_fill_policy(PaperFillPolicy.MANUAL) == PaperFillPolicy.MANUAL
    assert normalize_paper_fill_policy(" IMMEDIATE_MARKET ") == PaperFillPolicy.IMMEDIATE_MARKET

    with pytest.raises(ValueError):
        normalize_paper_fill_policy("bad")


def test_paper_snapshot_to_dict():
    snapshot = PaperBrokerSnapshot(
        broker_id=" paper-1 ",
        cash_balance=100000,
        orders=[build_order()],
        trades=[build_trade()],
        metadata={
            "source": "test",
        },
    )

    payload = snapshot.to_dict()

    assert snapshot.order_count == 1
    assert snapshot.trade_count == 1
    assert snapshot.open_order_count == 1
    assert snapshot.filled_order_count == 0
    assert payload["broker_id"] == "paper-1"
    assert payload["cash_balance"] == 100000.0
    assert payload["metadata"] == {
        "source": "test",
    }


def test_paper_snapshot_rejects_invalid_values():
    with pytest.raises(ValueError):
        PaperBrokerSnapshot(broker_id="", cash_balance=100000)

    with pytest.raises(ValueError):
        PaperBrokerSnapshot(broker_id="paper-1", cash_balance=-1)

    with pytest.raises(ValueError):
        PaperBrokerSnapshot(broker_id="paper-1", cash_balance=100000, orders=["bad"])

    with pytest.raises(ValueError):
        PaperBrokerSnapshot(broker_id="paper-1", cash_balance=100000, trades=["bad"])

    with pytest.raises(ValueError):
        PaperBrokerSnapshot(broker_id="paper-1", cash_balance=100000, metadata=[])


def test_build_paper_broker_snapshot():
    snapshot = build_paper_broker_snapshot(
        broker_id="paper-1",
        cash_balance=100000,
    )

    assert isinstance(snapshot, PaperBrokerSnapshot)
    assert snapshot.order_count == 0


def test_validate_paper_broker_config():
    config = build_broker_config(
        broker_id="paper-1",
        name="Paper",
        broker_type="paper",
        capabilities=["paper_trading"],
        paper_mode=True,
    )

    assert validate_paper_broker_config(config) == config

    with pytest.raises(ValueError):
        validate_paper_broker_config("bad")

    with pytest.raises(ValueError):
        validate_paper_broker_config(
            build_broker_config(
                broker_id="exchange-1",
                name="Exchange",
                broker_type=BrokerType.EXCHANGE,
                capabilities=["paper_trading"],
                paper_mode=True,
            ),
        )

    with pytest.raises(ValueError):
        validate_paper_broker_config(
            build_broker_config(
                broker_id="paper-1",
                name="Paper",
                broker_type="paper",
                capabilities=["paper_trading"],
                paper_mode=False,
            ),
        )

    with pytest.raises(ValueError):
        validate_paper_broker_config(
            build_broker_config(
                broker_id="paper-1",
                name="Paper",
                broker_type="paper",
                capabilities=["market_orders"],
                paper_mode=True,
            ),
        )


def test_paper_validators():
    order = build_order()
    trade = build_trade()

    assert validate_paper_orders([order]) == [order]
    assert validate_paper_trades([trade]) == [trade]
    assert validate_paper_order_dict({"order-1": order}) == {"order-1": order}
    assert validate_paper_trade_dict({"trade-1": trade}) == {"trade-1": trade}
    assert validate_paper_price_dict({"XAUUSD": 2000}) == {"XAUUSD": 2000}

    with pytest.raises(ValueError):
        validate_paper_orders("bad")

    with pytest.raises(ValueError):
        validate_paper_orders(["bad"])

    with pytest.raises(ValueError):
        validate_paper_trades("bad")

    with pytest.raises(ValueError):
        validate_paper_trades(["bad"])

    with pytest.raises(ValueError):
        validate_paper_order_dict("bad")

    with pytest.raises(ValueError):
        validate_paper_order_dict({"": order})

    with pytest.raises(ValueError):
        validate_paper_order_dict({"order-1": "bad"})

    with pytest.raises(ValueError):
        validate_paper_trade_dict("bad")

    with pytest.raises(ValueError):
        validate_paper_trade_dict({"": trade})

    with pytest.raises(ValueError):
        validate_paper_trade_dict({"trade-1": "bad"})

    with pytest.raises(ValueError):
        validate_paper_price_dict("bad")

    with pytest.raises(ValueError):
        validate_paper_price_dict({"bad symbol": 2000})

    with pytest.raises(ValueError):
        validate_paper_price_dict({"XAUUSD": 0})


def test_build_paper_broker_adapter():
    adapter = build_paper_broker_adapter(
        broker_id="paper-1",
        name="Paper 1",
        cash_balance=50000,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(adapter, PaperBrokerAdapter)
    assert adapter.broker_id == "paper-1"
    assert adapter.active is True
    assert adapter.cash_balance == 50000
    assert adapter.broker_config.supports(BrokerCapability.PAPER_TRADING)
    assert adapter.metadata == {
        "source": "test",
    }


def test_paper_broker_adapter_rejects_invalid_values():
    config = build_broker_config(
        broker_id="paper-1",
        name="Paper",
        broker_type="paper",
        capabilities=["paper_trading"],
    )

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config="bad")

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, cash_balance=-1)

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, fill_policy="bad")

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, orders=[])

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, trades=[])

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, last_prices=[])

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, order_sequence=-1)

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, trade_sequence=-1)

    with pytest.raises(ValueError):
        PaperBrokerAdapter(broker_config=config, metadata=[])


def test_update_and_get_price():
    adapter = build_paper_broker_adapter(broker_id="paper-1")

    assert adapter.get_price("XAUUSD") == 0.0
    assert adapter.update_price(symbol="xauusd", price=2000) == 2000.0
    assert adapter.get_price("XAUUSD") == 2000.0

    with pytest.raises(ValueError):
        adapter.update_price(symbol="bad symbol", price=2000)

    with pytest.raises(ValueError):
        adapter.update_price(symbol="XAUUSD", price=0)


def test_submit_market_order_auto_fills():
    adapter = build_paper_broker_adapter(
        broker_id="paper-1",
        cash_balance=100000,
    )

    result = adapter.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=2,
        market_price=2000,
        client_order_id="client-1",
    )

    assert result.success is True
    assert result.data["order"]["status"] == "filled"
    assert result.data["order"]["filled_quantity"] == 2.0
    assert result.data["trade"]["price"] == 2000.0
    assert result.data["cash_balance"] == 96000.0
    assert len(adapter.list_orders()) == 1
    assert len(adapter.list_trades()) == 1
    assert adapter.filled_orders()[0].filled is True


def test_submit_market_order_uses_last_price():
    adapter = build_paper_broker_adapter(broker_id="paper-1")
    adapter.update_price(symbol="XAUUSD", price=2001)

    request = build_broker_order_request(
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    result = adapter.submit_order(request)

    assert result.success is True
    assert result.data["trade"]["price"] == 2001.0


def test_submit_market_order_without_price_rejects():
    adapter = build_paper_broker_adapter(broker_id="paper-1")
    request = build_broker_order_request(
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    result = adapter.submit_order(request)

    assert result.success is True
    assert result.data["order"]["status"] == "rejected"
    assert result.data["order"]["metadata"]["rejection_reason"] == "Market price is required for paper market fill."


def test_submit_limit_order_stays_open():
    adapter = build_paper_broker_adapter(broker_id="paper-1")
    request = build_broker_order_request(
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        order_type="limit",
        quantity=1,
        price=1990,
    )

    result = adapter.submit_order(request)

    assert result.success is True
    assert result.data["order"]["status"] == "accepted"
    assert len(adapter.open_orders()) == 1


def test_submit_order_failures():
    adapter = build_paper_broker_adapter(broker_id="paper-1")
    wrong_request = build_broker_order_request(
        broker_id="other",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    wrong_result = adapter.submit_order(wrong_request)

    inactive_adapter = build_paper_broker_adapter(
        broker_config=build_broker_config(
            broker_id="inactive",
            name="Inactive",
            broker_type="paper",
            status=BrokerStatus.INACTIVE,
            capabilities=["paper_trading"],
            paper_mode=True,
        ),
    )
    inactive_request = build_broker_order_request(
        broker_id="inactive",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )
    inactive_result = inactive_adapter.submit_order(inactive_request)

    assert wrong_result.success is False
    assert wrong_result.error == "Request broker ID does not match paper broker ID."
    assert inactive_result.success is False
    assert inactive_result.error == "Paper broker is not active."

    with pytest.raises(ValueError):
        adapter.submit_order("bad")


def test_manual_fill_flow():
    adapter = build_paper_broker_adapter(
        broker_id="paper-1",
        fill_policy="manual",
    )
    request = build_broker_order_request(
        broker_id="paper-1",
        symbol="XAUUSD",
        side="sell",
        order_type="market",
        quantity=2,
    )

    submit_result = adapter.submit_order(request)
    order_id = submit_result.data["order"]["order_id"]

    fill_result = adapter.fill_order(
        order_id=order_id,
        fill_quantity=1,
        fill_price=2000,
        fee=1,
    )

    assert submit_result.success is True
    assert submit_result.data["order"]["status"] == "accepted"
    assert fill_result.success is True
    assert fill_result.data["order"]["status"] == "partially_filled"
    assert fill_result.data["cash_balance"] == 101999.0


def test_fill_order_failures():
    adapter = build_paper_broker_adapter(broker_id="paper-1")

    missing_result = adapter.fill_order(
        order_id="missing",
        fill_quantity=1,
        fill_price=2000,
    )

    assert missing_result.success is False
    assert missing_result.error == "Order not found."

    filled_result = adapter.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
    )
    order_id = filled_result.data["order"]["order_id"]

    second_fill = adapter.fill_order(
        order_id=order_id,
        fill_quantity=1,
        fill_price=2000,
    )

    assert second_fill.success is False
    assert second_fill.error == "Only open orders can be filled."


def test_cancel_order_flow_and_failures():
    adapter = build_paper_broker_adapter(
        broker_id="paper-1",
        fill_policy="manual",
    )
    request = build_broker_order_request(
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )
    submit_result = adapter.submit_order(request)
    order_id = submit_result.data["order"]["order_id"]

    cancel_result = adapter.cancel_order(order_id)

    assert cancel_result.success is True
    assert cancel_result.data["order"]["status"] == "cancelled"

    missing_result = adapter.cancel_order("missing")

    assert missing_result.success is False
    assert missing_result.error == "Order not found."

    filled = adapter.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
    )
    filled_cancel = adapter.cancel_order(filled.data["order"]["order_id"])

    assert filled_cancel.success is False
    assert "Filled orders cannot be cancelled" in filled_cancel.error


def test_lists_snapshot_reset_and_lookup():
    adapter = build_paper_broker_adapter(broker_id="paper-1")
    result = adapter.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
    )
    order_id = result.data["order"]["order_id"]
    trade_id = result.data["trade"]["trade_id"]

    assert adapter.get_order(order_id).order_id == order_id
    assert adapter.get_trade(trade_id).trade_id == trade_id
    assert len(adapter.list_orders()) == 1
    assert len(adapter.list_trades()) == 1
    assert len(adapter.trades_for_symbol("xauusd")) == 1

    snapshot = adapter.snapshot()

    assert snapshot.order_count == 1
    assert snapshot.trade_count == 1

    adapter.reset(cash_balance=50000)

    assert adapter.cash_balance == 50000
    assert adapter.list_orders() == []
    assert adapter.list_trades() == []
    assert adapter.order_sequence == 0
    assert adapter.trade_sequence == 0

    with pytest.raises(ValueError):
        adapter.get_order("")

    with pytest.raises(ValueError):
        adapter.get_trade("")

    with pytest.raises(ValueError):
        adapter.reset(cash_balance=-1)


def test_helpers():
    adapter = build_paper_broker_adapter(broker_id="paper-1")
    order = build_order()

    assert should_auto_fill_order(order=order, fill_policy="immediate_market") is True
    assert should_auto_fill_order(order=order, fill_policy="manual") is False
    assert resolve_paper_fill_price(order=order, market_price=2000) == 2000
    assert resolve_paper_fill_price(order=order, last_price=2001) == 2001

    limit_order = build_broker_order(
        order_id="order-2",
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        order_type="limit",
        quantity=1,
        price=1990,
    )

    assert resolve_paper_fill_price(order=limit_order) == 1990

    rejected = reject_paper_order(order, reason="bad")
    assert rejected.status == OrderStatus.REJECTED

    request = build_broker_order_request(
        broker_id="paper-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    adapter.update_price(symbol="XAUUSD", price=2000)
    submit_result = submit_paper_order(adapter=adapter, request=request)
    fill_result = fill_paper_order(
        adapter=build_paper_broker_adapter(broker_id="paper-2"),
        order_id="missing",
        fill_quantity=1,
        fill_price=2000,
    )
    cancel_result = cancel_paper_order(adapter=adapter, order_id=submit_result.data["order"]["order_id"])
    snapshot_result = paper_broker_snapshot_result(adapter)
    error_result = paper_broker_error_result(
        broker_id="paper-1",
        error="failed",
        operation="test",
    )

    assert submit_result.success is True
    assert fill_result.success is False
    assert cancel_result.success is False
    assert snapshot_result.success is True
    assert error_result.success is False

    with pytest.raises(ValueError):
        should_auto_fill_order(order="bad", fill_policy="manual")

    with pytest.raises(ValueError):
        resolve_paper_fill_price(order="bad")

    with pytest.raises(ValueError):
        submit_paper_order(adapter="bad", request=request)

    with pytest.raises(ValueError):
        fill_paper_order(adapter="bad", order_id="order-1", fill_quantity=1, fill_price=1)

    with pytest.raises(ValueError):
        cancel_paper_order(adapter="bad", order_id="order-1")

    with pytest.raises(ValueError):
        paper_broker_snapshot_result("bad")


def test_apply_cash_impact_rejects_invalid_trade():
    adapter = build_paper_broker_adapter(broker_id="paper-1")

    with pytest.raises(ValueError):
        adapter.apply_cash_impact("bad")


def test_paper_broker_exports_exist():
    import aqos.brokers as brokers

    expected_exports = [
        "PaperBrokerAdapter",
        "PaperBrokerSnapshot",
        "PaperFillPolicy",
        "build_paper_broker_adapter",
        "build_paper_broker_snapshot",
        "cancel_paper_order",
        "fill_paper_order",
        "normalize_paper_fill_policy",
        "paper_broker_error_result",
        "paper_broker_snapshot_result",
        "reject_paper_order",
        "resolve_paper_fill_price",
        "should_auto_fill_order",
        "submit_paper_order",
        "validate_paper_broker_config",
        "validate_paper_order_dict",
        "validate_paper_orders",
        "validate_paper_price_dict",
        "validate_paper_trade_dict",
        "validate_paper_trades",
    ]

    for export_name in expected_exports:
        assert hasattr(brokers, export_name), export_name