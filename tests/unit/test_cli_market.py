"""
Unit tests for AQOS CLI market commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliMarketRequest,
    build_market_cli_output,
    cli_calendar_context,
    cli_market_snapshot,
    cli_market_state,
    cli_news_context,
    cli_regime_summary,
    cli_trend_summary,
    execute_market_operation,
)


def fake_market_state(agent, symbol="XAUUSD", timeframe="H1", request_id=None):
    return api_success(
        message="Market state loaded.",
        data={
            "agent": agent.name,
            "symbol": symbol,
            "timeframe": timeframe,
            "regime": "bullish",
            "trend": "uptrend",
        },
        request_id=request_id,
    )


def fake_market_snapshot(agent, symbol="XAUUSD", timeframe="H1", request_id=None):
    return api_success(
        message="Market snapshot loaded.",
        data={
            "agent": agent.name,
            "symbol": symbol,
            "timeframe": timeframe,
            "close": 2025.0,
        },
        request_id=request_id,
    )


def fake_trend_summary(agent, symbol="XAUUSD", timeframe="H1", request_id=None):
    return api_success(
        message="Trend summary loaded.",
        data={
            "agent": agent.name,
            "symbol": symbol,
            "timeframe": timeframe,
            "trend": "uptrend",
        },
        request_id=request_id,
    )


def fake_regime_summary(agent, symbol="XAUUSD", timeframe="H1", request_id=None):
    return api_success(
        message="Regime summary loaded.",
        data={
            "agent": agent.name,
            "symbol": symbol,
            "timeframe": timeframe,
            "regime": "bullish",
        },
        request_id=request_id,
    )


def fake_news_context(agent, symbol="XAUUSD", timeframe="H1", request_id=None):
    return api_success(
        message="News context loaded.",
        data={
            "agent": agent.name,
            "symbol": symbol,
            "timeframe": timeframe,
            "items": 2,
            "sentiment": "positive",
        },
        request_id=request_id,
    )


def fake_calendar_context(agent, symbol="XAUUSD", timeframe="H1", request_id=None):
    return api_success(
        message="Calendar context loaded.",
        data={
            "agent": agent.name,
            "symbol": symbol,
            "timeframe": timeframe,
            "events": 1,
            "impact": "high",
        },
        request_id=request_id,
    )


def fake_failure_market(agent, symbol="XAUUSD", timeframe="H1", request_id=None):
    return api_failure(
        message="Market command failed.",
        data={
            "symbol": symbol,
            "timeframe": timeframe,
        },
        request_id=request_id,
    )


def test_cli_market_request_accepts_valid_values():
    agent = SimpleNamespace(name="market-agent")

    request = CliMarketRequest(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="pretty-json",
        include_metadata=True,
        request_id="market-request-1",
    )

    assert request.agent == agent
    assert request.symbol == "xauusd"
    assert request.timeframe == "h1"
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "market-request-1"

    assert request.to_market_request().to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_cli_market_request_rejects_invalid_values():
    agent = SimpleNamespace(name="market-agent")

    with pytest.raises(ValueError):
        CliMarketRequest(agent=None)

    with pytest.raises(ValueError):
        CliMarketRequest(agent=agent, symbol="")

    with pytest.raises(ValueError):
        CliMarketRequest(agent=agent, timeframe="BAD")

    with pytest.raises(ValueError):
        CliMarketRequest(agent=agent, output_format="bad")

    with pytest.raises(ValueError):
        CliMarketRequest(agent=agent, include_metadata="yes")

    with pytest.raises(ValueError):
        CliMarketRequest(agent=agent, request_id="")


def test_execute_market_operation_with_request_id():
    agent = SimpleNamespace(name="market-agent")

    response = execute_market_operation(
        fake_market_state,
        agent=agent,
        symbol="XAUUSD",
        timeframe="H1",
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["agent"] == "market-agent"


def test_execute_market_operation_rejects_invalid_values():
    agent = SimpleNamespace(name="market-agent")

    with pytest.raises(ValueError):
        execute_market_operation(
            "not-callable",
            agent=agent,
        )

    with pytest.raises(ValueError):
        execute_market_operation(
            fake_market_state,
            agent=None,
        )


def test_build_market_cli_output_success():
    agent = SimpleNamespace(name="market-agent")

    response = fake_market_state(
        agent,
        request_id="request-1",
    )

    cli_output = build_market_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Market state loaded." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_market_cli_output_failure():
    agent = SimpleNamespace(name="market-agent")
    response = fake_failure_market(agent)

    cli_output = build_market_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Market command failed."


def test_cli_market_state_text_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_market_state(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        request_id="market-state-1",
        operation=fake_market_state,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Market state loaded." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "timeframe: H1" in cli_output.output
    assert "regime: bullish" in cli_output.output
    assert "trend: uptrend" in cli_output.output


def test_cli_market_state_json_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_market_state(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="json",
        operation=fake_market_state,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["symbol"] == "XAUUSD"
    assert payload["data"]["timeframe"] == "H1"
    assert "metadata" not in payload


def test_cli_market_state_validation_failure():
    agent = SimpleNamespace(name="market-agent")

    with pytest.raises(ValueError):
        cli_market_state(
            agent=agent,
            symbol="",
            operation=fake_market_state,
        )


def test_cli_market_snapshot_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_market_snapshot(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_market_snapshot,
    )

    assert cli_output.success is True
    assert "SUCCESS: Market snapshot loaded." in cli_output.output
    assert "close: 2025.0" in cli_output.output


def test_cli_trend_summary_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_trend_summary(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_trend_summary,
    )

    assert cli_output.success is True
    assert "SUCCESS: Trend summary loaded." in cli_output.output
    assert "trend: uptrend" in cli_output.output


def test_cli_regime_summary_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_regime_summary(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_regime_summary,
    )

    assert cli_output.success is True
    assert "SUCCESS: Regime summary loaded." in cli_output.output
    assert "regime: bullish" in cli_output.output


def test_cli_news_context_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_news_context(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_news_context,
    )

    assert cli_output.success is True
    assert "SUCCESS: News context loaded." in cli_output.output
    assert "items: 2" in cli_output.output
    assert "sentiment: positive" in cli_output.output


def test_cli_calendar_context_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_calendar_context(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_calendar_context,
    )

    assert cli_output.success is True
    assert "SUCCESS: Calendar context loaded." in cli_output.output
    assert "events: 1" in cli_output.output
    assert "impact: high" in cli_output.output