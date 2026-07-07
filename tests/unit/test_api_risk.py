"""
Unit tests for AQOS API risk operations.
"""

from types import SimpleNamespace

import pytest

from aqos.api import (
    RiskTradeRequest,
    api_approve_trade,
    api_assess_trade,
    api_position_size,
    api_reject_reason,
    api_risk_handoff,
    build_risk_trade_request,
    normalize_trade_request,
    risk_agent_operation,
)


class SuccessfulRiskAgent:
    name = "risk-agent"

    def __init__(self):
        self.calls = []

    def execute(self, action, payload=None, metadata=None):
        payload = payload or {}
        trade_request = payload.get("trade_request", {})

        self.calls.append(
            {
                "action": action,
                "payload": payload,
                "metadata": metadata,
            }
        )

        data_by_action = {
            "position-size": {
                "symbol": trade_request.get("symbol"),
                "side": trade_request.get("side"),
                "position_size": 10.0,
                "risk_amount": 100.0,
            },
            "assess-trade": {
                "symbol": trade_request.get("symbol"),
                "side": trade_request.get("side"),
                "allowed": True,
                "reason": "Trade risk is acceptable.",
            },
            "approve-trade": {
                "symbol": trade_request.get("symbol"),
                "side": trade_request.get("side"),
                "approved": True,
                "reason": "Trade approved.",
            },
            "reject-reason": {
                "symbol": trade_request.get("symbol"),
                "side": trade_request.get("side"),
                "rejected": False,
                "reason": "No rejection reason.",
            },
            "risk-handoff": {
                "symbol": trade_request.get("symbol"),
                "side": trade_request.get("side"),
                "allowed": True,
                "reason": "Trade allowed.",
                "position_size": 10.0,
                "entry_price": trade_request.get("entry_price"),
                "stop_loss_price": trade_request.get("stop_loss_price"),
                "take_profit_price": trade_request.get("take_profit_price"),
                "risk_amount": 100.0,
                "risk_percent": trade_request.get("risk_percent"),
                "execution_ready": True,
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


class FailingRiskAgent:
    name = "risk-agent"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Risk agent failed.",
            data={
                "reason": "risk rejected",
            },
            metadata={},
        )


class BrokenRiskAgent:
    name = "broken-risk-agent"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Risk agent exploded.")


def sample_trade_request():
    return {
        "symbol": "xauusd",
        "side": "buy",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "take_profit_price": 2045.0,
    }


def test_risk_trade_request_defaults():
    request = RiskTradeRequest()

    assert request.to_trade_request() == {
        "symbol": "XAUUSD",
        "side": "buy",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "take_profit_price": 2045.0,
    }


def test_risk_trade_request_normalizes_values():
    request = RiskTradeRequest(
        symbol="xauusd",
        side="BUY",
        account_balance=10_000.0,
        risk_percent=0.01,
        entry_price=2025.0,
        stop_loss_price=2015.0,
        take_profit_price=2045.0,
    )

    assert request.to_payload() == {
        "trade_request": {
            "symbol": "XAUUSD",
            "side": "buy",
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
            "entry_price": 2025.0,
            "stop_loss_price": 2015.0,
            "take_profit_price": 2045.0,
        }
    }


def test_risk_trade_request_accepts_sell_directional_stop_loss():
    request = RiskTradeRequest(
        symbol="XAUUSD",
        side="sell",
        account_balance=10_000.0,
        risk_percent=0.01,
        entry_price=2025.0,
        stop_loss_price=2035.0,
        take_profit_price=2000.0,
    )

    assert request.to_trade_request()["side"] == "sell"
    assert request.to_trade_request()["stop_loss_price"] == 2035.0


def test_risk_trade_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        RiskTradeRequest(symbol="")

    with pytest.raises(ValueError):
        RiskTradeRequest(side="hold")

    with pytest.raises(ValueError):
        RiskTradeRequest(account_balance=0)

    with pytest.raises(ValueError):
        RiskTradeRequest(risk_percent=0)

    with pytest.raises(ValueError):
        RiskTradeRequest(entry_price=0)

    with pytest.raises(ValueError):
        RiskTradeRequest(stop_loss_price=0)


def test_risk_trade_request_rejects_invalid_buy_stop_loss():
    with pytest.raises(ValueError, match="Buy trade stop loss"):
        RiskTradeRequest(
            side="buy",
            entry_price=2025.0,
            stop_loss_price=2030.0,
        )


def test_risk_trade_request_rejects_invalid_sell_stop_loss():
    with pytest.raises(ValueError, match="Sell trade stop loss"):
        RiskTradeRequest(
            side="sell",
            entry_price=2025.0,
            stop_loss_price=2015.0,
        )


def test_build_risk_trade_request():
    request = build_risk_trade_request(
        symbol="xauusd",
        side="buy",
        account_balance=10_000.0,
        risk_percent=0.01,
        entry_price=2025.0,
        stop_loss_price=2015.0,
        take_profit_price=2045.0,
    )

    assert isinstance(request, RiskTradeRequest)
    assert request.to_trade_request()["symbol"] == "XAUUSD"
    assert request.to_trade_request()["side"] == "buy"


def test_normalize_trade_request_preserves_extra_fields():
    normalized = normalize_trade_request(
        {
            **sample_trade_request(),
            "strategy_id": "strategy-1",
        }
    )

    assert normalized["symbol"] == "XAUUSD"
    assert normalized["side"] == "buy"
    assert normalized["entry_price"] == 2025.0
    assert normalized["strategy_id"] == "strategy-1"


def test_normalize_trade_request_rejects_non_dict():
    with pytest.raises(ValueError, match="Trade request"):
        normalize_trade_request("bad")


def test_risk_agent_operation_success():
    agent = SuccessfulRiskAgent()

    response = risk_agent_operation(
        agent,
        action="risk-handoff",
        payload={
            "trade_request": {
                "symbol": "XAUUSD",
                "side": "buy",
                "account_balance": 10_000.0,
                "risk_percent": 0.01,
                "entry_price": 2025.0,
                "stop_loss_price": 2015.0,
                "take_profit_price": 2045.0,
            },
        },
        success_message="Risk handoff generated.",
        failure_message="Risk handoff failed.",
        request_id="risk-request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Risk handoff generated."
    assert payload["data"]["action"] == "risk-handoff"
    assert payload["data"]["agent"] == "risk-agent"
    assert payload["data"]["result"]["allowed"] is True
    assert payload["metadata"]["request_id"] == "risk-request-1"


def test_risk_agent_operation_failure():
    response = risk_agent_operation(
        FailingRiskAgent(),
        action="risk-handoff",
        payload={
            "trade_request": sample_trade_request(),
        },
        success_message="Risk handoff generated.",
        failure_message="Risk handoff failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Risk handoff failed."
    assert payload["errors"][0]["code"] == "RISK_AGENT_ERROR"
    assert payload["errors"][0]["message"] == "Risk agent failed."
    assert payload["data"]["result"] == {
        "reason": "risk rejected",
    }


def test_risk_agent_operation_exception():
    response = risk_agent_operation(
        BrokenRiskAgent(),
        action="risk-handoff",
        payload={
            "trade_request": sample_trade_request(),
        },
        success_message="Risk handoff generated.",
        failure_message="Risk handoff failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Risk handoff failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Risk agent exploded."


def test_api_position_size_success():
    agent = SuccessfulRiskAgent()

    response = api_position_size(
        agent,
        trade_request=sample_trade_request(),
        request_id="position-size-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Position size calculated."
    assert payload["data"]["action"] == "position-size"
    assert payload["data"]["result"]["position_size"] == 10.0
    assert payload["data"]["result"]["risk_amount"] == 100.0
    assert payload["metadata"]["request_id"] == "position-size-1"

    assert agent.calls[0]["payload"]["trade_request"]["symbol"] == "XAUUSD"


def test_api_position_size_validation_failure():
    response = api_position_size(
        SuccessfulRiskAgent(),
        trade_request="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "trade_request"


def test_api_assess_trade_success():
    response = api_assess_trade(
        SuccessfulRiskAgent(),
        trade_request=sample_trade_request(),
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trade risk assessed."
    assert payload["data"]["action"] == "assess-trade"
    assert payload["data"]["result"]["allowed"] is True


def test_api_approve_trade_success():
    response = api_approve_trade(
        SuccessfulRiskAgent(),
        trade_request=sample_trade_request(),
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trade approval completed."
    assert payload["data"]["action"] == "approve-trade"
    assert payload["data"]["result"]["approved"] is True


def test_api_reject_reason_success():
    response = api_reject_reason(
        SuccessfulRiskAgent(),
        trade_request=sample_trade_request(),
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Reject reason generated."
    assert payload["data"]["action"] == "reject-reason"
    assert payload["data"]["result"]["rejected"] is False


def test_api_risk_handoff_success():
    response = api_risk_handoff(
        SuccessfulRiskAgent(),
        trade_request=sample_trade_request(),
        request_id="risk-handoff-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Risk handoff generated."
    assert payload["data"]["action"] == "risk-handoff"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["side"] == "buy"
    assert payload["data"]["result"]["allowed"] is True
    assert payload["data"]["result"]["execution_ready"] is True
    assert payload["metadata"]["request_id"] == "risk-handoff-1"