"""
Unit tests for AQOS API evaluation operations.
"""

from types import SimpleNamespace

import pytest

from aqos.api import (
    BacktestNameRequest,
    CompareBacktestsRequest,
    EvaluationBacktestRequest,
    api_backtest_summary,
    api_compare_backtests,
    api_evaluation_report,
    api_performance_grade,
    api_run_backtest,
    evaluation_agent_operation,
    normalize_backtest_request,
)


class SuccessfulEvaluationAgent:
    name = "evaluation-agent"

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
            "run-backtest": {
                "name": payload.get("name"),
                "initial_balance": payload.get("initial_balance"),
                "final_balance": 10_075.0,
                "total_profit": 75.0,
                "total_trades": 3,
                "metadata": payload.get("metadata", {}),
            },
            "backtest-summary": {
                "name": payload.get("name"),
                "initial_balance": 10_000.0,
                "final_balance": 10_075.0,
                "total_profit": 75.0,
                "total_trades": 3,
            },
            "compare-backtests": {
                "baseline_name": payload.get("baseline_name"),
                "candidate_name": payload.get("candidate_name"),
                "profit_delta": 80.0,
                "return_delta": 0.8,
                "win_rate_delta": 0.2,
                "improved": True,
            },
            "performance-grade": {
                "name": payload.get("name"),
                "grade": "A",
                "score": 0.9,
            },
            "evaluation-report": {
                "name": payload.get("name"),
                "metrics": {
                    "total_profit": 75.0,
                    "total_trades": 3,
                    "final_balance": 10_075.0,
                },
            },
        }

        return SimpleNamespace(
            success=True,
            message=f"{action} completed.",
            data=data_by_action[action],
            metadata={
                "source": "unit-test",
            },
        )


class FailingEvaluationAgent:
    name = "evaluation-agent"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Evaluation agent failed.",
            data={
                "reason": "missing backtest",
            },
            metadata={},
        )


class BrokenEvaluationAgent:
    name = "broken-evaluation-agent"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Evaluation agent exploded.")


def sample_backtest():
    return {
        "name": "api-run-1",
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
    }


def test_evaluation_backtest_request_defaults():
    request = EvaluationBacktestRequest()

    assert request.to_payload() == {
        "name": "api-backtest-run",
        "profits": [
            100.0,
            -50.0,
            25.0,
        ],
        "initial_balance": 10_000.0,
        "metadata": {},
    }


def test_evaluation_backtest_request_normalizes_values():
    request = EvaluationBacktestRequest(
        name=" api-run-1 ",
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
        "name": "api-run-1",
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


def test_evaluation_backtest_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        EvaluationBacktestRequest(name="")

    with pytest.raises(ValueError):
        EvaluationBacktestRequest(profits=[])

    with pytest.raises(ValueError):
        EvaluationBacktestRequest(profits=["bad"])

    with pytest.raises(ValueError):
        EvaluationBacktestRequest(initial_balance=0)

    with pytest.raises(ValueError):
        EvaluationBacktestRequest(metadata=[])


def test_backtest_name_request_to_payload():
    request = BacktestNameRequest(name=" run-1 ")

    assert request.to_payload() == {
        "name": "run-1",
    }


def test_compare_backtests_request_to_payload():
    request = CompareBacktestsRequest(
        baseline_name=" baseline ",
        candidate_name=" candidate ",
    )

    assert request.to_payload() == {
        "baseline_name": "baseline",
        "candidate_name": "candidate",
    }


def test_normalize_backtest_request_preserves_extra_fields():
    normalized = normalize_backtest_request(
        {
            **sample_backtest(),
            "strategy_id": "strategy-1",
        }
    )

    assert normalized["name"] == "api-run-1"
    assert normalized["profits"] == [
        100.0,
        -50.0,
        25.0,
    ]
    assert normalized["initial_balance"] == 10_000.0
    assert normalized["strategy_id"] == "strategy-1"


def test_normalize_backtest_request_rejects_non_dict():
    with pytest.raises(ValueError, match="Backtest request"):
        normalize_backtest_request("bad")


def test_evaluation_agent_operation_success():
    agent = SuccessfulEvaluationAgent()

    response = evaluation_agent_operation(
        agent,
        action="run-backtest",
        payload=sample_backtest(),
        success_message="Backtest executed.",
        failure_message="Backtest failed.",
        request_id="evaluation-request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Backtest executed."
    assert payload["data"]["action"] == "run-backtest"
    assert payload["data"]["agent"] == "evaluation-agent"
    assert payload["data"]["result"]["total_profit"] == 75.0
    assert payload["metadata"]["request_id"] == "evaluation-request-1"


def test_evaluation_agent_operation_failure():
    response = evaluation_agent_operation(
        FailingEvaluationAgent(),
        action="backtest-summary",
        payload={
            "name": "missing-run",
        },
        success_message="Backtest summary loaded.",
        failure_message="Backtest summary failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Backtest summary failed."
    assert payload["errors"][0]["code"] == "EVALUATION_AGENT_ERROR"
    assert payload["errors"][0]["message"] == "Evaluation agent failed."
    assert payload["data"]["result"] == {
        "reason": "missing backtest",
    }


def test_evaluation_agent_operation_exception():
    response = evaluation_agent_operation(
        BrokenEvaluationAgent(),
        action="run-backtest",
        payload=sample_backtest(),
        success_message="Backtest executed.",
        failure_message="Backtest failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Backtest failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Evaluation agent exploded."


def test_api_run_backtest_success():
    agent = SuccessfulEvaluationAgent()

    response = api_run_backtest(
        agent,
        backtest=sample_backtest(),
        request_id="run-backtest-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Backtest executed."
    assert payload["data"]["action"] == "run-backtest"
    assert payload["data"]["result"]["name"] == "api-run-1"
    assert payload["data"]["result"]["total_profit"] == 75.0
    assert payload["metadata"]["request_id"] == "run-backtest-1"

    assert agent.calls[0]["payload"]["name"] == "api-run-1"


def test_api_run_backtest_validation_failure():
    response = api_run_backtest(
        SuccessfulEvaluationAgent(),
        backtest="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "backtest"


def test_api_backtest_summary_success():
    response = api_backtest_summary(
        SuccessfulEvaluationAgent(),
        name="api-run-1",
        request_id="summary-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Backtest summary loaded."
    assert payload["data"]["action"] == "backtest-summary"
    assert payload["data"]["result"]["name"] == "api-run-1"
    assert payload["data"]["result"]["total_trades"] == 3
    assert payload["metadata"]["request_id"] == "summary-1"


def test_api_backtest_summary_validation_failure():
    response = api_backtest_summary(
        SuccessfulEvaluationAgent(),
        name="",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "name"


def test_api_compare_backtests_success():
    response = api_compare_backtests(
        SuccessfulEvaluationAgent(),
        baseline_name="baseline-run",
        candidate_name="candidate-run",
        request_id="compare-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Backtests compared."
    assert payload["data"]["action"] == "compare-backtests"
    assert payload["data"]["result"]["baseline_name"] == "baseline-run"
    assert payload["data"]["result"]["candidate_name"] == "candidate-run"
    assert payload["data"]["result"]["improved"] is True
    assert payload["metadata"]["request_id"] == "compare-1"


def test_api_compare_backtests_validation_failure():
    response = api_compare_backtests(
        SuccessfulEvaluationAgent(),
        baseline_name="",
        candidate_name="candidate-run",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "compare_backtests"


def test_api_performance_grade_success():
    response = api_performance_grade(
        SuccessfulEvaluationAgent(),
        name="api-run-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Performance grade loaded."
    assert payload["data"]["action"] == "performance-grade"
    assert payload["data"]["result"]["grade"] == "A"


def test_api_evaluation_report_success():
    response = api_evaluation_report(
        SuccessfulEvaluationAgent(),
        name="api-run-1",
        request_id="report-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Evaluation report loaded."
    assert payload["data"]["action"] == "evaluation-report"
    assert payload["data"]["result"]["name"] == "api-run-1"
    assert payload["data"]["result"]["metrics"]["total_profit"] == 75.0
    assert payload["metadata"]["request_id"] == "report-1"