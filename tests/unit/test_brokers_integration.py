"""
Unit tests for AQOS broker execution integration helpers.
"""

import pytest

from aqos.brokers import (
    BrokerExecutionHub,
    BrokerExecutionPayload,
    BrokerTrade,
    build_broker_execution_hub,
    build_broker_execution_payload,
    build_broker_order_request,
    build_broker_registry,
    build_broker_trade,
    build_paper_broker_adapter,
    build_position_account_adapter,
    build_sample_broker_execution_hub,
    build_sample_broker_registry,
    broker_account_snapshot_to_payload,
    broker_result_account,
    broker_result_order,
    broker_result_positions,
    broker_result_snapshot,
    broker_result_to_execution_payload,
    broker_result_trade,
    cancel_broker_order_via_hub,
    execution_failure,
    fetch_broker_account_snapshot,
    register_execution_adapters,
    submit_broker_order,
    submit_market_broker_order,
    validate_broker_execution_hub,
    validate_execution_positions,
)


def build_trade():
    return build_broker_trade(
        trade_id="trade-1",
        order_id="order-1",
        broker_id="paper-broker",
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        price=2000,
        fee=1,
        executed_at="2026-01-01T00:00:00+00:00",
    )


def test_broker_execution_payload_to_dict():
    payload = BrokerExecutionPayload(
        broker_id=" broker-1 ",
        operation=" submit_order ",
        success=True,
        order={
            "order_id": "order-1",
        },
        trade={
            "trade_id": "trade-1",
        },
        account={
            "account_id": "account-1",
        },
        positions=[
            {
                "symbol": "XAUUSD",
            }
        ],
        snapshot={
            "position_count": 1,
        },
        metadata={
            "source": "test",
        },
    )

    result = payload.to_dict()

    assert payload.failed is False
    assert payload.has_order is True
    assert payload.has_trade is True
    assert payload.has_account is True
    assert payload.position_count == 1
    assert result["broker_id"] == "broker-1"
    assert result["operation"] == "submit_order"
    assert result["metadata"] == {
        "source": "test",
    }


def test_broker_execution_payload_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="", operation="test", success=True)

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="", success=True)

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success="yes")

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, order=[])

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, trade=[])

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, account=[])

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, positions="bad")

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, positions=["bad"])

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, snapshot=[])

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, error=123)

    with pytest.raises(ValueError):
        BrokerExecutionPayload(broker_id="broker-1", operation="test", success=True, metadata=[])


def test_build_broker_execution_payload_and_validators():
    payload = build_broker_execution_payload(
        broker_id="broker-1",
        operation="test",
        success=True,
    )
    hub = build_broker_execution_hub()

    assert isinstance(payload, BrokerExecutionPayload)
    assert validate_execution_positions([{"symbol": "XAUUSD"}]) == [{"symbol": "XAUUSD"}]
    assert validate_broker_execution_hub(hub) == hub

    with pytest.raises(ValueError):
        validate_execution_positions("bad")

    with pytest.raises(ValueError):
        validate_execution_positions(["bad"])

    with pytest.raises(ValueError):
        validate_broker_execution_hub("bad")


def test_build_sample_broker_registry_and_hub():
    registry = build_sample_broker_registry(
        broker_id="paper-broker",
        cash_balance=100000,
    )
    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )

    assert registry.count() == 1
    assert isinstance(hub, BrokerExecutionHub)
    assert hub.summary()["registry"]["total"] == 1
    assert hub.summary()["metadata"] == {
        "sample": True,
    }


def test_register_execution_adapters():
    registry = build_broker_registry()
    paper_adapter = build_paper_broker_adapter(broker_id="paper-1")
    account_adapter = build_position_account_adapter(
        broker_config=paper_adapter.broker_config,
        account_id="account-1",
        cash_balance=100000,
    )

    entry = register_execution_adapters(
        registry=registry,
        broker_adapter=paper_adapter,
        account_adapter=account_adapter,
        metadata={
            "source": "test",
        },
    )

    assert entry.broker_id == "paper-1"
    assert entry.has_adapter is True
    assert entry.has_account_adapter is True
    assert entry.metadata == {
        "source": "test",
    }

    with pytest.raises(ValueError):
        register_execution_adapters(
            registry="bad",
            broker_adapter=paper_adapter,
        )

    with pytest.raises(ValueError):
        register_execution_adapters(
            registry=registry,
            broker_adapter="bad",
        )


def test_hub_submit_market_order_and_payload_conversion():
    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )

    result = hub.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
        client_order_id="client-1",
    )
    payload = hub.payload_from_result(
        result,
        operation="submit_market_order",
    )

    assert result.success is True
    assert result.data["order"]["status"] == "filled"
    assert result.data["trade"]["price"] == 2000.0
    assert isinstance(payload, BrokerExecutionPayload)
    assert payload.has_order is True
    assert payload.has_trade is True
    assert payload.order["client_order_id"] == "client-1"


def test_hub_submit_order_helper():
    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )
    request = build_broker_order_request(
        broker_id="paper-broker",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    result = submit_broker_order(
        hub=hub,
        request=request,
        market_price=2000,
    )

    assert result.success is True
    assert result.data["order"]["status"] == "filled"

    with pytest.raises(ValueError):
        submit_broker_order(
            hub="bad",
            request=request,
        )


def test_submit_market_broker_order_helper():
    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )

    result = submit_market_broker_order(
        hub=hub,
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
    )

    assert result.success is True
    assert result.data["trade"]["price"] == 2000.0

    with pytest.raises(ValueError):
        submit_market_broker_order(
            hub="bad",
            symbol="XAUUSD",
            side="buy",
            quantity=1,
            market_price=2000,
        )


def test_cancel_broker_order_via_hub():
    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )
    adapter = hub.resolve_execution_adapter(preferred_broker_id="paper-broker")
    adapter.fill_policy = "manual"

    submit_result = hub.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
        preferred_broker_id="paper-broker",
    )
    order_id = submit_result.data["order"]["order_id"]

    cancel_result = cancel_broker_order_via_hub(
        hub=hub,
        order_id=order_id,
        preferred_broker_id="paper-broker",
    )

    assert submit_result.success is True
    assert submit_result.data["order"]["status"] == "accepted"
    assert cancel_result.success is True
    assert cancel_result.data["order"]["status"] == "cancelled"

    with pytest.raises(ValueError):
        cancel_broker_order_via_hub(
            hub="bad",
            order_id=order_id,
        )


def test_account_snapshot_and_apply_trade():
    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )
    trade = build_trade()

    apply_result = hub.apply_trade_to_account(trade)
    snapshot_result = hub.account_snapshot()
    helper_snapshot_result = fetch_broker_account_snapshot(hub=hub)

    assert apply_result.success is True
    assert apply_result.data["position"]["symbol"] == "XAUUSD"
    assert snapshot_result.success is True
    assert snapshot_result.data["snapshot"]["position_count"] == 1
    assert helper_snapshot_result.success is True

    with pytest.raises(ValueError):
        fetch_broker_account_snapshot(hub="bad")


def test_apply_trade_to_broker_account_helper():
    from aqos.brokers import apply_trade_to_broker_account

    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )
    trade = build_trade()

    result = apply_trade_to_broker_account(
        hub=hub,
        trade=trade,
    )

    assert result.success is True
    assert result.data["position"]["quantity"] == 1.0

    with pytest.raises(ValueError):
        apply_trade_to_broker_account(
            hub="bad",
            trade=trade,
        )


def test_result_extractors_and_payload_conversion():
    hub = build_sample_broker_execution_hub(
        broker_id="paper-broker",
        cash_balance=100000,
    )
    order_result = hub.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
    )
    snapshot_result = hub.account_snapshot()

    order = broker_result_order(order_result)
    trade = broker_result_trade(order_result)
    snapshot = broker_result_snapshot(snapshot_result)
    account = broker_result_account(snapshot_result)
    positions = broker_result_positions(snapshot_result)

    payload = broker_result_to_execution_payload(
        order_result,
        operation="submit_market_order",
    )

    assert order is not None
    assert order["symbol"] == "XAUUSD"
    assert trade is not None
    assert trade["price"] == 2000.0
    assert snapshot is not None
    assert account is not None
    assert positions is not None
    assert payload.success is True
    assert payload.has_order is True

    failed = execution_failure(
        error="failed",
        operation="test",
    )

    assert broker_result_order(failed) is None
    assert broker_result_trade(failed) is None
    assert broker_result_snapshot(failed) is None
    assert broker_result_account(failed) is None
    assert broker_result_positions(failed) is None

    with pytest.raises(ValueError):
        broker_result_order("bad")

    with pytest.raises(ValueError):
        broker_result_trade("bad")

    with pytest.raises(ValueError):
        broker_result_snapshot("bad")

    with pytest.raises(ValueError):
        broker_result_account("bad")

    with pytest.raises(ValueError):
        broker_result_positions("bad")

    with pytest.raises(ValueError):
        broker_result_to_execution_payload("bad", operation="test")


def test_broker_account_snapshot_to_payload():
    hub = build_sample_broker_execution_hub()
    snapshot_result = hub.account_snapshot()
    account_snapshot = hub.registry.resolve_account_adapter().snapshot()

    payload = broker_account_snapshot_to_payload(account_snapshot)

    assert isinstance(payload, BrokerExecutionPayload)
    assert payload.has_account is True
    assert payload.position_count == 0
    assert payload.snapshot["position_count"] == 0

    with pytest.raises(ValueError):
        broker_account_snapshot_to_payload("bad")


def test_missing_adapter_failures():
    hub = build_broker_execution_hub()

    request = build_broker_order_request(
        broker_id="missing",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    submit_result = hub.submit_order(request, market_price=2000)
    market_result = hub.submit_market_order(
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        market_price=2000,
    )
    cancel_result = hub.cancel_order(order_id="order-1")
    snapshot_result = hub.account_snapshot()
    apply_result = hub.apply_trade_to_account(build_trade())

    assert submit_result.success is False
    assert submit_result.error == "Execution adapter is not registered."
    assert market_result.success is False
    assert cancel_result.success is False
    assert snapshot_result.success is False
    assert apply_result.success is False


def test_hub_rejects_invalid_inputs():
    hub = build_sample_broker_execution_hub()
    request = build_broker_order_request(
        broker_id="paper-broker",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    with pytest.raises(ValueError):
        hub.submit_order("bad")

    with pytest.raises(ValueError):
        hub.submit_order(request, market_price=-1)

    with pytest.raises(ValueError):
        hub.submit_market_order(
            symbol="bad symbol",
            side="buy",
            quantity=1,
            market_price=2000,
        )

    with pytest.raises(ValueError):
        hub.submit_market_order(
            symbol="XAUUSD",
            side="buy",
            quantity=0,
            market_price=2000,
        )

    with pytest.raises(ValueError):
        hub.submit_market_order(
            symbol="XAUUSD",
            side="buy",
            quantity=1,
            market_price=0,
        )

    with pytest.raises(ValueError):
        hub.cancel_order(order_id="")

    with pytest.raises(ValueError):
        hub.apply_trade_to_account("bad")


def test_execution_failure():
    result = execution_failure(
        error="failed",
        operation="unit-test",
    )

    assert result.success is False
    assert result.broker_id == "broker-execution-integration"
    assert result.error == "failed"
    assert result.metadata["operation"] == "unit-test"

    with pytest.raises(ValueError):
        execution_failure(error="failed", operation="")


def test_broker_integration_exports_exist():
    import aqos.brokers as brokers

    expected_exports = [
        "BrokerExecutionHub",
        "BrokerExecutionPayload",
        "apply_trade_to_broker_account",
        "broker_account_snapshot_to_payload",
        "broker_result_account",
        "broker_result_order",
        "broker_result_positions",
        "broker_result_snapshot",
        "broker_result_to_execution_payload",
        "broker_result_trade",
        "build_broker_execution_hub",
        "build_broker_execution_payload",
        "build_sample_broker_execution_hub",
        "build_sample_broker_registry",
        "cancel_broker_order_via_hub",
        "execution_failure",
        "fetch_broker_account_snapshot",
        "register_execution_adapters",
        "submit_broker_order",
        "submit_market_broker_order",
        "validate_broker_execution_hub",
        "validate_execution_positions",
    ]

    for export_name in expected_exports:
        assert hasattr(brokers, export_name), export_name