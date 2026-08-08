"""
Signal lifecycle action endpoints against real MySQL.

Every assertion here is about persisted state: the signal row, the event trail
and the reason rows as MySQL holds them after the request. A transition that is
refused must leave all three exactly as they were.

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
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.http_api.routes_signal_actions import (
    EXPIRY_REASON_MESSAGE,
    SIGNAL_ACTION_STATUSES,
)
from aqos.signal_reasons.repositories import SignalReasonRepository
from aqos.signal_reasons.taxonomy import (
    SignalReasonCode,
    resolve_minimum_severity,
    resolve_reason_category,
)
from aqos.signals.models import SignalAction, SignalSource, SignalStatus
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

#: A code the taxonomy allows only for ``rejected``.
REJECTION_CODE = SignalReasonCode.SPREAD_TOO_HIGH

#: A code the taxonomy allows only for ``missed``.
#:
#: Deliberately disjoint from the rejection code so "wrong code for this
#: outcome" can be tested in both directions.
MISS_CODE = SignalReasonCode.EXECUTION_WINDOW_CLOSED

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so signal lifecycle actions are "
            "NOT verified against MySQL by this run. Run them with:\n"
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
            "so signal lifecycle actions are NOT verified by this run. Start "
            "MySQL and run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "signal_reasons",
            "signal_events",
            "trading_signals",
            "trading_accounts",
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
            name=f"Paper {email}",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            created_at_utc=FIXED_NOW,
        ).account_id

    return {"user_id": user_id, "email": email, "account_id": account_id}


def create_signal(
    database: AqosDatabase,
    owner: dict,
    status: SignalStatus = SignalStatus.GENERATED,
    expires_at_utc: datetime | None = None,
    symbol: str = "XAUUSD",
) -> str:
    """
    Seed one signal, moved into place through the real lifecycle.

    Statuses are reached by transitioning rather than by writing the column
    directly, so the seeded row always has an event trail a real signal would
    have. Creation itself writes a ``Signal created.`` event, so a freshly
    seeded signal already has one event before any action runs.
    """

    with database.session() as session:
        signals = TradingSignalRepository(session)

        signal = signals.create_signal(
            user_id=owner["user_id"],
            account_id=owner["account_id"],
            symbol=symbol,
            timeframe="H1",
            action=SignalAction.BUY,
            source=SignalSource.ML_MODEL,
            model_id="model_1",
            model_version="1.0",
            confidence=0.8,
            generated_at_utc=FIXED_NOW,
            expires_at_utc=expires_at_utc,
        )

        if status is not SignalStatus.GENERATED:
            signals.transition_signal(
                signal_id=signal.signal_id,
                to_status=status,
                reason="Seeded for test.",
                actor="seed",
                occurred_at_utc=FIXED_NOW + timedelta(minutes=1),
            )

        return signal.signal_id


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


def action_url(signal_id: str, action: str) -> str:
    return f"{API_V1_PREFIX}/signals/{signal_id}/{action}"


def body_for(action: str) -> dict:
    """The smallest valid body for each action."""

    if action == "reject":
        return {"reason_code": REJECTION_CODE.value}

    if action == "miss":
        return {"reason_code": MISS_CODE.value}

    if action == "cancel":
        return {"note": "No longer wanted."}

    return {}


def read_signal(database: AqosDatabase, signal_id: str) -> dict:
    """The persisted state, read back on a fresh session."""

    with database.session() as session:
        signals = TradingSignalRepository(session)
        signal = signals.require_signal(signal_id)

        return {
            "status": signal.status,
            "status_reason": signal.status_reason,
            "events": len(signals.list_events(signal_id)),
            "event_actors": [
                event.actor for event in signals.list_events(signal_id)
            ],
            "reasons": len(
                SignalReasonRepository(session).list_reasons(
                    signal_id=signal_id
                )
            ),
        }


class TestRouteRegistration:
    def test_every_action_is_reachable(self, client, action_database, alice) -> None:
        """Each named action answers something other than "no such route"."""

        token = login(client, alice["email"])

        for action in SIGNAL_ACTION_STATUSES:
            signal_id = create_signal(action_database, alice)
            response = client.post(
                action_url(signal_id, action),
                json=body_for(action),
                headers=auth_header(token),
            )

            assert response.status_code != 404, action
            assert response.status_code != 405, action

    def test_actions_do_not_answer_get(self, client, action_database, alice) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        for action in SIGNAL_ACTION_STATUSES:
            assert client.get(
                action_url(signal_id, action),
                headers=auth_header(token),
            ).status_code == 405, action


class TestAuthenticationIsRequired:
    def test_no_token_is_refused(self, client, action_database, alice) -> None:
        signal_id = create_signal(action_database, alice)

        for action in SIGNAL_ACTION_STATUSES:
            response = client.post(
                action_url(signal_id, action),
                json=body_for(action),
            )

            assert response.status_code == 401, action

    def test_an_invalid_token_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)

        for action in SIGNAL_ACTION_STATUSES:
            response = client.post(
                action_url(signal_id, action),
                json=body_for(action),
                headers=auth_header("not-a-real-token"),
            )

            assert response.status_code == 401, action

    def test_a_revoked_token_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        client.post(
            f"{API_V1_PREFIX}/auth/logout",
            headers=auth_header(token),
        )

        assert client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        ).status_code == 401

    def test_an_expired_token_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        with action_database.session() as session:
            record = UserSessionRepository(session).find_by_token(token)
            record.expires_at_utc = database_utc_now() - timedelta(minutes=1)

        assert client.post(
            action_url(signal_id, "approve"),
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
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        with action_database.session() as session:
            UserProfileRepository(session).set_status(
                user_id=alice["user_id"],
                status=status,
            )

        response = client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        )

        assert response.status_code == 403
        assert read_signal(action_database, signal_id)["status"] is (
            SignalStatus.GENERATED
        )

    def test_authentication_is_checked_before_the_body(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        A stranger learns nothing about what the body should look like.

        Validating first would let an anonymous caller probe the request schema
        by watching 422s come back instead of 401s.
        """

        signal_id = create_signal(action_database, alice)

        for body in ({"reason_code": "made_up"}, {"unknown_field": 1}, {}):
            assert client.post(
                action_url(signal_id, "reject"),
                json=body,
            ).status_code == 401, body

    def test_a_refused_request_changes_nothing(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """An unauthenticated attempt must not move the signal."""

        signal_id = create_signal(action_database, alice)
        before = read_signal(action_database, signal_id)

        client.post(action_url(signal_id, "approve"), json={})

        assert read_signal(action_database, signal_id) == before


class TestOwnership:
    def test_another_users_signal_is_not_actionable(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        signal_id = create_signal(action_database, bob)
        token = login(client, alice["email"])

        for action in SIGNAL_ACTION_STATUSES:
            response = client.post(
                action_url(signal_id, action),
                json=body_for(action),
                headers=auth_header(token),
            )

            assert response.status_code == 404, action

    def test_the_refusal_matches_a_missing_signal(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        """
        Foreign and absent must be indistinguishable.

        Otherwise a caller could walk the id space and learn which signal ids
        are real on other accounts.
        """

        foreign_id = create_signal(action_database, bob)
        token = login(client, alice["email"])

        foreign = client.post(
            action_url(foreign_id, "approve"),
            json={},
            headers=auth_header(token),
        )
        missing = client.post(
            action_url("signal_does_not_exist", "approve"),
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

    def test_a_foreign_signal_is_left_untouched(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        signal_id = create_signal(action_database, bob)
        before = read_signal(action_database, signal_id)
        token = login(client, alice["email"])

        client.post(
            action_url(signal_id, "cancel"),
            json=body_for("cancel"),
            headers=auth_header(token),
        )

        assert read_signal(action_database, signal_id) == before


class TestValidTransitions:
    def test_approve_moves_the_signal_and_records_an_event(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "approve"),
            json={"note": "Setup confirmed."},
            headers=auth_header(token),
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["signal"]["status"] == "approved"
        assert payload["event"]["from_status"] == "generated"
        assert payload["event"]["to_status"] == "approved"
        assert payload["reason"] is None

        stored = read_signal(action_database, signal_id)

        assert stored["status"] is SignalStatus.APPROVED
        assert stored["events"] == 2  # creation, then the approval
        assert stored["reasons"] == 0

    def test_the_acting_user_is_recorded(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """The audit trail says who decided, not just what was decided."""

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        )

        actors = read_signal(action_database, signal_id)["event_actors"]

        assert actors[-1] == alice["user_id"]

    def test_approve_works_with_no_body_at_all(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        The note is optional, so sending nothing has to be enough.

        A client with nothing to say should not have to send ``{}`` to say it.
        """

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "approve"),
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["signal"]["status"] == "approved"

        stored = read_signal(action_database, signal_id)

        assert stored["status"] is SignalStatus.APPROVED
        assert stored["status_reason"] is None

    def test_an_unknown_field_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        A misspelled field fails loudly rather than being dropped.

        Silently ignoring it would let a caller believe they had sent a note,
        or a severity, and had it honoured.
        """

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "approve"),
            json={"notes": "typo in the field name"},
            headers=auth_header(token),
        )

        assert response.status_code == 422
        assert read_signal(action_database, signal_id)["status"] is (
            SignalStatus.GENERATED
        )

    def test_mark_pending_approval_parks_the_signal(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "mark-pending-approval"),
            json={},
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["signal"]["status"] == "pending_approval"

    def test_reject_records_a_reason_row(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "reject"),
            json={
                "reason_code": REJECTION_CODE.value,
                "message": "Spread was 4x normal.",
            },
            headers=auth_header(token),
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["signal"]["status"] == "rejected"
        assert payload["event"]["to_status"] == "rejected"
        assert payload["reason"]["reason_code"] == REJECTION_CODE.value
        assert payload["reason"]["message"] == "Spread was 4x normal."

        stored = read_signal(action_database, signal_id)

        assert stored["status"] is SignalStatus.REJECTED
        assert stored["events"] == 2  # creation, then the rejection
        assert stored["reasons"] == 1

    def test_miss_records_a_reason_row(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "miss"),
            json={"reason_code": MISS_CODE.value},
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["signal"]["status"] == "missed"
        assert response.json()["reason"]["reason_code"] == MISS_CODE.value

        stored = read_signal(action_database, signal_id)

        assert stored["status"] is SignalStatus.MISSED
        assert stored["reasons"] == 1

    def test_a_blank_message_falls_back_to_the_canonical_one(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """A reason row can never explain nothing."""

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        payload = client.post(
            action_url(signal_id, "reject"),
            json={"reason_code": REJECTION_CODE.value},
            headers=auth_header(token),
        ).json()

        assert payload["reason"]["message"]

    def test_cancel_moves_the_signal(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "cancel"),
            json={"note": "Session ended."},
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["signal"]["status"] == "cancelled"

        stored = read_signal(action_database, signal_id)

        assert stored["status"] is SignalStatus.CANCELLED
        assert stored["status_reason"] == "Session ended."
        assert stored["reasons"] == 0

    def test_cancel_without_a_note_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "cancel"),
            json={},
            headers=auth_header(token),
        )

        assert response.status_code == 422
        assert read_signal(action_database, signal_id)["status"] is (
            SignalStatus.GENERATED
        )

    def test_an_approved_signal_can_still_be_cancelled(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(
            action_database,
            alice,
            status=SignalStatus.APPROVED,
        )
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "cancel"),
            json={"note": "Changed my mind."},
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["signal"]["status"] == "cancelled"


class TestExpiry:
    def test_a_due_signal_expires(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(
            action_database,
            alice,
            expires_at_utc=database_utc_now() - timedelta(hours=1),
        )
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "expire"),
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["signal"]["status"] == "expired"
        assert response.json()["event"]["reason"] == EXPIRY_REASON_MESSAGE

        assert read_signal(action_database, signal_id)["status"] is (
            SignalStatus.EXPIRED
        )

    def test_a_live_signal_cannot_be_expired(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(
            action_database,
            alice,
            expires_at_utc=database_utc_now() + timedelta(hours=1),
        )
        token = login(client, alice["email"])
        before = read_signal(action_database, signal_id)

        response = client.post(
            action_url(signal_id, "expire"),
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert read_signal(action_database, signal_id) == before

    def test_a_signal_with_no_expiry_cannot_be_expired(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "expire"),
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert response.json()["error"]["details"]["has_expiry"] is False


class TestInvalidTransitions:
    @pytest.mark.parametrize(
        "seeded_status, action",
        [
            (SignalStatus.APPROVED, "approve"),
            (SignalStatus.APPROVED, "mark-pending-approval"),
            (SignalStatus.REJECTED, "approve"),
            (SignalStatus.REJECTED, "reject"),
            (SignalStatus.CANCELLED, "cancel"),
            (SignalStatus.MISSED, "miss"),
        ],
    )
    def test_a_refused_transition_is_a_conflict(
        self,
        client,
        action_database,
        alice,
        seeded_status: SignalStatus,
        action: str,
    ) -> None:
        signal_id = create_signal(
            action_database,
            alice,
            status=seeded_status,
        )
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, action),
            json=body_for(action),
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "conflict"

    def test_generated_cannot_jump_to_executed(self) -> None:
        """
        There is no endpoint that can put a signal in the market.

        Execution is a separate concern with its own safety rails, so the
        transition is not merely refused — it is unreachable.
        """

        assert SignalStatus.EXECUTED not in set(SIGNAL_ACTION_STATUSES.values())

    def test_a_refused_transition_writes_nothing(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """The whole write session rolls back, so no audit row survives."""

        signal_id = create_signal(
            action_database,
            alice,
            status=SignalStatus.REJECTED,
        )
        before = read_signal(action_database, signal_id)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert read_signal(action_database, signal_id) == before

    def test_a_refused_rejection_writes_no_reason_row(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """A reason must never describe a decision that did not happen."""

        signal_id = create_signal(
            action_database,
            alice,
            status=SignalStatus.CANCELLED,
        )
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "reject"),
            json={"reason_code": REJECTION_CODE.value},
            headers=auth_header(token),
        )

        assert response.status_code == 409
        assert read_signal(action_database, signal_id)["reasons"] == 0

    def test_the_conflict_says_what_is_possible(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(
            action_database,
            alice,
            status=SignalStatus.APPROVED,
        )
        token = login(client, alice["email"])

        details = client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        ).json()["error"]["details"]

        assert details["from_status"] == "approved"
        assert "executed" in details["allowed_transitions"]


class TestRepeatedActions:
    def test_repeating_a_terminal_action_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])
        body = {"reason_code": REJECTION_CODE.value}

        first = client.post(
            action_url(signal_id, "reject"),
            json=body,
            headers=auth_header(token),
        )
        second = client.post(
            action_url(signal_id, "reject"),
            json=body,
            headers=auth_header(token),
        )

        assert first.status_code == 200
        assert second.status_code == 409

    def test_repeating_it_creates_no_second_audit_row(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        Duplicates are refused, never silently written.

        Two reason rows for one decision would double-count the signal in every
        downstream summary.
        """

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])
        body = {"reason_code": REJECTION_CODE.value}

        client.post(
            action_url(signal_id, "reject"),
            json=body,
            headers=auth_header(token),
        )
        after_first = read_signal(action_database, signal_id)

        for _ in range(3):
            client.post(
                action_url(signal_id, "reject"),
                json=body,
                headers=auth_header(token),
            )

        assert read_signal(action_database, signal_id) == after_first
        assert after_first["events"] == 2  # creation, then the one rejection
        assert after_first["reasons"] == 1

    def test_a_second_approval_does_not_duplicate_the_event(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        )
        client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        )

        assert read_signal(action_database, signal_id)["events"] == 2


class TestReasonRules:
    def test_a_rejection_needs_a_reason_code(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "reject"),
            json={},
            headers=auth_header(token),
        )

        assert response.status_code == 422
        assert read_signal(action_database, signal_id)["status"] is (
            SignalStatus.GENERATED
        )

    def test_an_unknown_reason_code_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "reject"),
            json={"reason_code": "totally_made_up"},
            headers=auth_header(token),
        )

        assert response.status_code == 422
        assert read_signal(action_database, signal_id)["status"] is (
            SignalStatus.GENERATED
        )

    def test_a_code_that_cannot_explain_the_status_is_refused(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "miss"),
            json={"reason_code": REJECTION_CODE.value},
            headers=auth_header(token),
        )

        assert response.status_code == 422

        stored = read_signal(action_database, signal_id)

        assert stored["status"] is SignalStatus.GENERATED
        assert stored["reasons"] == 0

    def test_category_and_severity_are_derived_from_the_code(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """The taxonomy decides, so the stored row matches it exactly."""

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        reason = client.post(
            action_url(signal_id, "reject"),
            json={"reason_code": REJECTION_CODE.value},
            headers=auth_header(token),
        ).json()["reason"]

        assert reason["reason_category"] == (
            resolve_reason_category(REJECTION_CODE).value
        )
        assert reason["severity"] == (
            resolve_minimum_severity(REJECTION_CODE).value
        )

    def test_a_client_cannot_downgrade_the_severity(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """
        Sending severity is refused outright, not quietly ignored.

        Silently dropping it would let a caller believe they had filed a
        breached rule as informational.
        """

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "reject"),
            json={
                "reason_code": REJECTION_CODE.value,
                "severity": "informational",
                "reason_category": "market_condition",
            },
            headers=auth_header(token),
        )

        assert response.status_code == 422
        assert read_signal(action_database, signal_id)["reasons"] == 0

    def test_metadata_is_not_accepted(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        """Unvalidated client JSON does not belong in an audit row."""

        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        response = client.post(
            action_url(signal_id, "reject"),
            json={
                "reason_code": REJECTION_CODE.value,
                "metadata": {"anything": "at all"},
            },
            headers=auth_header(token),
        )

        assert response.status_code == 422


class TestAuditTrailIsVisible:
    def test_the_action_appears_in_the_event_endpoint(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        client.post(
            action_url(signal_id, "approve"),
            json={"note": "Confirmed."},
            headers=auth_header(token),
        )

        events = client.get(
            f"{API_V1_PREFIX}/signals/{signal_id}/events",
            headers=auth_header(token),
        ).json()["items"]

        assert [event["to_status"] for event in events] == [
            "generated",
            "approved",
        ]
        assert events[-1]["actor"] == alice["user_id"]
        assert events[-1]["reason"] == "Confirmed."

    def test_a_rejection_appears_in_the_reason_endpoint(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        client.post(
            action_url(signal_id, "reject"),
            json={"reason_code": REJECTION_CODE.value},
            headers=auth_header(token),
        )

        reasons = client.get(
            f"{API_V1_PREFIX}/signals/{signal_id}/reasons",
            headers=auth_header(token),
        ).json()["items"]

        assert len(reasons) == 1
        assert reasons[0]["reason_code"] == REJECTION_CODE.value

    def test_a_miss_appears_in_the_reason_endpoint(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        client.post(
            action_url(signal_id, "miss"),
            json={"reason_code": MISS_CODE.value},
            headers=auth_header(token),
        )

        reasons = client.get(
            f"{API_V1_PREFIX}/signals/{signal_id}/reasons",
            headers=auth_header(token),
        ).json()["items"]

        assert [reason["reason_code"] for reason in reasons] == [
            MISS_CODE.value
        ]

    def test_the_detail_endpoint_shows_the_new_status(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        )

        detail = client.get(
            f"{API_V1_PREFIX}/signals/{signal_id}",
            headers=auth_header(token),
        ).json()

        assert detail["status"] == "approved"


class TestResponseSafety:
    def test_every_action_response_is_strict_json(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        for action in SIGNAL_ACTION_STATUSES:
            signal_id = create_signal(
                action_database,
                alice,
                expires_at_utc=database_utc_now() - timedelta(hours=1),
            )
            body = client.post(
                action_url(signal_id, action),
                json=body_for(action),
                headers=auth_header(token),
            ).text

            for fragment in ("Infinity", "-Infinity", "NaN"):
                assert fragment not in body, action

            json.loads(body)

    def test_errors_leak_nothing(
        self,
        client,
        action_database,
        alice,
        bob,
    ) -> None:
        signal_id = create_signal(
            action_database,
            alice,
            status=SignalStatus.REJECTED,
        )
        token = login(client, alice["email"])

        bodies = [
            client.post(action_url(signal_id, "approve"), json={}).text,
            client.post(
                action_url(signal_id, "approve"),
                json={},
                headers=auth_header("bogus"),
            ).text,
            client.post(
                action_url(signal_id, "approve"),
                json={},
                headers=auth_header(token),
            ).text,
            client.post(
                action_url(signal_id, "reject"),
                json={"reason_code": "made_up"},
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
                "InvalidSignalTransitionError",
                "SignalReasonError",
                token,
            ):
                assert fragment not in body

    def test_every_action_response_carries_the_expected_shape(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        for action in SIGNAL_ACTION_STATUSES:
            signal_id = create_signal(
                action_database,
                alice,
                expires_at_utc=database_utc_now() - timedelta(hours=1),
            )
            payload = client.post(
                action_url(signal_id, action),
                json=body_for(action),
                headers=auth_header(token),
            ).json()

            assert set(payload) == {"signal", "event", "reason"}, action
            assert payload["signal"]["signal_id"] == signal_id
            assert payload["event"]["to_status"] == (
                SIGNAL_ACTION_STATUSES[action].value
            )

    def test_no_orm_internals_are_exposed(
        self,
        client,
        action_database,
        alice,
    ) -> None:
        signal_id = create_signal(action_database, alice)
        token = login(client, alice["email"])

        payload = client.post(
            action_url(signal_id, "approve"),
            json={},
            headers=auth_header(token),
        ).json()

        assert "_sa_instance_state" not in json.dumps(payload)
        assert "extra_metadata" not in json.dumps(payload)
