"""
API authentication against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import json
import os
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.types import database_utc_now
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.auth import (
    ACCOUNT_LOCKED_MESSAGE,
    INVALID_CREDENTIALS_MESSAGE,
    INVALID_TOKEN_MESSAGE,
)
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.users.models import UserStatus
from aqos.users.passwords import hash_session_token
from aqos.users.repositories import (
    UserCredentialRepository,
    UserProfileRepository,
    UserSessionRepository,
)


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

EMAIL = "trader@example.com"
PASSWORD = "Correct-Horse-Battery-9"
WRONG_PASSWORD = "not-the-password-1A"

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so API authentication is NOT "
            "verified against MySQL by this run. Run it with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "user_preferences",
            "user_sessions",
            "user_credentials",
            "user_profiles",
        ):
            session.execute(text(f"TRUNCATE TABLE {table}"))

        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def database_url() -> str:
    return requires_mysql()


@pytest.fixture
def auth_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; API auth NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(auth_database) -> str:
    with auth_database.session() as session:
        profile = UserProfileRepository(session).create_user(
            email=EMAIL,
            display_name="Primary Trader",
        )
        UserCredentialRepository(session).set_password(
            user_id=profile.user_id,
            password=PASSWORD,
        )

        return profile.user_id


@pytest.fixture
def client(auth_database, database_url: str) -> TestClient:
    app = create_aqos_api_app(
        ApiConfig(
            environment=ApiEnvironment.TEST,
            database_url=database_url,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    app.state.aqos_database.dispose()


def login(client: TestClient, password: str = PASSWORD, **overrides):
    payload = {"email": EMAIL, "password": password}
    payload.update(overrides)

    return client.post(f"{API_V1_PREFIX}/auth/login", json=payload)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestLogin:
    def test_valid_credentials_issue_a_session(self, client, user_id) -> None:
        response = login(client)

        assert response.status_code == 201

        payload = response.json()

        assert payload["token"]
        assert payload["token_type"] == "bearer"
        assert payload["user"]["email"] == EMAIL
        assert payload["user"]["user_id"] == user_id
        assert payload["session"]["is_active"] is True

    def test_the_raw_token_is_never_stored(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        """Only the hash is persisted, so a stolen database yields no tokens."""

        token = login(client).json()["token"]

        with auth_database.read_session() as session:
            stored = session.execute(
                text("SELECT token_hash FROM user_sessions")
            ).scalar_one()

        assert stored != token
        assert stored == hash_session_token(token)

    def test_a_wrong_password_is_refused(self, client, user_id) -> None:
        response = login(client, password=WRONG_PASSWORD)

        assert response.status_code == 401
        assert response.json()["error"]["message"] == INVALID_CREDENTIALS_MESSAGE

    def test_an_unknown_email_answers_identically(self, client, user_id) -> None:
        """
        No user enumeration.

        A different answer here would tell an attacker which addresses are
        registered, so both failures are word for word the same.
        """

        unknown = client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": "nobody@example.com", "password": PASSWORD},
        )
        wrong = login(client, password=WRONG_PASSWORD)

        assert unknown.status_code == wrong.status_code == 401
        assert unknown.json()["error"] == {
            **wrong.json()["error"],
            "request_id": unknown.json()["error"]["request_id"],
        }

    @pytest.mark.parametrize(
        "address",
        [
            "dev@localhost",
            "not-an-email",
            "@example.com",
            "spaces in@example.com",
            "",
        ],
    )
    def test_a_malformed_address_answers_identically_too(
        self,
        client,
        user_id,
        address: str,
    ) -> None:
        """
        An address that is not an address is just another failed login.

        Letting the email normalizer's error escape answered with a 500, which
        told a caller their input never reached the credential check — and
        logged a traceback for what is only ever bad input. Found by running
        the app locally after Sprint 069.
        """

        malformed = client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": address, "password": PASSWORD},
        )

        assert malformed.status_code != 500
        assert malformed.status_code in (401, 422)

    def test_a_malformed_address_is_word_for_word_a_wrong_password(
        self,
        client,
        user_id,
    ) -> None:
        """The third failure mode must not be distinguishable from the other two."""

        malformed = client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": "dev@localhost", "password": PASSWORD},
        )
        wrong = login(client, password=WRONG_PASSWORD)

        assert malformed.status_code == wrong.status_code == 401
        assert malformed.json()["error"] == {
            **wrong.json()["error"],
            "request_id": malformed.json()["error"]["request_id"],
        }

    def test_a_malformed_address_leaks_nothing(self, client, user_id) -> None:
        body = client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": "dev@localhost", "password": PASSWORD},
        ).text

        for fragment in (
            "Traceback",
            "ValueError",
            "normalize_email",
            "is not valid",
            PASSWORD,
        ):
            assert fragment not in body

    def test_the_response_never_carries_the_password(
        self,
        client,
        user_id,
    ) -> None:
        body = login(client).text

        assert PASSWORD not in body
        assert "password" not in body.lower()

    def test_the_response_never_carries_a_password_hash(
        self,
        client,
        user_id,
    ) -> None:
        payload = login(client).json()

        assert "password_hash" not in json.dumps(payload)
        assert "token_hash" not in json.dumps(payload)

    def test_repeated_failures_lock_the_account(self, client, user_id) -> None:
        for _ in range(10):
            response = login(client, password=WRONG_PASSWORD)

            if response.status_code == 403:
                break

        assert response.status_code == 403
        assert response.json()["error"]["message"] == ACCOUNT_LOCKED_MESSAGE
        assert response.json()["error"]["code"] == "forbidden"

    def test_a_locked_account_refuses_the_right_password(
        self,
        client,
        user_id,
    ) -> None:
        """A lockout that the correct password bypasses is not a lockout."""

        for _ in range(10):
            if login(client, password=WRONG_PASSWORD).status_code == 403:
                break

        response = login(client)

        assert response.status_code == 403

    def test_failed_attempts_are_persisted(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        """
        The counter must survive the failed request that produced it.

        A failed login raises, and the request transaction rolls back with it;
        if the bookkeeping went too, the counter would reset on every attempt
        and the threshold could never be reached.
        """

        for _ in range(3):
            login(client, password=WRONG_PASSWORD)

        with auth_database.read_session() as session:
            attempts = session.execute(
                text("SELECT failed_attempt_count FROM user_credentials")
            ).scalar_one()

        assert attempts == 3

    def test_the_lockout_deadline_is_persisted(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        """The attempt that trips the threshold must commit the lock itself."""

        for _ in range(10):
            if login(client, password=WRONG_PASSWORD).status_code == 403:
                break

        with auth_database.read_session() as session:
            locked_until = session.execute(
                text("SELECT locked_until_utc FROM user_credentials")
            ).scalar_one()

        assert locked_until is not None
        assert locked_until > database_utc_now()

    def test_a_successful_login_clears_the_counter(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        for _ in range(2):
            login(client, password=WRONG_PASSWORD)

        assert login(client).status_code == 201

        with auth_database.read_session() as session:
            attempts = session.execute(
                text("SELECT failed_attempt_count FROM user_credentials")
            ).scalar_one()

        assert attempts == 0

    @pytest.mark.parametrize(
        "status",
        [UserStatus.SUSPENDED, UserStatus.DISABLED],
    )
    def test_an_inactive_user_gets_no_session(
        self,
        client,
        auth_database,
        user_id,
        status,
    ) -> None:
        with auth_database.session() as session:
            UserProfileRepository(session).set_status(user_id, status)

        response = login(client)

        assert response.status_code == 403

        with auth_database.read_session() as session:
            assert session.execute(
                text("SELECT COUNT(*) FROM user_sessions")
            ).scalar_one() == 0

    def test_a_malformed_request_is_a_validation_error(self, client) -> None:
        response = client.post(f"{API_V1_PREFIX}/auth/login", json={})

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_a_validation_error_never_echoes_the_password(
        self,
        client,
    ) -> None:
        """Pydantic errors quote input; the password must not be in one."""

        response = client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": "x", "password": PASSWORD},
        )

        assert PASSWORD not in response.text


class TestAuthenticatedAccess:
    def test_me_returns_the_caller(self, client, user_id) -> None:
        token = login(client).json()["token"]
        response = client.get(
            f"{API_V1_PREFIX}/auth/me",
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["user_id"] == user_id

    def test_me_requires_a_token(self, client, user_id) -> None:
        response = client.get(f"{API_V1_PREFIX}/auth/me")

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"

    @pytest.mark.parametrize(
        "header",
        [
            {"Authorization": "Bearer not-a-real-token"},
            {"Authorization": "Basic abc123"},
            {"Authorization": "Bearer"},
            {"Authorization": ""},
        ],
    )
    def test_a_bad_authorization_header_is_refused(
        self,
        client,
        user_id,
        header,
    ) -> None:
        response = client.get(f"{API_V1_PREFIX}/auth/me", headers=header)

        assert response.status_code == 401

    def test_the_scheme_is_case_insensitive(self, client, user_id) -> None:
        token = login(client).json()["token"]
        response = client.get(
            f"{API_V1_PREFIX}/auth/me",
            headers={"Authorization": f"bearer {token}"},
        )

        assert response.status_code == 200

    def test_an_expired_session_is_refused(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        token = login(client).json()["token"]

        with auth_database.session() as session:
            record = UserSessionRepository(session).find_by_token(token)
            record.expires_at_utc = database_utc_now() - timedelta(minutes=1)

        response = client.get(
            f"{API_V1_PREFIX}/auth/me",
            headers=auth_header(token),
        )

        assert response.status_code == 401
        assert response.json()["error"]["message"] == INVALID_TOKEN_MESSAGE

    def test_a_user_deactivated_mid_session_loses_access(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        """A live token must not outlive the account's right to use it."""

        token = login(client).json()["token"]

        with auth_database.session() as session:
            UserProfileRepository(session).set_status(
                user_id,
                UserStatus.SUSPENDED,
            )

        response = client.get(
            f"{API_V1_PREFIX}/auth/me",
            headers=auth_header(token),
        )

        assert response.status_code == 403

    def test_using_a_session_updates_last_seen(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        token = login(client).json()["token"]

        client.get(f"{API_V1_PREFIX}/auth/me", headers=auth_header(token))

        with auth_database.read_session() as session:
            record = UserSessionRepository(session).find_by_token(token)

            assert record.last_seen_at_utc is not None


class TestLogout:
    def test_logout_revokes_the_session(self, client, user_id) -> None:
        token = login(client).json()["token"]

        response = client.post(
            f"{API_V1_PREFIX}/auth/logout",
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["revoked"] is True

    def test_a_revoked_token_no_longer_works(self, client, user_id) -> None:
        token = login(client).json()["token"]
        client.post(f"{API_V1_PREFIX}/auth/logout", headers=auth_header(token))

        response = client.get(
            f"{API_V1_PREFIX}/auth/me",
            headers=auth_header(token),
        )

        assert response.status_code == 401

    def test_logging_out_twice_is_not_an_error(self, client, user_id) -> None:
        """The caller's intent is satisfied either way."""

        token = login(client).json()["token"]
        client.post(f"{API_V1_PREFIX}/auth/logout", headers=auth_header(token))

        response = client.post(
            f"{API_V1_PREFIX}/auth/logout",
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["revoked"] is False

    def test_logout_without_a_token_is_not_an_error(self, client) -> None:
        response = client.post(f"{API_V1_PREFIX}/auth/logout")

        assert response.status_code == 200
        assert response.json()["revoked"] is False


class TestSessionManagement:
    def test_sessions_lists_only_the_callers_own(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        """One user must never be able to enumerate another's devices."""

        with auth_database.session() as session:
            other = UserProfileRepository(session).create_user(
                email="other@example.com",
                display_name="Other Trader",
            )
            UserSessionRepository(session).create_session(user_id=other.user_id)

        token = login(client).json()["token"]
        payload = client.get(
            f"{API_V1_PREFIX}/auth/sessions",
            headers=auth_header(token),
        ).json()

        assert payload["total"] == 1
        assert {item["user_id"] for item in payload["sessions"]} == {user_id}

    def test_the_session_list_carries_no_token_material(
        self,
        client,
        user_id,
    ) -> None:
        token = login(client).json()["token"]
        body = client.get(
            f"{API_V1_PREFIX}/auth/sessions",
            headers=auth_header(token),
        ).text

        assert token not in body
        assert "token_hash" not in body

    def test_revoke_all_kills_every_session(
        self,
        client,
        user_id,
    ) -> None:
        first = login(client).json()["token"]
        second = login(client).json()["token"]

        response = client.post(
            f"{API_V1_PREFIX}/auth/logout-all",
            headers=auth_header(first),
        )

        assert response.status_code == 200
        assert response.json()["revoked"] == 2

        for token in (first, second):
            assert client.get(
                f"{API_V1_PREFIX}/auth/me",
                headers=auth_header(token),
            ).status_code == 401

    def test_sessions_require_authentication(self, client, user_id) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/auth/sessions"
        ).status_code == 401
        assert client.post(
            f"{API_V1_PREFIX}/auth/logout-all"
        ).status_code == 401


class TestResponseSafety:
    def test_no_auth_response_leaks_a_credential(
        self,
        client,
        user_id,
        database_url,
    ) -> None:
        token = login(client).json()["token"]

        bodies = [
            login(client).text,
            client.get(
                f"{API_V1_PREFIX}/auth/me",
                headers=auth_header(token),
            ).text,
            client.get(
                f"{API_V1_PREFIX}/auth/sessions",
                headers=auth_header(token),
            ).text,
        ]

        for body in bodies:
            assert PASSWORD not in body
            assert database_url not in body
            assert "aqos_pw" not in body
            assert "pbkdf2" not in body.lower()

    def test_every_auth_response_is_strict_json(self, client, user_id) -> None:
        token = login(client).json()["token"]

        for response in (
            login(client),
            client.get(f"{API_V1_PREFIX}/auth/me", headers=auth_header(token)),
            client.get(
                f"{API_V1_PREFIX}/auth/sessions",
                headers=auth_header(token),
            ),
            client.get(f"{API_V1_PREFIX}/auth/me"),
        ):
            for token_text in ("Infinity", "-Infinity", "NaN"):
                assert token_text not in response.text

            json.loads(response.text)

    def test_auth_errors_carry_the_request_id(self, client) -> None:
        response = client.get(f"{API_V1_PREFIX}/auth/me")

        assert response.json()["error"]["request_id"] == response.headers[
            "X-Request-ID"
        ]


class TestPerSessionRevoke:
    """
    Revoking one session by id.

    The risk here is cross-account probing: a caller must not be able to learn
    whether somebody else's session id exists.
    """

    def other_users_session_id(self, auth_database) -> str:
        with auth_database.session() as session:
            other = UserProfileRepository(session).create_user(
                email="stranger@example.com",
                display_name="Stranger",
            )

            return UserSessionRepository(session).create_session(
                user_id=other.user_id,
            ).session.session_id

    def test_a_caller_can_revoke_their_own_session(
        self,
        client,
        user_id,
    ) -> None:
        first = login(client).json()
        second_token = login(client).json()["token"]

        response = client.post(
            f"{API_V1_PREFIX}/auth/sessions/"
            f"{first['session']['session_id']}/revoke",
            headers=auth_header(second_token),
        )

        assert response.status_code == 200
        assert response.json()["revoked"] is True

        # The revoked session's token no longer works.
        assert client.get(
            f"{API_V1_PREFIX}/auth/me",
            headers=auth_header(first["token"]),
        ).status_code == 401

    def test_revoking_the_current_session_works(
        self,
        client,
        user_id,
    ) -> None:
        payload = login(client).json()

        response = client.post(
            f"{API_V1_PREFIX}/auth/sessions/"
            f"{payload['session']['session_id']}/revoke",
            headers=auth_header(payload["token"]),
        )

        assert response.status_code == 200
        assert client.get(
            f"{API_V1_PREFIX}/auth/me",
            headers=auth_header(payload["token"]),
        ).status_code == 401

    def test_revoking_twice_is_handled_safely(
        self,
        client,
        user_id,
    ) -> None:
        """Already revoked reports false rather than failing."""

        first = login(client).json()
        second_token = login(client).json()["token"]
        session_id = first["session"]["session_id"]

        client.post(
            f"{API_V1_PREFIX}/auth/sessions/{session_id}/revoke",
            headers=auth_header(second_token),
        )
        again = client.post(
            f"{API_V1_PREFIX}/auth/sessions/{session_id}/revoke",
            headers=auth_header(second_token),
        )

        assert again.status_code == 200
        assert again.json()["revoked"] is False

    def test_another_users_session_answers_as_not_found(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        """
        Ownership failure and absence share one answer.

        Anything else would let a caller probe for valid session ids on other
        accounts by comparing responses.
        """

        stranger_session_id = self.other_users_session_id(auth_database)
        token = login(client).json()["token"]

        owned_but_absent = client.post(
            f"{API_V1_PREFIX}/auth/sessions/session_does_not_exist/revoke",
            headers=auth_header(token),
        )
        someone_elses = client.post(
            f"{API_V1_PREFIX}/auth/sessions/{stranger_session_id}/revoke",
            headers=auth_header(token),
        )

        assert owned_but_absent.status_code == someone_elses.status_code == 404
        assert owned_but_absent.json()["error"]["code"] == (
            someone_elses.json()["error"]["code"]
        )
        assert owned_but_absent.json()["error"]["message"] == (
            someone_elses.json()["error"]["message"]
        )

    def test_another_users_session_is_not_actually_revoked(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        """The refusal must not have done the work anyway."""

        stranger_session_id = self.other_users_session_id(auth_database)
        token = login(client).json()["token"]

        client.post(
            f"{API_V1_PREFIX}/auth/sessions/{stranger_session_id}/revoke",
            headers=auth_header(token),
        )

        with auth_database.read_session() as session:
            record = UserSessionRepository(session).require(
                stranger_session_id
            )

            assert record.revoked_at_utc is None

    def test_revoke_requires_authentication(self, client, user_id) -> None:
        assert client.post(
            f"{API_V1_PREFIX}/auth/sessions/some_session/revoke"
        ).status_code == 401

    def test_the_response_carries_no_token_material(
        self,
        client,
        user_id,
    ) -> None:
        payload = login(client).json()
        body = client.post(
            f"{API_V1_PREFIX}/auth/sessions/"
            f"{payload['session']['session_id']}/revoke",
            headers=auth_header(payload["token"]),
        ).text

        assert payload["token"] not in body
        assert "token_hash" not in body


class TestLogoutAll:
    def test_it_revokes_every_session(self, client, user_id) -> None:
        first = login(client).json()["token"]
        second = login(client).json()["token"]

        response = client.post(
            f"{API_V1_PREFIX}/auth/logout-all",
            headers=auth_header(first),
        )

        assert response.status_code == 200
        assert response.json()["revoked"] == 2

        for token in (first, second):
            assert client.get(
                f"{API_V1_PREFIX}/auth/me",
                headers=auth_header(token),
            ).status_code == 401

    def test_it_leaves_another_users_sessions_alone(
        self,
        client,
        auth_database,
        user_id,
    ) -> None:
        with auth_database.session() as session:
            other = UserProfileRepository(session).create_user(
                email="bystander@example.com",
                display_name="Bystander",
            )
            stranger_session_id = UserSessionRepository(
                session
            ).create_session(user_id=other.user_id).session.session_id

        token = login(client).json()["token"]

        client.post(
            f"{API_V1_PREFIX}/auth/logout-all",
            headers=auth_header(token),
        )

        with auth_database.read_session() as session:
            record = UserSessionRepository(session).require(
                stranger_session_id
            )

            assert record.revoked_at_utc is None

    def test_it_requires_authentication(self, client, user_id) -> None:
        assert client.post(
            f"{API_V1_PREFIX}/auth/logout-all"
        ).status_code == 401
