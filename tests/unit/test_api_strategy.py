"""
Unit tests for AQOS API strategy operations.
"""

from types import SimpleNamespace

import pytest

from aqos.api import (
    StrategyMarketStateRequest,
    api_entry_check,
    api_exit_check,
    api_strategy_decision,
    api_strategy_explanation,
    api_strategy_handoff,
    api_strategy_signal,
    build_strategy_market_state_request,
    normalize_market_state,
    strategy_agent_operation,
)


class SuccessfulStrategyAgent:
    name = "strategy-agent"

    def __init__(self):
        self.calls = []

    def execute(self, action, payload=None, metadata=None):
        payload = payload or {}
        market_state = payload.get("market_state", {})

        self.calls.append(
            {
                "action": action,
                "payload": payload,
                "metadata": metadata,
            }
        )

        data_by_action = {
            "signal": {
                "symbol": market_state.get("symbol"),
                "timeframe": market_state.get("timeframe"),
                "signal": "buy",
                "confidence": 0.75,
            },
            "decision": {
                "symbol": market_state.get("symbol"),
                "timeframe": market_state.get("timeframe"),
                "signal": "buy",
                "decision": "enter",
                "entry_price": market_state.get("entry_price"),
            },
            "explain-signal": {
                "signal": "buy",
                "explanation": "Bullish regime and uptrend support buy signal.",
            },
            "entry-check": {
                "should_enter": True,
                "reason": "Entry conditions are valid.",
            },
            "exit-check": {
                "should_exit": False,
                "reason": "Exit conditions are not met.",
            },
            "handoff": {
                "symbol": market_state.get("symbol"),
                "timeframe": market_state.get("timeframe"),
                "signal": "buy",
                "entry_price": market_state.get("entry_price"),
                "stop_loss_price": 2015.0,
                "take_profit_price": 2045.0,
                "should_enter": True,
                "should_exit": False,
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


class FailingStrategyAgent:
    name = "strategy-agent"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Strategy agent failed.",
            data={
                "reason": "missing market state",
            },
            metadata={},
        )


class BrokenStrategyAgent:
    name = "broken-strategy-agent"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Strategy agent exploded.")


def sample_market_state():
    return {
        "symbol": "xauusd",
        "timeframe": "h1",
        "regime": "bullish",
        "trend": "uptrend",
        "entry_price": 2025.0,
    }


def test_strategy_market_state_request_defaults():
    request = StrategyMarketStateRequest()

    assert request.to_market_state() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "regime": "bullish",
        "trend": "uptrend",
        "entry_price": 2025.0,
    }


def test_strategy_market_state_request_normalizes_values():
    request = StrategyMarketStateRequest(
        symbol="xauusd",
        timeframe="h1",
        regime=" Bullish ",
        trend=" UpTrend ",
        entry_price=2025.0,
    )

    assert request.to_payload() == {
        "market_state": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "regime": "bullish",
            "trend": "uptrend",
            "entry_price": 2025.0,
        }
    }


def test_strategy_market_state_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        StrategyMarketStateRequest(symbol="", timeframe="H1")

    with pytest.raises(ValueError):
        StrategyMarketStateRequest(symbol="XAUUSD", timeframe="BAD")

    with pytest.raises(ValueError):
        StrategyMarketStateRequest(regime="")

    with pytest.raises(ValueError):
        StrategyMarketStateRequest(trend="")

    with pytest.raises(ValueError):
        StrategyMarketStateRequest(entry_price=0)


def test_build_strategy_market_state_request():
    request = build_strategy_market_state_request(
        symbol="xauusd",
        timeframe="h1",
        regime="bullish",
        trend="uptrend",
        entry_price=2025.0,
    )

    assert isinstance(request, StrategyMarketStateRequest)
    assert request.to_market_state()["symbol"] == "XAUUSD"
    assert request.to_market_state()["timeframe"] == "H1"


def test_normalize_market_state_uses_close_as_entry_price():
    normalized = normalize_market_state(
        {
            "symbol": "xauusd",
            "timeframe": "h1",
            "regime": "bullish",
            "trend": "uptrend",
            "close": 2025.0,
            "extra": "preserved",
        }
    )

    assert normalized["symbol"] == "XAUUSD"
    assert normalized["timeframe"] == "H1"
    assert normalized["entry_price"] == 2025.0
    assert normalized["close"] == 2025.0
    assert normalized["extra"] == "preserved"


def test_normalize_market_state_rejects_non_dict():
    with pytest.raises(ValueError, match="Market state"):
        normalize_market_state("bad")


def test_strategy_agent_operation_success():
    agent = SuccessfulStrategyAgent()

    response = strategy_agent_operation(
        agent,
        action="signal",
        payload={
            "market_state": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2025.0,
            },
        },
        success_message="Strategy signal generated.",
        failure_message="Strategy signal failed.",
        request_id="strategy-request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Strategy signal generated."
    assert payload["data"]["action"] == "signal"
    assert payload["data"]["agent"] == "strategy-agent"
    assert payload["data"]["result"]["signal"] == "buy"
    assert payload["metadata"]["request_id"] == "strategy-request-1"


def test_strategy_agent_operation_failure():
    response = strategy_agent_operation(
        FailingStrategyAgent(),
        action="signal",
        payload={
            "market_state": sample_market_state(),
        },
        success_message="Strategy signal generated.",
        failure_message="Strategy signal failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Strategy signal failed."
    assert payload["errors"][0]["code"] == "STRATEGY_AGENT_ERROR"
    assert payload["errors"][0]["message"] == "Strategy agent failed."
    assert payload["data"]["result"] == {
        "reason": "missing market state",
    }


def test_strategy_agent_operation_exception():
    response = strategy_agent_operation(
        BrokenStrategyAgent(),
        action="signal",
        payload={
            "market_state": sample_market_state(),
        },
        success_message="Strategy signal generated.",
        failure_message="Strategy signal failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Strategy signal failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Strategy agent exploded."


def test_api_strategy_signal_success():
    agent = SuccessfulStrategyAgent()

    response = api_strategy_signal(
        agent,
        market_state=sample_market_state(),
        request_id="strategy-signal-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Strategy signal generated."
    assert payload["data"]["action"] == "signal"
    assert payload["data"]["result"]["signal"] == "buy"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["metadata"]["request_id"] == "strategy-signal-1"

    assert agent.calls[0]["payload"]["market_state"]["symbol"] == "XAUUSD"
    assert agent.calls[0]["payload"]["market_state"]["timeframe"] == "H1"


def test_api_strategy_signal_validation_failure():
    response = api_strategy_signal(
        SuccessfulStrategyAgent(),
        market_state="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "market_state"


def test_api_strategy_decision_success():
    response = api_strategy_decision(
        SuccessfulStrategyAgent(),
        market_state=sample_market_state(),
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Strategy decision generated."
    assert payload["data"]["action"] == "decision"
    assert payload["data"]["result"]["decision"] == "enter"
    assert payload["data"]["result"]["entry_price"] == 2025.0


def test_api_strategy_explanation_success():
    response = api_strategy_explanation(
        SuccessfulStrategyAgent(),
        market_state=sample_market_state(),
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Strategy explanation generated."
    assert payload["data"]["action"] == "explain-signal"
    assert "Bullish regime" in payload["data"]["result"]["explanation"]


def test_api_entry_check_success():
    response = api_entry_check(
        SuccessfulStrategyAgent(),
        market_state=sample_market_state(),
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Entry check completed."
    assert payload["data"]["action"] == "entry-check"
    assert payload["data"]["result"]["should_enter"] is True


def test_api_exit_check_success():
    response = api_exit_check(
        SuccessfulStrategyAgent(),
        market_state=sample_market_state(),
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Exit check completed."
    assert payload["data"]["action"] == "exit-check"
    assert payload["data"]["result"]["should_exit"] is False


def test_api_strategy_handoff_success():
    response = api_strategy_handoff(
        SuccessfulStrategyAgent(),
        market_state=sample_market_state(),
        request_id="strategy-handoff-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Strategy handoff generated."
    assert payload["data"]["action"] == "handoff"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["signal"] == "buy"
    assert payload["data"]["result"]["should_enter"] is True
    assert payload["metadata"]["request_id"] == "strategy-handoff-1"