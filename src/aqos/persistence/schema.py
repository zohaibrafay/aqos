from __future__ import annotations

from typing import Any

from aqos.persistence.database import AqosDatabase


AQOS_SCHEMA_VERSION = 1


USER_PROFILES_TABLE = """
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    locale TEXT NOT NULL DEFAULT 'en',
    created_at_utc TEXT NOT NULL,
    updated_at_utc TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}'
);
"""

USER_PROFILES_EMAIL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_user_profiles_email
ON user_profiles (email);
"""

USER_PROFILES_STATUS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_user_profiles_status
ON user_profiles (status);
"""


AQOS_SCHEMA_STATEMENTS: tuple[str, ...] = (
    USER_PROFILES_TABLE,
    USER_PROFILES_EMAIL_INDEX,
    USER_PROFILES_STATUS_INDEX,
)

AQOS_SCHEMA_TABLES: tuple[str, ...] = ("user_profiles",)


def apply_aqos_schema(
    database: AqosDatabase,
    statements: tuple[str, ...] = AQOS_SCHEMA_STATEMENTS,
    schema_version: int = AQOS_SCHEMA_VERSION,
) -> int:
    """
    Create every AQOS table that does not exist yet and stamp the schema version.
    """

    with database.transaction():
        for statement in statements:
            database.execute(statement)

    database.set_user_version(schema_version)

    return schema_version


def read_aqos_schema_version(database: AqosDatabase) -> int:
    return database.user_version()


def is_aqos_schema_current(database: AqosDatabase) -> bool:
    return read_aqos_schema_version(database) == AQOS_SCHEMA_VERSION


def list_missing_aqos_tables(
    database: AqosDatabase,
    expected_tables: tuple[str, ...] = AQOS_SCHEMA_TABLES,
) -> tuple[str, ...]:
    existing = set(database.list_tables())

    return tuple(table for table in expected_tables if table not in existing)


def ensure_aqos_schema(database: AqosDatabase) -> int:
    """
    Apply the schema when it is missing or out of date, then return the version.
    """

    if is_aqos_schema_current(database) and not list_missing_aqos_tables(database):
        return read_aqos_schema_version(database)

    return apply_aqos_schema(database)


def describe_aqos_schema(database: AqosDatabase) -> dict[str, Any]:
    return {
        "schema_version": read_aqos_schema_version(database),
        "expected_schema_version": AQOS_SCHEMA_VERSION,
        "is_current": is_aqos_schema_current(database),
        "tables": list(database.list_tables()),
        "missing_tables": list(list_missing_aqos_tables(database)),
    }


__all__ = [
    "AQOS_SCHEMA_STATEMENTS",
    "AQOS_SCHEMA_TABLES",
    "AQOS_SCHEMA_VERSION",
    "USER_PROFILES_EMAIL_INDEX",
    "USER_PROFILES_STATUS_INDEX",
    "USER_PROFILES_TABLE",
    "apply_aqos_schema",
    "describe_aqos_schema",
    "ensure_aqos_schema",
    "is_aqos_schema_current",
    "list_missing_aqos_tables",
    "read_aqos_schema_version",
]
