"""
AQOS CLI research commands.

This module converts AQOS API research operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aqos.api import (
    ApiResponse,
    CreateExperimentRequest,
    ExperimentPlanRequest,
    ResearchFindingRequest,
    ResearchHypothesisRequest,
    api_create_experiment,
    api_experiment_plan,
    api_record_finding,
    api_research_hypothesis,
    api_research_summary,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
)
from aqos.common import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME


DEFAULT_CLI_SIGNAL_SOURCE = "market regime"
DEFAULT_CLI_RESEARCH_OBJECTIVE = "improve strategy quality"
DEFAULT_CLI_EXPERIMENT_NAME = "cli-research-experiment"
DEFAULT_CLI_RESEARCH_METRIC = "win_rate"
DEFAULT_CLI_RESEARCH_HYPOTHESIS = "Market regime improves strategy quality."


@dataclass(frozen=True)
class CliResearchHypothesisRequest:
    """
    Standard CLI research hypothesis request.
    """

    agent: Any
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    signal_source: str = DEFAULT_CLI_SIGNAL_SOURCE
    objective: str = DEFAULT_CLI_RESEARCH_OBJECTIVE
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Research agent is required.")

        ResearchHypothesisRequest(
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal_source=self.signal_source,
            objective=self.objective,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into research hypothesis payload."""
        return ResearchHypothesisRequest(
            symbol=self.symbol,
            timeframe=self.timeframe,
            signal_source=self.signal_source,
            objective=self.objective,
        ).to_payload()


@dataclass(frozen=True)
class CliExperimentPlanRequest:
    """
    Standard CLI experiment-plan request.
    """

    agent: Any
    name: str = DEFAULT_CLI_EXPERIMENT_NAME
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    hypothesis: str = DEFAULT_CLI_RESEARCH_HYPOTHESIS
    metric: str = DEFAULT_CLI_RESEARCH_METRIC
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Research agent is required.")

        ExperimentPlanRequest(
            name=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            hypothesis=self.hypothesis,
            metric=self.metric,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into experiment-plan payload."""
        return ExperimentPlanRequest(
            name=self.name,
            symbol=self.symbol,
            timeframe=self.timeframe,
            hypothesis=self.hypothesis,
            metric=self.metric,
        ).to_payload()


@dataclass(frozen=True)
class CliCreateExperimentRequest:
    """
    Standard CLI create-experiment request.
    """

    agent: Any
    name: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Research agent is required.")

        CreateExperimentRequest(
            name=self.name,
            description=self.description,
            metadata=self.metadata,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into create-experiment payload."""
        return CreateExperimentRequest(
            name=self.name,
            description=self.description,
            metadata=self.metadata,
        ).to_payload()


@dataclass(frozen=True)
class CliResearchFindingRequest:
    """
    Standard CLI research finding request.
    """

    agent: Any
    finding_id: str
    title: str
    finding: str
    conclusion: str
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Research agent is required.")

        ResearchFindingRequest(
            finding_id=self.finding_id,
            title=self.title,
            finding=self.finding,
            conclusion=self.conclusion,
            metadata=self.metadata,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into research finding payload."""
        return ResearchFindingRequest(
            finding_id=self.finding_id,
            title=self.title,
            finding=self.finding,
            conclusion=self.conclusion,
            metadata=self.metadata,
        ).to_payload()


@dataclass(frozen=True)
class CliResearchSummaryRequest:
    """
    Standard CLI research-summary request.
    """

    agent: Any
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Research agent is required.")

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_research_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI research operation callback."""
    if not callable(operation):
        raise ValueError("Research operation must be callable.")

    return operation


def execute_research_operation(
    operation: Callable[..., ApiResponse],
    *,
    agent: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute a research API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_research_operation(operation)

    if agent is None:
        raise ValueError("Research agent is required.")

    if request_id is not None:
        try:
            return operation(
                agent,
                request_id=request_id,
                **kwargs,
            )
        except TypeError:
            return operation(
                agent,
                **kwargs,
            )

    return operation(
        agent,
        **kwargs,
    )


def build_research_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for a research API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def cli_research_hypothesis(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    signal_source: str = DEFAULT_CLI_SIGNAL_SOURCE,
    objective: str = DEFAULT_CLI_RESEARCH_OBJECTIVE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_research_hypothesis,
) -> CliOutput:
    """Run research-hypothesis command."""
    request = CliResearchHypothesisRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        signal_source=signal_source,
        objective=objective,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_research_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        hypothesis_request=request.to_payload(),
    )

    return build_research_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_experiment_plan(
    *,
    agent: Any,
    name: str = DEFAULT_CLI_EXPERIMENT_NAME,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    hypothesis: str = DEFAULT_CLI_RESEARCH_HYPOTHESIS,
    metric: str = DEFAULT_CLI_RESEARCH_METRIC,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_experiment_plan,
) -> CliOutput:
    """Run experiment-plan command."""
    request = CliExperimentPlanRequest(
        agent=agent,
        name=name,
        symbol=symbol,
        timeframe=timeframe,
        hypothesis=hypothesis,
        metric=metric,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_research_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        experiment_plan=request.to_payload(),
    )

    return build_research_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_create_experiment(
    *,
    agent: Any,
    name: str,
    description: str = "",
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_create_experiment,
) -> CliOutput:
    """Run create-experiment command."""
    request = CliCreateExperimentRequest(
        agent=agent,
        name=name,
        description=description,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_research_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_research_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_record_finding(
    *,
    agent: Any,
    finding_id: str,
    title: str,
    finding: str,
    conclusion: str,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_record_finding,
) -> CliOutput:
    """Run record-finding command."""
    request = CliResearchFindingRequest(
        agent=agent,
        finding_id=finding_id,
        title=title,
        finding=finding,
        conclusion=conclusion,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_research_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        finding=request.to_payload(),
    )

    return build_research_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_research_summary(
    *,
    agent: Any,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_research_summary,
) -> CliOutput:
    """Run research-summary command."""
    request = CliResearchSummaryRequest(
        agent=agent,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_research_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
    )

    return build_research_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )