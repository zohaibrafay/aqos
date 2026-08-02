from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from aqos.database.repository import AqosRepository, RepositoryError
from aqos.database.types import database_utc_now
from aqos.users.models import (
    DEFAULT_LOCKOUT_MINUTES,
    DEFAULT_MAX_FAILED_ATTEMPTS,
    DEFAULT_SESSION_MINUTES,
    NotificationChannel,
    UserCredential,
    UserPreferences,
    UserProfile,
    UserRole,
    UserSession,
    UserStatus,
    UserTheme,
    build_lockout_deadline,
    build_session_expiry,
    normalize_email,
)
from aqos.users.passwords import (
    DEFAULT_PASSWORD_ITERATIONS,
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


AQOS_USER_REPOSITORIES_VERSION = "1.0"


class AuthenticationOutcome(str, Enum):
    SUCCESS = "success"
    INVALID_PASSWORD = "invalid_password"
    NO_CREDENTIAL = "no_credential"
    LOCKED = "locked"


@dataclass(frozen=True)
class AuthenticationResult:
    outcome: AuthenticationOutcome
    user_id: str
    failed_attempt_count: int = 0
    locked_until_utc: datetime | None = None

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
            "locked_until_utc": (
                self.locked_until_utc.isoformat() if self.locked_until_utc else None
            ),
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


def build_entity_id(prefix: str) -> str:
    clean_prefix = prefix.strip().lower()

    if not clean_prefix:
        raise ValueError("Entity id prefix cannot be empty.")

    return f"{clean_prefix}_{uuid4().hex}"


class UserProfileRepository(AqosRepository[UserProfile]):
    model = UserProfile

    def create_user(
        self,
        email: str,
        display_name: str,
        role: UserRole = UserRole.TRADER,
        status: UserStatus = UserStatus.ACTIVE,
        timezone: str = "UTC",
        locale: str = "en",
        metadata: dict[str, Any] | None = None,
        user_id: str | None = None,
        created_at_utc: datetime | None = None,
    ) -> UserProfile:
        normalized_email = normalize_email(email)

        if self.find_by_email(normalized_email) is not None:
            raise RepositoryError(f"User email already exists: {normalized_email}")

        timestamp = created_at_utc or database_utc_now()

        profile = UserProfile(
            user_id=user_id or build_entity_id("user"),
            email=normalized_email,
            display_name=display_name,
            role=role,
            status=status,
            timezone=timezone,
            locale=locale,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
        )

        self.add(profile)
        self.flush()

        return profile

    def find_by_email(self, email: str) -> UserProfile | None:
        return self.session.execute(
            select(UserProfile).where(UserProfile.email == normalize_email(email))
        ).scalar_one_or_none()

    def list_users(
        self,
        status: UserStatus | None = None,
        role: UserRole | None = None,
    ) -> tuple[UserProfile, ...]:
        statement = select(UserProfile)

        if status is not None:
            statement = statement.where(UserProfile.status == status)

        if role is not None:
            statement = statement.where(UserProfile.role == role)

        statement = statement.order_by(
            UserProfile.created_at_utc,
            UserProfile.user_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def update_user(
        self,
        user_id: str,
        display_name: str | None = None,
        role: UserRole | None = None,
        status: UserStatus | None = None,
        timezone: str | None = None,
        locale: str | None = None,
        email: str | None = None,
        metadata: dict[str, Any] | None = None,
        updated_at_utc: datetime | None = None,
    ) -> UserProfile:
        profile = self.require(user_id)

        if email is not None:
            normalized_email = normalize_email(email)
            existing = self.find_by_email(normalized_email)

            if existing is not None and existing.user_id != user_id:
                raise RepositoryError(f"User email already exists: {normalized_email}")

            profile.email = normalized_email

        if display_name is not None:
            profile.display_name = display_name

        if role is not None:
            profile.role = role

        if status is not None:
            profile.status = status

        if timezone is not None:
            profile.timezone = timezone

        if locale is not None:
            profile.locale = locale

        if metadata is not None:
            profile.extra_metadata = metadata

        profile.updated_at_utc = updated_at_utc or database_utc_now()

        self.flush()

        return profile

    def set_status(
        self,
        user_id: str,
        status: UserStatus,
        updated_at_utc: datetime | None = None,
    ) -> UserProfile:
        return self.update_user(
            user_id=user_id,
            status=status,
            updated_at_utc=updated_at_utc,
        )

    def delete_user(self, user_id: str) -> bool:
        return self.delete_by_primary_key(user_id)


class UserCredentialRepository(AqosRepository[UserCredential]):
    """Password verifiers and lockout state, one row per user."""

    model = UserCredential

    def __init__(
        self,
        session: Session,
        password_iterations: int = DEFAULT_PASSWORD_ITERATIONS,
        max_failed_attempts: int = DEFAULT_MAX_FAILED_ATTEMPTS,
        lockout_minutes: int = DEFAULT_LOCKOUT_MINUTES,
    ) -> None:
        if max_failed_attempts < 1:
            raise ValueError("max_failed_attempts must be at least 1.")

        super().__init__(session)

        self.password_iterations = password_iterations
        self.max_failed_attempts = max_failed_attempts
        self.lockout_minutes = lockout_minutes

    def set_password(
        self,
        user_id: str,
        password: str,
        enforce_policy: bool = True,
        created_at_utc: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> UserCredential:
        password_hash = hash_password(
            password=password,
            iterations=self.password_iterations,
            enforce_policy=enforce_policy,
        ).to_storage_string()

        timestamp = created_at_utc or database_utc_now()
        credential = self.get(user_id)

        if credential is None:
            credential = UserCredential(
                user_id=user_id,
                password_hash=password_hash,
                created_at_utc=timestamp,
                updated_at_utc=timestamp,
                password_updated_at_utc=timestamp,
                extra_metadata=metadata or {},
            )
            self.add(credential)
        else:
            credential.password_hash = password_hash
            credential.password_updated_at_utc = timestamp
            credential.updated_at_utc = timestamp

            if metadata is not None:
                credential.extra_metadata = metadata

        credential.failed_attempt_count = 0
        credential.locked_until_utc = None

        self.flush()

        return credential

    def authenticate(
        self,
        user_id: str,
        password: str,
        now_utc: datetime | None = None,
    ) -> AuthenticationResult:
        credential = self.get(user_id)

        if credential is None:
            return AuthenticationResult(
                outcome=AuthenticationOutcome.NO_CREDENTIAL,
                user_id=user_id,
            )

        timestamp = now_utc or database_utc_now()

        if credential.is_locked(timestamp):
            return AuthenticationResult(
                outcome=AuthenticationOutcome.LOCKED,
                user_id=user_id,
                failed_attempt_count=credential.failed_attempt_count,
                locked_until_utc=credential.locked_until_utc,
            )

        if not verify_password(password, credential.password_hash):
            return self._register_failure(credential, timestamp)

        credential.failed_attempt_count = 0
        credential.locked_until_utc = None
        credential.last_login_at_utc = timestamp
        credential.updated_at_utc = timestamp

        self.flush()

        return AuthenticationResult(
            outcome=AuthenticationOutcome.SUCCESS,
            user_id=user_id,
        )

    def unlock(
        self,
        user_id: str,
        updated_at_utc: datetime | None = None,
    ) -> UserCredential:
        credential = self.require(user_id)

        credential.failed_attempt_count = 0
        credential.locked_until_utc = None
        credential.updated_at_utc = updated_at_utc or database_utc_now()

        self.flush()

        return credential

    def delete_credential(self, user_id: str) -> bool:
        return self.delete_by_primary_key(user_id)

    def _register_failure(
        self,
        credential: UserCredential,
        timestamp: datetime,
    ) -> AuthenticationResult:
        attempts = credential.failed_attempt_count + 1

        locked_until = (
            build_lockout_deadline(timestamp, self.lockout_minutes)
            if attempts >= self.max_failed_attempts
            else None
        )

        credential.failed_attempt_count = attempts
        credential.locked_until_utc = locked_until
        credential.updated_at_utc = timestamp

        self.flush()

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


class UserSessionRepository(AqosRepository[UserSession]):
    """Opaque session tokens stored only as SHA-256 hashes."""

    model = UserSession

    def __init__(
        self,
        session: Session,
        session_minutes: int = DEFAULT_SESSION_MINUTES,
    ) -> None:
        if session_minutes < 1:
            raise ValueError("session_minutes must be at least 1.")

        super().__init__(session)

        self.session_minutes = session_minutes

    def create_session(
        self,
        user_id: str,
        client_label: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at_utc: datetime | None = None,
        session_minutes: int | None = None,
        session_id: str | None = None,
        token: str | None = None,
    ) -> IssuedSession:
        raw_token = token or generate_session_token()
        timestamp = created_at_utc or database_utc_now()

        user_session = UserSession(
            session_id=session_id or build_entity_id("session"),
            user_id=user_id,
            token_hash=hash_session_token(raw_token),
            created_at_utc=timestamp,
            expires_at_utc=build_session_expiry(
                now_utc=timestamp,
                session_minutes=session_minutes or self.session_minutes,
            ),
            client_label=client_label,
            extra_metadata=metadata or {},
        )

        self.add(user_session)
        self.flush()

        return IssuedSession(session=user_session, token=raw_token)

    def find_by_token(self, token: str) -> UserSession | None:
        return self.session.execute(
            select(UserSession).where(
                UserSession.token_hash == hash_session_token(token)
            )
        ).scalar_one_or_none()

    def resolve_active_session(
        self,
        token: str,
        now_utc: datetime | None = None,
    ) -> UserSession | None:
        user_session = self.find_by_token(token)

        if user_session is None or not user_session.is_active(now_utc):
            return None

        return user_session

    def touch_session(
        self,
        session_id: str,
        seen_at_utc: datetime | None = None,
    ) -> UserSession:
        user_session = self.require(session_id)
        user_session.last_seen_at_utc = seen_at_utc or database_utc_now()

        self.flush()

        return user_session

    def list_sessions(
        self,
        user_id: str,
        active_only: bool = False,
        now_utc: datetime | None = None,
    ) -> tuple[UserSession, ...]:
        statement = (
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(UserSession.created_at_utc, UserSession.session_id)
        )

        sessions = tuple(self.session.execute(statement).scalars().all())

        if not active_only:
            return sessions

        return tuple(item for item in sessions if item.is_active(now_utc))

    def revoke_session(
        self,
        session_id: str,
        revoked_at_utc: datetime | None = None,
    ) -> bool:
        result = self.session.execute(
            update(UserSession)
            .where(
                UserSession.session_id == session_id,
                UserSession.revoked_at_utc.is_(None),
            )
            .values(revoked_at_utc=revoked_at_utc or database_utc_now())
        )

        return int(result.rowcount or 0) > 0

    def revoke_user_sessions(
        self,
        user_id: str,
        revoked_at_utc: datetime | None = None,
    ) -> int:
        result = self.session.execute(
            update(UserSession)
            .where(
                UserSession.user_id == user_id,
                UserSession.revoked_at_utc.is_(None),
            )
            .values(revoked_at_utc=revoked_at_utc or database_utc_now())
        )

        return int(result.rowcount or 0)

    def purge_expired_sessions(self, now_utc: datetime | None = None) -> int:
        reference = now_utc or database_utc_now()

        expired = self.session.execute(
            select(UserSession).where(UserSession.expires_at_utc <= reference)
        ).scalars().all()

        for user_session in expired:
            self.session.delete(user_session)

        self.flush()

        return len(expired)


class UserPreferencesRepository(AqosRepository[UserPreferences]):
    """One preferences row per user, created on demand with safe defaults."""

    model = UserPreferences

    def get_for_user(self, user_id: str) -> UserPreferences | None:
        return self.session.execute(
            select(UserPreferences).where(UserPreferences.user_id == user_id)
        ).scalar_one_or_none()

    def get_or_create_for_user(
        self,
        user_id: str,
        created_at_utc: datetime | None = None,
    ) -> UserPreferences:
        existing = self.get_for_user(user_id)

        if existing is not None:
            return existing

        timestamp = created_at_utc or database_utc_now()

        preferences = UserPreferences(
            preferences_id=build_entity_id("prefs"),
            user_id=user_id,
            notification_channels=[NotificationChannel.IN_APP.value],
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata={},
        )

        self.add(preferences)
        self.flush()

        return preferences

    def update_for_user(
        self,
        user_id: str,
        theme: UserTheme | None = None,
        default_currency: str | None = None,
        date_format: str | None = None,
        landing_page: str | None = None,
        notification_channels: tuple[str, ...] | list[str] | None = None,
        email_notifications_enabled: bool | None = None,
        push_notifications_enabled: bool | None = None,
        metadata: dict[str, Any] | None = None,
        updated_at_utc: datetime | None = None,
    ) -> UserPreferences:
        preferences = self.get_for_user(user_id)

        if preferences is None:
            raise RepositoryError(f"User preferences do not exist: {user_id}")

        if theme is not None:
            preferences.theme = theme

        if default_currency is not None:
            preferences.default_currency = default_currency

        if date_format is not None:
            preferences.date_format = date_format

        if landing_page is not None:
            preferences.landing_page = landing_page

        if notification_channels is not None:
            preferences.notification_channels = list(notification_channels)

        if email_notifications_enabled is not None:
            preferences.email_notifications_enabled = email_notifications_enabled

        if push_notifications_enabled is not None:
            preferences.push_notifications_enabled = push_notifications_enabled

        if metadata is not None:
            preferences.extra_metadata = metadata

        preferences.updated_at_utc = updated_at_utc or database_utc_now()

        self.flush()

        return preferences

    def reset_for_user(
        self,
        user_id: str,
        updated_at_utc: datetime | None = None,
    ) -> UserPreferences:
        return self.update_for_user(
            user_id=user_id,
            theme=UserTheme.SYSTEM,
            default_currency="USD",
            date_format="YYYY-MM-DD",
            landing_page="dashboard",
            notification_channels=[NotificationChannel.IN_APP.value],
            email_notifications_enabled=True,
            push_notifications_enabled=True,
            metadata={},
            updated_at_utc=updated_at_utc,
        )

    def delete_for_user(self, user_id: str) -> bool:
        preferences = self.get_for_user(user_id)

        if preferences is None:
            return False

        self.session.delete(preferences)
        self.flush()

        return True


__all__ = [
    "AQOS_USER_REPOSITORIES_VERSION",
    "AuthenticationOutcome",
    "AuthenticationResult",
    "IssuedSession",
    "UserCredentialRepository",
    "UserPreferencesRepository",
    "UserProfileRepository",
    "UserSessionRepository",
    "build_entity_id",
]
