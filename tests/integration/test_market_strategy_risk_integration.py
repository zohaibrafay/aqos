"""
Market → Strategy → Risk integration tests.

Validates that market context can flow into strategy decisions and then
into risk-approved trade handoffs.
"""

from aqos.agents import (
    AgentOrchestrator,
    MarketAgent,
    RiskAgent,
    StrategyAgent,
)
from aqos.common import (
    DEFAULT_ACCOUNT_BALANCE,
    DEFAULT_RISK_PERCENT,
)


def build_trade_request_from_strategy_handoff(
    strategy_handoff: dict,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
) -> dict:
    """
    Build a risk trade request from a strategy handoff.
    """

    trade_request = {
        "symbol": strategy_handoff["symbol"],
        "side": strategy_handoff["signal"],
        "account_balance": account_balance,
        "risk_percent": risk_percent,
        "entry_price": strategy_handoff["entry_price"],
        "stop_loss_price": strategy_handoff["stop_loss_price"],
    }

    if strategy_handoff.get("take_profit_price") is not None:
        trade_request["take_profit_price"] = strategy_handoff["take_profit_price"]

    return trade_request


def test_market_state_feeds_strategy_handoff(
    market_agent: MarketAgent,
    strategy_agent: StrategyAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    market_result = market_agent.execute(
        action="market-state",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert market_result.success is True
    assert market_result.data["symbol"] == integration_symbol
    assert market_result.data["timeframe"] == integration_timeframe
    assert market_result.data["trend"] == "uptrend"
    assert market_result.data["regime"] == "bullish"

    market_state = {
        **market_result.data,
        "entry_price": market_result.data["close"],
    }

    strategy_result = strategy_agent.execute(
        action="handoff",
        payload={
            "market_state": market_state,
        },
    )

    assert strategy_result.success is True
    assert strategy_result.data["symbol"] == integration_symbol
    assert strategy_result.data["timeframe"] == integration_timeframe
    assert strategy_result.data["signal"] == "buy"
    assert strategy_result.data["should_enter"] is True
    assert strategy_result.data["entry_price"] == market_result.data["close"]
    assert strategy_result.data["stop_loss_price"] is not None
    assert strategy_result.data["take_profit_price"] is not None


def test_strategy_handoff_feeds_risk_agent(
    market_agent: MarketAgent,
    strategy_agent: StrategyAgent,
    risk_agent: RiskAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    market_result = market_agent.execute(
        action="market-state",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    market_state = {
        **market_result.data,
        "entry_price": market_result.data["close"],
    }

    strategy_result = strategy_agent.execute(
        action="handoff",
        payload={
            "market_state": market_state,
        },
    )

    trade_request = build_trade_request_from_strategy_handoff(
        strategy_handoff=strategy_result.data,
    )

    risk_result = risk_agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": trade_request,
        },
    )

    assert risk_result.success is True
    assert risk_result.data["symbol"] == integration_symbol
    assert risk_result.data["side"] == "buy"
    assert risk_result.data["allowed"] is True
    assert risk_result.data["execution_ready"] is True
    assert risk_result.data["entry_price"] == strategy_result.data["entry_price"]
    assert risk_result.data["stop_loss_price"] == strategy_result.data["stop_loss_price"]
    assert risk_result.data["risk_percent"] == DEFAULT_RISK_PERCENT
    assert risk_result.data["position_size"] > 0


def test_manual_market_strategy_risk_workflow(
    market_agent: MarketAgent,
    strategy_agent: StrategyAgent,
    risk_agent: RiskAgent,
    integration_symbol: str,
    integration_timeframe: str,
    integration_account_balance: float,
    integration_risk_percent: float,
):
    market_result = market_agent.execute(
        action="market-state",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert market_result.success is True

    strategy_result = strategy_agent.execute(
        action="handoff",
        payload={
            "market_state": {
                **market_result.data,
                "entry_price": market_result.data["close"],
            },
        },
    )

    assert strategy_result.success is True

    trade_request = build_trade_request_from_strategy_handoff(
        strategy_handoff=strategy_result.data,
        account_balance=integration_account_balance,
        risk_percent=integration_risk_percent,
    )

    risk_result = risk_agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": trade_request,
        },
    )

    assert risk_result.success is True
    assert risk_result.data["allowed"] is True
    assert risk_result.data["execution_ready"] is True
    assert risk_result.data["risk_amount"] == (
        integration_account_balance * integration_risk_percent
    )
    assert risk_result.data["position_size"] > 0


def test_orchestrator_market_strategy_workflow(
    agent_orchestrator: AgentOrchestrator,
    integration_symbol: str,
    integration_timeframe: str,
):
    result = agent_orchestrator.execute(
        action="market-strategy-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
        metadata={
            "request_id": "integration-market-strategy",
        },
    )

    assert result.success is True
    assert result.message == "Market strategy workflow completed."
    assert result.data["market_state"]["symbol"] == integration_symbol
    assert result.data["market_state"]["timeframe"] == integration_timeframe
    assert result.data["market_state"]["regime"] == "bullish"
    assert result.data["market_state"]["trend"] == "uptrend"
    assert result.data["strategy_handoff"]["signal"] == "buy"
    assert result.data["strategy_handoff"]["should_enter"] is True
    assert result.metadata["request_id"] == "integration-market-strategy"


def test_orchestrator_strategy_risk_workflow(
    agent_orchestrator: AgentOrchestrator,
    integration_symbol: str,
    integration_timeframe: str,
    integration_account_balance: float,
    integration_risk_percent: float,
):
    market_strategy_result = agent_orchestrator.execute(
        action="market-strategy-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert market_strategy_result.success is True

    result = agent_orchestrator.execute(
        action="strategy-risk-workflow",
        payload={
            "strategy_handoff": market_strategy_result.data["strategy_handoff"],
            "account_balance": integration_account_balance,
            "risk_percent": integration_risk_percent,
        },
        metadata={
            "request_id": "integration-strategy-risk",
        },
    )

    assert result.success is True
    assert result.message == "Strategy risk workflow completed."
    assert result.data["strategy_handoff"]["signal"] == "buy"
    assert result.data["trade_request"]["side"] == "buy"
    assert result.data["risk_handoff"]["allowed"] is True
    assert result.data["risk_handoff"]["execution_ready"] is True
    assert result.data["risk_handoff"]["position_size"] > 0
    assert result.metadata["request_id"] == "integration-strategy-risk"


def test_orchestrator_market_strategy_risk_chain(
    agent_orchestrator: AgentOrchestrator,
    integration_symbol: str,
    integration_timeframe: str,
):
    market_strategy_result = agent_orchestrator.execute(
        action="market-strategy-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert market_strategy_result.success is True

    strategy_risk_result = agent_orchestrator.execute(
        action="strategy-risk-workflow",
        payload={
            "strategy_handoff": market_strategy_result.data["strategy_handoff"],
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert strategy_risk_result.success is True
    assert strategy_risk_result.data["risk_handoff"]["symbol"] == integration_symbol
    assert strategy_risk_result.data["risk_handoff"]["side"] == "buy"
    assert strategy_risk_result.data["risk_handoff"]["allowed"] is True
    assert strategy_risk_result.data["risk_handoff"]["execution_ready"] is True


def test_strategy_risk_workflow_stops_on_hold_signal(
    agent_orchestrator: AgentOrchestrator,
):
    result = agent_orchestrator.execute(
        action="strategy-risk-workflow",
        payload={
            "strategy_handoff": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "signal": "hold",
                "should_enter": False,
                "should_exit": False,
                "entry_price": 2025.0,
                "stop_loss_price": None,
                "take_profit_price": None,
            },
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert result.success is False
    assert result.message == "Strategy signal is hold; no risk workflow required."
    assert result.data["strategy_handoff"]["signal"] == "hold"


def test_risk_rejects_invalid_buy_stop_after_strategy_like_handoff(
    risk_agent: RiskAgent,
):
    result = risk_agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": {
                "symbol": "XAUUSD",
                "side": "buy",
                "account_balance": 10_000.0,
                "risk_percent": 0.01,
                "entry_price": 2025.0,
                "stop_loss_price": 2030.0,
            },
        },
    )

    assert result.success is True
    assert result.data["allowed"] is False
    assert result.data["execution_ready"] is False
    assert "Buy trade stop loss must be below entry price." in result.data["reason"]