from __future__ import annotations

import re
from dataclasses import dataclass, field as dataclass_field
from typing import Any, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from aqos.database.engine import AqosDatabase


AQOS_PROCEDURES_VERSION = "1.0"

#: MySQL identifiers: letters, digits, underscore and dollar, max 64 characters.
PROCEDURE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,63}$")

PARAMETER_PREFIX = "p"
OUT_VARIABLE_PREFIX = "@aqos_out_"


class StoredProcedureError(RuntimeError):
    """Raised when a stored procedure cannot be called safely."""


def normalize_procedure_name(name: str) -> str:
    """
    Validate a stored procedure name.

    Procedure names cannot be bound as query parameters, so the name is
    validated against a strict identifier pattern instead of being escaped.
    """

    clean_name = name.strip()

    if not clean_name:
        raise StoredProcedureError("Stored procedure name cannot be empty.")

    if not PROCEDURE_NAME_PATTERN.match(clean_name):
        raise StoredProcedureError(
            f"Unsafe stored procedure name: {name}. Names must be plain MySQL "
            "identifiers."
        )

    return clean_name


def build_parameter_names(count: int) -> tuple[str, ...]:
    if count < 0:
        raise StoredProcedureError("Parameter count cannot be negative.")

    return tuple(f"{PARAMETER_PREFIX}{index}" for index in range(count))


def build_out_variable_name(parameter_name: str) -> str:
    clean_name = parameter_name.strip()

    if not clean_name or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", clean_name):
        raise StoredProcedureError(
            f"Unsafe stored procedure out parameter name: {parameter_name}"
        )

    return f"{OUT_VARIABLE_PREFIX}{clean_name}"


def build_call_statement(
    procedure_name: str,
    parameter_names: Sequence[str] = (),
    out_variable_names: Sequence[str] = (),
) -> str:
    """Build a parameterized ``CALL`` statement for a stored procedure."""

    safe_name = normalize_procedure_name(procedure_name)

    arguments = [f":{name}" for name in parameter_names]
    arguments.extend(out_variable_names)

    return f"CALL {safe_name}({', '.join(arguments)})"


def build_parameter_bindings(
    parameters: Sequence[Any],
) -> dict[str, Any]:
    return {
        name: value
        for name, value in zip(build_parameter_names(len(parameters)), parameters)
    }


@dataclass(frozen=True)
class StoredProcedureResult:
    procedure_name: str
    rows: tuple[dict[str, Any], ...] = ()
    out_values: dict[str, Any] = dataclass_field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def first_row(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "procedure_name": self.procedure_name,
            "row_count": self.row_count,
            "rows": [dict(row) for row in self.rows],
            "out_values": self.out_values,
        }


def rows_from_result(result: Any) -> tuple[dict[str, Any], ...]:
    if result is None or not getattr(result, "returns_rows", False):
        return ()

    return tuple(dict(row) for row in result.mappings().all())


def call_stored_procedure_on_session(
    session: Session,
    procedure_name: str,
    parameters: Sequence[Any] = (),
    out_parameters: Sequence[str] = (),
) -> StoredProcedureResult:
    """Call a stored procedure using bound parameters on an existing session."""

    safe_name = normalize_procedure_name(procedure_name)

    parameter_names = build_parameter_names(len(parameters))
    out_variables = tuple(build_out_variable_name(name) for name in out_parameters)

    statement = build_call_statement(
        procedure_name=safe_name,
        parameter_names=parameter_names,
        out_variable_names=out_variables,
    )

    result = session.execute(
        text(statement),
        build_parameter_bindings(parameters),
    )
    rows = rows_from_result(result)

    out_values: dict[str, Any] = {}

    if out_variables:
        selected = session.execute(
            text("SELECT " + ", ".join(out_variables))
        ).first()

        if selected is not None:
            out_values = {
                name: selected[index]
                for index, name in enumerate(out_parameters)
            }

    return StoredProcedureResult(
        procedure_name=safe_name,
        rows=rows,
        out_values=out_values,
    )


class StoredProcedureService:
    """
    Calls MySQL stored procedures safely.

    Procedure names are validated as identifiers and every argument is bound,
    so nothing a caller supplies is ever concatenated into SQL.
    """

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database

    def call(
        self,
        procedure_name: str,
        parameters: Sequence[Any] = (),
        out_parameters: Sequence[str] = (),
    ) -> StoredProcedureResult:
        with self.database.session() as session:
            return call_stored_procedure_on_session(
                session=session,
                procedure_name=procedure_name,
                parameters=parameters,
                out_parameters=out_parameters,
            )

    def call_read_only(
        self,
        procedure_name: str,
        parameters: Sequence[Any] = (),
    ) -> StoredProcedureResult:
        with self.database.read_session() as session:
            return call_stored_procedure_on_session(
                session=session,
                procedure_name=procedure_name,
                parameters=parameters,
            )

    def list_procedures(self) -> tuple[str, ...]:
        with self.database.read_session() as session:
            rows = session.execute(
                text(
                    "SELECT ROUTINE_NAME FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_TYPE = 'PROCEDURE' "
                    "AND ROUTINE_SCHEMA = DATABASE() "
                    "ORDER BY ROUTINE_NAME"
                )
            ).all()

        return tuple(str(row[0]) for row in rows)

    def procedure_exists(self, procedure_name: str) -> bool:
        safe_name = normalize_procedure_name(procedure_name)

        with self.database.read_session() as session:
            row = session.execute(
                text(
                    "SELECT 1 FROM information_schema.ROUTINES "
                    "WHERE ROUTINE_TYPE = 'PROCEDURE' "
                    "AND ROUTINE_SCHEMA = DATABASE() "
                    "AND ROUTINE_NAME = :procedure_name"
                ),
                {"procedure_name": safe_name},
            ).first()

        return row is not None

    def drop_procedure(self, procedure_name: str) -> None:
        safe_name = normalize_procedure_name(procedure_name)

        with self.database.session() as session:
            session.execute(text(f"DROP PROCEDURE IF EXISTS {safe_name}"))


__all__ = [
    "AQOS_PROCEDURES_VERSION",
    "OUT_VARIABLE_PREFIX",
    "PARAMETER_PREFIX",
    "PROCEDURE_NAME_PATTERN",
    "StoredProcedureError",
    "StoredProcedureResult",
    "StoredProcedureService",
    "build_call_statement",
    "build_out_variable_name",
    "build_parameter_bindings",
    "build_parameter_names",
    "call_stored_procedure_on_session",
    "normalize_procedure_name",
    "rows_from_result",
]
