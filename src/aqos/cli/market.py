"""
AQOS CLI market commands.

This module converts AQOS API market operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aqos.api import (
    ApiResponse,
    MarketRequest,
    api_calendar_context,
    api_market_snapshot,
    api_market_state,
    api_news_context,
    api_regime_summary,
    api_trend_summary,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
)
from aqos.common import DEFAULT_SYMBOL, DEFAULT_TIMEFRAME
from aqos.common.validators import validate_symbol, validate_timeframe


@dataclass(frozen=True)
class CliMarketRequest:
    """
    Standard CLI market request.
    """

    agent: Any
    symbol: str = DEFAULT_SYMBOL
    timeframe: str = DEFAULT_TIMEFRAME
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Market agent is required.")

        validate_symbol(self.symbol)
        validate_timeframe(self.timeframe)
        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_market_request(self) -> MarketRequest:
        """Convert CLI request into API market request."""
        return MarketRequest(
            symbol=self.symbol,
            timeframe=self.timeframe,
        )


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_market_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI market operation callback."""
    if not callable(operation):
        raise ValueError("Market operation must be callable.")

    return operation


def execute_market_operation(
    operation: Callable[..., ApiResponse],
    *,
    agent: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute a market API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_market_operation(operation)

    if agent is None:
        raise ValueError("Market agent is required.")

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


def build_market_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for a market API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def cli_market_state(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_market_state,
) -> CliOutput:
    """Run market-state command."""
    request = CliMarketRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    market_request = request.to_market_request()

    response = execute_market_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **market_request.to_payload(),
    )

    return build_market_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_market_snapshot(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_market_snapshot,
) -> CliOutput:
    """Run market-snapshot command."""
    request = CliMarketRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    market_request = request.to_market_request()

    response = execute_market_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **market_request.to_payload(),
    )

    return build_market_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_trend_summary(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_trend_summary,
) -> CliOutput:
    """Run trend-summary command."""
    request = CliMarketRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    market_request = request.to_market_request()

    response = execute_market_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **market_request.to_payload(),
    )

    return build_market_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_regime_summary(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_regime_summary,
) -> CliOutput:
    """Run regime-summary command."""
    request = CliMarketRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    market_request = request.to_market_request()

    response = execute_market_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **market_request.to_payload(),
    )

    return build_market_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_news_context(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_news_context,
) -> CliOutput:
    """Run news-context command."""
    request = CliMarketRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    market_request = request.to_market_request()

    response = execute_market_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **market_request.to_payload(),
    )

    return build_market_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_calendar_context(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    timeframe: str = DEFAULT_TIMEFRAME,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_calendar_context,
) -> CliOutput:
    """Run calendar-context command."""
    request = CliMarketRequest(
        agent=agent,
        symbol=symbol,
        timeframe=timeframe,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    market_request = request.to_market_request()

    response = execute_market_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **market_request.to_payload(),
    )

    return build_market_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )