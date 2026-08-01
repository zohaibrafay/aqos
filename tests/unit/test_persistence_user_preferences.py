from __future__ import annotations

import pytest

from aqos.persistence.database import AqosDatabase
from aqos.persistence.user_preferences import (
    AQOS_USER_PREFERENCES_VERSION,
    NotificationChannel,
    UserPreferences,
    UserPreferencesRepository,
    UserTheme,
    build_default_user_preferences,
    normalize_currency,
    normalize_landing_page,
    normalize_notification_channels,
)
from aqos.persistence.users import UserProfileRepository


@pytest.fixture
def preferences_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def stored_user(preferences_database):
    return UserProfileRepository(preferences_database).create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def preferences(preferences_database) -> UserPreferencesRepository:
    return UserPreferencesRepository(preferences_database)


def test_preferences_version_is_exposed() -> None:
    assert AQOS_USER_PREFERENCES_VERSION == "1.0"


def test_normalize_notification_channels_deduplicates() -> None:
    channels = normalize_notification_channels(("email", "EMAIL", "push"))

    assert channels == (NotificationChannel.EMAIL, NotificationChannel.PUSH)
    assert normalize_notification_channels(None) == ()
    assert normalize_notification_channels(()) == ()


def test_normalize_notification_channels_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        normalize_notification_channels(("carrier_pigeon",))


def test_normalize_landing_page() -> None:
    assert normalize_landing_page(" Signals ") == "signals"

    with pytest.raises(ValueError, match="Unsupported landing page"):
        normalize_landing_page("nowhere")


def test_normalize_currency() -> None:
    assert normalize_currency(" usd ") == "USD"

    with pytest.raises(ValueError, match="3 letter code"):
        normalize_currency("US")

    with pytest.raises(ValueError, match="3 letter code"):
        normalize_currency("US1")


def test_preferences_validation() -> None:
    valid = {
        "preferences_id": "prefs_1",
        "user_id": "user_1",
        "created_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(ValueError, match="preferences_id cannot be empty"):
        UserPreferences(**{**valid, "preferences_id": " "})

    with pytest.raises(ValueError, match="user_id cannot be empty"):
        UserPreferences(**{**valid, "user_id": ""})

    with pytest.raises(ValueError, match="date_format cannot be empty"):
        UserPreferences(**valid, date_format=" ")

    with pytest.raises(ValueError, match="3 letter code"):
        UserPreferences(**valid, default_currency="DOLLARS")

    with pytest.raises(ValueError, match="Unsupported landing page"):
        UserPreferences(**valid, landing_page="nowhere")


def test_preferences_channel_helpers() -> None:
    preferences = build_default_user_preferences(
        "user_1",
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert preferences.has_channel(NotificationChannel.IN_APP) is True
    assert preferences.has_channel(NotificationChannel.WEBHOOK) is False
    assert preferences.notifications_enabled is True


def test_preferences_dict_payload() -> None:
    preferences = build_default_user_preferences(
        "user_1",
        created_at_utc="2026-01-01T00:00:00Z",
    )

    payload = preferences.to_dict()

    assert payload["theme"] == "system"
    assert payload["default_currency"] == "USD"
    assert payload["landing_page"] == "dashboard"
    assert payload["notification_channels"] == ["in_app"]
    assert payload["notifications_enabled"] is True


def test_get_or_create_is_idempotent(preferences, stored_user) -> None:
    first = preferences.get_or_create_preferences(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    second = preferences.get_or_create_preferences(stored_user.user_id)

    assert first.preferences_id == second.preferences_id
    assert second.created_at_utc == "2026-01-01T00:00:00Z"


def test_get_preferences_returns_none_when_missing(preferences) -> None:
    assert preferences.get_preferences("user_missing") is None


def test_require_preferences_raises_when_missing(preferences) -> None:
    with pytest.raises(LookupError, match="do not exist"):
        preferences.require_preferences("user_missing")


def test_update_preferences_round_trip(preferences, stored_user) -> None:
    preferences.get_or_create_preferences(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    updated = preferences.update_preferences(
        stored_user.user_id,
        theme=UserTheme.DARK,
        default_currency="eur",
        date_format="DD/MM/YYYY",
        landing_page="signals",
        notification_channels=("email", "push"),
        email_notifications_enabled=False,
        metadata={"beta": True},
        updated_at_utc="2026-02-01T00:00:00Z",
    )

    assert updated.theme == UserTheme.DARK
    assert updated.default_currency == "EUR"
    assert updated.date_format == "DD/MM/YYYY"
    assert updated.landing_page == "signals"
    assert updated.notification_channels == (
        NotificationChannel.EMAIL,
        NotificationChannel.PUSH,
    )
    assert updated.email_notifications_enabled is False
    assert updated.push_notifications_enabled is True
    assert updated.metadata == {"beta": True}
    assert updated.updated_at_utc == "2026-02-01T00:00:00Z"

    stored = preferences.require_preferences(stored_user.user_id)

    assert stored.to_dict() == updated.to_dict()


def test_update_preferences_keeps_unspecified_fields(preferences, stored_user) -> None:
    preferences.get_or_create_preferences(stored_user.user_id)

    updated = preferences.update_preferences(
        stored_user.user_id,
        theme=UserTheme.LIGHT,
    )

    assert updated.default_currency == "USD"
    assert updated.notification_channels == (NotificationChannel.IN_APP,)


def test_update_preferences_can_disable_all_notifications(
    preferences,
    stored_user,
) -> None:
    preferences.get_or_create_preferences(stored_user.user_id)

    updated = preferences.update_preferences(
        stored_user.user_id,
        email_notifications_enabled=False,
        push_notifications_enabled=False,
    )

    assert updated.notifications_enabled is False


def test_update_preferences_rejects_invalid_values(preferences, stored_user) -> None:
    preferences.get_or_create_preferences(stored_user.user_id)

    with pytest.raises(ValueError, match="3 letter code"):
        preferences.update_preferences(stored_user.user_id, default_currency="dollars")

    with pytest.raises(ValueError, match="Unsupported landing page"):
        preferences.update_preferences(stored_user.user_id, landing_page="nowhere")


def test_reset_preferences(preferences, stored_user) -> None:
    created = preferences.get_or_create_preferences(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    preferences.update_preferences(
        stored_user.user_id,
        theme=UserTheme.DARK,
        landing_page="risk",
    )

    reset = preferences.reset_preferences(
        stored_user.user_id,
        updated_at_utc="2026-03-01T00:00:00Z",
    )

    assert reset.preferences_id == created.preferences_id
    assert reset.created_at_utc == created.created_at_utc
    assert reset.theme == UserTheme.SYSTEM
    assert reset.landing_page == "dashboard"
    assert reset.updated_at_utc == "2026-03-01T00:00:00Z"


def test_delete_preferences(preferences, stored_user) -> None:
    preferences.get_or_create_preferences(stored_user.user_id)

    assert preferences.delete_preferences(stored_user.user_id) is True
    assert preferences.get_preferences(stored_user.user_id) is None
    assert preferences.delete_preferences(stored_user.user_id) is False


def test_deleting_user_cascades_to_preferences(
    preferences_database,
    preferences,
    stored_user,
) -> None:
    preferences.get_or_create_preferences(stored_user.user_id)

    UserProfileRepository(preferences_database).delete_user(stored_user.user_id)

    assert preferences.get_preferences(stored_user.user_id) is None
