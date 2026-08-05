"""
AQOS HTTP API.

The FastAPI transport layer. Kept separate from :mod:`aqos.api`, which holds
framework-independent boundary utilities shared with the CLI: mixing a web
framework into those would tie the CLI to FastAPI for no reason.

Sprint 053 establishes only the foundation — app factory, config, health,
errors, request ids and safe JSON. Business endpoints arrive in later sprints.
"""

from aqos.http_api.config import (
    API_V1_PREFIX,
    AQOS_API_CONFIG_VERSION,
    ApiConfig,
    ApiConfigError,
    ApiEnvironment,
    DEFAULT_API_NAME,
    DEFAULT_API_VERSION,
    DEFAULT_DEV_CORS_ORIGINS,
    PROTECTED_API_ENVIRONMENTS,
    load_api_config_from_env,
    mask_database_url,
    mask_secret,
    parse_bool,
    parse_cors_origins,
)

from aqos.http_api.errors import (
    AQOS_API_ERRORS_VERSION,
    ApiErrorBody,
    ApiErrorCode,
    AqosApiError,
    DatabaseUnavailableApiError,
    GENERIC_INTERNAL_MESSAGE,
    HTTP_STATUS_BY_ERROR_CODE,
    NotFoundApiError,
    ValidationApiError,
    build_error_payload,
    build_internal_error_payload,
    status_for_error_code,
)

from aqos.http_api.responses import (
    AQOS_HTTP_RESPONSES_VERSION,
    SafeJSONResponse,
    json_response,
    replace_non_finite,
)

from aqos.http_api.middleware import (
    AQOS_HTTP_MIDDLEWARE_VERSION,
    REQUEST_ID_HEADER,
    RequestIdMiddleware,
    generate_request_id,
    is_valid_request_id,
    read_request_id,
    resolve_request_id,
)

from aqos.http_api.dependencies import (
    AQOS_HTTP_DEPENDENCIES_VERSION,
    build_database,
    describe_database_readiness,
    get_api_config,
    get_database,
    get_optional_database,
    get_session,
    get_write_session,
)

from aqos.http_api.health import (
    AQOS_HTTP_HEALTH_VERSION,
    HealthStatus,
    LivenessReport,
    ReadinessReport,
    build_liveness_report,
    build_readiness_report,
    build_system_info,
)

from aqos.http_api.routes import (
    AQOS_HTTP_ROUTES_VERSION,
    build_health_router,
    build_system_router,
    register_routes,
)

from aqos.http_api.app import (
    AQOS_HTTP_APP_VERSION,
    HTTP_STATUS_TO_ERROR_CODE,
    create_aqos_api_app,
    error_code_for_status,
    register_error_handlers,
    register_middleware,
)

__all__ = [
    "AQOS_API_CONFIG_VERSION",
    "AQOS_API_ERRORS_VERSION",
    "AQOS_HTTP_APP_VERSION",
    "AQOS_HTTP_DEPENDENCIES_VERSION",
    "AQOS_HTTP_HEALTH_VERSION",
    "AQOS_HTTP_MIDDLEWARE_VERSION",
    "AQOS_HTTP_RESPONSES_VERSION",
    "AQOS_HTTP_ROUTES_VERSION",
    "API_V1_PREFIX",
    "ApiConfig",
    "ApiConfigError",
    "ApiEnvironment",
    "ApiErrorBody",
    "ApiErrorCode",
    "AqosApiError",
    "DEFAULT_API_NAME",
    "DEFAULT_API_VERSION",
    "DEFAULT_DEV_CORS_ORIGINS",
    "DatabaseUnavailableApiError",
    "GENERIC_INTERNAL_MESSAGE",
    "HTTP_STATUS_BY_ERROR_CODE",
    "HTTP_STATUS_TO_ERROR_CODE",
    "HealthStatus",
    "LivenessReport",
    "NotFoundApiError",
    "PROTECTED_API_ENVIRONMENTS",
    "REQUEST_ID_HEADER",
    "ReadinessReport",
    "RequestIdMiddleware",
    "SafeJSONResponse",
    "ValidationApiError",
    "build_database",
    "build_error_payload",
    "build_health_router",
    "build_internal_error_payload",
    "build_liveness_report",
    "build_readiness_report",
    "build_system_info",
    "build_system_router",
    "create_aqos_api_app",
    "describe_database_readiness",
    "error_code_for_status",
    "generate_request_id",
    "get_api_config",
    "get_database",
    "get_optional_database",
    "get_session",
    "get_write_session",
    "is_valid_request_id",
    "json_response",
    "load_api_config_from_env",
    "mask_database_url",
    "mask_secret",
    "parse_bool",
    "parse_cors_origins",
    "read_request_id",
    "register_error_handlers",
    "register_middleware",
    "register_routes",
    "replace_non_finite",
    "resolve_request_id",
    "status_for_error_code",
]
