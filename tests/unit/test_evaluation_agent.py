"""
Unit tests for EvaluationAgent.
"""

from aqos.agents import (
    AgentBase,
    EvaluationAgent,
)
from aqos.services import BacktestService


def create_evaluation_agent() -> EvaluationAgent:
    return EvaluationAgent(
        backtest_service=BacktestService(),
    )


def create_agent_with_runs() -> EvaluationAgent:
    agent = create_evaluation_agent()

    agent.execute(
        action="run-backtest",
        payload={
            "name": "baseline",
            "profits": [
                50.0,
                -25.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
    )

    agent.execute(
        action="run-backtest",
        payload={
            "name": "candidate",
            "profits": [
                100.0,
                -20.0,
                80.0,
            ],
            "initial_balance": 10_000.0,
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
    )

    return agent


def test_evaluation_agent_is_agent_base_instance():
    agent = EvaluationAgent()

    assert isinstance(agent, AgentBase)


def test_evaluation_agent_name():
    agent = EvaluationAgent()

    assert agent.name == "evaluation-agent"


def test_evaluation_agent_description():
    agent = EvaluationAgent()

    assert agent.description == (
        "Agent for backtests, performance summaries, reports, and comparisons."
    )


def test_available_actions():
    agent = EvaluationAgent()

    assert agent.available_actions() == [
        "backtest-summary",
        "compare-backtests",
        "evaluation-report",
        "health",
        "performance-grade",
        "run-backtest",
    ]


def test_health():
    agent = create_evaluation_agent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Evaluation agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["backtest_runs"] == 0


def test_run_backtest():
    agent = create_evaluation_agent()

    result = agent.execute(
        action="run-backtest",
        payload={
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
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Backtest executed."
    assert result.data["name"] == "run-1"
    assert result.data["initial_balance"] == 10_000.0
    assert result.data["final_balance"] == 10_075.0
    assert result.data["total_profit"] == 75.0
    assert result.data["total_trades"] == 3
    assert result.data["metadata"]["symbol"] == "XAUUSD"
    assert result.data["metadata"]["request_id"] == "req-1"
    assert result.metadata["request_id"] == "req-1"


def test_run_backtest_missing_name():
    agent = create_evaluation_agent()

    result = agent.execute(
        action="run-backtest",
        payload={
            "profits": [
                100.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: name"


def test_run_backtest_duplicate_name_returns_failure():
    agent = create_evaluation_agent()

    payload = {
        "name": "run-1",
        "profits": [
            100.0,
        ],
        "initial_balance": 10_000.0,
    }

    agent.execute(
        action="run-backtest",
        payload=payload,
    )
    result = agent.execute(
        action="run-backtest",
        payload=payload,
    )

    assert result.success is False
    assert result.message == "Backtest run already exists."


def test_backtest_summary():
    agent = create_agent_with_runs()

    result = agent.execute(
        action="backtest-summary",
        payload={
            "name": "baseline",
        },
    )

    assert result.success is True
    assert result.message == "Backtest summary generated."
    assert result.data["name"] == "baseline"
    assert result.data["total_profit"] == 50.0
    assert result.data["final_balance"] == 10_050.0


def test_backtest_summary_missing_run():
    agent = create_evaluation_agent()

    result = agent.execute(
        action="backtest-summary",
        payload={
            "name": "missing",
        },
    )

    assert result.success is False
    assert result.message == "Backtest run does not exist."


def test_compare_backtests():
    agent = create_agent_with_runs()

    result = agent.execute(
        action="compare-backtests",
        payload={
            "baseline_name": "baseline",
            "candidate_name": "candidate",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Backtests compared."
    assert result.data["baseline_name"] == "baseline"
    assert result.data["candidate_name"] == "candidate"
    assert result.data["baseline_total_profit"] == 50.0
    assert result.data["candidate_total_profit"] == 160.0
    assert result.data["profit_delta"] == 110.0
    assert result.metadata["request_id"] == "req-1"


def test_compare_backtests_missing_baseline():
    agent = create_agent_with_runs()

    result = agent.execute(
        action="compare-backtests",
        payload={
            "baseline_name": "missing",
            "candidate_name": "candidate",
        },
    )

    assert result.success is False
    assert result.message == "Baseline backtest run does not exist."


def test_compare_backtests_missing_candidate():
    agent = create_agent_with_runs()

    result = agent.execute(
        action="compare-backtests",
        payload={
            "baseline_name": "baseline",
            "candidate_name": "missing",
        },
    )

    assert result.success is False
    assert result.message == "Candidate backtest run does not exist."


def test_performance_grade():
    agent = create_agent_with_runs()

    result = agent.execute(
        action="performance-grade",
        payload={
            "name": "candidate",
        },
    )

    assert result.success is True
    assert result.message == "Performance grade generated."
    assert result.data["name"] == "candidate"
    assert result.data["grade"] in {
        "A",
        "B",
        "C",
        "D",
    }
    assert result.data["total_profit"] == 160.0


def test_performance_grade_missing_run():
    agent = create_evaluation_agent()

    result = agent.execute(
        action="performance-grade",
        payload={
            "name": "missing",
        },
    )

    assert result.success is False
    assert result.message == "Backtest run does not exist."


def test_evaluation_report():
    agent = create_agent_with_runs()

    result = agent.execute(
        action="evaluation-report",
        payload={
            "name": "candidate",
        },
    )

    assert result.success is True
    assert result.message == "Evaluation report generated."
    assert result.data["name"] == "candidate"
    assert result.data["summary"] == (
        "Backtest candidate finished with total profit 160.0 "
        "and final balance 10160.0."
    )
    assert result.data["metrics"]["total_profit"] == 160.0
    assert result.data["metrics"]["final_balance"] == 10_160.0
    assert result.data["metrics"]["total_trades"] == 3


def test_evaluation_report_missing_run():
    agent = create_evaluation_agent()

    result = agent.execute(
        action="evaluation-report",
        payload={
            "name": "missing",
        },
    )

    assert result.success is False
    assert result.message == "Backtest run does not exist."


def test_unsupported_action():
    agent = EvaluationAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"