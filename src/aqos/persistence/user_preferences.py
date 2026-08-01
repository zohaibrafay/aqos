from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from enum import Enum
from typing import Any

from aqos.persistence.database import AqosDatabase
from aqos.persistence.records import (
    build_record_id,
    decode_bool,
    decode_json_field,
    decode_string_list,
    encode_bool,
    encode_json_field,
    encode_string_list,
    normalize_required_text,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema


AQOS_USER_PREFERENCES_VERSION = "1.0"


class UserTheme(str, Enum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


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


def normalize_notification_channels(
    channels: tuple[str, ...] | tuple[NotificationChannel, ...] | None,
) -> tuple[NotificationChannel, ...]:
    if not channels:
        return ()

    resolved: list[NotificationChannel] = []

    for channel in channels:
        value = (
            channel
            if isinstance(channel, NotificationChannel)
            else NotificationChannel(str(channel).strip().lower())
        )

        if value not in resolved:
            resolved.append(value)

    return tuple(resolved)


def normalize_landing_page(value: str) -> str:
    page = value.strip().lower()

    if page not in SUPPORTED_LANDING_PAGES:
        raise ValueError(f"Unsupported landing page: {value}")

    return page


def normalize_currency(value: str) -> str:
    currency = value.strip().upper()

    if len(currency) != 3 or not currency.isalpha():
        raise ValueError(f"Currency must be a 3 letter code: {value}")

    return currency


@dataclass(frozen=True)
class UserPreferences:
    preferences_id: str
    user_id: str
    created_at_utc: str
    updated_at_utc: str
    theme: UserTheme = UserTheme.SYSTEM
    default_currency: str = DEFAULT_CURRENCY
    date_format: str = DEFAULT_DATE_FORMAT
    landing_page: str = DEFAULT_LANDING_PAGE
    notification_channels: tuple[NotificationChannel, ...] = ()
    email_notifications_enabled: bool = True
    push_notifications_enabled: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.preferences_id.strip():
            raise ValueError("preferences_id cannot be empty.")

        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.updated_at_utc.strip():
            raise ValueError("updated_at_utc cannot be empty.")

        if not self.date_format.strip():
            raise ValueError("date_format cannot be empty.")

        normalize_currency(self.default_currency)
        normalize_landing_page(self.landing_page)

    def has_channel(self, channel: NotificationChannel) -> bool:
        return channel in self.notification_channels

    @property
    def notifications_enabled(self) -> bool:
        return self.email_notifications_enabled or self.push_notifications_enabled

    def to_dict(self) -> dict[str, Any]:
        return {
            "preferences_id": self.preferences_id,
            "user_id": self.user_id,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "theme": self.theme.value,
            "default_currency": self.default_currency,
            "date_format": self.date_format,
            "landing_page": self.landing_page,
            "notification_channels": [
                channel.value for channel in self.notification_channels
            ],
            "email_notifications_enabled": self.email_notifications_enabled,
            "push_notifications_enabled": self.push_notifications_enabled,
            "notifications_enabled": self.notifications_enabled,
            "metadata": self.metadata,
        }


def build_user_preferences_from_row(row: dict[str, Any]) -> UserPreferences:
    return UserPreferences(
        preferences_id=str(row["preferences_id"]),
        user_id=str(row["user_id"]),
        created_at_utc=str(row["created_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        theme=UserTheme(str(row["theme"])),
        default_currency=str(row["default_currency"]),
        date_format=str(row["date_format"]),
        landing_page=str(row["landing_page"]),
        notification_channels=normalize_notification_channels(
            decode_string_list(row.get("notification_channels"))
        ),
        email_notifications_enabled=decode_bool(row["email_notifications_enabled"]),
        push_notifications_enabled=decode_bool(row["push_notifications_enabled"]),
        metadata=decode_json_field(row.get("metadata")),
    )


def build_default_user_preferences(
    user_id: str,
    preferences_id: str | None = None,
    created_at_utc: str | None = None,
) -> UserPreferences:
    timestamp = created_at_utc or record_utc_now()

    return UserPreferences(
        preferences_id=preferences_id or build_record_id("prefs"),
        user_id=normalize_required_text(user_id, "user_id"),
        created_at_utc=timestamp,
        updated_at_utc=timestamp,
        notification_channels=(NotificationChannel.IN_APP,),
    )


class UserPreferencesRepository:
    """One preferences row per user, created on demand with safe defaults."""

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

    def get_preferences(self, user_id: str) -> UserPreferences | None:
        row = self.database.query_one(
            "SELECT * FROM user_preferences WHERE user_id = ?;",
            (user_id,),
        )

        return build_user_preferences_from_row(row) if row is not None else None

    def require_preferences(self, user_id: str) -> UserPreferences:
        preferences = self.get_preferences(user_id)

        if preferences is None:
            raise LookupError(f"User preferences do not exist: {user_id}")

        return preferences

    def get_or_create_preferences(
        self,
        user_id: str,
        created_at_utc: str | None = None,
    ) -> UserPreferences:
        existing = self.get_preferences(user_id)

        if existing is not None:
            return existing

        preferences = build_default_user_preferences(
            user_id=user_id,
            created_at_utc=created_at_utc,
        )
        self._insert(preferences)

        return preferences

    def update_preferences(
        self,
        user_id: str,
        theme: UserTheme | None = None,
        default_currency: str | None = None,
        date_format: str | None = None,
        landing_page: str | None = None,
        notification_channels: tuple[str, ...] | None = None,
        email_notifications_enabled: bool | None = None,
        push_notifications_enabled: bool | None = None,
        metadata: dict[str, Any] | None = None,
        updated_at_utc: str | None = None,
    ) -> UserPreferences:
        current = self.require_preferences(user_id)

        updated = replace(
            current,
            theme=theme or current.theme,
            default_currency=(
                normalize_currency(default_currency)
                if default_currency is not None
                else current.default_currency
            ),
            date_format=(
                normalize_required_text(date_format, "date_format")
                if date_format is not None
                else current.date_format
            ),
            landing_page=(
                normalize_landing_page(landing_page)
                if landing_page is not None
                else current.landing_page
            ),
            notification_channels=(
                normalize_notification_channels(notification_channels)
                if notification_channels is not None
                else current.notification_channels
            ),
            email_notifications_enabled=(
                email_notifications_enabled
                if email_notifications_enabled is not None
                else current.email_notifications_enabled
            ),
            push_notifications_enabled=(
                push_notifications_enabled
                if push_notifications_enabled is not None
                else current.push_notifications_enabled
            ),
            metadata=metadata if metadata is not None else current.metadata,
            updated_at_utc=updated_at_utc or record_utc_now(),
        )

        self._update(updated)

        return updated

    def reset_preferences(
        self,
        user_id: str,
        updated_at_utc: str | None = None,
    ) -> UserPreferences:
        current = self.require_preferences(user_id)

        defaults = build_default_user_preferences(
            user_id=user_id,
            preferences_id=current.preferences_id,
            created_at_utc=current.created_at_utc,
        )
        reset = replace(defaults, updated_at_utc=updated_at_utc or record_utc_now())

        self._update(reset)

        return reset

    def delete_preferences(self, user_id: str) -> bool:
        cursor = self.database.execute(
            "DELETE FROM user_preferences WHERE user_id = ?;",
            (user_id,),
        )

        return cursor.rowcount > 0

    def _insert(self, preferences: UserPreferences) -> None:
        self.database.execute(
            """
            INSERT INTO user_preferences (
                preferences_id, user_id, theme, default_currency, date_format,
                landing_page, notification_channels, email_notifications_enabled,
                push_notifications_enabled, created_at_utc, updated_at_utc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                preferences.preferences_id,
                preferences.user_id,
                preferences.theme.value,
                preferences.default_currency,
                preferences.date_format,
                preferences.landing_page,
                encode_string_list(
                    tuple(channel.value for channel in preferences.notification_channels)
                ),
                encode_bool(preferences.email_notifications_enabled),
                encode_bool(preferences.push_notifications_enabled),
                preferences.created_at_utc,
                preferences.updated_at_utc,
                encode_json_field(preferences.metadata),
            ),
        )

    def _update(self, preferences: UserPreferences) -> None:
        self.database.execute(
            """
            UPDATE user_preferences
            SET theme = ?, default_currency = ?, date_format = ?, landing_page = ?,
                notification_channels = ?, email_notifications_enabled = ?,
                push_notifications_enabled = ?, updated_at_utc = ?, metadata = ?
            WHERE user_id = ?;
            """,
            (
                preferences.theme.value,
                preferences.default_currency,
                preferences.date_format,
                preferences.landing_page,
                encode_string_list(
                    tuple(channel.value for channel in preferences.notification_channels)
                ),
                encode_bool(preferences.email_notifications_enabled),
                encode_bool(preferences.push_notifications_enabled),
                preferences.updated_at_utc,
                encode_json_field(preferences.metadata),
                preferences.user_id,
            ),
        )


__all__ = [
    "AQOS_USER_PREFERENCES_VERSION",
    "DEFAULT_CURRENCY",
    "DEFAULT_DATE_FORMAT",
    "DEFAULT_LANDING_PAGE",
    "NotificationChannel",
    "SUPPORTED_LANDING_PAGES",
    "UserPreferences",
    "UserPreferencesRepository",
    "UserTheme",
    "build_default_user_preferences",
    "build_user_preferences_from_row",
    "normalize_currency",
    "normalize_landing_page",
    "normalize_notification_channels",
]
