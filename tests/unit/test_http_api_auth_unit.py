"""Unit tests for API auth helpers and response schemas."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from aqos.http_api.auth import (
    AQOS_HTTP_AUTH_VERSION,
    ACTIVE_USER_STATUSES,
    AuthenticatedCaller,
    ForbiddenApiError,
    INACTIVE_ACCOUNT_MESSAGE,
    INVALID_CREDENTIALS_MESSAGE,
    MISSING_TOKEN_MESSAGE,
    UnauthorizedApiError,
    assert_user_may_hold_a_session,
    extract_bearer_token,
)
from aqos.http_api.errors import ApiErrorCode
from aqos.http_api.auth_schemas import (
    AQOS_HTTP_AUTH_SCHEMAS_VERSION,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    MAX_PASSWORD_LENGTH,
    SessionListResponse,
    SessionResponse,
    UserResponse,
)
from aqos.users.models import UserProfile, UserRole, UserSession, UserStatus


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
PASSWORD = "Correct-Horse-Battery-9"


class FakeHeaders:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, key: str, default=None):
        return self.values.get(key, default)


class FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = FakeHeaders(headers or {})


def build_profile(status: UserStatus = UserStatus.ACTIVE) -> UserProfile:
    return UserProfile(
        user_id="user_1",
        email="trader@example.com",
        display_name="Primary Trader",
        role=UserRole.TRADER,
        status=status,
        timezone="UTC",
        locale="en-US",
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
    )


def build_session() -> UserSession:
    return UserSession(
        session_id="session_1",
        user_id="user_1",
        token_hash="a" * 64,
        created_at_utc=FIXED_NOW,
        expires_at_utc=FIXED_NOW + timedelta(hours=1),
        client_label="web",
    )


def test_module_versions_are_declared() -> None:
    assert AQOS_HTTP_AUTH_VERSION == "1.0"
    assert AQOS_HTTP_AUTH_SCHEMAS_VERSION == "1.0"


class TestBearerExtraction:
    def test_a_valid_header_yields_the_token(self) -> None:
        request = FakeRequest({"Authorization": "Bearer abc123"})

        assert extract_bearer_token(request) == "abc123"

    def test_the_scheme_is_case_insensitive(self) -> None:
        request = FakeRequest({"Authorization": "bearer abc123"})

        assert extract_bearer_token(request) == "abc123"

    @pytest.mark.parametrize(
        "header",
        [
            "Basic abc123",
            "Bearer",
            "Bearer   ",
            "abc123",
            "",
        ],
    )
    def test_a_malformed_header_yields_nothing(self, header: str) -> None:
        """A partial guess is worse than no token at all."""

        request = FakeRequest({"Authorization": header})

        assert extract_bearer_token(request) is None

    def test_a_missing_header_yields_nothing(self) -> None:
        assert extract_bearer_token(FakeRequest()) is None

    def test_surrounding_whitespace_is_trimmed(self) -> None:
        request = FakeRequest({"Authorization": "Bearer   abc123  "})

        assert extract_bearer_token(request) == "abc123"


class TestSessionEligibility:
    def test_an_active_user_may_hold_a_session(self) -> None:
        assert_user_may_hold_a_session(build_profile())

    @pytest.mark.parametrize(
        "status",
        [UserStatus.SUSPENDED, UserStatus.DISABLED],
    )
    def test_an_inactive_user_may_not(self, status: UserStatus) -> None:
        with pytest.raises(ForbiddenApiError, match="not active"):
            assert_user_may_hold_a_session(build_profile(status))

    def test_only_active_counts_as_eligible(self) -> None:
        assert ACTIVE_USER_STATUSES == (UserStatus.ACTIVE,)


class TestAuthErrors:
    def test_unauthorized_maps_to_401(self) -> None:
        error = UnauthorizedApiError()

        assert error.status_code == 401
        assert error.code == ApiErrorCode.UNAUTHORIZED
        assert error.message == MISSING_TOKEN_MESSAGE

    def test_forbidden_maps_to_403(self) -> None:
        error = ForbiddenApiError()

        assert error.status_code == 403
        assert error.code == ApiErrorCode.FORBIDDEN
        assert error.message == INACTIVE_ACCOUNT_MESSAGE

    def test_the_invalid_credentials_message_says_nothing_specific(self) -> None:
        """It must not reveal whether the address exists."""

        message = INVALID_CREDENTIALS_MESSAGE.lower()

        assert "email or password" in message
        assert "not found" not in message
        assert "unknown" not in message


class TestAuthenticatedCaller:
    def test_it_exposes_the_ids(self) -> None:
        caller = AuthenticatedCaller(
            user=build_profile(),
            session=build_session(),
        )

        assert caller.user_id == "user_1"
        assert caller.session_id == "session_1"


class TestLoginRequest:
    def test_a_valid_request_parses(self) -> None:
        request = LoginRequest(
            email="trader@example.com",
            password=PASSWORD,
            client_label="web",
        )

        assert request.email == "trader@example.com"

    def test_the_masked_form_omits_the_password_entirely(self) -> None:
        """Not masked, not truncated: absent, so it cannot reach a log."""

        request = LoginRequest(email="trader@example.com", password=PASSWORD)
        masked = request.masked()

        assert "password" not in masked
        assert PASSWORD not in json.dumps(masked)

    def test_an_absurdly_long_password_is_refused(self) -> None:
        with pytest.raises(ValueError):
            LoginRequest(
                email="trader@example.com",
                password="x" * (MAX_PASSWORD_LENGTH + 1),
            )

    def test_a_missing_password_is_refused(self) -> None:
        with pytest.raises(ValueError):
            LoginRequest(email="trader@example.com")


class TestResponseSchemas:
    def test_the_user_response_is_an_allow_list(self) -> None:
        """A field added to the ORM later must not appear on the wire."""

        payload = UserResponse.from_profile(build_profile()).model_dump()

        assert set(payload) == {
            "user_id",
            "email",
            "display_name",
            "role",
            "status",
            "timezone",
            "locale",
            "is_active",
        }

    def test_the_user_response_carries_no_secret(self) -> None:
        rendered = json.dumps(
            UserResponse.from_profile(build_profile()).model_dump()
        )

        assert "password" not in rendered.lower()
        assert "hash" not in rendered.lower()

    def test_the_session_response_carries_no_token_material(self) -> None:
        """The stored hash is a secret no endpoint has a reason to reveal."""

        payload = SessionResponse.from_session(build_session()).model_dump()
        rendered = json.dumps(payload, default=str)

        assert "token" not in rendered.lower()
        assert "a" * 64 not in rendered
        assert set(payload) == {
            "session_id",
            "user_id",
            "created_at_utc",
            "expires_at_utc",
            "last_seen_at_utc",
            "client_label",
            "is_active",
        }

    def test_the_login_response_carries_the_raw_token(self) -> None:
        """The one place it is returned; only the hash is ever stored."""

        response = LoginResponse(
            token="raw-token-value",
            expires_at_utc=FIXED_NOW + timedelta(hours=1),
            user=UserResponse.from_profile(build_profile()),
            session=SessionResponse.from_session(build_session()),
        )

        assert response.token == "raw-token-value"
        assert response.token_type == "bearer"

    def test_the_logout_response_reports_what_happened(self) -> None:
        assert LogoutResponse(revoked=False).session_id is None
        assert LogoutResponse(
            revoked=True,
            session_id="session_1",
        ).session_id == "session_1"

    def test_the_session_list_counts_its_entries(self) -> None:
        body = SessionListResponse(
            sessions=[SessionResponse.from_session(build_session())],
            total=1,
        )

        assert body.total == 1

    def test_every_schema_serialises_to_strict_json(self) -> None:
        payloads = [
            UserResponse.from_profile(build_profile()).model_dump(mode="json"),
            SessionResponse.from_session(build_session()).model_dump(
                mode="json"
            ),
            LogoutResponse(revoked=True, session_id="s").model_dump(
                mode="json"
            ),
        ]

        for payload in payloads:
            rendered = json.dumps(payload, allow_nan=False)

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in rendered
