from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from starlette.requests import Request

from aqos.database.engine import AqosDatabase
from aqos.http_api.config import ApiConfig
from aqos.http_api.dependencies import get_api_config, get_optional_database
from aqos.http_api.health import (
    build_liveness_report,
    build_readiness_report,
    build_system_info,
)
from aqos.http_api.middleware import read_request_id
from aqos.http_api.responses import json_response
from aqos.http_api.routes_accounts import build_accounts_router
from aqos.http_api.routes_auth import build_auth_router
from aqos.http_api.routes_backtests import build_backtests_router
from aqos.http_api.routes_paper import build_paper_router
from aqos.http_api.routes_models import (
    build_models_router,
    build_predictions_router,
)
from aqos.http_api.routes_signals import build_signals_router


AQOS_HTTP_ROUTES_VERSION = "1.0"

HEALTH_PREFIX = "/health"


def build_health_router() -> APIRouter:
    """
    Liveness and readiness.

    These sit outside the versioned prefix on purpose: an orchestrator's probes
    should not have to be rewritten when the business API version changes.
    """

    router = APIRouter(prefix=HEALTH_PREFIX, tags=["health"])

    @router.get("/live")
    def read_liveness(
        config: ApiConfig = Depends(get_api_config),
    ):
        # No database work here at all: liveness answers "is this process
        # running", and a restart cannot fix a database outage.
        return json_response(build_liveness_report(config).to_dict())

    @router.get("/ready")
    def read_readiness(
        config: ApiConfig = Depends(get_api_config),
        database: AqosDatabase | None = Depends(get_optional_database),
    ):
        report = build_readiness_report(config, database)

        return json_response(
            report.to_dict(),
            status_code=200 if report.is_ready else 503,
        )

    return router


def build_system_router() -> APIRouter:
    router = APIRouter(prefix="/system", tags=["system"])

    @router.get("/info")
    def read_system_info(
        request: Request,
        config: ApiConfig = Depends(get_api_config),
    ):
        payload = build_system_info(config)
        payload["request_id"] = read_request_id(request)

        return json_response(payload)

    return router


def register_routes(app: FastAPI, config: ApiConfig) -> None:
    """
    Attach every route the API serves.

    One place, so what the API exposes can be read off a single function rather
    than discovered by import side effects.
    """

    app.include_router(build_health_router())
    app.include_router(build_system_router(), prefix=config.api_prefix)
    app.include_router(build_auth_router(), prefix=config.api_prefix)
    app.include_router(build_signals_router(), prefix=config.api_prefix)
    app.include_router(build_accounts_router(), prefix=config.api_prefix)
    app.include_router(build_paper_router(), prefix=config.api_prefix)
    app.include_router(build_backtests_router(), prefix=config.api_prefix)
    app.include_router(build_predictions_router(), prefix=config.api_prefix)
    app.include_router(build_models_router(), prefix=config.api_prefix)


__all__ = [
    "AQOS_HTTP_ROUTES_VERSION",
    "HEALTH_PREFIX",
    "build_health_router",
    "build_system_router",
    "register_routes",
]
