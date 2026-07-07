"""
AQOS API orchestrator operations.

This module provides framework-independent API helpers for orchestrated
multi-agent workflows.
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
from aqos.common import (
    DEFAULT_ACCOUNT_BALANCE,
    DEFAULT_RISK_PERCENT,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
)
from aqos.common.validators import (
    validate_account_balance,
    validate_risk_percent,
    validate_symbol,
    validate_timeframe,
)


DEFAULT_ORCHESTRATOR_BACKTEST_NAME = "api-orchestrator-backtest"
DEFAULT_ORCHESTRATOR_PROFITS = [100.0, -50.0, 25.0]


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_dict(value: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Validate dictionary value."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    return value


def validate_positive_number(value: float, field_name: str) -> float:
    """Validate positive number."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number.")

    normalized = float(value)

    if normalized <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return normalized


def validate_profits(profits: list[float]) -> list[float]:
    """Validate backtest profits."""
    if not isinstance(profits, list) or not profits:
        raise ValueError("Profits must be a non-empty list.")

    normalized: list[float] = []

    for profit in profits:
        if not isinstance(profit, int | float) or isinstance(profit, bool):
            raise ValueError("Each profit value must be a number.")

        normalized.append(float(profit))

    return normalized


@dataclass(frozen=True)
class OrchestratorRouteRequest:
    """
    Standard orchestrator route request.
    """

    agent: str
    action: str
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.agent, "Agent")
        validate_non_empty_string(self.action, "Action")
        validate_dict(self.payload, "Payload")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into AgentOrchestrator route payload."""
        return {
            "agent": validate_non_empty_string(self.agent, "Agent"),
            "action": validate_non_empty_string(self.action, "Action"),
            "payload": self.payload,
        }


@dataclass(frozen=True)
class MarketStrategyWorkflowRequest:
    """
    Market → Strategy workflow request.
    """

    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)

    def to_payload(self) -> dict[str, Any]:
        """Convert request into workflow payload."""
        return {
            "symbol": validate_symbol(self.symbol),
            "timeframe": validate_timeframe(self.timeframe),
        }


@dataclass(frozen=True)
class StrategyRiskWorkflowRequest:
    """
    Strategy → Risk workflow request.
    """

    strategy_handoff: dict[str, Any]
    account_balance: float = DEFAULT_ACCOUNT_BALANCE
    risk_percent: float = DEFAULT_RISK_PERCENT

    def __post_init__(self) -> None:
        validate_dict(self.strategy_handoff, "Strategy handoff")
        validate_account_balance(self.account_balance)
        validate_risk_percent(self.risk_percent)

    def to_payload(self) -> dict[str, Any]:
        """Convert request into workflow payload."""
        return {
            "strategy_handoff": self.strategy_handoff,
            "account_balance": validate_account_balance(self.account_balance),
            "risk_percent": validate_risk_percent(self.risk_percent),
        }


@dataclass(frozen=True)
class RiskExecutionWorkflowRequest:
    """
    Risk → Execution workflow request.
    """

    risk_handoff: dict[str, Any]

    def __post_init__(self) -> None:
        validate_dict(self.risk_handoff, "Risk handoff")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into workflow payload."""
        return {
            "risk_handoff": self.risk_handoff,
        }


@dataclass(frozen=True)
class TradeWorkflowRequest:
    """
    Full trade workflow request.
    """

    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    account_balance: float = DEFAULT_ACCOUNT_BALANCE
    risk_percent: float = DEFAULT_RISK_PERCENT

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_account_balance(self.account_balance)
        validate_risk_percent(self.risk_percent)

    def to_payload(self) -> dict[str, Any]:
        """Convert request into workflow payload."""
        return {
            "symbol": validate_symbol(self.symbol),
            "timeframe": validate_timeframe(self.timeframe),
            "account_balance": validate_account_balance(self.account_balance),
            "risk_percent": validate_risk_percent(self.risk_percent),
        }


@dataclass(frozen=True)
class ResearchWorkflowRequest:
    """
    Research workflow request.
    """

    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    signal_source: str = "market regime"
    objective: str = "improve strategy quality"
    experiment_name: str = "api-research-experiment"
    metric: str = "win_rate"

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_non_empty_string(self.signal_source, "Signal source")
        validate_non_empty_string(self.objective, "Objective")
        validate_non_empty_string(self.experiment_name, "Experiment name")
        validate_non_empty_string(self.metric, "Metric")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into workflow payload."""
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
            "experiment_name": validate_non_empty_string(
                self.experiment_name,
                "Experiment name",
            ),
            "metric": validate_non_empty_string(self.metric, "Metric"),
        }


@dataclass(frozen=True)
class BacktestWorkflowRequest:
    """
    Backtest workflow request.
    """

    name: str = DEFAULT_ORCHESTRATOR_BACKTEST_NAME
    profits: list[float] = field(
        default_factory=lambda: DEFAULT_ORCHESTRATOR_PROFITS.copy()
    )
    initial_balance: float = DEFAULT_ACCOUNT_BALANCE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Backtest name")
        validate_profits(self.profits)
        validate_positive_number(self.initial_balance, "Initial balance")
        validate_dict(self.metadata, "Backtest metadata")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into workflow payload."""
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
class MemoryWorkflowRequest:
    """
    Memory workflow request.
    """

    memory_id: str
    content: str
    memory_type: str = "observation"
    importance: float = 0.5
    query: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.memory_id, "Memory ID")
        validate_non_empty_string(self.content, "Memory content")
        validate_non_empty_string(self.memory_type, "Memory type")
        validate_positive_number(self.importance, "Importance")
        validate_dict(self.metadata, "Memory metadata")

        if self.importance > 1:
            raise ValueError("Importance must be between 0 and 1.")

        if self.query is not None:
            validate_non_empty_string(self.query, "Memory query")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into workflow payload."""
        payload: dict[str, Any] = {
            "memory_id": validate_non_empty_string(self.memory_id, "Memory ID"),
            "content": validate_non_empty_string(
                self.content,
                "Memory content",
            ),
            "memory_type": validate_non_empty_string(
                self.memory_type,
                "Memory type",
            ),
            "importance": validate_positive_number(
                self.importance,
                "Importance",
            ),
            "metadata": self.metadata,
        }

        if self.query is not None:
            payload["query"] = validate_non_empty_string(
                self.query,
                "Memory query",
            )

        return payload


def orchestrator_operation(
    orchestrator: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute an AgentOrchestrator action and convert the result into an API response.
    """
    try:
        result = orchestrator.execute(
            action=action,
            payload=payload,
            metadata={
                "request_id": request_id,
            }
            if request_id
            else None,
        )

        response_data = {
            "action": action,
            "orchestrator": getattr(
                orchestrator,
                "name",
                orchestrator.__class__.__name__,
            ),
            "result": result.data,
            "orchestrator_metadata": result.metadata,
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
                    code="ORCHESTRATOR_ERROR",
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


def api_orchestrator_route(
    orchestrator: Any,
    *,
    agent: str,
    action: str,
    payload: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Route a request through AgentOrchestrator."""
    try:
        request = OrchestratorRouteRequest(
            agent=agent,
            action=action,
            payload=payload or {},
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="route",
            details={
                "agent": agent,
                "action": action,
                "payload": payload,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="route",
        payload=request.to_payload(),
        success_message="Orchestrator route completed.",
        failure_message="Orchestrator route could not be completed.",
        request_id=request_id,
    )


def api_market_strategy_workflow(
    orchestrator: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    request_id: str | None = None,
) -> ApiResponse:
    """Run Market → Strategy workflow."""
    try:
        request = MarketStrategyWorkflowRequest(
            symbol=symbol,
            timeframe=timeframe,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="market_strategy_workflow",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="market-strategy-workflow",
        payload=request.to_payload(),
        success_message="Market strategy workflow completed.",
        failure_message="Market strategy workflow could not be completed.",
        request_id=request_id,
    )


def api_strategy_risk_workflow(
    orchestrator: Any,
    *,
    strategy_handoff: dict[str, Any],
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    request_id: str | None = None,
) -> ApiResponse:
    """Run Strategy → Risk workflow."""
    try:
        request = StrategyRiskWorkflowRequest(
            strategy_handoff=strategy_handoff,
            account_balance=account_balance,
            risk_percent=risk_percent,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="strategy_risk_workflow",
            details={
                "strategy_handoff": strategy_handoff,
                "account_balance": account_balance,
                "risk_percent": risk_percent,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="strategy-risk-workflow",
        payload=request.to_payload(),
        success_message="Strategy risk workflow completed.",
        failure_message="Strategy risk workflow could not be completed.",
        request_id=request_id,
    )


def api_risk_execution_workflow(
    orchestrator: Any,
    *,
    risk_handoff: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Run Risk → Execution workflow."""
    try:
        request = RiskExecutionWorkflowRequest(
            risk_handoff=risk_handoff,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="risk_execution_workflow",
            details={
                "risk_handoff": risk_handoff,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="risk-execution-workflow",
        payload=request.to_payload(),
        success_message="Risk execution workflow completed.",
        failure_message="Risk execution workflow could not be completed.",
        request_id=request_id,
    )


def api_trade_workflow(
    orchestrator: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    request_id: str | None = None,
) -> ApiResponse:
    """Run full trade workflow."""
    try:
        request = TradeWorkflowRequest(
            symbol=symbol,
            timeframe=timeframe,
            account_balance=account_balance,
            risk_percent=risk_percent,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade_workflow",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
                "account_balance": account_balance,
                "risk_percent": risk_percent,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="trade-workflow",
        payload=request.to_payload(),
        success_message="Trade workflow completed.",
        failure_message="Trade workflow could not be completed.",
        request_id=request_id,
    )


def api_research_workflow(
    orchestrator: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    signal_source: str = "market regime",
    objective: str = "improve strategy quality",
    experiment_name: str = "api-research-experiment",
    metric: str = "win_rate",
    request_id: str | None = None,
) -> ApiResponse:
    """Run research workflow."""
    try:
        request = ResearchWorkflowRequest(
            symbol=symbol,
            timeframe=timeframe,
            signal_source=signal_source,
            objective=objective,
            experiment_name=experiment_name,
            metric=metric,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="research_workflow",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
                "signal_source": signal_source,
                "objective": objective,
                "experiment_name": experiment_name,
                "metric": metric,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="research-workflow",
        payload=request.to_payload(),
        success_message="Research workflow completed.",
        failure_message="Research workflow could not be completed.",
        request_id=request_id,
    )


def api_backtest_workflow(
    orchestrator: Any,
    *,
    name: str = DEFAULT_ORCHESTRATOR_BACKTEST_NAME,
    profits: list[float] | None = None,
    initial_balance: float = DEFAULT_ACCOUNT_BALANCE,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Run backtest workflow."""
    try:
        request = BacktestWorkflowRequest(
            name=name,
            profits=profits or DEFAULT_ORCHESTRATOR_PROFITS.copy(),
            initial_balance=initial_balance,
            metadata=metadata or {},
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="backtest_workflow",
            details={
                "name": name,
                "profits": profits,
                "initial_balance": initial_balance,
                "metadata": metadata,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="backtest-workflow",
        payload=request.to_payload(),
        success_message="Backtest workflow completed.",
        failure_message="Backtest workflow could not be completed.",
        request_id=request_id,
    )


def api_memory_workflow(
    orchestrator: Any,
    *,
    memory_id: str,
    content: str,
    memory_type: str = "observation",
    importance: float = 0.5,
    query: str | None = None,
    metadata: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Run memory workflow."""
    try:
        request = MemoryWorkflowRequest(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            query=query,
            metadata=metadata or {},
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="memory_workflow",
            details={
                "memory_id": memory_id,
                "content": content,
                "memory_type": memory_type,
                "importance": importance,
                "query": query,
                "metadata": metadata,
            },
            request_id=request_id,
        )

    return orchestrator_operation(
        orchestrator,
        action="memory-workflow",
        payload=request.to_payload(),
        success_message="Memory workflow completed.",
        failure_message="Memory workflow could not be completed.",
        request_id=request_id,
    )