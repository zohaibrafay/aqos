"""
Backtest → Evaluation integration tests.

Validates that backtest results can flow through the EvaluationAgent
and AgentOrchestrator evaluation workflows.
"""

from aqos.agents import (
    AgentOrchestrator,
    EvaluationAgent,
    MemoryAgent,
)
from aqos.services import BacktestService


def test_evaluation_agent_runs_backtest_and_stores_result(
    evaluation_agent: EvaluationAgent,
    backtest_service: BacktestService,
):
    result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "evaluation-run-1",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
            "metadata": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
            },
        },
    )

    assert result.success is True
    assert result.message == "Backtest executed."
    assert result.data["name"] == "evaluation-run-1"
    assert result.data["initial_balance"] == 10_000.0
    assert result.data["final_balance"] == 10_075.0
    assert result.data["total_profit"] == 75.0
    assert result.data["total_trades"] == 3
    assert result.data["metadata"]["symbol"] == "XAUUSD"

    stored_run = backtest_service.get("evaluation-run-1")

    assert stored_run is not None
    assert stored_run.name == "evaluation-run-1"
    assert stored_run.result.total_profit == 75.0


def test_evaluation_agent_reads_backtest_summary_from_service_state(
    evaluation_agent: EvaluationAgent,
):
    run_result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "evaluation-summary-run",
            "profits": [
                120.0,
                -20.0,
                40.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert run_result.success is True

    summary_result = evaluation_agent.execute(
        action="backtest-summary",
        payload={
            "name": "evaluation-summary-run",
        },
    )

    assert summary_result.success is True
    assert summary_result.message == "Backtest summary generated."
    assert summary_result.data["name"] == "evaluation-summary-run"
    assert summary_result.data["initial_balance"] == 10_000.0
    assert summary_result.data["final_balance"] == 10_140.0
    assert summary_result.data["total_profit"] == 140.0
    assert summary_result.data["total_trades"] == 3


def test_evaluation_agent_report_uses_backtest_result(
    evaluation_agent: EvaluationAgent,
):
    run_result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "evaluation-report-run",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert run_result.success is True

    report_result = evaluation_agent.execute(
        action="evaluation-report",
        payload={
            "name": "evaluation-report-run",
        },
    )

    assert report_result.success is True
    assert report_result.message == "Evaluation report generated."
    assert report_result.data["name"] == "evaluation-report-run"
    assert report_result.data["metrics"]["total_profit"] == 75.0
    assert report_result.data["metrics"]["total_trades"] == 3
    assert report_result.data["metrics"]["final_balance"] == 10_075.0


def test_evaluation_agent_compares_backtests(
    evaluation_agent: EvaluationAgent,
):
    baseline_result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "baseline-run",
            "profits": [
                50.0,
                -25.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )
    candidate_result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "candidate-run",
            "profits": [
                100.0,
                -20.0,
                50.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert baseline_result.success is True
    assert candidate_result.success is True

    compare_result = evaluation_agent.execute(
        action="compare-backtests",
        payload={
            "baseline_name": "baseline-run",
            "candidate_name": "candidate-run",
        },
    )

    assert compare_result.success is True
    assert compare_result.message == "Backtests compared."
    assert compare_result.data["baseline_name"] == "baseline-run"
    assert compare_result.data["candidate_name"] == "candidate-run"
    assert compare_result.data["profit_delta"] == 80.0
    assert compare_result.data["return_delta"] > 0
    assert compare_result.data["win_rate_delta"] >= 0
    assert compare_result.data["improved"] is True


def test_evaluation_agent_rejects_duplicate_backtest_name(
    evaluation_agent: EvaluationAgent,
):
    payload = {
        "name": "duplicate-run",
        "profits": [
            100.0,
        ],
        "initial_balance": 10_000.0,
    }

    first_result = evaluation_agent.execute(
        action="run-backtest",
        payload=payload,
    )
    second_result = evaluation_agent.execute(
        action="run-backtest",
        payload=payload,
    )

    assert first_result.success is True
    assert second_result.success is False
    assert second_result.message == "Backtest run already exists."


def test_evaluation_agent_missing_summary_backtest_returns_failure(
    evaluation_agent: EvaluationAgent,
):
    result = evaluation_agent.execute(
        action="backtest-summary",
        payload={
            "name": "missing-run",
        },
    )

    assert result.success is False
    assert result.message == "Backtest run does not exist."


def test_orchestrator_backtest_workflow(
    agent_orchestrator: AgentOrchestrator,
):
    result = agent_orchestrator.execute(
        action="backtest-workflow",
        payload={
            "name": "orchestrator-backtest-run",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
            "metadata": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
            },
        },
        metadata={
            "request_id": "integration-backtest-workflow",
        },
    )

    assert result.success is True
    assert result.message == "Backtest workflow completed."
    assert result.metadata["request_id"] == "integration-backtest-workflow"

    assert result.data["backtest"]["name"] == "orchestrator-backtest-run"
    assert result.data["backtest"]["total_profit"] == 75.0
    assert result.data["backtest"]["total_trades"] == 3
    assert result.data["backtest"]["metadata"]["symbol"] == "XAUUSD"

    assert result.data["report"]["name"] == "orchestrator-backtest-run"
    assert result.data["report"]["metrics"]["total_profit"] == 75.0
    assert result.data["report"]["metrics"]["total_trades"] == 3


def test_orchestrator_backtest_workflow_duplicate_name_fails(
    agent_orchestrator: AgentOrchestrator,
):
    payload = {
        "name": "orchestrator-duplicate-run",
        "profits": [
            100.0,
        ],
        "initial_balance": 10_000.0,
    }

    first_result = agent_orchestrator.execute(
        action="backtest-workflow",
        payload=payload,
    )
    second_result = agent_orchestrator.execute(
        action="backtest-workflow",
        payload=payload,
    )

    assert first_result.success is True
    assert second_result.success is False
    assert second_result.message == "Backtest workflow failed."
    assert second_result.data["failed_step"] == "run-backtest"
    assert second_result.data["result"]["message"] == "Backtest run already exists."


def test_backtest_evaluation_output_can_be_saved_to_memory(
    evaluation_agent: EvaluationAgent,
    memory_agent: MemoryAgent,
):
    run_result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "memory-backtest-run",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert run_result.success is True

    memory_result = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "backtest-memory-1",
            "content": "Backtest memory-backtest-run produced 75.0 total profit.",
            "memory_type": "evaluation",
            "importance": 0.8,
            "metadata": {
                "backtest_name": run_result.data["name"],
                "total_profit": run_result.data["total_profit"],
                "total_trades": run_result.data["total_trades"],
            },
        },
    )

    assert memory_result.success is True
    assert memory_result.data["memory_id"] == "backtest-memory-1"
    assert memory_result.data["memory_type"] == "evaluation"

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "Backtest profit",
            "memory_type": "evaluation",
        },
    )

    assert recall_result.success is True
    assert recall_result.data["count"] == 1
    assert recall_result.data["results"][0]["record"]["memory_id"] == (
        "backtest-memory-1"
    )