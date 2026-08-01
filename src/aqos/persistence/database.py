from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence


AQOS_DATABASE_VERSION = "1.0"

IN_MEMORY_DATABASE = ":memory:"


@dataclass(frozen=True)
class AqosDatabaseConfig:
    database_path: str | Path = IN_MEMORY_DATABASE
    enable_foreign_keys: bool = True
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not str(self.database_path).strip():
            raise ValueError("database_path cannot be empty.")

        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive.")

    @property
    def is_in_memory(self) -> bool:
        return str(self.database_path) == IN_MEMORY_DATABASE

    def resolved_path(self) -> str:
        if self.is_in_memory:
            return IN_MEMORY_DATABASE

        return Path(self.database_path).as_posix()

    def to_dict(self) -> dict[str, Any]:
        return {
            "database_path": self.resolved_path(),
            "is_in_memory": self.is_in_memory,
            "enable_foreign_keys": self.enable_foreign_keys,
            "timeout_seconds": self.timeout_seconds,
        }


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return {key: row[key] for key in row.keys()}


class AqosDatabase:
    """
    Thin SQLite wrapper used by every AQOS persistence repository.

    SQLite is used deliberately: it ships with Python, needs no server, and
    keeps tests deterministic and offline.
    """

    def __init__(self, config: AqosDatabaseConfig | None = None) -> None:
        self.config = config or AqosDatabaseConfig()
        self._connection: sqlite3.Connection | None = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    @property
    def connection(self) -> sqlite3.Connection:
        return self.connect()

    def connect(self) -> sqlite3.Connection:
        if self._connection is not None:
            return self._connection

        if not self.config.is_in_memory:
            Path(self.config.database_path).parent.mkdir(parents=True, exist_ok=True)

        connection = sqlite3.connect(
            self.config.resolved_path(),
            timeout=self.config.timeout_seconds,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row

        if self.config.enable_foreign_keys:
            connection.execute("PRAGMA foreign_keys = ON;")

        self._connection = connection

        return connection

    def close(self) -> None:
        if self._connection is None:
            return

        self._connection.close()
        self._connection = None

    def __enter__(self) -> "AqosDatabase":
        self.connect()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def execute(
        self,
        sql: str,
        parameters: Sequence[Any] | dict[str, Any] = (),
    ) -> sqlite3.Cursor:
        return self.connection.execute(sql, parameters)

    def execute_many(
        self,
        sql: str,
        parameter_sets: Sequence[Sequence[Any] | dict[str, Any]],
    ) -> sqlite3.Cursor:
        return self.connection.executemany(sql, parameter_sets)

    def execute_script(self, sql: str) -> None:
        self.connection.executescript(sql)

    def query_all(
        self,
        sql: str,
        parameters: Sequence[Any] | dict[str, Any] = (),
    ) -> list[dict[str, Any]]:
        cursor = self.execute(sql, parameters)

        return [dict(row_to_dict(row) or {}) for row in cursor.fetchall()]

    def query_one(
        self,
        sql: str,
        parameters: Sequence[Any] | dict[str, Any] = (),
    ) -> dict[str, Any] | None:
        cursor = self.execute(sql, parameters)

        return row_to_dict(cursor.fetchone())

    def query_scalar(
        self,
        sql: str,
        parameters: Sequence[Any] | dict[str, Any] = (),
    ) -> Any:
        row = self.execute(sql, parameters).fetchone()

        if row is None:
            return None

        return row[0]

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        connection.execute("BEGIN;")

        try:
            yield connection
        except Exception:
            connection.execute("ROLLBACK;")
            raise

        connection.execute("COMMIT;")

    def table_exists(self, table_name: str) -> bool:
        row = self.query_one(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?;",
            (table_name,),
        )

        return row is not None

    def list_tables(self) -> tuple[str, ...]:
        rows = self.query_all(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name;"
        )

        return tuple(str(row["name"]) for row in rows)

    def user_version(self) -> int:
        return int(self.query_scalar("PRAGMA user_version;") or 0)

    def set_user_version(self, version: int) -> None:
        if version < 0:
            raise ValueError("user_version cannot be negative.")

        self.execute(f"PRAGMA user_version = {int(version)};")


def open_aqos_database(
    database_path: str | Path = IN_MEMORY_DATABASE,
    enable_foreign_keys: bool = True,
) -> AqosDatabase:
    database = AqosDatabase(
        AqosDatabaseConfig(
            database_path=database_path,
            enable_foreign_keys=enable_foreign_keys,
        )
    )
    database.connect()

    return database


__all__ = [
    "AQOS_DATABASE_VERSION",
    "AqosDatabase",
    "AqosDatabaseConfig",
    "IN_MEMORY_DATABASE",
    "open_aqos_database",
    "row_to_dict",
]
