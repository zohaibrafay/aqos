"""
AQOS API memory operations.

This module provides framework-independent API helpers for memory-facing
operations. It wraps MemoryAgent actions in consistent ApiResponse envelopes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.api.responses import (
    ApiResponse,
    api_error,
    api_failure,
    api_success,
    exception_failure,
    validation_failure,
)
from aqos.common import DEFAULT_SYMBOL
from aqos.common.validators import validate_side, validate_symbol


DEFAULT_MEMORY_TYPE = "observation"
DEFAULT_MEMORY_IMPORTANCE = 0.5
VALID_API_MEMORY_TYPES = {
    "observation",
    "pattern",
    "trade",
    "research",
    "strategy",
    "risk",
    "execution",
    "evaluation",
}


def validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")

    return value.strip()


def validate_optional_memory_type(value: str | None) -> str | None:
    """Validate optional memory type."""
    if value is None:
        return None

    return validate_memory_type(value)


def validate_memory_type(value: str) -> str:
    """Validate memory type."""
    normalized = validate_non_empty_string(value, "Memory type").lower()

    if normalized not in VALID_API_MEMORY_TYPES:
        raise ValueError(
            "Memory type must be one of: "
            + ", ".join(sorted(VALID_API_MEMORY_TYPES))
            + "."
        )

    return normalized


def validate_importance(value: float) -> float:
    """Validate memory importance score."""
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise ValueError("Memory importance must be a number.")

    normalized = float(value)

    if normalized < 0 or normalized > 1:
        raise ValueError("Memory importance must be between 0 and 1.")

    return normalized


def validate_metadata(metadata: dict[str, Any], field_name: str) -> dict[str, Any]:
    """Validate metadata dictionary."""
    if not isinstance(metadata, dict):
        raise ValueError(f"{field_name} must be a dictionary.")

    return metadata


@dataclass(frozen=True)
class RememberMemoryRequest:
    """
    Standard memory API remember request.
    """

    memory_id: str
    content: str
    memory_type: str = DEFAULT_MEMORY_TYPE
    importance: float = DEFAULT_MEMORY_IMPORTANCE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.memory_id, "Memory ID")
        validate_non_empty_string(self.content, "Memory content")
        validate_memory_type(self.memory_type)
        validate_importance(self.importance)
        validate_metadata(self.metadata, "Memory metadata")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into MemoryAgent payload."""
        return {
            "memory_id": validate_non_empty_string(self.memory_id, "Memory ID"),
            "content": validate_non_empty_string(
                self.content,
                "Memory content",
            ),
            "memory_type": validate_memory_type(self.memory_type),
            "importance": validate_importance(self.importance),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class RecallMemoryRequest:
    """
    Standard memory API recall request.
    """

    query: str
    memory_type: str | None = None

    def __post_init__(self) -> None:
        validate_non_empty_string(self.query, "Memory query")
        validate_optional_memory_type(self.memory_type)

    def to_payload(self) -> dict[str, Any]:
        """Convert request into MemoryAgent payload."""
        payload: dict[str, Any] = {
            "query": validate_non_empty_string(
                self.query,
                "Memory query",
            ),
        }

        normalized_memory_type = validate_optional_memory_type(self.memory_type)

        if normalized_memory_type:
            payload["memory_type"] = normalized_memory_type

        return payload


@dataclass(frozen=True)
class MemoryIdRequest:
    """
    Standard memory API memory-id request.
    """

    memory_id: str

    def __post_init__(self) -> None:
        validate_non_empty_string(self.memory_id, "Memory ID")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into MemoryAgent payload."""
        return {
            "memory_id": validate_non_empty_string(self.memory_id, "Memory ID"),
        }


@dataclass(frozen=True)
class PatternMemoryRequest:
    """
    Standard memory API pattern-memory request.
    """

    memory_id: str
    pattern: str
    importance: float = DEFAULT_MEMORY_IMPORTANCE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.memory_id, "Memory ID")
        validate_non_empty_string(self.pattern, "Pattern")
        validate_importance(self.importance)
        validate_metadata(self.metadata, "Pattern metadata")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into MemoryAgent payload."""
        return {
            "memory_id": validate_non_empty_string(self.memory_id, "Memory ID"),
            "pattern": validate_non_empty_string(self.pattern, "Pattern"),
            "importance": validate_importance(self.importance),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class TradeMemoryRequest:
    """
    Standard memory API trade-memory request.
    """

    memory_id: str
    symbol: str = DEFAULT_SYMBOL
    side: str = "buy"
    outcome: str = "open"
    importance: float = DEFAULT_MEMORY_IMPORTANCE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.memory_id, "Memory ID")
        validate_symbol(self.symbol)
        validate_side(self.side)
        validate_non_empty_string(self.outcome, "Trade outcome")
        validate_importance(self.importance)
        validate_metadata(self.metadata, "Trade metadata")

    def to_payload(self) -> dict[str, Any]:
        """Convert request into MemoryAgent payload."""
        return {
            "memory_id": validate_non_empty_string(self.memory_id, "Memory ID"),
            "symbol": validate_symbol(self.symbol),
            "side": validate_side(self.side),
            "outcome": validate_non_empty_string(
                self.outcome,
                "Trade outcome",
            ),
            "importance": validate_importance(self.importance),
            "metadata": self.metadata,
        }


def normalize_remember_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external remember request dictionary."""
    if not isinstance(request, dict):
        raise ValueError("Remember request must be a dictionary.")

    normalized_request = RememberMemoryRequest(
        memory_id=request.get("memory_id", ""),
        content=request.get("content", ""),
        memory_type=request.get("memory_type", DEFAULT_MEMORY_TYPE),
        importance=request.get("importance", DEFAULT_MEMORY_IMPORTANCE),
        metadata=request.get("metadata", {}),
    )

    normalized = normalized_request.to_payload()

    for key, value in request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def normalize_recall_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external recall request dictionary."""
    if not isinstance(request, dict):
        raise ValueError("Recall request must be a dictionary.")

    normalized_request = RecallMemoryRequest(
        query=request.get("query", ""),
        memory_type=request.get("memory_type"),
    )

    normalized = normalized_request.to_payload()

    for key, value in request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def normalize_pattern_memory_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external pattern-memory request dictionary."""
    if not isinstance(request, dict):
        raise ValueError("Pattern memory request must be a dictionary.")

    normalized_request = PatternMemoryRequest(
        memory_id=request.get("memory_id", ""),
        pattern=request.get("pattern", ""),
        importance=request.get("importance", DEFAULT_MEMORY_IMPORTANCE),
        metadata=request.get("metadata", {}),
    )

    normalized = normalized_request.to_payload()

    for key, value in request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def normalize_trade_memory_request(
    request: dict[str, Any],
) -> dict[str, Any]:
    """Normalize an external trade-memory request dictionary."""
    if not isinstance(request, dict):
        raise ValueError("Trade memory request must be a dictionary.")

    normalized_request = TradeMemoryRequest(
        memory_id=request.get("memory_id", ""),
        symbol=request.get("symbol", DEFAULT_SYMBOL),
        side=request.get("side", "buy"),
        outcome=request.get("outcome", "open"),
        importance=request.get("importance", DEFAULT_MEMORY_IMPORTANCE),
        metadata=request.get("metadata", {}),
    )

    normalized = normalized_request.to_payload()

    for key, value in request.items():
        if key not in normalized:
            normalized[key] = value

    return normalized


def memory_agent_operation(
    agent: Any,
    *,
    action: str,
    payload: dict[str, Any],
    success_message: str,
    failure_message: str,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Execute a MemoryAgent action and convert the result into an API response.
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
                    code="MEMORY_AGENT_ERROR",
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


def api_remember(
    agent: Any,
    *,
    memory: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Store memory through MemoryAgent."""
    try:
        payload = normalize_remember_request(memory)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="memory",
            details={
                "memory": memory,
            },
            request_id=request_id,
        )

    return memory_agent_operation(
        agent,
        action="remember",
        payload=payload,
        success_message="Memory stored.",
        failure_message="Memory could not be stored.",
        request_id=request_id,
    )


def api_recall(
    agent: Any,
    *,
    recall: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Recall memories through MemoryAgent."""
    try:
        payload = normalize_recall_request(recall)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="recall",
            details={
                "recall": recall,
            },
            request_id=request_id,
        )

    return memory_agent_operation(
        agent,
        action="recall",
        payload=payload,
        success_message="Memory recall completed.",
        failure_message="Memory recall could not be completed.",
        request_id=request_id,
    )


def api_get_memory(
    agent: Any,
    *,
    memory_id: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Get memory by ID through MemoryAgent."""
    try:
        request = MemoryIdRequest(memory_id=memory_id)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="memory_id",
            details={
                "memory_id": memory_id,
            },
            request_id=request_id,
        )

    return memory_agent_operation(
        agent,
        action="get-memory",
        payload=request.to_payload(),
        success_message="Memory loaded.",
        failure_message="Memory could not be loaded.",
        request_id=request_id,
    )


def api_forget(
    agent: Any,
    *,
    memory_id: str,
    request_id: str | None = None,
) -> ApiResponse:
    """Forget memory by ID through MemoryAgent."""
    try:
        request = MemoryIdRequest(memory_id=memory_id)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="memory_id",
            details={
                "memory_id": memory_id,
            },
            request_id=request_id,
        )

    return memory_agent_operation(
        agent,
        action="forget",
        payload=request.to_payload(),
        success_message="Memory forgotten.",
        failure_message="Memory could not be forgotten.",
        request_id=request_id,
    )


def api_memory_summary(
    agent: Any,
    *,
    request_id: str | None = None,
) -> ApiResponse:
    """Return memory summary through MemoryAgent."""
    return memory_agent_operation(
        agent,
        action="memory-summary",
        payload={},
        success_message="Memory summary loaded.",
        failure_message="Memory summary could not be loaded.",
        request_id=request_id,
    )


def api_pattern_memory(
    agent: Any,
    *,
    pattern_memory: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Store pattern memory through MemoryAgent."""
    try:
        payload = normalize_pattern_memory_request(pattern_memory)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="pattern_memory",
            details={
                "pattern_memory": pattern_memory,
            },
            request_id=request_id,
        )

    return memory_agent_operation(
        agent,
        action="pattern-memory",
        payload=payload,
        success_message="Pattern memory stored.",
        failure_message="Pattern memory could not be stored.",
        request_id=request_id,
    )


def api_trade_memory(
    agent: Any,
    *,
    trade_memory: dict[str, Any],
    request_id: str | None = None,
) -> ApiResponse:
    """Store trade memory through MemoryAgent."""
    try:
        payload = normalize_trade_memory_request(trade_memory)
    except ValueError as exception:
        return validation_failure(
            message=str(exception),
            field="trade_memory",
            details={
                "trade_memory": trade_memory,
            },
            request_id=request_id,
        )

    return memory_agent_operation(
        agent,
        action="trade-memory",
        payload=payload,
        success_message="Trade memory stored.",
        failure_message="Trade memory could not be stored.",
        request_id=request_id,
    )