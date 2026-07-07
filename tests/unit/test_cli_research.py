"""
Unit tests for AQOS CLI research commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliCreateExperimentRequest,
    CliExperimentPlanRequest,
    CliResearchFindingRequest,
    CliResearchHypothesisRequest,
    CliResearchSummaryRequest,
    build_research_cli_output,
    cli_create_experiment,
    cli_experiment_plan,
    cli_record_finding,
    cli_research_hypothesis,
    cli_research_summary,
    execute_research_operation,
)


def sample_hypothesis_request():
    return {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "signal_source": "news sentiment",
        "objective": "reduce false entries",
    }


def sample_experiment_plan():
    return {
        "name": "news-filter",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "hypothesis": "News sentiment can reduce false entries.",
        "metric": "win_rate",
    }


def sample_experiment():
    return {
        "name": "experiment-1",
        "description": "Test experiment.",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def sample_finding():
    return {
        "finding_id": "finding-1",
        "title": "News sentiment improves filtering",
        "finding": "Positive news sentiment reduced false short entries.",
        "conclusion": "News sentiment should be included in market context.",
        "metadata": {
            "symbol": "XAUUSD",
            "metric": "win_rate",
        },
    }


def fake_research_hypothesis(agent, hypothesis_request, request_id=None):
    return api_success(
        message="Research hypothesis generated.",
        data={
            "agent": agent.name,
            "symbol": hypothesis_request["symbol"],
            "timeframe": hypothesis_request["timeframe"],
            "signal_source": hypothesis_request["signal_source"],
            "objective": hypothesis_request["objective"],
            "hypothesis": (
                f"{hypothesis_request['signal_source']} can help "
                f"{hypothesis_request['objective']}."
            ),
        },
        request_id=request_id,
    )


def fake_experiment_plan(agent, experiment_plan, request_id=None):
    return api_success(
        message="Experiment plan generated.",
        data={
            "agent": agent.name,
            "name": experiment_plan["name"],
            "symbol": experiment_plan["symbol"],
            "timeframe": experiment_plan["timeframe"],
            "hypothesis": experiment_plan["hypothesis"],
            "metric": experiment_plan["metric"],
            "steps": [
                "Prepare dataset.",
                "Run baseline.",
                "Compare candidate.",
            ],
        },
        request_id=request_id,
    )


def fake_create_experiment(
    agent,
    name,
    description="",
    metadata=None,
    request_id=None,
):
    return api_success(
        message="Experiment created.",
        data={
            "agent": agent.name,
            "name": name,
            "status": "created",
            "description": description,
            "metadata": metadata or {},
        },
        request_id=request_id,
    )


def fake_record_finding(agent, finding, request_id=None):
    return api_success(
        message="Research finding recorded.",
        data={
            "agent": agent.name,
            "finding_id": finding["finding_id"],
            "title": finding["title"],
            "finding": finding["finding"],
            "conclusion": finding["conclusion"],
            "metadata": finding["metadata"],
        },
        request_id=request_id,
    )


def fake_research_summary(agent, request_id=None):
    return api_success(
        message="Research summary loaded.",
        data={
            "agent": agent.name,
            "experiments": 1,
            "findings": 1,
            "status": "active",
        },
        request_id=request_id,
    )


def fake_failure_research(agent, hypothesis_request=None, request_id=None):
    return api_failure(
        message="Research command failed.",
        data={
            "symbol": (
                hypothesis_request.get("symbol")
                if hypothesis_request
                else "XAUUSD"
            ),
        },
        request_id=request_id,
    )


def test_cli_research_hypothesis_request_accepts_valid_values():
    agent = SimpleNamespace(name="research-agent")

    request = CliResearchHypothesisRequest(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        signal_source=" news sentiment ",
        objective=" reduce false entries ",
        output_format="pretty-json",
        include_metadata=True,
        request_id="research-request-1",
    )

    assert request.agent == agent
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "research-request-1"
    assert request.to_payload() == sample_hypothesis_request()


def test_cli_research_hypothesis_request_rejects_invalid_values():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=None)

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=agent, symbol="")

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=agent, timeframe="BAD")

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=agent, signal_source="")

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=agent, objective="")

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=agent, output_format="bad")

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=agent, include_metadata="yes")

    with pytest.raises(ValueError):
        CliResearchHypothesisRequest(agent=agent, request_id="")


def test_cli_experiment_plan_request_accepts_valid_values():
    agent = SimpleNamespace(name="research-agent")

    request = CliExperimentPlanRequest(
        agent=agent,
        name=" news-filter ",
        symbol="xauusd",
        timeframe="h1",
        hypothesis=" News sentiment can reduce false entries. ",
        metric=" win_rate ",
    )

    assert request.to_payload() == sample_experiment_plan()


def test_cli_experiment_plan_request_rejects_invalid_values():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        CliExperimentPlanRequest(agent=None)

    with pytest.raises(ValueError):
        CliExperimentPlanRequest(agent=agent, name="")

    with pytest.raises(ValueError):
        CliExperimentPlanRequest(agent=agent, hypothesis="")

    with pytest.raises(ValueError):
        CliExperimentPlanRequest(agent=agent, metric="")


def test_cli_create_experiment_request_accepts_valid_values():
    agent = SimpleNamespace(name="research-agent")

    request = CliCreateExperimentRequest(
        agent=agent,
        name=" experiment-1 ",
        description=" Test experiment. ",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == sample_experiment()


def test_cli_create_experiment_request_rejects_invalid_values():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        CliCreateExperimentRequest(agent=None, name="experiment-1")

    with pytest.raises(ValueError):
        CliCreateExperimentRequest(agent=agent, name="")

    with pytest.raises(ValueError):
        CliCreateExperimentRequest(agent=agent, name="experiment-1", metadata=[])


def test_cli_research_finding_request_accepts_valid_values():
    agent = SimpleNamespace(name="research-agent")

    request = CliResearchFindingRequest(
        agent=agent,
        finding_id=" finding-1 ",
        title=" News sentiment improves filtering ",
        finding=" Positive news sentiment reduced false short entries. ",
        conclusion=" News sentiment should be included in market context. ",
        metadata={
            "symbol": "XAUUSD",
            "metric": "win_rate",
        },
    )

    assert request.to_payload() == sample_finding()


def test_cli_research_finding_request_rejects_invalid_values():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        CliResearchFindingRequest(
            agent=None,
            finding_id="finding-1",
            title="Title",
            finding="Finding.",
            conclusion="Conclusion.",
        )

    with pytest.raises(ValueError):
        CliResearchFindingRequest(
            agent=agent,
            finding_id="",
            title="Title",
            finding="Finding.",
            conclusion="Conclusion.",
        )

    with pytest.raises(ValueError):
        CliResearchFindingRequest(
            agent=agent,
            finding_id="finding-1",
            title="",
            finding="Finding.",
            conclusion="Conclusion.",
        )

    with pytest.raises(ValueError):
        CliResearchFindingRequest(
            agent=agent,
            finding_id="finding-1",
            title="Title",
            finding="",
            conclusion="Conclusion.",
        )

    with pytest.raises(ValueError):
        CliResearchFindingRequest(
            agent=agent,
            finding_id="finding-1",
            title="Title",
            finding="Finding.",
            conclusion="",
        )

    with pytest.raises(ValueError):
        CliResearchFindingRequest(
            agent=agent,
            finding_id="finding-1",
            title="Title",
            finding="Finding.",
            conclusion="Conclusion.",
            metadata=[],
        )


def test_cli_research_summary_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        CliResearchSummaryRequest(agent=None)

    with pytest.raises(ValueError):
        CliResearchSummaryRequest(
            agent=SimpleNamespace(name="research-agent"),
            output_format="bad",
        )


def test_execute_research_operation_with_request_id():
    agent = SimpleNamespace(name="research-agent")

    response = execute_research_operation(
        fake_research_hypothesis,
        agent=agent,
        hypothesis_request=sample_hypothesis_request(),
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["agent"] == "research-agent"


def test_execute_research_operation_rejects_invalid_values():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        execute_research_operation(
            "not-callable",
            agent=agent,
        )

    with pytest.raises(ValueError):
        execute_research_operation(
            fake_research_hypothesis,
            agent=None,
        )


def test_build_research_cli_output_success():
    agent = SimpleNamespace(name="research-agent")

    response = fake_research_hypothesis(
        agent,
        sample_hypothesis_request(),
        request_id="request-1",
    )

    cli_output = build_research_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Research hypothesis generated." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_research_cli_output_failure():
    agent = SimpleNamespace(name="research-agent")

    response = fake_failure_research(
        agent,
        sample_hypothesis_request(),
    )

    cli_output = build_research_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Research command failed."


def test_cli_research_hypothesis_text_success():
    agent = SimpleNamespace(name="research-agent")

    cli_output = cli_research_hypothesis(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        signal_source="news sentiment",
        objective="reduce false entries",
        output_format="text",
        request_id="hypothesis-1",
        operation=fake_research_hypothesis,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Research hypothesis generated." in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "timeframe: H1" in cli_output.output
    assert "signal_source: news sentiment" in cli_output.output


def test_cli_research_hypothesis_json_success():
    agent = SimpleNamespace(name="research-agent")

    cli_output = cli_research_hypothesis(
        agent=agent,
        symbol="xauusd",
        timeframe="h1",
        signal_source="news sentiment",
        objective="reduce false entries",
        output_format="json",
        operation=fake_research_hypothesis,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["symbol"] == "XAUUSD"
    assert payload["data"]["signal_source"] == "news sentiment"
    assert "metadata" not in payload


def test_cli_research_hypothesis_validation_failure():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        cli_research_hypothesis(
            agent=agent,
            symbol="",
            operation=fake_research_hypothesis,
        )


def test_cli_experiment_plan_success():
    agent = SimpleNamespace(name="research-agent")

    cli_output = cli_experiment_plan(
        agent=agent,
        name="news-filter",
        symbol="xauusd",
        timeframe="h1",
        hypothesis="News sentiment can reduce false entries.",
        metric="win_rate",
        output_format="text",
        operation=fake_experiment_plan,
    )

    assert cli_output.success is True
    assert "SUCCESS: Experiment plan generated." in cli_output.output
    assert "name: news-filter" in cli_output.output
    assert "metric: win_rate" in cli_output.output
    assert "Prepare dataset." in cli_output.output


def test_cli_create_experiment_success():
    agent = SimpleNamespace(name="research-agent")

    cli_output = cli_create_experiment(
        agent=agent,
        name="experiment-1",
        description="Test experiment.",
        metadata={
            "symbol": "XAUUSD",
        },
        output_format="text",
        request_id="create-experiment-1",
        operation=fake_create_experiment,
    )

    assert cli_output.success is True
    assert "SUCCESS: Experiment created." in cli_output.output
    assert "name: experiment-1" in cli_output.output
    assert "status: created" in cli_output.output


def test_cli_create_experiment_validation_failure():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        cli_create_experiment(
            agent=agent,
            name="",
            operation=fake_create_experiment,
        )


def test_cli_record_finding_success():
    agent = SimpleNamespace(name="research-agent")

    cli_output = cli_record_finding(
        agent=agent,
        finding_id="finding-1",
        title="News sentiment improves filtering",
        finding="Positive news sentiment reduced false short entries.",
        conclusion="News sentiment should be included in market context.",
        metadata={
            "symbol": "XAUUSD",
            "metric": "win_rate",
        },
        output_format="text",
        request_id="finding-1",
        operation=fake_record_finding,
    )

    assert cli_output.success is True
    assert "SUCCESS: Research finding recorded." in cli_output.output
    assert "finding_id: finding-1" in cli_output.output
    assert "News sentiment improves filtering" in cli_output.output


def test_cli_record_finding_validation_failure():
    agent = SimpleNamespace(name="research-agent")

    with pytest.raises(ValueError):
        cli_record_finding(
            agent=agent,
            finding_id="",
            title="Title",
            finding="Finding.",
            conclusion="Conclusion.",
            operation=fake_record_finding,
        )


def test_cli_research_summary_success():
    agent = SimpleNamespace(name="research-agent")

    cli_output = cli_research_summary(
        agent=agent,
        output_format="text",
        request_id="summary-1",
        operation=fake_research_summary,
    )

    assert cli_output.success is True
    assert "SUCCESS: Research summary loaded." in cli_output.output
    assert "experiments: 1" in cli_output.output
    assert "findings: 1" in cli_output.output
    assert "status: active" in cli_output.output