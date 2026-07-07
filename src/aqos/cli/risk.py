"""
AQOS CLI risk commands.

This module converts AQOS API risk operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aqos.api import (
    ApiResponse,
    RiskTradeRequest,
    api_approve_trade,
    api_assess_trade,
    api_position_size,
    api_reject_reason,
    api_risk_handoff,
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
)


DEFAULT_CLI_RISK_SIDE = "buy"
DEFAULT_CLI_RISK_ENTRY_PRICE = 2025.0
DEFAULT_CLI_RISK_STOP_LOSS_PRICE = 2015.0
DEFAULT_CLI_RISK_TAKE_PROFIT_PRICE = 2045.0


@dataclass(frozen=True)
class CliRiskRequest:
    """
    Standard CLI risk request.
    """

    agent: Any
    symbol: str = DEFAULT_SYMBOL
    side: str = DEFAULT_CLI_RISK_SIDE
    account_balance: float = DEFAULT_ACCOUNT_BALANCE
    risk_percent: float = DEFAULT_RISK_PERCENT
    entry_price: float = DEFAULT_CLI_RISK_ENTRY_PRICE
    stop_loss_price: float = DEFAULT_CLI_RISK_STOP_LOSS_PRICE
    take_profit_price: float | None = DEFAULT_CLI_RISK_TAKE_PROFIT_PRICE
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Risk agent is required.")

        RiskTradeRequest(
            symbol=self.symbol,
            side=self.side,
            account_balance=self.account_balance,
            risk_percent=self.risk_percent,
            entry_price=self.entry_price,
            stop_loss_price=self.stop_loss_price,
            take_profit_price=self.take_profit_price,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_trade_request(self) -> dict[str, Any]:
        """Convert CLI request into API risk trade request."""
        return RiskTradeRequest(
            symbol=self.symbol,
            side=self.side,
            account_balance=self.account_balance,
            risk_percent=self.risk_percent,
            entry_price=self.entry_price,
            stop_loss_price=self.stop_loss_price,
            take_profit_price=self.take_profit_price,
        ).to_trade_request()


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_risk_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI risk operation callback."""
    if not callable(operation):
        raise ValueError("Risk operation must be callable.")

    return operation


def execute_risk_operation(
    operation: Callable[..., ApiResponse],
    *,
    agent: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute a risk API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_risk_operation(operation)

    if agent is None:
        raise ValueError("Risk agent is required.")

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


def build_risk_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for a risk API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def run_risk_cli_operation(
    *,
    agent: Any,
    operation: Callable[..., ApiResponse],
    output_format: CliOutputFormat | str,
    include_metadata: bool,
    request_id: str | None,
    symbol: str,
    side: str,
    account_balance: float,
    risk_percent: float,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float | None,
) -> CliOutput:
    """Run a shared risk CLI operation."""
    request = CliRiskRequest(
        agent=agent,
        symbol=symbol,
        side=side,
        account_balance=account_balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_risk_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        trade_request=request.to_trade_request(),
    )

    return build_risk_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_position_size(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_RISK_SIDE,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    entry_price: float = DEFAULT_CLI_RISK_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_CLI_RISK_STOP_LOSS_PRICE,
    take_profit_price: float | None = DEFAULT_CLI_RISK_TAKE_PROFIT_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_position_size,
) -> CliOutput:
    """Run position-size command."""
    return run_risk_cli_operation(
        agent=agent,
        operation=operation,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        side=side,
        account_balance=account_balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def cli_assess_trade(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_RISK_SIDE,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    entry_price: float = DEFAULT_CLI_RISK_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_CLI_RISK_STOP_LOSS_PRICE,
    take_profit_price: float | None = DEFAULT_CLI_RISK_TAKE_PROFIT_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_assess_trade,
) -> CliOutput:
    """Run assess-trade command."""
    return run_risk_cli_operation(
        agent=agent,
        operation=operation,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        side=side,
        account_balance=account_balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def cli_approve_trade(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_RISK_SIDE,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    entry_price: float = DEFAULT_CLI_RISK_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_CLI_RISK_STOP_LOSS_PRICE,
    take_profit_price: float | None = DEFAULT_CLI_RISK_TAKE_PROFIT_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_approve_trade,
) -> CliOutput:
    """Run approve-trade command."""
    return run_risk_cli_operation(
        agent=agent,
        operation=operation,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        side=side,
        account_balance=account_balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def cli_reject_reason(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_RISK_SIDE,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    entry_price: float = DEFAULT_CLI_RISK_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_CLI_RISK_STOP_LOSS_PRICE,
    take_profit_price: float | None = DEFAULT_CLI_RISK_TAKE_PROFIT_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_reject_reason,
) -> CliOutput:
    """Run reject-reason command."""
    return run_risk_cli_operation(
        agent=agent,
        operation=operation,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        side=side,
        account_balance=account_balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )


def cli_risk_handoff(
    *,
    agent: Any,
    symbol: str = DEFAULT_SYMBOL,
    side: str = DEFAULT_CLI_RISK_SIDE,
    account_balance: float = DEFAULT_ACCOUNT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    entry_price: float = DEFAULT_CLI_RISK_ENTRY_PRICE,
    stop_loss_price: float = DEFAULT_CLI_RISK_STOP_LOSS_PRICE,
    take_profit_price: float | None = DEFAULT_CLI_RISK_TAKE_PROFIT_PRICE,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_risk_handoff,
) -> CliOutput:
    """Run risk-handoff command."""
    return run_risk_cli_operation(
        agent=agent,
        operation=operation,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
        symbol=symbol,
        side=side,
        account_balance=account_balance,
        risk_percent=risk_percent,
        entry_price=entry_price,
        stop_loss_price=stop_loss_price,
        take_profit_price=take_profit_price,
    )