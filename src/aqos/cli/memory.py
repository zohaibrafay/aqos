"""
AQOS CLI memory commands.

This module converts AQOS API memory operations into CLI-friendly outputs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from aqos.api import (
    ApiResponse,
    MemoryIdRequest,
    PatternMemoryRequest,
    RecallMemoryRequest,
    RememberMemoryRequest,
    TradeMemoryRequest,
    api_forget,
    api_get_memory,
    api_memory_summary,
    api_pattern_memory,
    api_recall,
    api_remember,
    api_trade_memory,
)
from aqos.cli.formatting import (
    CliOutput,
    CliOutputFormat,
    build_cli_output,
    normalize_output_format,
)
from aqos.common import DEFAULT_SYMBOL


DEFAULT_CLI_MEMORY_TYPE = "observation"
DEFAULT_CLI_MEMORY_IMPORTANCE = 0.5


@dataclass(frozen=True)
class CliRememberMemoryRequest:
    """
    Standard CLI remember-memory request.
    """

    agent: Any
    memory_id: str
    content: str
    memory_type: str = DEFAULT_CLI_MEMORY_TYPE
    importance: float = DEFAULT_CLI_MEMORY_IMPORTANCE
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Memory agent is required.")

        RememberMemoryRequest(
            memory_id=self.memory_id,
            content=self.content,
            memory_type=self.memory_type,
            importance=self.importance,
            metadata=self.metadata,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_memory(self) -> dict[str, Any]:
        """Convert CLI request into remember-memory payload."""
        return RememberMemoryRequest(
            memory_id=self.memory_id,
            content=self.content,
            memory_type=self.memory_type,
            importance=self.importance,
            metadata=self.metadata,
        ).to_payload()


@dataclass(frozen=True)
class CliRecallMemoryRequest:
    """
    Standard CLI recall-memory request.
    """

    agent: Any
    query: str
    memory_type: str | None = None
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Memory agent is required.")

        RecallMemoryRequest(
            query=self.query,
            memory_type=self.memory_type,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_recall(self) -> dict[str, Any]:
        """Convert CLI request into recall-memory payload."""
        return RecallMemoryRequest(
            query=self.query,
            memory_type=self.memory_type,
        ).to_payload()


@dataclass(frozen=True)
class CliMemoryIdRequest:
    """
    Standard CLI memory-id request.
    """

    agent: Any
    memory_id: str
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Memory agent is required.")

        MemoryIdRequest(memory_id=self.memory_id)
        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert CLI request into memory-id payload."""
        return MemoryIdRequest(memory_id=self.memory_id).to_payload()


@dataclass(frozen=True)
class CliPatternMemoryRequest:
    """
    Standard CLI pattern-memory request.
    """

    agent: Any
    memory_id: str
    pattern: str
    importance: float = DEFAULT_CLI_MEMORY_IMPORTANCE
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Memory agent is required.")

        PatternMemoryRequest(
            memory_id=self.memory_id,
            pattern=self.pattern,
            importance=self.importance,
            metadata=self.metadata,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_pattern_memory(self) -> dict[str, Any]:
        """Convert CLI request into pattern-memory payload."""
        return PatternMemoryRequest(
            memory_id=self.memory_id,
            pattern=self.pattern,
            importance=self.importance,
            metadata=self.metadata,
        ).to_payload()


@dataclass(frozen=True)
class CliTradeMemoryRequest:
    """
    Standard CLI trade-memory request.
    """

    agent: Any
    memory_id: str
    symbol: str = DEFAULT_SYMBOL
    side: str = "buy"
    outcome: str = "open"
    importance: float = DEFAULT_CLI_MEMORY_IMPORTANCE
    metadata: dict[str, Any] = field(default_factory=dict)
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Memory agent is required.")

        TradeMemoryRequest(
            memory_id=self.memory_id,
            symbol=self.symbol,
            side=self.side,
            outcome=self.outcome,
            importance=self.importance,
            metadata=self.metadata,
        )

        normalize_output_format(self.output_format)

        if not isinstance(self.include_metadata, bool):
            raise ValueError("Include metadata must be a boolean.")

        if self.request_id is not None:
            validate_non_empty_string(self.request_id, "Request ID")

    def to_trade_memory(self) -> dict[str, Any]:
        """Convert CLI request into trade-memory payload."""
        return TradeMemoryRequest(
            memory_id=self.memory_id,
            symbol=self.symbol,
            side=self.side,
            outcome=self.outcome,
            importance=self.importance,
            metadata=self.metadata,
        ).to_payload()


@dataclass(frozen=True)
class CliMemorySummaryRequest:
    """
    Standard CLI memory-summary request.
    """

    agent: Any
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT
    include_metadata: bool = False
    request_id: str | None = None

    def __post_init__(self) -> None:
        if self.agent is None:
            raise ValueError("Memory agent is required.")

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


def validate_memory_operation(
    operation: Callable[..., ApiResponse],
) -> Callable[..., ApiResponse]:
    """Validate CLI memory operation callback."""
    if not callable(operation):
        raise ValueError("Memory operation must be callable.")

    return operation


def execute_memory_operation(
    operation: Callable[..., ApiResponse],
    *,
    agent: Any,
    request_id: str | None = None,
    **kwargs: Any,
) -> ApiResponse:
    """
    Execute a memory API operation.

    This helper passes request_id when the target operation supports it, while
    remaining compatible with simple fake operations used in unit tests.
    """
    validate_memory_operation(operation)

    if agent is None:
        raise ValueError("Memory agent is required.")

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


def build_memory_cli_output(
    response: ApiResponse,
    *,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
) -> CliOutput:
    """Build CLI output for a memory API response."""
    return build_cli_output(
        response,
        output_format=output_format,
        include_metadata=include_metadata,
    )


def cli_remember(
    *,
    agent: Any,
    memory_id: str,
    content: str,
    memory_type: str = DEFAULT_CLI_MEMORY_TYPE,
    importance: float = DEFAULT_CLI_MEMORY_IMPORTANCE,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_remember,
) -> CliOutput:
    """Run remember command."""
    request = CliRememberMemoryRequest(
        agent=agent,
        memory_id=memory_id,
        content=content,
        memory_type=memory_type,
        importance=importance,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_memory_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        memory=request.to_memory(),
    )

    return build_memory_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_recall(
    *,
    agent: Any,
    query: str,
    memory_type: str | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_recall,
) -> CliOutput:
    """Run recall command."""
    request = CliRecallMemoryRequest(
        agent=agent,
        query=query,
        memory_type=memory_type,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_memory_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        recall=request.to_recall(),
    )

    return build_memory_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_get_memory(
    *,
    agent: Any,
    memory_id: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_get_memory,
) -> CliOutput:
    """Run get-memory command."""
    request = CliMemoryIdRequest(
        agent=agent,
        memory_id=memory_id,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_memory_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_memory_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_forget(
    *,
    agent: Any,
    memory_id: str,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_forget,
) -> CliOutput:
    """Run forget command."""
    request = CliMemoryIdRequest(
        agent=agent,
        memory_id=memory_id,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_memory_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        **request.to_payload(),
    )

    return build_memory_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_memory_summary(
    *,
    agent: Any,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_memory_summary,
) -> CliOutput:
    """Run memory-summary command."""
    request = CliMemorySummaryRequest(
        agent=agent,
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_memory_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
    )

    return build_memory_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_pattern_memory(
    *,
    agent: Any,
    memory_id: str,
    pattern: str,
    importance: float = DEFAULT_CLI_MEMORY_IMPORTANCE,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_pattern_memory,
) -> CliOutput:
    """Run pattern-memory command."""
    request = CliPatternMemoryRequest(
        agent=agent,
        memory_id=memory_id,
        pattern=pattern,
        importance=importance,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_memory_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        pattern_memory=request.to_pattern_memory(),
    )

    return build_memory_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )


def cli_trade_memory(
    *,
    agent: Any,
    memory_id: str,
    symbol: str = DEFAULT_SYMBOL,
    side: str = "buy",
    outcome: str = "open",
    importance: float = DEFAULT_CLI_MEMORY_IMPORTANCE,
    metadata: dict[str, Any] | None = None,
    output_format: CliOutputFormat | str = CliOutputFormat.TEXT,
    include_metadata: bool = False,
    request_id: str | None = None,
    operation: Callable[..., ApiResponse] = api_trade_memory,
) -> CliOutput:
    """Run trade-memory command."""
    request = CliTradeMemoryRequest(
        agent=agent,
        memory_id=memory_id,
        symbol=symbol,
        side=side,
        outcome=outcome,
        importance=importance,
        metadata=metadata or {},
        output_format=output_format,
        include_metadata=include_metadata,
        request_id=request_id,
    )

    response = execute_memory_operation(
        operation,
        agent=request.agent,
        request_id=request.request_id,
        trade_memory=request.to_trade_memory(),
    )

    return build_memory_cli_output(
        response,
        output_format=request.output_format,
        include_metadata=request.include_metadata,
    )