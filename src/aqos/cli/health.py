"""
AQOS CLI health commands.

This module converts AQOS API health operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from aqos.api import (
    ApiResponse,
    agent_health,
    agents_health,
    api_health,
    dependency_health,
    system_health,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
)


@dataclass(frozen=True)
class CliHealthRequest:
    """
    Standard CLI health request.
    """

    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
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


def validate_metadata(details: dict[str, Any] | None) -> dict[str, Any]:
    """Validate optional details dictionary."""
    if details is None:
        return {}

    if not isinstance(details, dict):
        raise ValueError("Details must be a dictionary.")

    return details


def validate_operation(operation: Callable[..., ApiResponse]) -> Callable[..., ApiResponse]:
    """Validate CLI health operation callback."""
    if not callable(operation):
        raise ValueError("Health operation must be callable.")

    return operation


def execute_health_operation(
    operation: Callable[..., ApiResponse],
    *,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute a health API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_operation(operation)

    if request_id is not None:
        try:
            return operation(
                request_id=request_id,
                **kwargs,
            )
        except TypeError:
            return operation(**kwargs)

    return operation(**kwargs)


def build_health_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for a health API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def cli_api_health(
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_health,
) -> CliOutput:
    """Run API health command."""
    request = CliHealthRequest(
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_health_operation(
        operation,
        request_id=request.request_id,
    )

    return build_health_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_system_health(
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = system_health,
) -> CliOutput:
    """Run system health command."""
    request = CliHealthRequest(
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_health_operation(
        operation,
        request_id=request.request_id,
    )

    return build_health_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_dependency_health(
    *,
    name: str,
    status: str = "healthy",
    message: str = "Dependency is healthy.",
    details: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = dependency_health,
) -> CliOutput:
    """Run dependency health command."""
    request = CliHealthRequest(
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_health_operation(
        operation,
        request_id=request.request_id,
        name=validate_non_empty_string(name, "Dependency name"),
        status=validate_non_empty_string(status, "Dependency status"),
        message=validate_non_empty_string(message, "Dependency message"),
        details=validate_metadata(details),
    )

    return build_health_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_agent_health(
    *,
    agent: Any,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = agent_health,
) -> CliOutput:
    """Run single-agent health command."""
    if agent is None:
        raise ValueError("Agent is required.")

    request = CliHealthRequest(
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_health_operation(
        operation,
        request_id=request.request_id,
        agent=agent,
    )

    return build_health_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_agents_health(
    *,
    agents: Sequence[Any],
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = agents_health,
) -> CliOutput:
    """Run multi-agent health command."""
    if not isinstance(agents, Sequence) or isinstance(agents, str) or not agents:
        raise ValueError("Agents must be a non-empty sequence.")

    request = CliHealthRequest(
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_health_operation(
        operation,
        request_id=request.request_id,
        agents=agents,
    )

    return build_health_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )