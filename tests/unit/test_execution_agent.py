"""
Unit tests for ExecutionAgent.
"""

from aqos.agents import (
    AgentBase,
    ExecutionAgent,
)
from aqos.services import BrokerService


def create_execution_agent() -> ExecutionAgent:
    return ExecutionAgent(
        broker_service=BrokerService(),
    )


def valid_trade_handoff() -> dict:
    return {
        "order_id": "order-1",
        "symbol": "XAUUSD",
        "side": "buy",
        "allowed": True,
        "execution_ready": True,
        "reason": "Trade allowed.",
        "position_size": 10.0,
        "entry_price": 2000.0,
        "stop_loss_price": 1990.0,
        "risk_amount": 100.0,
        "risk_percent": 0.01,
    }


def test_execution_agent_is_agent_base_instance():
    agent = ExecutionAgent()

    assert isinstance(agent, AgentBase)


def test_execution_agent_name():
    agent = ExecutionAgent()

    assert agent.name == "execution-agent"


def test_execution_agent_description():
    agent = ExecutionAgent()

    assert agent.description == (
        "Agent for simulated order execution, fills, cancellations, and positions."
    )


def test_available_actions():
    agent = ExecutionAgent()

    assert agent.available_actions() == [
        "cancel-order",
        "close-position",
        "execute-trade",
        "execution-summary",
        "fill-order",
        "health",
        "order-status",
        "place-order",
    ]


def test_health():
    agent = create_execution_agent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Execution agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["orders"] == 0
    assert result.data["positions"] == 0
    assert result.data["supported_sides"] == [
        "buy",
        "sell",
    ]
    assert result.data["supported_order_types"] == [
        "limit",
        "market",
        "stop",
    ]


def test_place_order():
    agent = create_execution_agent()

    result = agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
            "order_type": "market",
            "price": 2000.0,
            "metadata": {
                "source": "test",
            },
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Order placed."
    assert result.data["order_id"] == "order-1"
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["side"] == "buy"
    assert result.data["quantity"] == 1.0
    assert result.data["order_type"] == "market"
    assert result.data["status"] == "open"
    assert result.data["price"] == 2000.0
    assert result.data["metadata"]["source"] == "test"
    assert result.data["metadata"]["request_id"] == "req-1"
    assert result.metadata["request_id"] == "req-1"


def test_place_order_defaults_order_type():
    agent = create_execution_agent()

    result = agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
        },
    )

    assert result.success is True
    assert result.data["order_type"] == "market"


def test_place_order_missing_order_id():
    agent = create_execution_agent()

    result = agent.execute(
        action="place-order",
        payload={
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: order_id"


def test_place_order_rejects_invalid_side():
    agent = create_execution_agent()

    result = agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "hold",
            "quantity": 1.0,
        },
    )

    assert result.success is False
    assert result.message == "Side must be buy or sell."


def test_place_order_rejects_invalid_quantity():
    agent = create_execution_agent()

    result = agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 0,
        },
    )

    assert result.success is False
    assert result.message == "Quantity must be greater than zero."


def test_place_order_rejects_invalid_order_type():
    agent = create_execution_agent()

    result = agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
            "order_type": "invalid",
        },
    )

    assert result.success is False
    assert result.message == "Order type must be market, limit, or stop."


def test_execute_trade_places_order():
    agent = create_execution_agent()

    result = agent.execute(
        action="execute-trade",
        payload={
            "trade": valid_trade_handoff(),
        },
    )

    assert result.success is True
    assert result.message == "Trade execution order placed."
    assert result.data["order_id"] == "order-1"
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["side"] == "buy"
    assert result.data["quantity"] == 10.0
    assert result.data["status"] == "open"


def test_execute_trade_generates_default_order_id():
    agent = create_execution_agent()

    trade = valid_trade_handoff()
    trade.pop("order_id")

    result = agent.execute(
        action="execute-trade",
        payload={
            "trade": trade,
        },
    )

    assert result.success is True
    assert result.data["order_id"] == "order-1"


def test_execute_trade_rejects_not_ready_trade():
    agent = create_execution_agent()

    trade = valid_trade_handoff()
    trade["allowed"] = False
    trade["execution_ready"] = False
    trade["reason"] = "Risk percent exceeds maximum allowed risk percent."

    result = agent.execute(
        action="execute-trade",
        payload={
            "trade": trade,
        },
    )

    assert result.success is False
    assert result.message == "Risk percent exceeds maximum allowed risk percent."
    assert result.data["allowed"] is False
    assert result.data["execution_ready"] is False


def test_execute_trade_missing_trade():
    agent = create_execution_agent()

    result = agent.execute(
        action="execute-trade",
        payload={},
    )

    assert result.success is False
    assert result.message == "Missing required payload key: trade"


def test_execute_trade_rejects_invalid_trade_type():
    agent = create_execution_agent()

    result = agent.execute(
        action="execute-trade",
        payload={
            "trade": "invalid",
        },
    )

    assert result.success is False
    assert result.message == "Trade must be a dictionary."


def test_fill_order():
    agent = create_execution_agent()

    agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
        },
    )

    result = agent.execute(
        action="fill-order",
        payload={
            "order_id": "order-1",
            "fill_price": 2000.0,
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Order filled."
    assert result.data["position_id"] == "position-order-1"
    assert result.data["order_id"] == "order-1"
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["side"] == "buy"
    assert result.data["quantity"] == 1.0
    assert result.data["entry_price"] == 2000.0
    assert result.data["status"] == "open"
    assert result.metadata["request_id"] == "req-1"


def test_fill_order_missing_order():
    agent = create_execution_agent()

    result = agent.execute(
        action="fill-order",
        payload={
            "order_id": "missing",
            "fill_price": 2000.0,
        },
    )

    assert result.success is False
    assert result.message == "Order does not exist."


def test_fill_order_rejects_invalid_fill_price():
    agent = create_execution_agent()

    result = agent.execute(
        action="fill-order",
        payload={
            "order_id": "order-1",
            "fill_price": 0,
        },
    )

    assert result.success is False
    assert result.message == "Fill price must be greater than zero."


def test_cancel_order():
    agent = create_execution_agent()

    agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
        },
    )

    result = agent.execute(
        action="cancel-order",
        payload={
            "order_id": "order-1",
        },
    )

    assert result.success is True
    assert result.message == "Order cancelled."
    assert result.data["order_id"] == "order-1"
    assert result.data["status"] == "cancelled"


def test_cancel_order_missing_order():
    agent = create_execution_agent()

    result = agent.execute(
        action="cancel-order",
        payload={
            "order_id": "missing",
        },
    )

    assert result.success is False
    assert result.message == "Order does not exist."


def test_close_position():
    agent = create_execution_agent()

    agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
        },
    )
    agent.execute(
        action="fill-order",
        payload={
            "order_id": "order-1",
            "fill_price": 2000.0,
        },
    )

    result = agent.execute(
        action="close-position",
        payload={
            "position_id": "position-order-1",
            "exit_price": 2010.0,
        },
    )

    assert result.success is True
    assert result.message == "Position closed."
    assert result.data["position_id"] == "position-order-1"
    assert result.data["status"] == "closed"
    assert result.data["exit_price"] == 2010.0
    assert result.data["profit"] == 10.0


def test_close_short_position_profit():
    agent = create_execution_agent()

    agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "sell",
            "quantity": 1.0,
        },
    )
    agent.execute(
        action="fill-order",
        payload={
            "order_id": "order-1",
            "fill_price": 2000.0,
        },
    )

    result = agent.execute(
        action="close-position",
        payload={
            "position_id": "position-order-1",
            "exit_price": 1990.0,
        },
    )

    assert result.success is True
    assert result.data["profit"] == 10.0


def test_close_position_missing_position():
    agent = create_execution_agent()

    result = agent.execute(
        action="close-position",
        payload={
            "position_id": "missing",
            "exit_price": 2010.0,
        },
    )

    assert result.success is False
    assert result.message == "Position does not exist."


def test_close_position_rejects_invalid_exit_price():
    agent = create_execution_agent()

    result = agent.execute(
        action="close-position",
        payload={
            "position_id": "position-1",
            "exit_price": 0,
        },
    )

    assert result.success is False
    assert result.message == "Exit price must be greater than zero."


def test_order_status():
    agent = create_execution_agent()

    agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
        },
    )

    result = agent.execute(
        action="order-status",
        payload={
            "order_id": "order-1",
        },
    )

    assert result.success is True
    assert result.message == "Order status retrieved."
    assert result.data["order_id"] == "order-1"
    assert result.data["status"] == "open"


def test_order_status_missing_order():
    agent = create_execution_agent()

    result = agent.execute(
        action="order-status",
        payload={
            "order_id": "missing",
        },
    )

    assert result.success is False
    assert result.message == "Order does not exist."


def test_execution_summary():
    agent = create_execution_agent()

    agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 1.0,
        },
    )
    agent.execute(
        action="fill-order",
        payload={
            "order_id": "order-1",
            "fill_price": 2000.0,
        },
    )
    agent.execute(
        action="close-position",
        payload={
            "position_id": "position-order-1",
            "exit_price": 2010.0,
        },
    )

    result = agent.execute("execution-summary")

    assert result.success is True
    assert result.message == "Execution summary generated."
    assert result.data["orders"] == 1
    assert result.data["positions"] == 1
    assert result.data["open_orders"] == 0
    assert result.data["filled_orders"] == 1
    assert result.data["cancelled_orders"] == 0
    assert result.data["open_positions"] == 0
    assert result.data["closed_positions"] == 1
    assert result.data["realized_profit"] == 10.0


def test_unsupported_action():
    agent = ExecutionAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"