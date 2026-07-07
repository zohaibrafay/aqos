"""
AQOS API health operations.

This module provides framework-independent health response helpers.
It can later be connected to FastAPI, Flask, Django, CLI, or dashboard layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.api.responses import ApiResponse, api_failure, api_success, exception_failure


API_SERVICE_NAME = "aqos-api"
API_VERSION = "v0.15.0-dev"


class HealthStatus(str, Enum):
    """Supported health statuses."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass(frozen=True)
class HealthCheck:
    """
    Single health check result.
    """

    name: str
    status: HealthStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Health check name must be a non-empty string.")

        if not isinstance(self.status, HealthStatus):
            raise ValueError("Health check status must be a HealthStatus.")

        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Health check message must be a non-empty string.")

        if not isinstance(self.details, dict):
            raise ValueError("Health check details must be a dictionary.")

    def to_dict(self) -> dict[str, Any]:
        """Convert health check to dictionary."""
        payload: dict[str, Any] = {
            "name": self.name.strip(),
            "status": self.status.value,
            "message": self.message.strip(),
        }

        if self.details:
            payload["details"] = self.details

        return payload


def health_check(
    *,
    name: str,
    status: HealthStatus = HealthStatus.HEALTHY,
    message: str = "Health check passed.",
    details: dict[str, Any] | None = None,
) -> HealthCheck:
    """Create a health check object."""
    return HealthCheck(
        name=name,
        status=status,
        message=message,
        details=details or {},
    )


def resolve_overall_health(checks: list[HealthCheck]) -> HealthStatus:
    """Resolve overall health status from individual checks."""
    if any(check.status == HealthStatus.UNHEALTHY for check in checks):
        return HealthStatus.UNHEALTHY

    if any(check.status == HealthStatus.DEGRADED for check in checks):
        return HealthStatus.DEGRADED

    return HealthStatus.HEALTHY


def api_health(
    *,
    request_id: str | None = None,
) -> ApiResponse:
    """Return basic API health status."""
    return api_success(
        message="AQOS API is healthy.",
        data={
            "service": API_SERVICE_NAME,
            "version": API_VERSION,
            "status": HealthStatus.HEALTHY.value,
            "checks": [],
        },
        request_id=request_id,
    )


def system_health(
    *,
    checks: list[HealthCheck] | None = None,
    request_id: str | None = None,
) -> ApiResponse:
    """Return system health status from optional health checks."""
    resolved_checks = checks or []
    overall_status = resolve_overall_health(resolved_checks)

    data = {
        "service": API_SERVICE_NAME,
        "version": API_VERSION,
        "status": overall_status.value,
        "checks": [check.to_dict() for check in resolved_checks],
    }

    if overall_status == HealthStatus.UNHEALTHY:
        return api_failure(
            message="AQOS API is unhealthy.",
            data=data,
            request_id=request_id,
        )

    if overall_status == HealthStatus.DEGRADED:
        return api_success(
            message="AQOS API is degraded.",
            data=data,
            request_id=request_id,
        )

    return api_success(
        message="AQOS API is healthy.",
        data=data,
        request_id=request_id,
    )


def dependency_health(
    *,
    name: str,
    available: bool,
    details: dict[str, Any] | None = None,
) -> HealthCheck:
    """Create a dependency health check."""
    if available:
        return health_check(
            name=name,
            status=HealthStatus.HEALTHY,
            message=f"{name} is available.",
            details=details,
        )

    return health_check(
        name=name,
        status=HealthStatus.UNHEALTHY,
        message=f"{name} is unavailable.",
        details=details,
    )


def agent_health(
    agent: Any,
    *,
    request_id: str | None = None,
) -> ApiResponse:
    """
    Run an agent health check and convert it into an API response.

    The agent is expected to expose an execute("health") method.
    """
    try:
        result = agent.execute("health")

        data = {
            "agent": getattr(agent, "name", agent.__class__.__name__),
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "metadata": result.metadata,
        }

        if result.success:
            return api_success(
                message=f"{data['agent']} is healthy.",
                data=data,
                request_id=request_id,
            )

        return api_failure(
            message=f"{data['agent']} health check failed.",
            data=data,
            request_id=request_id,
        )

    except Exception as exception:
        return exception_failure(
            exception,
            message="Agent health check raised an exception.",
            request_id=request_id,
        )


def agents_health(
    agents: list[Any],
    *,
    request_id: str | None = None,
) -> ApiResponse:
    """Run health checks for multiple agents."""
    checks: list[HealthCheck] = []

    for agent in agents:
        try:
            result = agent.execute("health")
            agent_name = getattr(agent, "name", agent.__class__.__name__)

            checks.append(
                health_check(
                    name=agent_name,
                    status=(
                        HealthStatus.HEALTHY
                        if result.success
                        else HealthStatus.UNHEALTHY
                    ),
                    message=result.message,
                    details={
                        "data": result.data,
                        "metadata": result.metadata,
                    },
                )
            )
        except Exception as exception:
            checks.append(
                health_check(
                    name=getattr(agent, "name", agent.__class__.__name__),
                    status=HealthStatus.UNHEALTHY,
                    message=str(exception),
                    details={
                        "exception_type": exception.__class__.__name__,
                    },
                )
            )

    return system_health(
        checks=checks,
        request_id=request_id,
    )