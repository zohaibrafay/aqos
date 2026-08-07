"""
User, credential, session and preference repositories against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest
from sqlalchemy import text

from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.database.repository import RecordNotFoundError, RepositoryError
from aqos.users.models import (
    NotificationChannel,
    UserRole,
    UserStatus,
    UserTheme,
)
from aqos.users.repositories import (
    AuthenticationOutcome,
    UserCredentialRepository,
    UserPreferencesRepository,
    UserProfileRepository,
    UserSessionRepository,
)


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

VALID_PASSWORD = "Sup3rSecretPhrase"
OTHER_PASSWORD = "An0therGoodPhrase"
FAST_ITERATIONS = 1_000

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so the user repositories are NOT "
            "verified against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_user_tables(database: AqosDatabase) -> None:
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
def user_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; user repositories NOT verified.")

    apply_migrations(database)
    reset_user_tables(database)

    yield database

    reset_user_tables(database)
    database.dispose()


def create_user(session, email: str = "trader@example.com", **overrides):
    payload = {
        "email": email,
        "display_name": "Primary Trader",
        "created_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return UserProfileRepository(session).create_user(**payload)


def test_user_tables_and_procedures_exist(user_database) -> None:
    with user_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    tables = {str(row[0]) for row in rows}

    assert {
        "user_profiles",
        "user_credentials",
        "user_sessions",
        "user_preferences",
    } <= tables

    procedures = StoredProcedureService(user_database).list_procedures()

    assert "sp_aqos_user_status_counts" in procedures
    assert "sp_aqos_purge_expired_sessions" in procedures


def test_create_and_read_user(user_database) -> None:
    with user_database.session() as session:
        profile = create_user(session, metadata={"tier": 2})
        user_id = profile.user_id

    with user_database.read_session() as session:
        stored = UserProfileRepository(session).require(user_id)

        assert stored.email == "trader@example.com"
        assert stored.role == UserRole.TRADER
        assert stored.status == UserStatus.ACTIVE
        assert stored.extra_metadata == {"tier": 2}
        assert stored.can_trade is True


def test_email_uniqueness_is_enforced(user_database) -> None:
    with user_database.session() as session:
        create_user(session)

    with pytest.raises(RepositoryError, match="already exists"):
        with user_database.session() as session:
            create_user(session, email="TRADER@example.com")


def test_require_raises_for_missing_user(user_database) -> None:
    with user_database.read_session() as session:
        with pytest.raises(RecordNotFoundError, match="does not exist"):
            UserProfileRepository(session).require("user_missing")


def test_find_by_email_is_case_insensitive(user_database) -> None:
    with user_database.session() as session:
        profile = create_user(session)
        user_id = profile.user_id

    with user_database.read_session() as session:
        repository = UserProfileRepository(session)

        assert repository.find_by_email("TRADER@EXAMPLE.COM").user_id == user_id
        assert repository.find_by_email("nobody@example.com") is None


def test_list_users_filters_and_orders(user_database) -> None:
    with user_database.session() as session:
        create_user(session, email="a@example.com", created_at_utc=FIXED_NOW)
        create_user(
            session,
            email="b@example.com",
            created_at_utc=datetime(2026, 1, 2),
            role=UserRole.ANALYST,
        )
        create_user(
            session,
            email="c@example.com",
            created_at_utc=datetime(2026, 1, 3),
            status=UserStatus.DISABLED,
        )

    with user_database.read_session() as session:
        repository = UserProfileRepository(session)

        assert [user.email for user in repository.list_users()] == [
            "a@example.com",
            "b@example.com",
            "c@example.com",
        ]
        assert len(repository.list_users(status=UserStatus.ACTIVE)) == 2
        assert len(repository.list_users(role=UserRole.ANALYST)) == 1
        assert repository.count() == 3


def test_update_user_round_trip(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id

    with user_database.session() as session:
        updated = UserProfileRepository(session).update_user(
            user_id,
            display_name="Senior Trader",
            role=UserRole.ADMIN,
            timezone="Asia/Karachi",
            metadata={"tier": 3},
            updated_at_utc=datetime(2026, 2, 1),
        )

        assert updated.display_name == "Senior Trader"

    with user_database.read_session() as session:
        stored = UserProfileRepository(session).require(user_id)

        assert stored.role == UserRole.ADMIN
        assert stored.timezone == "Asia/Karachi"
        assert stored.extra_metadata == {"tier": 3}
        assert stored.updated_at_utc == datetime(2026, 2, 1)


def test_update_user_rejects_conflicting_email(user_database) -> None:
    with user_database.session() as session:
        first = create_user(session, email="a@example.com").user_id
        create_user(session, email="b@example.com")

    with pytest.raises(RepositoryError, match="already exists"):
        with user_database.session() as session:
            UserProfileRepository(session).update_user(first, email="b@example.com")


def test_set_status_blocks_trading(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id

    with user_database.session() as session:
        suspended = UserProfileRepository(session).set_status(
            user_id,
            UserStatus.SUSPENDED,
        )

        assert suspended.can_trade is False


def test_password_round_trip_and_authentication(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id

        UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        ).set_password(user_id, VALID_PASSWORD, created_at_utc=FIXED_NOW)

    with user_database.session() as session:
        credentials = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        )

        assert credentials.authenticate(
            user_id,
            VALID_PASSWORD,
            now_utc=datetime(2026, 1, 5, 9, 0, 0),
        ).authenticated is True

    with user_database.read_session() as session:
        stored = UserCredentialRepository(session).require(user_id)

        assert stored.last_login_at_utc == datetime(2026, 1, 5, 9, 0, 0)
        assert stored.failed_attempt_count == 0
        assert VALID_PASSWORD not in stored.password_hash


def test_password_rotation(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        credentials = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        )
        credentials.set_password(user_id, VALID_PASSWORD, created_at_utc=FIXED_NOW)
        credentials.set_password(
            user_id,
            OTHER_PASSWORD,
            created_at_utc=datetime(2026, 2, 1),
        )

    with user_database.session() as session:
        credentials = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        )

        assert credentials.authenticate(user_id, OTHER_PASSWORD).authenticated is True

    with user_database.session() as session:
        credentials = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        )

        assert credentials.authenticate(user_id, VALID_PASSWORD).authenticated is False


def test_failed_attempts_lock_the_account(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        ).set_password(user_id, VALID_PASSWORD)

    outcomes = []

    for minute in range(3):
        with user_database.session() as session:
            credentials = UserCredentialRepository(
                session,
                password_iterations=FAST_ITERATIONS,
                max_failed_attempts=3,
            )
            outcomes.append(
                credentials.authenticate(
                    user_id,
                    "WrongPassword1",
                    now_utc=datetime(2026, 1, 1, 0, minute, 0),
                )
            )

    assert outcomes[0].outcome == AuthenticationOutcome.INVALID_PASSWORD
    assert outcomes[1].failed_attempt_count == 2
    assert outcomes[2].outcome == AuthenticationOutcome.LOCKED

    with user_database.session() as session:
        credentials = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
            max_failed_attempts=3,
        )
        locked = credentials.authenticate(
            user_id,
            VALID_PASSWORD,
            now_utc=datetime(2026, 1, 1, 0, 5, 0),
        )

    assert locked.outcome == AuthenticationOutcome.LOCKED


def test_unlock_clears_the_lock(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        credentials = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
            max_failed_attempts=1,
        )
        credentials.set_password(user_id, VALID_PASSWORD)
        credentials.authenticate(user_id, "WrongPassword1", now_utc=FIXED_NOW)

    with user_database.session() as session:
        credentials = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        )
        unlocked = credentials.unlock(user_id)

        assert unlocked.locked_until_utc is None
        assert unlocked.failed_attempt_count == 0


def test_authenticate_without_credential(user_database) -> None:
    with user_database.read_session() as session:
        result = UserCredentialRepository(session).authenticate(
            "user_missing",
            VALID_PASSWORD,
        )

    assert result.outcome == AuthenticationOutcome.NO_CREDENTIAL

    with pytest.raises(PermissionError, match="no_credential"):
        result.raise_if_failed()


def test_session_issue_and_resolve(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        issued = UserSessionRepository(session, session_minutes=60).create_session(
            user_id,
            client_label="web",
            created_at_utc=FIXED_NOW,
        )
        token = issued.token
        session_id = issued.session.session_id

    with user_database.read_session() as session:
        sessions = UserSessionRepository(session)

        active = sessions.resolve_active_session(
            token,
            now_utc=datetime(2026, 1, 1, 0, 30, 0),
        )

        assert active is not None
        assert active.session_id == session_id
        assert active.client_label == "web"

        assert sessions.resolve_active_session(
            token,
            now_utc=datetime(2026, 1, 1, 2, 0, 0),
        ) is None
        assert sessions.resolve_active_session("unknown-token") is None


def test_session_revocation(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        issued = UserSessionRepository(session, session_minutes=60).create_session(
            user_id,
            created_at_utc=FIXED_NOW,
        )
        token = issued.token
        session_id = issued.session.session_id

    with user_database.session() as session:
        sessions = UserSessionRepository(session)

        assert sessions.revoke_session(
            session_id,
            revoked_at_utc=datetime(2026, 1, 1, 0, 10, 0),
        ) is True
        assert sessions.revoke_session(session_id) is False

    with user_database.read_session() as session:
        assert UserSessionRepository(session).resolve_active_session(
            token,
            now_utc=datetime(2026, 1, 1, 0, 20, 0),
        ) is None


def test_revoke_all_user_sessions(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        sessions = UserSessionRepository(session, session_minutes=60)
        sessions.create_session(user_id, created_at_utc=FIXED_NOW)
        sessions.create_session(user_id, created_at_utc=datetime(2026, 1, 1, 0, 5, 0))

    with user_database.session() as session:
        revoked = UserSessionRepository(session).revoke_user_sessions(
            user_id,
            revoked_at_utc=datetime(2026, 1, 1, 0, 10, 0),
        )

    assert revoked == 2

    with user_database.read_session() as session:
        assert UserSessionRepository(session).list_sessions(
            user_id,
            active_only=True,
            now_utc=datetime(2026, 1, 1, 0, 20, 0),
        ) == ()


def test_touch_session_records_last_seen(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        session_id = UserSessionRepository(
            session,
            session_minutes=60,
        ).create_session(user_id, created_at_utc=FIXED_NOW).session.session_id

    with user_database.session() as session:
        touched = UserSessionRepository(session).touch_session(
            session_id,
            seen_at_utc=datetime(2026, 1, 1, 0, 15, 0),
        )

        assert touched.last_seen_at_utc == datetime(2026, 1, 1, 0, 15, 0)


def test_purge_expired_sessions(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        sessions = UserSessionRepository(session, session_minutes=60)
        sessions.create_session(user_id, created_at_utc=FIXED_NOW)
        sessions.create_session(user_id, created_at_utc=datetime(2026, 1, 1, 5, 0, 0))

    with user_database.session() as session:
        purged = UserSessionRepository(session).purge_expired_sessions(
            now_utc=datetime(2026, 1, 1, 2, 0, 0)
        )

    assert purged == 1

    with user_database.read_session() as session:
        assert len(UserSessionRepository(session).list_sessions(user_id)) == 1


def test_purge_expired_sessions_stored_procedure(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        UserSessionRepository(session, session_minutes=60).create_session(
            user_id,
            created_at_utc=FIXED_NOW,
        )

    result = StoredProcedureService(user_database).call(
        "sp_aqos_purge_expired_sessions",
        parameters=(datetime(2026, 1, 2, 0, 0, 0),),
        out_parameters=("deleted",),
    )

    assert result.out_values["deleted"] == 1


def test_user_status_counts_stored_procedure(user_database) -> None:
    with user_database.session() as session:
        create_user(session, email="a@example.com")
        create_user(
            session,
            email="b@example.com",
            status=UserStatus.SUSPENDED,
        )

    result = StoredProcedureService(user_database).call_read_only(
        "sp_aqos_user_status_counts"
    )

    counts = {row["status"]: row["total"] for row in result.rows}

    assert counts == {"active": 1, "suspended": 1}


def test_preferences_get_or_create_is_idempotent(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        first = UserPreferencesRepository(session).get_or_create_for_user(
            user_id,
            created_at_utc=FIXED_NOW,
        )
        preferences_id = first.preferences_id

    with user_database.session() as session:
        second = UserPreferencesRepository(session).get_or_create_for_user(user_id)

        assert second.preferences_id == preferences_id
        assert second.notification_channels == [NotificationChannel.IN_APP.value]


def test_preferences_update_and_reset(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        UserPreferencesRepository(session).get_or_create_for_user(
            user_id,
            created_at_utc=FIXED_NOW,
        )

    with user_database.session() as session:
        updated = UserPreferencesRepository(session).update_for_user(
            user_id,
            theme=UserTheme.DARK,
            default_currency="eur",
            landing_page="signals",
            notification_channels=["email", "push"],
            email_notifications_enabled=False,
            metadata={"beta": True},
            updated_at_utc=datetime(2026, 2, 1),
        )

        assert updated.default_currency == "EUR"

    with user_database.read_session() as session:
        stored = UserPreferencesRepository(session).get_for_user(user_id)

        assert stored.theme == UserTheme.DARK
        assert stored.landing_page == "signals"
        assert stored.notification_channels == ["email", "push"]
        assert stored.email_notifications_enabled is False
        assert stored.extra_metadata == {"beta": True}

    with user_database.session() as session:
        reset = UserPreferencesRepository(session).reset_for_user(user_id)

        assert reset.theme == UserTheme.SYSTEM
        assert reset.landing_page == "dashboard"
        assert reset.default_currency == "USD"


def test_preferences_update_requires_existing_row(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id

    with pytest.raises(RepositoryError, match="do not exist"):
        with user_database.session() as session:
            UserPreferencesRepository(session).update_for_user(
                user_id,
                theme=UserTheme.DARK,
            )


def test_deleting_a_user_cascades(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id

        UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        ).set_password(user_id, VALID_PASSWORD)
        UserSessionRepository(session).create_session(user_id)
        UserPreferencesRepository(session).get_or_create_for_user(user_id)

    with user_database.session() as session:
        assert UserProfileRepository(session).delete_user(user_id) is True

    with user_database.read_session() as session:
        assert UserProfileRepository(session).get(user_id) is None
        assert UserCredentialRepository(session).get(user_id) is None
        assert UserSessionRepository(session).list_sessions(user_id) == ()
        assert UserPreferencesRepository(session).get_for_user(user_id) is None


def test_rollback_leaves_no_partial_user(user_database) -> None:
    with pytest.raises(RuntimeError, match="deliberate failure"):
        with user_database.session() as session:
            create_user(session, email="rollback@example.com")
            raise RuntimeError("deliberate failure")

    with user_database.read_session() as session:
        assert UserProfileRepository(session).find_by_email(
            "rollback@example.com"
        ) is None


def test_a_rolled_back_failure_loses_the_lockout_bookkeeping(
    user_database,
) -> None:
    """
    The hazard a caller must not walk into.

    ``authenticate`` stages the attempt counter; the caller owns the commit. A
    caller that raises on a failed login and rolls back discards the count it
    just incremented, so the threshold is never reached and brute-force
    protection is silently absent. This pins that behaviour so the requirement
    on callers is visible rather than folklore.
    """

    with user_database.session() as session:
        user_id = create_user(session).user_id
        UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        ).set_password(user_id, VALID_PASSWORD)

    for _ in range(5):
        with pytest.raises(RuntimeError, match="handler failed"):
            with user_database.session() as session:
                UserCredentialRepository(
                    session,
                    password_iterations=FAST_ITERATIONS,
                    max_failed_attempts=3,
                ).authenticate(user_id, "WrongPassword1")

                # What a naive HTTP handler does: report the failure by raising.
                raise RuntimeError("handler failed")

    with user_database.read_session() as session:
        credential = UserCredentialRepository(session).require(user_id)

        assert credential.failed_attempt_count == 0
        assert credential.locked_until_utc is None


def test_a_committed_failure_keeps_the_lockout_bookkeeping(
    user_database,
) -> None:
    """The same five attempts, committed, do reach the threshold."""

    with user_database.session() as session:
        user_id = create_user(session).user_id
        UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        ).set_password(user_id, VALID_PASSWORD)

    for _ in range(3):
        with user_database.session() as session:
            UserCredentialRepository(
                session,
                password_iterations=FAST_ITERATIONS,
                max_failed_attempts=3,
            ).authenticate(user_id, "WrongPassword1")

    with user_database.read_session() as session:
        credential = UserCredentialRepository(session).require(user_id)

        assert credential.failed_attempt_count == 3
        assert credential.locked_until_utc is not None


def test_a_persisted_lockout_survives_a_new_session(user_database) -> None:
    """
    A lockout read back from MySQL still refuses the correct password.

    The earlier lockout test works within one process; this proves the state
    that matters is in the database, not in a live object.
    """

    with user_database.session() as session:
        user_id = create_user(session).user_id
        UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        ).set_password(user_id, VALID_PASSWORD)

    for _ in range(3):
        with user_database.session() as session:
            UserCredentialRepository(
                session,
                password_iterations=FAST_ITERATIONS,
                max_failed_attempts=3,
            ).authenticate(user_id, "WrongPassword1")

    with user_database.read_session() as session:
        stored = session.execute(
            text(
                "SELECT locked_until_utc, failed_attempt_count "
                "FROM user_credentials WHERE user_id = :user_id"
            ),
            {"user_id": user_id},
        ).one()

    assert stored[0] is not None
    assert stored[1] == 3

    with user_database.session() as session:
        result = UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
            max_failed_attempts=3,
        ).authenticate(user_id, VALID_PASSWORD)

    assert result.outcome == AuthenticationOutcome.LOCKED
    assert result.authenticated is False


def test_stored_credentials_never_expose_an_attackable_verifier(
    user_database,
) -> None:
    """
    A serialized credential must not be an offline cracking oracle.

    The salt plus any part of the derived key is enough to confirm a guess:
    derive a candidate with the same salt and compare. Neither may appear.
    """

    with user_database.session() as session:
        user_id = create_user(session).user_id
        UserCredentialRepository(
            session,
            password_iterations=FAST_ITERATIONS,
        ).set_password(user_id, VALID_PASSWORD)

    with user_database.read_session() as session:
        credential = UserCredentialRepository(session).require(user_id)
        parsed = credential.parsed_password_hash()
        rendered = json.dumps(credential.to_dict())

    assert parsed.salt_hex not in rendered
    assert parsed.hash_hex not in rendered
    assert parsed.hash_hex[:8] not in rendered
    assert VALID_PASSWORD not in rendered
    assert "salt" not in rendered.lower()
    assert "preview" not in rendered.lower()


def test_stored_sessions_never_expose_token_material(user_database) -> None:
    with user_database.session() as session:
        user_id = create_user(session).user_id
        issued = UserSessionRepository(session).create_session(user_id=user_id)
        token = issued.token
        session_id = issued.session.session_id

    with user_database.read_session() as session:
        record = UserSessionRepository(session).require(session_id)
        rendered = json.dumps(record.to_dict())

    assert token not in rendered
    assert record.token_hash not in rendered
    assert "token_hash" not in rendered
