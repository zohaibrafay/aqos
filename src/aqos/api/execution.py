"""
AQOS API execution operations.

This module provides framework-independent API helpers for execution-facing
operations. It wraps ExecutionAgent actions in consistent ApiResponse envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aqos.api.responses import (
    ApiResponse,
    api_error,
    api_failure,
    api_success,
    exception_failure,
    validation_failure,
)
from aqos.common import DEFAULT_RISK_PERCENT, DEFAULT_SYMBOL
from aqos.common.validators import validate_price, validate_side, validate_symbol


DEFAULT_EXECUTION_SIDE = "buy"
DEFAULT_EXECUTION_POSITION_SIZE = 10.0
DEFAULT_EXECUTION_ENTRY_PRICE = 2025.0
DEFAULT_EXECUTION_STOP_LOSS_PRICE = 2015.0
DEFAULT_EXECUTION_RISK_AMOUNT = 100.0


def validate_positive_number(value: float, field_name: str) -> float:
    """Validate that a number is positive."""
    if not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    normalized = float(value)

    if normalized <= 0:
        raise ValueError(f"{field_name} must be greater than zero.")

    return normalized


def validate_non_empty_id(value: str, field_name: str) -> str:
    """Validate a non-empty identifier."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


@dataclass(frozen=True)
class ExecutionTradeRequest:
    """
    Standard execution API trade request.

    This request mirrors the RiskAgent risk-handoff payload used by
    ExecutionAgent.execute-trade.
    """

    symbol: str = DEFAULT_SYMBOL
    side: str = DEFAULT_EXECUTION_SIDE
    allowed: bool = True
    reason: str = "Trade allowed."
    position_size: float = DEFAULT_EXECUTION_POSITION_SIZE
    entry_price: float = DEFAULT_EXECUTION_ENTRY_PRICE
    stop_loss_price: float = DEFAULT_EXECUTION_STOP_LOSS_PRICE
    risk_amount: float = DEFAULT_EXECUTION_RISK_AMOUNT
    risk_percent: float = DEFAULT_RISK_PERCENT
    execution_ready: bool = True

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_side(self.side)
        validate_positive_number(self.position_size, "Position size")
        validate_price(self.entry_price)
        validate_price(self.stop_loss_price)
        validate_positive_number(self.risk_amount, "Risk amount")
        validate_positive_number(self.risk_percent, "Risk percent")

        if not isinstance(self.allowed, bool):
            raise ValueError("Allowed must be a boolean.")

        if not isinstance(self.execution_ready, bool):
            raise ValueError("Execution ready must be a boolean.")

        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ValueError("Execution reason must be a non-empty string.")

    def to_trade(self) -> dict[str, Any]:
        """Convert request into an ExecutionAgent trade payload."""
        return {
            "symbol": validate_symbol(self.symbol),
            "side": validate_side(self.side),
            "allowed": self.allowed,
            "reason": self.reason.strip(),
            "position_size": validate_positive_number(
                self.position_size,
                "Position size",
            ),
            "entry_price": validate_price(self.entry_price),
            "stop_loss_price": validate_price(self.stop_loss_price),
            "risk_amount": validate_positive_number(
                self.risk_amount,
                "Risk amount",
            ),
            "risk_percent": validate_positive_number(
                self.risk_percent,
                "Risk percent",
            ),
            "execution_ready": self.execution_ready,
        }

    def to_payload(self) -> dict[str, Any]:
        """Convert request into agent payload."""
        return {
            "trade": self.to_trade(),
        }


@dataclass(frozen=True)
class ExecutionOrderRequest:
    """
    Standard execution API order request.
    """

    order_id: str
    symbol: str = DEFAULT_SYMBOL
    side: str = DEFAULT_EXECUTION_SIDE
    quantity: float = DEFAULT_EXECUTION_POSITION_SIZE
    price: float = DEFAULT_EXECUTION_ENTRY_PRICE

    def __post_init__(self) -> None:
        validate_non_empty_id(self.order_id, "Order ID")
        validate_symbol(self.symbol)
        validate_side(self.side)
        validate_positive_number(self.quantity, "Quantity")
        validate_price(self.price)

    def to_order(self) -> dict[str, Any]:
        """Convert request into an ExecutionAgent order payload."""
        return {
            "order_id": validate_non_empty_id(self.order_id, "Order ID"),
            "symbol": validate_symbol(self.symbol),
            "side": validate_side(self.side),
            "quantity": validate_positive_number(self.quantity, "Quantity"),
            "price": validate_price(self.price),
        }


@dataclass(frozen=True)
class FillOrderRequest:
    """
    Standard execution API fill-order request.
    """

    order_id: str
    fill_price: float = DEFAULT_EXECUTION_ENTRY_PRICE

    def __post_init__(self) -> None:
        validate_non_empty_id(self.order_id, "Order ID")
        validate_price(self.fill_price)

    def to_payload(self) -> dict[str, Any]:
        """Convert request into agent payload."""
        return {
            "order_id": validate_non_empty_id(self.order_id, "Order ID"),
            "fill_price": validate_price(self.fill_price),
        }


@dataclass(frozen=True)
class OrderIdRequest:
    """
    Standard execution API order-id request.
    """

    order_id: str

    def __post_init__(self) -> None:
        validate_non_empty_id(self.order_id, "Order ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into agent payload."""
        return {
            "order_id": validate_non_empty_id(self.order_id, "Order ID"),
        }


@dataclass(frozen=True)
class ClosePositionRequest:
    """
    Standard execution API close-position request.
    """

    position_id: str
    close_price: float = DEFAULT_EXECUTION_ENTRY_PRICE

    def __post_init__(self) -> None:
        validate_non_empty_id(self.position_id, "Position ID")
        validate_price(self.close_price)

    def to_payload(self) -> dict[str, Any]:
        """Convert request into agent payload."""
        return {
            "position_id": validate_non_empty_id(
                self.position_id,
                "Position ID",
            ),
            "close_price": validate_price(self.close_price),
        }


def build_execution_trade_request(
    *,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_EXECUTION_SIDE,
    allowed: bool = True,
    reason: str = "Trade allowed.",
    position_size: float = DEFAULT_EXECUTION_POSITION_SIZE,
    entry_price: float = DEFAULT_EXECUTION_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_EXECUTION_STOP_LOSS_PRICE,
    risk_amount: float = DEFAULT_EXECUTION_RISK_AMOUNT,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    execution_ready: bool = True,
) -> ExecutionTradeRequest:
    """Build and validate an execution trade request."""
    return ExecutionTradeRequest(
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
    )


def normalize_execution_trade(
    trade: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external execution trade dictionary."""
    if not isinstance(trade, dict):
        raise ValueError("Execution trade must be a dictionary.")

    request = build_execution_trade_request(
        symbol=trade.get("symbol", DEFAULT_SYMBOL),
        side=trade.get("side", DEFAULT_EXECUTION_SIDE),
        allowed=trade.get("allowed", True),
        reason=trade.get("reason", "Trade allowed."),
        position_size=trade.get(
            "position_size",
            DEFAULT_EXECUTION_POSITION_SIZE,
        ),
        entry_price=trade.get("entry_price", DEFAULT_EXECUTION_ENTRY_PRICE),
        stop_loss_price=trade.get(
            "stop_loss_price",
            DEFAULT_EXECUTION_STOP_LOSS_PRICE,
        ),
        risk_amount=trade.get("risk_amount", DEFAULT_EXECUTION_RISK_AMOUNT),
        risk_percent=trade.get("risk_percent", DEFAULT_RISK_PERCENT),
        execution_ready=trade.get("execution_ready", True),
    )

    normalized = request.to_trade()

    for key, value in trade.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def execution_agent_operation(
    agent: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute an ExecutionAgent action and convert the result into an API response.
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
                    code="EXECUTION_AGENT_ERROR",
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


def api_execute_trade(
    agent: Any,
    *,
    trade: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Execute a trade through ExecutionAgent."""
    try:
        payload = {
            "trade": normalize_execution_trade(trade),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade",
            details={
                "trade": trade,
            },
            request_id=request_id,
        )

    return execution_agent_operation(
        agent,
        action="execute-trade",
        payload=payload,
        success_message="Trade execution completed.",
        failure_message="Trade execution could not be completed.",
        request_id=request_id,
    )


def api_place_order(
    agent: Any,
    *,
    order_id: str,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_EXECUTION_SIDE,
    quantity: float = DEFAULT_EXECUTION_POSITION_SIZE,
    price: float = DEFAULT_EXECUTION_ENTRY_PRICE,
    request_id: str | None = None,
) -> ApiResponse:
    """Place an order through ExecutionAgent."""
    try:
        request = ExecutionOrderRequest(
            order_id=order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="order",
            details={
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
            },
            request_id=request_id,
        )

    return execution_agent_operation(
        agent,
        action="place-order",
        payload=request.to_order(),
        success_message="Order placed.",
        failure_message="Order could not be placed.",
        request_id=request_id,
    )


def api_fill_order(
    agent: Any,
    *,
    order_id: str,
    fill_price: float = DEFAULT_EXECUTION_ENTRY_PRICE,
    request_id: str | None = None,
) -> ApiResponse:
    """Fill an order through ExecutionAgent."""
    try:
        request = FillOrderRequest(
            order_id=order_id,
            fill_price=fill_price,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="fill_order",
            details={
                "order_id": order_id,
                "fill_price": fill_price,
            },
            request_id=request_id,
        )

    return execution_agent_operation(
        agent,
        action="fill-order",
        payload=request.to_payload(),
        success_message="Order filled.",
        failure_message="Order could not be filled.",
        request_id=request_id,
    )


def api_cancel_order(
    agent: Any,
    *,
    order_id: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Cancel an order through ExecutionAgent."""
    try:
        request = OrderIdRequest(order_id=order_id)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="order_id",
            details={
                "order_id": order_id,
            },
            request_id=request_id,
        )

    return execution_agent_operation(
        agent,
        action="cancel-order",
        payload=request.to_payload(),
        success_message="Order cancelled.",
        failure_message="Order could not be cancelled.",
        request_id=request_id,
    )


def api_order_status(
    agent: Any,
    *,
    order_id: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Return order status through ExecutionAgent."""
    try:
        request = OrderIdRequest(order_id=order_id)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="order_id",
            details={
                "order_id": order_id,
            },
            request_id=request_id,
        )

    return execution_agent_operation(
        agent,
        action="order-status",
        payload=request.to_payload(),
        success_message="Order status loaded.",
        failure_message="Order status could not be loaded.",
        request_id=request_id,
    )


def api_close_position(
    agent: Any,
    *,
    position_id: str,
    close_price: float = DEFAULT_EXECUTION_ENTRY_PRICE,
    request_id: str | None = None,
) -> ApiResponse:
    """Close a position through ExecutionAgent."""
    try:
        request = ClosePositionRequest(
            position_id=position_id,
            close_price=close_price,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="close_position",
            details={
                "position_id": position_id,
                "close_price": close_price,
            },
            request_id=request_id,
        )

    return execution_agent_operation(
        agent,
        action="close-position",
        payload=request.to_payload(),
        success_message="Position closed.",
        failure_message="Position could not be closed.",
        request_id=request_id,
    )


def api_execution_summary(
    agent: Any,
    *,
    request_id: str | None = None,
) -> ApiResponse:
    """Return execution summary through ExecutionAgent."""
    return execution_agent_operation(
        agent,
        action="execution-summary",
        payload={},
        success_message="Execution summary loaded.",
        failure_message="Execution summary could not be loaded.",
        request_id=request_id,
    )