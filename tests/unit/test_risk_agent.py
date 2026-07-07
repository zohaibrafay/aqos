"""
Unit tests for RiskAgent.
"""

from aqos.agents import (
    AgentBase,
    RiskAgent,
)


def valid_buy_trade_request() -> dict:
    return {
        "symbol": "XAUUSD",
        "side": "buy",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
        "entry_price": 2000.0,
        "stop_loss_price": 1990.0,
    }


def valid_sell_trade_request() -> dict:
    return {
        "symbol": "XAUUSD",
        "side": "sell",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
        "entry_price": 2000.0,
        "stop_loss_price": 2010.0,
    }


def test_risk_agent_is_agent_base_instance():
    agent = RiskAgent()

    assert isinstance(agent, AgentBase)


def test_risk_agent_name():
    agent = RiskAgent()

    assert agent.name == "risk-agent"


def test_risk_agent_description():
    agent = RiskAgent()

    assert agent.description == (
        "Agent for trade risk assessment, position sizing, and approval checks."
    )


def test_available_actions():
    agent = RiskAgent()

    assert agent.available_actions() == [
        "approve-trade",
        "assess-trade",
        "health",
        "position-size",
        "reject-reason",
        "risk-handoff",
    ]


def test_health():
    agent = RiskAgent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Risk agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["supported_sides"] == [
        "buy",
        "sell",
    ]
    assert result.data["default_max_risk_percent"] == 0.02


def test_position_size_buy():
    agent = RiskAgent()

    result = agent.execute(
        action="position-size",
        payload={
            "trade_request": valid_buy_trade_request(),
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Position size calculated."
    assert result.data["account_balance"] == 10_000.0
    assert result.data["risk_percent"] == 0.01
    assert result.data["risk_amount"] == 100.0
    assert result.data["risk_per_unit"] == 10.0
    assert result.data["position_size"] == 10.0
    assert result.metadata["request_id"] == "req-1"


def test_position_size_sell():
    agent = RiskAgent()

    result = agent.execute(
        action="position-size",
        payload={
            "trade_request": valid_sell_trade_request(),
        },
    )

    assert result.success is True
    assert result.data["risk_amount"] == 100.0
    assert result.data["risk_per_unit"] == 10.0
    assert result.data["position_size"] == 10.0


def test_position_size_missing_trade_request():
    agent = RiskAgent()

    result = agent.execute(
        action="position-size",
        payload={},
    )

    assert result.success is False
    assert result.message == "Missing required payload key: trade_request"


def test_position_size_rejects_invalid_trade_request_type():
    agent = RiskAgent()

    result = agent.execute(
        action="position-size",
        payload={
            "trade_request": "invalid",
        },
    )

    assert result.success is False
    assert result.message == "Trade request must be a dictionary."


def test_position_size_rejects_missing_key():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request.pop("entry_price")

    result = agent.execute(
        action="position-size",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is False
    assert result.message == "Trade request is missing required key: entry_price"


def test_position_size_rejects_zero_risk_per_unit():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["stop_loss_price"] = 2000.0

    result = agent.execute(
        action="position-size",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is False
    assert result.message == "Buy trade stop loss must be below entry price."


def test_assess_trade_allowed():
    agent = RiskAgent()

    result = agent.execute(
        action="assess-trade",
        payload={
            "trade_request": valid_buy_trade_request(),
        },
    )

    assert result.success is True
    assert result.message == "Trade risk assessed."
    assert result.data["allowed"] is True
    assert result.data["reason"] == "Trade allowed."
    assert result.data["position_size"] == 10.0
    assert result.data["risk_amount"] == 100.0


def test_assess_trade_rejected_invalid_side():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["side"] = "hold"

    result = agent.execute(
        action="assess-trade",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.message == "Trade risk assessed."
    assert result.data["allowed"] is False
    assert result.data["reason"] == "Side must be buy or sell."
    assert result.data["position_size"] is None


def test_assess_trade_rejected_risk_too_high():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["risk_percent"] = 0.03

    result = agent.execute(
        action="assess-trade",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["reason"] == "Risk percent exceeds maximum allowed risk percent."


def test_assess_trade_with_custom_max_risk_percent():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["risk_percent"] = 0.03
    trade_request["max_risk_percent"] = 0.05

    result = agent.execute(
        action="assess-trade",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["allowed"] is True
    assert result.data["position_size"] == 30.0


def test_assess_trade_rejected_position_size_too_large():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["max_position_size"] = 5.0

    result = agent.execute(
        action="assess-trade",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["reason"] == "Position size exceeds maximum allowed size."


def test_assess_trade_rejected_invalid_buy_stop_loss():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["stop_loss_price"] = 2010.0

    result = agent.execute(
        action="assess-trade",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["reason"] == "Buy trade stop loss must be below entry price."


def test_assess_trade_rejected_invalid_sell_stop_loss():
    agent = RiskAgent()

    trade_request = valid_sell_trade_request()
    trade_request["stop_loss_price"] = 1990.0

    result = agent.execute(
        action="assess-trade",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["reason"] == "Sell trade stop loss must be above entry price."


def test_approve_trade_allowed():
    agent = RiskAgent()

    result = agent.execute(
        action="approve-trade",
        payload={
            "trade_request": valid_buy_trade_request(),
        },
    )

    assert result.success is True
    assert result.message == "Trade approval checked."
    assert result.data["approved"] is True
    assert result.data["reason"] == "Trade allowed."
    assert result.data["position_size"] == 10.0


def test_approve_trade_rejected():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["risk_percent"] = 0.03

    result = agent.execute(
        action="approve-trade",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["approved"] is False
    assert result.data["reason"] == "Risk percent exceeds maximum allowed risk percent."


def test_reject_reason_for_allowed_trade():
    agent = RiskAgent()

    result = agent.execute(
        action="reject-reason",
        payload={
            "trade_request": valid_buy_trade_request(),
        },
    )

    assert result.success is True
    assert result.message == "Risk rejection reason generated."
    assert result.data["allowed"] is True
    assert result.data["reason"] == "Trade is not rejected."


def test_reject_reason_for_rejected_trade():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["side"] = "invalid"

    result = agent.execute(
        action="reject-reason",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["reason"] == "Side must be buy or sell."


def test_risk_handoff_allowed():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["take_profit_price"] = 2020.0

    result = agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": trade_request,
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Risk handoff generated."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["side"] == "buy"
    assert result.data["allowed"] is True
    assert result.data["reason"] == "Trade allowed."
    assert result.data["position_size"] == 10.0
    assert result.data["entry_price"] == 2000.0
    assert result.data["stop_loss_price"] == 1990.0
    assert result.data["take_profit_price"] == 2020.0
    assert result.data["execution_ready"] is True
    assert result.metadata["request_id"] == "req-1"


def test_risk_handoff_rejected():
    agent = RiskAgent()

    trade_request = valid_buy_trade_request()
    trade_request["risk_percent"] = 0.03

    result = agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": trade_request,
        },
    )

    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["execution_ready"] is False
    assert result.data["position_size"] is None
    assert result.data["reason"] == "Risk percent exceeds maximum allowed risk percent."


def test_unsupported_action():
    agent = RiskAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"


def test_rejects_invalid_default_max_risk_percent():
    try:
        RiskAgent(default_max_risk_percent=0)
        created = True
    except ValueError as exc:
        created = False
        message = str(exc)

    assert created is False
    assert message == "Risk percent must be between 0 and 1."