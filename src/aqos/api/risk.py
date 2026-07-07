"""
AQOS API risk operations.

This module provides framework-independent API helpers for risk-facing
operations. It wraps RiskAgent actions in consistent ApiResponse envelopes.
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
from aqos.common import (
    DEFAULT_ACCOUNT_BALANCE,
    DEFAULT_RISK_PERCENT,
    DEFAULT_SYMBOL,
)
from aqos.common.validators import (
    validate_account_balance,
    validate_price,
    validate_risk_percent,
    validate_side,
    validate_symbol,
)


DEFAULT_RISK_SIDE = "buy"
DEFAULT_RISK_ENTRY_PRICE = 2025.0
DEFAULT_RISK_STOP_LOSS_PRICE = 2015.0
DEFAULT_RISK_TAKE_PROFIT_PRICE = 2045.0


@dataclass(frozen=True)
class RiskTradeRequest:
    """
    Standard risk API trade request.

    Attributes:
        symbol: Trading symbol.
        side: Trade side.
        account_balance: Account balance.
        risk_percent: Risk percentage as decimal.
        entry_price: Intended entry price.
        stop_loss_price: Stop loss price.
        take_profit_price: Optional take profit price.
    """

    symbol: str = DEFAULT_SYMBOL
    side: str = DEFAULT_RISK_SIDE
    account_balance: float = DEFAULT_ACCOUNT_BALANCE
    risk_percent: float = DEFAULT_RISK_PERCENT
    entry_price: float = DEFAULT_RISK_ENTRY_PRICE
    stop_loss_price: float = DEFAULT_RISK_STOP_LOSS_PRICE
    take_profit_price: float | None = DEFAULT_RISK_TAKE_PROFIT_PRICE

    def __post_init__(self) -> None:
        normalized_side = validate_side(self.side)

        validate_symbol(self.symbol)
        validate_account_balance(self.account_balance)
        validate_risk_percent(self.risk_percent)
        validate_price(self.entry_price)
        validate_price(self.stop_loss_price)

        if self.take_profit_price is not None:
            validate_price(self.take_profit_price)

        if normalized_side == "buy" and self.stop_loss_price >= self.entry_price:
            raise ValueError("Buy trade stop loss must be below entry price.")

        if normalized_side == "sell" and self.stop_loss_price <= self.entry_price:
            raise ValueError("Sell trade stop loss must be above entry price.")

    def to_trade_request(self) -> dict[str, Any]:
        """Convert request into a RiskAgent trade request payload."""
        payload: dict[str, Any] = {
            "symbol": validate_symbol(self.symbol),
            "side": validate_side(self.side),
            "account_balance": validate_account_balance(self.account_balance),
            "risk_percent": validate_risk_percent(self.risk_percent),
            "entry_price": validate_price(self.entry_price),
            "stop_loss_price": validate_price(self.stop_loss_price),
        }

        if self.take_profit_price is not None:
            payload["take_profit_price"] = validate_price(self.take_profit_price)

        return payload

    def to_payload(self) -> dict[str, Any]:
        """Convert request into agent payload."""
        return {
            "trade_request": self.to_trade_request(),
        }


def build_risk_trade_request(
    *,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_RISK_SIDE,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    entry_price: float = DEFAULT_RISK_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_RISK_STOP_LOSS_PRICE,
    take_profit_price: float | None = DEFAULT_RISK_TAKE_PROFIT_PRICE,
) -> RiskTradeRequest:
    """Build and validate a risk trade request."""
    return RiskTradeRequest(
        symbol=symbol,
        side=side,
        account_balance=account_balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def normalize_trade_request(
    trade_request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external trade_request dictionary for RiskAgent."""
    if not isinstance(trade_request, dict):
        raise ValueError("Trade request must be a dictionary.")

    request = build_risk_trade_request(
        symbol=trade_request.get("symbol", DEFAULT_SYMBOL),
        side=trade_request.get("side", DEFAULT_RISK_SIDE),
        account_balance=trade_request.get(
            "account_balance",
            DEFAULT_ACCOUNT_BALANCE,
        ),
        risk_percent=trade_request.get("risk_percent", DEFAULT_RISK_PERCENT),
        entry_price=trade_request.get("entry_price", DEFAULT_RISK_ENTRY_PRICE),
        stop_loss_price=trade_request.get(
            "stop_loss_price",
            DEFAULT_RISK_STOP_LOSS_PRICE,
        ),
        take_profit_price=trade_request.get(
            "take_profit_price",
            DEFAULT_RISK_TAKE_PROFIT_PRICE,
        ),
    )

    normalized = request.to_trade_request()

    for key, value in trade_request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def risk_agent_operation(
    agent: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute a RiskAgent action and convert the result into an API response.
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
                    code="RISK_AGENT_ERROR",
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


def api_position_size(
    agent: Any,
    *,
    trade_request: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return position sizing from RiskAgent."""
    try:
        payload = {
            "trade_request": normalize_trade_request(trade_request),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade_request",
            details={
                "trade_request": trade_request,
            },
            request_id=request_id,
        )

    return risk_agent_operation(
        agent,
        action="position-size",
        payload=payload,
        success_message="Position size calculated.",
        failure_message="Position size could not be calculated.",
        request_id=request_id,
    )


def api_assess_trade(
    agent: Any,
    *,
    trade_request: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return trade risk assessment from RiskAgent."""
    try:
        payload = {
            "trade_request": normalize_trade_request(trade_request),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade_request",
            details={
                "trade_request": trade_request,
            },
            request_id=request_id,
        )

    return risk_agent_operation(
        agent,
        action="assess-trade",
        payload=payload,
        success_message="Trade risk assessed.",
        failure_message="Trade risk could not be assessed.",
        request_id=request_id,
    )


def api_approve_trade(
    agent: Any,
    *,
    trade_request: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return trade approval result from RiskAgent."""
    try:
        payload = {
            "trade_request": normalize_trade_request(trade_request),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade_request",
            details={
                "trade_request": trade_request,
            },
            request_id=request_id,
        )

    return risk_agent_operation(
        agent,
        action="approve-trade",
        payload=payload,
        success_message="Trade approval completed.",
        failure_message="Trade approval could not be completed.",
        request_id=request_id,
    )


def api_reject_reason(
    agent: Any,
    *,
    trade_request: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return trade rejection reason from RiskAgent."""
    try:
        payload = {
            "trade_request": normalize_trade_request(trade_request),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade_request",
            details={
                "trade_request": trade_request,
            },
            request_id=request_id,
        )

    return risk_agent_operation(
        agent,
        action="reject-reason",
        payload=payload,
        success_message="Reject reason generated.",
        failure_message="Reject reason could not be generated.",
        request_id=request_id,
    )


def api_risk_handoff(
    agent: Any,
    *,
    trade_request: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return risk handoff from RiskAgent."""
    try:
        payload = {
            "trade_request": normalize_trade_request(trade_request),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade_request",
            details={
                "trade_request": trade_request,
            },
            request_id=request_id,
        )

    return risk_agent_operation(
        agent,
        action="risk-handoff",
        payload=payload,
        success_message="Risk handoff generated.",
        failure_message="Risk handoff could not be generated.",
        request_id=request_id,
    )