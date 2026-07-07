"""
AQOS API strategy operations.

This module provides framework-independent API helpers for strategy-facing
operations. It wraps StrategyAgent actions in consistent ApiResponse envelopes.
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
from aqos.common.validators import validate_price, validate_symbol, validate_timeframe


DEFAULT_STRATEGY_REGIME = "bullish"
DEFAULT_STRATEGY_TREND = "uptrend"
DEFAULT_STRATEGY_ENTRY_PRICE = 2025.0


@dataclass(frozen=True)
class StrategyMarketStateRequest:
    """
    Standard strategy API market-state request.

    Attributes:
        symbol: Trading symbol.
        timeframe: Market timeframe.
        regime: Market regime.
        trend: Market trend.
        entry_price: Current or intended entry price.
    """

    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    regime: str = DEFAULT_STRATEGY_REGIME
    trend: str = DEFAULT_STRATEGY_TREND
    entry_price: float = DEFAULT_STRATEGY_ENTRY_PRICE

    def __post_init__(self) -> None:
        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        validate_price(self.entry_price)

        if not isinstance(self.regime, str) or not self.regime.strip():
            raise ValueError("Strategy regime must be a non-empty string.")

        if not isinstance(self.trend, str) or not self.trend.strip():
            raise ValueError("Strategy trend must be a non-empty string.")

    def to_market_state(self) -> dict[str, Any]:
        """Convert request into a StrategyAgent market_state payload."""
        return {
            "symbol": validate_symbol(self.symbol),
            "timeframe": validate_timeframe(self.timeframe),
            "regime": self.regime.strip().lower(),
            "trend": self.trend.strip().lower(),
            "entry_price": validate_price(self.entry_price),
        }

    def to_payload(self) -> dict[str, Any]:
        """Convert request into agent payload."""
        return {
            "market_state": self.to_market_state(),
        }


def build_strategy_market_state_request(
    *,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_STRATEGY_REGIME,
    trend: str = DEFAULT_STRATEGY_TREND,
    entry_price: float = DEFAULT_STRATEGY_ENTRY_PRICE,
) -> StrategyMarketStateRequest:
    """Build and validate a strategy market-state request."""
    return StrategyMarketStateRequest(
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
    )


def normalize_market_state(
    market_state: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external market_state dictionary for StrategyAgent."""
    if not isinstance(market_state, dict):
        raise ValueError("Market state must be a dictionary.")

    request = build_strategy_market_state_request(
        symbol=market_state.get("symbol", DEFAULT_SYMBOL),
        timeframe=market_state.get("timeframe", DEFAULT_TIMEFRAME),
        regime=market_state.get("regime", DEFAULT_STRATEGY_REGIME),
        trend=market_state.get("trend", DEFAULT_STRATEGY_TREND),
        entry_price=market_state.get("entry_price", market_state.get("close", DEFAULT_STRATEGY_ENTRY_PRICE)),
    )

    normalized = request.to_market_state()

    for key, value in market_state.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def strategy_agent_operation(
    agent: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute a StrategyAgent action and convert the result into an API response.
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
                    code="STRATEGY_AGENT_ERROR",
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


def api_strategy_signal(
    agent: Any,
    *,
    market_state: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return strategy signal from StrategyAgent."""
    try:
        payload = {
            "market_state": normalize_market_state(market_state),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="market_state",
            details={
                "market_state": market_state,
            },
            request_id=request_id,
        )

    return strategy_agent_operation(
        agent,
        action="signal",
        payload=payload,
        success_message="Strategy signal generated.",
        failure_message="Strategy signal could not be generated.",
        request_id=request_id,
    )


def api_strategy_decision(
    agent: Any,
    *,
    market_state: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return strategy decision from StrategyAgent."""
    try:
        payload = {
            "market_state": normalize_market_state(market_state),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="market_state",
            details={
                "market_state": market_state,
            },
            request_id=request_id,
        )

    return strategy_agent_operation(
        agent,
        action="decision",
        payload=payload,
        success_message="Strategy decision generated.",
        failure_message="Strategy decision could not be generated.",
        request_id=request_id,
    )


def api_strategy_explanation(
    agent: Any,
    *,
    market_state: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return strategy explanation from StrategyAgent."""
    try:
        payload = {
            "market_state": normalize_market_state(market_state),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="market_state",
            details={
                "market_state": market_state,
            },
            request_id=request_id,
        )

    return strategy_agent_operation(
        agent,
        action="explain-signal",
        payload=payload,
        success_message="Strategy explanation generated.",
        failure_message="Strategy explanation could not be generated.",
        request_id=request_id,
    )


def api_entry_check(
    agent: Any,
    *,
    market_state: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return entry check from StrategyAgent."""
    try:
        payload = {
            "market_state": normalize_market_state(market_state),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="market_state",
            details={
                "market_state": market_state,
            },
            request_id=request_id,
        )

    return strategy_agent_operation(
        agent,
        action="entry-check",
        payload=payload,
        success_message="Entry check completed.",
        failure_message="Entry check could not be completed.",
        request_id=request_id,
    )


def api_exit_check(
    agent: Any,
    *,
    market_state: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return exit check from StrategyAgent."""
    try:
        payload = {
            "market_state": normalize_market_state(market_state),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="market_state",
            details={
                "market_state": market_state,
            },
            request_id=request_id,
        )

    return strategy_agent_operation(
        agent,
        action="exit-check",
        payload=payload,
        success_message="Exit check completed.",
        failure_message="Exit check could not be completed.",
        request_id=request_id,
    )


def api_strategy_handoff(
    agent: Any,
    *,
    market_state: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Return strategy handoff from StrategyAgent."""
    try:
        payload = {
            "market_state": normalize_market_state(market_state),
        }
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="market_state",
            details={
                "market_state": market_state,
            },
            request_id=request_id,
        )

    return strategy_agent_operation(
        agent,
        action="handoff",
        payload=payload,
        success_message="Strategy handoff generated.",
        failure_message="Strategy handoff could not be generated.",
        request_id=request_id,
    )