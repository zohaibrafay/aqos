from __future__ import annotations

from aqos.persistence.database import AqosDatabase, open_aqos_database
from aqos.persistence.schema import (
    AQOS_SCHEMA_STATEMENTS,
    AQOS_SCHEMA_TABLES,
    AQOS_SCHEMA_VERSION,
    apply_aqos_schema,
    describe_aqos_schema,
    ensure_aqos_schema,
    is_aqos_schema_current,
    list_missing_aqos_tables,
    read_aqos_schema_version,
)


def test_schema_version_is_positive() -> None:
    assert AQOS_SCHEMA_VERSION >= 1


def test_schema_statements_are_not_empty() -> None:
    assert AQOS_SCHEMA_STATEMENTS
    assert all(statement.strip() for statement in AQOS_SCHEMA_STATEMENTS)


def test_apply_schema_creates_expected_tables() -> None:
    with AqosDatabase() as database:
        version = apply_aqos_schema(database)

        assert version == AQOS_SCHEMA_VERSION
        assert set(AQOS_SCHEMA_TABLES) <= set(database.list_tables())
        assert read_aqos_schema_version(database) == AQOS_SCHEMA_VERSION


def test_apply_schema_is_idempotent() -> None:
    with AqosDatabase() as database:
        apply_aqos_schema(database)
        tables_after_first = database.list_tables()

        apply_aqos_schema(database)

        assert database.list_tables() == tables_after_first


def test_schema_is_not_current_before_apply() -> None:
    with AqosDatabase() as database:
        assert is_aqos_schema_current(database) is False
        assert list_missing_aqos_tables(database) == AQOS_SCHEMA_TABLES


def test_ensure_schema_applies_once() -> None:
    with AqosDatabase() as database:
        assert ensure_aqos_schema(database) == AQOS_SCHEMA_VERSION
        assert ensure_aqos_schema(database) == AQOS_SCHEMA_VERSION
        assert is_aqos_schema_current(database) is True


def test_ensure_schema_repairs_dropped_table() -> None:
    with AqosDatabase() as database:
        ensure_aqos_schema(database)
        database.execute("DROP TABLE user_profiles;")

        assert list_missing_aqos_tables(database) == ("user_profiles",)

        ensure_aqos_schema(database)

        assert list_missing_aqos_tables(database) == ()


def test_describe_schema_payload() -> None:
    with AqosDatabase() as database:
        ensure_aqos_schema(database)

        payload = describe_aqos_schema(database)

        assert payload["schema_version"] == AQOS_SCHEMA_VERSION
        assert payload["expected_schema_version"] == AQOS_SCHEMA_VERSION
        assert payload["is_current"] is True
        assert payload["missing_tables"] == []
        assert "user_profiles" in payload["tables"]


def test_schema_survives_reconnect(tmp_path) -> None:
    database_path = tmp_path / "aqos.db"

    first = open_aqos_database(database_path)
    ensure_aqos_schema(first)
    first.close()

    second = open_aqos_database(database_path)

    assert is_aqos_schema_current(second) is True
    assert list_missing_aqos_tables(second) == ()

    second.close()


def test_user_profiles_email_is_unique() -> None:
    import sqlite3

    import pytest

    with AqosDatabase() as database:
        ensure_aqos_schema(database)

        insert = (
            "INSERT INTO user_profiles ("
            "user_id, email, display_name, role, status, timezone, locale,"
            " created_at_utc, updated_at_utc, metadata"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"
        )
        values = (
            "user_2",
            "same@example.com",
            "Second",
            "trader",
            "active",
            "UTC",
            "en",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
            "{}",
        )

        database.execute(insert, ("user_1", *values[1:]))

        with pytest.raises(sqlite3.IntegrityError):
            database.execute(insert, values)
