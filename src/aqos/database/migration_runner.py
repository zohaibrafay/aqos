from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from aqos.database.engine import AqosDatabase


AQOS_MIGRATIONS_VERSION = "1.0"

MIGRATIONS_DIRECTORY = Path(__file__).parent / "migrations"

MIGRATION_FILENAME_PATTERN = re.compile(r"^V(?P<version>\d{4})__(?P<name>[\w-]+)\.sql$")

DELIMITER_PATTERN = re.compile(r"^\s*DELIMITER\s+(?P<delimiter>\S+)\s*$", re.IGNORECASE)

SCHEMA_MIGRATIONS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    checksum VARCHAR(64) NOT NULL,
    applied_at_utc DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
"""


@dataclass(frozen=True)
class MigrationScript:
    version: int
    name: str
    path: Path
    sql: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("Migration version must be at least 1.")

        if not self.name.strip():
            raise ValueError("Migration name cannot be empty.")

        if not self.sql.strip():
            raise ValueError(f"Migration file is empty: {self.path}")

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()

    @property
    def filename(self) -> str:
        return self.path.name

    def statements(self) -> tuple[str, ...]:
        return split_sql_statements(self.sql)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "filename": self.filename,
            "checksum": self.checksum,
            "statement_count": len(self.statements()),
        }


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    name: str
    checksum: str
    applied_at_utc: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "name": self.name,
            "checksum": self.checksum,
            "applied_at_utc": self.applied_at_utc,
        }


@dataclass(frozen=True)
class MigrationPlan:
    applied: tuple[AppliedMigration, ...] = ()
    pending: tuple[MigrationScript, ...] = ()
    checksum_mismatches: tuple[str, ...] = ()

    @property
    def current_version(self) -> int:
        return max((item.version for item in self.applied), default=0)

    @property
    def target_version(self) -> int:
        return max(
            (item.version for item in self.pending),
            default=self.current_version,
        )

    @property
    def is_up_to_date(self) -> bool:
        return not self.pending

    def raise_if_corrupted(self) -> None:
        if not self.checksum_mismatches:
            return

        raise ValueError(
            "Applied migrations were modified after they ran: "
            + "; ".join(self.checksum_mismatches)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_version": self.current_version,
            "target_version": self.target_version,
            "is_up_to_date": self.is_up_to_date,
            "applied": [item.to_dict() for item in self.applied],
            "pending": [item.to_dict() for item in self.pending],
            "checksum_mismatches": list(self.checksum_mismatches),
        }


@dataclass(frozen=True)
class MigrationRunResult:
    applied_versions: tuple[int, ...] = ()
    current_version: int = 0
    statements_executed: int = 0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    @property
    def applied_count(self) -> int:
        return len(self.applied_versions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "applied_versions": list(self.applied_versions),
            "applied_count": self.applied_count,
            "current_version": self.current_version,
            "statements_executed": self.statements_executed,
            "metadata": self.metadata,
        }


def parse_migration_filename(filename: str) -> tuple[int, str]:
    match = MIGRATION_FILENAME_PATTERN.match(filename)

    if match is None:
        raise ValueError(
            f"Migration filename must look like V0001__name.sql: {filename}"
        )

    return int(match.group("version")), match.group("name")


def split_sql_statements(sql: str) -> tuple[str, ...]:
    """
    Split a migration file into server-executable statements.

    ``DELIMITER`` is a MySQL client directive that the server never sees, so the
    body between delimiter changes is kept together as one statement. That is
    what allows stored procedures to ship inside migration files.
    """

    statements: list[str] = []
    buffer: list[str] = []
    delimiter = ";"

    for line in sql.splitlines():
        delimiter_match = DELIMITER_PATTERN.match(line)

        if delimiter_match is not None:
            flushed = "\n".join(buffer).strip()

            if flushed:
                statements.append(flushed)

            buffer = []
            delimiter = delimiter_match.group("delimiter")
            continue

        stripped = line.strip()

        if stripped.startswith("--") and not buffer:
            continue

        buffer.append(line)

        if stripped.endswith(delimiter):
            joined = "\n".join(buffer).strip()
            joined = joined[: -len(delimiter)].strip()

            if joined:
                statements.append(joined)

            buffer = []

    remaining = "\n".join(buffer).strip()

    if remaining:
        statements.append(remaining)

    return tuple(statement for statement in statements if statement.strip())


def load_migration_script(path: str | Path) -> MigrationScript:
    script_path = Path(path)

    if not script_path.exists():
        raise FileNotFoundError(f"Migration file does not exist: {script_path}")

    version, name = parse_migration_filename(script_path.name)

    return MigrationScript(
        version=version,
        name=name,
        path=script_path,
        sql=script_path.read_text(encoding="utf-8"),
    )


def discover_migration_scripts(
    directory: str | Path = MIGRATIONS_DIRECTORY,
) -> tuple[MigrationScript, ...]:
    migrations_path = Path(directory)

    if not migrations_path.exists():
        raise FileNotFoundError(
            f"Migrations directory does not exist: {migrations_path}"
        )

    scripts = [
        load_migration_script(path)
        for path in sorted(migrations_path.glob("*.sql"))
    ]

    versions = [script.version for script in scripts]

    if len(versions) != len(set(versions)):
        raise ValueError("Duplicate migration versions found.")

    return tuple(sorted(scripts, key=lambda script: script.version))


def ensure_migrations_table(session: Session) -> None:
    session.execute(text(SCHEMA_MIGRATIONS_TABLE_SQL))


def read_applied_migrations(session: Session) -> tuple[AppliedMigration, ...]:
    rows = session.execute(
        text(
            "SELECT version, name, checksum, applied_at_utc "
            "FROM schema_migrations ORDER BY version"
        )
    ).all()

    return tuple(
        AppliedMigration(
            version=int(row[0]),
            name=str(row[1]),
            checksum=str(row[2]),
            applied_at_utc=str(row[3]) if row[3] is not None else None,
        )
        for row in rows
    )


def build_migration_plan(
    scripts: tuple[MigrationScript, ...],
    applied: tuple[AppliedMigration, ...],
) -> MigrationPlan:
    applied_by_version = {item.version: item for item in applied}

    pending: list[MigrationScript] = []
    mismatches: list[str] = []

    for script in scripts:
        existing = applied_by_version.get(script.version)

        if existing is None:
            pending.append(script)
            continue

        if existing.checksum != script.checksum:
            mismatches.append(
                f"V{script.version:04d}__{script.name}.sql checksum changed"
            )

    return MigrationPlan(
        applied=applied,
        pending=tuple(pending),
        checksum_mismatches=tuple(mismatches),
    )


def record_applied_migration(session: Session, script: MigrationScript) -> None:
    session.execute(
        text(
            "INSERT INTO schema_migrations (version, name, checksum) "
            "VALUES (:version, :name, :checksum)"
        ),
        {
            "version": script.version,
            "name": script.name,
            "checksum": script.checksum,
        },
    )


def apply_migration_script(session: Session, script: MigrationScript) -> int:
    statements = script.statements()

    for statement in statements:
        session.execute(text(statement))

    record_applied_migration(session, script)

    return len(statements)


def plan_migrations(
    database: AqosDatabase,
    directory: str | Path = MIGRATIONS_DIRECTORY,
) -> MigrationPlan:
    scripts = discover_migration_scripts(directory)

    with database.session() as session:
        ensure_migrations_table(session)
        applied = read_applied_migrations(session)

    return build_migration_plan(scripts, applied)


def apply_migrations(
    database: AqosDatabase,
    directory: str | Path = MIGRATIONS_DIRECTORY,
    allow_checksum_mismatch: bool = False,
) -> MigrationRunResult:
    """Apply every pending migration file in version order."""

    scripts = discover_migration_scripts(directory)

    applied_versions: list[int] = []
    statements_executed = 0

    with database.session() as session:
        ensure_migrations_table(session)
        plan = build_migration_plan(scripts, read_applied_migrations(session))

        if not allow_checksum_mismatch:
            plan.raise_if_corrupted()

        for script in plan.pending:
            statements_executed += apply_migration_script(session, script)
            applied_versions.append(script.version)

        current_version = max(
            applied_versions + [plan.current_version],
            default=0,
        )

    return MigrationRunResult(
        applied_versions=tuple(applied_versions),
        current_version=current_version,
        statements_executed=statements_executed,
        metadata={"directory": Path(directory).as_posix()},
    )


def read_schema_version(database: AqosDatabase) -> int:
    with database.read_session() as session:
        ensure_migrations_table(session)
        applied = read_applied_migrations(session)

    return max((item.version for item in applied), default=0)


__all__ = [
    "AQOS_MIGRATIONS_VERSION",
    "AppliedMigration",
    "MIGRATIONS_DIRECTORY",
    "MIGRATION_FILENAME_PATTERN",
    "MigrationPlan",
    "MigrationRunResult",
    "MigrationScript",
    "SCHEMA_MIGRATIONS_TABLE_SQL",
    "apply_migration_script",
    "apply_migrations",
    "build_migration_plan",
    "discover_migration_scripts",
    "ensure_migrations_table",
    "load_migration_script",
    "parse_migration_filename",
    "plan_migrations",
    "read_applied_migrations",
    "read_schema_version",
    "record_applied_migration",
    "split_sql_statements",
]
