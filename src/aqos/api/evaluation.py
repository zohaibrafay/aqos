"""
AQOS API evaluation operations.

This module provides framework-independent API helpers for evaluation-facing
operations. It wraps EvaluationAgent actions in consistent ApiResponse envelopes.
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


DEFAULT_BACKTEST_NAME = "api-backtest-run"
DEFAULT_INITIAL_BALANCE = 10_000.0


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_positive_number(value: float, field_name: str) -> float:
    """Validate a positive number."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number.")

    normalized = float(value)

    if normalized <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return normalized


def validate_profits(profits: list[float]) -> list[float]:
    """Validate a list of profit/loss values."""
    if not isinstance(profits, list) or not profits:
        raise ValueError("Profits must be a non-empty list.")

    normalized: list[float] = []

    for profit in profits:
        if not isinstance(profit, int | float) or isinstance(profit, bool):
            raise ValueError("Each profit value must be a number.")

        normalized.append(float(profit))

    return normalized


@dataclass(frozen=True)
class EvaluationBacktestRequest:
    """
    Standard evaluation API backtest request.
    """

    name: str = DEFAULT_BACKTEST_NAME
    profits: list[float] = field(default_factory=lambda: [100.0, -50.0, 25.0])
    initial_balance: float = DEFAULT_INITIAL_BALANCE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Backtest name")
        validate_profits(self.profits)
        validate_positive_number(self.initial_balance, "Initial balance")

        if not isinstance(self.metadata, dict):
            raise ValueError("Backtest metadata must be a dictionary.")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into EvaluationAgent payload."""
        return {
            "name": validate_non_empty_string(self.name, "Backtest name"),
            "profits": validate_profits(self.profits),
            "initial_balance": validate_positive_number(
                self.initial_balance,
                "Initial balance",
            ),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestNameRequest:
    """
    Standard evaluation API backtest-name request.
    """

    name: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Backtest name")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into EvaluationAgent payload."""
        return {
            "name": validate_non_empty_string(self.name, "Backtest name"),
        }


@dataclass(frozen=True)
class CompareBacktestsRequest:
    """
    Standard evaluation API compare-backtests request.
    """

    baseline_name: str
    candidate_name: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.baseline_name, "Baseline name")
        validate_non_empty_string(self.candidate_name, "Candidate name")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into EvaluationAgent payload."""
        return {
            "baseline_name": validate_non_empty_string(
                self.baseline_name,
                "Baseline name",
            ),
            "candidate_name": validate_non_empty_string(
                self.candidate_name,
                "Candidate name",
            ),
        }


def normalize_backtest_request(
    backtest: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external backtest request dictionary."""
    if not isinstance(backtest, dict):
        raise ValueError("Backtest request must be a dictionary.")

    request = EvaluationBacktestRequest(
        name=backtest.get("name", DEFAULT_BACKTEST_NAME),
        profits=backtest.get("profits", [100.0, -50.0, 25.0]),
        initial_balance=backtest.get("initial_balance", DEFAULT_INITIAL_BALANCE),
        metadata=backtest.get("metadata", {}),
    )

    normalized = request.to_payload()

    for key, value in backtest.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def evaluation_agent_operation(
    agent: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute an EvaluationAgent action and convert the result into an API response.
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
                    code="EVALUATION_AGENT_ERROR",
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


def api_run_backtest(
    agent: Any,
    *,
    backtest: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Run a backtest through EvaluationAgent."""
    try:
        payload = normalize_backtest_request(backtest)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="backtest",
            details={
                "backtest": backtest,
            },
            request_id=request_id,
        )

    return evaluation_agent_operation(
        agent,
        action="run-backtest",
        payload=payload,
        success_message="Backtest executed.",
        failure_message="Backtest could not be executed.",
        request_id=request_id,
    )


def api_backtest_summary(
    agent: Any,
    *,
    name: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Return a backtest summary through EvaluationAgent."""
    try:
        request = BacktestNameRequest(name=name)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="name",
            details={
                "name": name,
            },
            request_id=request_id,
        )

    return evaluation_agent_operation(
        agent,
        action="backtest-summary",
        payload=request.to_payload(),
        success_message="Backtest summary loaded.",
        failure_message="Backtest summary could not be loaded.",
        request_id=request_id,
    )


def api_compare_backtests(
    agent: Any,
    *,
    baseline_name: str,
    candidate_name: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Compare two backtests through EvaluationAgent."""
    try:
        request = CompareBacktestsRequest(
            baseline_name=baseline_name,
            candidate_name=candidate_name,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="compare_backtests",
            details={
                "baseline_name": baseline_name,
                "candidate_name": candidate_name,
            },
            request_id=request_id,
        )

    return evaluation_agent_operation(
        agent,
        action="compare-backtests",
        payload=request.to_payload(),
        success_message="Backtests compared.",
        failure_message="Backtests could not be compared.",
        request_id=request_id,
    )


def api_performance_grade(
    agent: Any,
    *,
    name: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Return performance grade through EvaluationAgent."""
    try:
        request = BacktestNameRequest(name=name)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="name",
            details={
                "name": name,
            },
            request_id=request_id,
        )

    return evaluation_agent_operation(
        agent,
        action="performance-grade",
        payload=request.to_payload(),
        success_message="Performance grade loaded.",
        failure_message="Performance grade could not be loaded.",
        request_id=request_id,
    )


def api_evaluation_report(
    agent: Any,
    *,
    name: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Return evaluation report through EvaluationAgent."""
    try:
        request = BacktestNameRequest(name=name)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="name",
            details={
                "name": name,
            },
            request_id=request_id,
        )

    return evaluation_agent_operation(
        agent,
        action="evaluation-report",
        payload=request.to_payload(),
        success_message="Evaluation report loaded.",
        failure_message="Evaluation report could not be loaded.",
        request_id=request_id,
    )