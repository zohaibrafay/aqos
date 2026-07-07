"""
Unit tests for AQOS CLI execution commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliClosePositionRequest,
    CliExecutionOrderRequest,
    CliExecutionSummaryRequest,
    CliExecutionTradeRequest,
    CliFillOrderRequest,
    CliOrderIdRequest,
    build_execution_cli_output,
    cli_cancel_order,
    cli_close_position,
    cli_execute_trade,
    cli_execution_summary,
    cli_fill_order,
    cli_order_status,
    cli_place_order,
    execute_execution_operation,
)


def sample_execution_trade():
    return {
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


def sample_order():
    return {
        "order_id": "order-1",
        "symbol": "XAUUSD",
        "side": "buy",
        "quantity": 10.0,
        "price": 2025.0,
    }


def fake_execute_trade(agent, trade, request_id=None):
    return api_success(
        message="Trade execution completed.",
        data={
            "agent": agent.name,
            "symbol": trade["symbol"],
            "side": trade["side"],
            "quantity": trade["position_size"],
            "price": trade["entry_price"],
            "status": "open",
            "order_id": "order-1",
        },
        request_id=request_id,
    )


def fake_place_order(
    agent,
    order_id,
    symbol="XAUUSD",
    side="buy",
    quantity=10.0,
    price=2025.0,
    request_id=None,
):
    return api_success(
        message="Order placed.",
        data={
            "agent": agent.name,
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": "open",
        },
        request_id=request_id,
    )


def fake_fill_order(agent, order_id, fill_price=2025.0, request_id=None):
    return api_success(
        message="Order filled.",
        data={
            "agent": agent.name,
            "order_id": order_id,
            "fill_price": fill_price,
            "status": "filled",
            "position_id": "position-1",
        },
        request_id=request_id,
    )


def fake_cancel_order(agent, order_id, request_id=None):
    return api_success(
        message="Order cancelled.",
        data={
            "agent": agent.name,
            "order_id": order_id,
            "status": "cancelled",
        },
        request_id=request_id,
    )


def fake_order_status(agent, order_id, request_id=None):
    return api_success(
        message="Order status loaded.",
        data={
            "agent": agent.name,
            "order_id": order_id,
            "status": "open",
        },
        request_id=request_id,
    )


def fake_close_position(agent, position_id, close_price=2035.0, request_id=None):
    return api_success(
        message="Position closed.",
        data={
            "agent": agent.name,
            "position_id": position_id,
            "close_price": close_price,
            "status": "closed",
            "profit": 100.0,
        },
        request_id=request_id,
    )


def fake_execution_summary(agent, request_id=None):
    return api_success(
        message="Execution summary loaded.",
        data={
            "agent": agent.name,
            "orders": 1,
            "positions": 0,
            "open_positions": 0,
        },
        request_id=request_id,
    )


def fake_failure_execution(agent, trade=None, request_id=None):
    return api_failure(
        message="Execution command failed.",
        data={
            "symbol": trade.get("symbol") if trade else "XAUUSD",
        },
        request_id=request_id,
    )


def test_cli_execution_trade_request_accepts_valid_values():
    agent = SimpleNamespace(name="execution-agent")

    request = CliExecutionTradeRequest(
        agent=agent,
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
        output_format="pretty-json",
        include_metadata=True,
        request_id="execution-request-1",
    )

    assert request.agent == agent
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "execution-request-1"
    assert request.to_trade() == sample_execution_trade()


def test_cli_execution_trade_request_rejects_invalid_values():
    agent = SimpleNamespace(name="execution-agent")

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=None)

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, symbol="")

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, side="hold")

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, position_size=0)

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, entry_price=0)

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, stop_loss_price=0)

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, risk_amount=0)

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, risk_percent=0)

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, reason="")

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, output_format="bad")

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, include_metadata="yes")

    with pytest.raises(ValueError):
        CliExecutionTradeRequest(agent=agent, request_id="")


def test_cli_execution_order_request_accepts_valid_values():
    agent = SimpleNamespace(name="execution-agent")

    request = CliExecutionOrderRequest(
        agent=agent,
        order_id="order-1",
        symbol="xauusd",
        side="BUY",
        quantity=10.0,
        price=2025.0,
    )

    assert request.to_order() == sample_order()


def test_cli_execution_order_request_rejects_invalid_values():
    agent = SimpleNamespace(name="execution-agent")

    with pytest.raises(ValueError):
        CliExecutionOrderRequest(agent=None, order_id="order-1")

    with pytest.raises(ValueError):
        CliExecutionOrderRequest(agent=agent, order_id="")

    with pytest.raises(ValueError):
        CliExecutionOrderRequest(agent=agent, order_id="order-1", quantity=0)

    with pytest.raises(ValueError):
        CliExecutionOrderRequest(agent=agent, order_id="order-1", price=0)


def test_cli_fill_order_request_to_payload():
    agent = SimpleNamespace(name="execution-agent")

    request = CliFillOrderRequest(
        agent=agent,
        order_id="order-1",
        fill_price=2025.0,
    )

    assert request.to_payload() == {
        "order_id": "order-1",
        "fill_price": 2025.0,
    }


def test_cli_order_id_request_to_payload():
    agent = SimpleNamespace(name="execution-agent")

    request = CliOrderIdRequest(
        agent=agent,
        order_id="order-1",
    )

    assert request.to_payload() == {
        "order_id": "order-1",
    }


def test_cli_close_position_request_to_payload():
    agent = SimpleNamespace(name="execution-agent")

    request = CliClosePositionRequest(
        agent=agent,
        position_id="position-1",
        close_price=2035.0,
    )

    assert request.to_payload() == {
        "position_id": "position-1",
        "close_price": 2035.0,
    }


def test_cli_execution_summary_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        CliExecutionSummaryRequest(agent=None)

    with pytest.raises(ValueError):
        CliExecutionSummaryRequest(
            agent=SimpleNamespace(name="execution-agent"),
            output_format="bad",
        )


def test_execute_execution_operation_with_request_id():
    agent = SimpleNamespace(name="execution-agent")

    response = execute_execution_operation(
        fake_execute_trade,
        agent=agent,
        trade=sample_execution_trade(),
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["agent"] == "execution-agent"


def test_execute_execution_operation_rejects_invalid_values():
    agent = SimpleNamespace(name="execution-agent")

    with pytest.raises(ValueError):
        execute_execution_operation(
            "not-callable",
            agent=agent,
        )

    with pytest.raises(ValueError):
        execute_execution_operation(
            fake_execute_trade,
            agent=None,
        )


def test_build_execution_cli_output_success():
    agent = SimpleNamespace(name="execution-agent")

    response = fake_execute_trade(
        agent,
        sample_execution_trade(),
        request_id="request-1",
    )

    cli_output = build_execution_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Trade execution completed." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_execution_cli_output_failure():
    agent = SimpleNamespace(name="execution-agent")

    response = fake_failure_execution(
        agent,
        sample_execution_trade(),
    )

    cli_output = build_execution_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Execution command failed."


def test_cli_execute_trade_text_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_execute_trade(
        agent=agent,
        symbol="xauusd",
        side="buy",
        output_format="text",
        request_id="execute-trade-1",
        operation=fake_execute_trade,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Trade execution completed." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "side: buy" in cli_output.output
    assert "status: open" in cli_output.output
    assert "order_id: order-1" in cli_output.output


def test_cli_execute_trade_json_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_execute_trade(
        agent=agent,
        symbol="xauusd",
        side="buy",
        output_format="json",
        operation=fake_execute_trade,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["symbol"] == "XAUUSD"
    assert payload["data"]["status"] == "open"
    assert "metadata" not in payload


def test_cli_execute_trade_validation_failure():
    agent = SimpleNamespace(name="execution-agent")

    with pytest.raises(ValueError):
        cli_execute_trade(
            agent=agent,
            symbol="",
            operation=fake_execute_trade,
        )


def test_cli_place_order_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_place_order(
        agent=agent,
        order_id="order-1",
        symbol="xauusd",
        side="buy",
        quantity=10.0,
        price=2025.0,
        output_format="text",
        operation=fake_place_order,
    )

    assert cli_output.success is True
    assert "SUCCESS: Order placed." in cli_output.output
    assert "order_id: order-1" in cli_output.output
    assert "status: open" in cli_output.output


def test_cli_fill_order_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_fill_order(
        agent=agent,
        order_id="order-1",
        fill_price=2025.0,
        output_format="text",
        operation=fake_fill_order,
    )

    assert cli_output.success is True
    assert "SUCCESS: Order filled." in cli_output.output
    assert "status: filled" in cli_output.output
    assert "position_id: position-1" in cli_output.output


def test_cli_cancel_order_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_cancel_order(
        agent=agent,
        order_id="order-1",
        output_format="text",
        operation=fake_cancel_order,
    )

    assert cli_output.success is True
    assert "SUCCESS: Order cancelled." in cli_output.output
    assert "status: cancelled" in cli_output.output


def test_cli_order_status_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_order_status(
        agent=agent,
        order_id="order-1",
        output_format="text",
        operation=fake_order_status,
    )

    assert cli_output.success is True
    assert "SUCCESS: Order status loaded." in cli_output.output
    assert "status: open" in cli_output.output


def test_cli_close_position_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_close_position(
        agent=agent,
        position_id="position-1",
        close_price=2035.0,
        output_format="text",
        request_id="close-position-1",
        operation=fake_close_position,
    )

    assert cli_output.success is True
    assert "SUCCESS: Position closed." in cli_output.output
    assert "position_id: position-1" in cli_output.output
    assert "status: closed" in cli_output.output
    assert "profit: 100.0" in cli_output.output


def test_cli_execution_summary_success():
    agent = SimpleNamespace(name="execution-agent")

    cli_output = cli_execution_summary(
        agent=agent,
        output_format="text",
        request_id="execution-summary-1",
        operation=fake_execution_summary,
    )

    assert cli_output.success is True
    assert "SUCCESS: Execution summary loaded." in cli_output.output
    assert "orders: 1" in cli_output.output
    assert "open_positions: 0" in cli_output.output