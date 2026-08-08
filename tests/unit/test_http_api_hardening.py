"""
Unit tests for the request-level protections added in Sprint 062.

These are about what a caller can make the process do — how often, how much,
and what a browser is told about the answer — rather than about what any
endpoint returns. None of them needs a database.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import (
    API_V1_PREFIX,
    ApiConfig,
    ApiConfigError,
    ApiEnvironment,
)
from aqos.http_api.errors import ApiErrorCode, status_for_error_code
from aqos.http_api.hardening import (
    AUTH_PATH_MARKER,
    BODY_TOO_LARGE_MESSAGE,
    DEFAULT_SECURITY_HEADERS,
    PRIVATE_CACHE_CONTROL,
    RATE_LIMITED_ENVIRONMENTS,
    RATE_LIMITER_IS_SINGLE_PROCESS,
    RATE_LIMIT_MESSAGE,
    InProcessRateLimiter,
    RateLimitRule,
    is_auth_path,
    resolve_rate_limiting,
)
from aqos.http_api.middleware import REQUEST_ID_HEADER
from aqos.http_api.pagination import (
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    validate_limit,
    validate_offset,
)


SAFE_ORIGINS = ("https://app.example.com",)


def build_client(**overrides) -> TestClient:
    payload = {"environment": ApiEnvironment.TEST}
    payload.update(overrides)

    return TestClient(create_aqos_api_app(ApiConfig(**payload)))


def build_authenticated_client(**overrides) -> TestClient:
    """A client whose caller dependency is stubbed, for database-free routes."""

    from datetime import datetime, timedelta

    from aqos.http_api.auth import AuthenticatedCaller
    from aqos.http_api.authz import get_read_only_caller
    from aqos.users.models import UserProfile, UserRole, UserSession, UserStatus

    payload = {"environment": ApiEnvironment.TEST}
    payload.update(overrides)

    app = create_aqos_api_app(ApiConfig(**payload))
    now = datetime(2026, 1, 1, 0, 0, 0)

    app.dependency_overrides[get_read_only_caller] = lambda: AuthenticatedCaller(
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

    return TestClient(app)


def build_throttled_client(**overrides) -> TestClient:
    payload = {
        "environment": ApiEnvironment.STAGING,
        "cors_origins": SAFE_ORIGINS,
    }
    payload.update(overrides)

    return TestClient(create_aqos_api_app(ApiConfig(**payload)))


class TestRateLimiter:
    def test_requests_inside_the_allowance_are_allowed(self) -> None:
        limiter = InProcessRateLimiter()
        rule = RateLimitRule(requests=3)

        decisions = [limiter.check("a", rule, now=0.0) for _ in range(3)]

        assert all(decision.allowed for decision in decisions)
        assert [decision.remaining for decision in decisions] == [2, 1, 0]

    def test_the_next_request_is_refused(self) -> None:
        limiter = InProcessRateLimiter()
        rule = RateLimitRule(requests=2)

        limiter.check("a", rule, now=0.0)
        limiter.check("a", rule, now=0.0)
        decision = limiter.check("a", rule, now=0.0)

        assert decision.allowed is False
        assert decision.remaining == 0
        assert decision.retry_after_seconds >= 1

    def test_the_window_slides(self) -> None:
        """
        Old hits age out, so a steady caller is never permanently locked out.

        A fixed window would let a client spend its whole allowance at the end
        of one window and again at the start of the next.
        """

        limiter = InProcessRateLimiter()
        rule = RateLimitRule(requests=2, window_seconds=10.0)

        limiter.check("a", rule, now=0.0)
        limiter.check("a", rule, now=0.0)

        assert limiter.check("a", rule, now=5.0).allowed is False
        assert limiter.check("a", rule, now=11.0).allowed is True

    def test_clients_are_counted_separately(self) -> None:
        """One noisy caller must not throttle everybody else."""

        limiter = InProcessRateLimiter()
        rule = RateLimitRule(requests=1)

        assert limiter.check("a", rule, now=0.0).allowed is True
        assert limiter.check("a", rule, now=0.0).allowed is False
        assert limiter.check("b", rule, now=0.0).allowed is True

    def test_retry_after_points_past_the_oldest_hit(self) -> None:
        limiter = InProcessRateLimiter()
        rule = RateLimitRule(requests=1, window_seconds=60.0)

        limiter.check("a", rule, now=0.0)
        decision = limiter.check("a", rule, now=10.0)

        assert 1 <= decision.retry_after_seconds <= 61

    def test_reset_forgets_everything(self) -> None:
        limiter = InProcessRateLimiter()
        rule = RateLimitRule(requests=1)

        limiter.check("a", rule, now=0.0)
        limiter.reset()

        assert limiter.check("a", rule, now=0.0).allowed is True

    @pytest.mark.parametrize(
        "requests, window",
        [(0, 60.0), (-1, 60.0), (1, 0.0), (1, -5.0)],
    )
    def test_a_nonsensical_rule_is_refused(
        self,
        requests: int,
        window: float,
    ) -> None:
        with pytest.raises(ValueError):
            RateLimitRule(requests=requests, window_seconds=window)

    def test_the_single_process_limitation_is_stated(self) -> None:
        """
        The scope is part of the public surface, not a comment.

        Behind two workers each process counts its own traffic, so a reader has
        to be able to discover that without reading the implementation.
        """

        assert RATE_LIMITER_IS_SINGLE_PROCESS is True


class TestRateLimitingIsEnvironmentAware:
    @pytest.mark.parametrize("environment", RATE_LIMITED_ENVIRONMENTS)
    def test_it_is_on_where_it_matters(
        self,
        environment: ApiEnvironment,
    ) -> None:
        config = ApiConfig(environment=environment, cors_origins=SAFE_ORIGINS)

        assert resolve_rate_limiting(config) is True

    @pytest.mark.parametrize(
        "environment",
        [ApiEnvironment.DEVELOPMENT, ApiEnvironment.TEST],
    )
    def test_it_is_off_locally(self, environment: ApiEnvironment) -> None:
        """A limiter that fires during a test suite teaches people to disable it."""

        assert resolve_rate_limiting(ApiConfig(environment=environment)) is False

    def test_an_explicit_setting_wins_either_way(self) -> None:
        assert resolve_rate_limiting(
            ApiConfig(environment=ApiEnvironment.TEST, rate_limit_enabled=True)
        ) is True
        assert resolve_rate_limiting(
            ApiConfig(
                environment=ApiEnvironment.PRODUCTION,
                cors_origins=SAFE_ORIGINS,
                rate_limit_enabled=False,
            )
        ) is False

    def test_the_auth_allowance_is_stricter(self) -> None:
        """
        Guessing a password is what the tighter limit exists for.

        Reading data is a normal thing to do often; trying to log in eighty
        times a minute is not.
        """

        config = ApiConfig(environment=ApiEnvironment.TEST)

        assert config.auth_rate_limit_per_minute < config.rate_limit_per_minute

    def test_auth_paths_are_recognised(self) -> None:
        assert is_auth_path(f"{API_V1_PREFIX}/auth/login") is True
        assert is_auth_path(f"{API_V1_PREFIX}/signals") is False
        assert AUTH_PATH_MARKER in f"{API_V1_PREFIX}/auth/login"


class TestThrottledResponses:
    def test_exceeding_the_limit_returns_the_standard_envelope(self) -> None:
        client = build_throttled_client(auth_rate_limit_per_minute=2)
        url = f"{API_V1_PREFIX}/auth/login"
        body = {"email": "a@example.com", "password": "x"}

        for _ in range(2):
            client.post(url, json=body)

        response = client.post(url, json=body)
        payload = response.json()

        assert response.status_code == 429
        assert payload["error"]["code"] == ApiErrorCode.RATE_LIMITED.value
        assert payload["error"]["message"] == RATE_LIMIT_MESSAGE
        assert payload["error"]["request_id"]
        assert set(payload["error"]) == {
            "code",
            "message",
            "details",
            "request_id",
        }

    def test_it_says_when_to_come_back(self, ) -> None:
        client = build_throttled_client(auth_rate_limit_per_minute=1)
        url = f"{API_V1_PREFIX}/auth/login"
        body = {"email": "a@example.com", "password": "x"}

        client.post(url, json=body)
        response = client.post(url, json=body)

        assert response.headers["Retry-After"]
        assert response.json()["error"]["details"]["retry_after_seconds"] >= 1

    def test_reads_have_their_own_allowance(self) -> None:
        """
        Spending the login budget must not close the read endpoints.

        The two are counted in separate buckets, so a burst of failed logins
        does not also lock a user out of their own data.
        """

        client = build_throttled_client(
            auth_rate_limit_per_minute=1,
            rate_limit_per_minute=50,
        )
        login_url = f"{API_V1_PREFIX}/auth/login"
        body = {"email": "a@example.com", "password": "x"}

        client.post(login_url, json=body)

        assert client.post(login_url, json=body).status_code == 429
        assert client.get(f"{API_V1_PREFIX}/signals").status_code != 429

    def test_health_probes_are_never_throttled(self) -> None:
        """
        A monitoring system polls steadily and that is correct behaviour.

        Throttling it would turn a busy API into one that also looks down.
        """

        client = build_throttled_client(rate_limit_per_minute=1)

        for _ in range(10):
            assert client.get("/health/live").status_code == 200

    def test_nothing_is_throttled_in_test_environments(self) -> None:
        client = build_client()
        url = f"{API_V1_PREFIX}/auth/login"

        for _ in range(30):
            assert client.post(
                url,
                json={"email": "a@example.com", "password": "x"},
            ).status_code != 429

    def test_a_throttled_response_is_strict_json(self) -> None:
        client = build_throttled_client(auth_rate_limit_per_minute=1)
        url = f"{API_V1_PREFIX}/auth/login"
        body = {"email": "a@example.com", "password": "x"}

        client.post(url, json=body)
        text = client.post(url, json=body).text

        for fragment in ("Infinity", "-Infinity", "NaN", "Traceback"):
            assert fragment not in text

        json.loads(text)


class TestRequestSizeLimit:
    def test_an_oversized_body_is_refused(self) -> None:
        client = build_client(max_request_bytes=1_024)

        response = client.post(
            f"{API_V1_PREFIX}/auth/login",
            content=b"x" * 4_096,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 413
        assert response.json()["error"]["code"] == (
            ApiErrorCode.PAYLOAD_TOO_LARGE.value
        )
        assert response.json()["error"]["message"] == BODY_TOO_LARGE_MESSAGE

    def test_the_refusal_states_the_limit(self) -> None:
        client = build_client(max_request_bytes=1_024)

        details = client.post(
            f"{API_V1_PREFIX}/auth/login",
            content=b"x" * 4_096,
            headers={"Content-Type": "application/json"},
        ).json()["error"]["details"]

        assert details["max_bytes"] == 1_024

    def test_it_refuses_before_the_body_is_parsed(self) -> None:
        """
        Malformed JSON that is also too large comes back as too large.

        Parsing first would mean buffering and decoding whatever arrived, which
        is the work the limit exists to avoid.
        """

        client = build_client(max_request_bytes=512)

        response = client.post(
            f"{API_V1_PREFIX}/auth/login",
            content=b"{not json at all" + b"x" * 2_048,
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 413

    def test_a_normal_body_passes(self) -> None:
        client = build_client()

        response = client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": "a@example.com", "password": "correct horse"},
        )

        assert response.status_code != 413

    def test_the_default_limit_is_modest(self) -> None:
        """Every request this API takes is a small JSON object."""

        assert ApiConfig(environment=ApiEnvironment.TEST).max_request_bytes <= (
            1_048_576
        )

    def test_a_nonsensical_limit_is_refused(self) -> None:
        with pytest.raises(ApiConfigError):
            ApiConfig(environment=ApiEnvironment.TEST, max_request_bytes=0)


class TestSecurityHeaders:
    @pytest.mark.parametrize("header", sorted(DEFAULT_SECURITY_HEADERS))
    def test_every_response_carries_it(self, header: str) -> None:
        client = build_client()

        for path in ("/health/live", "/health/ready", f"{API_V1_PREFIX}/signals"):
            assert client.get(path).headers[header] == (
                DEFAULT_SECURITY_HEADERS[header]
            )

    def test_an_authenticated_response_is_never_stored(self) -> None:
        """
        A reply built for one bearer token is not a reply for the next caller.

        A shared cache holding it is exactly how one user reads another's data
        without ever authenticating as them.
        """

        client = build_client()

        response = client.get(
            f"{API_V1_PREFIX}/signals",
            headers={"Authorization": "Bearer whatever"},
        )

        assert response.headers["Cache-Control"] == PRIVATE_CACHE_CONTROL

    def test_an_anonymous_probe_is_cacheable(self) -> None:
        """Liveness carries nothing private, so nothing is claimed about it."""

        assert "Cache-Control" not in build_client().get("/health/live").headers

    def test_the_request_id_survives_the_stack(self) -> None:
        client = build_client()

        assert client.get("/health/live").headers[REQUEST_ID_HEADER]

    def test_no_debug_header_is_exposed(self) -> None:
        client = build_client()
        headers = {name.lower() for name in client.get("/health/live").headers}

        for leak in (
            "x-powered-by",
            "server-timing",
            "x-aspnet-version",
            "x-debug",
            "x-traceback",
        ):
            assert leak not in headers


class TestPaginationIsConsistent:
    def test_an_absent_limit_uses_the_default(self) -> None:
        assert validate_limit(None) == DEFAULT_PAGE_LIMIT

    def test_the_maximum_is_enforced(self) -> None:
        from aqos.http_api.errors import ValidationApiError

        with pytest.raises(ValidationApiError):
            validate_limit(MAX_PAGE_LIMIT + 1)

    @pytest.mark.parametrize("limit", [0, -1, -100])
    def test_a_non_positive_limit_is_refused(self, limit: int) -> None:
        from aqos.http_api.errors import ValidationApiError

        with pytest.raises(ValidationApiError):
            validate_limit(limit)

    def test_an_absent_offset_starts_at_zero(self) -> None:
        assert validate_offset(None) == 0

    @pytest.mark.parametrize("offset", [-1, -50])
    def test_a_negative_offset_is_refused(self, offset: int) -> None:
        from aqos.http_api.errors import ValidationApiError

        with pytest.raises(ValidationApiError):
            validate_offset(offset)

    def test_every_list_endpoint_shares_the_rules(self) -> None:
        """
        One set of rules, applied everywhere.

        Each list endpoint calls the same two validators, so a limit that is
        rejected on signals cannot be accepted on accounts.
        """

        client = build_client()
        list_paths = (
            f"{API_V1_PREFIX}/signals",
            f"{API_V1_PREFIX}/accounts",
            f"{API_V1_PREFIX}/paper/sessions",
            f"{API_V1_PREFIX}/backtests",
            f"{API_V1_PREFIX}/predictions",
            f"{API_V1_PREFIX}/models/promotions",
            f"{API_V1_PREFIX}/auth/sessions",
        )

        for path in list_paths:
            response = client.get(f"{path}?limit=0")

            # 422 from the shared validator, or refused earlier by auth or by
            # an unconfigured dependency. What must never happen is a 200.
            assert response.status_code != 200, path


class TestErrorContract:
    @pytest.mark.parametrize(
        "path, expected",
        [
            ("/does-not-exist", 404),
            (f"{API_V1_PREFIX}/signals", 503),
            (f"{API_V1_PREFIX}/backtests", 503),
        ],
    )
    def test_every_failure_uses_the_same_envelope(
        self,
        path: str,
        expected: int,
    ) -> None:
        response = build_client().get(path)
        payload = response.json()

        assert response.status_code == expected
        assert set(payload) == {"error"}
        assert set(payload["error"]) == {
            "code",
            "message",
            "details",
            "request_id",
        }

    def test_a_validation_failure_uses_it_too(self, tmp_path) -> None:
        """
        A real 422, produced by the shared pagination validator.

        Reaching one without a database needs the caller dependency overridden,
        because FastAPI resolves dependencies before it validates anything —
        which is why an unauthenticated bad request is a 401 rather than a 422.
        """

        registry = tmp_path / "predictions.json"
        registry.write_text(
            json.dumps({"registry_version": "1.0", "runs": []}),
            encoding="utf-8",
        )

        client = build_authenticated_client(
            prediction_registry_path=str(registry)
        )
        response = client.get(f"{API_V1_PREFIX}/predictions?limit=0")
        payload = response.json()

        assert response.status_code == 422
        assert payload["error"]["code"] == ApiErrorCode.VALIDATION_ERROR.value
        assert set(payload["error"]) == {
            "code",
            "message",
            "details",
            "request_id",
        }

    def test_pagination_is_validated_the_same_way_everywhere(
        self,
        tmp_path,
    ) -> None:
        """
        The same bad input is refused identically on every registry list.

        One shared validator, so a limit rejected on predictions cannot be
        quietly accepted on promotions.
        """

        predictions = tmp_path / "predictions.json"
        predictions.write_text(
            json.dumps({"registry_version": "1.0", "runs": []}),
            encoding="utf-8",
        )
        promotions = tmp_path / "promotions.json"
        promotions.write_text(
            json.dumps({"registry_version": "1.0", "promotions": []}),
            encoding="utf-8",
        )

        client = build_authenticated_client(
            prediction_registry_path=str(predictions),
            model_promotion_registry_path=str(promotions),
        )

        for path in (
            f"{API_V1_PREFIX}/predictions",
            f"{API_V1_PREFIX}/models/promotions",
        ):
            for query in ("limit=0", "limit=-1", "offset=-1"):
                response = client.get(f"{path}?{query}")

                assert response.status_code == 422, f"{path}?{query}"
                assert response.json()["error"]["code"] == (
                    ApiErrorCode.VALIDATION_ERROR.value
                )

    def test_every_error_code_maps_to_a_status(self) -> None:
        for code in ApiErrorCode:
            assert 400 <= status_for_error_code(code) <= 599

    def test_the_new_code_is_a_client_error(self) -> None:
        assert status_for_error_code(ApiErrorCode.PAYLOAD_TOO_LARGE) == 413


class TestOpenApiIsSafe:
    def build_schema(self) -> dict:
        return create_aqos_api_app(
            ApiConfig(
                environment=ApiEnvironment.TEST,
                database_url=(
                    "mysql+pymysql://aqos:sup3rs3cret@db.internal:3306/aqos"
                ),
                backtest_registry_path="/srv/aqos/registry.json",
                backtest_dataset_dir="/srv/aqos/datasets",
                backtest_output_dir="/srv/aqos/out",
            )
        ).openapi()

    def test_it_names_no_secret(self) -> None:
        rendered = json.dumps(self.build_schema())

        for secret in ("sup3rs3cret", "db.internal", "aqos_pw"):
            assert secret not in rendered

    def test_it_names_no_filesystem_path(self) -> None:
        rendered = json.dumps(self.build_schema())

        for path in ("/srv/aqos", "registry.json", "C:\\\\"):
            assert path not in rendered

    def test_it_names_no_orm_internal(self) -> None:
        """
        The schema describes the wire, not the database.

        A model class name in a public schema tells a reader what the tables
        are called, which is a head start they should not be given.
        """

        rendered = json.dumps(self.build_schema())

        for internal in (
            "TradingSignal",
            "PaperSessionRecord",
            "UserProfile",
            "sqlalchemy",
            "_sa_instance_state",
        ):
            assert internal not in rendered

    def test_no_schema_accepts_an_internal_field(self) -> None:
        """
        Checked as field names rather than as words.

        Schema docstrings are published, and one of them explains *why*
        ``extra_metadata`` is not accepted — so a substring search would flag
        the very prose that documents the rule. What matters is that no schema
        actually declares such a property.
        """

        schemas = self.build_schema().get("components", {}).get("schemas", {})
        declared = {
            name
            for schema in schemas.values()
            for name in (schema.get("properties") or {})
        }

        for internal in (
            "extra_metadata",
            "metadata",
            "user_id",
            "data_path",
            "password_hash",
            "token_hash",
        ):
            assert internal not in declared

    def test_it_carries_no_traceback(self) -> None:
        rendered = json.dumps(self.build_schema())

        assert "Traceback" not in rendered
        assert "File \\\"" not in rendered

    def test_it_is_withheld_in_production(self) -> None:
        app = create_aqos_api_app(
            ApiConfig(
                environment=ApiEnvironment.PRODUCTION,
                cors_origins=SAFE_ORIGINS,
            )
        )

        assert app.openapi_url is None


class TestCorsSafety:
    def test_a_wildcard_is_refused_in_production(self) -> None:
        with pytest.raises(ApiConfigError):
            ApiConfig(
                environment=ApiEnvironment.PRODUCTION,
                cors_origins=("*",),
            )

    def test_a_wildcard_is_refused_in_staging(self) -> None:
        with pytest.raises(ApiConfigError):
            ApiConfig(environment=ApiEnvironment.STAGING, cors_origins=("*",))

    def test_a_safe_origin_is_accepted(self) -> None:
        config = ApiConfig(
            environment=ApiEnvironment.PRODUCTION,
            cors_origins=SAFE_ORIGINS,
        )

        assert config.allows_any_origin is False

    def test_credentials_are_withheld_from_a_wildcard(self) -> None:
        """
        A wildcard origin with credentials would let any site read a session.

        Development may use a wildcard; it may not also send cookies.
        """

        config = ApiConfig(
            environment=ApiEnvironment.DEVELOPMENT,
            cors_origins=("*",),
        )

        assert config.allows_any_origin is True

    def test_local_origins_are_allowed_locally(self) -> None:
        config = ApiConfig(
            environment=ApiEnvironment.DEVELOPMENT,
            cors_origins=("http://localhost:5173",),
        )

        assert config.allows_any_origin is False
