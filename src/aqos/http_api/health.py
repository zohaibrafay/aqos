from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any

from aqos.database.engine import AqosDatabase
from aqos.database.types import database_utc_now
from aqos.http_api.config import ApiConfig
from aqos.http_api.dependencies import describe_database_readiness


AQOS_HTTP_HEALTH_VERSION = "1.0"


class HealthStatus(str, Enum):
    OK = "ok"
    NOT_READY = "not_ready"


@dataclass(frozen=True)
class LivenessReport:
    """
    Whether the API process itself is running.

    Deliberately knows nothing about the database. A liveness probe that fails
    on a database outage gets the process killed and restarted for a problem a
    restart cannot fix.
    """

    status: HealthStatus
    name: str
    version: str
    environment: str
    checked_at_utc: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "name": self.name,
            "version": self.version,
            "environment": self.environment,
            "checked_at_utc": self.checked_at_utc.isoformat(),
        }


@dataclass(frozen=True)
class ReadinessReport:
    """
    Whether the API can actually serve traffic.

    An API with a database configured but unreachable is running yet useless,
    so it reports not ready rather than ok.
    """

    status: HealthStatus
    name: str
    version: str
    environment: str
    checked_at_utc: datetime
    checks: dict[str, Any] = dataclass_field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status == HealthStatus.OK

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "ready": self.is_ready,
            "name": self.name,
            "version": self.version,
            "environment": self.environment,
            "checked_at_utc": self.checked_at_utc.isoformat(),
            "checks": self.checks,
        }


def build_liveness_report(
    config: ApiConfig,
    checked_at_utc: datetime | None = None,
) -> LivenessReport:
    return LivenessReport(
        status=HealthStatus.OK,
        name=config.name,
        version=config.version,
        environment=config.environment.value,
        checked_at_utc=checked_at_utc or database_utc_now(),
    )


def build_readiness_report(
    config: ApiConfig,
    database: AqosDatabase | None,
    checked_at_utc: datetime | None = None,
) -> ReadinessReport:
    """
    Assess readiness from what can be checked safely.

    An API with no database configured is ready: it has nothing to wait for.
    One that is configured but cannot reach MySQL is not.
    """

    database_check = describe_database_readiness(database)

    ready = (not database_check["configured"]) or bool(
        database_check["reachable"]
    )

    return ReadinessReport(
        status=HealthStatus.OK if ready else HealthStatus.NOT_READY,
        name=config.name,
        version=config.version,
        environment=config.environment.value,
        checked_at_utc=checked_at_utc or database_utc_now(),
        checks={"database": database_check},
    )


def build_system_info(
    config: ApiConfig,
    checked_at_utc: datetime | None = None,
) -> dict[str, Any]:
    """
    Describe the running API.

    Built from :meth:`ApiConfig.to_dict`, which already masks the database URL,
    so no credential can reach this endpoint.
    """

    return {
        "api": config.to_dict(),
        "reported_at_utc": (checked_at_utc or database_utc_now()).isoformat(),
    }


__all__ = [
    "AQOS_HTTP_HEALTH_VERSION",
    "HealthStatus",
    "LivenessReport",
    "ReadinessReport",
    "build_liveness_report",
    "build_readiness_report",
    "build_system_info",
]
