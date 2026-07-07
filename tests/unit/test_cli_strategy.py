"""
Unit tests for AQOS CLI strategy commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliStrategyRequest,
    build_strategy_cli_output,
    cli_entry_check,
    cli_exit_check,
    cli_strategy_decision,
    cli_strategy_explanation,
    cli_strategy_handoff,
    cli_strategy_signal,
    execute_strategy_operation,
)


def fake_strategy_signal(agent, market_state, request_id=None):
    return api_success(
        message="Strategy signal generated.",
        data={
            "agent": agent.name,
            "symbol": market_state["symbol"],
            "timeframe": market_state["timeframe"],
            "regime": market_state["regime"],
            "trend": market_state["trend"],
            "entry_price": market_state["entry_price"],
            "signal": "buy",
        },
        request_id=request_id,
    )


def fake_strategy_decision(agent, market_state, request_id=None):
    return api_success(
        message="Strategy decision generated.",
        data={
            "agent": agent.name,
            "symbol": market_state["symbol"],
            "signal": "buy",
            "decision": "enter",
        },
        request_id=request_id,
    )


def fake_strategy_explanation(agent, market_state, request_id=None):
    return api_success(
        message="Strategy explanation generated.",
        data={
            "agent": agent.name,
            "symbol": market_state["symbol"],
            "explanation": "Bullish regime and uptrend support buy signal.",
        },
        request_id=request_id,
    )


def fake_entry_check(agent, market_state, request_id=None):
    return api_success(
        message="Entry check completed.",
        data={
            "agent": agent.name,
            "symbol": market_state["symbol"],
            "should_enter": True,
        },
        request_id=request_id,
    )


def fake_exit_check(agent, market_state, request_id=None):
    return api_success(
        message="Exit check completed.",
        data={
            "agent": agent.name,
            "symbol": market_state["symbol"],
            "should_exit": False,
        },
        request_id=request_id,
    )


def fake_strategy_handoff(agent, market_state, request_id=None):
    return api_success(
        message="Strategy handoff generated.",
        data={
            "agent": agent.name,
            "symbol": market_state["symbol"],
            "timeframe": market_state["timeframe"],
            "signal": "buy",
            "entry_price": market_state["entry_price"],
            "stop_loss_price": 2015.0,
            "take_profit_price": 2045.0,
            "should_enter": True,
            "should_exit": False,
        },
        request_id=request_id,
    )


def fake_failure_strategy(agent, market_state, request_id=None):
    return api_failure(
        message="Strategy command failed.",
        data={
            "symbol": market_state["symbol"],
            "timeframe": market_state["timeframe"],
        },
        request_id=request_id,
    )


def test_cli_strategy_request_accepts_valid_values():
    agent = SimpleNamespace(name="strategy-agent")

    request = CliStrategyRequest(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        regime=" bullish ",
        trend=" uptrend ",
        entry_price=2025.0,
        output_format="pretty-json",
        include_metadata=True,
        request_id="strategy-request-1",
    )

    assert request.agent == agent
    assert request.symbol == "xauusd"
    assert request.timeframe == "h1"
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "strategy-request-1"

    assert request.to_market_state() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "regime": "bullish",
        "trend": "uptrend",
        "entry_price": 2025.0,
    }


def test_cli_strategy_request_rejects_invalid_values():
    agent = SimpleNamespace(name="strategy-agent")

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=None)

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, symbol="")

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, timeframe="BAD")

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, regime="")

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, trend="")

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, entry_price=0)

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, output_format="bad")

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, include_metadata="yes")

    with pytest.raises(ValueError):
        CliStrategyRequest(agent=agent, request_id="")


def test_execute_strategy_operation_with_request_id():
    agent = SimpleNamespace(name="strategy-agent")

    response = execute_strategy_operation(
        fake_strategy_signal,
        agent=agent,
        market_state={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "regime": "bullish",
            "trend": "uptrend",
            "entry_price": 2025.0,
        },
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["agent"] == "strategy-agent"


def test_execute_strategy_operation_rejects_invalid_values():
    agent = SimpleNamespace(name="strategy-agent")

    with pytest.raises(ValueError):
        execute_strategy_operation(
            "not-callable",
            agent=agent,
        )

    with pytest.raises(ValueError):
        execute_strategy_operation(
            fake_strategy_signal,
            agent=None,
        )


def test_build_strategy_cli_output_success():
    agent = SimpleNamespace(name="strategy-agent")

    response = fake_strategy_signal(
        agent,
        {
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "regime": "bullish",
            "trend": "uptrend",
            "entry_price": 2025.0,
        },
        request_id="request-1",
    )

    cli_output = build_strategy_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Strategy signal generated." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_strategy_cli_output_failure():
    agent = SimpleNamespace(name="strategy-agent")

    response = fake_failure_strategy(
        agent,
        {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    cli_output = build_strategy_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Strategy command failed."


def test_cli_strategy_signal_text_success():
    agent = SimpleNamespace(name="strategy-agent")

    cli_output = cli_strategy_signal(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        regime="bullish",
        trend="uptrend",
        entry_price=2025.0,
        output_format="text",
        request_id="strategy-signal-1",
        operation=fake_strategy_signal,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Strategy signal generated." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "timeframe: H1" in cli_output.output
    assert "signal: buy" in cli_output.output
    assert "trend: uptrend" in cli_output.output


def test_cli_strategy_signal_json_success():
    agent = SimpleNamespace(name="strategy-agent")

    cli_output = cli_strategy_signal(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="json",
        operation=fake_strategy_signal,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["symbol"] == "XAUUSD"
    assert payload["data"]["signal"] == "buy"
    assert "metadata" not in payload


def test_cli_strategy_signal_validation_failure():
    agent = SimpleNamespace(name="strategy-agent")

    with pytest.raises(ValueError):
        cli_strategy_signal(
            agent=agent,
            symbol="",
            operation=fake_strategy_signal,
        )


def test_cli_strategy_decision_success():
    agent = SimpleNamespace(name="strategy-agent")

    cli_output = cli_strategy_decision(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_strategy_decision,
    )

    assert cli_output.success is True
    assert "SUCCESS: Strategy decision generated." in cli_output.output
    assert "decision: enter" in cli_output.output


def test_cli_strategy_explanation_success():
    agent = SimpleNamespace(name="strategy-agent")

    cli_output = cli_strategy_explanation(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_strategy_explanation,
    )

    assert cli_output.success is True
    assert "SUCCESS: Strategy explanation generated." in cli_output.output
    assert "Bullish regime and uptrend support buy signal." in cli_output.output


def test_cli_entry_check_success():
    agent = SimpleNamespace(name="strategy-agent")

    cli_output = cli_entry_check(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_entry_check,
    )

    assert cli_output.success is True
    assert "SUCCESS: Entry check completed." in cli_output.output
    assert "should_enter: true" in cli_output.output


def test_cli_exit_check_success():
    agent = SimpleNamespace(name="strategy-agent")

    cli_output = cli_exit_check(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_exit_check,
    )

    assert cli_output.success is True
    assert "SUCCESS: Exit check completed." in cli_output.output
    assert "should_exit: false" in cli_output.output


def test_cli_strategy_handoff_success():
    agent = SimpleNamespace(name="strategy-agent")

    cli_output = cli_strategy_handoff(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        request_id="handoff-1",
        operation=fake_strategy_handoff,
    )

    assert cli_output.success is True
    assert "SUCCESS: Strategy handoff generated." in cli_output.output
    assert "signal: buy" in cli_output.output
    assert "stop_loss_price: 2015.0" in cli_output.output
    assert "take_profit_price: 2045.0" in cli_output.output