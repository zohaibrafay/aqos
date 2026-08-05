from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request

from aqos.http_api.config import ApiConfig, load_api_config_from_env
from aqos.http_api.dependencies import (
    CONFIG_STATE_KEY,
    DATABASE_STATE_KEY,
    build_database,
)
from aqos.http_api.errors import (
    ApiErrorCode,
    AqosApiError,
    build_error_payload,
    build_internal_error_payload,
)
from aqos.http_api.middleware import RequestIdMiddleware, read_request_id
from aqos.http_api.responses import json_response
from aqos.http_api.routes import register_routes


AQOS_HTTP_APP_VERSION = "1.0"

LOGGER = logging.getLogger("aqos.http_api")

#: Starlette statuses that map onto an AQOS error code.
HTTP_STATUS_TO_ERROR_CODE: dict[int, ApiErrorCode] = {
    401: ApiErrorCode.UNAUTHORIZED,
    403: ApiErrorCode.FORBIDDEN,
    404: ApiErrorCode.NOT_FOUND,
    409: ApiErrorCode.CONFLICT,
    422: ApiErrorCode.VALIDATION_ERROR,
    429: ApiErrorCode.RATE_LIMITED,
    503: ApiErrorCode.NOT_READY,
}


def error_code_for_status(status_code: int) -> ApiErrorCode:
    """An unmapped status falls back to an internal error, never to success."""

    return HTTP_STATUS_TO_ERROR_CODE.get(status_code, ApiErrorCode.INTERNAL_ERROR)


def register_error_handlers(app: FastAPI) -> None:
    """
    One error shape for every failure.

    Handlers exist for the framework's own exceptions too, so a 404 or a
    validation failure comes back in the same envelope as an AQOS error rather
    than in FastAPI's default shape.
    """

    @app.exception_handler(AqosApiError)
    async def handle_aqos_error(request: Request, exc: AqosApiError):
        return json_response(
            build_error_payload(
                code=exc.code,
                message=exc.message,
                request_id=read_request_id(request),
                details=exc.details,
            ),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ):
        return json_response(
            build_error_payload(
                code=ApiErrorCode.VALIDATION_ERROR,
                message="The request failed validation.",
                request_id=read_request_id(request),
                # Pydantic's errors describe the request the caller sent, so
                # they are safe to echo; they contain nothing server-side.
                details={"errors": jsonable_validation_errors(exc)},
            ),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(
        request: Request,
        exc: StarletteHTTPException,
    ):
        return json_response(
            build_error_payload(
                code=error_code_for_status(exc.status_code),
                message=str(exc.detail),
                request_id=read_request_id(request),
            ),
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        # Logged in full server-side, reported generically to the caller: an
        # unexpected exception can carry a connection string or a query
        # fragment, and the request id is what ties the two together.
        LOGGER.exception(
            "Unhandled API error (request_id=%s)",
            read_request_id(request),
        )

        return json_response(
            build_internal_error_payload(read_request_id(request)),
            status_code=500,
        )


def jsonable_validation_errors(exc: RequestValidationError) -> list[dict]:
    """Reduce pydantic errors to plain JSON-safe dictionaries."""

    errors: list[dict] = []

    for error in exc.errors():
        errors.append(
            {
                "location": [str(part) for part in error.get("loc", ())],
                "message": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
        )

    return errors


def register_middleware(app: FastAPI, config: ApiConfig) -> None:
    app.add_middleware(RequestIdMiddleware)

    if config.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(config.cors_origins),
            allow_credentials=not config.allows_any_origin,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )


def create_aqos_api_app(config: ApiConfig | None = None) -> FastAPI:
    """
    Build the AQOS API application.

    Deterministic and side effect free: no database connection is opened, no
    migration is run, and nothing is read from the environment unless the caller
    omits a config. That is what makes the app safe to build in a test.
    """

    resolved = config or load_api_config_from_env()

    app = FastAPI(
        title=resolved.name,
        version=resolved.version,
        debug=resolved.debug,
        # Docs stay off in production: the schema describes the whole surface
        # and there is no reason to publish it by default.
        docs_url=None if resolved.is_production else "/docs",
        redoc_url=None if resolved.is_production else "/redoc",
        openapi_url=None if resolved.is_production else "/openapi.json",
    )

    setattr(app.state, CONFIG_STATE_KEY, resolved)
    # Creating the handle does not connect; SQLAlchemy pools lazily, so the app
    # still starts and answers liveness while MySQL is down.
    setattr(app.state, DATABASE_STATE_KEY, build_database(resolved))

    register_middleware(app, resolved)
    register_error_handlers(app)
    register_routes(app, resolved)

    return app


__all__ = [
    "AQOS_HTTP_APP_VERSION",
    "HTTP_STATUS_TO_ERROR_CODE",
    "create_aqos_api_app",
    "error_code_for_status",
    "jsonable_validation_errors",
    "register_error_handlers",
    "register_middleware",
]
