from __future__ import annotations

from typing import Any

import pytest

from aqos.database.engine import AqosDatabase
from aqos.database.procedures import (
    AQOS_PROCEDURES_VERSION,
    OUT_VARIABLE_PREFIX,
    StoredProcedureError,
    StoredProcedureResult,
    StoredProcedureService,
    build_call_statement,
    build_out_variable_name,
    build_parameter_bindings,
    build_parameter_names,
    call_stored_procedure_on_session,
    normalize_procedure_name,
    rows_from_result,
)


class FakeMappings:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def all(self) -> list[dict[str, Any]]:
        return list(self._rows)


class FakeResult:
    def __init__(
        self,
        rows: list[dict[str, Any]] | None = None,
        returns_rows: bool = True,
        first_row: tuple[Any, ...] | None = None,
    ) -> None:
        self._rows = rows or []
        self.returns_rows = returns_rows
        self._first_row = first_row

    def mappings(self) -> FakeMappings:
        return FakeMappings(self._rows)

    def first(self) -> tuple[Any, ...] | None:
        return self._first_row


class FakeSession:
    """Records executed statements and bindings without touching a server."""

    def __init__(self, results: list[FakeResult] | None = None) -> None:
        self.results = results or []
        self.executed: list[tuple[str, dict[str, Any] | None]] = []
        self.committed = False
        self.closed = False

    def execute(self, statement: Any, parameters: Any = None) -> FakeResult:
        self.executed.append((str(statement), parameters))

        if self.results:
            return self.results.pop(0)

        return FakeResult()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True


class FakeSessionFactory:
    def __init__(self, session: FakeSession) -> None:
        self.session = session

    def __call__(self) -> FakeSession:
        return self.session


def build_service(session: FakeSession) -> StoredProcedureService:
    return StoredProcedureService(
        AqosDatabase(session_factory=FakeSessionFactory(session))  # type: ignore[arg-type]
    )


def test_procedures_version_is_exposed() -> None:
    assert AQOS_PROCEDURES_VERSION == "1.0"


def test_normalize_procedure_name_accepts_identifiers() -> None:
    assert normalize_procedure_name(" sp_aqos_schema_version ") == (
        "sp_aqos_schema_version"
    )
    assert normalize_procedure_name("sp$legacy_1") == "sp$legacy_1"


def test_normalize_procedure_name_rejects_injection_attempts() -> None:
    unsafe_names = (
        "sp_demo; DROP TABLE users",
        "sp_demo()",
        "sp demo",
        "1sp_demo",
        "`sp_demo`",
        "sp_demo--",
    )

    for name in unsafe_names:
        with pytest.raises(StoredProcedureError, match="Unsafe stored procedure name"):
            normalize_procedure_name(name)


def test_normalize_procedure_name_rejects_empty_and_overlong() -> None:
    with pytest.raises(StoredProcedureError, match="cannot be empty"):
        normalize_procedure_name("   ")

    with pytest.raises(StoredProcedureError, match="Unsafe stored procedure name"):
        normalize_procedure_name("sp_" + "x" * 70)


def test_build_parameter_names() -> None:
    assert build_parameter_names(0) == ()
    assert build_parameter_names(3) == ("p0", "p1", "p2")

    with pytest.raises(StoredProcedureError, match="cannot be negative"):
        build_parameter_names(-1)


def test_build_out_variable_name() -> None:
    assert build_out_variable_name("total") == f"{OUT_VARIABLE_PREFIX}total"

    with pytest.raises(StoredProcedureError, match="Unsafe stored procedure out"):
        build_out_variable_name("total; DROP TABLE users")

    with pytest.raises(StoredProcedureError, match="Unsafe stored procedure out"):
        build_out_variable_name("  ")


def test_build_call_statement_without_parameters() -> None:
    assert build_call_statement("sp_aqos_schema_version") == (
        "CALL sp_aqos_schema_version()"
    )


def test_build_call_statement_binds_every_parameter() -> None:
    statement = build_call_statement("sp_demo", ("p0", "p1"))

    assert statement == "CALL sp_demo(:p0, :p1)"


def test_build_call_statement_includes_out_variables() -> None:
    statement = build_call_statement(
        "sp_aqos_metadata_count",
        (),
        ("@aqos_out_total",),
    )

    assert statement == "CALL sp_aqos_metadata_count(@aqos_out_total)"


def test_build_call_statement_validates_the_name() -> None:
    with pytest.raises(StoredProcedureError, match="Unsafe stored procedure name"):
        build_call_statement("sp_demo; DROP TABLE users")


def test_build_parameter_bindings() -> None:
    assert build_parameter_bindings(("aqos", 7)) == {"p0": "aqos", "p1": 7}
    assert build_parameter_bindings(()) == {}


def test_rows_from_result() -> None:
    assert rows_from_result(None) == ()
    assert rows_from_result(FakeResult(returns_rows=False)) == ()
    assert rows_from_result(FakeResult(rows=[{"a": 1}])) == ({"a": 1},)


def test_stored_procedure_result_payload() -> None:
    result = StoredProcedureResult(
        procedure_name="sp_demo",
        rows=({"schema_version": 2},),
        out_values={"total": 5},
    )

    assert result.row_count == 1
    assert result.first_row == {"schema_version": 2}
    assert result.to_dict()["out_values"] == {"total": 5}

    assert StoredProcedureResult(procedure_name="sp_demo").first_row is None


def test_call_on_session_binds_parameters() -> None:
    session = FakeSession(results=[FakeResult(rows=[{"schema_version": 2}])])

    result = call_stored_procedure_on_session(
        session=session,  # type: ignore[arg-type]
        procedure_name="sp_aqos_set_metadata",
        parameters=("schema_owner", "aqos"),
    )

    statement, bindings = session.executed[0]

    assert statement == "CALL sp_aqos_set_metadata(:p0, :p1)"
    assert bindings == {"p0": "schema_owner", "p1": "aqos"}
    assert result.rows == ({"schema_version": 2},)
    assert result.procedure_name == "sp_aqos_set_metadata"


def test_call_on_session_reads_out_parameters() -> None:
    session = FakeSession(
        results=[
            FakeResult(returns_rows=False),
            FakeResult(first_row=(12,)),
        ]
    )

    result = call_stored_procedure_on_session(
        session=session,  # type: ignore[arg-type]
        procedure_name="sp_aqos_metadata_count",
        out_parameters=("total",),
    )

    call_statement, _ = session.executed[0]
    select_statement, _ = session.executed[1]

    assert call_statement == "CALL sp_aqos_metadata_count(@aqos_out_total)"
    assert select_statement == "SELECT @aqos_out_total"
    assert result.out_values == {"total": 12}
    assert result.rows == ()


def test_call_on_session_rejects_unsafe_names() -> None:
    session = FakeSession()

    with pytest.raises(StoredProcedureError, match="Unsafe stored procedure name"):
        call_stored_procedure_on_session(
            session=session,  # type: ignore[arg-type]
            procedure_name="sp_demo; DROP TABLE users",
        )

    assert session.executed == []


def test_service_call_commits() -> None:
    session = FakeSession(results=[FakeResult(rows=[{"schema_version": 2}])])
    service = build_service(session)

    result = service.call("sp_aqos_schema_version")

    assert result.first_row == {"schema_version": 2}
    assert session.committed is True
    assert session.closed is True


def test_service_read_only_call_does_not_commit() -> None:
    session = FakeSession(results=[FakeResult(rows=[{"schema_version": 2}])])
    service = build_service(session)

    service.call_read_only("sp_aqos_schema_version")

    assert session.committed is False
    assert session.closed is True


def test_service_lists_procedures() -> None:
    session = FakeSession()
    session.results = [FakeResult()]
    service = build_service(session)

    class _RoutineResult(FakeResult):
        def all(self) -> list[tuple[str]]:
            return [("sp_aqos_schema_version",), ("sp_aqos_set_metadata",)]

    session.results = [_RoutineResult()]

    assert service.list_procedures() == (
        "sp_aqos_schema_version",
        "sp_aqos_set_metadata",
    )


def test_service_checks_procedure_existence() -> None:
    session = FakeSession(results=[FakeResult(first_row=(1,))])
    service = build_service(session)

    assert service.procedure_exists("sp_aqos_schema_version") is True

    statement, bindings = session.executed[0]

    assert "information_schema.ROUTINES" in statement
    assert bindings == {"procedure_name": "sp_aqos_schema_version"}


def test_service_reports_missing_procedure() -> None:
    session = FakeSession(results=[FakeResult(first_row=None)])
    service = build_service(session)

    assert service.procedure_exists("sp_missing") is False


def test_service_drop_procedure_validates_the_name() -> None:
    session = FakeSession()
    service = build_service(session)

    service.drop_procedure("sp_aqos_schema_version")

    statement, _ = session.executed[0]

    assert statement == "DROP PROCEDURE IF EXISTS sp_aqos_schema_version"

    with pytest.raises(StoredProcedureError, match="Unsafe stored procedure name"):
        service.drop_procedure("sp_demo; DROP TABLE users")
