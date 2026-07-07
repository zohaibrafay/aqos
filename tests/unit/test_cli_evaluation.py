"""
Unit tests for AQOS CLI evaluation commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliBacktestNameRequest,
    CliCompareBacktestsRequest,
    CliEvaluationBacktestRequest,
    build_evaluation_cli_output,
    cli_backtest_summary,
    cli_compare_backtests,
    cli_evaluation_report,
    cli_performance_grade,
    cli_run_backtest,
    execute_evaluation_operation,
)


def sample_backtest():
    return {
        "name": "cli-run-1",
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


def fake_run_backtest(agent, backtest, request_id=None):
    return api_success(
        message="Backtest executed.",
        data={
            "agent": agent.name,
            "name": backtest["name"],
            "initial_balance": backtest["initial_balance"],
            "final_balance": 10_075.0,
            "total_profit": 75.0,
            "total_trades": len(backtest["profits"]),
            "metadata": backtest["metadata"],
        },
        request_id=request_id,
    )


def fake_backtest_summary(agent, name, request_id=None):
    return api_success(
        message="Backtest summary loaded.",
        data={
            "agent": agent.name,
            "name": name,
            "initial_balance": 10_000.0,
            "final_balance": 10_075.0,
            "total_profit": 75.0,
            "total_trades": 3,
        },
        request_id=request_id,
    )


def fake_compare_backtests(agent, baseline_name, candidate_name, request_id=None):
    return api_success(
        message="Backtests compared.",
        data={
            "agent": agent.name,
            "baseline_name": baseline_name,
            "candidate_name": candidate_name,
            "profit_delta": 80.0,
            "return_delta": 0.8,
            "win_rate_delta": 0.2,
            "improved": True,
        },
        request_id=request_id,
    )


def fake_performance_grade(agent, name, request_id=None):
    return api_success(
        message="Performance grade loaded.",
        data={
            "agent": agent.name,
            "name": name,
            "grade": "A",
            "score": 0.9,
        },
        request_id=request_id,
    )


def fake_evaluation_report(agent, name, request_id=None):
    return api_success(
        message="Evaluation report loaded.",
        data={
            "agent": agent.name,
            "name": name,
            "metrics": {
                "total_profit": 75.0,
                "total_trades": 3,
                "final_balance": 10_075.0,
            },
        },
        request_id=request_id,
    )


def fake_failure_evaluation(agent, backtest=None, request_id=None):
    return api_failure(
        message="Evaluation command failed.",
        data={
            "name": backtest.get("name") if backtest else "missing-run",
        },
        request_id=request_id,
    )


def test_cli_evaluation_backtest_request_accepts_valid_values():
    agent = SimpleNamespace(name="evaluation-agent")

    request = CliEvaluationBacktestRequest(
        agent=agent,
        name=" cli-run-1 ",
        profits=[
            100,
            -50,
            25,
        ],
        initial_balance=10_000,
        metadata={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        output_format="pretty-json",
        include_metadata=True,
        request_id="evaluation-request-1",
    )

    assert request.agent == agent
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "evaluation-request-1"
    assert request.to_backtest() == sample_backtest()


def test_cli_evaluation_backtest_request_rejects_invalid_values():
    agent = SimpleNamespace(name="evaluation-agent")

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=None)

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, name="")

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, profits=[])

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, profits=["bad"])

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, initial_balance=0)

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, metadata=[])

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, output_format="bad")

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, include_metadata="yes")

    with pytest.raises(ValueError):
        CliEvaluationBacktestRequest(agent=agent, request_id="")


def test_cli_backtest_name_request_to_payload():
    agent = SimpleNamespace(name="evaluation-agent")

    request = CliBacktestNameRequest(
        agent=agent,
        name=" run-1 ",
    )

    assert request.to_payload() == {
        "name": "run-1",
    }


def test_cli_backtest_name_request_rejects_invalid_values():
    agent = SimpleNamespace(name="evaluation-agent")

    with pytest.raises(ValueError):
        CliBacktestNameRequest(agent=None, name="run-1")

    with pytest.raises(ValueError):
        CliBacktestNameRequest(agent=agent, name="")


def test_cli_compare_backtests_request_to_payload():
    agent = SimpleNamespace(name="evaluation-agent")

    request = CliCompareBacktestsRequest(
        agent=agent,
        baseline_name=" baseline ",
        candidate_name=" candidate ",
    )

    assert request.to_payload() == {
        "baseline_name": "baseline",
        "candidate_name": "candidate",
    }


def test_cli_compare_backtests_request_rejects_invalid_values():
    agent = SimpleNamespace(name="evaluation-agent")

    with pytest.raises(ValueError):
        CliCompareBacktestsRequest(
            agent=None,
            baseline_name="baseline",
            candidate_name="candidate",
        )

    with pytest.raises(ValueError):
        CliCompareBacktestsRequest(
            agent=agent,
            baseline_name="",
            candidate_name="candidate",
        )

    with pytest.raises(ValueError):
        CliCompareBacktestsRequest(
            agent=agent,
            baseline_name="baseline",
            candidate_name="",
        )


def test_execute_evaluation_operation_with_request_id():
    agent = SimpleNamespace(name="evaluation-agent")

    response = execute_evaluation_operation(
        fake_run_backtest,
        agent=agent,
        backtest=sample_backtest(),
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["agent"] == "evaluation-agent"


def test_execute_evaluation_operation_rejects_invalid_values():
    agent = SimpleNamespace(name="evaluation-agent")

    with pytest.raises(ValueError):
        execute_evaluation_operation(
            "not-callable",
            agent=agent,
        )

    with pytest.raises(ValueError):
        execute_evaluation_operation(
            fake_run_backtest,
            agent=None,
        )


def test_build_evaluation_cli_output_success():
    agent = SimpleNamespace(name="evaluation-agent")

    response = fake_run_backtest(
        agent,
        sample_backtest(),
        request_id="request-1",
    )

    cli_output = build_evaluation_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Backtest executed." in cli_output.output
    assert "name: cli-run-1" in cli_output.output
    assert "total_profit: 75.0" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_evaluation_cli_output_failure():
    agent = SimpleNamespace(name="evaluation-agent")

    response = fake_failure_evaluation(
        agent,
        sample_backtest(),
    )

    cli_output = build_evaluation_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Evaluation command failed."


def test_cli_run_backtest_text_success():
    agent = SimpleNamespace(name="evaluation-agent")

    cli_output = cli_run_backtest(
        agent=agent,
        name="cli-run-1",
        profits=[
            100.0,
            -50.0,
            25.0,
        ],
        initial_balance=10_000.0,
        metadata={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        output_format="text",
        request_id="run-backtest-1",
        operation=fake_run_backtest,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Backtest executed." in cli_output.output
    assert "name: cli-run-1" in cli_output.output
    assert "total_profit: 75.0" in cli_output.output
    assert "total_trades: 3" in cli_output.output


def test_cli_run_backtest_json_success():
    agent = SimpleNamespace(name="evaluation-agent")

    cli_output = cli_run_backtest(
        agent=agent,
        name="cli-run-1",
        profits=[
            100.0,
            -50.0,
            25.0,
        ],
        output_format="json",
        operation=fake_run_backtest,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["name"] == "cli-run-1"
    assert payload["data"]["total_profit"] == 75.0
    assert "metadata" not in payload


def test_cli_run_backtest_validation_failure():
    agent = SimpleNamespace(name="evaluation-agent")

    with pytest.raises(ValueError):
        cli_run_backtest(
            agent=agent,
            name="",
            operation=fake_run_backtest,
        )


def test_cli_backtest_summary_success():
    agent = SimpleNamespace(name="evaluation-agent")

    cli_output = cli_backtest_summary(
        agent=agent,
        name="cli-run-1",
        output_format="text",
        operation=fake_backtest_summary,
    )

    assert cli_output.success is True
    assert "SUCCESS: Backtest summary loaded." in cli_output.output
    assert "name: cli-run-1" in cli_output.output
    assert "total_trades: 3" in cli_output.output


def test_cli_backtest_summary_validation_failure():
    agent = SimpleNamespace(name="evaluation-agent")

    with pytest.raises(ValueError):
        cli_backtest_summary(
            agent=agent,
            name="",
            operation=fake_backtest_summary,
        )


def test_cli_compare_backtests_success():
    agent = SimpleNamespace(name="evaluation-agent")

    cli_output = cli_compare_backtests(
        agent=agent,
        baseline_name="baseline-run",
        candidate_name="candidate-run",
        output_format="text",
        request_id="compare-1",
        operation=fake_compare_backtests,
    )

    assert cli_output.success is True
    assert "SUCCESS: Backtests compared." in cli_output.output
    assert "baseline_name: baseline-run" in cli_output.output
    assert "candidate_name: candidate-run" in cli_output.output
    assert "improved: true" in cli_output.output


def test_cli_compare_backtests_validation_failure():
    agent = SimpleNamespace(name="evaluation-agent")

    with pytest.raises(ValueError):
        cli_compare_backtests(
            agent=agent,
            baseline_name="",
            candidate_name="candidate-run",
            operation=fake_compare_backtests,
        )


def test_cli_performance_grade_success():
    agent = SimpleNamespace(name="evaluation-agent")

    cli_output = cli_performance_grade(
        agent=agent,
        name="cli-run-1",
        output_format="text",
        operation=fake_performance_grade,
    )

    assert cli_output.success is True
    assert "SUCCESS: Performance grade loaded." in cli_output.output
    assert "grade: A" in cli_output.output
    assert "score: 0.9" in cli_output.output


def test_cli_evaluation_report_success():
    agent = SimpleNamespace(name="evaluation-agent")

    cli_output = cli_evaluation_report(
        agent=agent,
        name="cli-run-1",
        output_format="text",
        request_id="report-1",
        operation=fake_evaluation_report,
    )

    assert cli_output.success is True
    assert "SUCCESS: Evaluation report loaded." in cli_output.output
    assert "name: cli-run-1" in cli_output.output
    assert "metrics:" in cli_output.output
    assert "total_profit: 75.0" in cli_output.output