"""
Unit tests for AQOS API execution operations.
"""

from types import SimpleNamespace

import pytest

from aqos.api import (
    ClosePositionRequest,
    ExecutionOrderRequest,
    ExecutionTradeRequest,
    FillOrderRequest,
    OrderIdRequest,
    api_cancel_order,
    api_close_position,
    api_execute_trade,
    api_execution_summary,
    api_fill_order,
    api_order_status,
    api_place_order,
    build_execution_trade_request,
    execution_agent_operation,
    normalize_execution_trade,
)


class SuccessfulExecutionAgent:
    name = "execution-agent"

    def __init__(self):
        self.calls = []

    def execute(self, action, payload=None, metadata=None):
        payload = payload or {}
        trade = payload.get("trade", {})

        self.calls.append(
            {
                "action": action,
                "payload": payload,
                "metadata": metadata,
            }
        )

        data_by_action = {
            "execute-trade": {
                "symbol": trade.get("symbol"),
                "side": trade.get("side"),
                "quantity": trade.get("position_size"),
                "price": trade.get("entry_price"),
                "status": "open",
                "order_id": "order-1",
            },
            "place-order": {
                "order_id": payload.get("order_id"),
                "symbol": payload.get("symbol"),
                "side": payload.get("side"),
                "quantity": payload.get("quantity"),
                "price": payload.get("price"),
                "status": "open",
            },
            "fill-order": {
                "order_id": payload.get("order_id"),
                "fill_price": payload.get("fill_price"),
                "status": "filled",
                "position_id": "position-1",
            },
            "cancel-order": {
                "order_id": payload.get("order_id"),
                "status": "cancelled",
            },
            "order-status": {
                "order_id": payload.get("order_id"),
                "status": "open",
            },
            "close-position": {
                "position_id": payload.get("position_id"),
                "close_price": payload.get("close_price"),
                "status": "closed",
                "profit": 100.0,
            },
            "execution-summary": {
                "orders": 1,
                "positions": 0,
                "open_positions": 0,
            },
        }

        return SimpleNamespace(
            success=True,
            message=f"{action} completed.",
            data=data_by_action[action],
            metadata={
                "source": "unit-test",
            },
        )


class FailingExecutionAgent:
    name = "execution-agent"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Execution agent failed.",
            data={
                "reason": "order rejected",
            },
            metadata={},
        )


class BrokenExecutionAgent:
    name = "broken-execution-agent"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Execution agent exploded.")


def sample_execution_trade():
    return {
        "symbol": "xauusd",
        "side": "buy",
        "allowed": True,
        "reason": "Trade allowed.",
        "position_size": 10.0,
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "risk_amount": 100.0,
        "risk_percent": 0.01,
        "execution_ready": True,
    }


def test_execution_trade_request_defaults():
    request = ExecutionTradeRequest()

    assert request.to_trade() == {
        "symbol": "XAUUSD",
        "side": "buy",
        "allowed": True,
        "reason": "Trade allowed.",
        "position_size": 10.0,
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "risk_amount": 100.0,
        "risk_percent": 0.01,
        "execution_ready": True,
    }


def test_execution_trade_request_normalizes_values():
    request = ExecutionTradeRequest(
        symbol="xauusd",
        side="BUY",
        allowed=True,
        reason=" Trade allowed. ",
        position_size=10.0,
        entry_price=2025.0,
        stop_loss_price=2015.0,
        risk_amount=100.0,
        risk_percent=0.01,
        execution_ready=True,
    )

    assert request.to_payload() == {
        "trade": {
            "symbol": "XAUUSD",
            "side": "buy",
            "allowed": True,
            "reason": "Trade allowed.",
            "position_size": 10.0,
            "entry_price": 2025.0,
            "stop_loss_price": 2015.0,
            "risk_amount": 100.0,
            "risk_percent": 0.01,
            "execution_ready": True,
        }
    }


def test_execution_trade_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ExecutionTradeRequest(symbol="")

    with pytest.raises(ValueError):
        ExecutionTradeRequest(side="hold")

    with pytest.raises(ValueError):
        ExecutionTradeRequest(position_size=0)

    with pytest.raises(ValueError):
        ExecutionTradeRequest(entry_price=0)

    with pytest.raises(ValueError):
        ExecutionTradeRequest(stop_loss_price=0)

    with pytest.raises(ValueError):
        ExecutionTradeRequest(risk_amount=0)

    with pytest.raises(ValueError):
        ExecutionTradeRequest(risk_percent=0)

    with pytest.raises(ValueError):
        ExecutionTradeRequest(reason="")


def test_execution_order_request_to_order():
    request = ExecutionOrderRequest(
        order_id="order-1",
        symbol="xauusd",
        side="BUY",
        quantity=10.0,
        price=2025.0,
    )

    assert request.to_order() == {
        "order_id": "order-1",
        "symbol": "XAUUSD",
        "side": "buy",
        "quantity": 10.0,
        "price": 2025.0,
    }


def test_execution_order_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ExecutionOrderRequest(order_id="")

    with pytest.raises(ValueError):
        ExecutionOrderRequest(order_id="order-1", quantity=0)

    with pytest.raises(ValueError):
        ExecutionOrderRequest(order_id="order-1", price=0)


def test_fill_order_request_to_payload():
    request = FillOrderRequest(
        order_id="order-1",
        fill_price=2025.0,
    )

    assert request.to_payload() == {
        "order_id": "order-1",
        "fill_price": 2025.0,
    }


def test_order_id_request_to_payload():
    request = OrderIdRequest(order_id="order-1")

    assert request.to_payload() == {
        "order_id": "order-1",
    }


def test_close_position_request_to_payload():
    request = ClosePositionRequest(
        position_id="position-1",
        close_price=2035.0,
    )

    assert request.to_payload() == {
        "position_id": "position-1",
        "close_price": 2035.0,
    }


def test_build_execution_trade_request():
    request = build_execution_trade_request(
        symbol="xauusd",
        side="buy",
        position_size=10.0,
        entry_price=2025.0,
        stop_loss_price=2015.0,
        risk_amount=100.0,
        risk_percent=0.01,
    )

    assert isinstance(request, ExecutionTradeRequest)
    assert request.to_trade()["symbol"] == "XAUUSD"
    assert request.to_trade()["side"] == "buy"


def test_normalize_execution_trade_preserves_extra_fields():
    normalized = normalize_execution_trade(
        {
            **sample_execution_trade(),
            "strategy_id": "strategy-1",
        }
    )

    assert normalized["symbol"] == "XAUUSD"
    assert normalized["side"] == "buy"
    assert normalized["entry_price"] == 2025.0
    assert normalized["strategy_id"] == "strategy-1"


def test_normalize_execution_trade_rejects_non_dict():
    with pytest.raises(ValueError, match="Execution trade"):
        normalize_execution_trade("bad")


def test_execution_agent_operation_success():
    agent = SuccessfulExecutionAgent()

    response = execution_agent_operation(
        agent,
        action="execute-trade",
        payload={
            "trade": sample_execution_trade(),
        },
        success_message="Trade execution completed.",
        failure_message="Trade execution failed.",
        request_id="execution-request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trade execution completed."
    assert payload["data"]["action"] == "execute-trade"
    assert payload["data"]["agent"] == "execution-agent"
    assert payload["data"]["result"]["status"] == "open"
    assert payload["metadata"]["request_id"] == "execution-request-1"


def test_execution_agent_operation_failure():
    response = execution_agent_operation(
        FailingExecutionAgent(),
        action="execute-trade",
        payload={
            "trade": sample_execution_trade(),
        },
        success_message="Trade execution completed.",
        failure_message="Trade execution failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Trade execution failed."
    assert payload["errors"][0]["code"] == "EXECUTION_AGENT_ERROR"
    assert payload["errors"][0]["message"] == "Execution agent failed."
    assert payload["data"]["result"] == {
        "reason": "order rejected",
    }


def test_execution_agent_operation_exception():
    response = execution_agent_operation(
        BrokenExecutionAgent(),
        action="execute-trade",
        payload={
            "trade": sample_execution_trade(),
        },
        success_message="Trade execution completed.",
        failure_message="Trade execution failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Trade execution failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Execution agent exploded."


def test_api_execute_trade_success():
    agent = SuccessfulExecutionAgent()

    response = api_execute_trade(
        agent,
        trade=sample_execution_trade(),
        request_id="execute-trade-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trade execution completed."
    assert payload["data"]["action"] == "execute-trade"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["side"] == "buy"
    assert payload["data"]["result"]["status"] == "open"
    assert payload["metadata"]["request_id"] == "execute-trade-1"

    assert agent.calls[0]["payload"]["trade"]["symbol"] == "XAUUSD"


def test_api_execute_trade_validation_failure():
    response = api_execute_trade(
        SuccessfulExecutionAgent(),
        trade="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "trade"


def test_api_place_order_success():
    agent = SuccessfulExecutionAgent()

    response = api_place_order(
        agent,
        order_id="order-1",
        symbol="xauusd",
        side="buy",
        quantity=10.0,
        price=2025.0,
        request_id="place-order-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Order placed."
    assert payload["data"]["action"] == "place-order"
    assert payload["data"]["result"]["order_id"] == "order-1"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["status"] == "open"
    assert payload["metadata"]["request_id"] == "place-order-1"


def test_api_place_order_validation_failure():
    response = api_place_order(
        SuccessfulExecutionAgent(),
        order_id="",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "order"


def test_api_fill_order_success():
    response = api_fill_order(
        SuccessfulExecutionAgent(),
        order_id="order-1",
        fill_price=2025.0,
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Order filled."
    assert payload["data"]["action"] == "fill-order"
    assert payload["data"]["result"]["status"] == "filled"
    assert payload["data"]["result"]["position_id"] == "position-1"


def test_api_cancel_order_success():
    response = api_cancel_order(
        SuccessfulExecutionAgent(),
        order_id="order-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Order cancelled."
    assert payload["data"]["action"] == "cancel-order"
    assert payload["data"]["result"]["status"] == "cancelled"


def test_api_order_status_success():
    response = api_order_status(
        SuccessfulExecutionAgent(),
        order_id="order-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Order status loaded."
    assert payload["data"]["action"] == "order-status"
    assert payload["data"]["result"]["status"] == "open"


def test_api_close_position_success():
    response = api_close_position(
        SuccessfulExecutionAgent(),
        position_id="position-1",
        close_price=2035.0,
        request_id="close-position-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Position closed."
    assert payload["data"]["action"] == "close-position"
    assert payload["data"]["result"]["position_id"] == "position-1"
    assert payload["data"]["result"]["status"] == "closed"
    assert payload["metadata"]["request_id"] == "close-position-1"


def test_api_execution_summary_success():
    response = api_execution_summary(
        SuccessfulExecutionAgent(),
        request_id="execution-summary-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Execution summary loaded."
    assert payload["data"]["action"] == "execution-summary"
    assert payload["data"]["result"]["orders"] == 1
    assert payload["metadata"]["request_id"] == "execution-summary-1"