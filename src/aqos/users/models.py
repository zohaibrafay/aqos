from __future__ import annotations

import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.types import EnumString, database_utc_now
from aqos.users.passwords import PasswordHash, parse_password_hash


AQOS_USER_MODELS_VERSION = "1.0"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

DEFAULT_TIMEZONE = "UTC"
DEFAULT_LOCALE = "en"
DEFAULT_CURRENCY = "USD"
DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
DEFAULT_LANDING_PAGE = "dashboard"

SUPPORTED_LANDING_PAGES = (
    "dashboard",
    "signals",
    "accounts",
    "backtesting",
    "risk",
    "settings",
)

DEFAULT_MAX_FAILED_ATTEMPTS = 5
DEFAULT_LOCKOUT_MINUTES = 15
DEFAULT_SESSION_MINUTES = 60 * 12


class UserRole(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    TRADER = "trader"
    ANALYST = "analyst"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DISABLED = "disabled"


class UserTheme(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


#: Roles that may never place or approve orders.
READ_ONLY_USER_ROLES = (UserRole.ANALYST, UserRole.VIEWER)


def normalize_email(value: str) -> str:
    email = value.strip().lower()

    if not email:
        raise ValueError("email cannot be empty.")

    if not EMAIL_PATTERN.match(email):
        raise ValueError(f"email is not valid: {value}")

    return email


def normalize_required_text(value: str, field_name: str) -> str:
    text = value.strip()

    if not text:
        raise ValueError(f"{field_name} cannot be empty.")

    return text


def normalize_currency(value: str) -> str:
    currency = value.strip().upper()

    if len(currency) != 3 or not currency.isalpha():
        raise ValueError(f"Currency must be a 3 letter code: {value}")

    return currency


def normalize_landing_page(value: str) -> str:
    page = value.strip().lower()

    if page not in SUPPORTED_LANDING_PAGES:
        raise ValueError(f"Unsupported landing page: {value}")

    return page


def normalize_notification_channels(
    channels: tuple[Any, ...] | list[Any] | None,
) -> tuple[str, ...]:
    if not channels:
        return ()

    resolved: list[str] = []

    for channel in channels:
        value = (
            channel.value
            if isinstance(channel, NotificationChannel)
            else NotificationChannel(str(channel).strip().lower()).value
        )

        if value not in resolved:
            resolved.append(value)

    return tuple(resolved)


def build_lockout_deadline(
    now_utc: datetime | None = None,
    lockout_minutes: int = DEFAULT_LOCKOUT_MINUTES,
) -> datetime:
    if lockout_minutes < 1:
        raise ValueError("lockout_minutes must be at least 1.")

    return (now_utc or database_utc_now()) + timedelta(minutes=lockout_minutes)


def build_session_expiry(
    now_utc: datetime | None = None,
    session_minutes: int = DEFAULT_SESSION_MINUTES,
) -> datetime:
    if session_minutes < 1:
        raise ValueError("session_minutes must be at least 1.")

    return (now_utc or database_utc_now()) + timedelta(minutes=session_minutes)


class UserProfile(AqosBase):
    """A person who uses AQOS."""

    __tablename__ = "user_profiles"
    __table_args__ = AQOS_TABLE_ARGS

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(191), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(191), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        EnumString(UserRole),
        nullable=False,
        default=UserRole.TRADER,
    )
    status: Mapped[UserStatus] = mapped_column(
        EnumString(UserStatus),
        nullable=False,
        default=UserStatus.ACTIVE,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default=DEFAULT_TIMEZONE,
    )
    locale: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DEFAULT_LOCALE,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        onupdate=database_utc_now,
        server_default=func.now(),
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    @validates("email")
    def _validate_email(self, key: str, value: str) -> str:
        return normalize_email(value)

    @validates("display_name")
    def _validate_display_name(self, key: str, value: str) -> str:
        return normalize_required_text(value, "display_name")

    @validates("timezone")
    def _validate_timezone(self, key: str, value: str) -> str:
        return normalize_required_text(value, "timezone")

    @validates("locale")
    def _validate_locale(self, key: str, value: str) -> str:
        return normalize_required_text(value, "locale")

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    @property
    def can_trade(self) -> bool:
        """A read-only role or a non-active status can never trade."""

        return self.is_active and self.role not in READ_ONLY_USER_ROLES

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "email": self.email,
            "display_name": self.display_name,
            "role": self.role.value if self.role else None,
            "status": self.status.value if self.status else None,
            "timezone": self.timezone,
            "locale": self.locale,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "updated_at_utc": (
                self.updated_at_utc.isoformat() if self.updated_at_utc else None
            ),
            "is_active": self.is_active,
            "can_trade": self.can_trade,
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return f"UserProfile(user_id={self.user_id!r}, email={self.email!r})"


class UserCredential(AqosBase):
    """
    Authentication material for one user.

    ``password_hash`` is always a PBKDF2 verifier string; plaintext passwords
    never reach this table.
    """

    __tablename__ = "user_credentials"
    __table_args__ = AQOS_TABLE_ARGS

    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    failed_attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    locked_until_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        onupdate=database_utc_now,
        server_default=func.now(),
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    @validates("password_hash")
    def _validate_password_hash(self, key: str, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("password_hash cannot be empty.")

        parse_password_hash(value)

        return value

    @validates("failed_attempt_count")
    def _validate_failed_attempt_count(self, key: str, value: int) -> int:
        if value < 0:
            raise ValueError("failed_attempt_count cannot be negative.")

        return value

    def parsed_password_hash(self) -> PasswordHash:
        return parse_password_hash(self.password_hash)

    def is_locked(self, now_utc: datetime | None = None) -> bool:
        if self.locked_until_utc is None:
            return False

        return self.locked_until_utc > (now_utc or database_utc_now())

    def to_dict(self) -> dict[str, Any]:
        """Serialize without leaking the password verifier."""

        return {
            "user_id": self.user_id,
            "failed_attempt_count": self.failed_attempt_count,
            "locked_until_utc": (
                self.locked_until_utc.isoformat() if self.locked_until_utc else None
            ),
            "last_login_at_utc": (
                self.last_login_at_utc.isoformat() if self.last_login_at_utc else None
            ),
            "password_updated_at_utc": (
                self.password_updated_at_utc.isoformat()
                if self.password_updated_at_utc
                else None
            ),
            "password_hash": self.parsed_password_hash().to_dict(),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return f"UserCredential(user_id={self.user_id!r})"


class UserSession(AqosBase):
    """An opaque session token, stored only as a SHA-256 hash."""

    __tablename__ = "user_sessions"
    __table_args__ = AQOS_TABLE_ARGS

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_label: Mapped[str | None] = mapped_column(String(191), nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    @validates("token_hash")
    def _validate_token_hash(self, key: str, value: str) -> str:
        if not value or len(value) != 64:
            raise ValueError("token_hash must be a 64 character SHA-256 digest.")

        return value

    @property
    def is_revoked(self) -> bool:
        return self.revoked_at_utc is not None

    def is_expired(self, now_utc: datetime | None = None) -> bool:
        return self.expires_at_utc <= (now_utc or database_utc_now())

    def is_active(self, now_utc: datetime | None = None) -> bool:
        return not self.is_revoked and not self.is_expired(now_utc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize without exposing the token hash."""

        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "expires_at_utc": (
                self.expires_at_utc.isoformat() if self.expires_at_utc else None
            ),
            "revoked_at_utc": (
                self.revoked_at_utc.isoformat() if self.revoked_at_utc else None
            ),
            "last_seen_at_utc": (
                self.last_seen_at_utc.isoformat() if self.last_seen_at_utc else None
            ),
            "client_label": self.client_label,
            "is_revoked": self.is_revoked,
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return f"UserSession(session_id={self.session_id!r}, user_id={self.user_id!r})"


class UserPreferences(AqosBase):
    """Display and notification settings for one user."""

    __tablename__ = "user_preferences"
    __table_args__ = AQOS_TABLE_ARGS

    preferences_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    theme: Mapped[UserTheme] = mapped_column(
        EnumString(UserTheme),
        nullable=False,
        default=UserTheme.SYSTEM,
    )
    default_currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default=DEFAULT_CURRENCY,
    )
    date_format: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_DATE_FORMAT,
    )
    landing_page: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DEFAULT_LANDING_PAGE,
    )
    notification_channels: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    email_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    push_notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        onupdate=database_utc_now,
        server_default=func.now(),
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    @validates("default_currency")
    def _validate_currency(self, key: str, value: str) -> str:
        return normalize_currency(value)

    @validates("landing_page")
    def _validate_landing_page(self, key: str, value: str) -> str:
        return normalize_landing_page(value)

    @validates("date_format")
    def _validate_date_format(self, key: str, value: str) -> str:
        return normalize_required_text(value, "date_format")

    @validates("notification_channels")
    def _validate_notification_channels(
        self,
        key: str,
        value: Any,
    ) -> list[str]:
        return list(normalize_notification_channels(value))

    def has_channel(self, channel: NotificationChannel) -> bool:
        return channel.value in (self.notification_channels or [])

    @property
    def notifications_enabled(self) -> bool:
        return bool(self.email_notifications_enabled or self.push_notifications_enabled)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferences_id": self.preferences_id,
            "user_id": self.user_id,
            "theme": self.theme.value if self.theme else None,
            "default_currency": self.default_currency,
            "date_format": self.date_format,
            "landing_page": self.landing_page,
            "notification_channels": list(self.notification_channels or []),
            "email_notifications_enabled": bool(self.email_notifications_enabled),
            "push_notifications_enabled": bool(self.push_notifications_enabled),
            "notifications_enabled": self.notifications_enabled,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "updated_at_utc": (
                self.updated_at_utc.isoformat() if self.updated_at_utc else None
            ),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return f"UserPreferences(user_id={self.user_id!r})"


__all__ = [
    "AQOS_USER_MODELS_VERSION",
    "DEFAULT_CURRENCY",
    "DEFAULT_DATE_FORMAT",
    "DEFAULT_LANDING_PAGE",
    "DEFAULT_LOCALE",
    "DEFAULT_LOCKOUT_MINUTES",
    "DEFAULT_MAX_FAILED_ATTEMPTS",
    "DEFAULT_SESSION_MINUTES",
    "DEFAULT_TIMEZONE",
    "EMAIL_PATTERN",
    "NotificationChannel",
    "READ_ONLY_USER_ROLES",
    "SUPPORTED_LANDING_PAGES",
    "UserCredential",
    "UserPreferences",
    "UserProfile",
    "UserRole",
    "UserSession",
    "UserStatus",
    "UserTheme",
    "build_lockout_deadline",
    "build_session_expiry",
    "normalize_currency",
    "normalize_email",
    "normalize_landing_page",
    "normalize_notification_channels",
    "normalize_required_text",
]
