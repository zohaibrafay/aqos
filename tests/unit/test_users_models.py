from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from aqos.database.types import (
    AQOS_DATABASE_TYPES_VERSION,
    EnumString,
    database_utc_now,
    to_naive_utc,
)
from aqos.users.models import (
    AQOS_USER_MODELS_VERSION,
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
    normalize_currency,
    normalize_email,
    normalize_landing_page,
    normalize_notification_channels,
    normalize_required_text,
)
from aqos.users.passwords import hash_password, hash_session_token


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
FAST_ITERATIONS = 1_000


def build_password_hash() -> str:
    return hash_password(
        "Sup3rSecretPhrase",
        iterations=FAST_ITERATIONS,
    ).to_storage_string()


def build_profile(**overrides) -> UserProfile:
    payload = {
        "user_id": "user_1",
        "email": "trader@example.com",
        "display_name": "Primary Trader",
        "role": UserRole.TRADER,
        "status": UserStatus.ACTIVE,
    }
    payload.update(overrides)

    return UserProfile(**payload)


def test_versions_are_exposed() -> None:
    assert AQOS_USER_MODELS_VERSION == "1.0"
    assert AQOS_DATABASE_TYPES_VERSION == "1.0"


def test_database_utc_now_is_naive() -> None:
    now = database_utc_now()

    assert now.tzinfo is None
    assert now.microsecond == 0


def test_to_naive_utc_converts_aware_datetimes() -> None:
    from datetime import UTC, timezone

    aware = datetime(2026, 1, 1, 5, 0, 0, tzinfo=timezone(timedelta(hours=5)))

    assert to_naive_utc(aware) == datetime(2026, 1, 1, 0, 0, 0)
    assert to_naive_utc(datetime(2026, 1, 1, tzinfo=UTC)).tzinfo is None
    assert to_naive_utc(FIXED_NOW) == FIXED_NOW


def test_enum_string_requires_an_enum() -> None:
    with pytest.raises(TypeError, match="requires an Enum subclass"):
        EnumString(str)  # type: ignore[arg-type]


def test_enum_string_binds_and_reads_values() -> None:
    column_type = EnumString(UserRole)

    assert column_type.process_bind_param(UserRole.ADMIN, None) == "admin"
    assert column_type.process_bind_param("admin", None) == "admin"
    assert column_type.process_bind_param(None, None) is None
    assert column_type.process_result_value("admin", None) == UserRole.ADMIN
    assert column_type.process_result_value(None, None) is None


def test_enum_string_rejects_unknown_values() -> None:
    column_type = EnumString(UserRole)

    with pytest.raises(ValueError):
        column_type.process_bind_param("emperor", None)

    with pytest.raises(ValueError):
        column_type.process_result_value("emperor", None)


def test_enum_string_copy_keeps_the_enum() -> None:
    copied = EnumString(UserStatus).copy()

    assert copied.enum_class is UserStatus


def test_normalize_email() -> None:
    assert normalize_email("  Trader@Example.COM ") == "trader@example.com"

    with pytest.raises(ValueError, match="email cannot be empty"):
        normalize_email("   ")

    with pytest.raises(ValueError, match="email is not valid"):
        normalize_email("not-an-email")


def test_normalize_required_text() -> None:
    assert normalize_required_text("  name  ", "display_name") == "name"

    with pytest.raises(ValueError, match="display_name cannot be empty"):
        normalize_required_text("   ", "display_name")


def test_normalize_currency() -> None:
    assert normalize_currency(" usd ") == "USD"

    with pytest.raises(ValueError, match="3 letter code"):
        normalize_currency("US")

    with pytest.raises(ValueError, match="3 letter code"):
        normalize_currency("US1")


def test_normalize_landing_page() -> None:
    assert normalize_landing_page(" Signals ") == "signals"

    with pytest.raises(ValueError, match="Unsupported landing page"):
        normalize_landing_page("nowhere")


def test_normalize_notification_channels_deduplicates() -> None:
    assert normalize_notification_channels(("email", "EMAIL", "push")) == (
        "email",
        "push",
    )
    assert normalize_notification_channels(None) == ()
    assert normalize_notification_channels(
        (NotificationChannel.IN_APP,)
    ) == ("in_app",)


def test_normalize_notification_channels_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        normalize_notification_channels(("carrier_pigeon",))


def test_build_lockout_deadline() -> None:
    assert build_lockout_deadline(FIXED_NOW, 15) == datetime(2026, 1, 1, 0, 15, 0)

    with pytest.raises(ValueError, match="lockout_minutes must be at least 1"):
        build_lockout_deadline(FIXED_NOW, 0)


def test_build_session_expiry() -> None:
    assert build_session_expiry(FIXED_NOW, 60) == datetime(2026, 1, 1, 1, 0, 0)

    with pytest.raises(ValueError, match="session_minutes must be at least 1"):
        build_session_expiry(FIXED_NOW, 0)


def test_profile_validates_on_assignment() -> None:
    with pytest.raises(ValueError, match="email is not valid"):
        build_profile(email="broken")

    with pytest.raises(ValueError, match="display_name cannot be empty"):
        build_profile(display_name="   ")

    with pytest.raises(ValueError, match="timezone cannot be empty"):
        build_profile(timezone=" ")

    with pytest.raises(ValueError, match="locale cannot be empty"):
        build_profile(locale="")


def test_profile_normalizes_email() -> None:
    assert build_profile(email=" Trader@Example.COM ").email == "trader@example.com"


def test_profile_capabilities() -> None:
    assert build_profile().can_trade is True
    assert build_profile(role=UserRole.VIEWER).can_trade is False
    assert build_profile(role=UserRole.ANALYST).can_trade is False
    assert build_profile(status=UserStatus.SUSPENDED).can_trade is False
    assert build_profile(status=UserStatus.SUSPENDED).is_active is False


def test_profile_dict_payload() -> None:
    payload = build_profile(
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
        extra_metadata={"tier": 2},
    ).to_dict()

    assert payload["role"] == "trader"
    assert payload["status"] == "active"
    assert payload["can_trade"] is True
    assert payload["created_at_utc"] == "2026-01-01T00:00:00"
    assert payload["metadata"] == {"tier": 2}
    assert "user_1" in repr(build_profile())


def test_credential_validates_the_password_hash() -> None:
    with pytest.raises(ValueError, match="password_hash cannot be empty"):
        UserCredential(user_id="user_1", password_hash="")

    with pytest.raises(ValueError, match="malformed"):
        UserCredential(user_id="user_1", password_hash="not-a-hash")


def test_credential_rejects_negative_attempts() -> None:
    with pytest.raises(ValueError, match="failed_attempt_count cannot be negative"):
        UserCredential(
            user_id="user_1",
            password_hash=build_password_hash(),
            failed_attempt_count=-1,
        )


def test_credential_lock_state() -> None:
    credential = UserCredential(
        user_id="user_1",
        password_hash=build_password_hash(),
        locked_until_utc=datetime(2026, 1, 1, 1, 0, 0),
    )

    assert credential.is_locked(datetime(2026, 1, 1, 0, 30, 0)) is True
    assert credential.is_locked(datetime(2026, 1, 1, 2, 0, 0)) is False

    assert UserCredential(
        user_id="user_2",
        password_hash=build_password_hash(),
    ).is_locked(FIXED_NOW) is False


def test_credential_dict_hides_the_verifier() -> None:
    stored = build_password_hash()

    payload = UserCredential(
        user_id="user_1",
        password_hash=stored,
        password_updated_at_utc=FIXED_NOW,
    ).to_dict()

    assert payload["password_hash"]["algorithm"] == "pbkdf2_sha256"
    assert "hash_hex" not in payload["password_hash"]
    assert stored.split("$")[-1] not in str(payload)
    assert "user_1" in repr(
        UserCredential(user_id="user_1", password_hash=stored)
    )


def test_session_validates_the_token_hash() -> None:
    with pytest.raises(ValueError, match="64 character SHA-256 digest"):
        UserSession(
            session_id="session_1",
            user_id="user_1",
            token_hash="short",
            expires_at_utc=FIXED_NOW,
        )


def test_session_lifecycle_state() -> None:
    user_session = UserSession(
        session_id="session_1",
        user_id="user_1",
        token_hash=hash_session_token("token"),
        created_at_utc=FIXED_NOW,
        expires_at_utc=datetime(2026, 1, 1, 1, 0, 0),
    )

    assert user_session.is_revoked is False
    assert user_session.is_expired(datetime(2026, 1, 1, 0, 30, 0)) is False
    assert user_session.is_active(datetime(2026, 1, 1, 0, 30, 0)) is True
    assert user_session.is_expired(datetime(2026, 1, 1, 2, 0, 0)) is True
    assert user_session.is_active(datetime(2026, 1, 1, 2, 0, 0)) is False

    user_session.revoked_at_utc = datetime(2026, 1, 1, 0, 10, 0)

    assert user_session.is_revoked is True
    assert user_session.is_active(datetime(2026, 1, 1, 0, 30, 0)) is False


def test_session_dict_never_exposes_the_token_hash() -> None:
    token_hash = hash_session_token("token")

    payload = UserSession(
        session_id="session_1",
        user_id="user_1",
        token_hash=token_hash,
        created_at_utc=FIXED_NOW,
        expires_at_utc=datetime(2026, 1, 1, 1, 0, 0),
        client_label="web",
    ).to_dict()

    assert token_hash not in str(payload)
    assert payload["client_label"] == "web"
    assert payload["is_revoked"] is False
    assert "session_1" in repr(
        UserSession(
            session_id="session_1",
            user_id="user_1",
            token_hash=token_hash,
            expires_at_utc=FIXED_NOW,
        )
    )


def test_preferences_validate_fields() -> None:
    with pytest.raises(ValueError, match="3 letter code"):
        UserPreferences(
            preferences_id="prefs_1",
            user_id="user_1",
            default_currency="DOLLARS",
        )

    with pytest.raises(ValueError, match="Unsupported landing page"):
        UserPreferences(
            preferences_id="prefs_1",
            user_id="user_1",
            landing_page="nowhere",
        )

    with pytest.raises(ValueError, match="date_format cannot be empty"):
        UserPreferences(
            preferences_id="prefs_1",
            user_id="user_1",
            date_format="  ",
        )


def test_preferences_normalize_channels() -> None:
    preferences = UserPreferences(
        preferences_id="prefs_1",
        user_id="user_1",
        notification_channels=["EMAIL", "email", "push"],
    )

    assert preferences.notification_channels == ["email", "push"]
    assert preferences.has_channel(NotificationChannel.EMAIL) is True
    assert preferences.has_channel(NotificationChannel.WEBHOOK) is False


def test_preferences_notifications_enabled_flag() -> None:
    preferences = UserPreferences(
        preferences_id="prefs_1",
        user_id="user_1",
        email_notifications_enabled=False,
        push_notifications_enabled=False,
    )

    assert preferences.notifications_enabled is False

    preferences.push_notifications_enabled = True

    assert preferences.notifications_enabled is True


def test_preferences_dict_payload() -> None:
    payload = UserPreferences(
        preferences_id="prefs_1",
        user_id="user_1",
        theme=UserTheme.DARK,
        default_currency="eur",
        landing_page="Signals",
        notification_channels=["in_app"],
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
    ).to_dict()

    assert payload["theme"] == "dark"
    assert payload["default_currency"] == "EUR"
    assert payload["landing_page"] == "signals"
    assert payload["notification_channels"] == ["in_app"]
    assert "user_1" in repr(
        UserPreferences(preferences_id="prefs_1", user_id="user_1")
    )
