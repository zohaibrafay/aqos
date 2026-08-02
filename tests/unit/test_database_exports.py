from __future__ import annotations

from pathlib import Path

import aqos.database as database


SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "aqos"

EXPECTED_EXPORTS = (
    "AQOS_DATABASE_BASE_VERSION",
    "AQOS_DATABASE_CONFIG_VERSION",
    "AQOS_DATABASE_ENGINE_VERSION",
    "AQOS_MIGRATIONS_VERSION",
    "AQOS_PROCEDURES_VERSION",
    "AQOS_REPOSITORY_VERSION",
    "AqosBase",
    "AqosDatabase",
    "AqosRepository",
    "MigrationPlan",
    "MigrationRunResult",
    "MigrationScript",
    "MySQLDatabaseConfig",
    "SchemaMigration",
    "StoredProcedureResult",
    "StoredProcedureService",
    "apply_migrations",
    "build_aqos_database_from_env",
    "create_aqos_engine",
    "create_aqos_session_factory",
    "discover_migration_scripts",
    "load_database_config_from_env",
    "normalize_procedure_name",
    "parse_database_url",
    "plan_migrations",
    "read_schema_version",
)


def iter_source_files() -> list[Path]:
    return [
        path
        for path in SOURCE_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def test_expected_symbols_are_exported() -> None:
    for name in EXPECTED_EXPORTS:
        assert name in database.__all__, name
        assert hasattr(database, name), name


def test_all_entries_are_importable() -> None:
    for name in database.__all__:
        assert hasattr(database, name), name


def test_all_has_no_duplicates() -> None:
    assert len(database.__all__) == len(set(database.__all__))


def test_aqos_source_never_imports_sqlite3() -> None:
    """AQOS is MySQL-first: no production module may fall back to SQLite."""

    offenders: list[str] = []

    for path in iter_source_files():
        content = path.read_text(encoding="utf-8")

        if "import sqlite3" in content or "sqlite3." in content:
            offenders.append(path.relative_to(SOURCE_ROOT).as_posix())

    assert offenders == []


def test_aqos_source_never_builds_sqlite_urls() -> None:
    offenders: list[str] = []

    for path in iter_source_files():
        content = path.read_text(encoding="utf-8").lower()

        if "sqlite:///" in content or "sqlite+pysqlite" in content:
            offenders.append(path.relative_to(SOURCE_ROOT).as_posix())

    assert offenders == []


def test_supported_drivers_are_mysql_only() -> None:
    assert all(
        driver.startswith("mysql+") for driver in database.SUPPORTED_MYSQL_DRIVERS
    )
