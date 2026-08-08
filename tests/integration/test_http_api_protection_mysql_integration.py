"""
Authentication and ownership enforcement on the read-only APIs.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aqos.accounts.models import AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.types import database_utc_now
from aqos.execution_policy.modes import ExecutionMode
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.authz import CROSS_USER_FILTER_MESSAGE
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.paper_trading.session_service import PaperSessionService
from aqos.paper_trading.sessions import PaperSessionType
from aqos.signals.models import SignalAction, SignalSource
from aqos.signals.repositories import TradingSignalRepository
from aqos.users.models import UserStatus
from aqos.users.repositories import (
    UserCredentialRepository,
    UserProfileRepository,
    UserSessionRepository,
)


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
PASSWORD = "Correct-Horse-Battery-9"

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so API protection is NOT verified "
            "against MySQL by this run. Run it with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def requires_reachable_mysql(url: str) -> None:
    database = AqosDatabase(config=parse_database_url(url))

    try:
        reachable = database.ping()
    except Exception:
        reachable = False
    finally:
        database.dispose()

    if not reachable:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is set but the MySQL server is not reachable, "
            "so API protection is NOT verified by this run. Start MySQL and "
            "run it with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "paper_execution_decisions",
            "paper_account_snapshots",
            "paper_trades",
            "paper_fills",
            "paper_positions",
            "paper_orders",
            "paper_sessions",
            "account_performance_reports",
            "account_analytics_snapshots",
            "signal_reasons",
            "signal_events",
            "trading_signals",
            "funded_account_rules",
            "funded_rule_templates",
            "trading_accounts",
            "trading_settings",
            "user_sessions",
            "user_credentials",
            "user_profiles",
        ):
            session.execute(text(f"TRUNCATE TABLE {table}"))

        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def database_url() -> str:
    url = requires_mysql()
    requires_reachable_mysql(url)

    return url


@pytest.fixture
def protected_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


def create_user_with_data(database: AqosDatabase, email: str) -> dict:
    """One user owning an account, a signal and a paper session."""

    with database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email=email,
            display_name=email,
            created_at_utc=FIXED_NOW,
        ).user_id

        UserCredentialRepository(session).set_password(
            user_id=user_id,
            password=PASSWORD,
        )

        account_id = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name=f"Account {email}",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
            created_at_utc=FIXED_NOW,
        ).account_id

        signal_id = TradingSignalRepository(session).create_signal(
            user_id=user_id,
            account_id=account_id,
            symbol="XAUUSD",
            timeframe="H1",
            action=SignalAction.BUY,
            source=SignalSource.MANUAL,
            generated_at_utc=FIXED_NOW,
        ).signal_id

    with database.session() as session:
        account = TradingAccountRepository(session).require(account_id)
        session_id = PaperSessionService(session).start_session(
            account=account,
            session_name=f"Run {email}",
            session_type=PaperSessionType.MANUAL_PAPER_SESSION,
            started_at_utc=FIXED_NOW,
        ).session_id

    return {
        "user_id": user_id,
        "email": email,
        "account_id": account_id,
        "signal_id": signal_id,
        "session_id": session_id,
    }


@pytest.fixture
def client(protected_database, database_url: str) -> TestClient:
    app = create_aqos_api_app(
        ApiConfig(
            environment=ApiEnvironment.TEST,
            database_url=database_url,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    app.state.aqos_database.dispose()


@pytest.fixture
def alice(protected_database) -> dict:
    return create_user_with_data(protected_database, "alice@example.com")


@pytest.fixture
def bob(protected_database) -> dict:
    return create_user_with_data(protected_database, "bob@example.com")


def login(client: TestClient, email: str) -> str:
    response = client.post(
        f"{API_V1_PREFIX}/auth/login",
        json={"email": email, "password": PASSWORD},
    )

    assert response.status_code == 201

    return response.json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def business_paths(data: dict) -> list[str]:
    """Every protected read endpoint, with this user's ids substituted."""

    return [
        f"{API_V1_PREFIX}/system/info",
        f"{API_V1_PREFIX}/signals",
        f"{API_V1_PREFIX}/signals/{data['signal_id']}",
        f"{API_V1_PREFIX}/signals/{data['signal_id']}/events",
        f"{API_V1_PREFIX}/signals/{data['signal_id']}/reasons",
        f"{API_V1_PREFIX}/accounts",
        f"{API_V1_PREFIX}/accounts/{data['account_id']}",
        f"{API_V1_PREFIX}/accounts/{data['account_id']}/execution-constraints",
        f"{API_V1_PREFIX}/accounts/{data['account_id']}/funded-rules",
        f"{API_V1_PREFIX}/accounts/{data['account_id']}/analytics",
        f"{API_V1_PREFIX}/accounts/{data['account_id']}/analytics/snapshots",
        f"{API_V1_PREFIX}/accounts/{data['account_id']}/reports",
        f"{API_V1_PREFIX}/paper/sessions",
        f"{API_V1_PREFIX}/paper/sessions/{data['session_id']}",
        f"{API_V1_PREFIX}/paper/sessions/{data['session_id']}/result",
        f"{API_V1_PREFIX}/paper/sessions/{data['session_id']}/orders",
        f"{API_V1_PREFIX}/paper/sessions/{data['session_id']}/fills",
        f"{API_V1_PREFIX}/paper/sessions/{data['session_id']}/positions",
        f"{API_V1_PREFIX}/paper/sessions/{data['session_id']}/trades",
        f"{API_V1_PREFIX}/paper/sessions/{data['session_id']}/decisions",
        f"{API_V1_PREFIX}/predictions",
        f"{API_V1_PREFIX}/models/promotions",
        f"{API_V1_PREFIX}/backtests",
    ]


class TestPublicEndpoints:
    def test_health_stays_public(self, client) -> None:
        """Probes must work before anyone can log in."""

        assert client.get("/health/live").status_code == 200
        assert client.get("/health/ready").status_code == 200

    def test_login_stays_public(self, client, alice) -> None:
        assert client.post(
            f"{API_V1_PREFIX}/auth/login",
            json={"email": alice["email"], "password": PASSWORD},
        ).status_code == 201


class TestEveryBusinessRouteIsProtected:
    def test_no_token_is_refused(self, client, alice) -> None:
        for path in business_paths(alice):
            response = client.get(path)

            assert response.status_code == 401, path
            assert response.json()["error"]["code"] == "unauthorized", path

    def test_an_invalid_token_is_refused(self, client, alice) -> None:
        for path in business_paths(alice):
            response = client.get(
                path,
                headers=auth_header("not-a-real-token-value"),
            )

            assert response.status_code == 401, path

    def test_a_valid_token_is_accepted(self, client, alice) -> None:
        """
        Every protected route answers for its owner.

        Registry-backed routes report 503 when unconfigured, which is still an
        authenticated answer rather than a refusal.
        """

        token = login(client, alice["email"])

        for path in business_paths(alice):
            response = client.get(path, headers=auth_header(token))

            assert response.status_code in (200, 404, 503), (
                path,
                response.status_code,
            )
            assert response.status_code != 401, path

    def test_system_info_is_protected(self, client, alice) -> None:
        """
        It names the allowed CORS origins and the environment.

        That is deployment reconnaissance, so it needs a session even though it
        carries no user data.
        """

        assert client.get(f"{API_V1_PREFIX}/system/info").status_code == 401

        token = login(client, alice["email"])

        assert client.get(
            f"{API_V1_PREFIX}/system/info",
            headers=auth_header(token),
        ).status_code == 200


class TestTokenLifecycle:
    def test_a_revoked_token_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])

        client.post(
            f"{API_V1_PREFIX}/auth/logout",
            headers=auth_header(token),
        )

        assert client.get(
            f"{API_V1_PREFIX}/signals",
            headers=auth_header(token),
        ).status_code == 401

    def test_an_expired_token_is_refused(
        self,
        client,
        protected_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        with protected_database.session() as session:
            record = UserSessionRepository(session).find_by_token(token)
            record.expires_at_utc = database_utc_now() - timedelta(minutes=1)

        assert client.get(
            f"{API_V1_PREFIX}/signals",
            headers=auth_header(token),
        ).status_code == 401

    @pytest.mark.parametrize(
        "status",
        [UserStatus.SUSPENDED, UserStatus.DISABLED],
    )
    def test_an_inactive_user_is_refused(
        self,
        client,
        protected_database,
        alice,
        status,
    ) -> None:
        """A live token must not outlive the account's right to use it."""

        token = login(client, alice["email"])

        with protected_database.session() as session:
            UserProfileRepository(session).set_status(alice["user_id"], status)

        response = client.get(
            f"{API_V1_PREFIX}/signals",
            headers=auth_header(token),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "forbidden"


class TestOwnershipScoping:
    def test_signal_list_is_scoped_to_the_caller(
        self,
        client,
        alice,
        bob,
    ) -> None:
        token = login(client, alice["email"])
        payload = client.get(
            f"{API_V1_PREFIX}/signals",
            headers=auth_header(token),
        ).json()

        assert payload["count"] == 1
        assert payload["items"][0]["user_id"] == alice["user_id"]

    def test_account_list_is_scoped_to_the_caller(
        self,
        client,
        alice,
        bob,
    ) -> None:
        token = login(client, alice["email"])
        payload = client.get(
            f"{API_V1_PREFIX}/accounts",
            headers=auth_header(token),
        ).json()

        assert payload["count"] == 1
        assert payload["items"][0]["user_id"] == alice["user_id"]

    def test_paper_session_list_is_scoped_to_the_caller(
        self,
        client,
        alice,
        bob,
    ) -> None:
        token = login(client, alice["email"])
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions",
            headers=auth_header(token),
        ).json()

        assert payload["total"] == 1
        assert payload["items"][0]["user_id"] == alice["user_id"]

    def test_an_explicit_cross_user_filter_is_refused(
        self,
        client,
        alice,
        bob,
    ) -> None:
        """
        Refused rather than quietly narrowed.

        Silently returning the caller's own rows would look like a real answer
        and would hide the attempt from the caller and from the logs.
        """

        token = login(client, alice["email"])

        for path in (
            f"{API_V1_PREFIX}/signals",
            f"{API_V1_PREFIX}/accounts",
            f"{API_V1_PREFIX}/paper/sessions",
        ):
            response = client.get(
                f"{path}?user_id={bob['user_id']}",
                headers=auth_header(token),
            )

            assert response.status_code == 403, path
            assert response.json()["error"]["message"] == (
                CROSS_USER_FILTER_MESSAGE
            )

    def test_filtering_by_your_own_user_id_is_allowed(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        response = client.get(
            f"{API_V1_PREFIX}/signals?user_id={alice['user_id']}",
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["count"] == 1


class TestCrossUserDetailAccess:
    def cross_user_paths(self, other: dict) -> list[str]:
        return [
            f"{API_V1_PREFIX}/signals/{other['signal_id']}",
            f"{API_V1_PREFIX}/signals/{other['signal_id']}/events",
            f"{API_V1_PREFIX}/signals/{other['signal_id']}/reasons",
            f"{API_V1_PREFIX}/accounts/{other['account_id']}",
            f"{API_V1_PREFIX}/accounts/{other['account_id']}"
            "/execution-constraints",
            f"{API_V1_PREFIX}/accounts/{other['account_id']}/funded-rules",
            f"{API_V1_PREFIX}/accounts/{other['account_id']}/analytics",
            f"{API_V1_PREFIX}/accounts/{other['account_id']}"
            "/analytics/snapshots",
            f"{API_V1_PREFIX}/accounts/{other['account_id']}/reports",
            f"{API_V1_PREFIX}/paper/sessions/{other['session_id']}",
            f"{API_V1_PREFIX}/paper/sessions/{other['session_id']}/result",
            f"{API_V1_PREFIX}/paper/sessions/{other['session_id']}/orders",
            f"{API_V1_PREFIX}/paper/sessions/{other['session_id']}/fills",
            f"{API_V1_PREFIX}/paper/sessions/{other['session_id']}/positions",
            f"{API_V1_PREFIX}/paper/sessions/{other['session_id']}/trades",
            f"{API_V1_PREFIX}/paper/sessions/{other['session_id']}/decisions",
        ]

    def test_another_users_resources_are_not_readable(
        self,
        client,
        alice,
        bob,
    ) -> None:
        token = login(client, alice["email"])

        for path in self.cross_user_paths(bob):
            response = client.get(path, headers=auth_header(token))

            assert response.status_code == 404, path

    def test_the_refusal_matches_a_genuinely_missing_resource(
        self,
        client,
        alice,
        bob,
    ) -> None:
        """
        Ownership failure and absence answer identically.

        Any difference would turn these endpoints into an existence oracle for
        ids on other accounts.
        """

        token = login(client, alice["email"])

        owned_missing = client.get(
            f"{API_V1_PREFIX}/signals/signal_does_not_exist",
            headers=auth_header(token),
        )
        someone_elses = client.get(
            f"{API_V1_PREFIX}/signals/{bob['signal_id']}",
            headers=auth_header(token),
        )

        assert owned_missing.status_code == someone_elses.status_code == 404
        assert owned_missing.json()["error"]["code"] == (
            someone_elses.json()["error"]["code"]
        )
        assert owned_missing.json()["error"]["message"] == (
            someone_elses.json()["error"]["message"]
        )

    def test_a_report_cannot_be_read_through_another_users_account(
        self,
        client,
        alice,
        bob,
    ) -> None:
        token = login(client, alice["email"])
        response = client.get(
            f"{API_V1_PREFIX}/accounts/{bob['account_id']}"
            "/reports/report_anything",
            headers=auth_header(token),
        )

        assert response.status_code == 404


class TestErrorPayloads:
    def test_auth_errors_carry_a_request_id(self, client, alice) -> None:
        response = client.get(f"{API_V1_PREFIX}/signals")

        assert response.json()["error"]["request_id"] == response.headers[
            "X-Request-ID"
        ]

    def test_auth_errors_leak_nothing(
        self,
        client,
        protected_database,
        alice,
        database_url,
    ) -> None:
        token = login(client, alice["email"])

        with protected_database.read_session() as session:
            record = UserSessionRepository(session).find_by_token(token)
            token_hash = record.token_hash

        for response in (
            client.get(f"{API_V1_PREFIX}/signals"),
            client.get(
                f"{API_V1_PREFIX}/signals",
                headers=auth_header("bogus-token"),
            ),
        ):
            body = response.text

            assert token not in body
            assert token_hash not in body
            assert PASSWORD not in body
            assert database_url not in body
            assert "Traceback" not in body
            assert "pbkdf2" not in body.lower()

    def test_protected_responses_stay_strict_json(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        for path in business_paths(alice):
            for headers in ({}, auth_header(token)):
                body = client.get(path, headers=headers).text

                for token_text in ("Infinity", "-Infinity", "NaN"):
                    assert token_text not in body

                json.loads(body)


class TestReadsStayReads:
    def test_protected_reads_write_nothing(
        self,
        client,
        protected_database,
        alice,
    ) -> None:
        """
        Authentication must not turn a GET into a write.

        Resolving a caller on a read session with the last-seen touch disabled
        is what keeps a burst of reads from becoming a burst of UPDATEs.
        """

        token = login(client, alice["email"])

        def snapshot() -> dict:
            with protected_database.read_session() as session:
                row = session.execute(
                    text(
                        "SELECT last_seen_at_utc FROM user_sessions "
                        "WHERE user_id = :user_id"
                    ),
                    {"user_id": alice["user_id"]},
                ).one()

                return {"last_seen": row[0]}

        before = snapshot()

        for path in business_paths(alice):
            client.get(path, headers=auth_header(token))

        assert snapshot() == before
