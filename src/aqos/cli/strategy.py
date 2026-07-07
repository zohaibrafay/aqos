"""
AQOS CLI strategy commands.

This module converts AQOS API strategy operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aqos.api import (
    ApiResponse,
    StrategyMarketStateRequest,
    api_entry_check,
    api_exit_check,
    api_strategy_decision,
    api_strategy_explanation,
    api_strategy_handoff,
    api_strategy_signal,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
)
from aqos.common import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME


DEFAULT_CLI_STRATEGY_REGIME = "bullish"
DEFAULT_CLI_STRATEGY_TREND = "uptrend"
DEFAULT_CLI_STRATEGY_ENTRY_PRICE = 2025.0


@dataclass(frozen=True)
class CliStrategyRequest:
    """
    Standard CLI strategy request.
    """

    agent: Any
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    regime: str = DEFAULT_CLI_STRATEGY_REGIME
    trend: str = DEFAULT_CLI_STRATEGY_TREND
    entry_price: float = DEFAULT_CLI_STRATEGY_ENTRY_PRICE
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Strategy agent is required.")

        StrategyMarketStateRequest(
            symbol=self.symbol,
            timeframe=self.timeframe,
            regime=self.regime,
            trend=self.trend,
            entry_price=self.entry_price,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_market_state(self) -> dict[str, Any]:
        """Convert CLI request into API strategy market state."""
        return StrategyMarketStateRequest(
            symbol=self.symbol,
            timeframe=self.timeframe,
            regime=self.regime,
            trend=self.trend,
            entry_price=self.entry_price,
        ).to_market_state()


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_strategy_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI strategy operation callback."""
    if not callable(operation):
        raise ValueError("Strategy operation must be callable.")

    return operation


def execute_strategy_operation(
    operation: Callable[..., ApiResponse],
    *,
    agent: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute a strategy API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_strategy_operation(operation)

    if agent is None:
        raise ValueError("Strategy agent is required.")

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


def build_strategy_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for a strategy API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def run_strategy_cli_operation(
    *,
    agent: Any,
    operation: Callable[..., ApiResponse],
    success_output_format: CliOutputFormat | str,
    include_metadata: bool,
    request_id: str | None,
    symbol: str,
    timeframe: str,
    regime: str,
    trend: str,
    entry_price: float,
) -> CliOutput:
    """Run a shared strategy CLI operation."""
    request = CliStrategyRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
        output_format=success_output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_strategy_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        market_state=request.to_market_state(),
    )

    return build_strategy_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_strategy_signal(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_CLI_STRATEGY_REGIME,
    trend: str = DEFAULT_CLI_STRATEGY_TREND,
    entry_price: float = DEFAULT_CLI_STRATEGY_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_strategy_signal,
) -> CliOutput:
    """Run strategy-signal command."""
    return run_strategy_cli_operation(
        agent=agent,
        operation=operation,
        success_output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
    )


def cli_strategy_decision(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_CLI_STRATEGY_REGIME,
    trend: str = DEFAULT_CLI_STRATEGY_TREND,
    entry_price: float = DEFAULT_CLI_STRATEGY_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_strategy_decision,
) -> CliOutput:
    """Run strategy-decision command."""
    return run_strategy_cli_operation(
        agent=agent,
        operation=operation,
        success_output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
    )


def cli_strategy_explanation(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_CLI_STRATEGY_REGIME,
    trend: str = DEFAULT_CLI_STRATEGY_TREND,
    entry_price: float = DEFAULT_CLI_STRATEGY_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_strategy_explanation,
) -> CliOutput:
    """Run strategy-explanation command."""
    return run_strategy_cli_operation(
        agent=agent,
        operation=operation,
        success_output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
    )


def cli_entry_check(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_CLI_STRATEGY_REGIME,
    trend: str = DEFAULT_CLI_STRATEGY_TREND,
    entry_price: float = DEFAULT_CLI_STRATEGY_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_entry_check,
) -> CliOutput:
    """Run strategy entry-check command."""
    return run_strategy_cli_operation(
        agent=agent,
        operation=operation,
        success_output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
    )


def cli_exit_check(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_CLI_STRATEGY_REGIME,
    trend: str = DEFAULT_CLI_STRATEGY_TREND,
    entry_price: float = DEFAULT_CLI_STRATEGY_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_exit_check,
) -> CliOutput:
    """Run strategy exit-check command."""
    return run_strategy_cli_operation(
        agent=agent,
        operation=operation,
        success_output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
    )


def cli_strategy_handoff(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    regime: str = DEFAULT_CLI_STRATEGY_REGIME,
    trend: str = DEFAULT_CLI_STRATEGY_TREND,
    entry_price: float = DEFAULT_CLI_STRATEGY_ENTRY_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_strategy_handoff,
) -> CliOutput:
    """Run strategy-handoff command."""
    return run_strategy_cli_operation(
        agent=agent,
        operation=operation,
        success_output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        timeframe=timeframe,
        regime=regime,
        trend=trend,
        entry_price=entry_price,
    )