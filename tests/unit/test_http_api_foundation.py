"""Unit tests for the FastAPI backend foundation."""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from aqos.http_api.app import (
    create_aqos_api_app,
    error_code_for_status,
)
from aqos.http_api.config import (
    API_V1_PREFIX,
    ApiConfig,
    ApiConfigError,
    ApiEnvironment,
    DEFAULT_DEV_CORS_ORIGINS,
    ENV_API_CORS_ORIGINS,
    ENV_API_DEBUG,
    ENV_API_ENV,
    ENV_API_NAME,
    ENV_API_VERSION,
    ENV_DB_URL,
    load_api_config_from_env,
    mask_database_url,
    mask_secret,
    parse_bool,
    parse_cors_origins,
)
from aqos.http_api.errors import (
    ApiErrorCode,
    AqosApiError,
    DatabaseUnavailableApiError,
    GENERIC_INTERNAL_MESSAGE,
    NotFoundApiError,
    ValidationApiError,
    build_error_payload,
    build_internal_error_payload,
    status_for_error_code,
)
from aqos.http_api.middleware import (
    REQUEST_ID_HEADER,
    generate_request_id,
    is_valid_request_id,
    resolve_request_id,
)
from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.authz import get_read_only_caller
from aqos.http_api.responses import SafeJSONResponse, replace_non_finite
from aqos.users.models import (
    UserProfile,
    UserRole,
    UserSession,
    UserStatus,
)


SECRET_DB_URL = "mysql+pymysql://aqos:sup3rs3cret@db.internal:3306/aqos"


def build_config(**overrides) -> ApiConfig:
    payload = {"environment": ApiEnvironment.TEST}
    payload.update(overrides)

    return ApiConfig(**payload)


def build_client(**overrides) -> TestClient:
    return TestClient(create_aqos_api_app(build_config(**overrides)))


def build_stub_caller() -> AuthenticatedCaller:
    """
    A caller for tests that have no database.

    This suite is about routing and serialization, not about authentication;
    the real token path is proven end to end by the MySQL protection suite.
    """

    now = datetime(2026, 1, 1, 0, 0, 0)

    return AuthenticatedCaller(
        user=UserProfile(
            user_id="user_stub",
            email="stub@example.com",
            display_name="Stub",
            role=UserRole.TRADER,
            status=UserStatus.ACTIVE,
            created_at_utc=now,
            updated_at_utc=now,
        ),
        session=UserSession(
            session_id="session_stub",
            user_id="user_stub",
            token_hash="a" * 64,
            created_at_utc=now,
            expires_at_utc=now + timedelta(hours=1),
        ),
    )


def build_authenticated_client(**overrides) -> TestClient:
    app = create_aqos_api_app(build_config(**overrides))
    app.dependency_overrides[get_read_only_caller] = build_stub_caller

    return TestClient(app)


def collect_route_paths(app) -> set[str]:
    """
    Every path the app serves.

    Read from the OpenAPI schema rather than ``app.routes``: FastAPI wraps
    included routers in objects that expose no path, and the schema is the
    surface a client actually sees.
    """

    return set(app.openapi()["paths"])


class TestAppFactory:
    def test_the_factory_builds_an_app(self) -> None:
        app = create_aqos_api_app(build_config())

        assert app.title == "AQOS API"

    def test_the_factory_is_deterministic(self) -> None:
        """Two apps from one config expose the same surface."""

        config = build_config()

        first = collect_route_paths(create_aqos_api_app(config))
        second = collect_route_paths(create_aqos_api_app(config))

        assert first == second

    def test_building_an_app_opens_no_connection(self) -> None:
        """
        A database handle is created but never dialled.

        The app has to start while MySQL is down, otherwise a database outage
        also takes out the liveness probe.
        """

        app = create_aqos_api_app(
            build_config(database_url="mysql+pymysql://u:p@127.0.0.1:1/none")
        )

        assert app.state.aqos_database is not None

    def test_an_app_without_a_database_has_none(self) -> None:
        app = create_aqos_api_app(build_config())

        assert app.state.aqos_database is None

    def test_docs_are_served_outside_production(self) -> None:
        app = create_aqos_api_app(build_config())

        assert app.docs_url == "/docs"

    def test_docs_are_withheld_in_production(self) -> None:
        """The schema describes the whole surface; do not publish it by default."""

        app = create_aqos_api_app(
            ApiConfig(
                environment=ApiEnvironment.PRODUCTION,
                cors_origins=("https://app.example.com",),
            )
        )

        assert app.docs_url is None
        assert app.openapi_url is None


class TestVersioningAndRoutes:
    def test_health_sits_outside_the_version_prefix(self) -> None:
        """Probes should survive an API version bump."""

        paths = collect_route_paths(create_aqos_api_app(build_config()))

        assert "/health/live" in paths
        assert "/health/ready" in paths

    def test_system_info_sits_behind_the_version_prefix(self) -> None:
        paths = collect_route_paths(create_aqos_api_app(build_config()))

        assert f"{API_V1_PREFIX}/system/info" in paths

    def test_the_exposed_surface_is_exactly_this(self) -> None:
        """
        An allow list, so an unintended route fails rather than sneaks in.

        Endpoints arrive with their own sprints; adding one here is a deliberate
        act that has to be written down.
        """

        assert collect_route_paths(create_aqos_api_app(build_config())) == {
            "/health/live",
            "/health/ready",
            f"{API_V1_PREFIX}/system/info",
            f"{API_V1_PREFIX}/signals",
            f"{API_V1_PREFIX}/signals/{{signal_id}}",
            f"{API_V1_PREFIX}/signals/{{signal_id}}/events",
            f"{API_V1_PREFIX}/signals/{{signal_id}}/reasons",
            f"{API_V1_PREFIX}/predictions",
            f"{API_V1_PREFIX}/predictions/{{prediction_id}}",
            f"{API_V1_PREFIX}/models/promotions",
            f"{API_V1_PREFIX}/models/{{model_id}}/promotion-status",
            f"{API_V1_PREFIX}/accounts",
            f"{API_V1_PREFIX}/accounts/{{account_id}}",
            f"{API_V1_PREFIX}/accounts/{{account_id}}/execution-constraints",
            f"{API_V1_PREFIX}/accounts/{{account_id}}/funded-rules",
            f"{API_V1_PREFIX}/accounts/{{account_id}}/analytics",
            f"{API_V1_PREFIX}/accounts/{{account_id}}/analytics/snapshots",
            f"{API_V1_PREFIX}/accounts/{{account_id}}/reports",
            f"{API_V1_PREFIX}/accounts/{{account_id}}/reports/{{report_id}}",
            f"{API_V1_PREFIX}/paper/sessions",
            f"{API_V1_PREFIX}/paper/sessions/{{session_id}}",
            f"{API_V1_PREFIX}/paper/sessions/{{session_id}}/result",
            f"{API_V1_PREFIX}/paper/sessions/{{session_id}}/orders",
            f"{API_V1_PREFIX}/paper/sessions/{{session_id}}/fills",
            f"{API_V1_PREFIX}/paper/sessions/{{session_id}}/positions",
            f"{API_V1_PREFIX}/paper/sessions/{{session_id}}/trades",
            f"{API_V1_PREFIX}/paper/sessions/{{session_id}}/decisions",
            f"{API_V1_PREFIX}/backtests",
            f"{API_V1_PREFIX}/backtests/{{backtest_id}}",
            f"{API_V1_PREFIX}/backtests/{{backtest_id}}/trades",
            f"{API_V1_PREFIX}/backtests/{{backtest_id}}/orders",
            f"{API_V1_PREFIX}/backtests/{{backtest_id}}/equity",
            f"{API_V1_PREFIX}/auth/login",
            f"{API_V1_PREFIX}/auth/logout",
            f"{API_V1_PREFIX}/auth/logout-all",
            f"{API_V1_PREFIX}/auth/me",
            f"{API_V1_PREFIX}/auth/sessions",
            f"{API_V1_PREFIX}/auth/sessions/{{session_id}}/revoke",
        }

    def test_only_auth_accepts_a_write_verb(self) -> None:
        """
        The business surface stays read-only.

        Sprint 057 adds POST for authentication only — logging in, logging out
        and revoking a session. Nothing that reads trading data may mutate, so
        any new write verb outside ``/auth`` has to be a deliberate decision
        recorded here.
        """

        app = create_aqos_api_app(build_config())
        write_verbs = {"post", "put", "patch", "delete"}
        offenders = [
            path
            for path, operations in app.openapi()["paths"].items()
            if (write_verbs & set(operations))
            and f"{API_V1_PREFIX}/auth" not in path
        ]

        assert offenders == []

    def test_no_business_endpoint_mutates(self) -> None:
        """Signals, accounts, paper and backtests are read-only throughout."""

        app = create_aqos_api_app(build_config())

        for path, operations in app.openapi()["paths"].items():
            if f"{API_V1_PREFIX}/auth" in path:
                continue

            assert set(operations) == {"get"}, path

    def test_the_prefix_can_be_moved(self) -> None:
        app = create_aqos_api_app(build_config(api_prefix="/api/v2"))
        paths = collect_route_paths(app)

        assert "/api/v2/system/info" in paths


class TestLiveness:
    def test_live_returns_ok_without_a_database(self) -> None:
        response = build_client().get("/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_live_ignores_an_unreachable_database(self) -> None:
        """A restart cannot fix a database outage, so liveness must not fail."""

        client = build_client(
            database_url="mysql+pymysql://u:p@127.0.0.1:1/none"
        )
        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_live_reports_the_environment(self) -> None:
        payload = build_client().get("/health/live").json()

        assert payload["environment"] == "test"
        assert payload["checked_at_utc"]


class TestReadiness:
    def test_ready_without_a_database_is_ok(self) -> None:
        """Nothing configured means nothing to wait for."""

        response = build_client().get("/health/ready")

        assert response.status_code == 200

        payload = response.json()

        assert payload["ready"] is True
        assert payload["checks"]["database"]["configured"] is False
        assert payload["checks"]["database"]["reachable"] is None

    def test_ready_is_503_when_the_database_is_unreachable(self) -> None:
        client = build_client(
            database_url="mysql+pymysql://u:p@127.0.0.1:1/none"
        )
        response = client.get("/health/ready")

        assert response.status_code == 503

        payload = response.json()

        assert payload["ready"] is False
        assert payload["status"] == "not_ready"
        assert payload["checks"]["database"]["configured"] is True
        assert payload["checks"]["database"]["reachable"] is False

    def test_readiness_never_leaks_the_connection_details(self) -> None:
        """A readiness probe is often public; it needs none of this."""

        client = build_client(database_url=SECRET_DB_URL)
        body = client.get("/health/ready").text

        for secret in ("sup3rs3cret", "db.internal", "aqos:"):
            assert secret not in body


class TestSystemInfo:
    def test_system_info_is_not_public(self) -> None:
        """
        It reports deployment configuration, so it needs a caller.

        The response names the environment, the debug flag and the allowed
        origins, which is exactly the kind of detail an anonymous client should
        not be able to enumerate. This app has no database, so the refusal is
        "no caller can be resolved" rather than a 401; either way nothing is
        served. The 401 itself is proven against real MySQL in the protection
        suite.
        """

        response = build_client().get(f"{API_V1_PREFIX}/system/info")

        assert response.status_code >= 400
        assert "api" not in response.json()

    def test_system_info_masks_the_database_url(self) -> None:
        client = build_authenticated_client(database_url=SECRET_DB_URL)
        payload = client.get(f"{API_V1_PREFIX}/system/info").json()

        assert payload["api"]["has_database"] is True
        assert payload["api"]["database_url"] == "mysql+pymysql://***"

    def test_system_info_carries_the_request_id(self) -> None:
        response = build_authenticated_client().get(
            f"{API_V1_PREFIX}/system/info"
        )

        assert response.json()["request_id"] == response.headers[
            REQUEST_ID_HEADER
        ]


class TestApiConfig:
    def test_to_dict_never_carries_a_credential(self) -> None:
        payload = build_config(database_url=SECRET_DB_URL).to_dict()
        rendered = json.dumps(payload)

        assert "sup3rs3cret" not in rendered
        assert "db.internal" not in rendered
        assert payload["database_url"] == "mysql+pymysql://***"

    def test_an_absent_database_stays_none(self) -> None:
        """Unset and hidden must not look the same."""

        payload = build_config().to_dict()

        assert payload["database_url"] is None
        assert payload["has_database"] is False

    @pytest.mark.parametrize(
        "url, expected",
        [
            (None, None),
            ("", None),
            ("   ", None),
            ("mysql+pymysql://u:p@h/db", "mysql+pymysql://***"),
            ("no-scheme", "unknown://***"),
        ],
    )
    def test_mask_database_url(self, url, expected) -> None:
        assert mask_database_url(url) == expected

    @pytest.mark.parametrize(
        "value, expected",
        [(None, None), ("", None), ("   ", None), ("hunter2", "***")],
    )
    def test_mask_secret(self, value, expected) -> None:
        assert mask_secret(value) == expected

    def test_an_empty_name_is_rejected(self) -> None:
        with pytest.raises(ApiConfigError, match="name cannot be empty"):
            build_config(name="  ")

    def test_a_prefix_must_be_rooted(self) -> None:
        with pytest.raises(ApiConfigError, match="must start with"):
            build_config(api_prefix="api/v1")

    @pytest.mark.parametrize(
        "value, expected",
        [("1", True), ("true", True), ("ON", True), ("0", False), ("no", False)],
    )
    def test_parse_bool(self, value, expected) -> None:
        assert parse_bool(value) is expected

    def test_parse_bool_rejects_nonsense(self) -> None:
        with pytest.raises(ApiConfigError, match="as a boolean"):
            parse_bool("maybe")

    def test_parse_cors_origins_splits_and_trims(self) -> None:
        assert parse_cors_origins(" a.com , b.com ,, ") == ("a.com", "b.com")


class TestCorsConfiguration:
    def test_development_gets_a_local_default(self) -> None:
        config = load_api_config_from_env({ENV_API_ENV: "development"})

        assert config.cors_origins == DEFAULT_DEV_CORS_ORIGINS
        assert config.allows_any_origin is False

    def test_production_inherits_no_default(self) -> None:
        """A browser-facing API must not be opened up by omission."""

        config = load_api_config_from_env({ENV_API_ENV: "production"})

        assert config.cors_origins == ()

    def test_a_wildcard_is_refused_in_production(self) -> None:
        with pytest.raises(ApiConfigError, match="not allowed in production"):
            ApiConfig(
                environment=ApiEnvironment.PRODUCTION,
                cors_origins=("*",),
            )

    def test_a_wildcard_is_refused_in_staging(self) -> None:
        with pytest.raises(ApiConfigError, match="not allowed in staging"):
            ApiConfig(
                environment=ApiEnvironment.STAGING,
                cors_origins=("*",),
            )

    def test_a_wildcard_is_allowed_in_development(self) -> None:
        config = ApiConfig(
            environment=ApiEnvironment.DEVELOPMENT,
            cors_origins=("*",),
        )

        assert config.allows_any_origin is True

    def test_configured_origins_are_honoured(self) -> None:
        client = build_client(cors_origins=("https://app.example.com",))
        response = client.get(
            "/health/live",
            headers={"Origin": "https://app.example.com"},
        )

        assert response.headers["access-control-allow-origin"] == (
            "https://app.example.com"
        )

    def test_an_unlisted_origin_is_not_allowed(self) -> None:
        client = build_client(cors_origins=("https://app.example.com",))
        response = client.get(
            "/health/live",
            headers={"Origin": "https://evil.example.com"},
        )

        assert "access-control-allow-origin" not in response.headers


class TestEnvironmentLoading:
    def test_values_are_read_from_the_environment(self) -> None:
        config = load_api_config_from_env(
            {
                ENV_API_ENV: "staging",
                ENV_API_NAME: "AQOS Staging",
                ENV_API_VERSION: "9.9.9",
                ENV_API_DEBUG: "true",
                ENV_API_CORS_ORIGINS: "https://a.example.com,https://b.example.com",
                ENV_DB_URL: SECRET_DB_URL,
            }
        )

        assert config.environment == ApiEnvironment.STAGING
        assert config.name == "AQOS Staging"
        assert config.version == "9.9.9"
        assert config.debug is True
        assert len(config.cors_origins) == 2
        assert config.has_database is True

    def test_an_unknown_environment_is_refused(self) -> None:
        with pytest.raises(ApiConfigError, match="Unknown AQOS_API_ENV"):
            load_api_config_from_env({ENV_API_ENV: "prod-ish"})

    def test_an_empty_environment_defaults_to_development(self) -> None:
        assert load_api_config_from_env({}).environment == (
            ApiEnvironment.DEVELOPMENT
        )


class TestRequestId:
    def test_a_request_id_is_generated(self) -> None:
        response = build_client().get("/health/live")

        assert is_valid_request_id(response.headers[REQUEST_ID_HEADER])

    def test_a_valid_incoming_id_is_honoured(self) -> None:
        """A trace should be able to span services."""

        supplied = "trace-0123456789"
        response = build_client().get(
            "/health/live",
            headers={REQUEST_ID_HEADER: supplied},
        )

        assert response.headers[REQUEST_ID_HEADER] == supplied

    @pytest.mark.parametrize(
        "supplied",
        ["short", "", "has spaces here", "x" * 200, "<script>alert(1)</script>"],
    )
    def test_an_unsafe_incoming_id_is_replaced(self, supplied: str) -> None:
        """The id is echoed into headers and payloads, so it cannot be trusted."""

        response = build_client().get(
            "/health/live",
            headers={REQUEST_ID_HEADER: supplied},
        )
        returned = response.headers[REQUEST_ID_HEADER]

        assert returned != supplied
        assert is_valid_request_id(returned)

    def test_ids_differ_between_requests(self) -> None:
        client = build_client()

        first = client.get("/health/live").headers[REQUEST_ID_HEADER]
        second = client.get("/health/live").headers[REQUEST_ID_HEADER]

        assert first != second

    def test_generated_ids_are_valid(self) -> None:
        assert is_valid_request_id(generate_request_id())

    def test_resolve_keeps_a_good_id(self) -> None:
        assert resolve_request_id("trace-0123456789") == "trace-0123456789"


class TestErrorContract:
    def test_a_not_found_uses_the_standard_shape(self) -> None:
        response = build_client().get(f"{API_V1_PREFIX}/nope")
        payload = response.json()

        assert response.status_code == 404
        assert set(payload) == {"error"}
        assert set(payload["error"]) == {
            "code",
            "message",
            "details",
            "request_id",
        }
        assert payload["error"]["code"] == "not_found"

    def test_the_error_carries_the_request_id(self) -> None:
        response = build_client().get(f"{API_V1_PREFIX}/nope")

        assert response.json()["error"]["request_id"] == response.headers[
            REQUEST_ID_HEADER
        ]

    def test_an_unexpected_error_is_reported_generically(self) -> None:
        """
        An exception can carry a connection string or a query fragment.

        The caller gets a fixed message and a request id; the detail stays in
        the server log.
        """

        config = build_config()
        app = create_aqos_api_app(config)
        router = APIRouter()

        @router.get("/boom")
        def boom():
            raise RuntimeError(
                f"connection failed for {SECRET_DB_URL} while running SELECT"
            )

        app.include_router(router, prefix=config.api_prefix)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"{API_V1_PREFIX}/boom")
        body = response.text

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "internal_error"
        assert response.json()["error"]["message"] == GENERIC_INTERNAL_MESSAGE
        assert "sup3rs3cret" not in body
        assert "SELECT" not in body
        assert "Traceback" not in body
        assert "RuntimeError" not in body

    def test_an_aqos_error_keeps_its_code_and_details(self) -> None:
        config = build_config()
        app = create_aqos_api_app(config)
        router = APIRouter()

        @router.get("/missing")
        def missing():
            raise NotFoundApiError(
                "Account was not found.",
                details={"account_id": "account_1"},
            )

        app.include_router(router, prefix=config.api_prefix)

        response = TestClient(app).get(f"{API_V1_PREFIX}/missing")
        payload = response.json()

        assert response.status_code == 404
        assert payload["error"]["code"] == "not_found"
        assert payload["error"]["details"] == {"account_id": "account_1"}

    def test_a_database_unavailable_error_is_503(self) -> None:
        assert DatabaseUnavailableApiError().status_code == 503

    def test_a_validation_error_is_422(self) -> None:
        assert ValidationApiError("bad").status_code == 422

    @pytest.mark.parametrize(
        "code, status",
        [
            (ApiErrorCode.NOT_FOUND, 404),
            (ApiErrorCode.VALIDATION_ERROR, 422),
            (ApiErrorCode.INTERNAL_ERROR, 500),
            (ApiErrorCode.DATABASE_UNAVAILABLE, 503),
        ],
    )
    def test_status_for_error_code(self, code, status) -> None:
        assert status_for_error_code(code) == status

    def test_an_unmapped_status_falls_back_to_internal(self) -> None:
        """A new status must never read as success."""

        assert error_code_for_status(418) == ApiErrorCode.INTERNAL_ERROR

    def test_the_payload_builders_match_the_contract(self) -> None:
        payload = build_error_payload(
            code=ApiErrorCode.CONFLICT,
            message="Already exists.",
            request_id="trace-0123456789",
            details={"field": "email"},
        )

        assert payload["error"]["code"] == "conflict"
        assert payload["error"]["request_id"] == "trace-0123456789"

    def test_the_internal_payload_carries_no_details(self) -> None:
        payload = build_internal_error_payload("trace-0123456789")

        assert payload["error"]["details"] == {}
        assert payload["error"]["message"] == GENERIC_INTERNAL_MESSAGE

    def test_a_custom_status_is_respected(self) -> None:
        error = AqosApiError(
            ApiErrorCode.CONFLICT,
            "Nope.",
            status_code=451,
        )

        assert error.status_code == 451


class TestJsonSafety:
    """
    Sprint 052 banned Infinity and NaN from stored payloads.

    The wire format has the same requirement: neither token is JSON, so a
    browser or strict client cannot parse a response containing one.
    """

    @pytest.mark.parametrize(
        "value",
        [math.inf, -math.inf, math.nan],
    )
    def test_non_finite_floats_become_null(self, value: float) -> None:
        assert replace_non_finite(value) is None

    def test_finite_floats_survive(self) -> None:
        assert replace_non_finite(2.5) == 2.5

    def test_booleans_are_not_treated_as_numbers(self) -> None:
        assert replace_non_finite(True) is True
        assert replace_non_finite(False) is False

    def test_nested_structures_are_walked(self) -> None:
        payload = {
            "a": [1.0, math.inf, {"b": math.nan}],
            "c": {"d": (-math.inf, 3.0)},
        }

        assert replace_non_finite(payload) == {
            "a": [1.0, None, {"b": None}],
            "c": {"d": [None, 3.0]},
        }

    def test_the_response_renders_valid_json(self) -> None:
        rendered = SafeJSONResponse(
            content={"profit_factor": math.inf, "nan": math.nan}
        ).render({"profit_factor": math.inf, "nan": math.nan})
        text = rendered.decode("utf-8")

        for token in ("Infinity", "-Infinity", "NaN"):
            assert token not in text

        assert json.loads(text) == {"profit_factor": None, "nan": None}

    def test_an_endpoint_returning_infinity_stays_parseable(self) -> None:
        config = build_config()
        app = create_aqos_api_app(config)
        router = APIRouter()

        @router.get("/metrics")
        def metrics():
            from aqos.http_api.responses import json_response

            return json_response(
                {
                    "profit_factor": math.inf,
                    "profit_factor_state": "infinite_no_losses",
                }
            )

        app.include_router(router, prefix=config.api_prefix)

        response = TestClient(app).get(f"{API_V1_PREFIX}/metrics")

        for token in ("Infinity", "-Infinity", "NaN"):
            assert token not in response.text

        payload = response.json()

        assert payload["profit_factor"] is None
        assert payload["profit_factor_state"] == "infinite_no_losses"

    def test_every_foundation_endpoint_is_strict_json(self) -> None:
        client = build_client(database_url=SECRET_DB_URL)

        for path in ("/health/live", "/health/ready", f"{API_V1_PREFIX}/system/info"):
            body = client.get(path).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)
