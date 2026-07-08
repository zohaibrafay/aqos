"""
Unit tests for AQOS exchange HTTP broker adapter.
"""

import pytest

from aqos.brokers import (
    BrokerAccount,
    BrokerOrder,
    BrokerPosition,
    BrokerStatus,
    BrokerTrade,
    ExchangeHttpBrokerAdapter,
    ExchangeHttpMethod,
    ExchangeHttpRequest,
    ExchangeHttpResponse,
    build_broker_config,
    build_broker_order_request,
    build_exchange_http_broker_adapter,
    build_exchange_http_request,
    build_exchange_http_response,
    cancel_exchange_http_order,
    exchange_http_error_result,
    fetch_exchange_http_account,
    fetch_exchange_http_positions,
    is_success_exchange_http_status,
    join_exchange_http_url,
    json_payload_to_broker_account,
    json_payload_to_broker_order,
    json_payload_to_broker_position,
    json_payload_to_broker_positions,
    json_payload_to_broker_trade,
    normalize_exchange_http_method,
    submit_exchange_http_order,
    validate_exchange_http_broker_config,
    validate_exchange_http_headers,
    validate_exchange_http_params,
    validate_exchange_http_status_code,
    validate_exchange_http_url,
)


def fake_transport(request: ExchangeHttpRequest) -> ExchangeHttpResponse:
    if request.method == ExchangeHttpMethod.POST and request.url.endswith("/orders"):
        return build_exchange_http_response(
            broker_id=request.broker_id,
            status_code=200,
            payload={
                "order": {
                    "order_id": "order-1",
                    "symbol": request.body["symbol"],
                    "side": request.body["side"],
                    "order_type": request.body["order_type"],
                    "quantity": request.body["quantity"],
                    "status": "accepted",
                    "price": request.body.get("price", 0),
                    "client_order_id": request.body.get("client_order_id", ""),
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
            elapsed_ms=12.5,
        )

    if request.method == ExchangeHttpMethod.DELETE and "/orders/" in request.url:
        return build_exchange_http_response(
            broker_id=request.broker_id,
            status_code=200,
            payload={
                "order": {
                    "order_id": "order-1",
                    "symbol": "XAUUSD",
                    "side": "buy",
                    "order_type": "market",
                    "quantity": 1,
                    "status": "cancelled",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "updated_at": "2026-01-01T00:01:00+00:00",
                }
            },
        )

    if request.url.endswith("/account"):
        return build_exchange_http_response(
            broker_id=request.broker_id,
            status_code=200,
            payload={
                "account": {
                    "account_id": "account-1",
                    "currency": "USD",
                    "cash_balance": 100000,
                    "equity": 101000,
                    "buying_power": 90000,
                    "margin_used": 1000,
                    "realized_pnl": 500,
                    "unrealized_pnl": 500,
                    "updated_at": "2026-01-01T00:00:00+00:00",
                }
            },
        )

    if request.url.endswith("/positions"):
        return build_exchange_http_response(
            broker_id=request.broker_id,
            status_code=200,
            payload={
                "positions": [
                    {
                        "position_id": "exchange-1-position-XAUUSD",
                        "symbol": "XAUUSD",
                        "side": "long",
                        "quantity": 2,
                        "average_price": 2000,
                        "market_price": 2010,
                        "fees": 1,
                        "opened_at": "2026-01-01T00:00:00+00:00",
                        "updated_at": "2026-01-01T00:00:00+00:00",
                    }
                ]
            },
        )

    if request.url.endswith("/trades/trade-1"):
        return build_exchange_http_response(
            broker_id=request.broker_id,
            status_code=200,
            payload={
                "trade": {
                    "trade_id": "trade-1",
                    "order_id": "order-1",
                    "symbol": "XAUUSD",
                    "side": "buy",
                    "quantity": 1,
                    "price": 2000,
                    "fee": 1,
                    "status": "open",
                    "executed_at": "2026-01-01T00:00:00+00:00",
                }
            },
        )

    return build_exchange_http_response(
        broker_id=request.broker_id,
        status_code=404,
        payload={
            "error": "not found",
        },
    )


def failing_transport(request: ExchangeHttpRequest) -> ExchangeHttpResponse:
    return build_exchange_http_response(
        broker_id=request.broker_id,
        status_code=500,
        payload={
            "error": "failed",
        },
    )


def build_adapter(transport=fake_transport):
    return build_exchange_http_broker_adapter(
        broker_id="exchange-1",
        base_url="https://example.com/api",
        transport=transport,
    )


def test_exchange_http_method_normalizer():
    assert ExchangeHttpMethod.GET.value == "GET"
    assert ExchangeHttpMethod.POST.value == "POST"
    assert ExchangeHttpMethod.DELETE.value == "DELETE"

    assert normalize_exchange_http_method(ExchangeHttpMethod.GET) == ExchangeHttpMethod.GET
    assert normalize_exchange_http_method(" post ") == ExchangeHttpMethod.POST

    with pytest.raises(ValueError):
        normalize_exchange_http_method("PATCH")


def test_exchange_http_validators():
    assert validate_exchange_http_url("https://example.com") == "https://example.com"
    assert validate_exchange_http_status_code(200) == 200
    assert validate_exchange_http_params({"symbol": "XAUUSD"}) == {"symbol": "XAUUSD"}
    assert validate_exchange_http_headers({"Accept": "application/json"}) == {"Accept": "application/json"}

    assert is_success_exchange_http_status(200) is True
    assert is_success_exchange_http_status(299) is True
    assert is_success_exchange_http_status(300) is False

    with pytest.raises(ValueError):
        validate_exchange_http_url("bad")

    with pytest.raises(ValueError):
        validate_exchange_http_status_code(99)

    with pytest.raises(ValueError):
        validate_exchange_http_status_code(600)

    with pytest.raises(ValueError):
        validate_exchange_http_status_code(True)

    with pytest.raises(ValueError):
        validate_exchange_http_params([])

    with pytest.raises(ValueError):
        validate_exchange_http_params({"": "bad"})

    with pytest.raises(ValueError):
        validate_exchange_http_headers([])

    with pytest.raises(ValueError):
        validate_exchange_http_headers({"": "bad"})

    with pytest.raises(ValueError):
        validate_exchange_http_headers({"Accept": 123})


def test_join_exchange_http_url():
    assert join_exchange_http_url("https://example.com/api", "/orders") == "https://example.com/api/orders"
    assert join_exchange_http_url("https://example.com/api/", "orders") == "https://example.com/api/orders"
    assert join_exchange_http_url("https://example.com", "https://other.com/orders") == "https://other.com/orders"

    with pytest.raises(ValueError):
        join_exchange_http_url("bad", "/orders")

    with pytest.raises(ValueError):
        join_exchange_http_url("https://example.com", "")


def test_exchange_http_request_to_dict():
    request = ExchangeHttpRequest(
        broker_id=" exchange-1 ",
        method=" get ",
        url="https://example.com/orders",
        params={
            "symbol": "XAUUSD",
            "empty": "",
        },
        headers={
            "Accept": "application/json",
        },
        timeout_seconds=10,
        metadata={
            "source": "test",
        },
    )

    payload = request.to_dict()

    assert payload["broker_id"] == "exchange-1"
    assert payload["method"] == "GET"
    assert payload["resolved_url"] == "https://example.com/orders?symbol=XAUUSD"
    assert payload["timeout_seconds"] == 10.0


def test_exchange_http_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="", method="GET", url="https://example.com")

    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="exchange-1", method="BAD", url="https://example.com")

    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="exchange-1", method="GET", url="bad")

    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="exchange-1", method="GET", url="https://example.com", params=[])

    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="exchange-1", method="GET", url="https://example.com", headers=[])

    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="exchange-1", method="GET", url="https://example.com", body=[])

    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="exchange-1", method="GET", url="https://example.com", timeout_seconds=0)

    with pytest.raises(ValueError):
        ExchangeHttpRequest(broker_id="exchange-1", method="GET", url="https://example.com", metadata=[])


def test_build_exchange_http_request():
    request = build_exchange_http_request(
        broker_id="exchange-1",
        method="GET",
        url="https://example.com",
    )

    assert isinstance(request, ExchangeHttpRequest)


def test_exchange_http_response_to_dict():
    response = ExchangeHttpResponse(
        broker_id=" exchange-1 ",
        status_code=200,
        payload={
            "ok": True,
        },
        headers={
            "Content-Type": "application/json",
        },
        elapsed_ms=12.5,
        metadata={
            "source": "test",
        },
    )

    assert response.success is True
    assert response.failed is False
    assert response.to_dict()["broker_id"] == "exchange-1"
    assert response.to_dict()["status_code"] == 200
    assert response.to_dict()["payload"] == {
        "ok": True,
    }


def test_exchange_http_response_rejects_invalid_values():
    with pytest.raises(ValueError):
        ExchangeHttpResponse(broker_id="", status_code=200, payload={})

    with pytest.raises(ValueError):
        ExchangeHttpResponse(broker_id="exchange-1", status_code=99, payload={})

    with pytest.raises(ValueError):
        ExchangeHttpResponse(broker_id="exchange-1", status_code=200, payload="bad")

    with pytest.raises(ValueError):
        ExchangeHttpResponse(broker_id="exchange-1", status_code=200, payload={}, headers=[])

    with pytest.raises(ValueError):
        ExchangeHttpResponse(broker_id="exchange-1", status_code=200, payload={}, elapsed_ms=-1)

    with pytest.raises(ValueError):
        ExchangeHttpResponse(broker_id="exchange-1", status_code=200, payload={}, metadata=[])


def test_validate_exchange_http_broker_config():
    config = build_broker_config(
        broker_id="exchange-1",
        name="Exchange",
        broker_type="exchange",
        base_url="https://example.com",
        capabilities=["live_trading"],
        paper_mode=False,
    )

    assert validate_exchange_http_broker_config(config) == config

    with pytest.raises(ValueError):
        validate_exchange_http_broker_config("bad")

    with pytest.raises(ValueError):
        validate_exchange_http_broker_config(
            build_broker_config(
                broker_id="bad",
                name="Bad",
                broker_type="paper",
                base_url="https://example.com",
                capabilities=["live_trading"],
                paper_mode=False,
            )
        )

    with pytest.raises(ValueError):
        validate_exchange_http_broker_config(
            build_broker_config(
                broker_id="bad",
                name="Bad",
                broker_type="exchange",
                base_url="https://example.com",
                capabilities=["live_trading"],
                paper_mode=True,
            )
        )

    with pytest.raises(ValueError):
        validate_exchange_http_broker_config(
            build_broker_config(
                broker_id="bad",
                name="Bad",
                broker_type="exchange",
                base_url="bad",
                capabilities=["live_trading"],
                paper_mode=False,
            )
        )

    with pytest.raises(ValueError):
        validate_exchange_http_broker_config(
            build_broker_config(
                broker_id="bad",
                name="Bad",
                broker_type="exchange",
                base_url="https://example.com",
                capabilities=["trade_history"],
                paper_mode=False,
            )
        )


def test_build_exchange_http_broker_adapter():
    adapter = build_adapter()

    assert isinstance(adapter, ExchangeHttpBrokerAdapter)
    assert adapter.broker_id == "exchange-1"
    assert adapter.base_url == "https://example.com/api"
    assert adapter.active is True


def test_exchange_http_broker_adapter_rejects_invalid_values():
    config = build_broker_config(
        broker_id="exchange-1",
        name="Exchange",
        broker_type="exchange",
        base_url="https://example.com",
        capabilities=["live_trading"],
        paper_mode=False,
    )

    with pytest.raises(ValueError):
        ExchangeHttpBrokerAdapter(broker_config="bad")

    with pytest.raises(ValueError):
        ExchangeHttpBrokerAdapter(broker_config=config, transport="bad")

    with pytest.raises(ValueError):
        ExchangeHttpBrokerAdapter(broker_config=config, metadata=[])


def test_exchange_http_broker_request():
    adapter = build_adapter()
    request = build_exchange_http_request(
        broker_id="exchange-1",
        method="GET",
        url="https://example.com/api/account",
    )

    response = adapter.request(request)

    assert response.success is True
    assert response.payload["account"]["account_id"] == "account-1"

    wrong_request = build_exchange_http_request(
        broker_id="other",
        method="GET",
        url="https://example.com/api/account",
    )

    with pytest.raises(ValueError):
        adapter.request("bad")

    with pytest.raises(ValueError):
        adapter.request(wrong_request)


def test_json_payload_to_broker_order():
    request = build_broker_order_request(
        broker_id="exchange-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    order = json_payload_to_broker_order(
        broker_id="exchange-1",
        payload={
            "order": {
                "order_id": "order-1",
                "status": "accepted",
            }
        },
        fallback_request=request,
    )

    direct_order = json_payload_to_broker_order(
        broker_id="exchange-1",
        payload={
            "id": "order-2",
            "s": "XAUUSD",
            "side": "buy",
            "type": "market",
            "qty": 1,
        },
        order_key="",
        field_map={
            "order_id": "id",
            "symbol": "s",
            "order_type": "type",
            "quantity": "qty",
        },
    )

    assert isinstance(order, BrokerOrder)
    assert order.order_id == "order-1"
    assert order.symbol == "XAUUSD"
    assert direct_order.order_id == "order-2"

    with pytest.raises(ValueError):
        json_payload_to_broker_order(broker_id="", payload={})

    with pytest.raises(ValueError):
        json_payload_to_broker_order(broker_id="exchange-1", payload=[])

    with pytest.raises(ValueError):
        json_payload_to_broker_order(broker_id="exchange-1", payload={}, fallback_request="bad")

    with pytest.raises(KeyError):
        json_payload_to_broker_order(broker_id="exchange-1", payload={})


def test_json_payload_to_broker_trade():
    trade = json_payload_to_broker_trade(
        broker_id="exchange-1",
        payload={
            "trade": {
                "trade_id": "trade-1",
                "order_id": "order-1",
                "symbol": "XAUUSD",
                "side": "buy",
                "quantity": 1,
                "price": 2000,
                "fee": 1,
            }
        },
    )

    assert isinstance(trade, BrokerTrade)
    assert trade.trade_id == "trade-1"
    assert trade.notional == 2000.0

    with pytest.raises(ValueError):
        json_payload_to_broker_trade(broker_id="", payload={})

    with pytest.raises(ValueError):
        json_payload_to_broker_trade(broker_id="exchange-1", payload=[])

    with pytest.raises(KeyError):
        json_payload_to_broker_trade(broker_id="exchange-1", payload={})


def test_json_payload_to_broker_account():
    account = json_payload_to_broker_account(
        broker_id="exchange-1",
        payload={
            "account": {
                "account_id": "account-1",
                "currency": "USD",
                "cash_balance": 100000,
            }
        },
    )

    assert isinstance(account, BrokerAccount)
    assert account.account_id == "account-1"
    assert account.equity == 100000

    with pytest.raises(ValueError):
        json_payload_to_broker_account(broker_id="", payload={})

    with pytest.raises(ValueError):
        json_payload_to_broker_account(broker_id="exchange-1", payload=[])

    with pytest.raises(KeyError):
        json_payload_to_broker_account(broker_id="exchange-1", payload={})


def test_json_payload_to_broker_position_and_positions():
    position = json_payload_to_broker_position(
        broker_id="exchange-1",
        payload={
            "symbol": "XAUUSD",
            "side": "long",
            "quantity": 2,
            "average_price": 2000,
            "market_price": 2010,
        },
    )
    positions = json_payload_to_broker_positions(
        broker_id="exchange-1",
        payload={
            "positions": [
                {
                    "symbol": "XAUUSD",
                    "side": "long",
                    "quantity": 2,
                    "average_price": 2000,
                    "market_price": 2010,
                }
            ]
        },
    )

    assert isinstance(position, BrokerPosition)
    assert position.position_id == "exchange-1-position-XAUUSD"
    assert len(positions) == 1
    assert positions[0].market_value == 4020.0

    with pytest.raises(ValueError):
        json_payload_to_broker_position(broker_id="", payload={})

    with pytest.raises(ValueError):
        json_payload_to_broker_position(broker_id="exchange-1", payload=[])

    with pytest.raises(ValueError):
        json_payload_to_broker_positions(broker_id="exchange-1", payload={"positions": {}})

    with pytest.raises(KeyError):
        json_payload_to_broker_position(broker_id="exchange-1", payload={})


def test_submit_order_success():
    adapter = build_adapter()
    request = build_broker_order_request(
        broker_id="exchange-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
        client_order_id="client-1",
    )

    result = adapter.submit_order(request)

    assert result.success is True
    assert result.data["order"]["order_id"] == "order-1"
    assert result.data["order"]["status"] == "accepted"
    assert result.data["order"]["client_order_id"] == "client-1"


def test_submit_order_helper():
    adapter = build_adapter()
    request = build_broker_order_request(
        broker_id="exchange-1",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    result = submit_exchange_http_order(
        adapter=adapter,
        request=request,
    )

    assert result.success is True

    with pytest.raises(ValueError):
        submit_exchange_http_order(adapter="bad", request=request)


def test_cancel_order_success_and_helper():
    adapter = build_adapter()

    result = adapter.cancel_order(order_id="order-1")
    helper_result = cancel_exchange_http_order(
        adapter=adapter,
        order_id="order-1",
    )

    assert result.success is True
    assert result.data["order"]["status"] == "cancelled"
    assert helper_result.success is True

    with pytest.raises(ValueError):
        cancel_exchange_http_order(adapter="bad", order_id="order-1")


def test_fetch_account_success_and_helper():
    adapter = build_adapter()

    result = adapter.fetch_account()
    helper_result = fetch_exchange_http_account(adapter=adapter)

    assert result.success is True
    assert result.data["account"]["account_id"] == "account-1"
    assert result.data["account"]["total_pnl"] == 1000.0
    assert helper_result.success is True

    with pytest.raises(ValueError):
        fetch_exchange_http_account(adapter="bad")


def test_fetch_positions_success_and_helper():
    adapter = build_adapter()

    result = adapter.fetch_positions()
    helper_result = fetch_exchange_http_positions(adapter=adapter)

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["positions"][0]["symbol"] == "XAUUSD"
    assert helper_result.success is True

    with pytest.raises(ValueError):
        fetch_exchange_http_positions(adapter="bad")


def test_fetch_trade_success():
    adapter = build_adapter()

    result = adapter.fetch_trade(trade_id="trade-1")

    assert result.success is True
    assert result.data["trade"]["trade_id"] == "trade-1"
    assert result.data["trade"]["notional"] == 2000.0


def test_exchange_http_failures():
    adapter = build_adapter()
    wrong_request = build_broker_order_request(
        broker_id="other",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )

    wrong_result = adapter.submit_order(wrong_request)

    inactive_adapter = build_exchange_http_broker_adapter(
        broker_config=build_broker_config(
            broker_id="inactive",
            name="Inactive",
            broker_type="exchange",
            base_url="https://example.com",
            status=BrokerStatus.INACTIVE,
            capabilities=["live_trading", "market_orders"],
            paper_mode=False,
        ),
        transport=fake_transport,
    )
    inactive_request = build_broker_order_request(
        broker_id="inactive",
        symbol="XAUUSD",
        side="buy",
        order_type="market",
        quantity=1,
    )
    inactive_submit = inactive_adapter.submit_order(inactive_request)
    inactive_cancel = inactive_adapter.cancel_order(order_id="order-1")

    no_order_capability_adapter = build_exchange_http_broker_adapter(
        broker_config=build_broker_config(
            broker_id="no-orders",
            name="No Orders",
            broker_type="exchange",
            base_url="https://example.com",
            capabilities=["account_info"],
            paper_mode=False,
        ),
        transport=fake_transport,
    )
    no_order_result = no_order_capability_adapter.submit_order(
        build_broker_order_request(
            broker_id="no-orders",
            symbol="XAUUSD",
            side="buy",
            order_type="market",
            quantity=1,
        )
    )

    no_account_capability_adapter = build_exchange_http_broker_adapter(
        broker_config=build_broker_config(
            broker_id="no-account",
            name="No Account",
            broker_type="exchange",
            base_url="https://example.com",
            capabilities=["live_trading"],
            paper_mode=False,
        ),
        transport=fake_transport,
    )
    no_account_result = no_account_capability_adapter.fetch_account()
    no_positions_result = no_account_capability_adapter.fetch_positions()

    failing_adapter = build_adapter(transport=failing_transport)
    failing_submit = failing_adapter.submit_order(
        build_broker_order_request(
            broker_id="exchange-1",
            symbol="XAUUSD",
            side="buy",
            order_type="market",
            quantity=1,
        )
    )
    failing_cancel = failing_adapter.cancel_order(order_id="order-1")
    failing_account = failing_adapter.fetch_account()
    failing_positions = failing_adapter.fetch_positions()
    failing_trade = failing_adapter.fetch_trade(trade_id="trade-1")

    assert wrong_result.success is False
    assert inactive_submit.success is False
    assert inactive_cancel.success is False
    assert no_order_result.success is False
    assert no_account_result.success is False
    assert no_positions_result.success is False
    assert failing_submit.success is False
    assert failing_submit.metadata["status_code"] == 500
    assert failing_cancel.success is False
    assert failing_account.success is False
    assert failing_positions.success is False
    assert failing_trade.success is False

    with pytest.raises(ValueError):
        adapter.submit_order("bad")


def test_exchange_http_error_result():
    result = exchange_http_error_result(
        broker_id="exchange-1",
        error="failed",
        operation="submit_order",
    )

    assert result.success is False
    assert result.error == "failed"
    assert result.metadata["broker_type"] == "exchange_http"
    assert result.metadata["operation"] == "submit_order"


def test_exchange_http_exports_exist():
    import aqos.brokers as brokers

    expected_exports = [
        "ExchangeHttpBrokerAdapter",
        "ExchangeHttpMethod",
        "ExchangeHttpRequest",
        "ExchangeHttpResponse",
        "build_exchange_http_broker_adapter",
        "build_exchange_http_request",
        "build_exchange_http_response",
        "cancel_exchange_http_order",
        "default_exchange_http_transport",
        "exchange_http_error_result",
        "fetch_exchange_http_account",
        "fetch_exchange_http_positions",
        "is_success_exchange_http_status",
        "join_exchange_http_url",
        "json_payload_to_broker_account",
        "json_payload_to_broker_order",
        "json_payload_to_broker_position",
        "json_payload_to_broker_positions",
        "json_payload_to_broker_trade",
        "normalize_exchange_http_method",
        "submit_exchange_http_order",
        "validate_exchange_http_broker_config",
        "validate_exchange_http_headers",
        "validate_exchange_http_params",
        "validate_exchange_http_status_code",
        "validate_exchange_http_url",
    ]

    for export_name in expected_exports:
        assert hasattr(brokers, export_name), export_name