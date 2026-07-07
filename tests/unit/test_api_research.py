"""
Unit tests for AQOS API research operations.
"""

from types import SimpleNamespace

import pytest

from aqos.api import (
    CreateExperimentRequest,
    ExperimentPlanRequest,
    ResearchFindingRequest,
    ResearchHypothesisRequest,
    api_create_experiment,
    api_experiment_plan,
    api_record_finding,
    api_research_hypothesis,
    api_research_summary,
    normalize_experiment_plan_request,
    normalize_finding_request,
    normalize_hypothesis_request,
    research_agent_operation,
)


class SuccessfulResearchAgent:
    name = "research-agent"

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
            "hypothesis": {
                "symbol": payload.get("symbol"),
                "timeframe": payload.get("timeframe"),
                "signal_source": payload.get("signal_source"),
                "objective": payload.get("objective"),
                "hypothesis": (
                    f"{payload.get('signal_source')} can help "
                    f"{payload.get('objective')}."
                ),
            },
            "experiment-plan": {
                "name": payload.get("name"),
                "symbol": payload.get("symbol"),
                "timeframe": payload.get("timeframe"),
                "hypothesis": payload.get("hypothesis"),
                "metric": payload.get("metric"),
                "steps": [
                    "Prepare dataset.",
                    "Run baseline.",
                    "Compare candidate.",
                ],
            },
            "create-experiment": {
                "name": payload.get("name"),
                "status": "created",
                "description": payload.get("description"),
                "metadata": payload.get("metadata", {}),
            },
            "record-finding": {
                "finding_id": payload.get("finding_id"),
                "title": payload.get("title"),
                "finding": payload.get("finding"),
                "conclusion": payload.get("conclusion"),
                "metadata": payload.get("metadata", {}),
            },
            "research-summary": {
                "experiments": 1,
                "findings": 1,
                "status": "active",
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


class FailingResearchAgent:
    name = "research-agent"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Research agent failed.",
            data={
                "reason": "invalid research request",
            },
            metadata={},
        )


class BrokenResearchAgent:
    name = "broken-research-agent"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Research agent exploded.")


def sample_hypothesis_request():
    return {
        "symbol": "xauusd",
        "timeframe": "h1",
        "signal_source": "news sentiment",
        "objective": "reduce false entries",
    }


def sample_experiment_plan():
    return {
        "name": "news-sentiment-filter-test",
        "symbol": "xauusd",
        "timeframe": "h1",
        "hypothesis": "News sentiment can reduce false entries.",
        "metric": "win_rate",
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


def test_research_hypothesis_request_defaults():
    request = ResearchHypothesisRequest()

    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "signal_source": "market regime",
        "objective": "improve strategy quality",
    }


def test_research_hypothesis_request_normalizes_values():
    request = ResearchHypothesisRequest(
        symbol="xauusd",
        timeframe="h1",
        signal_source=" news sentiment ",
        objective=" reduce false entries ",
    )

    assert request.to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "signal_source": "news sentiment",
        "objective": "reduce false entries",
    }


def test_research_hypothesis_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ResearchHypothesisRequest(symbol="")

    with pytest.raises(ValueError):
        ResearchHypothesisRequest(timeframe="BAD")

    with pytest.raises(ValueError):
        ResearchHypothesisRequest(signal_source="")

    with pytest.raises(ValueError):
        ResearchHypothesisRequest(objective="")


def test_experiment_plan_request_to_payload():
    request = ExperimentPlanRequest(
        name=" news-filter ",
        symbol="xauusd",
        timeframe="h1",
        hypothesis=" News can improve filtering. ",
        metric=" win_rate ",
    )

    assert request.to_payload() == {
        "name": "news-filter",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "hypothesis": "News can improve filtering.",
        "metric": "win_rate",
    }


def test_experiment_plan_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ExperimentPlanRequest(name="")

    with pytest.raises(ValueError):
        ExperimentPlanRequest(name="experiment", hypothesis="")

    with pytest.raises(ValueError):
        ExperimentPlanRequest(name="experiment", metric="")


def test_create_experiment_request_to_payload():
    request = CreateExperimentRequest(
        name=" experiment-1 ",
        description=" Test experiment. ",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == {
        "name": "experiment-1",
        "description": "Test experiment.",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_create_experiment_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        CreateExperimentRequest(name="")

    with pytest.raises(ValueError):
        CreateExperimentRequest(name="experiment", description=[])

    with pytest.raises(ValueError):
        CreateExperimentRequest(name="experiment", metadata=[])


def test_research_finding_request_to_payload():
    request = ResearchFindingRequest(
        finding_id=" finding-1 ",
        title=" Title ",
        finding=" Finding body. ",
        conclusion=" Conclusion body. ",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == {
        "finding_id": "finding-1",
        "title": "Title",
        "finding": "Finding body.",
        "conclusion": "Conclusion body.",
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_research_finding_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        ResearchFindingRequest(
            finding_id="",
            title="Title",
            finding="Finding.",
            conclusion="Conclusion.",
        )

    with pytest.raises(ValueError):
        ResearchFindingRequest(
            finding_id="finding-1",
            title="",
            finding="Finding.",
            conclusion="Conclusion.",
        )

    with pytest.raises(ValueError):
        ResearchFindingRequest(
            finding_id="finding-1",
            title="Title",
            finding="",
            conclusion="Conclusion.",
        )

    with pytest.raises(ValueError):
        ResearchFindingRequest(
            finding_id="finding-1",
            title="Title",
            finding="Finding.",
            conclusion="",
        )

    with pytest.raises(ValueError):
        ResearchFindingRequest(
            finding_id="finding-1",
            title="Title",
            finding="Finding.",
            conclusion="Conclusion.",
            metadata=[],
        )


def test_normalize_hypothesis_request_preserves_extra_fields():
    normalized = normalize_hypothesis_request(
        {
            **sample_hypothesis_request(),
            "source_id": "source-1",
        }
    )

    assert normalized["symbol"] == "XAUUSD"
    assert normalized["timeframe"] == "H1"
    assert normalized["signal_source"] == "news sentiment"
    assert normalized["source_id"] == "source-1"


def test_normalize_hypothesis_request_rejects_non_dict():
    with pytest.raises(ValueError, match="Hypothesis request"):
        normalize_hypothesis_request("bad")


def test_normalize_experiment_plan_request_preserves_extra_fields():
    normalized = normalize_experiment_plan_request(
        {
            **sample_experiment_plan(),
            "source_id": "source-1",
        }
    )

    assert normalized["name"] == "news-sentiment-filter-test"
    assert normalized["symbol"] == "XAUUSD"
    assert normalized["timeframe"] == "H1"
    assert normalized["metric"] == "win_rate"
    assert normalized["source_id"] == "source-1"


def test_normalize_experiment_plan_request_rejects_non_dict():
    with pytest.raises(ValueError, match="Experiment plan request"):
        normalize_experiment_plan_request("bad")


def test_normalize_finding_request_preserves_extra_fields():
    normalized = normalize_finding_request(
        {
            **sample_finding(),
            "source_id": "source-1",
        }
    )

    assert normalized["finding_id"] == "finding-1"
    assert normalized["title"] == "News sentiment improves filtering"
    assert normalized["metadata"]["symbol"] == "XAUUSD"
    assert normalized["source_id"] == "source-1"


def test_normalize_finding_request_rejects_non_dict():
    with pytest.raises(ValueError, match="Finding request"):
        normalize_finding_request("bad")


def test_research_agent_operation_success():
    agent = SuccessfulResearchAgent()

    response = research_agent_operation(
        agent,
        action="hypothesis",
        payload=sample_hypothesis_request(),
        success_message="Research hypothesis generated.",
        failure_message="Research hypothesis failed.",
        request_id="research-request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Research hypothesis generated."
    assert payload["data"]["action"] == "hypothesis"
    assert payload["data"]["agent"] == "research-agent"
    assert payload["data"]["result"]["signal_source"] == "news sentiment"
    assert payload["metadata"]["request_id"] == "research-request-1"


def test_research_agent_operation_failure():
    response = research_agent_operation(
        FailingResearchAgent(),
        action="hypothesis",
        payload=sample_hypothesis_request(),
        success_message="Research hypothesis generated.",
        failure_message="Research hypothesis failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Research hypothesis failed."
    assert payload["errors"][0]["code"] == "RESEARCH_AGENT_ERROR"
    assert payload["errors"][0]["message"] == "Research agent failed."
    assert payload["data"]["result"] == {
        "reason": "invalid research request",
    }


def test_research_agent_operation_exception():
    response = research_agent_operation(
        BrokenResearchAgent(),
        action="hypothesis",
        payload=sample_hypothesis_request(),
        success_message="Research hypothesis generated.",
        failure_message="Research hypothesis failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Research hypothesis failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Research agent exploded."


def test_api_research_hypothesis_success():
    agent = SuccessfulResearchAgent()

    response = api_research_hypothesis(
        agent,
        hypothesis_request=sample_hypothesis_request(),
        request_id="hypothesis-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Research hypothesis generated."
    assert payload["data"]["action"] == "hypothesis"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["timeframe"] == "H1"
    assert payload["data"]["result"]["signal_source"] == "news sentiment"
    assert payload["metadata"]["request_id"] == "hypothesis-1"

    assert agent.calls[0]["payload"]["symbol"] == "XAUUSD"


def test_api_research_hypothesis_validation_failure():
    response = api_research_hypothesis(
        SuccessfulResearchAgent(),
        hypothesis_request="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "hypothesis_request"


def test_api_experiment_plan_success():
    agent = SuccessfulResearchAgent()

    response = api_experiment_plan(
        agent,
        experiment_plan=sample_experiment_plan(),
        request_id="experiment-plan-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Experiment plan generated."
    assert payload["data"]["action"] == "experiment-plan"
    assert payload["data"]["result"]["name"] == "news-sentiment-filter-test"
    assert payload["data"]["result"]["metric"] == "win_rate"
    assert payload["metadata"]["request_id"] == "experiment-plan-1"

    assert agent.calls[0]["payload"]["symbol"] == "XAUUSD"


def test_api_experiment_plan_validation_failure():
    response = api_experiment_plan(
        SuccessfulResearchAgent(),
        experiment_plan="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "experiment_plan"


def test_api_create_experiment_success():
    agent = SuccessfulResearchAgent()

    response = api_create_experiment(
        agent,
        name="experiment-1",
        description="Test experiment.",
        metadata={
            "symbol": "XAUUSD",
        },
        request_id="create-experiment-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Experiment created."
    assert payload["data"]["action"] == "create-experiment"
    assert payload["data"]["result"]["name"] == "experiment-1"
    assert payload["data"]["result"]["status"] == "created"
    assert payload["metadata"]["request_id"] == "create-experiment-1"


def test_api_create_experiment_validation_failure():
    response = api_create_experiment(
        SuccessfulResearchAgent(),
        name="",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "experiment"


def test_api_record_finding_success():
    agent = SuccessfulResearchAgent()

    response = api_record_finding(
        agent,
        finding=sample_finding(),
        request_id="finding-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Research finding recorded."
    assert payload["data"]["action"] == "record-finding"
    assert payload["data"]["result"]["finding_id"] == "finding-1"
    assert payload["data"]["result"]["title"] == (
        "News sentiment improves filtering"
    )
    assert payload["metadata"]["request_id"] == "finding-1"


def test_api_record_finding_validation_failure():
    response = api_record_finding(
        SuccessfulResearchAgent(),
        finding="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "finding"


def test_api_research_summary_success():
    response = api_research_summary(
        SuccessfulResearchAgent(),
        request_id="research-summary-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Research summary loaded."
    assert payload["data"]["action"] == "research-summary"
    assert payload["data"]["result"]["experiments"] == 1
    assert payload["data"]["result"]["findings"] == 1
    assert payload["metadata"]["request_id"] == "research-summary-1"