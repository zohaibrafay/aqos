"""
Unit tests for ResearchAgent.
"""

from aqos.agents import (
    AgentBase,
    ResearchAgent,
)
from aqos.services import (
    ExperimentService,
    StorageService,
)


def create_research_agent() -> ResearchAgent:
    return ResearchAgent(
        experiment_service=ExperimentService(),
        storage_service=StorageService(),
    )


def test_research_agent_is_agent_base_instance():
    agent = ResearchAgent()

    assert isinstance(agent, AgentBase)


def test_research_agent_name():
    agent = ResearchAgent()

    assert agent.name == "research-agent"


def test_research_agent_description():
    agent = ResearchAgent()

    assert agent.description == (
        "Agent for hypotheses, experiment planning, and research findings."
    )


def test_available_actions():
    agent = ResearchAgent()

    assert agent.available_actions() == [
        "create-experiment",
        "experiment-plan",
        "health",
        "hypothesis",
        "record-finding",
        "research-summary",
    ]


def test_health():
    agent = create_research_agent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Research agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["experiments"] == 0
    assert result.data["findings"] == 0


def test_hypothesis():
    agent = create_research_agent()

    result = agent.execute(
        action="hypothesis",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "signal_source": "news sentiment",
            "objective": "reduce false entries",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Research hypothesis generated."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["signal_source"] == "news sentiment"
    assert result.data["objective"] == "reduce false entries"
    assert result.data["hypothesis"] == (
        "news sentiment may improve XAUUSD H1 decision quality "
        "by helping AQOS reduce false entries."
    )
    assert result.metadata["request_id"] == "req-1"


def test_hypothesis_defaults_timeframe_and_objective():
    agent = create_research_agent()

    result = agent.execute(
        action="hypothesis",
        payload={
            "symbol": "XAUUSD",
            "signal_source": "market regime",
        },
    )

    assert result.success is True
    assert result.data["timeframe"] == "H1"
    assert result.data["objective"] == "improve signal quality"


def test_hypothesis_missing_symbol():
    agent = create_research_agent()

    result = agent.execute(
        action="hypothesis",
        payload={
            "signal_source": "news sentiment",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: symbol"


def test_hypothesis_missing_signal_source():
    agent = create_research_agent()

    result = agent.execute(
        action="hypothesis",
        payload={
            "symbol": "XAUUSD",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: signal_source"


def test_experiment_plan():
    agent = create_research_agent()

    result = agent.execute(
        action="experiment-plan",
        payload={
            "name": "news-sentiment-test",
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "hypothesis": "News sentiment improves entry quality.",
            "metric": "return_percent",
        },
    )

    assert result.success is True
    assert result.message == "Research experiment plan generated."
    assert result.data["name"] == "news-sentiment-test"
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["hypothesis"] == "News sentiment improves entry quality."
    assert result.data["metric"] == "return_percent"
    assert result.data["steps"] == [
        "Prepare historical OHLCV dataset.",
        "Generate baseline strategy results.",
        "Apply proposed research hypothesis.",
        "Run backtest on the same dataset.",
        "Compare results against baseline metrics.",
        "Record finding and recommendation.",
    ]


def test_experiment_plan_defaults_symbol_timeframe_and_metric():
    agent = create_research_agent()

    result = agent.execute(
        action="experiment-plan",
        payload={
            "name": "baseline-test",
            "hypothesis": "Baseline improves decision quality.",
        },
    )

    assert result.success is True
    assert result.data["symbol"] == "UNKNOWN"
    assert result.data["timeframe"] == "H1"
    assert result.data["metric"] == "win_rate"


def test_experiment_plan_missing_name():
    agent = create_research_agent()

    result = agent.execute(
        action="experiment-plan",
        payload={
            "hypothesis": "News sentiment improves entry quality.",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: name"


def test_create_experiment():
    agent = create_research_agent()

    result = agent.execute(
        action="create-experiment",
        payload={
            "name": "experiment-1",
            "description": "Baseline research experiment",
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Research experiment created."
    assert result.data["name"] == "experiment-1"
    assert result.data["status"] == "created"
    assert result.data["description"] == "Baseline research experiment"
    assert result.data["metadata"]["symbol"] == "XAUUSD"
    assert result.data["metadata"]["request_id"] == "req-1"


def test_create_duplicate_experiment_returns_failure():
    agent = create_research_agent()

    payload = {
        "name": "experiment-1",
    }

    agent.execute(
        action="create-experiment",
        payload=payload,
    )
    result = agent.execute(
        action="create-experiment",
        payload=payload,
    )

    assert result.success is False
    assert result.message == "Experiment already exists."


def test_create_experiment_missing_name():
    agent = create_research_agent()

    result = agent.execute(
        action="create-experiment",
        payload={},
    )

    assert result.success is False
    assert result.message == "Missing required payload key: name"


def test_record_finding():
    storage_service = StorageService()
    agent = ResearchAgent(
        experiment_service=ExperimentService(),
        storage_service=storage_service,
    )

    result = agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-1",
            "title": "News filter improves entries",
            "conclusion": "Avoiding low-impact news reduced false entries.",
            "confidence": 0.8,
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
        metadata={
            "request_id": "req-1",
        },
    )

    stored = storage_service.get(
        key="finding-1",
        namespace="research",
    )

    assert result.success is True
    assert result.message == "Research finding recorded."
    assert result.data["finding_id"] == "finding-1"
    assert result.data["title"] == "News filter improves entries"
    assert result.data["conclusion"] == "Avoiding low-impact news reduced false entries."
    assert result.data["confidence"] == 0.8
    assert result.data["metadata"]["symbol"] == "XAUUSD"
    assert result.metadata["request_id"] == "req-1"
    assert stored is not None
    assert stored.value["finding_id"] == "finding-1"


def test_record_finding_default_confidence():
    agent = create_research_agent()

    result = agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-1",
            "title": "Baseline finding",
            "conclusion": "Baseline recorded.",
        },
    )

    assert result.success is True
    assert result.data["confidence"] == 0.0


def test_record_finding_rejects_invalid_confidence():
    agent = create_research_agent()

    result = agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-1",
            "title": "Invalid finding",
            "conclusion": "Invalid confidence.",
            "confidence": 1.1,
        },
    )

    assert result.success is False
    assert result.message == "Confidence must be between 0.0 and 1.0."


def test_record_finding_missing_title():
    agent = create_research_agent()

    result = agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-1",
            "conclusion": "Missing title.",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: title"


def test_research_summary():
    agent = create_research_agent()

    agent.execute(
        action="create-experiment",
        payload={
            "name": "experiment-1",
        },
    )
    agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-1",
            "title": "High confidence finding",
            "conclusion": "Finding is useful.",
            "confidence": 0.8,
        },
    )
    agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-2",
            "title": "Low confidence finding",
            "conclusion": "Finding needs more testing.",
            "confidence": 0.4,
        },
    )

    result = agent.execute(
        action="research-summary",
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Research summary generated."
    assert result.data["experiments"] == 1
    assert result.data["findings"] == 2
    assert result.data["high_confidence_findings"] == 1
    assert result.data["finding_ids"] == [
        "finding-1",
        "finding-2",
    ]
    assert result.metadata["request_id"] == "req-1"


def test_unsupported_action():
    agent = ResearchAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"