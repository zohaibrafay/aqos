"""
Unit tests for agents package exports.
"""

from aqos.agents import (
    AgentBase,
    AgentOrchestrator,
    AgentResult,
    AgentTask,
    DataAgent,
    EvaluationAgent,
    ExecutionAgent,
    MarketAgent,
    MemoryAgent,
    ResearchAgent,
    RiskAgent,
    StrategyAgent,
)


def test_agents_exports():
    assert AgentBase is not None
    assert AgentOrchestrator is not None
    assert AgentResult is not None
    assert AgentTask is not None
    assert DataAgent is not None
    assert EvaluationAgent is not None
    assert ExecutionAgent is not None
    assert MarketAgent is not None
    assert MemoryAgent is not None
    assert ResearchAgent is not None
    assert RiskAgent is not None
    assert StrategyAgent is not None


def test_agent_task_can_be_created():
    task = AgentTask(
        action="health",
        payload={
            "symbol": "XAUUSD",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert task.action == "health"
    assert task.payload["symbol"] == "XAUUSD"
    assert task.metadata["request_id"] == "req-1"


def test_agent_result_can_be_created():
    result = AgentResult(
        success=True,
        message="Completed.",
        data={
            "status": "ok",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Completed."
    assert result.data["status"] == "ok"
    assert result.metadata["request_id"] == "req-1"


def test_agent_instances_can_be_created():
    assert isinstance(DataAgent(), DataAgent)
    assert isinstance(EvaluationAgent(), EvaluationAgent)
    assert isinstance(ExecutionAgent(), ExecutionAgent)
    assert isinstance(MarketAgent(), MarketAgent)
    assert isinstance(MemoryAgent(), MemoryAgent)
    assert isinstance(ResearchAgent(), ResearchAgent)
    assert isinstance(RiskAgent(), RiskAgent)
    assert isinstance(StrategyAgent(), StrategyAgent)
    assert isinstance(AgentOrchestrator(), AgentOrchestrator)


def test_agent_instances_are_agent_base_instances():
    agents = [
        DataAgent(),
        EvaluationAgent(),
        ExecutionAgent(),
        MarketAgent(),
        MemoryAgent(),
        ResearchAgent(),
        RiskAgent(),
        StrategyAgent(),
        AgentOrchestrator(),
    ]

    for agent in agents:
        assert isinstance(agent, AgentBase)


def test_agent_health_actions_work():
    agents = [
        DataAgent(),
        EvaluationAgent(),
        ExecutionAgent(),
        MarketAgent(),
        MemoryAgent(),
        ResearchAgent(),
        RiskAgent(),
        StrategyAgent(),
        AgentOrchestrator(),
    ]

    for agent in agents:
        result = agent.execute("health")

        assert result.success is True
        assert "healthy" in result.message.lower()