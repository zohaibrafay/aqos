from __future__ import annotations

import pytest

from aqos.persistence.auth import (
    AQOS_AUTH_VERSION,
    AuthenticationOutcome,
    AuthenticationResult,
    UserCredential,
    UserCredentialRepository,
    UserSession,
    UserSessionRepository,
    build_lockout_timestamp,
    build_session_expiry,
)
from aqos.persistence.database import AqosDatabase
from aqos.persistence.passwords import hash_password, hash_session_token
from aqos.persistence.users import UserProfileRepository


VALID_PASSWORD = "Sup3rSecretPhrase"
OTHER_PASSWORD = "An0therGoodPhrase"
FAST_ITERATIONS = 1_000


@pytest.fixture
def auth_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def stored_user(auth_database):
    repository = UserProfileRepository(auth_database)

    return repository.create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def credentials(auth_database) -> UserCredentialRepository:
    return UserCredentialRepository(
        auth_database,
        password_iterations=FAST_ITERATIONS,
        max_failed_attempts=3,
        lockout_minutes=15,
    )


@pytest.fixture
def sessions(auth_database) -> UserSessionRepository:
    return UserSessionRepository(auth_database, session_minutes=60)


def test_auth_version_is_exposed() -> None:
    assert AQOS_AUTH_VERSION == "1.0"


def test_credential_validation() -> None:
    valid = {
        "user_id": "user_1",
        "password_hash": "pbkdf2_sha256$1000$aa$bb",
        "created_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
        "password_updated_at_utc": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(ValueError, match="user_id cannot be empty"):
        UserCredential(**{**valid, "user_id": " "})

    with pytest.raises(ValueError, match="password_hash cannot be empty"):
        UserCredential(**{**valid, "password_hash": ""})

    with pytest.raises(ValueError, match="failed_attempt_count cannot be negative"):
        UserCredential(**valid, failed_attempt_count=-1)

    with pytest.raises(ValueError, match="created_at_utc cannot be empty"):
        UserCredential(**{**valid, "created_at_utc": " "})


def test_credential_lock_state() -> None:
    credential = UserCredential(
        user_id="user_1",
        password_hash="pbkdf2_sha256$1000$aa$bb",
        created_at_utc="2026-01-01T00:00:00Z",
        updated_at_utc="2026-01-01T00:00:00Z",
        password_updated_at_utc="2026-01-01T00:00:00Z",
        locked_until_utc="2026-01-01T01:00:00Z",
    )

    assert credential.is_locked("2026-01-01T00:30:00Z") is True
    assert credential.is_locked("2026-01-01T02:00:00Z") is False


def test_credential_dict_hides_verifier() -> None:
    password_hash = hash_password(VALID_PASSWORD, iterations=FAST_ITERATIONS)

    credential = UserCredential(
        user_id="user_1",
        password_hash=password_hash.to_storage_string(),
        created_at_utc="2026-01-01T00:00:00Z",
        updated_at_utc="2026-01-01T00:00:00Z",
        password_updated_at_utc="2026-01-01T00:00:00Z",
    )

    payload = credential.to_dict()

    assert payload["password_hash"]["algorithm"] == "pbkdf2_sha256"
    assert "hash_hex" not in payload["password_hash"]
    assert password_hash.hash_hex not in str(payload)


def test_authentication_result_helpers() -> None:
    success = AuthenticationResult(
        outcome=AuthenticationOutcome.SUCCESS,
        user_id="user_1",
    )

    assert success.authenticated is True
    success.raise_if_failed()

    failure = AuthenticationResult(
        outcome=AuthenticationOutcome.INVALID_PASSWORD,
        user_id="user_1",
    )

    assert failure.to_dict()["authenticated"] is False

    with pytest.raises(PermissionError, match="invalid_password"):
        failure.raise_if_failed()


def test_build_lockout_and_session_timestamps() -> None:
    assert build_lockout_timestamp("2026-01-01T00:00:00Z", 15) == (
        "2026-01-01T00:15:00Z"
    )
    assert build_session_expiry("2026-01-01T00:00:00Z", 60) == "2026-01-01T01:00:00Z"

    with pytest.raises(ValueError, match="lockout_minutes must be at least 1"):
        build_lockout_timestamp("2026-01-01T00:00:00Z", 0)

    with pytest.raises(ValueError, match="session_minutes must be at least 1"):
        build_session_expiry("2026-01-01T00:00:00Z", 0)


def test_credential_repository_rejects_bad_configuration(auth_database) -> None:
    with pytest.raises(ValueError, match="max_failed_attempts must be at least 1"):
        UserCredentialRepository(auth_database, max_failed_attempts=0)


def test_set_password_creates_credential(credentials, stored_user) -> None:
    credential = credentials.set_password(
        stored_user.user_id,
        VALID_PASSWORD,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert credential.user_id == stored_user.user_id
    assert credential.failed_attempt_count == 0
    assert credential.password_hash.startswith("pbkdf2_sha256$")

    stored = credentials.require_credential(stored_user.user_id)

    assert stored.password_hash == credential.password_hash


def test_set_password_enforces_policy(credentials, stored_user) -> None:
    with pytest.raises(ValueError, match="Password rejected"):
        credentials.set_password(stored_user.user_id, "weak")


def test_set_password_rotates_existing_credential(credentials, stored_user) -> None:
    first = credentials.set_password(
        stored_user.user_id,
        VALID_PASSWORD,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    second = credentials.set_password(
        stored_user.user_id,
        OTHER_PASSWORD,
        created_at_utc="2026-02-01T00:00:00Z",
    )

    assert second.created_at_utc == first.created_at_utc
    assert second.password_updated_at_utc == "2026-02-01T00:00:00Z"
    assert second.password_hash != first.password_hash

    assert credentials.authenticate(stored_user.user_id, OTHER_PASSWORD).authenticated
    assert not credentials.authenticate(stored_user.user_id, VALID_PASSWORD).authenticated


def test_authenticate_success_records_login(credentials, stored_user) -> None:
    credentials.set_password(stored_user.user_id, VALID_PASSWORD)

    result = credentials.authenticate(
        stored_user.user_id,
        VALID_PASSWORD,
        now_utc="2026-01-05T09:00:00Z",
    )

    assert result.outcome == AuthenticationOutcome.SUCCESS

    credential = credentials.require_credential(stored_user.user_id)

    assert credential.last_login_at_utc == "2026-01-05T09:00:00Z"
    assert credential.failed_attempt_count == 0


def test_authenticate_without_credential(credentials) -> None:
    result = credentials.authenticate("user_missing", VALID_PASSWORD)

    assert result.outcome == AuthenticationOutcome.NO_CREDENTIAL
    assert result.authenticated is False


def test_require_credential_raises_when_missing(credentials) -> None:
    with pytest.raises(LookupError, match="does not exist"):
        credentials.require_credential("user_missing")


def test_failed_attempts_accumulate_then_lock(credentials, stored_user) -> None:
    credentials.set_password(stored_user.user_id, VALID_PASSWORD)

    first = credentials.authenticate(
        stored_user.user_id,
        "WrongPassword1",
        now_utc="2026-01-01T00:00:00Z",
    )
    second = credentials.authenticate(
        stored_user.user_id,
        "WrongPassword1",
        now_utc="2026-01-01T00:01:00Z",
    )
    third = credentials.authenticate(
        stored_user.user_id,
        "WrongPassword1",
        now_utc="2026-01-01T00:02:00Z",
    )

    assert first.outcome == AuthenticationOutcome.INVALID_PASSWORD
    assert first.failed_attempt_count == 1
    assert second.failed_attempt_count == 2
    assert third.outcome == AuthenticationOutcome.LOCKED
    assert third.locked_until_utc == "2026-01-01T00:17:00Z"


def test_locked_credential_rejects_correct_password(credentials, stored_user) -> None:
    credentials.set_password(stored_user.user_id, VALID_PASSWORD)

    for minute in range(3):
        credentials.authenticate(
            stored_user.user_id,
            "WrongPassword1",
            now_utc=f"2026-01-01T00:0{minute}:00Z",
        )

    locked = credentials.authenticate(
        stored_user.user_id,
        VALID_PASSWORD,
        now_utc="2026-01-01T00:05:00Z",
    )

    assert locked.outcome == AuthenticationOutcome.LOCKED


def test_lock_expires_naturally(credentials, stored_user) -> None:
    credentials.set_password(stored_user.user_id, VALID_PASSWORD)

    for minute in range(3):
        credentials.authenticate(
            stored_user.user_id,
            "WrongPassword1",
            now_utc=f"2026-01-01T00:0{minute}:00Z",
        )

    result = credentials.authenticate(
        stored_user.user_id,
        VALID_PASSWORD,
        now_utc="2026-01-01T01:00:00Z",
    )

    assert result.outcome == AuthenticationOutcome.SUCCESS


def test_unlock_clears_lock(credentials, stored_user) -> None:
    credentials.set_password(stored_user.user_id, VALID_PASSWORD)

    for minute in range(3):
        credentials.authenticate(
            stored_user.user_id,
            "WrongPassword1",
            now_utc=f"2026-01-01T00:0{minute}:00Z",
        )

    unlocked = credentials.unlock(stored_user.user_id)

    assert unlocked.locked_until_utc is None
    assert unlocked.failed_attempt_count == 0
    assert credentials.authenticate(
        stored_user.user_id,
        VALID_PASSWORD,
        now_utc="2026-01-01T00:05:00Z",
    ).authenticated


def test_delete_credential(credentials, stored_user) -> None:
    credentials.set_password(stored_user.user_id, VALID_PASSWORD)

    assert credentials.delete_credential(stored_user.user_id) is True
    assert credentials.get_credential(stored_user.user_id) is None
    assert credentials.delete_credential(stored_user.user_id) is False


def test_deleting_user_cascades_to_credential(
    auth_database,
    credentials,
    stored_user,
) -> None:
    credentials.set_password(stored_user.user_id, VALID_PASSWORD)

    UserProfileRepository(auth_database).delete_user(stored_user.user_id)

    assert credentials.get_credential(stored_user.user_id) is None


def test_session_validation() -> None:
    with pytest.raises(ValueError, match="session_id cannot be empty"):
        UserSession(
            session_id=" ",
            user_id="user_1",
            token_hash="abc",
            created_at_utc="2026-01-01T00:00:00Z",
            expires_at_utc="2026-01-01T01:00:00Z",
        )

    with pytest.raises(ValueError, match="token_hash cannot be empty"):
        UserSession(
            session_id="s",
            user_id="user_1",
            token_hash="",
            created_at_utc="2026-01-01T00:00:00Z",
            expires_at_utc="2026-01-01T01:00:00Z",
        )

    with pytest.raises(ValueError, match="expires_at_utc must be after"):
        UserSession(
            session_id="s",
            user_id="user_1",
            token_hash="abc",
            created_at_utc="2026-01-01T01:00:00Z",
            expires_at_utc="2026-01-01T00:00:00Z",
        )


def test_create_session_returns_token_once(sessions, stored_user) -> None:
    issued = sessions.create_session(
        stored_user.user_id,
        client_label="web",
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert issued.token
    assert issued.session.token_hash == hash_session_token(issued.token)
    assert issued.session.expires_at_utc == "2026-01-01T01:00:00Z"
    assert issued.session.client_label == "web"
    assert issued.to_dict()["token_issued"] is True
    assert issued.token not in str(issued.session.to_dict())


def test_resolve_active_session(sessions, stored_user) -> None:
    issued = sessions.create_session(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    active = sessions.resolve_active_session(
        issued.token,
        now_utc="2026-01-01T00:30:00Z",
    )

    assert active is not None
    assert active.session_id == issued.session.session_id

    assert sessions.resolve_active_session("unknown-token") is None


def test_resolve_rejects_expired_session(sessions, stored_user) -> None:
    issued = sessions.create_session(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert issued.session.is_expired("2026-01-01T02:00:00Z") is True
    assert sessions.resolve_active_session(
        issued.token,
        now_utc="2026-01-01T02:00:00Z",
    ) is None


def test_revoke_session(sessions, stored_user) -> None:
    issued = sessions.create_session(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert sessions.revoke_session(
        issued.session.session_id,
        revoked_at_utc="2026-01-01T00:10:00Z",
    ) is True
    assert sessions.revoke_session(issued.session.session_id) is False

    revoked = sessions.get_session(issued.session.session_id)

    assert revoked is not None
    assert revoked.is_revoked is True
    assert sessions.resolve_active_session(
        issued.token,
        now_utc="2026-01-01T00:20:00Z",
    ) is None


def test_revoke_user_sessions(sessions, stored_user) -> None:
    sessions.create_session(stored_user.user_id, created_at_utc="2026-01-01T00:00:00Z")
    sessions.create_session(stored_user.user_id, created_at_utc="2026-01-01T00:05:00Z")

    revoked = sessions.revoke_user_sessions(
        stored_user.user_id,
        revoked_at_utc="2026-01-01T00:10:00Z",
    )

    assert revoked == 2
    assert sessions.list_sessions(
        stored_user.user_id,
        active_only=True,
        now_utc="2026-01-01T00:20:00Z",
    ) == ()


def test_list_sessions_orders_and_filters(sessions, stored_user) -> None:
    first = sessions.create_session(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    sessions.create_session(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:05:00Z",
    )
    sessions.revoke_session(
        first.session.session_id,
        revoked_at_utc="2026-01-01T00:06:00Z",
    )

    all_sessions = sessions.list_sessions(stored_user.user_id)
    active = sessions.list_sessions(
        stored_user.user_id,
        active_only=True,
        now_utc="2026-01-01T00:30:00Z",
    )

    assert len(all_sessions) == 2
    assert all_sessions[0].created_at_utc == "2026-01-01T00:00:00Z"
    assert len(active) == 1
    assert active[0].created_at_utc == "2026-01-01T00:05:00Z"


def test_touch_session_updates_last_seen(sessions, stored_user) -> None:
    issued = sessions.create_session(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    touched = sessions.touch_session(
        issued.session.session_id,
        seen_at_utc="2026-01-01T00:15:00Z",
    )

    assert touched.last_seen_at_utc == "2026-01-01T00:15:00Z"


def test_touch_session_requires_existing_session(sessions) -> None:
    with pytest.raises(LookupError, match="does not exist"):
        sessions.touch_session("session_missing")


def test_purge_expired_sessions(sessions, stored_user) -> None:
    sessions.create_session(stored_user.user_id, created_at_utc="2026-01-01T00:00:00Z")
    sessions.create_session(stored_user.user_id, created_at_utc="2026-01-01T05:00:00Z")

    purged = sessions.purge_expired_sessions(now_utc="2026-01-01T02:00:00Z")

    assert purged == 1
    assert len(sessions.list_sessions(stored_user.user_id)) == 1


def test_session_repository_rejects_bad_configuration(auth_database) -> None:
    with pytest.raises(ValueError, match="session_minutes must be at least 1"):
        UserSessionRepository(auth_database, session_minutes=0)


def test_deleting_user_cascades_to_sessions(
    auth_database,
    sessions,
    stored_user,
) -> None:
    sessions.create_session(stored_user.user_id)

    UserProfileRepository(auth_database).delete_user(stored_user.user_id)

    assert sessions.list_sessions(stored_user.user_id) == ()
