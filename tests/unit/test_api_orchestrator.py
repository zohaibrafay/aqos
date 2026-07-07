"""
Unit tests for AQOS API orchestrator operations.
"""

from types import SimpleNamespace

import pytest

from aqos.api import (
    BacktestWorkflowRequest,
    MarketStrategyWorkflowRequest,
    MemoryWorkflowRequest,
    OrchestratorRouteRequest,
    ResearchWorkflowRequest,
    RiskExecutionWorkflowRequest,
    StrategyRiskWorkflowRequest,
    TradeWorkflowRequest,
    api_backtest_workflow,
    api_market_strategy_workflow,
    api_memory_workflow,
    api_orchestrator_route,
    api_research_workflow,
    api_risk_execution_workflow,
    api_strategy_risk_workflow,
    api_trade_workflow,
    orchestrator_operation,
)


class SuccessfulOrchestrator:
    name = "agent-orchestrator"

    def __init__(self):
        self.calls = []

    def execute(self, action, payload=None, metadata=None):
        payload = payload or {}

        self.calls.append(
            {
                "action": action,
                "payload": payload,
                "metadata": metadata,
            }
        )

        data_by_action = {
            "route": {
                "agent": payload.get("agent"),
                "action": payload.get("action"),
                "result": {
                    "success": True,
                },
            },
            "market-strategy-workflow": {
                "market_state": {
                    "symbol": payload.get("symbol"),
                    "timeframe": payload.get("timeframe"),
                    "regime": "bullish",
                    "trend": "uptrend",
                },
                "strategy_handoff": {
                    "symbol": payload.get("symbol"),
                    "signal": "buy",
                    "should_enter": True,
                },
            },
            "strategy-risk-workflow": {
                "strategy_handoff": payload.get("strategy_handoff"),
                "trade_request": {
                    "symbol": payload.get("strategy_handoff", {}).get("symbol"),
                    "side": payload.get("strategy_handoff", {}).get("signal"),
                },
                "risk_handoff": {
                    "allowed": True,
                    "execution_ready": True,
                    "position_size": 10.0,
                },
            },
            "risk-execution-workflow": {
                "risk_handoff": payload.get("risk_handoff"),
                "execution": {
                    "symbol": payload.get("risk_handoff", {}).get("symbol"),
                    "side": payload.get("risk_handoff", {}).get("side"),
                    "status": "open",
                },
            },
            "trade-workflow": {
                "market_state": {
                    "symbol": payload.get("symbol"),
                    "timeframe": payload.get("timeframe"),
                },
                "strategy_handoff": {
                    "signal": "buy",
                    "should_enter": True,
                },
                "risk_handoff": {
                    "allowed": True,
                    "execution_ready": True,
                },
                "execution": {
                    "symbol": payload.get("symbol"),
                    "side": "buy",
                    "status": "open",
                },
            },
            "research-workflow": {
                "hypothesis": {
                    "symbol": payload.get("symbol"),
                    "timeframe": payload.get("timeframe"),
                    "hypothesis": "Market regime can improve strategy quality.",
                },
                "experiment_plan": {
                    "name": payload.get("experiment_name"),
                    "metric": payload.get("metric"),
                },
            },
            "backtest-workflow": {
                "backtest": {
                    "name": payload.get("name"),
                    "total_profit": 75.0,
                    "total_trades": 3,
                    "metadata": payload.get("metadata", {}),
                },
                "report": {
                    "name": payload.get("name"),
                    "metrics": {
                        "total_profit": 75.0,
                        "total_trades": 3,
                    },
                },
            },
            "memory-workflow": {
                "remember": {
                    "memory_id": payload.get("memory_id"),
                    "memory_type": payload.get("memory_type"),
                },
                "recall": {
                    "count": 1,
                    "results": [
                        {
                            "record": {
                                "memory_id": payload.get("memory_id"),
                            }
                        }
                    ],
                },
            },
        }

        return SimpleNamespace(
            success=True,
            message=f"{action} completed.",
            data=data_by_action[action],
            metadata=metadata or {},
        )


class FailingOrchestrator:
    name = "agent-orchestrator"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Orchestrator failed.",
            data={
                "failed_step": action,
            },
            metadata={},
        )


class BrokenOrchestrator:
    name = "broken-orchestrator"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Orchestrator exploded.")


def sample_strategy_handoff():
    return {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "signal": "buy",
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "take_profit_price": 2045.0,
        "should_enter": True,
    }


def sample_risk_handoff():
    return {
        "symbol": "XAUUSD",
        "side": "buy",
        "allowed": True,
        "position_size": 10.0,
        "entry_price": 2025.0,
        "stop_loss_price": 2015.0,
        "risk_amount": 100.0,
        "risk_percent": 0.01,
        "execution_ready": True,
    }


def test_orchestrator_route_request_to_payload():
    request = OrchestratorRouteRequest(
        agent=" market ",
        action=" health ",
        payload={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == {
        "agent": "market",
        "action": "health",
        "payload": {
            "symbol": "XAUUSD",
        },
    }


def test_orchestrator_route_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        OrchestratorRouteRequest(agent="", action="health")

    with pytest.raises(ValueError):
        OrchestratorRouteRequest(agent="market", action="")

    with pytest.raises(ValueError):
        OrchestratorRouteRequest(agent="market", action="health", payload=[])


def test_market_strategy_workflow_request_to_payload():
    request = MarketStrategyWorkflowRequest(
        symbol="xauusd",
        timeframe="h1",
    )

    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_strategy_risk_workflow_request_to_payload():
    request = StrategyRiskWorkflowRequest(
        strategy_handoff=sample_strategy_handoff(),
        account_balance=10_000.0,
        risk_percent=0.01,
    )

    assert request.to_payload()["strategy_handoff"]["signal"] == "buy"
    assert request.to_payload()["account_balance"] == 10_000.0
    assert request.to_payload()["risk_percent"] == 0.01


def test_risk_execution_workflow_request_to_payload():
    request = RiskExecutionWorkflowRequest(
        risk_handoff=sample_risk_handoff(),
    )

    assert request.to_payload() == {
        "risk_handoff": sample_risk_handoff(),
    }


def test_trade_workflow_request_to_payload():
    request = TradeWorkflowRequest(
        symbol="xauusd",
        timeframe="h1",
        account_balance=10_000.0,
        risk_percent=0.01,
    )

    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
    }


def test_research_workflow_request_to_payload():
    request = ResearchWorkflowRequest(
        symbol="xauusd",
        timeframe="h1",
        signal_source=" news sentiment ",
        objective=" reduce false entries ",
        experiment_name=" news-filter ",
        metric=" win_rate ",
    )

    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "signal_source": "news sentiment",
        "objective": "reduce false entries",
        "experiment_name": "news-filter",
        "metric": "win_rate",
    }


def test_backtest_workflow_request_to_payload():
    request = BacktestWorkflowRequest(
        name=" run-1 ",
        profits=[
            100,
            -50,
            25,
        ],
        initial_balance=10_000,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == {
        "name": "run-1",
        "profits": [
            100.0,
            -50.0,
            25.0,
        ],
        "initial_balance": 10_000.0,
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_memory_workflow_request_to_payload():
    request = MemoryWorkflowRequest(
        memory_id=" memory-1 ",
        content=" Memory content. ",
        memory_type=" research ",
        importance=0.8,
        query=" market regime ",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == {
        "memory_id": "memory-1",
        "content": "Memory content.",
        "memory_type": "research",
        "importance": 0.8,
        "metadata": {
            "symbol": "XAUUSD",
        },
        "query": "market regime",
    }


def test_workflow_requests_reject_invalid_values():
    with pytest.raises(ValueError):
        MarketStrategyWorkflowRequest(symbol="")

    with pytest.raises(ValueError):
        StrategyRiskWorkflowRequest(strategy_handoff=[])

    with pytest.raises(ValueError):
        RiskExecutionWorkflowRequest(risk_handoff=[])

    with pytest.raises(ValueError):
        TradeWorkflowRequest(account_balance=0)

    with pytest.raises(ValueError):
        ResearchWorkflowRequest(signal_source="")

    with pytest.raises(ValueError):
        BacktestWorkflowRequest(profits=[])

    with pytest.raises(ValueError):
        MemoryWorkflowRequest(memory_id="", content="Memory.")

    with pytest.raises(ValueError):
        MemoryWorkflowRequest(memory_id="memory-1", content="")


def test_orchestrator_operation_success():
    orchestrator = SuccessfulOrchestrator()

    response = orchestrator_operation(
        orchestrator,
        action="trade-workflow",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
        success_message="Trade workflow completed.",
        failure_message="Trade workflow failed.",
        request_id="orchestrator-request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trade workflow completed."
    assert payload["data"]["action"] == "trade-workflow"
    assert payload["data"]["orchestrator"] == "agent-orchestrator"
    assert payload["data"]["result"]["execution"]["status"] == "open"
    assert payload["metadata"]["request_id"] == "orchestrator-request-1"

    assert orchestrator.calls[0]["metadata"] == {
        "request_id": "orchestrator-request-1",
    }


def test_orchestrator_operation_failure():
    response = orchestrator_operation(
        FailingOrchestrator(),
        action="trade-workflow",
        payload={
            "symbol": "XAUUSD",
        },
        success_message="Trade workflow completed.",
        failure_message="Trade workflow failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Trade workflow failed."
    assert payload["errors"][0]["code"] == "ORCHESTRATOR_ERROR"
    assert payload["errors"][0]["message"] == "Orchestrator failed."
    assert payload["data"]["result"] == {
        "failed_step": "trade-workflow",
    }


def test_orchestrator_operation_exception():
    response = orchestrator_operation(
        BrokenOrchestrator(),
        action="trade-workflow",
        payload={
            "symbol": "XAUUSD",
        },
        success_message="Trade workflow completed.",
        failure_message="Trade workflow failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Trade workflow failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Orchestrator exploded."


def test_api_orchestrator_route_success():
    orchestrator = SuccessfulOrchestrator()

    response = api_orchestrator_route(
        orchestrator,
        agent="market",
        action="health",
        payload={
            "symbol": "XAUUSD",
        },
        request_id="route-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Orchestrator route completed."
    assert payload["data"]["action"] == "route"
    assert payload["data"]["result"]["agent"] == "market"
    assert payload["metadata"]["request_id"] == "route-1"

    assert orchestrator.calls[0]["payload"]["agent"] == "market"


def test_api_orchestrator_route_validation_failure():
    response = api_orchestrator_route(
        SuccessfulOrchestrator(),
        agent="",
        action="health",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "route"


def test_api_market_strategy_workflow_success():
    response = api_market_strategy_workflow(
        SuccessfulOrchestrator(),
        symbol="xauusd",
        timeframe="h1",
        request_id="market-strategy-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Market strategy workflow completed."
    assert payload["data"]["action"] == "market-strategy-workflow"
    assert payload["data"]["result"]["market_state"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["strategy_handoff"]["signal"] == "buy"
    assert payload["metadata"]["request_id"] == "market-strategy-1"


def test_api_market_strategy_workflow_validation_failure():
    response = api_market_strategy_workflow(
        SuccessfulOrchestrator(),
        symbol="",
        timeframe="H1",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["field"] == "market_strategy_workflow"


def test_api_strategy_risk_workflow_success():
    response = api_strategy_risk_workflow(
        SuccessfulOrchestrator(),
        strategy_handoff=sample_strategy_handoff(),
        account_balance=10_000.0,
        risk_percent=0.01,
        request_id="strategy-risk-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Strategy risk workflow completed."
    assert payload["data"]["action"] == "strategy-risk-workflow"
    assert payload["data"]["result"]["risk_handoff"]["allowed"] is True
    assert payload["metadata"]["request_id"] == "strategy-risk-1"


def test_api_strategy_risk_workflow_validation_failure():
    response = api_strategy_risk_workflow(
        SuccessfulOrchestrator(),
        strategy_handoff=[],
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["field"] == "strategy_risk_workflow"


def test_api_risk_execution_workflow_success():
    response = api_risk_execution_workflow(
        SuccessfulOrchestrator(),
        risk_handoff=sample_risk_handoff(),
        request_id="risk-execution-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Risk execution workflow completed."
    assert payload["data"]["action"] == "risk-execution-workflow"
    assert payload["data"]["result"]["execution"]["status"] == "open"
    assert payload["metadata"]["request_id"] == "risk-execution-1"


def test_api_trade_workflow_success():
    response = api_trade_workflow(
        SuccessfulOrchestrator(),
        symbol="xauusd",
        timeframe="h1",
        account_balance=10_000.0,
        risk_percent=0.01,
        request_id="trade-workflow-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trade workflow completed."
    assert payload["data"]["action"] == "trade-workflow"
    assert payload["data"]["result"]["execution"]["status"] == "open"
    assert payload["metadata"]["request_id"] == "trade-workflow-1"


def test_api_research_workflow_success():
    response = api_research_workflow(
        SuccessfulOrchestrator(),
        symbol="xauusd",
        timeframe="h1",
        signal_source="market regime",
        objective="improve strategy quality",
        experiment_name="regime-test",
        metric="win_rate",
        request_id="research-workflow-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Research workflow completed."
    assert payload["data"]["action"] == "research-workflow"
    assert payload["data"]["result"]["experiment_plan"]["name"] == "regime-test"
    assert payload["metadata"]["request_id"] == "research-workflow-1"


def test_api_backtest_workflow_success():
    response = api_backtest_workflow(
        SuccessfulOrchestrator(),
        name="api-backtest-1",
        profits=[
            100.0,
            -50.0,
            25.0,
        ],
        initial_balance=10_000.0,
        metadata={
            "symbol": "XAUUSD",
        },
        request_id="backtest-workflow-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Backtest workflow completed."
    assert payload["data"]["action"] == "backtest-workflow"
    assert payload["data"]["result"]["backtest"]["name"] == "api-backtest-1"
    assert payload["data"]["result"]["report"]["metrics"]["total_profit"] == 75.0
    assert payload["metadata"]["request_id"] == "backtest-workflow-1"


def test_api_memory_workflow_success():
    response = api_memory_workflow(
        SuccessfulOrchestrator(),
        memory_id="memory-1",
        content="Research memory content.",
        memory_type="research",
        importance=0.8,
        query="research memory",
        metadata={
            "symbol": "XAUUSD",
        },
        request_id="memory-workflow-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Memory workflow completed."
    assert payload["data"]["action"] == "memory-workflow"
    assert payload["data"]["result"]["remember"]["memory_id"] == "memory-1"
    assert payload["data"]["result"]["recall"]["count"] == 1
    assert payload["metadata"]["request_id"] == "memory-workflow-1"


def test_api_memory_workflow_validation_failure():
    response = api_memory_workflow(
        SuccessfulOrchestrator(),
        memory_id="",
        content="Memory.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["field"] == "memory_workflow"