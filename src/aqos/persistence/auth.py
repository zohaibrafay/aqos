from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from aqos.common.time_utils import add_minutes, format_datetime, parse_datetime, utc_now
from aqos.persistence.database import AqosDatabase
from aqos.persistence.passwords import (
    DEFAULT_PASSWORD_ITERATIONS,
    PasswordHash,
    generate_session_token,
    hash_password,
    hash_session_token,
    parse_password_hash,
    verify_password,
)
from aqos.persistence.records import (
    build_record_id,
    decode_json_field,
    encode_json_field,
    normalize_required_text,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema


AQOS_AUTH_VERSION = "1.0"

DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_LOCKOUT_MINUTES = 15
DEFAULT_SESSION_MINUTES = 60 * 12


class AuthenticationOutcome(str, Enum):
    SUCCESS = "success"
    INVALID_PASSWORD = "invalid_password"
    NO_CREDENTIAL = "no_credential"
    LOCKED = "locked"


@dataclass(frozen=True)
class UserCredential:
    """
    Stored authentication material for one user.

    ``password_hash`` is always a PBKDF2 verifier string; plaintext passwords
    never reach this record.
    """

    user_id: str
    password_hash: str
    created_at_utc: str
    updated_at_utc: str
    password_updated_at_utc: str
    failed_attempt_count: int = 0
    locked_until_utc: str | None = None
    last_login_at_utc: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.password_hash.strip():
            raise ValueError("password_hash cannot be empty.")

        if self.failed_attempt_count < 0:
            raise ValueError("failed_attempt_count cannot be negative.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

    def parsed_password_hash(self) -> PasswordHash:
        return parse_password_hash(self.password_hash)

    def is_locked(self, now_utc: str | None = None) -> bool:
        if self.locked_until_utc is None:
            return False

        reference = parse_datetime(now_utc) if now_utc else utc_now()

        return parse_datetime(self.locked_until_utc) > reference

    def to_dict(self) -> dict[str, Any]:
        """Serialize without leaking the password verifier."""

        return {
            "user_id": self.user_id,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "password_updated_at_utc": self.password_updated_at_utc,
            "failed_attempt_count": self.failed_attempt_count,
            "locked_until_utc": self.locked_until_utc,
            "last_login_at_utc": self.last_login_at_utc,
            "password_hash": self.parsed_password_hash().to_dict(),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class AuthenticationResult:
    outcome: AuthenticationOutcome
    user_id: str
    failed_attempt_count: int = 0
    locked_until_utc: str | None = None

    @property
    def authenticated(self) -> bool:
        return self.outcome == AuthenticationOutcome.SUCCESS

    def raise_if_failed(self) -> None:
        if self.authenticated:
            return

        raise PermissionError(
            f"Authentication failed for {self.user_id}: {self.outcome.value}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "authenticated": self.authenticated,
            "user_id": self.user_id,
            "failed_attempt_count": self.failed_attempt_count,
            "locked_until_utc": self.locked_until_utc,
        }


@dataclass(frozen=True)
class UserSession:
    session_id: str
    user_id: str
    token_hash: str
    created_at_utc: str
    expires_at_utc: str
    revoked_at_utc: str | None = None
    last_seen_at_utc: str | None = None
    client_label: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.session_id.strip():
            raise ValueError("session_id cannot be empty.")

        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.token_hash.strip():
            raise ValueError("token_hash cannot be empty.")

        if parse_datetime(self.expires_at_utc) <= parse_datetime(self.created_at_utc):
            raise ValueError("expires_at_utc must be after created_at_utc.")

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at_utc is not None

    def is_expired(self, now_utc: str | None = None) -> bool:
        reference = parse_datetime(now_utc) if now_utc else utc_now()

        return parse_datetime(self.expires_at_utc) <= reference

    def is_active(self, now_utc: str | None = None) -> bool:
        return not self.is_revoked and not self.is_expired(now_utc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize without exposing the session token hash."""

        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at_utc": self.created_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "revoked_at_utc": self.revoked_at_utc,
            "last_seen_at_utc": self.last_seen_at_utc,
            "client_label": self.client_label,
            "is_revoked": self.is_revoked,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class IssuedSession:
    """A freshly created session plus its raw token, returned exactly once."""

    session: UserSession
    token: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "session": self.session.to_dict(),
            "token_issued": True,
        }


def build_user_credential_from_row(row: dict[str, Any]) -> UserCredential:
    return UserCredential(
        user_id=str(row["user_id"]),
        password_hash=str(row["password_hash"]),
        created_at_utc=str(row["created_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        password_updated_at_utc=str(row["password_updated_at_utc"]),
        failed_attempt_count=int(row["failed_attempt_count"]),
        locked_until_utc=row.get("locked_until_utc"),
        last_login_at_utc=row.get("last_login_at_utc"),
        metadata=decode_json_field(row.get("metadata")),
    )


def build_user_session_from_row(row: dict[str, Any]) -> UserSession:
    return UserSession(
        session_id=str(row["session_id"]),
        user_id=str(row["user_id"]),
        token_hash=str(row["token_hash"]),
        created_at_utc=str(row["created_at_utc"]),
        expires_at_utc=str(row["expires_at_utc"]),
        revoked_at_utc=row.get("revoked_at_utc"),
        last_seen_at_utc=row.get("last_seen_at_utc"),
        client_label=row.get("client_label"),
        metadata=decode_json_field(row.get("metadata")),
    )


def build_lockout_timestamp(
    now_utc: str | None = None,
    lockout_minutes: int = DEFAULT_LOCKOUT_MINUTES,
) -> str:
    if lockout_minutes < 1:
        raise ValueError("lockout_minutes must be at least 1.")

    reference = parse_datetime(now_utc) if now_utc else utc_now()

    return format_datetime(add_minutes(reference, lockout_minutes))


def build_session_expiry(
    now_utc: str | None = None,
    session_minutes: int = DEFAULT_SESSION_MINUTES,
) -> str:
    if session_minutes < 1:
        raise ValueError("session_minutes must be at least 1.")

    reference = parse_datetime(now_utc) if now_utc else utc_now()

    return format_datetime(add_minutes(reference, session_minutes))


class UserCredentialRepository:
    """Password verifiers and lockout state, one row per user."""

    def __init__(
        self,
        database: AqosDatabase,
        password_iterations: int = DEFAULT_PASSWORD_ITERATIONS,
        max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
        lockout_minutes: int = DEFAULT_LOCKOUT_MINUTES,
    ) -> None:
        if max_failed_attempts < 1:
            raise ValueError("max_failed_attempts must be at least 1.")

        self.database = database
        self.password_iterations = password_iterations
        self.max_failed_attempts = max_failed_attempts
        self.lockout_minutes = lockout_minutes

        ensure_aqos_schema(database)

    def get_credential(self, user_id: str) -> UserCredential | None:
        row = self.database.query_one(
            "SELECT * FROM user_credentials WHERE user_id = ?;",
            (user_id,),
        )

        return build_user_credential_from_row(row) if row is not None else None

    def require_credential(self, user_id: str) -> UserCredential:
        credential = self.get_credential(user_id)

        if credential is None:
            raise LookupError(f"User credential does not exist: {user_id}")

        return credential

    def set_password(
        self,
        user_id: str,
        password: str,
        enforce_policy: bool = True,
        created_at_utc: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserCredential:
        password_hash = hash_password(
            password=password,
            iterations=self.password_iterations,
            enforce_policy=enforce_policy,
        ).to_storage_string()

        timestamp = created_at_utc or record_utc_now()
        existing = self.get_credential(user_id)

        credential = UserCredential(
            user_id=normalize_required_text(user_id, "user_id"),
            password_hash=password_hash,
            created_at_utc=existing.created_at_utc if existing else timestamp,
            updated_at_utc=timestamp,
            password_updated_at_utc=timestamp,
            failed_attempt_count=0,
            locked_until_utc=None,
            last_login_at_utc=existing.last_login_at_utc if existing else None,
            metadata=(
                metadata
                if metadata is not None
                else (existing.metadata if existing else {})
            ),
        )

        if existing is None:
            self._insert(credential)
        else:
            self._update(credential)

        return credential

    def authenticate(
        self,
        user_id: str,
        password: str,
        now_utc: str | None = None,
    ) -> AuthenticationResult:
        credential = self.get_credential(user_id)

        if credential is None:
            return AuthenticationResult(
                outcome=AuthenticationOutcome.NO_CREDENTIAL,
                user_id=user_id,
            )

        if credential.is_locked(now_utc):
            return AuthenticationResult(
                outcome=AuthenticationOutcome.LOCKED,
                user_id=user_id,
                failed_attempt_count=credential.failed_attempt_count,
                locked_until_utc=credential.locked_until_utc,
            )

        timestamp = now_utc or record_utc_now()

        if not verify_password(password, credential.password_hash):
            return self._register_failure(credential, timestamp)

        self._update(
            UserCredential(
                user_id=credential.user_id,
                password_hash=credential.password_hash,
                created_at_utc=credential.created_at_utc,
                updated_at_utc=timestamp,
                password_updated_at_utc=credential.password_updated_at_utc,
                failed_attempt_count=0,
                locked_until_utc=None,
                last_login_at_utc=timestamp,
                metadata=credential.metadata,
            )
        )

        return AuthenticationResult(
            outcome=AuthenticationOutcome.SUCCESS,
            user_id=user_id,
        )

    def unlock(
        self,
        user_id: str,
        updated_at_utc: str | None = None,
    ) -> UserCredential:
        credential = self.require_credential(user_id)

        unlocked = UserCredential(
            user_id=credential.user_id,
            password_hash=credential.password_hash,
            created_at_utc=credential.created_at_utc,
            updated_at_utc=updated_at_utc or record_utc_now(),
            password_updated_at_utc=credential.password_updated_at_utc,
            failed_attempt_count=0,
            locked_until_utc=None,
            last_login_at_utc=credential.last_login_at_utc,
            metadata=credential.metadata,
        )

        self._update(unlocked)

        return unlocked

    def delete_credential(self, user_id: str) -> bool:
        cursor = self.database.execute(
            "DELETE FROM user_credentials WHERE user_id = ?;",
            (user_id,),
        )

        return cursor.rowcount > 0

    def _register_failure(
        self,
        credential: UserCredential,
        timestamp: str,
    ) -> AuthenticationResult:
        attempts = credential.failed_attempt_count + 1

        locked_until = (
            build_lockout_timestamp(timestamp, self.lockout_minutes)
            if attempts >= self.max_failed_attempts
            else None
        )

        self._update(
            UserCredential(
                user_id=credential.user_id,
                password_hash=credential.password_hash,
                created_at_utc=credential.created_at_utc,
                updated_at_utc=timestamp,
                password_updated_at_utc=credential.password_updated_at_utc,
                failed_attempt_count=attempts,
                locked_until_utc=locked_until,
                last_login_at_utc=credential.last_login_at_utc,
                metadata=credential.metadata,
            )
        )

        return AuthenticationResult(
            outcome=(
                AuthenticationOutcome.LOCKED
                if locked_until is not None
                else AuthenticationOutcome.INVALID_PASSWORD
            ),
            user_id=credential.user_id,
            failed_attempt_count=attempts,
            locked_until_utc=locked_until,
        )

    def _insert(self, credential: UserCredential) -> None:
        self.database.execute(
            """
            INSERT INTO user_credentials (
                user_id, password_hash, failed_attempt_count, locked_until_utc,
                last_login_at_utc, password_updated_at_utc, created_at_utc,
                updated_at_utc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                credential.user_id,
                credential.password_hash,
                credential.failed_attempt_count,
                credential.locked_until_utc,
                credential.last_login_at_utc,
                credential.password_updated_at_utc,
                credential.created_at_utc,
                credential.updated_at_utc,
                encode_json_field(credential.metadata),
            ),
        )

    def _update(self, credential: UserCredential) -> None:
        self.database.execute(
            """
            UPDATE user_credentials
            SET password_hash = ?, failed_attempt_count = ?, locked_until_utc = ?,
                last_login_at_utc = ?, password_updated_at_utc = ?,
                updated_at_utc = ?, metadata = ?
            WHERE user_id = ?;
            """,
            (
                credential.password_hash,
                credential.failed_attempt_count,
                credential.locked_until_utc,
                credential.last_login_at_utc,
                credential.password_updated_at_utc,
                credential.updated_at_utc,
                encode_json_field(credential.metadata),
                credential.user_id,
            ),
        )


class UserSessionRepository:
    """Opaque session tokens stored only as SHA-256 hashes."""

    def __init__(
        self,
        database: AqosDatabase,
        session_minutes: int = DEFAULT_SESSION_MINUTES,
    ) -> None:
        if session_minutes < 1:
            raise ValueError("session_minutes must be at least 1.")

        self.database = database
        self.session_minutes = session_minutes

        ensure_aqos_schema(database)

    def create_session(
        self,
        user_id: str,
        client_label: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at_utc: str | None = None,
        session_minutes: int | None = None,
        session_id: str | None = None,
        token: str | None = None,
    ) -> IssuedSession:
        raw_token = token or generate_session_token()
        timestamp = created_at_utc or record_utc_now()

        session = UserSession(
            session_id=session_id or build_record_id("session"),
            user_id=normalize_required_text(user_id, "user_id"),
            token_hash=hash_session_token(raw_token),
            created_at_utc=timestamp,
            expires_at_utc=build_session_expiry(
                now_utc=timestamp,
                session_minutes=session_minutes or self.session_minutes,
            ),
            client_label=client_label,
            metadata=metadata or {},
        )

        self.database.execute(
            """
            INSERT INTO user_sessions (
                session_id, user_id, token_hash, created_at_utc, expires_at_utc,
                revoked_at_utc, last_seen_at_utc, client_label, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                session.session_id,
                session.user_id,
                session.token_hash,
                session.created_at_utc,
                session.expires_at_utc,
                session.revoked_at_utc,
                session.last_seen_at_utc,
                session.client_label,
                encode_json_field(session.metadata),
            ),
        )

        return IssuedSession(session=session, token=raw_token)

    def get_session(self, session_id: str) -> UserSession | None:
        row = self.database.query_one(
            "SELECT * FROM user_sessions WHERE session_id = ?;",
            (session_id,),
        )

        return build_user_session_from_row(row) if row is not None else None

    def find_session_by_token(self, token: str) -> UserSession | None:
        row = self.database.query_one(
            "SELECT * FROM user_sessions WHERE token_hash = ?;",
            (hash_session_token(token),),
        )

        return build_user_session_from_row(row) if row is not None else None

    def resolve_active_session(
        self,
        token: str,
        now_utc: str | None = None,
    ) -> UserSession | None:
        session = self.find_session_by_token(token)

        if session is None or not session.is_active(now_utc):
            return None

        return session

    def touch_session(
        self,
        session_id: str,
        seen_at_utc: str | None = None,
    ) -> UserSession:
        session = self.get_session(session_id)

        if session is None:
            raise LookupError(f"User session does not exist: {session_id}")

        timestamp = seen_at_utc or record_utc_now()

        self.database.execute(
            "UPDATE user_sessions SET last_seen_at_utc = ? WHERE session_id = ?;",
            (timestamp, session_id),
        )

        return build_user_session_from_row(
            self.database.query_one(
                "SELECT * FROM user_sessions WHERE session_id = ?;",
                (session_id,),
            )
            or {}
        )

    def list_sessions(
        self,
        user_id: str,
        active_only: bool = False,
        now_utc: str | None = None,
    ) -> tuple[UserSession, ...]:
        rows = self.database.query_all(
            "SELECT * FROM user_sessions WHERE user_id = ? "
            "ORDER BY created_at_utc, session_id;",
            (user_id,),
        )

        sessions = tuple(build_user_session_from_row(row) for row in rows)

        if not active_only:
            return sessions

        return tuple(session for session in sessions if session.is_active(now_utc))

    def revoke_session(
        self,
        session_id: str,
        revoked_at_utc: str | None = None,
    ) -> bool:
        cursor = self.database.execute(
            "UPDATE user_sessions SET revoked_at_utc = ? "
            "WHERE session_id = ? AND revoked_at_utc IS NULL;",
            (revoked_at_utc or record_utc_now(), session_id),
        )

        return cursor.rowcount > 0

    def revoke_user_sessions(
        self,
        user_id: str,
        revoked_at_utc: str | None = None,
    ) -> int:
        cursor = self.database.execute(
            "UPDATE user_sessions SET revoked_at_utc = ? "
            "WHERE user_id = ? AND revoked_at_utc IS NULL;",
            (revoked_at_utc or record_utc_now(), user_id),
        )

        return int(cursor.rowcount)

    def purge_expired_sessions(self, now_utc: str | None = None) -> int:
        reference = now_utc or record_utc_now()

        cursor = self.database.execute(
            "DELETE FROM user_sessions WHERE expires_at_utc <= ?;",
            (reference,),
        )

        return int(cursor.rowcount)


__all__ = [
    "AQOS_AUTH_VERSION",
    "AuthenticationOutcome",
    "AuthenticationResult",
    "DEFAULT_LOCKOUT_MINUTES",
    "DEFAULT_MAX_FAILED_ATTEMPTS",
    "DEFAULT_SESSION_MINUTES",
    "IssuedSession",
    "UserCredential",
    "UserCredentialRepository",
    "UserSession",
    "UserSessionRepository",
    "build_lockout_timestamp",
    "build_session_expiry",
    "build_user_credential_from_row",
    "build_user_session_from_row",
]
