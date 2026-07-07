"""
AQOS CLI evaluation commands.

This module converts AQOS API evaluation operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aqos.api import (
    ApiResponse,
    BacktestNameRequest,
    CompareBacktestsRequest,
    EvaluationBacktestRequest,
    api_backtest_summary,
    api_compare_backtests,
    api_evaluation_report,
    api_performance_grade,
    api_run_backtest,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
)


DEFAULT_CLI_BACKTEST_NAME = "cli-backtest-run"
DEFAULT_CLI_INITIAL_BALANCE = 10_000.0


@dataclass(frozen=True)
class CliEvaluationBacktestRequest:
    """
    Standard CLI evaluation backtest request.
    """

    agent: Any
    name: str = DEFAULT_CLI_BACKTEST_NAME
    profits: list[float] = field(default_factory=lambda: [100.0, -50.0, 25.0])
    initial_balance: float = DEFAULT_CLI_INITIAL_BALANCE
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Evaluation agent is required.")

        EvaluationBacktestRequest(
            name=self.name,
            profits=self.profits,
            initial_balance=self.initial_balance,
            metadata=self.metadata,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_backtest(self) -> dict[str, Any]:
        """Convert CLI request into evaluation backtest payload."""
        return EvaluationBacktestRequest(
            name=self.name,
            profits=self.profits,
            initial_balance=self.initial_balance,
            metadata=self.metadata,
        ).to_payload()


@dataclass(frozen=True)
class CliBacktestNameRequest:
    """
    Standard CLI backtest-name request.
    """

    agent: Any
    name: str
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Evaluation agent is required.")

        BacktestNameRequest(name=self.name)
        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into backtest-name payload."""
        return BacktestNameRequest(name=self.name).to_payload()


@dataclass(frozen=True)
class CliCompareBacktestsRequest:
    """
    Standard CLI compare-backtests request.
    """

    agent: Any
    baseline_name: str
    candidate_name: str
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Evaluation agent is required.")

        CompareBacktestsRequest(
            baseline_name=self.baseline_name,
            candidate_name=self.candidate_name,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into compare-backtests payload."""
        return CompareBacktestsRequest(
            baseline_name=self.baseline_name,
            candidate_name=self.candidate_name,
        ).to_payload()


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_evaluation_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI evaluation operation callback."""
    if not callable(operation):
        raise ValueError("Evaluation operation must be callable.")

    return operation


def execute_evaluation_operation(
    operation: Callable[..., ApiResponse],
    *,
    agent: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute an evaluation API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_evaluation_operation(operation)

    if agent is None:
        raise ValueError("Evaluation agent is required.")

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


def build_evaluation_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for an evaluation API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def cli_run_backtest(
    *,
    agent: Any,
    name: str = DEFAULT_CLI_BACKTEST_NAME,
    profits: list[float] | None = None,
    initial_balance: float = DEFAULT_CLI_INITIAL_BALANCE,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_run_backtest,
) -> CliOutput:
    """Run backtest command."""
    request = CliEvaluationBacktestRequest(
        agent=agent,
        name=name,
        profits=profits or [100.0, -50.0, 25.0],
        initial_balance=initial_balance,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_evaluation_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        backtest=request.to_backtest(),
    )

    return build_evaluation_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_backtest_summary(
    *,
    agent: Any,
    name: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_backtest_summary,
) -> CliOutput:
    """Run backtest-summary command."""
    request = CliBacktestNameRequest(
        agent=agent,
        name=name,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_evaluation_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_evaluation_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_compare_backtests(
    *,
    agent: Any,
    baseline_name: str,
    candidate_name: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_compare_backtests,
) -> CliOutput:
    """Run compare-backtests command."""
    request = CliCompareBacktestsRequest(
        agent=agent,
        baseline_name=baseline_name,
        candidate_name=candidate_name,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_evaluation_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_evaluation_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_performance_grade(
    *,
    agent: Any,
    name: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_performance_grade,
) -> CliOutput:
    """Run performance-grade command."""
    request = CliBacktestNameRequest(
        agent=agent,
        name=name,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_evaluation_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_evaluation_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_evaluation_report(
    *,
    agent: Any,
    name: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_evaluation_report,
) -> CliOutput:
    """Run evaluation-report command."""
    request = CliBacktestNameRequest(
        agent=agent,
        name=name,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_evaluation_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_evaluation_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )