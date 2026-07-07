"""
Full trade workflow integration tests.

Validates the complete AQOS flow:

Market → Strategy → Risk → Execution
"""

from aqos.agents import (
    AgentOrchestrator,
    ExecutionAgent,
    MarketAgent,
    RiskAgent,
    StrategyAgent,
)
from aqos.services import BrokerService


def test_manual_full_trade_workflow(
    market_agent: MarketAgent,
    strategy_agent: StrategyAgent,
    risk_agent: RiskAgent,
    execution_agent: ExecutionAgent,
    broker_service: BrokerService,
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
    assert market_result.data["symbol"] == integration_symbol
    assert market_result.data["regime"] == "bullish"
    assert market_result.data["trend"] == "uptrend"

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
    assert strategy_result.data["signal"] == "buy"
    assert strategy_result.data["should_enter"] is True

    risk_result = risk_agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": {
                "symbol": strategy_result.data["symbol"],
                "side": strategy_result.data["signal"],
                "account_balance": integration_account_balance,
                "risk_percent": integration_risk_percent,
                "entry_price": strategy_result.data["entry_price"],
                "stop_loss_price": strategy_result.data["stop_loss_price"],
                "take_profit_price": strategy_result.data["take_profit_price"],
            },
        },
    )

    assert risk_result.success is True
    assert risk_result.data["allowed"] is True
    assert risk_result.data["execution_ready"] is True
    assert risk_result.data["position_size"] > 0

    execution_result = execution_agent.execute(
        action="execute-trade",
        payload={
            "trade": risk_result.data,
        },
    )

    assert execution_result.success is True
    assert execution_result.data["symbol"] == integration_symbol
    assert execution_result.data["side"] == "buy"
    assert execution_result.data["status"] == "open"
    assert execution_result.data["quantity"] == risk_result.data["position_size"]

    orders = broker_service.list_orders()
    positions = broker_service.list_positions()

    assert len(orders) == 1
    assert len(positions) == 0
    assert orders[0].symbol == integration_symbol
    assert orders[0].side == "buy"
    assert orders[0].status == "open"


def test_orchestrator_full_trade_workflow(
    agent_orchestrator: AgentOrchestrator,
    broker_service: BrokerService,
    integration_symbol: str,
    integration_timeframe: str,
    integration_account_balance: float,
    integration_risk_percent: float,
):
    result = agent_orchestrator.execute(
        action="trade-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "account_balance": integration_account_balance,
            "risk_percent": integration_risk_percent,
        },
        metadata={
            "request_id": "integration-full-trade",
        },
    )

    assert result.success is True
    assert result.message == "Trade workflow completed."
    assert result.metadata["request_id"] == "integration-full-trade"

    assert result.data["market_state"]["symbol"] == integration_symbol
    assert result.data["market_state"]["timeframe"] == integration_timeframe
    assert result.data["market_state"]["regime"] == "bullish"
    assert result.data["market_state"]["trend"] == "uptrend"

    assert result.data["strategy_handoff"]["signal"] == "buy"
    assert result.data["strategy_handoff"]["should_enter"] is True

    assert result.data["trade_request"]["symbol"] == integration_symbol
    assert result.data["trade_request"]["side"] == "buy"

    assert result.data["risk_handoff"]["allowed"] is True
    assert result.data["risk_handoff"]["execution_ready"] is True
    assert result.data["risk_handoff"]["position_size"] > 0

    assert result.data["execution"]["symbol"] == integration_symbol
    assert result.data["execution"]["side"] == "buy"
    assert result.data["execution"]["status"] == "open"

    orders = broker_service.list_orders()
    positions = broker_service.list_positions()

    assert len(orders) == 1
    assert len(positions) == 0
    assert orders[0].symbol == integration_symbol
    assert orders[0].status == "open"


def test_orchestrator_full_trade_workflow_creates_order(
    agent_orchestrator: AgentOrchestrator,
    broker_service: BrokerService,
    integration_symbol: str,
    integration_timeframe: str,
):
    result = agent_orchestrator.execute(
        action="trade-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert result.success is True

    orders = broker_service.list_orders()
    positions = broker_service.list_positions()

    assert len(orders) == 1
    assert len(positions) == 0

    assert orders[0].symbol == integration_symbol
    assert orders[0].side == "buy"
    assert orders[0].status == "open"


def test_orchestrator_risk_execution_workflow(
    agent_orchestrator: AgentOrchestrator,
    broker_service: BrokerService,
    integration_symbol: str,
):
    risk_handoff = {
        "symbol": integration_symbol,
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

    result = agent_orchestrator.execute(
        action="risk-execution-workflow",
        payload={
            "risk_handoff": risk_handoff,
        },
    )

    assert result.success is True
    assert result.message == "Risk execution workflow completed."
    assert result.data["risk_handoff"] == risk_handoff
    assert result.data["execution"]["symbol"] == integration_symbol
    assert result.data["execution"]["side"] == "buy"
    assert result.data["execution"]["quantity"] == 10.0
    assert result.data["execution"]["status"] == "open"

    orders = broker_service.list_orders()
    positions = broker_service.list_positions()

    assert len(orders) == 1
    assert len(positions) == 0
    assert orders[0].symbol == integration_symbol
    assert orders[0].side == "buy"
    assert orders[0].status == "open"


def test_orchestrator_trade_workflow_fails_when_market_data_missing():
    orchestrator = AgentOrchestrator()

    result = orchestrator.execute(
        action="trade-workflow",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert result.success is False
    assert result.message == "Market strategy workflow failed."
    assert result.data["failed_step"] == "market-state"


def test_risk_execution_workflow_rejects_not_ready_trade(
    agent_orchestrator: AgentOrchestrator,
    integration_symbol: str,
):
    risk_handoff = {
        "symbol": integration_symbol,
        "side": "buy",
        "allowed": False,
        "reason": "Risk rejected.",
        "position_size": None,
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "risk_amount": None,
        "risk_percent": 0.01,
        "execution_ready": False,
    }

    result = agent_orchestrator.execute(
        action="risk-execution-workflow",
        payload={
            "risk_handoff": risk_handoff,
        },
    )

    assert result.success is False
    assert result.message == "Risk execution workflow failed."
    assert result.data["failed_step"] == "execute-trade"
    assert result.data["result"]["success"] is False


def test_trade_workflow_output_can_be_saved_to_memory(
    agent_orchestrator: AgentOrchestrator,
    memory_agent,
    integration_symbol: str,
    integration_timeframe: str,
):
    trade_result = agent_orchestrator.execute(
        action="trade-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert trade_result.success is True

    memory_result = memory_agent.execute(
        action="trade-memory",
        payload={
            "memory_id": "trade-workflow-1",
            "symbol": trade_result.data["execution"]["symbol"],
            "side": trade_result.data["execution"]["side"],
            "outcome": "open",
            "importance": 0.8,
            "metadata": {
                "order_id": trade_result.data["execution"].get("order_id"),
                "price": trade_result.data["execution"].get("price"),
            },
        },
    )

    assert memory_result.success is True
    assert memory_result.data["memory_id"] == "trade-workflow-1"
    assert memory_result.data["memory_type"] == "trade"

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "XAUUSD trade",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1