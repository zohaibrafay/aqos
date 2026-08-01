from __future__ import annotations

import pytest

from aqos.persistence.database import AqosDatabase, open_aqos_database
from aqos.persistence.records import (
    apply_optional_updates,
    build_record_id,
    decode_bool,
    decode_json_field,
    decode_string_list,
    encode_bool,
    encode_json_field,
    encode_string_list,
    normalize_email,
    normalize_required_text,
    normalize_symbol,
)
from aqos.persistence.users import (
    AQOS_USER_PROFILE_VERSION,
    UserProfile,
    UserProfileRepository,
    UserRole,
    UserStatus,
)


@pytest.fixture
def user_repository() -> UserProfileRepository:
    database = AqosDatabase()
    repository = UserProfileRepository(database)

    yield repository

    database.close()


def create_default_user(
    repository: UserProfileRepository,
    email: str = "trader@example.com",
    **overrides,
) -> UserProfile:
    payload = {
        "email": email,
        "display_name": "Primary Trader",
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)

    return repository.create_user(**payload)


def test_user_profile_version_is_exposed() -> None:
    assert AQOS_USER_PROFILE_VERSION == "1.0"


def test_build_record_id_uses_prefix() -> None:
    record_id = build_record_id("user")

    assert record_id.startswith("user_")
    assert len(record_id) > len("user_")


def test_build_record_id_rejects_empty_prefix() -> None:
    with pytest.raises(ValueError, match="prefix cannot be empty"):
        build_record_id("  ")


def test_json_field_round_trip() -> None:
    encoded = encode_json_field({"b": 2, "a": 1})

    assert encoded == '{"a":1,"b":2}'
    assert decode_json_field(encoded) == {"a": 1, "b": 2}
    assert decode_json_field(None) == {}
    assert decode_json_field({"a": 1}) == {"a": 1}


def test_json_field_rejects_non_dict() -> None:
    with pytest.raises(ValueError, match="must be dictionaries"):
        encode_json_field(["not", "a", "dict"])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="must decode to dictionaries"):
        decode_json_field("[1, 2]")


def test_string_list_round_trip() -> None:
    encoded = encode_string_list(("XAUUSD", "EURUSD"))

    assert decode_string_list(encoded) == ("XAUUSD", "EURUSD")
    assert encode_string_list(None) == "[]"
    assert decode_string_list(None) == ()
    assert decode_string_list(["a"]) == ("a",)


def test_string_list_rejects_non_list() -> None:
    with pytest.raises(ValueError, match="must decode to lists"):
        decode_string_list('{"a": 1}')


def test_bool_round_trip() -> None:
    assert encode_bool(True) == 1
    assert encode_bool(False) == 0
    assert decode_bool(1) is True
    assert decode_bool(0) is False
    assert decode_bool(None) is False
    assert decode_bool(True) is True


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


def test_normalize_symbol() -> None:
    assert normalize_symbol(" xau usd ") == "XAUUSD"

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        normalize_symbol("   ")


def test_apply_optional_updates_skips_none() -> None:
    merged = apply_optional_updates({"a": 1, "b": 2}, {"a": 9, "b": None, "c": 3})

    assert merged == {"a": 9, "b": 2, "c": 3}


def test_user_profile_validation() -> None:
    valid = {
        "user_id": "user_1",
        "email": "a@b.com",
        "display_name": "Name",
        "role": UserRole.TRADER,
        "status": UserStatus.ACTIVE,
        "created_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }

    for field, message in (
        ("user_id", "user_id cannot be empty"),
        ("email", "email cannot be empty"),
        ("display_name", "display_name cannot be empty"),
        ("created_at_utc", "created_at_utc cannot be empty"),
        ("updated_at_utc", "updated_at_utc cannot be empty"),
    ):
        with pytest.raises(ValueError, match=message):
            UserProfile(**{**valid, field: "  "})

    with pytest.raises(ValueError, match="timezone cannot be empty"):
        UserProfile(**valid, timezone=" ")

    with pytest.raises(ValueError, match="locale cannot be empty"):
        UserProfile(**valid, locale="")


def test_user_profile_capabilities() -> None:
    profile = UserProfile(
        user_id="user_1",
        email="a@b.com",
        display_name="Name",
        role=UserRole.TRADER,
        status=UserStatus.ACTIVE,
        created_at_utc="2026-01-01T00:00:00Z",
        updated_at_utc="2026-01-01T00:00:00Z",
    )

    assert profile.is_active is True
    assert profile.can_trade is True

    viewer = UserProfile(
        user_id="user_2",
        email="v@b.com",
        display_name="Viewer",
        role=UserRole.VIEWER,
        status=UserStatus.ACTIVE,
        created_at_utc="2026-01-01T00:00:00Z",
        updated_at_utc="2026-01-01T00:00:00Z",
    )

    assert viewer.can_trade is False

    suspended = UserProfile(
        user_id="user_3",
        email="s@b.com",
        display_name="Suspended",
        role=UserRole.TRADER,
        status=UserStatus.SUSPENDED,
        created_at_utc="2026-01-01T00:00:00Z",
        updated_at_utc="2026-01-01T00:00:00Z",
    )

    assert suspended.is_active is False
    assert suspended.can_trade is False


def test_create_user_persists_profile(user_repository) -> None:
    profile = create_default_user(user_repository)

    assert profile.user_id.startswith("user_")
    assert profile.email == "trader@example.com"
    assert profile.role == UserRole.TRADER
    assert profile.status == UserStatus.ACTIVE
    assert profile.created_at_utc == profile.updated_at_utc

    stored = user_repository.get_user(profile.user_id)

    assert stored is not None
    assert stored.to_dict() == profile.to_dict()


def test_create_user_normalizes_email(user_repository) -> None:
    profile = create_default_user(user_repository, email="  Mixed@Case.COM ")

    assert profile.email == "mixed@case.com"


def test_create_user_rejects_duplicate_email(user_repository) -> None:
    create_default_user(user_repository)

    with pytest.raises(ValueError, match="User email already exists"):
        create_default_user(user_repository, email="TRADER@example.com")


def test_create_user_rejects_invalid_email(user_repository) -> None:
    with pytest.raises(ValueError, match="email is not valid"):
        create_default_user(user_repository, email="broken")


def test_create_user_stores_metadata(user_repository) -> None:
    profile = create_default_user(
        user_repository,
        metadata={"onboarding": "completed", "tier": 2},
    )

    stored = user_repository.require_user(profile.user_id)

    assert stored.metadata == {"onboarding": "completed", "tier": 2}


def test_get_user_returns_none_when_missing(user_repository) -> None:
    assert user_repository.get_user("user_missing") is None


def test_require_user_raises_when_missing(user_repository) -> None:
    with pytest.raises(LookupError, match="does not exist"):
        user_repository.require_user("user_missing")


def test_find_user_by_email(user_repository) -> None:
    profile = create_default_user(user_repository)

    found = user_repository.find_user_by_email("TRADER@EXAMPLE.COM")

    assert found is not None
    assert found.user_id == profile.user_id
    assert user_repository.find_user_by_email("nobody@example.com") is None


def test_list_users_is_ordered_and_filterable(user_repository) -> None:
    create_default_user(
        user_repository,
        email="a@example.com",
        created_at_utc="2026-01-01T00:00:00Z",
    )
    create_default_user(
        user_repository,
        email="b@example.com",
        created_at_utc="2026-01-02T00:00:00Z",
        role=UserRole.ANALYST,
    )
    create_default_user(
        user_repository,
        email="c@example.com",
        created_at_utc="2026-01-03T00:00:00Z",
        status=UserStatus.DISABLED,
    )

    all_users = user_repository.list_users()

    assert [user.email for user in all_users] == [
        "a@example.com",
        "b@example.com",
        "c@example.com",
    ]

    assert [
        user.email for user in user_repository.list_users(status=UserStatus.ACTIVE)
    ] == ["a@example.com", "b@example.com"]

    assert [
        user.email for user in user_repository.list_users(role=UserRole.ANALYST)
    ] == ["b@example.com"]

    assert user_repository.list_users(
        status=UserStatus.DISABLED,
        role=UserRole.ANALYST,
    ) == ()


def test_count_users(user_repository) -> None:
    create_default_user(user_repository, email="a@example.com")
    create_default_user(
        user_repository,
        email="b@example.com",
        status=UserStatus.SUSPENDED,
    )

    assert user_repository.count_users() == 2
    assert user_repository.count_users(status=UserStatus.ACTIVE) == 1
    assert user_repository.count_users(status=UserStatus.DISABLED) == 0


def test_update_user_changes_fields(user_repository) -> None:
    profile = create_default_user(user_repository)

    updated = user_repository.update_user(
        profile.user_id,
        display_name="Senior Trader",
        role=UserRole.ADMIN,
        timezone="Asia/Karachi",
        locale="ur",
        metadata={"tier": 3},
        updated_at_utc="2026-02-01T00:00:00Z",
    )

    assert updated.display_name == "Senior Trader"
    assert updated.role == UserRole.ADMIN
    assert updated.timezone == "Asia/Karachi"
    assert updated.locale == "ur"
    assert updated.metadata == {"tier": 3}
    assert updated.created_at_utc == profile.created_at_utc
    assert updated.updated_at_utc == "2026-02-01T00:00:00Z"

    assert user_repository.require_user(profile.user_id).to_dict() == updated.to_dict()


def test_update_user_keeps_unspecified_fields(user_repository) -> None:
    profile = create_default_user(user_repository, metadata={"tier": 1})

    updated = user_repository.update_user(profile.user_id, display_name="Renamed")

    assert updated.email == profile.email
    assert updated.role == profile.role
    assert updated.metadata == {"tier": 1}


def test_update_user_can_change_email(user_repository) -> None:
    profile = create_default_user(user_repository)

    updated = user_repository.update_user(profile.user_id, email="New@Example.com")

    assert updated.email == "new@example.com"
    assert user_repository.find_user_by_email("new@example.com") is not None


def test_update_user_rejects_conflicting_email(user_repository) -> None:
    first = create_default_user(user_repository, email="a@example.com")
    create_default_user(user_repository, email="b@example.com")

    with pytest.raises(ValueError, match="User email already exists"):
        user_repository.update_user(first.user_id, email="b@example.com")


def test_update_user_allows_setting_same_email(user_repository) -> None:
    profile = create_default_user(user_repository)

    updated = user_repository.update_user(profile.user_id, email=profile.email)

    assert updated.email == profile.email


def test_update_user_raises_for_missing_user(user_repository) -> None:
    with pytest.raises(LookupError, match="does not exist"):
        user_repository.update_user("user_missing", display_name="Nope")


def test_set_user_status(user_repository) -> None:
    profile = create_default_user(user_repository)

    suspended = user_repository.set_user_status(
        profile.user_id,
        UserStatus.SUSPENDED,
        updated_at_utc="2026-03-01T00:00:00Z",
    )

    assert suspended.status == UserStatus.SUSPENDED
    assert suspended.can_trade is False
    assert suspended.updated_at_utc == "2026-03-01T00:00:00Z"


def test_delete_user(user_repository) -> None:
    profile = create_default_user(user_repository)

    assert user_repository.delete_user(profile.user_id) is True
    assert user_repository.get_user(profile.user_id) is None
    assert user_repository.delete_user(profile.user_id) is False


def test_repository_creates_schema_on_file_database(tmp_path) -> None:
    database = open_aqos_database(tmp_path / "aqos.db")
    repository = UserProfileRepository(database)

    profile = create_default_user(repository)
    database.close()

    reopened = open_aqos_database(tmp_path / "aqos.db")
    reopened_repository = UserProfileRepository(reopened)

    assert reopened_repository.require_user(profile.user_id).email == profile.email

    reopened.close()
