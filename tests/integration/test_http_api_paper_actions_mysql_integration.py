"""
Paper trading action endpoints against real MySQL.

Every assertion is about persisted rows: the session, its orders, fills,
positions, trades and eligibility decisions as MySQL holds them after the
request. A refused attempt must leave a decision and nothing else.

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
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.http_api.routes_paper_actions import PAPER_ACTION_COMMANDS
from aqos.paper_trading.repositories import (
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.session_service import PaperSessionRepository
from aqos.paper_trading.sessions import PaperSessionStatus, PaperSessionType
from aqos.trading_settings.models import SymbolPreferenceKind
from aqos.trading_settings.repositories import (
    SymbolPreferenceRepository,
    TradingSettingsRepository,
)
from aqos.users.models import UserStatus
from aqos.users.repositories import (
    UserCredentialRepository,
    UserProfileRepository,
    UserSessionRepository,
)


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
PASSWORD = "Correct-Horse-Battery-9"

BLOCKED_SYMBOL = "GBPUSD"

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so paper trading actions are NOT "
            "verified against MySQL by this run. Run them with:\n"
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
            "so paper trading actions are NOT verified by this run. Start "
            "MySQL and run them with:\n"
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
            "signal_reasons",
            "signal_events",
            "trading_signals",
            "symbol_preferences",
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
def action_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


def create_user(database: AqosDatabase, email: str) -> dict:
    """One user with a paper account, a funded account and a blocked symbol."""

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

        TradingSettingsRepository(session).create_for_user(
            user_id=user_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
            created_at_utc=FIXED_NOW,
        )

        SymbolPreferenceRepository(session).add_symbol(
            user_id=user_id,
            symbol=BLOCKED_SYMBOL,
            kind=SymbolPreferenceKind.BLOCKED,
            created_at_utc=FIXED_NOW,
        )

        accounts = TradingAccountRepository(session)

        paper_account_id = accounts.create_account(
            user_id=user_id,
            name=f"Paper {email}",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            created_at_utc=FIXED_NOW,
        ).account_id

        funded_account_id = accounts.create_account(
            user_id=user_id,
            name=f"Funded {email}",
            account_type=AccountType.FUNDED,
            broker=BrokerKind.MT5,
            initial_balance=50_000.0,
            created_at_utc=FIXED_NOW,
        ).account_id

    return {
        "user_id": user_id,
        "email": email,
        "paper_account_id": paper_account_id,
        "funded_account_id": funded_account_id,
    }


@pytest.fixture
def client(action_database, database_url: str) -> TestClient:
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
def alice(action_database) -> dict:
    return create_user(action_database, "alice@example.com")


@pytest.fixture
def bob(action_database) -> dict:
    return create_user(action_database, "bob@example.com")


def login(client: TestClient, email: str) -> str:
    response = client.post(
        f"{API_V1_PREFIX}/auth/login",
        json={"email": email, "password": PASSWORD},
    )

    assert response.status_code == 201, response.text

    return response.json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def sessions_url() -> str:
    return f"{API_V1_PREFIX}/paper/sessions"


def session_url(session_id: str, suffix: str = "") -> str:
    base = f"{API_V1_PREFIX}/paper/sessions/{session_id}"

    return f"{base}/{suffix}" if suffix else base


def bar(symbol: str = "XAUUSD", price: float = 100.0, minutes: int = 0) -> dict:
    return {
        "symbol": symbol,
        "timestamp_utc": (FIXED_NOW + timedelta(minutes=minutes)).isoformat(),
        "open": price,
        "high": price + 1.0,
        "low": price - 1.0,
        "close": price,
    }


def order_body(symbol: str = "XAUUSD", **overrides) -> dict:
    payload = {
        "symbol": symbol,
        "action": "buy",
        "order_type": "market",
        "quantity": 1.0,
        "market": bar(symbol=symbol),
        "submitted_at_utc": FIXED_NOW.isoformat(),
    }
    payload.update(overrides)

    return payload


def open_session(
    client: TestClient,
    token: str,
    owner: dict,
    start: bool = True,
    **overrides,
) -> str:
    payload = {
        "account_id": owner["paper_account_id"],
        "session_name": "Run",
        "session_type": PaperSessionType.MANUAL_PAPER_SESSION.value,
    }
    payload.update(overrides)

    response = client.post(sessions_url(), json=payload, headers=auth_header(token))

    assert response.status_code == 201, response.text

    session_id = response.json()["session"]["session_id"]

    if start:
        assert client.post(
            session_url(session_id, "start"),
            headers=auth_header(token),
        ).status_code == 200

    return session_id


def read_state(database: AqosDatabase, session_id: str) -> dict:
    """Everything one session has produced, counted from MySQL."""

    with database.session() as session:
        record = PaperSessionRepository(session).require_session(session_id)

        return {
            "status": record.status,
            "status_reason": record.status_reason,
            "orders": len(
                PaperOrderRepository(session).list_orders(session_id=session_id)
            ),
            "fills": len(
                PaperFillRepository(session).list_fills(session_id=session_id)
            ),
            "positions": len(
                PaperPositionRepository(session).list_positions(
                    session_id=session_id
                )
            ),
            "trades": len(
                PaperTradeRepository(session).list_trades(session_id=session_id)
            ),
            "decisions": len(
                PaperExecutionDecisionRepository(session).list_decisions(
                    session_id=session_id
                )
            ),
        }


class TestRouteRegistration:
    def test_every_session_command_is_reachable(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        for command in PAPER_ACTION_COMMANDS:
            session_id = open_session(client, token, alice, start=False)
            response = client.post(
                session_url(session_id, command),
                json={"reason": "Because."},
                headers=auth_header(token),
            )

            assert response.status_code != 404, command
            assert response.status_code != 405, command

    def test_commands_do_not_answer_get(self, client, alice) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice, start=False)

        for command in PAPER_ACTION_COMMANDS:
            assert client.get(
                session_url(session_id, command),
                headers=auth_header(token),
            ).status_code == 405, command


class TestAuthenticationIsRequired:
    def test_no_token_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        attempts = [
            (sessions_url(), {"account_id": alice["paper_account_id"],
                              "session_name": "Run",
                              "session_type": "manual_paper_session"}),
            (session_url(session_id, "pause"), {}),
            (session_url(session_id, "orders"), order_body()),
            (
                session_url(session_id, "orders/order_1/cancel"),
                None,
            ),
            (
                session_url(session_id, "positions/position_1/close"),
                {"exit_price": 100.0},
            ),
        ]

        for url, body in attempts:
            assert client.post(url, json=body).status_code == 401, url

    def test_an_invalid_token_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        assert client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header("not-a-real-token"),
        ).status_code == 401

    def test_a_revoked_token_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        client.post(
            f"{API_V1_PREFIX}/auth/logout",
            headers=auth_header(token),
        )

        assert client.post(
            session_url(session_id, "pause"),
            json={},
            headers=auth_header(token),
        ).status_code == 401

    def test_an_expired_token_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        with action_database.session() as session:
            record = UserSessionRepository(session).find_by_token(token)
            record.expires_at_utc = database_utc_now() - timedelta(minutes=1)

        assert client.post(
            session_url(session_id, "pause"),
            json={},
            headers=auth_header(token),
        ).status_code == 401

    @pytest.mark.parametrize(
        "status",
        [UserStatus.SUSPENDED, UserStatus.DISABLED],
    )
    def test_an_inactive_user_cannot_act(
        self,
        client,
        action_database,
        alice,
        status: UserStatus,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        with action_database.session() as session:
            UserProfileRepository(session).set_status(
                user_id=alice["user_id"],
                status=status,
            )

        response = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        )

        assert response.status_code == 403
        assert read_state(action_database, session_id)["orders"] == 0

    def test_a_refused_request_writes_nothing(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)
        before = read_state(action_database, session_id)

        client.post(session_url(session_id, "orders"), json=order_body())

        assert read_state(action_database, session_id) == before


class TestSessionCreation:
    def test_a_paper_account_gets_a_session(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        response = client.post(
            sessions_url(),
            json={
                "account_id": alice["paper_account_id"],
                "session_name": "Manual run",
                "session_type": "manual_paper_session",
            },
            headers=auth_header(token),
        )

        assert response.status_code == 201

        payload = response.json()

        assert payload["session"]["status"] == "created"
        assert payload["session"]["account_id"] == alice["paper_account_id"]
        assert payload["transition"]["command"] == "create"
        assert payload["transition"]["from_status"] is None
        assert payload["transition"]["to_status"] == "created"

    def test_a_funded_account_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        A session is what activity is booked against.

        Attaching one to a funded account would let simulated trades be grouped
        under real capital, so it is refused before anything is written.
        """

        token = login(client, alice["email"])

        response = client.post(
            sessions_url(),
            json={
                "account_id": alice["funded_account_id"],
                "session_name": "Nope",
                "session_type": "manual_paper_session",
            },
            headers=auth_header(token),
        )

        assert response.status_code == 409

        with action_database.session() as session:
            assert PaperSessionRepository(session).list_sessions() == ()

    def test_another_users_account_is_not_found(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        token = login(client, alice["email"])

        response = client.post(
            sessions_url(),
            json={
                "account_id": bob["paper_account_id"],
                "session_name": "Not mine",
                "session_type": "manual_paper_session",
            },
            headers=auth_header(token),
        )

        assert response.status_code == 404

        with action_database.session() as session:
            assert PaperSessionRepository(session).list_sessions() == ()

    def test_a_missing_account_answers_the_same(
        self,
        client,
        alice,
        bob,
    ) -> None:
        """Foreign and absent must be indistinguishable."""

        token = login(client, alice["email"])
        body = {
            "session_name": "Not mine",
            "session_type": "manual_paper_session",
        }

        foreign = client.post(
            sessions_url(),
            json={**body, "account_id": bob["paper_account_id"]},
            headers=auth_header(token),
        )
        missing = client.post(
            sessions_url(),
            json={**body, "account_id": "account_nope"},
            headers=auth_header(token),
        )

        assert foreign.status_code == missing.status_code == 404
        assert foreign.json()["error"]["message"] == (
            missing.json()["error"]["message"]
        )

    def test_a_model_forward_test_must_name_its_model(
        self,
        client,
        alice,
    ) -> None:
        """An unattributed forward test cannot be reproduced later."""

        token = login(client, alice["email"])

        response = client.post(
            sessions_url(),
            json={
                "account_id": alice["paper_account_id"],
                "session_name": "Forward test",
                "session_type": PaperSessionType.MODEL_FORWARD_TEST.value,
            },
            headers=auth_header(token),
        )

        assert response.status_code == 409

    def test_a_model_forward_test_with_a_model_is_accepted(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        response = client.post(
            sessions_url(),
            json={
                "account_id": alice["paper_account_id"],
                "session_name": "Forward test",
                "session_type": PaperSessionType.MODEL_FORWARD_TEST.value,
                "model_id": "model_1",
                "model_version": "1.0",
            },
            headers=auth_header(token),
        )

        assert response.status_code == 201
        assert response.json()["session"]["model_id"] == "model_1"

    def test_a_strategy_forward_test_must_name_its_strategy(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        response = client.post(
            sessions_url(),
            json={
                "account_id": alice["paper_account_id"],
                "session_name": "Strategy test",
                "session_type": PaperSessionType.STRATEGY_FORWARD_TEST.value,
            },
            headers=auth_header(token),
        )

        assert response.status_code == 409

    def test_an_unknown_session_type_is_refused(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        assert client.post(
            sessions_url(),
            json={
                "account_id": alice["paper_account_id"],
                "session_name": "Run",
                "session_type": "wishful_thinking",
            },
            headers=auth_header(token),
        ).status_code == 422


class TestSessionLifecycle:
    def test_a_created_session_starts(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice, start=False)

        response = client.post(
            session_url(session_id, "start"),
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["transition"]["from_status"] == "created"
        assert response.json()["transition"]["to_status"] == "running"
        assert read_state(action_database, session_id)["status"] is (
            PaperSessionStatus.RUNNING
        )

    def test_a_running_session_pauses_and_resumes(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        assert client.post(
            session_url(session_id, "pause"),
            json={"reason": "Stepping away."},
            headers=auth_header(token),
        ).status_code == 200
        assert read_state(action_database, session_id)["status"] is (
            PaperSessionStatus.PAUSED
        )

        assert client.post(
            session_url(session_id, "resume"),
            headers=auth_header(token),
        ).status_code == 200
        assert read_state(action_database, session_id)["status"] is (
            PaperSessionStatus.RUNNING
        )

    def test_a_running_session_completes(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        assert client.post(
            session_url(session_id, "complete"),
            headers=auth_header(token),
        ).status_code == 200
        assert read_state(action_database, session_id)["status"] is (
            PaperSessionStatus.COMPLETED
        )

    def test_cancelling_records_the_reason(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        assert client.post(
            session_url(session_id, "cancel"),
            json={"reason": "Data was wrong."},
            headers=auth_header(token),
        ).status_code == 200

        stored = read_state(action_database, session_id)

        assert stored["status"] is PaperSessionStatus.CANCELLED
        assert stored["status_reason"] == "Data was wrong."

    @pytest.mark.parametrize("command", ["cancel", "fail"])
    def test_stopping_without_a_reason_is_refused(
        self,
        client,
        action_database,
        alice,
        command: str,
    ) -> None:
        """A run that stopped badly has to record what went wrong."""

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        response = client.post(
            session_url(session_id, command),
            json={},
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert read_state(action_database, session_id)["status"] is (
            PaperSessionStatus.RUNNING
        )

    def test_a_paused_session_cannot_complete(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        client.post(
            session_url(session_id, "pause"),
            json={},
            headers=auth_header(token),
        )

        assert client.post(
            session_url(session_id, "complete"),
            headers=auth_header(token),
        ).status_code == 409
        assert read_state(action_database, session_id)["status"] is (
            PaperSessionStatus.PAUSED
        )

    @pytest.mark.parametrize("command", ["start", "resume", "pause"])
    def test_a_terminal_session_cannot_restart(
        self,
        client,
        action_database,
        alice,
        command: str,
    ) -> None:
        """Completed is the end of a run, not a pause in one."""

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        client.post(session_url(session_id, "complete"), headers=auth_header(token))

        response = client.post(
            session_url(session_id, command),
            json={},
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert read_state(action_database, session_id)["status"] is (
            PaperSessionStatus.COMPLETED
        )

    def test_a_refused_transition_writes_nothing(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        client.post(
            session_url(session_id, "cancel"),
            json={"reason": "Done."},
            headers=auth_header(token),
        )
        before = read_state(action_database, session_id)

        client.post(session_url(session_id, "start"), headers=auth_header(token))

        assert read_state(action_database, session_id) == before


class TestOrderSubmission:
    def test_a_valid_order_is_accepted(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        response = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        )

        assert response.status_code == 201

        payload = response.json()

        assert payload["accepted"] is True
        assert payload["order"]["status"] == "filled"
        assert payload["fills"]
        assert payload["position"] is not None
        assert payload["decision"]["is_allowed"] is True

    def test_the_order_is_attached_to_its_session(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        Every artefact carries the session id.

        Without it a run's result could not be measured from its own rows.
        """

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        payload = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).json()

        assert payload["order"]["session_id"] == session_id
        assert payload["decision"]["session_id"] == session_id
        assert payload["position"]["session_id"] == session_id

        for fill in payload["fills"]:
            assert fill["session_id"] == session_id

    def test_the_gate_runs_at_manual_approval(
        self,
        client,
        alice,
    ) -> None:
        """An order somebody sent is not autonomous trading."""

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        decision = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).json()["decision"]

        assert decision["requested_execution_mode"] == "manual_approval"

    def test_every_attempt_records_exactly_one_decision(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        for index in range(3):
            client.post(
                session_url(session_id, "orders"),
                json=order_body(
                    market=bar(minutes=index),
                    submitted_at_utc=(
                        FIXED_NOW + timedelta(minutes=index)
                    ).isoformat(),
                ),
                headers=auth_header(token),
            )

        assert read_state(action_database, session_id)["decisions"] == 3

    def test_a_refused_attempt_still_records_its_decision(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        A blocked symbol produces an audit row and no order.

        "Why did nothing happen?" has to be answerable from structured rows
        rather than from a log.
        """

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        response = client.post(
            session_url(session_id, "orders"),
            json=order_body(symbol=BLOCKED_SYMBOL),
            headers=auth_header(token),
        )

        assert response.status_code == 201

        payload = response.json()

        assert payload["accepted"] is False
        assert payload["order"] is None
        assert payload["position"] is None
        assert payload["trade"] is None
        assert payload["fills"] == []
        assert payload["decision"]["is_allowed"] is False
        assert payload["decision"]["primary_reason_code"]

        stored = read_state(action_database, session_id)

        assert stored["decisions"] == 1
        assert stored["fills"] == 0
        assert stored["positions"] == 0
        assert stored["trades"] == 0

    def test_a_wrong_side_stop_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """A buy whose stop sits above entry would lock in a guaranteed loss."""

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        response = client.post(
            session_url(session_id, "orders"),
            json=order_body(stop_loss=120.0, requested_price=100.0),
            headers=auth_header(token),
        )

        assert response.status_code == 201
        assert response.json()["accepted"] is False

        stored = read_state(action_database, session_id)

        assert stored["decisions"] == 1
        assert stored["fills"] == 0
        assert stored["positions"] == 0

    def test_a_wrong_side_target_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        response = client.post(
            session_url(session_id, "orders"),
            json=order_body(take_profit=80.0, requested_price=100.0),
            headers=auth_header(token),
        )

        assert response.status_code == 201
        assert response.json()["accepted"] is False

    def test_an_order_needs_a_running_session(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice, start=False)

        response = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert read_state(action_database, session_id)["decisions"] == 0

    def test_a_completed_session_accepts_no_orders(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        client.post(session_url(session_id, "complete"), headers=auth_header(token))

        assert client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).status_code == 409

    def test_an_unknown_action_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        assert client.post(
            session_url(session_id, "orders"),
            json=order_body(action="teleport"),
            headers=auth_header(token),
        ).status_code == 422

    def test_an_impossible_bar_is_refused(self, client, alice) -> None:
        """A high that does not cover the close is not a market."""

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        broken = bar()
        broken["high"] = 50.0

        assert client.post(
            session_url(session_id, "orders"),
            json=order_body(market=broken),
            headers=auth_header(token),
        ).status_code == 409


class TestOrderAndPositionCommands:
    def test_an_open_position_can_be_closed(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        position_id = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).json()["position"]["position_id"]

        response = client.post(
            session_url(session_id, f"positions/{position_id}/close"),
            json={
                "exit_price": 110.0,
                "closed_at_utc": (FIXED_NOW + timedelta(hours=1)).isoformat(),
            },
            headers=auth_header(token),
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["position"]["status"] == "closed"
        assert payload["exit_reason"] == "manual_close"
        assert payload["trade"]["net_pnl"] is not None

        assert read_state(action_database, session_id)["trades"] == 1

    def test_closing_twice_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        position_id = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).json()["position"]["position_id"]

        body = {
            "exit_price": 110.0,
            "closed_at_utc": (FIXED_NOW + timedelta(hours=1)).isoformat(),
        }

        client.post(
            session_url(session_id, f"positions/{position_id}/close"),
            json=body,
            headers=auth_header(token),
        )
        after_first = read_state(action_database, session_id)

        assert client.post(
            session_url(session_id, f"positions/{position_id}/close"),
            json=body,
            headers=auth_header(token),
        ).status_code == 409
        assert read_state(action_database, session_id) == after_first

    def test_a_position_from_another_session_is_not_found(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        first = open_session(client, token, alice)
        second = open_session(client, token, alice)

        position_id = client.post(
            session_url(first, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).json()["position"]["position_id"]

        assert client.post(
            session_url(second, f"positions/{position_id}/close"),
            json={"exit_price": 110.0},
            headers=auth_header(token),
        ).status_code == 409

    def test_a_filled_order_cannot_be_cancelled(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """A market order that already filled has nothing left to withdraw."""

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        order_id = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).json()["order"]["order_id"]

        assert client.post(
            session_url(session_id, f"orders/{order_id}/cancel"),
            headers=auth_header(token),
        ).status_code == 409

    def test_an_unknown_order_is_not_found(self, client, alice) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        assert client.post(
            session_url(session_id, "orders/paperorder_nope/cancel"),
            headers=auth_header(token),
        ).status_code == 409


class TestOwnership:
    def test_another_users_session_is_not_actionable(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        bob_token = login(client, bob["email"])
        session_id = open_session(client, bob_token, bob)

        alice_token = login(client, alice["email"])

        for command in PAPER_ACTION_COMMANDS:
            assert client.post(
                session_url(session_id, command),
                json={"reason": "Mine now."},
                headers=auth_header(alice_token),
            ).status_code == 404, command

    def test_another_users_session_accepts_no_orders(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        bob_token = login(client, bob["email"])
        session_id = open_session(client, bob_token, bob)
        before = read_state(action_database, session_id)

        alice_token = login(client, alice["email"])

        assert client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(alice_token),
        ).status_code == 404
        assert read_state(action_database, session_id) == before

    def test_the_refusal_matches_a_missing_session(
        self,
        client,
        alice,
        bob,
    ) -> None:
        bob_token = login(client, bob["email"])
        foreign_id = open_session(client, bob_token, bob)

        token = login(client, alice["email"])

        foreign = client.post(
            session_url(foreign_id, "pause"),
            json={},
            headers=auth_header(token),
        )
        missing = client.post(
            session_url("papersession_nope", "pause"),
            json={},
            headers=auth_header(token),
        )

        assert foreign.status_code == missing.status_code == 404
        assert foreign.json()["error"]["code"] == (
            missing.json()["error"]["code"]
        )
        assert foreign.json()["error"]["message"] == (
            missing.json()["error"]["message"]
        )


class TestResponseSafety:
    def test_every_action_response_is_strict_json(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        bodies = [
            client.post(
                session_url(session_id, "orders"),
                json=order_body(),
                headers=auth_header(token),
            ).text,
            client.post(
                session_url(session_id, "orders"),
                json=order_body(symbol=BLOCKED_SYMBOL),
                headers=auth_header(token),
            ).text,
            client.post(
                session_url(session_id, "pause"),
                json={},
                headers=auth_header(token),
            ).text,
            client.post(
                sessions_url(),
                json={
                    "account_id": alice["paper_account_id"],
                    "session_name": "Another",
                    "session_type": "manual_paper_session",
                },
                headers=auth_header(token),
            ).text,
        ]

        for body in bodies:
            for fragment in ("Infinity", "-Infinity", "NaN"):
                assert fragment not in body

            json.loads(body)

    def test_errors_leak_nothing(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        client.post(session_url(session_id, "complete"), headers=auth_header(token))

        bodies = [
            client.post(session_url(session_id, "orders"), json=order_body()).text,
            client.post(
                session_url(session_id, "orders"),
                json=order_body(),
                headers=auth_header("bogus"),
            ).text,
            client.post(
                session_url(session_id, "orders"),
                json=order_body(),
                headers=auth_header(token),
            ).text,
            client.post(
                sessions_url(),
                json={
                    "account_id": alice["funded_account_id"],
                    "session_name": "Nope",
                    "session_type": "manual_paper_session",
                },
                headers=auth_header(token),
            ).text,
        ]

        for body in bodies:
            for fragment in (
                PASSWORD,
                "Traceback",
                "SELECT ",
                "INSERT ",
                "pymysql",
                "sqlalchemy",
                "password_hash",
                "token_hash",
                "pbkdf2",
                "PaperCommandError",
                "PaperTradingError",
                "InvalidPaperSessionTransitionError",
                token,
            ):
                assert fragment not in body

    def test_no_orm_internals_or_metadata_are_exposed(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        body = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).text

        assert "_sa_instance_state" not in body
        assert "extra_metadata" not in body
        assert "broker_credential_ref" not in body


class TestSimulationStaysSimulated:
    def test_the_paper_account_is_the_only_one_that_moves(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        A funded account's balance is untouched by any paper activity.

        The session is on the paper account, so nothing here should reach the
        funded one — this is the assertion that would fail first if it did.
        """

        with action_database.session() as session:
            before = TradingAccountRepository(session).require(
                alice["funded_account_id"]
            ).current_balance

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        )

        with action_database.session() as session:
            after = TradingAccountRepository(session).require(
                alice["funded_account_id"]
            ).current_balance

        assert after == before

    def test_the_result_endpoint_measures_the_run(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """What the actions produced is readable through the Sprint 056 API."""

        token = login(client, alice["email"])
        session_id = open_session(client, token, alice)

        position_id = client.post(
            session_url(session_id, "orders"),
            json=order_body(),
            headers=auth_header(token),
        ).json()["position"]["position_id"]

        client.post(
            session_url(session_id, f"positions/{position_id}/close"),
            json={
                "exit_price": 110.0,
                "closed_at_utc": (FIXED_NOW + timedelta(hours=1)).isoformat(),
            },
            headers=auth_header(token),
        )

        result = client.get(
            session_url(session_id, "result"),
            headers=auth_header(token),
        ).json()

        assert result["total_trades"] == 1
        assert result["total_decisions"] == 1
