"""
Research → Memory integration tests.

Validates that research hypotheses, experiment plans, and findings
can be stored and recalled through the MemoryAgent.
"""

from aqos.agents import (
    AgentOrchestrator,
    MemoryAgent,
    ResearchAgent,
)
from aqos.services import StorageService


def test_research_hypothesis_can_be_saved_to_memory(
    research_agent: ResearchAgent,
    memory_agent: MemoryAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    hypothesis_result = research_agent.execute(
        action="hypothesis",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "signal_source": "news sentiment",
            "objective": "reduce false entries",
        },
    )

    assert hypothesis_result.success is True
    assert hypothesis_result.data["symbol"] == integration_symbol
    assert hypothesis_result.data["timeframe"] == integration_timeframe
    assert "hypothesis" in hypothesis_result.data

    memory_result = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "research-hypothesis-1",
            "content": hypothesis_result.data["hypothesis"],
            "memory_type": "research",
            "importance": 0.8,
            "metadata": {
                "symbol": hypothesis_result.data["symbol"],
                "timeframe": hypothesis_result.data["timeframe"],
                "signal_source": hypothesis_result.data["signal_source"],
            },
        },
    )

    assert memory_result.success is True
    assert memory_result.data["memory_id"] == "research-hypothesis-1"
    assert memory_result.data["memory_type"] == "research"
    assert memory_result.data["metadata"]["symbol"] == integration_symbol

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "news sentiment",
            "memory_type": "research",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1
    assert recall_result.data["results"][0]["record"]["memory_id"] == (
        "research-hypothesis-1"
    )


def test_research_experiment_plan_can_be_saved_to_memory(
    research_agent: ResearchAgent,
    memory_agent: MemoryAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    hypothesis_result = research_agent.execute(
        action="hypothesis",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "signal_source": "market regime",
            "objective": "improve entry filtering",
        },
    )

    plan_result = research_agent.execute(
        action="experiment-plan",
        payload={
            "name": "market-regime-entry-filter-test",
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "hypothesis": hypothesis_result.data["hypothesis"],
            "metric": "win_rate",
        },
    )

    assert plan_result.success is True
    assert plan_result.data["name"] == "market-regime-entry-filter-test"
    assert plan_result.data["symbol"] == integration_symbol
    assert plan_result.data["metric"] == "win_rate"

    memory_result = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "experiment-plan-1",
            "content": (
                "Experiment plan market-regime-entry-filter-test "
                "will measure win_rate for market regime entry filtering."
            ),
            "memory_type": "research",
            "importance": 0.7,
            "metadata": {
                "experiment_name": plan_result.data["name"],
                "symbol": plan_result.data["symbol"],
                "timeframe": plan_result.data["timeframe"],
                "metric": plan_result.data["metric"],
            },
        },
    )

    assert memory_result.success is True
    assert memory_result.data["metadata"]["experiment_name"] == (
        "market-regime-entry-filter-test"
    )

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "market regime entry",
            "memory_type": "research",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1
    assert recall_result.data["results"][0]["record"]["memory_id"] == (
        "experiment-plan-1"
    )


def test_research_finding_storage_can_feed_memory(
    research_agent: ResearchAgent,
    memory_agent: MemoryAgent,
    storage_service: StorageService,
):
    finding_result = research_agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-memory-1",
            "title": "News sentiment improves filtering",
            "finding": "Positive news sentiment reduced false short entries.",
            "conclusion": "News sentiment should be included in market context.",
            "metadata": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "metric": "win_rate",
            },
        },
    )

    assert finding_result.success is True

    stored_record = storage_service.get(
        key="finding-memory-1",
        namespace="research",
    )

    assert stored_record is not None
    assert stored_record.value["finding_id"] == "finding-memory-1"
    assert stored_record.value["title"] == "News sentiment improves filtering"
    assert stored_record.value["conclusion"] == (
        "News sentiment should be included in market context."
    )

    memory_result = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "research-finding-1",
            "content": stored_record.value["conclusion"],
            "memory_type": "research",
            "importance": 0.9,
            "metadata": {
                "finding_id": stored_record.value["finding_id"],
                "title": stored_record.value["title"],
                "symbol": stored_record.value["metadata"]["symbol"],
                "metric": stored_record.value["metadata"]["metric"],
            },
        },
    )

    assert memory_result.success is True
    assert memory_result.data["memory_id"] == "research-finding-1"
    assert memory_result.data["importance"] == 0.9

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "sentiment market context",
            "memory_type": "research",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1
    assert recall_result.data["results"][0]["record"]["metadata"]["finding_id"] == (
        "finding-memory-1"
    )


def test_research_summary_can_be_saved_to_memory(
    research_agent: ResearchAgent,
    memory_agent: MemoryAgent,
):
    research_agent.execute(
        action="record-finding",
        payload={
            "finding_id": "summary-finding-1",
            "title": "Regime filter improves entries",
            "finding": "Bullish regime filters improved buy entry quality.",
            "conclusion": "Regime context should be used before entry approval.",
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
    )

    summary_result = research_agent.execute("research-summary")

    assert summary_result.success is True
    assert summary_result.message == "Research summary generated."
    assert summary_result.data["findings"] >= 1

    memory_result = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "research-summary-1",
            "content": "Research summary contains recorded AQOS findings.",
            "memory_type": "research",
            "importance": 0.6,
            "metadata": {
                "findings": summary_result.data["findings"],
            },
        },
    )

    assert memory_result.success is True
    assert memory_result.data["memory_id"] == "research-summary-1"

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "research summary findings",
            "memory_type": "research",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1


def test_orchestrator_research_workflow_can_feed_memory(
    agent_orchestrator: AgentOrchestrator,
    memory_agent: MemoryAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    research_result = agent_orchestrator.execute(
        action="research-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "signal_source": "economic calendar",
            "objective": "avoid high-impact event risk",
            "experiment_name": "calendar-risk-filter-test",
            "metric": "max_drawdown",
        },
        metadata={
            "request_id": "integration-research-memory",
        },
    )

    assert research_result.success is True
    assert research_result.message == "Research workflow completed."
    assert research_result.metadata["request_id"] == "integration-research-memory"

    assert research_result.data["hypothesis"]["symbol"] == integration_symbol
    assert research_result.data["experiment_plan"]["name"] == (
        "calendar-risk-filter-test"
    )
    assert research_result.data["experiment_plan"]["metric"] == "max_drawdown"

    memory_result = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "orchestrator-research-1",
            "content": research_result.data["hypothesis"]["hypothesis"],
            "memory_type": "research",
            "importance": 0.8,
            "metadata": {
                "experiment_name": research_result.data["experiment_plan"]["name"],
                "metric": research_result.data["experiment_plan"]["metric"],
                "symbol": research_result.data["hypothesis"]["symbol"],
                "timeframe": research_result.data["hypothesis"]["timeframe"],
            },
        },
    )

    assert memory_result.success is True

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "economic calendar risk",
            "memory_type": "research",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1
    assert recall_result.data["results"][0]["record"]["memory_id"] == (
        "orchestrator-research-1"
    )


def test_orchestrator_memory_workflow_can_store_research_content(
    agent_orchestrator: AgentOrchestrator,
):
    result = agent_orchestrator.execute(
        action="memory-workflow",
        payload={
            "memory_id": "research-memory-workflow-1",
            "content": "Research found that bullish regime improved strategy quality.",
            "memory_type": "research",
            "importance": 0.8,
            "query": "bullish regime strategy",
        },
        metadata={
            "request_id": "integration-memory-workflow",
        },
    )

    assert result.success is True
    assert result.message == "Memory workflow completed."
    assert result.metadata["request_id"] == "integration-memory-workflow"

    assert result.data["remember"]["memory_id"] == "research-memory-workflow-1"
    assert result.data["remember"]["memory_type"] == "research"
    assert result.data["recall"]["count"] == 1
    assert result.data["recall"]["results"][0]["record"]["memory_id"] == (
        "research-memory-workflow-1"
    )


def test_research_memory_recall_respects_memory_type_filter(
    memory_agent: MemoryAgent,
):
    research_memory = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "research-type-1",
            "content": "Research memory about signal quality.",
            "memory_type": "research",
        },
    )
    trade_memory = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "trade-type-1",
            "content": "Trade memory about signal quality.",
            "memory_type": "trade",
        },
    )

    assert research_memory.success is True
    assert trade_memory.success is True

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "signal quality",
            "memory_type": "research",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1
    assert recall_result.data["results"][0]["record"]["memory_id"] == (
        "research-type-1"
    )