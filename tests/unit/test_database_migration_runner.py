from __future__ import annotations

from pathlib import Path

import pytest

from aqos.database.migration_runner import (
    AQOS_MIGRATIONS_VERSION,
    AppliedMigration,
    MIGRATIONS_DIRECTORY,
    MigrationPlan,
    MigrationRunResult,
    MigrationScript,
    build_migration_plan,
    discover_migration_scripts,
    load_migration_script,
    parse_migration_filename,
    split_sql_statements,
)


def write_migration(directory: Path, filename: str, sql: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(sql, encoding="utf-8")

    return path


def build_script(version: int = 1, name: str = "baseline", sql: str = "SELECT 1;"):
    return MigrationScript(
        version=version,
        name=name,
        path=Path(f"V{version:04d}__{name}.sql"),
        sql=sql,
    )


def test_migrations_version_is_exposed() -> None:
    assert AQOS_MIGRATIONS_VERSION == "1.0"


def test_parse_migration_filename() -> None:
    assert parse_migration_filename("V0001__aqos_baseline.sql") == (1, "aqos_baseline")
    assert parse_migration_filename("V0042__add_accounts.sql") == (42, "add_accounts")


def test_parse_migration_filename_rejects_bad_names() -> None:
    for filename in ("baseline.sql", "V1__baseline.sql", "V0001-baseline.sql"):
        with pytest.raises(ValueError, match="must look like V0001__name.sql"):
            parse_migration_filename(filename)


def test_script_validation() -> None:
    with pytest.raises(ValueError, match="version must be at least 1"):
        build_script(version=0)

    with pytest.raises(ValueError, match="name cannot be empty"):
        build_script(name="  ")

    with pytest.raises(ValueError, match="Migration file is empty"):
        build_script(sql="   ")


def test_script_checksum_is_content_based() -> None:
    first = build_script(sql="SELECT 1;")
    second = build_script(sql="SELECT 1;")
    changed = build_script(sql="SELECT 2;")

    assert first.checksum == second.checksum
    assert first.checksum != changed.checksum
    assert len(first.checksum) == 64


def test_script_dict_payload() -> None:
    payload = build_script(sql="SELECT 1;\nSELECT 2;").to_dict()

    assert payload["version"] == 1
    assert payload["filename"] == "V0001__baseline.sql"
    assert payload["statement_count"] == 2


def test_split_simple_statements() -> None:
    statements = split_sql_statements(
        "CREATE TABLE a (id INT);\nCREATE TABLE b (id INT);"
    )

    assert statements == ("CREATE TABLE a (id INT)", "CREATE TABLE b (id INT)")


def test_split_ignores_leading_comments() -> None:
    statements = split_sql_statements(
        "-- a comment\n-- another comment\nSELECT 1;"
    )

    assert statements == ("SELECT 1",)


def test_split_keeps_stored_procedure_bodies_together() -> None:
    sql = (
        "DROP PROCEDURE IF EXISTS sp_demo;\n"
        "DELIMITER $$\n"
        "CREATE PROCEDURE sp_demo()\n"
        "BEGIN\n"
        "    SELECT 1;\n"
        "    SELECT 2;\n"
        "END $$\n"
        "DELIMITER ;\n"
    )

    statements = split_sql_statements(sql)

    assert len(statements) == 2
    assert statements[0] == "DROP PROCEDURE IF EXISTS sp_demo"
    assert statements[1].startswith("CREATE PROCEDURE sp_demo()")
    assert statements[1].endswith("END")
    assert "SELECT 1;" in statements[1]


def test_split_handles_trailing_statement_without_semicolon() -> None:
    assert split_sql_statements("SELECT 1") == ("SELECT 1",)


def test_split_returns_nothing_for_blank_sql() -> None:
    assert split_sql_statements("\n\n   \n") == ()


def test_load_migration_script(tmp_path) -> None:
    path = write_migration(tmp_path, "V0003__demo.sql", "SELECT 1;")

    script = load_migration_script(path)

    assert script.version == 3
    assert script.name == "demo"
    assert script.sql.strip() == "SELECT 1;"


def test_load_migration_script_rejects_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="does not exist"):
        load_migration_script(tmp_path / "V0001__missing.sql")


def test_discover_orders_scripts_by_version(tmp_path) -> None:
    write_migration(tmp_path, "V0010__ten.sql", "SELECT 10;")
    write_migration(tmp_path, "V0002__two.sql", "SELECT 2;")
    write_migration(tmp_path, "V0001__one.sql", "SELECT 1;")

    scripts = discover_migration_scripts(tmp_path)

    assert [script.version for script in scripts] == [1, 2, 10]


def test_discover_rejects_missing_directory(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="Migrations directory does not exist"):
        discover_migration_scripts(tmp_path / "nope")


def test_discover_rejects_bad_filenames(tmp_path) -> None:
    write_migration(tmp_path, "not_a_migration.sql", "SELECT 1;")

    with pytest.raises(ValueError, match="must look like V0001__name.sql"):
        discover_migration_scripts(tmp_path)


def test_shipped_migrations_are_discoverable() -> None:
    scripts = discover_migration_scripts()

    assert MIGRATIONS_DIRECTORY.exists()
    assert scripts
    assert scripts[0].name == "aqos_baseline"
    assert scripts[1].name == "aqos_schema_procedures"


def test_shipped_migration_versions_are_contiguous_from_one() -> None:
    """A gap or duplicate would silently skip a migration on a fresh database."""

    versions = [script.version for script in discover_migration_scripts()]

    assert versions == list(range(1, len(versions) + 1))


def test_shipped_migrations_have_unique_names() -> None:
    names = [script.name for script in discover_migration_scripts()]

    assert len(names) == len(set(names))


def test_shipped_baseline_creates_the_expected_tables() -> None:
    baseline = discover_migration_scripts()[0]
    statements = baseline.statements()

    joined = "\n".join(statements)

    assert "CREATE TABLE IF NOT EXISTS schema_migrations" in joined
    assert "CREATE TABLE IF NOT EXISTS aqos_metadata" in joined
    assert "ENGINE=InnoDB" in joined
    assert all("DELIMITER" not in statement for statement in statements)


def test_shipped_procedures_migration_holds_complete_bodies() -> None:
    procedures = discover_migration_scripts()[1]
    statements = procedures.statements()

    creates = [
        statement
        for statement in statements
        if statement.startswith("CREATE PROCEDURE")
    ]

    assert len(creates) == 3
    assert all(statement.endswith("END") for statement in creates)
    assert any("sp_aqos_schema_version" in statement for statement in creates)
    assert any("sp_aqos_metadata_count" in statement for statement in creates)
    assert all("DELIMITER" not in statement for statement in statements)


def test_plan_lists_everything_as_pending_when_nothing_is_applied() -> None:
    scripts = (build_script(1, "one"), build_script(2, "two", "SELECT 2;"))

    plan = build_migration_plan(scripts, ())

    assert plan.current_version == 0
    assert plan.target_version == 2
    assert plan.is_up_to_date is False
    assert [script.version for script in plan.pending] == [1, 2]


def test_plan_is_up_to_date_when_all_applied() -> None:
    script = build_script(1, "one")
    applied = (
        AppliedMigration(version=1, name="one", checksum=script.checksum),
    )

    plan = build_migration_plan((script,), applied)

    assert plan.is_up_to_date is True
    assert plan.current_version == 1
    assert plan.target_version == 1
    assert plan.pending == ()

    plan.raise_if_corrupted()


def test_plan_detects_modified_migrations() -> None:
    script = build_script(1, "one", "SELECT 1;")
    applied = (AppliedMigration(version=1, name="one", checksum="stale"),)

    plan = build_migration_plan((script,), applied)

    assert plan.checksum_mismatches
    assert "V0001__one.sql checksum changed" in plan.checksum_mismatches[0]

    with pytest.raises(ValueError, match="modified after they ran"):
        plan.raise_if_corrupted()


def test_plan_dict_payload() -> None:
    plan = build_migration_plan((build_script(1, "one"),), ())

    payload = plan.to_dict()

    assert payload["current_version"] == 0
    assert payload["target_version"] == 1
    assert payload["is_up_to_date"] is False
    assert payload["pending"][0]["name"] == "one"


def test_empty_plan_is_up_to_date() -> None:
    plan = MigrationPlan()

    assert plan.is_up_to_date is True
    assert plan.current_version == 0
    assert plan.target_version == 0


def test_run_result_payload() -> None:
    result = MigrationRunResult(
        applied_versions=(1, 2),
        current_version=2,
        statements_executed=6,
    )

    payload = result.to_dict()

    assert payload["applied_count"] == 2
    assert payload["current_version"] == 2
    assert payload["statements_executed"] == 6


def test_applied_migration_payload() -> None:
    payload = AppliedMigration(
        version=1,
        name="one",
        checksum="abc",
        applied_at_utc="2026-01-01 00:00:00",
    ).to_dict()

    assert payload["version"] == 1
    assert payload["applied_at_utc"] == "2026-01-01 00:00:00"
