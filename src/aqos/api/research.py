"""
AQOS API research operations.

This module provides framework-independent API helpers for research-facing
operations. It wraps ResearchAgent actions in consistent ApiResponse envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.api.responses import (
    ApiResponse,
    api_error,
    api_failure,
    api_success,
    exception_failure,
    validation_failure,
)
from aqos.common import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from aqos.common.validators import validate_symbol, validate_timeframe


DEFAULT_SIGNAL_SOURCE = "market regime"
DEFAULT_RESEARCH_OBJECTIVE = "improve strategy quality"
DEFAULT_RESEARCH_METRIC = "win_rate"


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_metadata(metadata: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Validate metadata dictionary."""
    if not isinstance(metadata, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    return metadata


@dataclass(frozen=True)
class ResearchHypothesisRequest:
    """
    Standard research API hypothesis request.
    """

    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    signal_source: str = DEFAULT_SIGNAL_SOURCE
    objective: str = DEFAULT_RESEARCH_OBJECTIVE

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_non_empty_string(self.signal_source, "Signal source")
        validate_non_empty_string(self.objective, "Objective")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into ResearchAgent payload."""
        return {
            "symbol": validate_symbol(self.symbol),
            "timeframe": validate_timeframe(self.timeframe),
            "signal_source": validate_non_empty_string(
                self.signal_source,
                "Signal source",
            ),
            "objective": validate_non_empty_string(
                self.objective,
                "Objective",
            ),
        }


@dataclass(frozen=True)
class ExperimentPlanRequest:
    """
    Standard research API experiment-plan request.
    """

    name: str
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    hypothesis: str = "Market regime improves strategy quality."
    metric: str = DEFAULT_RESEARCH_METRIC

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Experiment name")
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_non_empty_string(self.hypothesis, "Hypothesis")
        validate_non_empty_string(self.metric, "Metric")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into ResearchAgent payload."""
        return {
            "name": validate_non_empty_string(self.name, "Experiment name"),
            "symbol": validate_symbol(self.symbol),
            "timeframe": validate_timeframe(self.timeframe),
            "hypothesis": validate_non_empty_string(
                self.hypothesis,
                "Hypothesis",
            ),
            "metric": validate_non_empty_string(self.metric, "Metric"),
        }


@dataclass(frozen=True)
class CreateExperimentRequest:
    """
    Standard research API create-experiment request.
    """

    name: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Experiment name")

        if not isinstance(self.description, str):
            raise ValueError("Experiment description must be a string.")

        validate_metadata(self.metadata, "Experiment metadata")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into ResearchAgent payload."""
        return {
            "name": validate_non_empty_string(self.name, "Experiment name"),
            "description": self.description.strip(),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ResearchFindingRequest:
    """
    Standard research API finding request.
    """

    finding_id: str
    title: str
    finding: str
    conclusion: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.finding_id, "Finding ID")
        validate_non_empty_string(self.title, "Finding title")
        validate_non_empty_string(self.finding, "Finding")
        validate_non_empty_string(self.conclusion, "Conclusion")
        validate_metadata(self.metadata, "Finding metadata")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into ResearchAgent payload."""
        return {
            "finding_id": validate_non_empty_string(
                self.finding_id,
                "Finding ID",
            ),
            "title": validate_non_empty_string(
                self.title,
                "Finding title",
            ),
            "finding": validate_non_empty_string(
                self.finding,
                "Finding",
            ),
            "conclusion": validate_non_empty_string(
                self.conclusion,
                "Conclusion",
            ),
            "metadata": self.metadata,
        }


def normalize_hypothesis_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external hypothesis request dictionary."""
    if not isinstance(request, dict):
        raise ValueError("Hypothesis request must be a dictionary.")

    normalized_request = ResearchHypothesisRequest(
        symbol=request.get("symbol", DEFAULT_SYMBOL),
        timeframe=request.get("timeframe", DEFAULT_TIMEFRAME),
        signal_source=request.get("signal_source", DEFAULT_SIGNAL_SOURCE),
        objective=request.get("objective", DEFAULT_RESEARCH_OBJECTIVE),
    )

    normalized = normalized_request.to_payload()

    for key, value in request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def normalize_experiment_plan_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external experiment-plan request dictionary."""
    if not isinstance(request, dict):
        raise ValueError("Experiment plan request must be a dictionary.")

    normalized_request = ExperimentPlanRequest(
        name=request.get("name", ""),
        symbol=request.get("symbol", DEFAULT_SYMBOL),
        timeframe=request.get("timeframe", DEFAULT_TIMEFRAME),
        hypothesis=request.get(
            "hypothesis",
            "Market regime improves strategy quality.",
        ),
        metric=request.get("metric", DEFAULT_RESEARCH_METRIC),
    )

    normalized = normalized_request.to_payload()

    for key, value in request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def normalize_finding_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external research finding request dictionary."""
    if not isinstance(request, dict):
        raise ValueError("Finding request must be a dictionary.")

    normalized_request = ResearchFindingRequest(
        finding_id=request.get("finding_id", ""),
        title=request.get("title", ""),
        finding=request.get("finding", ""),
        conclusion=request.get("conclusion", ""),
        metadata=request.get("metadata", {}),
    )

    normalized = normalized_request.to_payload()

    for key, value in request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def research_agent_operation(
    agent: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute a ResearchAgent action and convert the result into an API response.
    """
    try:
        result = agent.execute(
            action=action,
            payload=payload,
        )

        response_data = {
            "action": action,
            "agent": getattr(agent, "name", agent.__class__.__name__),
            "result": result.data,
            "agent_metadata": result.metadata,
        }

        if result.success:
            return api_success(
                message=success_message,
                data=response_data,
                request_id=request_id,
            )

        return api_failure(
            message=failure_message,
            data=response_data,
            errors=[
                api_error(
                    code="RESEARCH_AGENT_ERROR",
                    message=result.message,
                    details={
                        "action": action,
                        "payload": payload,
                    },
                )
            ],
            request_id=request_id,
        )

    except Exception as exception:
        return exception_failure(
            exception,
            message=f"{failure_message} Unexpected exception.",
            request_id=request_id,
        )


def api_research_hypothesis(
    agent: Any,
    *,
    hypothesis_request: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Generate a research hypothesis through ResearchAgent."""
    try:
        payload = normalize_hypothesis_request(hypothesis_request)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="hypothesis_request",
            details={
                "hypothesis_request": hypothesis_request,
            },
            request_id=request_id,
        )

    return research_agent_operation(
        agent,
        action="hypothesis",
        payload=payload,
        success_message="Research hypothesis generated.",
        failure_message="Research hypothesis could not be generated.",
        request_id=request_id,
    )


def api_experiment_plan(
    agent: Any,
    *,
    experiment_plan: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Generate an experiment plan through ResearchAgent."""
    try:
        payload = normalize_experiment_plan_request(experiment_plan)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="experiment_plan",
            details={
                "experiment_plan": experiment_plan,
            },
            request_id=request_id,
        )

    return research_agent_operation(
        agent,
        action="experiment-plan",
        payload=payload,
        success_message="Experiment plan generated.",
        failure_message="Experiment plan could not be generated.",
        request_id=request_id,
    )


def api_create_experiment(
    agent: Any,
    *,
    name: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Create a research experiment through ResearchAgent."""
    try:
        request = CreateExperimentRequest(
            name=name,
            description=description,
            metadata=metadata or {},
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="experiment",
            details={
                "name": name,
                "description": description,
                "metadata": metadata,
            },
            request_id=request_id,
        )

    return research_agent_operation(
        agent,
        action="create-experiment",
        payload=request.to_payload(),
        success_message="Experiment created.",
        failure_message="Experiment could not be created.",
        request_id=request_id,
    )


def api_record_finding(
    agent: Any,
    *,
    finding: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Record a research finding through ResearchAgent."""
    try:
        payload = normalize_finding_request(finding)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="finding",
            details={
                "finding": finding,
            },
            request_id=request_id,
        )

    return research_agent_operation(
        agent,
        action="record-finding",
        payload=payload,
        success_message="Research finding recorded.",
        failure_message="Research finding could not be recorded.",
        request_id=request_id,
    )


def api_research_summary(
    agent: Any,
    *,
    request_id: str | None = None,
) -> ApiResponse:
    """Return research summary through ResearchAgent."""
    return research_agent_operation(
        agent,
        action="research-summary",
        payload={},
        success_message="Research summary loaded.",
        failure_message="Research summary could not be loaded.",
        request_id=request_id,
    )