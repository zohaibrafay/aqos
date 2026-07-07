"""
Unit tests for AQOS CLI risk commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliRiskRequest,
    build_risk_cli_output,
    cli_approve_trade,
    cli_assess_trade,
    cli_position_size,
    cli_reject_reason,
    cli_risk_handoff,
    execute_risk_operation,
)


def sample_trade_request():
    return {
        "symbol": "XAUUSD",
        "side": "buy",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "take_profit_price": 2045.0,
    }


def fake_position_size(agent, trade_request, request_id=None):
    return api_success(
        message="Position size calculated.",
        data={
            "agent": agent.name,
            "symbol": trade_request["symbol"],
            "side": trade_request["side"],
            "position_size": 10.0,
            "risk_amount": 100.0,
        },
        request_id=request_id,
    )


def fake_assess_trade(agent, trade_request, request_id=None):
    return api_success(
        message="Trade risk assessed.",
        data={
            "agent": agent.name,
            "symbol": trade_request["symbol"],
            "side": trade_request["side"],
            "allowed": True,
            "reason": "Trade risk is acceptable.",
        },
        request_id=request_id,
    )


def fake_approve_trade(agent, trade_request, request_id=None):
    return api_success(
        message="Trade approval completed.",
        data={
            "agent": agent.name,
            "symbol": trade_request["symbol"],
            "side": trade_request["side"],
            "approved": True,
            "reason": "Trade approved.",
        },
        request_id=request_id,
    )


def fake_reject_reason(agent, trade_request, request_id=None):
    return api_success(
        message="Reject reason generated.",
        data={
            "agent": agent.name,
            "symbol": trade_request["symbol"],
            "side": trade_request["side"],
            "rejected": False,
            "reason": "No rejection reason.",
        },
        request_id=request_id,
    )


def fake_risk_handoff(agent, trade_request, request_id=None):
    return api_success(
        message="Risk handoff generated.",
        data={
            "agent": agent.name,
            "symbol": trade_request["symbol"],
            "side": trade_request["side"],
            "allowed": True,
            "reason": "Trade allowed.",
            "position_size": 10.0,
            "entry_price": trade_request["entry_price"],
            "stop_loss_price": trade_request["stop_loss_price"],
            "take_profit_price": trade_request["take_profit_price"],
            "risk_amount": 100.0,
            "risk_percent": trade_request["risk_percent"],
            "execution_ready": True,
        },
        request_id=request_id,
    )


def fake_failure_risk(agent, trade_request, request_id=None):
    return api_failure(
        message="Risk command failed.",
        data={
            "symbol": trade_request["symbol"],
            "side": trade_request["side"],
        },
        request_id=request_id,
    )


def test_cli_risk_request_accepts_valid_values():
    agent = SimpleNamespace(name="risk-agent")

    request = CliRiskRequest(
        agent=agent,
        symbol="xauusd",
        side="BUY",
        account_balance=10_000.0,
        risk_percent=0.01,
        entry_price=2025.0,
        stop_loss_price=2015.0,
        take_profit_price=2045.0,
        output_format="pretty-json",
        include_metadata=True,
        request_id="risk-request-1",
    )

    assert request.agent == agent
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "risk-request-1"

    assert request.to_trade_request() == sample_trade_request()


def test_cli_risk_request_accepts_sell_stop_loss_direction():
    agent = SimpleNamespace(name="risk-agent")

    request = CliRiskRequest(
        agent=agent,
        symbol="xauusd",
        side="sell",
        account_balance=10_000.0,
        risk_percent=0.01,
        entry_price=2025.0,
        stop_loss_price=2035.0,
        take_profit_price=2000.0,
    )

    trade_request = request.to_trade_request()

    assert trade_request["side"] == "sell"
    assert trade_request["stop_loss_price"] == 2035.0


def test_cli_risk_request_rejects_invalid_values():
    agent = SimpleNamespace(name="risk-agent")

    with pytest.raises(ValueError):
        CliRiskRequest(agent=None)

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, symbol="")

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, side="hold")

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, account_balance=0)

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, risk_percent=0)

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, entry_price=0)

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, stop_loss_price=0)

    with pytest.raises(ValueError):
        CliRiskRequest(
            agent=agent,
            side="buy",
            entry_price=2025.0,
            stop_loss_price=2035.0,
        )

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, output_format="bad")

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, include_metadata="yes")

    with pytest.raises(ValueError):
        CliRiskRequest(agent=agent, request_id="")


def test_execute_risk_operation_with_request_id():
    agent = SimpleNamespace(name="risk-agent")

    response = execute_risk_operation(
        fake_risk_handoff,
        agent=agent,
        trade_request=sample_trade_request(),
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["agent"] == "risk-agent"


def test_execute_risk_operation_rejects_invalid_values():
    agent = SimpleNamespace(name="risk-agent")

    with pytest.raises(ValueError):
        execute_risk_operation(
            "not-callable",
            agent=agent,
        )

    with pytest.raises(ValueError):
        execute_risk_operation(
            fake_risk_handoff,
            agent=None,
        )


def test_build_risk_cli_output_success():
    agent = SimpleNamespace(name="risk-agent")

    response = fake_risk_handoff(
        agent,
        sample_trade_request(),
        request_id="request-1",
    )

    cli_output = build_risk_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Risk handoff generated." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_risk_cli_output_failure():
    agent = SimpleNamespace(name="risk-agent")

    response = fake_failure_risk(
        agent,
        sample_trade_request(),
    )

    cli_output = build_risk_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Risk command failed."


def test_cli_position_size_text_success():
    agent = SimpleNamespace(name="risk-agent")

    cli_output = cli_position_size(
        agent=agent,
        symbol="xauusd",
        side="buy",
        account_balance=10_000.0,
        risk_percent=0.01,
        entry_price=2025.0,
        stop_loss_price=2015.0,
        output_format="text",
        request_id="position-size-1",
        operation=fake_position_size,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Position size calculated." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "side: buy" in cli_output.output
    assert "position_size: 10.0" in cli_output.output
    assert "risk_amount: 100.0" in cli_output.output


def test_cli_position_size_json_success():
    agent = SimpleNamespace(name="risk-agent")

    cli_output = cli_position_size(
        agent=agent,
        symbol="xauusd",
        side="buy",
        output_format="json",
        operation=fake_position_size,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["symbol"] == "XAUUSD"
    assert payload["data"]["position_size"] == 10.0
    assert "metadata" not in payload


def test_cli_position_size_validation_failure():
    agent = SimpleNamespace(name="risk-agent")

    with pytest.raises(ValueError):
        cli_position_size(
            agent=agent,
            symbol="",
            operation=fake_position_size,
        )


def test_cli_assess_trade_success():
    agent = SimpleNamespace(name="risk-agent")

    cli_output = cli_assess_trade(
        agent=agent,
        symbol="xauusd",
        side="buy",
        output_format="text",
        operation=fake_assess_trade,
    )

    assert cli_output.success is True
    assert "SUCCESS: Trade risk assessed." in cli_output.output
    assert "allowed: true" in cli_output.output
    assert "Trade risk is acceptable." in cli_output.output


def test_cli_approve_trade_success():
    agent = SimpleNamespace(name="risk-agent")

    cli_output = cli_approve_trade(
        agent=agent,
        symbol="xauusd",
        side="buy",
        output_format="text",
        operation=fake_approve_trade,
    )

    assert cli_output.success is True
    assert "SUCCESS: Trade approval completed." in cli_output.output
    assert "approved: true" in cli_output.output


def test_cli_reject_reason_success():
    agent = SimpleNamespace(name="risk-agent")

    cli_output = cli_reject_reason(
        agent=agent,
        symbol="xauusd",
        side="buy",
        output_format="text",
        operation=fake_reject_reason,
    )

    assert cli_output.success is True
    assert "SUCCESS: Reject reason generated." in cli_output.output
    assert "rejected: false" in cli_output.output
    assert "No rejection reason." in cli_output.output


def test_cli_risk_handoff_success():
    agent = SimpleNamespace(name="risk-agent")

    cli_output = cli_risk_handoff(
        agent=agent,
        symbol="xauusd",
        side="buy",
        output_format="text",
        request_id="risk-handoff-1",
        operation=fake_risk_handoff,
    )

    assert cli_output.success is True
    assert "SUCCESS: Risk handoff generated." in cli_output.output
    assert "allowed: true" in cli_output.output
    assert "execution_ready: true" in cli_output.output
    assert "stop_loss_price: 2015.0" in cli_output.output
    assert "take_profit_price: 2045.0" in cli_output.output