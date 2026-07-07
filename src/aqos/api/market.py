"""
AQOS API market operations.

This module provides framework-independent API helpers for market-facing
operations. It wraps MarketAgent actions in consistent ApiResponse envelopes.
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
from aqos.common import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from aqos.common.validators import validate_symbol, validate_timeframe


@dataclass(frozen=True)
class MarketRequest:
    """
    Standard market API request.

    Attributes:
        symbol: Trading symbol.
        timeframe: Market timeframe.
    """

    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)

    def to_payload(self) -> dict[str, Any]:
        """Convert request into agent payload."""
        return {
            "symbol": validate_symbol(self.symbol),
            "timeframe": validate_timeframe(self.timeframe),
        }


def build_market_request(
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
) -> MarketRequest:
    """Build and validate a market request."""
    return MarketRequest(
        symbol=symbol,
        timeframe=timeframe,
    )


def market_agent_operation(
    agent: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute a MarketAgent action and convert the result into an API response.
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
                    code="MARKET_AGENT_ERROR",
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


def api_market_state(
    agent: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    request_id: str | None = None,
) -> ApiResponse:
    """Return market state from MarketAgent."""
    try:
        request = build_market_request(
            symbol=symbol,
            timeframe=timeframe,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="symbol_timeframe",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
            },
            request_id=request_id,
        )

    return market_agent_operation(
        agent,
        action="market-state",
        payload=request.to_payload(),
        success_message="Market state loaded.",
        failure_message="Market state could not be loaded.",
        request_id=request_id,
    )


def api_market_snapshot(
    agent: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    request_id: str | None = None,
) -> ApiResponse:
    """Return market snapshot from MarketAgent."""
    try:
        request = build_market_request(
            symbol=symbol,
            timeframe=timeframe,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="symbol_timeframe",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
            },
            request_id=request_id,
        )

    return market_agent_operation(
        agent,
        action="snapshot",
        payload=request.to_payload(),
        success_message="Market snapshot loaded.",
        failure_message="Market snapshot could not be loaded.",
        request_id=request_id,
    )


def api_trend_summary(
    agent: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    request_id: str | None = None,
) -> ApiResponse:
    """Return trend summary from MarketAgent."""
    try:
        request = build_market_request(
            symbol=symbol,
            timeframe=timeframe,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="symbol_timeframe",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
            },
            request_id=request_id,
        )

    return market_agent_operation(
        agent,
        action="trend-summary",
        payload=request.to_payload(),
        success_message="Trend summary loaded.",
        failure_message="Trend summary could not be loaded.",
        request_id=request_id,
    )


def api_regime_summary(
    agent: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    request_id: str | None = None,
) -> ApiResponse:
    """Return regime summary from MarketAgent."""
    try:
        request = build_market_request(
            symbol=symbol,
            timeframe=timeframe,
        )
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="symbol_timeframe",
            details={
                "symbol": symbol,
                "timeframe": timeframe,
            },
            request_id=request_id,
        )

    return market_agent_operation(
        agent,
        action="regime-summary",
        payload=request.to_payload(),
        success_message="Regime summary loaded.",
        failure_message="Regime summary could not be loaded.",
        request_id=request_id,
    )


def api_news_context(
    agent: Any,
    *,
    symbol: str = DEFAULT_SYMBOL,
    request_id: str | None = None,
) -> ApiResponse:
    """Return news context from MarketAgent."""
    try:
        normalized_symbol = validate_symbol(symbol)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="symbol",
            details={
                "symbol": symbol,
            },
            request_id=request_id,
        )

    return market_agent_operation(
        agent,
        action="news-context",
        payload={
            "symbol": normalized_symbol,
        },
        success_message="News context loaded.",
        failure_message="News context could not be loaded.",
        request_id=request_id,
    )


def api_calendar_context(
    agent: Any,
    *,
    currency: str = "USD",
    request_id: str | None = None,
) -> ApiResponse:
    """Return economic calendar context from MarketAgent."""
    if not isinstance(currency, str) or not currency.strip():
        return validation_failure(
            message="Currency must be a non-empty string.",
            field="currency",
            details={
                "currency": currency,
            },
            request_id=request_id,
        )

    return market_agent_operation(
        agent,
        action="calendar-context",
        payload={
            "currency": currency.strip().upper(),
        },
        success_message="Calendar context loaded.",
        failure_message="Calendar context could not be loaded.",
        request_id=request_id,
    )