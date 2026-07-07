"""
Agent base.

Defines the shared base classes, task schema, and result schema
for all AQOS agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class AgentTask:
    """
    Represents a task sent to an AQOS agent.
    """

    action: str
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.action, str):
            raise TypeError("Agent task action must be a string.")

        if not self.action:
            raise ValueError("Agent task action cannot be empty.")

        if not isinstance(self.payload, dict):
            raise TypeError("Agent task payload must be a dictionary.")

        if not isinstance(self.metadata, dict):
            raise TypeError("Agent task metadata must be a dictionary.")


@dataclass(slots=True, frozen=True)
class AgentResult:
    """
    Represents a result returned by an AQOS agent.
    """

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise TypeError("Agent result success must be a boolean.")

        if not isinstance(self.message, str):
            raise TypeError("Agent result message must be a string.")

        if not self.message:
            raise ValueError("Agent result message cannot be empty.")

        if not isinstance(self.data, dict):
            raise TypeError("Agent result data must be a dictionary.")

        if not isinstance(self.metadata, dict):
            raise TypeError("Agent result metadata must be a dictionary.")


class AgentBase(ABC):
    """
    Base class for all AQOS agents.
    """

    SUPPORTED_ACTIONS: set[str] = set()

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return agent name.
        """

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return f"{self.name} agent"

    @abstractmethod
    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run an agent task.
        """

    def execute(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Execute an agent action safely.
        """

        try:
            normalized_action = self.normalize_action(action)

            task = AgentTask(
                action=normalized_action,
                payload=payload or {},
                metadata=metadata or {},
            )

            self.validate_supported_action(task.action)

            return self.run(task)
        except (TypeError, ValueError) as exc:
            return self.failure(
                message=str(exc),
                metadata=metadata or {},
            )

    def available_actions(self) -> list[str]:
        """
        Return supported actions.
        """

        return sorted(self.SUPPORTED_ACTIONS)

    def normalize_action(
        self,
        action: str,
    ) -> str:
        """
        Normalize an agent action name.
        """

        if not isinstance(action, str):
            raise TypeError("Agent action must be a string.")

        normalized = action.lower().strip().replace("_", "-").replace(" ", "-")

        if not normalized:
            raise ValueError("Agent action cannot be empty.")

        return normalized

    def validate_supported_action(
        self,
        action: str,
    ) -> None:
        """
        Validate that an action is supported by the agent.
        """

        if self.SUPPORTED_ACTIONS and action not in self.SUPPORTED_ACTIONS:
            raise ValueError(f"Unsupported agent action: {action}")

    def validate_task(
        self,
        task: AgentTask,
    ) -> None:
        """
        Validate an agent task.
        """

        if not isinstance(task, AgentTask):
            raise TypeError("Task must be an AgentTask.")

        self.validate_supported_action(task.action)

    def get_required_payload_value(
        self,
        payload: dict[str, Any],
        key: str,
    ) -> Any:
        """
        Get a required value from an agent payload.
        """

        self.validate_payload(payload)

        if not key:
            raise ValueError("Payload key cannot be empty.")

        if key not in payload:
            raise ValueError(f"Missing required payload key: {key}")

        return payload[key]

    def validate_payload(
        self,
        payload: dict[str, Any],
    ) -> None:
        """
        Validate payload.
        """

        if not isinstance(payload, dict):
            raise TypeError("Payload must be a dictionary.")

    def validate_metadata(
        self,
        metadata: dict[str, Any],
    ) -> None:
        """
        Validate metadata.
        """

        if not isinstance(metadata, dict):
            raise TypeError("Metadata must be a dictionary.")

    def success(
        self,
        message: str,
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Build a successful agent result.
        """

        return AgentResult(
            success=True,
            message=message,
            data=data or {},
            metadata=metadata or {},
        )

    def failure(
        self,
        message: str,
        data: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentResult:
        """
        Build a failed agent result.
        """

        return AgentResult(
            success=False,
            message=message,
            data=data or {},
            metadata=metadata or {},
        )


__all__ = [
    "AgentBase",
    "AgentResult",
    "AgentTask",
]