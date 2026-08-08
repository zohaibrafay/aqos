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
    ENV_BACKTEST_REGISTRY,
    ENV_MODEL_PROMOTION_REGISTRY,
    ENV_PREDICTION_REGISTRY,
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

from aqos.http_api.pagination import (
    AQOS_HTTP_PAGINATION_VERSION,
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    Page,
    build_page,
    validate_limit,
    validate_offset,
)

from aqos.http_api.read_schemas import (
    AQOS_HTTP_READ_SCHEMAS_VERSION,
    as_number_or_none,
    build_account_detail,
    build_account_summary,
    build_analytics_snapshot_summary,
    build_funded_rules,
    build_prediction_summary,
    build_report_detail,
    build_report_summary,
    build_promotion_summary,
    build_signal_detail,
    build_signal_event,
    build_signal_reason,
    build_signal_summary,
    parse_enum,
)

from aqos.http_api.auth_schemas import (
    AQOS_HTTP_AUTH_SCHEMAS_VERSION,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    SessionListResponse,
    SessionResponse,
    UserResponse,
)

from aqos.http_api.auth import (
    ACCOUNT_LOCKED_MESSAGE,
    AQOS_HTTP_AUTH_VERSION,
    AUTHORIZATION_HEADER,
    AuthenticatedCaller,
    ForbiddenApiError,
    INACTIVE_ACCOUNT_MESSAGE,
    INVALID_CREDENTIALS_MESSAGE,
    INVALID_TOKEN_MESSAGE,
    MISSING_TOKEN_MESSAGE,
    UnauthorizedApiError,
    extract_bearer_token,
    login,
    logout,
    resolve_caller,
    revoke_owned_session,
)

from aqos.http_api.authz import (
    AQOS_HTTP_AUTHZ_VERSION,
    CROSS_USER_FILTER_MESSAGE,
    DEFAULT_NOT_FOUND_MESSAGE,
    NOT_FOUND_MESSAGE_BY_RESOURCE,
    assert_owned_by_caller,
    get_read_only_caller,
    not_found_for,
    require_owned_record,
    resolve_scoped_user_id,
)

from aqos.http_api.routes_auth import (
    AQOS_HTTP_AUTH_ROUTES_VERSION,
    AUTH_PREFIX,
    build_auth_router,
    get_current_caller,
)

from aqos.http_api.routes_signals import (
    AQOS_HTTP_SIGNAL_ROUTES_VERSION,
    build_signals_router,
)

from aqos.http_api.routes_accounts import (
    AQOS_HTTP_ACCOUNT_ROUTES_VERSION,
    build_accounts_router,
    collect_account_constraints,
)

from aqos.http_api.routes_paper import (
    AQOS_HTTP_PAPER_ROUTES_VERSION,
    build_paper_router,
)

from aqos.http_api.routes_backtests import (
    AQOS_HTTP_BACKTEST_ROUTES_VERSION,
    build_backtests_router,
)

from aqos.http_api.routes_models import (
    AQOS_HTTP_MODEL_ROUTES_VERSION,
    PromotionState,
    build_models_router,
    build_predictions_router,
    resolve_promotion_state,
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
    "ACCOUNT_LOCKED_MESSAGE",
    "API_V1_PREFIX",
    "AQOS_API_CONFIG_VERSION",
    "AQOS_API_ERRORS_VERSION",
    "AQOS_HTTP_ACCOUNT_ROUTES_VERSION",
    "AQOS_HTTP_APP_VERSION",
    "AQOS_HTTP_AUTHZ_VERSION",
    "AQOS_HTTP_AUTH_ROUTES_VERSION",
    "AQOS_HTTP_AUTH_SCHEMAS_VERSION",
    "AQOS_HTTP_AUTH_VERSION",
    "AQOS_HTTP_BACKTEST_ROUTES_VERSION",
    "AQOS_HTTP_DEPENDENCIES_VERSION",
    "AQOS_HTTP_HEALTH_VERSION",
    "AQOS_HTTP_MIDDLEWARE_VERSION",
    "AQOS_HTTP_MODEL_ROUTES_VERSION",
    "AQOS_HTTP_PAGINATION_VERSION",
    "AQOS_HTTP_PAPER_ROUTES_VERSION",
    "AQOS_HTTP_READ_SCHEMAS_VERSION",
    "AQOS_HTTP_RESPONSES_VERSION",
    "AQOS_HTTP_ROUTES_VERSION",
    "AQOS_HTTP_SIGNAL_ROUTES_VERSION",
    "AUTHORIZATION_HEADER",
    "AUTH_PREFIX",
    "ApiConfig",
    "ApiConfigError",
    "ApiEnvironment",
    "ApiErrorBody",
    "ApiErrorCode",
    "AqosApiError",
    "AuthenticatedCaller",
    "CROSS_USER_FILTER_MESSAGE",
    "DEFAULT_API_NAME",
    "DEFAULT_API_VERSION",
    "DEFAULT_DEV_CORS_ORIGINS",
    "DEFAULT_NOT_FOUND_MESSAGE",
    "DEFAULT_PAGE_LIMIT",
    "DatabaseUnavailableApiError",
    "ENV_BACKTEST_REGISTRY",
    "ENV_MODEL_PROMOTION_REGISTRY",
    "ENV_PREDICTION_REGISTRY",
    "ForbiddenApiError",
    "GENERIC_INTERNAL_MESSAGE",
    "HTTP_STATUS_BY_ERROR_CODE",
    "HTTP_STATUS_TO_ERROR_CODE",
    "HealthStatus",
    "INACTIVE_ACCOUNT_MESSAGE",
    "INVALID_CREDENTIALS_MESSAGE",
    "INVALID_TOKEN_MESSAGE",
    "LivenessReport",
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "MAX_PAGE_LIMIT",
    "MISSING_TOKEN_MESSAGE",
    "NOT_FOUND_MESSAGE_BY_RESOURCE",
    "NotFoundApiError",
    "PROTECTED_API_ENVIRONMENTS",
    "Page",
    "PromotionState",
    "REQUEST_ID_HEADER",
    "ReadinessReport",
    "RequestIdMiddleware",
    "SafeJSONResponse",
    "SessionListResponse",
    "SessionResponse",
    "UnauthorizedApiError",
    "UserResponse",
    "ValidationApiError",
    "as_number_or_none",
    "assert_owned_by_caller",
    "build_account_detail",
    "build_account_summary",
    "build_accounts_router",
    "build_analytics_snapshot_summary",
    "build_auth_router",
    "build_backtests_router",
    "build_database",
    "build_error_payload",
    "build_funded_rules",
    "build_health_router",
    "build_internal_error_payload",
    "build_liveness_report",
    "build_models_router",
    "build_page",
    "build_paper_router",
    "build_prediction_summary",
    "build_predictions_router",
    "build_promotion_summary",
    "build_readiness_report",
    "build_report_detail",
    "build_report_summary",
    "build_signal_detail",
    "build_signal_event",
    "build_signal_reason",
    "build_signal_summary",
    "build_signals_router",
    "build_system_info",
    "build_system_router",
    "collect_account_constraints",
    "create_aqos_api_app",
    "describe_database_readiness",
    "error_code_for_status",
    "extract_bearer_token",
    "generate_request_id",
    "get_api_config",
    "get_current_caller",
    "get_database",
    "get_optional_database",
    "get_read_only_caller",
    "get_session",
    "get_write_session",
    "is_valid_request_id",
    "json_response",
    "load_api_config_from_env",
    "login",
    "logout",
    "mask_database_url",
    "mask_secret",
    "not_found_for",
    "parse_bool",
    "parse_cors_origins",
    "parse_enum",
    "read_request_id",
    "register_error_handlers",
    "register_middleware",
    "register_routes",
    "replace_non_finite",
    "require_owned_record",
    "resolve_caller",
    "resolve_promotion_state",
    "resolve_request_id",
    "resolve_scoped_user_id",
    "revoke_owned_session",
    "status_for_error_code",
    "validate_limit",
    "validate_offset",
]
