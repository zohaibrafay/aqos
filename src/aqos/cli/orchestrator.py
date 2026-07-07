"""
AQOS CLI orchestrator workflow commands.

This module converts AQOS API orchestrator operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aqos.api import (
    ApiResponse,
    api_backtest_workflow,
    api_market_strategy_workflow,
    api_memory_workflow,
    api_orchestrator_route,
    api_research_workflow,
    api_risk_execution_workflow,
    api_strategy_risk_workflow,
    api_trade_workflow,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
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
    validate_side,
    validate_symbol,
    validate_timeframe,
)


DEFAULT_CLI_ORCHESTRATOR_AGENT_NAME = "market"
DEFAULT_CLI_ORCHESTRATOR_ACTION = "health"
DEFAULT_CLI_ORCHESTRATOR_REGIME = "bullish"
DEFAULT_CLI_ORCHESTRATOR_TREND = "uptrend"
DEFAULT_CLI_ORCHESTRATOR_ENTRY_PRICE = 2025.0
DEFAULT_CLI_ORCHESTRATOR_SIDE = "buy"
DEFAULT_CLI_ORCHESTRATOR_POSITION_SIZE = 10.0
DEFAULT_CLI_ORCHESTRATOR_STOP_LOSS_PRICE = 2015.0
DEFAULT_CLI_ORCHESTRATOR_TAKE_PROFIT_PRICE = 2045.0
DEFAULT_CLI_ORCHESTRATOR_RISK_AMOUNT = 100.0
DEFAULT_CLI_ORCHESTRATOR_BACKTEST_NAME = "cli-workflow-backtest"
DEFAULT_CLI_ORCHESTRATOR_MEMORY_TYPE = "observation"
DEFAULT_CLI_ORCHESTRATOR_MEMORY_IMPORTANCE = 0.5


@dataclass(frozen=True)
class CliOrchestratorRouteRequest:
    """
    Standard CLI orchestrator route request.
    """

    orchestrator: Any
    agent_name: str = DEFAULT_CLI_ORCHESTRATOR_AGENT_NAME
    action: str = DEFAULT_CLI_ORCHESTRATOR_ACTION
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_non_empty_string(self.agent_name, "Agent name")
        validate_non_empty_string(self.action, "Action")
        validate_dictionary(self.payload, "Payload")
        validate_dictionary(self.metadata, "Metadata")
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_route(self) -> dict[str, Any]:
        """Convert CLI request into orchestrator route payload."""
        return {
            "agent_name": validate_non_empty_string(self.agent_name, "Agent name"),
            "action": validate_non_empty_string(self.action, "Action"),
            "payload": dict(self.payload),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CliMarketStrategyWorkflowRequest:
    """
    Standard CLI market-strategy workflow request.
    """

    orchestrator: Any
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_workflow(self) -> dict[str, Any]:
        """Convert CLI request into market-strategy workflow payload."""
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)

        return {
            "symbol": self.symbol.strip().upper(),
            "timeframe": self.timeframe.strip().upper(),
        }


@dataclass(frozen=True)
class CliStrategyRiskWorkflowRequest:
    """
    Standard CLI strategy-risk workflow request.
    """

    orchestrator: Any
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    regime: str = DEFAULT_CLI_ORCHESTRATOR_REGIME
    trend: str = DEFAULT_CLI_ORCHESTRATOR_TREND
    entry_price: float = DEFAULT_CLI_ORCHESTRATOR_ENTRY_PRICE
    account_balance: float = DEFAULT_ACCOUNT_BALANCE
    risk_percent: float = DEFAULT_RISK_PERCENT
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_non_empty_string(self.regime, "Regime")
        validate_non_empty_string(self.trend, "Trend")
        validate_positive_number(self.entry_price, "Entry price")
        validate_account_balance(self.account_balance)
        validate_risk_percent(self.risk_percent)
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_workflow(self) -> dict[str, Any]:
        """Convert CLI request into strategy-risk workflow payload."""
        return {
            "market_state": {
                "symbol": self.symbol.strip().upper(),
                "timeframe": self.timeframe.strip().upper(),
                "regime": self.regime.strip().lower(),
                "trend": self.trend.strip().lower(),
                "entry_price": float(self.entry_price),
            },
            "account_balance": float(self.account_balance),
            "risk_percent": float(self.risk_percent),
        }


@dataclass(frozen=True)
class CliRiskExecutionWorkflowRequest:
    """
    Standard CLI risk-execution workflow request.
    """

    orchestrator: Any
    symbol: str = DEFAULT_SYMBOL
    side: str = DEFAULT_CLI_ORCHESTRATOR_SIDE
    allowed: bool = True
    reason: str = "Trade allowed."
    position_size: float = DEFAULT_CLI_ORCHESTRATOR_POSITION_SIZE
    entry_price: float = DEFAULT_CLI_ORCHESTRATOR_ENTRY_PRICE
    stop_loss_price: float = DEFAULT_CLI_ORCHESTRATOR_STOP_LOSS_PRICE
    take_profit_price: float = DEFAULT_CLI_ORCHESTRATOR_TAKE_PROFIT_PRICE
    risk_amount: float = DEFAULT_CLI_ORCHESTRATOR_RISK_AMOUNT
    risk_percent: float = DEFAULT_RISK_PERCENT
    execution_ready: bool = True
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_symbol(self.symbol)
        validate_side(self.side)
        validate_boolean(self.allowed, "Allowed")
        validate_non_empty_string(self.reason, "Reason")
        validate_positive_number(self.position_size, "Position size")
        validate_positive_number(self.entry_price, "Entry price")
        validate_positive_number(self.stop_loss_price, "Stop loss price")
        validate_positive_number(self.take_profit_price, "Take profit price")
        validate_positive_number(self.risk_amount, "Risk amount")
        validate_risk_percent(self.risk_percent)
        validate_boolean(self.execution_ready, "Execution ready")
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_workflow(self) -> dict[str, Any]:
        """Convert CLI request into risk-execution workflow payload."""
        return {
            "risk_handoff": {
                "symbol": self.symbol.strip().upper(),
                "side": self.side.strip().lower(),
                "allowed": self.allowed,
                "reason": self.reason.strip(),
                "position_size": float(self.position_size),
                "entry_price": float(self.entry_price),
                "stop_loss_price": float(self.stop_loss_price),
                "take_profit_price": float(self.take_profit_price),
                "risk_amount": float(self.risk_amount),
                "risk_percent": float(self.risk_percent),
                "execution_ready": self.execution_ready,
            },
        }


@dataclass(frozen=True)
class CliTradeWorkflowRequest:
    """
    Standard CLI full trade workflow request.
    """

    orchestrator: Any
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    account_balance: float = DEFAULT_ACCOUNT_BALANCE
    risk_percent: float = DEFAULT_RISK_PERCENT
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_account_balance(self.account_balance)
        validate_risk_percent(self.risk_percent)
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_workflow(self) -> dict[str, Any]:
        """Convert CLI request into full trade workflow payload."""
        return {
            "symbol": self.symbol.strip().upper(),
            "timeframe": self.timeframe.strip().upper(),
            "account_balance": float(self.account_balance),
            "risk_percent": float(self.risk_percent),
        }


@dataclass(frozen=True)
class CliResearchWorkflowRequest:
    """
    Standard CLI research workflow request.
    """

    orchestrator: Any
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    signal_source: str = "market regime"
    objective: str = "improve strategy quality"
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_non_empty_string(self.signal_source, "Signal source")
        validate_non_empty_string(self.objective, "Objective")
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_workflow(self) -> dict[str, Any]:
        """Convert CLI request into research workflow payload."""
        return {
            "symbol": self.symbol.strip().upper(),
            "timeframe": self.timeframe.strip().upper(),
            "signal_source": self.signal_source.strip(),
            "objective": self.objective.strip(),
        }


@dataclass(frozen=True)
class CliBacktestWorkflowRequest:
    """
    Standard CLI backtest workflow request.
    """

    orchestrator: Any
    name: str = DEFAULT_CLI_ORCHESTRATOR_BACKTEST_NAME
    profits: list[float] = field(default_factory=lambda: [100.0, -50.0, 25.0])
    initial_balance: float = DEFAULT_ACCOUNT_BALANCE
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_non_empty_string(self.name, "Backtest name")
        validate_profits(self.profits)
        validate_account_balance(self.initial_balance)
        validate_dictionary(self.metadata, "Metadata")
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_workflow(self) -> dict[str, Any]:
        """Convert CLI request into backtest workflow payload."""
        return {
            "name": self.name.strip(),
            "profits": [float(profit) for profit in self.profits],
            "initial_balance": float(self.initial_balance),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class CliMemoryWorkflowRequest:
    """
    Standard CLI memory workflow request.
    """

    orchestrator: Any
    memory_id: str
    content: str
    query: str
    memory_type: str = DEFAULT_CLI_ORCHESTRATOR_MEMORY_TYPE
    importance: float = DEFAULT_CLI_ORCHESTRATOR_MEMORY_IMPORTANCE
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        validate_orchestrator(self.orchestrator)
        validate_non_empty_string(self.memory_id, "Memory ID")
        validate_non_empty_string(self.content, "Content")
        validate_non_empty_string(self.query, "Query")
        validate_non_empty_string(self.memory_type, "Memory type")
        validate_importance(self.importance)
        validate_dictionary(self.metadata, "Metadata")
        validate_output_settings(
            self.output_format,
            self.include_metadata,
            self.request_id,
        )

    def to_workflow(self) -> dict[str, Any]:
        """Convert CLI request into memory workflow payload."""
        return {
            "memory_id": self.memory_id.strip(),
            "content": self.content.strip(),
            "query": self.query.strip(),
            "memory_type": self.memory_type.strip().lower(),
            "importance": float(self.importance),
            "metadata": dict(self.metadata),
        }


def validate_orchestrator(orchestrator: Any) -> Any:
    """Validate orchestrator dependency."""
    if orchestrator is None:
        raise ValueError("Orchestrator is required.")

    return orchestrator


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_dictionary(value: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Validate dictionary value."""
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    return value


def validate_boolean(value: bool, field_name: str) -> bool:
    """Validate boolean value."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean.")

    return value


def validate_positive_number(value: float, field_name: str) -> float:
    """Validate positive numeric value."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ValueError(f"{field_name} must be a positive number.")

    return float(value)


def validate_importance(value: float) -> float:
    """Validate memory importance value."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("Importance must be a number.")

    if value < 0 or value > 1:
        raise ValueError("Importance must be between 0 and 1.")

    return float(value)


def validate_profits(profits: list[float]) -> list[float]:
    """Validate backtest profits."""
    if not isinstance(profits, list) or not profits:
        raise ValueError("Profits must be a non-empty list.")

    if any(isinstance(profit, bool) or not isinstance(profit, int | float) for profit in profits):
        raise ValueError("Profits must contain only numeric values.")

    return [float(profit) for profit in profits]


def validate_output_settings(
    output_format: CliOutputFormat | str,
    include_metadata: bool,
    request_id: str | None,
) -> None:
    """Validate shared CLI output settings."""
    normalize_output_format(output_format)

    if not isinstance(include_metadata, bool):
        raise ValueError("Include metadata must be a boolean.")

    if request_id is not None:
        validate_non_empty_string(request_id, "Request ID")


def validate_orchestrator_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI orchestrator operation callback."""
    if not callable(operation):
        raise ValueError("Orchestrator operation must be callable.")

    return operation


def execute_orchestrator_operation(
    operation: Callable[..., ApiResponse],
    *,
    orchestrator: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute an orchestrator API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_orchestrator_operation(operation)
    validate_orchestrator(orchestrator)

    if request_id is not None:
        try:
            return operation(
                orchestrator,
                request_id=request_id,
                **kwargs,
            )
        except TypeError:
            return operation(
                orchestrator,
                **kwargs,
            )

    return operation(
        orchestrator,
        **kwargs,
    )


def build_orchestrator_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for an orchestrator API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def cli_orchestrator_route(
    *,
    orchestrator: Any,
    agent_name: str = DEFAULT_CLI_ORCHESTRATOR_AGENT_NAME,
    action: str = DEFAULT_CLI_ORCHESTRATOR_ACTION,
    payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_orchestrator_route,
) -> CliOutput:
    """Run orchestrator route command."""
    request = CliOrchestratorRouteRequest(
        orchestrator=orchestrator,
        agent_name=agent_name,
        action=action,
        payload=payload or {},
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        route=request.to_route(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_market_strategy_workflow(
    *,
    orchestrator: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_market_strategy_workflow,
) -> CliOutput:
    """Run market-strategy workflow command."""
    request = CliMarketStrategyWorkflowRequest(
        orchestrator=orchestrator,
        symbol=symbol,
        timeframe=timeframe,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        workflow=request.to_workflow(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_strategy_risk_workflow(
    *,
    orchestrator: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_CLI_ORCHESTRATOR_REGIME,
    trend: str = DEFAULT_CLI_ORCHESTRATOR_TREND,
    entry_price: float = DEFAULT_CLI_ORCHESTRATOR_ENTRY_PRICE,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_strategy_risk_workflow,
) -> CliOutput:
    """Run strategy-risk workflow command."""
    request = CliStrategyRiskWorkflowRequest(
        orchestrator=orchestrator,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
        account_balance=account_balance,
        risk_percent=risk_percent,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        workflow=request.to_workflow(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_risk_execution_workflow(
    *,
    orchestrator: Any,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_ORCHESTRATOR_SIDE,
    allowed: bool = True,
    reason: str = "Trade allowed.",
    position_size: float = DEFAULT_CLI_ORCHESTRATOR_POSITION_SIZE,
    entry_price: float = DEFAULT_CLI_ORCHESTRATOR_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_CLI_ORCHESTRATOR_STOP_LOSS_PRICE,
    take_profit_price: float = DEFAULT_CLI_ORCHESTRATOR_TAKE_PROFIT_PRICE,
    risk_amount: float = DEFAULT_CLI_ORCHESTRATOR_RISK_AMOUNT,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    execution_ready: bool = True,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_risk_execution_workflow,
) -> CliOutput:
    """Run risk-execution workflow command."""
    request = CliRiskExecutionWorkflowRequest(
        orchestrator=orchestrator,
        symbol=symbol,
        side=side,
        allowed=allowed,
        reason=reason,
        position_size=position_size,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        risk_amount=risk_amount,
        risk_percent=risk_percent,
        execution_ready=execution_ready,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        workflow=request.to_workflow(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_trade_workflow(
    *,
    orchestrator: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_trade_workflow,
) -> CliOutput:
    """Run full trade workflow command."""
    request = CliTradeWorkflowRequest(
        orchestrator=orchestrator,
        symbol=symbol,
        timeframe=timeframe,
        account_balance=account_balance,
        risk_percent=risk_percent,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        workflow=request.to_workflow(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_research_workflow(
    *,
    orchestrator: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    signal_source: str = "market regime",
    objective: str = "improve strategy quality",
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_research_workflow,
) -> CliOutput:
    """Run research workflow command."""
    request = CliResearchWorkflowRequest(
        orchestrator=orchestrator,
        symbol=symbol,
        timeframe=timeframe,
        signal_source=signal_source,
        objective=objective,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        workflow=request.to_workflow(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_backtest_workflow(
    *,
    orchestrator: Any,
    name: str = DEFAULT_CLI_ORCHESTRATOR_BACKTEST_NAME,
    profits: list[float] | None = None,
    initial_balance: float = DEFAULT_ACCOUNT_BALANCE,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_backtest_workflow,
) -> CliOutput:
    """Run backtest workflow command."""
    request = CliBacktestWorkflowRequest(
        orchestrator=orchestrator,
        name=name,
        profits=profits or [100.0, -50.0, 25.0],
        initial_balance=initial_balance,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        workflow=request.to_workflow(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_memory_workflow(
    *,
    orchestrator: Any,
    memory_id: str,
    content: str,
    query: str,
    memory_type: str = DEFAULT_CLI_ORCHESTRATOR_MEMORY_TYPE,
    importance: float = DEFAULT_CLI_ORCHESTRATOR_MEMORY_IMPORTANCE,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_memory_workflow,
) -> CliOutput:
    """Run memory workflow command."""
    request = CliMemoryWorkflowRequest(
        orchestrator=orchestrator,
        memory_id=memory_id,
        content=content,
        query=query,
        memory_type=memory_type,
        importance=importance,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_orchestrator_operation(
        operation,
        orchestrator=request.orchestrator,
        request_id=request.request_id,
        workflow=request.to_workflow(),
    )

    return build_orchestrator_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )