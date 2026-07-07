"""
Unit tests for AQOS API health operations.
"""

import pytest

from aqos.agents import DataAgent, MarketAgent
from aqos.api import (
    API_SERVICE_NAME,
    API_VERSION,
    HealthCheck,
    HealthStatus,
    agent_health,
    agents_health,
    api_health,
    dependency_health,
    health_check,
    resolve_overall_health,
    system_health,
)


class BrokenAgent:
    name = "broken-agent"

    def execute(self, action):
        raise RuntimeError("Agent failed hard.")


def test_health_check_to_dict_minimal():
    check = health_check(
        name="database",
        status=HealthStatus.HEALTHY,
        message="Database is healthy.",
    )

    assert check.to_dict() == {
        "name": "database",
        "status": "healthy",
        "message": "Database is healthy.",
    }


def test_health_check_to_dict_with_details():
    check = health_check(
        name="market-data",
        status=HealthStatus.DEGRADED,
        message="Market data feed is delayed.",
        details={
            "delay_seconds": 30,
        },
    )

    assert check.to_dict() == {
        "name": "market-data",
        "status": "degraded",
        "message": "Market data feed is delayed.",
        "details": {
            "delay_seconds": 30,
        },
    }


def test_health_check_rejects_invalid_values():
    with pytest.raises(ValueError, match="Health check name"):
        HealthCheck(
            name="",
            status=HealthStatus.HEALTHY,
            message="Healthy.",
        )

    with pytest.raises(ValueError, match="Health check status"):
        HealthCheck(
            name="api",
            status="healthy",
            message="Healthy.",
        )

    with pytest.raises(ValueError, match="Health check message"):
        HealthCheck(
            name="api",
            status=HealthStatus.HEALTHY,
            message="",
        )

    with pytest.raises(ValueError, match="Health check details"):
        HealthCheck(
            name="api",
            status=HealthStatus.HEALTHY,
            message="Healthy.",
            details=[],
        )


def test_resolve_overall_health_healthy():
    checks = [
        health_check(name="api", status=HealthStatus.HEALTHY),
        health_check(name="agents", status=HealthStatus.HEALTHY),
    ]

    assert resolve_overall_health(checks) == HealthStatus.HEALTHY


def test_resolve_overall_health_degraded():
    checks = [
        health_check(name="api", status=HealthStatus.HEALTHY),
        health_check(name="market-data", status=HealthStatus.DEGRADED),
    ]

    assert resolve_overall_health(checks) == HealthStatus.DEGRADED


def test_resolve_overall_health_unhealthy():
    checks = [
        health_check(name="api", status=HealthStatus.HEALTHY),
        health_check(name="broker", status=HealthStatus.UNHEALTHY),
    ]

    assert resolve_overall_health(checks) == HealthStatus.UNHEALTHY


def test_api_health_response():
    response = api_health(request_id="health-request-1")
    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["status"] == "success"
    assert payload["message"] == "AQOS API is healthy."
    assert payload["data"] == {
        "service": API_SERVICE_NAME,
        "version": API_VERSION,
        "status": "healthy",
        "checks": [],
    }
    assert payload["metadata"]["request_id"] == "health-request-1"


def test_system_health_with_healthy_checks():
    response = system_health(
        checks=[
            health_check(name="api", status=HealthStatus.HEALTHY),
            health_check(name="agents", status=HealthStatus.HEALTHY),
        ],
        request_id="system-health-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "AQOS API is healthy."
    assert payload["data"]["status"] == "healthy"
    assert len(payload["data"]["checks"]) == 2
    assert payload["metadata"]["request_id"] == "system-health-1"


def test_system_health_with_degraded_checks():
    response = system_health(
        checks=[
            health_check(name="api", status=HealthStatus.HEALTHY),
            health_check(name="news", status=HealthStatus.DEGRADED),
        ],
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "AQOS API is degraded."
    assert payload["data"]["status"] == "degraded"


def test_system_health_with_unhealthy_checks():
    response = system_health(
        checks=[
            health_check(name="api", status=HealthStatus.HEALTHY),
            health_check(name="broker", status=HealthStatus.UNHEALTHY),
        ],
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["message"] == "AQOS API is unhealthy."
    assert payload["data"]["status"] == "unhealthy"


def test_dependency_health_available():
    check = dependency_health(
        name="market-data-service",
        available=True,
        details={
            "symbols": ["XAUUSD"],
        },
    )

    assert check.status == HealthStatus.HEALTHY
    assert check.message == "market-data-service is available."
    assert check.details == {
        "symbols": ["XAUUSD"],
    }


def test_dependency_health_unavailable():
    check = dependency_health(
        name="broker-service",
        available=False,
    )

    assert check.status == HealthStatus.UNHEALTHY
    assert check.message == "broker-service is unavailable."


def test_agent_health_success():
    agent = DataAgent()

    response = agent_health(
        agent,
        request_id="agent-health-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "data-agent is healthy."
    assert payload["data"]["agent"] == "data-agent"
    assert payload["data"]["success"] is True
    assert payload["metadata"]["request_id"] == "agent-health-1"


def test_agent_health_exception_failure():
    response = agent_health(
        BrokenAgent(),
        request_id="agent-health-2",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Agent health check raised an exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Agent failed hard."
    assert payload["metadata"]["request_id"] == "agent-health-2"


def test_agents_health_success():
    response = agents_health(
        agents=[
            DataAgent(),
            MarketAgent(),
        ],
        request_id="agents-health-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "AQOS API is healthy."
    assert payload["data"]["status"] == "healthy"
    assert len(payload["data"]["checks"]) == 2
    assert payload["data"]["checks"][0]["status"] == "healthy"
    assert payload["data"]["checks"][1]["status"] == "healthy"
    assert payload["metadata"]["request_id"] == "agents-health-1"


def test_agents_health_with_broken_agent():
    response = agents_health(
        agents=[
            DataAgent(),
            BrokenAgent(),
        ],
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "AQOS API is unhealthy."
    assert payload["data"]["status"] == "unhealthy"
    assert payload["data"]["checks"][1]["name"] == "broken-agent"
    assert payload["data"]["checks"][1]["status"] == "unhealthy"
    assert payload["data"]["checks"][1]["details"] == {
        "exception_type": "RuntimeError",
    }