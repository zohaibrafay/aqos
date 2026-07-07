"""
Unit tests for AQOS CLI health commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliHealthRequest,
    build_health_cli_output,
    cli_agent_health,
    cli_agents_health,
    cli_api_health,
    cli_dependency_health,
    cli_system_health,
    execute_health_operation,
)


def fake_api_health(request_id=None):
    return api_success(
        message="API health loaded.",
        data={
            "service": "aqos-api",
            "status": "healthy",
        },
        request_id=request_id,
    )


def fake_system_health(request_id=None):
    return api_success(
        message="System health loaded.",
        data={
            "status": "healthy",
            "checks": 3,
        },
        request_id=request_id,
    )


def fake_dependency_health(
    name,
    status="healthy",
    message="Dependency is healthy.",
    details=None,
    request_id=None,
):
    return api_success(
        message="Dependency health loaded.",
        data={
            "name": name,
            "status": status,
            "message": message,
            "details": details or {},
        },
        request_id=request_id,
    )


def fake_agent_health(agent, request_id=None):
    return api_success(
        message="Agent health loaded.",
        data={
            "agent": agent.name,
            "status": "healthy",
        },
        request_id=request_id,
    )


def fake_agents_health(agents, request_id=None):
    return api_success(
        message="Agents health loaded.",
        data={
            "count": len(agents),
            "status": "healthy",
        },
        request_id=request_id,
    )


def fake_failure_health(request_id=None):
    return api_failure(
        message="Health failed.",
        request_id=request_id,
    )


def test_cli_health_request_accepts_valid_values():
    request = CliHealthRequest(
        output_format="pretty-json",
        include_metadata=True,
        request_id="request-1",
    )

    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "request-1"


def test_cli_health_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        CliHealthRequest(output_format="bad")

    with pytest.raises(ValueError):
        CliHealthRequest(include_metadata="yes")

    with pytest.raises(ValueError):
        CliHealthRequest(request_id="")


def test_execute_health_operation_with_request_id():
    response = execute_health_operation(
        fake_api_health,
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"


def test_execute_health_operation_rejects_non_callable():
    with pytest.raises(ValueError):
        execute_health_operation(
            "not-callable",
            request_id="request-1",
        )


def test_build_health_cli_output_success():
    response = fake_api_health(
        request_id="request-1",
    )

    cli_output = build_health_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: API health loaded." in cli_output.output
    assert "service: aqos-api" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_health_cli_output_failure():
    response = fake_failure_health()

    cli_output = build_health_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Health failed."


def test_cli_api_health_text_success():
    cli_output = cli_api_health(
        output_format="text",
        request_id="api-health-1",
        operation=fake_api_health,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: API health loaded." in cli_output.output
    assert "service: aqos-api" in cli_output.output
    assert "status: healthy" in cli_output.output


def test_cli_api_health_json_success():
    cli_output = cli_api_health(
        output_format="json",
        operation=fake_api_health,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["status"] == "healthy"
    assert "metadata" not in payload


def test_cli_system_health_success():
    cli_output = cli_system_health(
        output_format="text",
        operation=fake_system_health,
    )

    assert cli_output.success is True
    assert "SUCCESS: System health loaded." in cli_output.output
    assert "checks: 3" in cli_output.output


def test_cli_dependency_health_success():
    cli_output = cli_dependency_health(
        name="database",
        status="healthy",
        message="Database connection is healthy.",
        details={
            "latency_ms": 2,
        },
        output_format="pretty-json",
        operation=fake_dependency_health,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["data"]["name"] == "database"
    assert payload["data"]["status"] == "healthy"
    assert payload["data"]["details"] == {
        "latency_ms": 2,
    }


def test_cli_dependency_health_rejects_invalid_values():
    with pytest.raises(ValueError):
        cli_dependency_health(
            name="",
            operation=fake_dependency_health,
        )

    with pytest.raises(ValueError):
        cli_dependency_health(
            name="database",
            status="",
            operation=fake_dependency_health,
        )

    with pytest.raises(ValueError):
        cli_dependency_health(
            name="database",
            details=[],
            operation=fake_dependency_health,
        )


def test_cli_agent_health_success():
    agent = SimpleNamespace(name="market-agent")

    cli_output = cli_agent_health(
        agent=agent,
        output_format="text",
        operation=fake_agent_health,
    )

    assert cli_output.success is True
    assert "SUCCESS: Agent health loaded." in cli_output.output
    assert "agent: market-agent" in cli_output.output


def test_cli_agent_health_rejects_missing_agent():
    with pytest.raises(ValueError):
        cli_agent_health(
            agent=None,
            operation=fake_agent_health,
        )


def test_cli_agents_health_success():
    agents = [
        SimpleNamespace(name="market-agent"),
        SimpleNamespace(name="strategy-agent"),
    ]

    cli_output = cli_agents_health(
        agents=agents,
        output_format="text",
        operation=fake_agents_health,
    )

    assert cli_output.success is True
    assert "SUCCESS: Agents health loaded." in cli_output.output
    assert "count: 2" in cli_output.output
    assert "status: healthy" in cli_output.output


def test_cli_agents_health_rejects_invalid_agents():
    with pytest.raises(ValueError):
        cli_agents_health(
            agents=[],
            operation=fake_agents_health,
        )

    with pytest.raises(ValueError):
        cli_agents_health(
            agents="bad",
            operation=fake_agents_health,
        )