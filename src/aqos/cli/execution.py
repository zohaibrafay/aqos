"""
AQOS CLI execution commands.

This module converts AQOS API execution operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aqos.api import (
    ApiResponse,
    ClosePositionRequest,
    ExecutionOrderRequest,
    ExecutionTradeRequest,
    FillOrderRequest,
    OrderIdRequest,
    api_cancel_order,
    api_close_position,
    api_execute_trade,
    api_execution_summary,
    api_fill_order,
    api_order_status,
    api_place_order,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
)
from aqos.common import DEFAULT_RISK_PERCENT, DEFAULT_SYMBOL


DEFAULT_CLI_EXECUTION_SIDE = "buy"
DEFAULT_CLI_EXECUTION_POSITION_SIZE = 10.0
DEFAULT_CLI_EXECUTION_ENTRY_PRICE = 2025.0
DEFAULT_CLI_EXECUTION_STOP_LOSS_PRICE = 2015.0
DEFAULT_CLI_EXECUTION_RISK_AMOUNT = 100.0


@dataclass(frozen=True)
class CliExecutionTradeRequest:
    """
    Standard CLI execution trade request.
    """

    agent: Any
    symbol: str = DEFAULT_SYMBOL
    side: str = DEFAULT_CLI_EXECUTION_SIDE
    allowed: bool = True
    reason: str = "Trade allowed."
    position_size: float = DEFAULT_CLI_EXECUTION_POSITION_SIZE
    entry_price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE
    stop_loss_price: float = DEFAULT_CLI_EXECUTION_STOP_LOSS_PRICE
    risk_amount: float = DEFAULT_CLI_EXECUTION_RISK_AMOUNT
    risk_percent: float = DEFAULT_RISK_PERCENT
    execution_ready: bool = True
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Execution agent is required.")

        ExecutionTradeRequest(
            symbol=self.symbol,
            side=self.side,
            allowed=self.allowed,
            reason=self.reason,
            position_size=self.position_size,
            entry_price=self.entry_price,
            stop_loss_price=self.stop_loss_price,
            risk_amount=self.risk_amount,
            risk_percent=self.risk_percent,
            execution_ready=self.execution_ready,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_trade(self) -> dict[str, Any]:
        """Convert CLI request into execution trade payload."""
        return ExecutionTradeRequest(
            symbol=self.symbol,
            side=self.side,
            allowed=self.allowed,
            reason=self.reason,
            position_size=self.position_size,
            entry_price=self.entry_price,
            stop_loss_price=self.stop_loss_price,
            risk_amount=self.risk_amount,
            risk_percent=self.risk_percent,
            execution_ready=self.execution_ready,
        ).to_trade()


@dataclass(frozen=True)
class CliExecutionOrderRequest:
    """
    Standard CLI execution order request.
    """

    agent: Any
    order_id: str
    symbol: str = DEFAULT_SYMBOL
    side: str = DEFAULT_CLI_EXECUTION_SIDE
    quantity: float = DEFAULT_CLI_EXECUTION_POSITION_SIZE
    price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Execution agent is required.")

        ExecutionOrderRequest(
            order_id=self.order_id,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            price=self.price,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_order(self) -> dict[str, Any]:
        """Convert CLI request into execution order payload."""
        return ExecutionOrderRequest(
            order_id=self.order_id,
            symbol=self.symbol,
            side=self.side,
            quantity=self.quantity,
            price=self.price,
        ).to_order()


@dataclass(frozen=True)
class CliFillOrderRequest:
    """
    Standard CLI fill-order request.
    """

    agent: Any
    order_id: str
    fill_price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Execution agent is required.")

        FillOrderRequest(
            order_id=self.order_id,
            fill_price=self.fill_price,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into fill-order payload."""
        return FillOrderRequest(
            order_id=self.order_id,
            fill_price=self.fill_price,
        ).to_payload()


@dataclass(frozen=True)
class CliOrderIdRequest:
    """
    Standard CLI order-id request.
    """

    agent: Any
    order_id: str
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Execution agent is required.")

        OrderIdRequest(order_id=self.order_id)
        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into order-id payload."""
        return OrderIdRequest(order_id=self.order_id).to_payload()


@dataclass(frozen=True)
class CliClosePositionRequest:
    """
    Standard CLI close-position request.
    """

    agent: Any
    position_id: str
    close_price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Execution agent is required.")

        ClosePositionRequest(
            position_id=self.position_id,
            close_price=self.close_price,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into close-position payload."""
        return ClosePositionRequest(
            position_id=self.position_id,
            close_price=self.close_price,
        ).to_payload()


@dataclass(frozen=True)
class CliExecutionSummaryRequest:
    """
    Standard CLI execution-summary request.
    """

    agent: Any
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Execution agent is required.")

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


def validate_execution_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI execution operation callback."""
    if not callable(operation):
        raise ValueError("Execution operation must be callable.")

    return operation


def execute_execution_operation(
    operation: Callable[..., ApiResponse],
    *,
    agent: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute an execution API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_execution_operation(operation)

    if agent is None:
        raise ValueError("Execution agent is required.")

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


def build_execution_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for an execution API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def cli_execute_trade(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_EXECUTION_SIDE,
    allowed: bool = True,
    reason: str = "Trade allowed.",
    position_size: float = DEFAULT_CLI_EXECUTION_POSITION_SIZE,
    entry_price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_CLI_EXECUTION_STOP_LOSS_PRICE,
    risk_amount: float = DEFAULT_CLI_EXECUTION_RISK_AMOUNT,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    execution_ready: bool = True,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_execute_trade,
) -> CliOutput:
    """Run execute-trade command."""
    request = CliExecutionTradeRequest(
        agent=agent,
        symbol=symbol,
        side=side,
        allowed=allowed,
        reason=reason,
        position_size=position_size,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        risk_amount=risk_amount,
        risk_percent=risk_percent,
        execution_ready=execution_ready,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_execution_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        trade=request.to_trade(),
    )

    return build_execution_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_place_order(
    *,
    agent: Any,
    order_id: str,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_EXECUTION_SIDE,
    quantity: float = DEFAULT_CLI_EXECUTION_POSITION_SIZE,
    price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_place_order,
) -> CliOutput:
    """Run place-order command."""
    request = CliExecutionOrderRequest(
        agent=agent,
        order_id=order_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    order = request.to_order()

    response = execute_execution_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **order,
    )

    return build_execution_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_fill_order(
    *,
    agent: Any,
    order_id: str,
    fill_price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_fill_order,
) -> CliOutput:
    """Run fill-order command."""
    request = CliFillOrderRequest(
        agent=agent,
        order_id=order_id,
        fill_price=fill_price,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_execution_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_execution_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_cancel_order(
    *,
    agent: Any,
    order_id: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_cancel_order,
) -> CliOutput:
    """Run cancel-order command."""
    request = CliOrderIdRequest(
        agent=agent,
        order_id=order_id,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_execution_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_execution_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_order_status(
    *,
    agent: Any,
    order_id: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_order_status,
) -> CliOutput:
    """Run order-status command."""
    request = CliOrderIdRequest(
        agent=agent,
        order_id=order_id,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_execution_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_execution_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_close_position(
    *,
    agent: Any,
    position_id: str,
    close_price: float = DEFAULT_CLI_EXECUTION_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_close_position,
) -> CliOutput:
    """Run close-position command."""
    request = CliClosePositionRequest(
        agent=agent,
        position_id=position_id,
        close_price=close_price,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_execution_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_execution_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_execution_summary(
    *,
    agent: Any,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_execution_summary,
) -> CliOutput:
    """Run execution-summary command."""
    request = CliExecutionSummaryRequest(
        agent=agent,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_execution_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
    )

    return build_execution_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )