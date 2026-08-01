from __future__ import annotations

import sqlite3

import pytest

from aqos.persistence.database import (
    AQOS_DATABASE_VERSION,
    AqosDatabase,
    AqosDatabaseConfig,
    IN_MEMORY_DATABASE,
    open_aqos_database,
    row_to_dict,
)


def build_demo_table(database: AqosDatabase) -> None:
    database.execute(
        "CREATE TABLE demo (id TEXT PRIMARY KEY, value INTEGER NOT NULL);"
    )


def test_database_version_is_exposed() -> None:
    assert AQOS_DATABASE_VERSION == "1.0"


def test_config_validation() -> None:
    with pytest.raises(ValueError, match="database_path cannot be empty"):
        AqosDatabaseConfig(database_path="   ")

    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        AqosDatabaseConfig(timeout_seconds=0.0)


def test_config_defaults_to_in_memory() -> None:
    config = AqosDatabaseConfig()

    assert config.is_in_memory is True
    assert config.resolved_path() == IN_MEMORY_DATABASE
    assert config.to_dict()["is_in_memory"] is True


def test_config_resolves_file_path(tmp_path) -> None:
    config = AqosDatabaseConfig(database_path=tmp_path / "aqos.db")

    assert config.is_in_memory is False
    assert config.resolved_path().endswith("aqos.db")


def test_row_to_dict_handles_none() -> None:
    assert row_to_dict(None) is None


def test_connect_is_idempotent() -> None:
    database = AqosDatabase()

    first = database.connect()
    second = database.connect()

    assert first is second
    assert database.is_connected is True

    database.close()

    assert database.is_connected is False


def test_close_is_safe_when_not_connected() -> None:
    database = AqosDatabase()
    database.close()

    assert database.is_connected is False


def test_context_manager_closes_connection() -> None:
    with AqosDatabase() as database:
        assert database.is_connected is True

    assert database.is_connected is False


def test_execute_and_query_round_trip() -> None:
    with AqosDatabase() as database:
        build_demo_table(database)
        database.execute("INSERT INTO demo VALUES (?, ?);", ("a", 1))

        row = database.query_one("SELECT * FROM demo WHERE id = ?;", ("a",))

        assert row == {"id": "a", "value": 1}


def test_query_one_returns_none_when_missing() -> None:
    with AqosDatabase() as database:
        build_demo_table(database)

        assert database.query_one("SELECT * FROM demo WHERE id = ?;", ("x",)) is None


def test_execute_many_and_query_all() -> None:
    with AqosDatabase() as database:
        build_demo_table(database)
        database.execute_many(
            "INSERT INTO demo VALUES (?, ?);",
            [("a", 1), ("b", 2), ("c", 3)],
        )

        rows = database.query_all("SELECT * FROM demo ORDER BY id;")

        assert [row["id"] for row in rows] == ["a", "b", "c"]


def test_query_scalar() -> None:
    with AqosDatabase() as database:
        build_demo_table(database)
        database.execute("INSERT INTO demo VALUES (?, ?);", ("a", 7))

        assert database.query_scalar("SELECT COUNT(*) FROM demo;") == 1
        assert database.query_scalar("SELECT value FROM demo WHERE id = 'zz';") is None


def test_execute_script() -> None:
    with AqosDatabase() as database:
        database.execute_script(
            "CREATE TABLE a (id TEXT); CREATE TABLE b (id TEXT);"
        )

        assert database.list_tables() == ("a", "b")


def test_transaction_commits() -> None:
    with AqosDatabase() as database:
        build_demo_table(database)

        with database.transaction():
            database.execute("INSERT INTO demo VALUES (?, ?);", ("a", 1))

        assert database.query_scalar("SELECT COUNT(*) FROM demo;") == 1


def test_transaction_rolls_back_on_error() -> None:
    with AqosDatabase() as database:
        build_demo_table(database)

        with pytest.raises(RuntimeError, match="boom"):
            with database.transaction():
                database.execute("INSERT INTO demo VALUES (?, ?);", ("a", 1))
                raise RuntimeError("boom")

        assert database.query_scalar("SELECT COUNT(*) FROM demo;") == 0


def test_table_exists_and_list_tables() -> None:
    with AqosDatabase() as database:
        assert database.table_exists("demo") is False

        build_demo_table(database)

        assert database.table_exists("demo") is True
        assert database.list_tables() == ("demo",)


def test_user_version_round_trip() -> None:
    with AqosDatabase() as database:
        assert database.user_version() == 0

        database.set_user_version(4)

        assert database.user_version() == 4


def test_user_version_rejects_negative() -> None:
    with AqosDatabase() as database:
        with pytest.raises(ValueError, match="cannot be negative"):
            database.set_user_version(-1)


def test_foreign_keys_are_enforced() -> None:
    with AqosDatabase() as database:
        database.execute_script(
            """
            CREATE TABLE parent (id TEXT PRIMARY KEY);
            CREATE TABLE child (
                id TEXT PRIMARY KEY,
                parent_id TEXT NOT NULL REFERENCES parent(id)
            );
            """
        )

        with pytest.raises(sqlite3.IntegrityError):
            database.execute("INSERT INTO child VALUES (?, ?);", ("c", "missing"))


def test_foreign_keys_can_be_disabled() -> None:
    database = AqosDatabase(AqosDatabaseConfig(enable_foreign_keys=False))

    with database:
        database.execute_script(
            """
            CREATE TABLE parent (id TEXT PRIMARY KEY);
            CREATE TABLE child (
                id TEXT PRIMARY KEY,
                parent_id TEXT NOT NULL REFERENCES parent(id)
            );
            """
        )

        database.execute("INSERT INTO child VALUES (?, ?);", ("c", "missing"))

        assert database.query_scalar("SELECT COUNT(*) FROM child;") == 1


def test_file_database_persists_between_connections(tmp_path) -> None:
    database_path = tmp_path / "nested" / "aqos.db"

    first = open_aqos_database(database_path)
    build_demo_table(first)
    first.execute("INSERT INTO demo VALUES (?, ?);", ("a", 1))
    first.close()

    second = open_aqos_database(database_path)

    assert second.query_scalar("SELECT value FROM demo WHERE id = 'a';") == 1

    second.close()


def test_open_database_creates_parent_directory(tmp_path) -> None:
    database_path = tmp_path / "created" / "aqos.db"

    database = open_aqos_database(database_path)
    database.close()

    assert database_path.exists()
