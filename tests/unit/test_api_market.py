"""
Unit tests for AQOS API market operations.
"""

import pytest

from types import SimpleNamespace

from aqos.api import (
    MarketRequest,
    api_calendar_context,
    api_market_snapshot,
    api_market_state,
    api_news_context,
    api_regime_summary,
    api_trend_summary,
    build_market_request,
    market_agent_operation,
)


class SuccessfulMarketAgent:
    name = "market-agent"

    def __init__(self):
        self.calls = []

    def execute(self, action, payload=None, metadata=None):
        self.calls.append(
            {
                "action": action,
                "payload": payload,
                "metadata": metadata,
            }
        )

        data_by_action = {
            "market-state": {
                "symbol": payload.get("symbol"),
                "timeframe": payload.get("timeframe"),
                "close": 2025.0,
                "trend": "uptrend",
                "regime": "bullish",
            },
            "snapshot": {
                "symbol": payload.get("symbol"),
                "timeframe": payload.get("timeframe"),
                "close": 2025.0,
            },
            "trend-summary": {
                "symbol": payload.get("symbol"),
                "timeframe": payload.get("timeframe"),
                "trend": "uptrend",
            },
            "regime-summary": {
                "symbol": payload.get("symbol"),
                "timeframe": payload.get("timeframe"),
                "regime": "bullish",
            },
            "news-context": {
                "symbol": payload.get("symbol"),
                "items": 1,
                "sentiment": "positive",
            },
            "calendar-context": {
                "currency": payload.get("currency"),
                "events": 1,
                "impact": "high",
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


class FailingMarketAgent:
    name = "market-agent"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Market agent failed.",
            data={
                "reason": "missing market data",
            },
            metadata={},
        )


class BrokenMarketAgent:
    name = "broken-market-agent"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Market agent exploded.")


def test_market_request_defaults():
    request = MarketRequest()

    assert request.symbol == "XAUUSD"
    assert request.timeframe == "H1"
    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_market_request_normalizes_values():
    request = MarketRequest(
        symbol="xauusd",
        timeframe="h1",
    )

    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_market_request_rejects_invalid_symbol():
    with pytest.raises(ValueError):
        MarketRequest(
            symbol="",
            timeframe="H1",
        )


def test_market_request_rejects_invalid_timeframe():
    with pytest.raises(ValueError):
        MarketRequest(
            symbol="XAUUSD",
            timeframe="BAD",
        )


def test_build_market_request():
    request = build_market_request(
        symbol="xauusd",
        timeframe="h1",
    )

    assert isinstance(request, MarketRequest)
    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_market_agent_operation_success():
    agent = SuccessfulMarketAgent()

    response = market_agent_operation(
        agent,
        action="market-state",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        success_message="Market state loaded.",
        failure_message="Market state failed.",
        request_id="market-request-1",
    )

    payload = response.to_dict()
    print(payload)
    assert payload["success"] is True
    assert payload["message"] == "Market state loaded."
    assert payload["data"]["action"] == "market-state"
    assert payload["data"]["agent"] == "market-agent"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["trend"] == "uptrend"
    assert payload["metadata"]["request_id"] == "market-request-1"


def test_market_agent_operation_failure():
    response = market_agent_operation(
        FailingMarketAgent(),
        action="market-state",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        success_message="Market state loaded.",
        failure_message="Market state failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Market state failed."
    assert payload["errors"][0]["code"] == "MARKET_AGENT_ERROR"
    assert payload["errors"][0]["message"] == "Market agent failed."
    assert payload["data"]["result"] == {
        "reason": "missing market data",
    }


def test_market_agent_operation_exception():
    response = market_agent_operation(
        BrokenMarketAgent(),
        action="market-state",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        success_message="Market state loaded.",
        failure_message="Market state failed.",
    )

    payload = response.to_dict()
    print(payload)
    assert payload["success"] is False
    assert payload["message"] == "Market state failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Market agent exploded."


def test_api_market_state_success():
    agent = SuccessfulMarketAgent()

    response = api_market_state(
        agent,
        symbol="xauusd",
        timeframe="h1",
        request_id="market-state-1",
    )

    payload = response.to_dict()
    
    assert payload["success"] is True
    assert payload["message"] == "Market state loaded."
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["timeframe"] == "H1"
    assert payload["data"]["result"]["regime"] == "bullish"
    assert payload["metadata"]["request_id"] == "market-state-1"

    assert agent.calls[0]["action"] == "market-state"
    assert agent.calls[0]["payload"] == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_api_market_state_validation_failure():
    response = api_market_state(
        SuccessfulMarketAgent(),
        symbol="",
        timeframe="H1",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "symbol_timeframe"


def test_api_market_snapshot_success():
    response = api_market_snapshot(
        SuccessfulMarketAgent(),
        symbol="XAUUSD",
        timeframe="H1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Market snapshot loaded."
    assert payload["data"]["action"] == "snapshot"
    assert payload["data"]["result"]["close"] == 2025.0


def test_api_trend_summary_success():
    response = api_trend_summary(
        SuccessfulMarketAgent(),
        symbol="XAUUSD",
        timeframe="H1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trend summary loaded."
    assert payload["data"]["action"] == "trend-summary"
    assert payload["data"]["result"]["trend"] == "uptrend"


def test_api_regime_summary_success():
    response = api_regime_summary(
        SuccessfulMarketAgent(),
        symbol="XAUUSD",
        timeframe="H1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Regime summary loaded."
    assert payload["data"]["action"] == "regime-summary"
    assert payload["data"]["result"]["regime"] == "bullish"


def test_api_news_context_success():
    agent = SuccessfulMarketAgent()

    response = api_news_context(
        agent,
        symbol="xauusd",
        request_id="news-context-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "News context loaded."
    assert payload["data"]["action"] == "news-context"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["items"] == 1
    assert payload["metadata"]["request_id"] == "news-context-1"

    assert agent.calls[0]["payload"] == {
        "symbol": "XAUUSD",
    }


def test_api_news_context_validation_failure():
    response = api_news_context(
        SuccessfulMarketAgent(),
        symbol="",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "symbol"


def test_api_calendar_context_success():
    agent = SuccessfulMarketAgent()

    response = api_calendar_context(
        agent,
        currency="usd",
        request_id="calendar-context-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Calendar context loaded."
    assert payload["data"]["action"] == "calendar-context"
    assert payload["data"]["result"]["currency"] == "USD"
    assert payload["data"]["result"]["events"] == 1
    assert payload["metadata"]["request_id"] == "calendar-context-1"

    assert agent.calls[0]["payload"] == {
        "currency": "USD",
    }


def test_api_calendar_context_validation_failure():
    response = api_calendar_context(
        SuccessfulMarketAgent(),
        currency="",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "currency"