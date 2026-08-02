"""
Integration tests against a real MySQL 8.x server.

These tests are skipped unless ``AQOS_TEST_DB_URL`` points at a disposable
MySQL database, for example::

    AQOS_TEST_DB_URL=mysql+pymysql://aqos:aqos@127.0.0.1:3306/aqos_test

The database is dropped and recreated between tests, so never point this at a
database you care about.
"""

from __future__ import annotations

import os

import pytest

from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import (
    apply_migrations,
    plan_migrations,
    read_schema_version,
)
from aqos.database.procedures import StoredProcedureService


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set; skipping MySQL integration tests."
        )

    return url


def drop_aqos_objects(database: AqosDatabase) -> None:
    from sqlalchemy import text

    with database.session() as session:
        for procedure in (
            "sp_aqos_schema_version",
            "sp_aqos_set_metadata",
            "sp_aqos_metadata_count",
        ):
            session.execute(text(f"DROP PROCEDURE IF EXISTS {procedure}"))

        session.execute(text("DROP TABLE IF EXISTS aqos_metadata"))
        session.execute(text("DROP TABLE IF EXISTS schema_migrations"))


@pytest.fixture
def mysql_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; skipping integration tests.")

    drop_aqos_objects(database)

    yield database

    drop_aqos_objects(database)
    database.dispose()


def test_server_is_mysql_8(mysql_database) -> None:
    version = mysql_database.server_version()

    assert version is not None
    assert version.startswith("8.")


def test_migrations_apply_cleanly(mysql_database) -> None:
    result = apply_migrations(mysql_database)

    assert result.applied_versions == (1, 2)
    assert result.current_version == 2
    assert result.statements_executed > 0
    assert read_schema_version(mysql_database) == 2


def test_migrations_are_idempotent(mysql_database) -> None:
    apply_migrations(mysql_database)

    second_run = apply_migrations(mysql_database)

    assert second_run.applied_versions == ()
    assert second_run.current_version == 2

    plan = plan_migrations(mysql_database)

    assert plan.is_up_to_date is True
    assert plan.checksum_mismatches == ()


def test_baseline_tables_exist(mysql_database) -> None:
    from sqlalchemy import text

    apply_migrations(mysql_database)

    with mysql_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME"
            )
        ).all()

    tables = {str(row[0]) for row in rows}

    assert {"schema_migrations", "aqos_metadata"} <= tables


def test_stored_procedures_are_installed(mysql_database) -> None:
    apply_migrations(mysql_database)

    service = StoredProcedureService(mysql_database)
    procedures = service.list_procedures()

    assert "sp_aqos_schema_version" in procedures
    assert "sp_aqos_set_metadata" in procedures
    assert "sp_aqos_metadata_count" in procedures
    assert service.procedure_exists("sp_aqos_schema_version") is True
    assert service.procedure_exists("sp_definitely_missing") is False


def test_call_stored_procedure_returning_rows(mysql_database) -> None:
    apply_migrations(mysql_database)

    result = StoredProcedureService(mysql_database).call("sp_aqos_schema_version")

    assert result.first_row is not None
    assert result.first_row["schema_version"] == 2
    assert result.first_row["applied_count"] == 2


def test_call_stored_procedure_with_in_parameters(mysql_database) -> None:
    from sqlalchemy import text

    apply_migrations(mysql_database)

    service = StoredProcedureService(mysql_database)
    service.call("sp_aqos_set_metadata", ("app_version", "0.39.0"))

    with mysql_database.read_session() as session:
        row = session.execute(
            text(
                "SELECT metadata_value FROM aqos_metadata "
                "WHERE metadata_key = :metadata_key"
            ),
            {"metadata_key": "app_version"},
        ).first()

    assert row is not None
    assert row[0] == "0.39.0"


def test_call_stored_procedure_with_out_parameter(mysql_database) -> None:
    apply_migrations(mysql_database)

    service = StoredProcedureService(mysql_database)
    service.call("sp_aqos_set_metadata", ("app_version", "0.39.0"))

    result = service.call("sp_aqos_metadata_count", out_parameters=("total",))

    assert result.out_values["total"] >= 2


def test_repository_round_trip_against_mysql(mysql_database) -> None:
    from aqos.database.base import AqosMetadataEntry
    from aqos.database.repository import AqosRepository, RecordNotFoundError

    class MetadataRepository(AqosRepository[AqosMetadataEntry]):
        model = AqosMetadataEntry

    apply_migrations(mysql_database)

    with mysql_database.session() as session:
        MetadataRepository(session).add(
            AqosMetadataEntry(metadata_key="region", metadata_value="eu-west")
        )

    with mysql_database.read_session() as session:
        repository = MetadataRepository(session)

        stored = repository.require("region")

        assert stored.metadata_value == "eu-west"
        assert repository.exists("region") is True
        assert repository.count() >= 2
        assert repository.find_one_by(metadata_key="region") is not None

        with pytest.raises(RecordNotFoundError):
            repository.require("missing_key")

    with mysql_database.session() as session:
        assert MetadataRepository(session).delete_by_primary_key("region") is True


def test_modified_migration_is_detected(mysql_database) -> None:
    from sqlalchemy import text

    apply_migrations(mysql_database)

    with mysql_database.session() as session:
        session.execute(
            text(
                "UPDATE schema_migrations SET checksum = 'tampered' WHERE version = 1"
            )
        )

    plan = plan_migrations(mysql_database)

    assert plan.checksum_mismatches

    with pytest.raises(ValueError, match="modified after they ran"):
        apply_migrations(mysql_database)
