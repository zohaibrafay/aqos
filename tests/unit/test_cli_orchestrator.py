"""
Unit tests for AQOS CLI orchestrator workflow commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliBacktestWorkflowRequest,
    CliMarketStrategyWorkflowRequest,
    CliMemoryWorkflowRequest,
    CliOrchestratorRouteRequest,
    CliResearchWorkflowRequest,
    CliRiskExecutionWorkflowRequest,
    CliStrategyRiskWorkflowRequest,
    CliTradeWorkflowRequest,
    build_orchestrator_cli_output,
    cli_backtest_workflow,
    cli_market_strategy_workflow,
    cli_memory_workflow,
    cli_orchestrator_route,
    cli_research_workflow,
    cli_risk_execution_workflow,
    cli_strategy_risk_workflow,
    cli_trade_workflow,
    execute_orchestrator_operation,
)


def fake_orchestrator_route(orchestrator, route, request_id=None):
    return api_success(
        message="Route executed.",
        data={
            "orchestrator": orchestrator.name,
            "agent_name": route["agent_name"],
            "action": route["action"],
            "payload": route["payload"],
            "routed": True,
        },
        request_id=request_id,
    )


def fake_market_strategy_workflow(orchestrator, workflow, request_id=None):
    return api_success(
        message="Market strategy workflow completed.",
        data={
            "orchestrator": orchestrator.name,
            "symbol": workflow["symbol"],
            "timeframe": workflow["timeframe"],
            "signal": "buy",
            "entry_price": 2025.0,
        },
        request_id=request_id,
    )


def fake_strategy_risk_workflow(orchestrator, workflow, request_id=None):
    return api_success(
        message="Strategy risk workflow completed.",
        data={
            "orchestrator": orchestrator.name,
            "symbol": workflow["market_state"]["symbol"],
            "timeframe": workflow["market_state"]["timeframe"],
            "allowed": True,
            "risk_percent": workflow["risk_percent"],
        },
        request_id=request_id,
    )


def fake_risk_execution_workflow(orchestrator, workflow, request_id=None):
    return api_success(
        message="Risk execution workflow completed.",
        data={
            "orchestrator": orchestrator.name,
            "symbol": workflow["risk_handoff"]["symbol"],
            "side": workflow["risk_handoff"]["side"],
            "execution_ready": workflow["risk_handoff"]["execution_ready"],
            "order_id": "order-1",
        },
        request_id=request_id,
    )


def fake_trade_workflow(orchestrator, workflow, request_id=None):
    return api_success(
        message="Trade workflow completed.",
        data={
            "orchestrator": orchestrator.name,
            "symbol": workflow["symbol"],
            "timeframe": workflow["timeframe"],
            "account_balance": workflow["account_balance"],
            "risk_percent": workflow["risk_percent"],
            "order_id": "order-1",
        },
        request_id=request_id,
    )


def fake_research_workflow(orchestrator, workflow, request_id=None):
    return api_success(
        message="Research workflow completed.",
        data={
            "orchestrator": orchestrator.name,
            "symbol": workflow["symbol"],
            "timeframe": workflow["timeframe"],
            "signal_source": workflow["signal_source"],
            "hypothesis": "Market regime improves strategy quality.",
        },
        request_id=request_id,
    )


def fake_backtest_workflow(orchestrator, workflow, request_id=None):
    return api_success(
        message="Backtest workflow completed.",
        data={
            "orchestrator": orchestrator.name,
            "name": workflow["name"],
            "initial_balance": workflow["initial_balance"],
            "total_profit": 75.0,
            "total_trades": len(workflow["profits"]),
        },
        request_id=request_id,
    )


def fake_memory_workflow(orchestrator, workflow, request_id=None):
    return api_success(
        message="Memory workflow completed.",
        data={
            "orchestrator": orchestrator.name,
            "memory_id": workflow["memory_id"],
            "query": workflow["query"],
            "memory_type": workflow["memory_type"],
            "remembered": True,
            "recalled": True,
        },
        request_id=request_id,
    )


def fake_failure_orchestrator(orchestrator, route=None, request_id=None):
    return api_failure(
        message="Orchestrator command failed.",
        data={
            "orchestrator": orchestrator.name,
        },
        request_id=request_id,
    )


def test_cli_orchestrator_route_request_accepts_valid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliOrchestratorRouteRequest(
        orchestrator=orchestrator,
        agent_name=" market ",
        action=" health ",
        payload={
            "symbol": "XAUUSD",
        },
        metadata={
            "source": "test",
        },
        output_format="pretty-json",
        include_metadata=True,
        request_id="route-request-1",
    )

    assert request.orchestrator == orchestrator
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "route-request-1"
    assert request.to_route() == {
        "agent_name": "market",
        "action": "health",
        "payload": {
            "symbol": "XAUUSD",
        },
        "metadata": {
            "source": "test",
        },
    }


def test_cli_orchestrator_route_request_rejects_invalid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=None)

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=orchestrator, agent_name="")

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=orchestrator, action="")

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=orchestrator, payload=[])

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=orchestrator, metadata=[])

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=orchestrator, output_format="bad")

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=orchestrator, include_metadata="yes")

    with pytest.raises(ValueError):
        CliOrchestratorRouteRequest(orchestrator=orchestrator, request_id="")


def test_cli_market_strategy_workflow_request_to_workflow():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliMarketStrategyWorkflowRequest(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
    )

    assert request.to_workflow() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_cli_market_strategy_workflow_request_rejects_invalid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    with pytest.raises(ValueError):
        CliMarketStrategyWorkflowRequest(orchestrator=None)

    with pytest.raises(ValueError):
        CliMarketStrategyWorkflowRequest(orchestrator=orchestrator, symbol="")

    with pytest.raises(ValueError):
        CliMarketStrategyWorkflowRequest(orchestrator=orchestrator, timeframe="BAD")


def test_cli_strategy_risk_workflow_request_to_workflow():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliStrategyRiskWorkflowRequest(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
        regime=" bullish ",
        trend=" uptrend ",
        entry_price=2025.0,
        account_balance=10_000.0,
        risk_percent=0.01,
    )

    assert request.to_workflow() == {
        "market_state": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "regime": "bullish",
            "trend": "uptrend",
            "entry_price": 2025.0,
        },
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
    }


def test_cli_strategy_risk_workflow_request_rejects_invalid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    with pytest.raises(ValueError):
        CliStrategyRiskWorkflowRequest(orchestrator=None)

    with pytest.raises(ValueError):
        CliStrategyRiskWorkflowRequest(orchestrator=orchestrator, regime="")

    with pytest.raises(ValueError):
        CliStrategyRiskWorkflowRequest(orchestrator=orchestrator, entry_price=0)

    with pytest.raises(ValueError):
        CliStrategyRiskWorkflowRequest(orchestrator=orchestrator, risk_percent=0)


def test_cli_risk_execution_workflow_request_to_workflow():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliRiskExecutionWorkflowRequest(
        orchestrator=orchestrator,
        symbol="xauusd",
        side="BUY",
        allowed=True,
        reason=" Trade allowed. ",
        position_size=10.0,
        entry_price=2025.0,
        stop_loss_price=2015.0,
        take_profit_price=2045.0,
        risk_amount=100.0,
        risk_percent=0.01,
        execution_ready=True,
    )

    assert request.to_workflow() == {
        "risk_handoff": {
            "symbol": "XAUUSD",
            "side": "buy",
            "allowed": True,
            "reason": "Trade allowed.",
            "position_size": 10.0,
            "entry_price": 2025.0,
            "stop_loss_price": 2015.0,
            "take_profit_price": 2045.0,
            "risk_amount": 100.0,
            "risk_percent": 0.01,
            "execution_ready": True,
        },
    }


def test_cli_risk_execution_workflow_request_rejects_invalid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    with pytest.raises(ValueError):
        CliRiskExecutionWorkflowRequest(orchestrator=None)

    with pytest.raises(ValueError):
        CliRiskExecutionWorkflowRequest(orchestrator=orchestrator, side="hold")

    with pytest.raises(ValueError):
        CliRiskExecutionWorkflowRequest(orchestrator=orchestrator, allowed="yes")

    with pytest.raises(ValueError):
        CliRiskExecutionWorkflowRequest(orchestrator=orchestrator, reason="")

    with pytest.raises(ValueError):
        CliRiskExecutionWorkflowRequest(orchestrator=orchestrator, position_size=0)

    with pytest.raises(ValueError):
        CliRiskExecutionWorkflowRequest(orchestrator=orchestrator, execution_ready="yes")


def test_cli_trade_workflow_request_to_workflow():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliTradeWorkflowRequest(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
        account_balance=10_000.0,
        risk_percent=0.01,
    )

    assert request.to_workflow() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "account_balance": 10_000.0,
        "risk_percent": 0.01,
    }


def test_cli_research_workflow_request_to_workflow():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliResearchWorkflowRequest(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
        signal_source=" news sentiment ",
        objective=" reduce false entries ",
    )

    assert request.to_workflow() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "signal_source": "news sentiment",
        "objective": "reduce false entries",
    }


def test_cli_backtest_workflow_request_to_workflow():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliBacktestWorkflowRequest(
        orchestrator=orchestrator,
        name=" cli-backtest ",
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

    assert request.to_workflow() == {
        "name": "cli-backtest",
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


def test_cli_backtest_workflow_request_rejects_invalid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    with pytest.raises(ValueError):
        CliBacktestWorkflowRequest(orchestrator=None)

    with pytest.raises(ValueError):
        CliBacktestWorkflowRequest(orchestrator=orchestrator, name="")

    with pytest.raises(ValueError):
        CliBacktestWorkflowRequest(orchestrator=orchestrator, profits=[])

    with pytest.raises(ValueError):
        CliBacktestWorkflowRequest(orchestrator=orchestrator, profits=["bad"])

    with pytest.raises(ValueError):
        CliBacktestWorkflowRequest(orchestrator=orchestrator, metadata=[])


def test_cli_memory_workflow_request_to_workflow():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    request = CliMemoryWorkflowRequest(
        orchestrator=orchestrator,
        memory_id=" memory-1 ",
        content=" Important market observation. ",
        query=" market observation ",
        memory_type=" research ",
        importance=0.8,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_workflow() == {
        "memory_id": "memory-1",
        "content": "Important market observation.",
        "query": "market observation",
        "memory_type": "research",
        "importance": 0.8,
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_cli_memory_workflow_request_rejects_invalid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    with pytest.raises(ValueError):
        CliMemoryWorkflowRequest(
            orchestrator=None,
            memory_id="memory-1",
            content="Memory.",
            query="memory",
        )

    with pytest.raises(ValueError):
        CliMemoryWorkflowRequest(
            orchestrator=orchestrator,
            memory_id="",
            content="Memory.",
            query="memory",
        )

    with pytest.raises(ValueError):
        CliMemoryWorkflowRequest(
            orchestrator=orchestrator,
            memory_id="memory-1",
            content="",
            query="memory",
        )

    with pytest.raises(ValueError):
        CliMemoryWorkflowRequest(
            orchestrator=orchestrator,
            memory_id="memory-1",
            content="Memory.",
            query="",
        )

    with pytest.raises(ValueError):
        CliMemoryWorkflowRequest(
            orchestrator=orchestrator,
            memory_id="memory-1",
            content="Memory.",
            query="memory",
            importance=2,
        )

    with pytest.raises(ValueError):
        CliMemoryWorkflowRequest(
            orchestrator=orchestrator,
            memory_id="memory-1",
            content="Memory.",
            query="memory",
            metadata=[],
        )


def test_execute_orchestrator_operation_with_request_id():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    response = execute_orchestrator_operation(
        fake_orchestrator_route,
        orchestrator=orchestrator,
        route={
            "agent_name": "market",
            "action": "health",
            "payload": {},
        },
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["orchestrator"] == "agent-orchestrator"


def test_execute_orchestrator_operation_rejects_invalid_values():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    with pytest.raises(ValueError):
        execute_orchestrator_operation(
            "not-callable",
            orchestrator=orchestrator,
        )

    with pytest.raises(ValueError):
        execute_orchestrator_operation(
            fake_orchestrator_route,
            orchestrator=None,
        )


def test_build_orchestrator_cli_output_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    response = fake_orchestrator_route(
        orchestrator,
        {
            "agent_name": "market",
            "action": "health",
            "payload": {},
        },
        request_id="request-1",
    )

    cli_output = build_orchestrator_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Route executed." in cli_output.output
    assert "agent_name: market" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_orchestrator_cli_output_failure():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    response = fake_failure_orchestrator(orchestrator)

    cli_output = build_orchestrator_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Orchestrator command failed."


def test_cli_orchestrator_route_text_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_orchestrator_route(
        orchestrator=orchestrator,
        agent_name="market",
        action="health",
        payload={
            "symbol": "XAUUSD",
        },
        output_format="text",
        request_id="route-1",
        operation=fake_orchestrator_route,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Route executed." in cli_output.output
    assert "agent_name: market" in cli_output.output
    assert "action: health" in cli_output.output
    assert "routed: true" in cli_output.output


def test_cli_orchestrator_route_json_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_orchestrator_route(
        orchestrator=orchestrator,
        agent_name="market",
        action="health",
        output_format="json",
        operation=fake_orchestrator_route,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["agent_name"] == "market"
    assert payload["data"]["routed"] is True
    assert "metadata" not in payload


def test_cli_market_strategy_workflow_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_market_strategy_workflow(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        request_id="market-strategy-1",
        operation=fake_market_strategy_workflow,
    )

    assert cli_output.success is True
    assert "SUCCESS: Market strategy workflow completed." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "signal: buy" in cli_output.output


def test_cli_strategy_risk_workflow_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_strategy_risk_workflow(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
        output_format="text",
        operation=fake_strategy_risk_workflow,
    )

    assert cli_output.success is True
    assert "SUCCESS: Strategy risk workflow completed." in cli_output.output
    assert "allowed: true" in cli_output.output
    assert "risk_percent: 0.01" in cli_output.output


def test_cli_risk_execution_workflow_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_risk_execution_workflow(
        orchestrator=orchestrator,
        symbol="xauusd",
        side="buy",
        output_format="text",
        operation=fake_risk_execution_workflow,
    )

    assert cli_output.success is True
    assert "SUCCESS: Risk execution workflow completed." in cli_output.output
    assert "execution_ready: true" in cli_output.output
    assert "order_id: order-1" in cli_output.output


def test_cli_trade_workflow_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_trade_workflow(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
        account_balance=10_000,
        risk_percent=0.01,
        output_format="text",
        request_id="trade-workflow-1",
        operation=fake_trade_workflow,
    )

    assert cli_output.success is True
    assert "SUCCESS: Trade workflow completed." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "order_id: order-1" in cli_output.output


def test_cli_research_workflow_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_research_workflow(
        orchestrator=orchestrator,
        symbol="xauusd",
        timeframe="h1",
        signal_source="market regime",
        objective="improve strategy quality",
        output_format="text",
        operation=fake_research_workflow,
    )

    assert cli_output.success is True
    assert "SUCCESS: Research workflow completed." in cli_output.output
    assert "signal_source: market regime" in cli_output.output
    assert "Market regime improves strategy quality." in cli_output.output


def test_cli_backtest_workflow_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_backtest_workflow(
        orchestrator=orchestrator,
        name="workflow-backtest",
        profits=[
            100,
            -50,
            25,
        ],
        initial_balance=10_000,
        metadata={
            "symbol": "XAUUSD",
        },
        output_format="text",
        request_id="backtest-workflow-1",
        operation=fake_backtest_workflow,
    )

    assert cli_output.success is True
    assert "SUCCESS: Backtest workflow completed." in cli_output.output
    assert "name: workflow-backtest" in cli_output.output
    assert "total_profit: 75.0" in cli_output.output
    assert "total_trades: 3" in cli_output.output


def test_cli_memory_workflow_success():
    orchestrator = SimpleNamespace(name="agent-orchestrator")

    cli_output = cli_memory_workflow(
        orchestrator=orchestrator,
        memory_id="memory-1",
        content="Important market observation.",
        query="market observation",
        memory_type="research",
        importance=0.8,
        metadata={
            "symbol": "XAUUSD",
        },
        output_format="text",
        request_id="memory-workflow-1",
        operation=fake_memory_workflow,
    )

    assert cli_output.success is True
    assert "SUCCESS: Memory workflow completed." in cli_output.output
    assert "memory_id: memory-1" in cli_output.output
    assert "remembered: true" in cli_output.output
    assert "recalled: true" in cli_output.output