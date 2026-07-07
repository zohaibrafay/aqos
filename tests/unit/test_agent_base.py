"""
Unit tests for AgentBase.
"""

import pytest

from aqos.agents import (
    AgentBase,
    AgentResult,
    AgentTask,
)


class DummyAgent(AgentBase):
    """
    Test implementation of AgentBase.
    """

    SUPPORTED_ACTIONS = {
        "echo",
        "health",
        "required-value",
    }

    @property
    def name(self) -> str:
        return "dummy-agent"

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        self.validate_task(task)

        if task.action == "health":
            return self.success(
                message="Dummy agent is healthy.",
                data={
                    "status": "ok",
                },
                metadata=task.metadata,
            )

        if task.action == "echo":
            return self.success(
                message="Echo completed.",
                data=task.payload,
                metadata=task.metadata,
            )

        if task.action == "required-value":
            value = self.get_required_payload_value(
                payload=task.payload,
                key="value",
            )

            return self.success(
                message="Required value retrieved.",
                data={
                    "value": value,
                },
                metadata=task.metadata,
            )

        return self.failure("Unhandled action.")


def test_agent_base_cannot_be_instantiated():
    with pytest.raises(TypeError):
        AgentBase()


def test_dummy_agent_is_agent_base_instance():
    agent = DummyAgent()

    assert isinstance(agent, AgentBase)


def test_agent_name():
    agent = DummyAgent()

    assert agent.name == "dummy-agent"


def test_agent_description():
    agent = DummyAgent()

    assert agent.description == "dummy-agent agent"


def test_agent_task():
    task = AgentTask(
        action="health",
        payload={
            "symbol": "XAUUSD",
        },
        metadata={
            "source": "test",
        },
    )

    assert task.action == "health"
    assert task.payload["symbol"] == "XAUUSD"
    assert task.metadata["source"] == "test"


def test_agent_task_rejects_non_string_action():
    with pytest.raises(TypeError):
        AgentTask(
            action=123,
        )


def test_agent_task_rejects_empty_action():
    with pytest.raises(ValueError):
        AgentTask(
            action="",
        )


def test_agent_task_rejects_invalid_payload():
    with pytest.raises(TypeError):
        AgentTask(
            action="health",
            payload="invalid",
        )


def test_agent_task_rejects_invalid_metadata():
    with pytest.raises(TypeError):
        AgentTask(
            action="health",
            metadata="invalid",
        )


def test_agent_result_success():
    result = AgentResult(
        success=True,
        message="Completed.",
        data={
            "status": "ok",
        },
        metadata={
            "source": "test",
        },
    )

    assert result.success is True
    assert result.message == "Completed."
    assert result.data["status"] == "ok"
    assert result.metadata["source"] == "test"


def test_agent_result_rejects_invalid_success():
    with pytest.raises(TypeError):
        AgentResult(
            success="true",
            message="Completed.",
        )


def test_agent_result_rejects_empty_message():
    with pytest.raises(ValueError):
        AgentResult(
            success=True,
            message="",
        )


def test_agent_result_rejects_invalid_data():
    with pytest.raises(TypeError):
        AgentResult(
            success=True,
            message="Completed.",
            data="invalid",
        )


def test_agent_result_rejects_invalid_metadata():
    with pytest.raises(TypeError):
        AgentResult(
            success=True,
            message="Completed.",
            metadata="invalid",
        )


def test_available_actions():
    agent = DummyAgent()

    assert agent.available_actions() == [
        "echo",
        "health",
        "required-value",
    ]


def test_normalize_action():
    agent = DummyAgent()

    assert agent.normalize_action(" HEALTH ") == "health"
    assert agent.normalize_action("required_value") == "required-value"
    assert agent.normalize_action("required value") == "required-value"


def test_normalize_action_rejects_non_string():
    agent = DummyAgent()

    with pytest.raises(TypeError):
        agent.normalize_action(123)


def test_normalize_action_rejects_empty_action():
    agent = DummyAgent()

    with pytest.raises(ValueError):
        agent.normalize_action("")


def test_execute_health():
    agent = DummyAgent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Dummy agent is healthy."
    assert result.data["status"] == "ok"


def test_execute_echo():
    agent = DummyAgent()

    result = agent.execute(
        action="echo",
        payload={
            "symbol": "XAUUSD",
        },
        metadata={
            "source": "test",
        },
    )

    assert result.success is True
    assert result.message == "Echo completed."
    assert result.data["symbol"] == "XAUUSD"
    assert result.metadata["source"] == "test"


def test_execute_normalized_action():
    agent = DummyAgent()

    result = agent.execute("REQUIRED_VALUE", {"value": 10})

    assert result.success is True
    assert result.message == "Required value retrieved."
    assert result.data["value"] == 10


def test_execute_unsupported_action():
    agent = DummyAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"


def test_execute_empty_action():
    agent = DummyAgent()

    result = agent.execute("")

    assert result.success is False
    assert result.message == "Agent action cannot be empty."


def test_execute_non_string_action():
    agent = DummyAgent()

    result = agent.execute(123)

    assert result.success is False
    assert result.message == "Agent action must be a string."


def test_execute_missing_required_payload_value():
    agent = DummyAgent()

    result = agent.execute("required-value", {})

    assert result.success is False
    assert result.message == "Missing required payload key: value"


def test_validate_task():
    agent = DummyAgent()

    task = AgentTask(
        action="health",
    )

    agent.validate_task(task)


def test_validate_task_rejects_invalid_type():
    agent = DummyAgent()

    with pytest.raises(TypeError):
        agent.validate_task("not-a-task")


def test_validate_task_rejects_unsupported_action():
    agent = DummyAgent()

    task = AgentTask(
        action="unknown",
    )

    with pytest.raises(ValueError):
        agent.validate_task(task)


def test_get_required_payload_value():
    agent = DummyAgent()

    value = agent.get_required_payload_value(
        payload={
            "symbol": "XAUUSD",
        },
        key="symbol",
    )

    assert value == "XAUUSD"


def test_get_required_payload_value_rejects_invalid_payload():
    agent = DummyAgent()

    with pytest.raises(TypeError):
        agent.get_required_payload_value(
            payload="invalid",
            key="symbol",
        )


def test_get_required_payload_value_rejects_empty_key():
    agent = DummyAgent()

    with pytest.raises(ValueError):
        agent.get_required_payload_value(
            payload={
                "symbol": "XAUUSD",
            },
            key="",
        )


def test_get_required_payload_value_rejects_missing_key():
    agent = DummyAgent()

    with pytest.raises(ValueError):
        agent.get_required_payload_value(
            payload={},
            key="symbol",
        )


def test_success_helper():
    agent = DummyAgent()

    result = agent.success(
        message="Completed.",
        data={
            "value": 1,
        },
    )

    assert result.success is True
    assert result.message == "Completed."
    assert result.data["value"] == 1


def test_failure_helper():
    agent = DummyAgent()

    result = agent.failure(
        message="Failed.",
        data={
            "reason": "invalid",
        },
    )

    assert result.success is False
    assert result.message == "Failed."
    assert result.data["reason"] == "invalid"