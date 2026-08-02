from __future__ import annotations

from typing import Any

import pytest

from aqos.database.base import AqosMetadataEntry
from aqos.database.repository import (
    AQOS_REPOSITORY_VERSION,
    AqosRepository,
    RecordNotFoundError,
    RepositoryError,
)


class FakeScalars:
    def __init__(self, values: list[Any]) -> None:
        self._values = values

    def all(self) -> list[Any]:
        return list(self._values)


class FakeResult:
    def __init__(self, values: list[Any] | None = None, scalar: Any = None) -> None:
        self._values = values or []
        self._scalar = scalar
        self.rowcount = len(self._values)

    def scalars(self) -> FakeScalars:
        return FakeScalars(self._values)

    def scalar(self) -> Any:
        return self._scalar


class FakeSession:
    """Session double: records calls and returns canned results."""

    def __init__(
        self,
        get_result: Any = None,
        execute_values: list[Any] | None = None,
        scalar_result: Any = None,
        delete_rowcount: int = 0,
    ) -> None:
        self.get_result = get_result
        self.execute_values = execute_values or []
        self.scalar_result = scalar_result
        self.delete_rowcount = delete_rowcount

        self.added: list[Any] = []
        self.deleted: list[Any] = []
        self.statements: list[Any] = []
        self.flushed = False
        self.refreshed: list[Any] = []

    def add(self, entity: Any) -> None:
        self.added.append(entity)

    def add_all(self, entities: list[Any]) -> None:
        self.added.extend(entities)

    def get(self, model: Any, primary_key: Any) -> Any:
        self.statements.append(("get", model, primary_key))
        return self.get_result

    def delete(self, entity: Any) -> None:
        self.deleted.append(entity)

    def execute(self, statement: Any, parameters: Any = None) -> FakeResult:
        self.statements.append(statement)

        compiled = str(statement).strip().upper()

        if compiled.startswith("DELETE"):
            result = FakeResult()
            result.rowcount = self.delete_rowcount
            return result

        return FakeResult(values=self.execute_values, scalar=self.scalar_result)

    def flush(self) -> None:
        self.flushed = True

    def refresh(self, entity: Any) -> None:
        self.refreshed.append(entity)


class MetadataRepository(AqosRepository[AqosMetadataEntry]):
    model = AqosMetadataEntry


class ModellessRepository(AqosRepository):
    pass


def build_entry(key: str = "schema_owner", value: str = "aqos") -> AqosMetadataEntry:
    return AqosMetadataEntry(metadata_key=key, metadata_value=value)


def test_repository_version_is_exposed() -> None:
    assert AQOS_REPOSITORY_VERSION == "1.0"


def test_repository_requires_a_session() -> None:
    with pytest.raises(ValueError, match="session is required"):
        MetadataRepository(None)  # type: ignore[arg-type]


def test_repository_requires_a_model() -> None:
    with pytest.raises(ValueError, match="must define a model"):
        ModellessRepository(FakeSession())  # type: ignore[arg-type]


def test_repository_does_not_own_the_session() -> None:
    session = FakeSession()
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    assert repository.session is session


def test_add_and_add_all() -> None:
    session = FakeSession()
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    first = build_entry("a")
    second = build_entry("b")

    assert repository.add(first) is first
    assert repository.add_all([second]) == (second,)
    assert session.added == [first, second]


def test_get_returns_the_session_result() -> None:
    entry = build_entry()
    session = FakeSession(get_result=entry)
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    assert repository.get("schema_owner") is entry
    assert session.statements[0] == ("get", AqosMetadataEntry, "schema_owner")


def test_get_returns_none_when_missing() -> None:
    repository = MetadataRepository(FakeSession())  # type: ignore[arg-type]

    assert repository.get("missing") is None


def test_require_raises_when_missing() -> None:
    repository = MetadataRepository(FakeSession())  # type: ignore[arg-type]

    with pytest.raises(RecordNotFoundError, match="AqosMetadataEntry does not exist"):
        repository.require("missing")


def test_require_returns_the_entity() -> None:
    entry = build_entry()
    repository = MetadataRepository(FakeSession(get_result=entry))  # type: ignore[arg-type]

    assert repository.require("schema_owner") is entry


def test_exists() -> None:
    assert MetadataRepository(
        FakeSession(get_result=build_entry())  # type: ignore[arg-type]
    ).exists("schema_owner") is True
    assert MetadataRepository(FakeSession()).exists("missing") is False  # type: ignore[arg-type]


def test_list_all_returns_scalars() -> None:
    entries = [build_entry("a"), build_entry("b")]
    repository = MetadataRepository(
        FakeSession(execute_values=entries)  # type: ignore[arg-type]
    )

    assert repository.list_all() == tuple(entries)


def test_list_all_applies_a_limit() -> None:
    session = FakeSession(execute_values=[build_entry()])
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    repository.list_all(limit=5)

    assert "LIMIT" in str(session.statements[0]).upper()


def test_find_by_builds_a_filtered_select() -> None:
    session = FakeSession(execute_values=[build_entry()])
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    results = repository.find_by(metadata_key="schema_owner")

    assert len(results) == 1
    assert "WHERE" in str(session.statements[0]).upper()


def test_find_by_rejects_unknown_columns() -> None:
    repository = MetadataRepository(FakeSession())  # type: ignore[arg-type]

    with pytest.raises(RepositoryError, match="has no column named nope"):
        repository.find_by(nope="value")


def test_find_one_by_returns_single_result() -> None:
    entry = build_entry()
    repository = MetadataRepository(
        FakeSession(execute_values=[entry])  # type: ignore[arg-type]
    )

    assert repository.find_one_by(metadata_key="schema_owner") is entry


def test_find_one_by_returns_none_when_empty() -> None:
    repository = MetadataRepository(FakeSession())  # type: ignore[arg-type]

    assert repository.find_one_by(metadata_key="missing") is None


def test_find_one_by_rejects_multiple_results() -> None:
    repository = MetadataRepository(
        FakeSession(execute_values=[build_entry("a"), build_entry("b")])  # type: ignore[arg-type]
    )

    with pytest.raises(RepositoryError, match="Expected at most one"):
        repository.find_one_by(metadata_key="schema_owner")


def test_count_reads_the_scalar_result() -> None:
    repository = MetadataRepository(
        FakeSession(scalar_result=4)  # type: ignore[arg-type]
    )

    assert repository.count() == 4
    assert MetadataRepository(FakeSession()).count() == 0  # type: ignore[arg-type]


def test_count_supports_filters() -> None:
    session = FakeSession(scalar_result=1)
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    repository.count(metadata_key="schema_owner")

    assert "WHERE" in str(session.statements[0]).upper()


def test_delete_passes_the_entity_to_the_session() -> None:
    session = FakeSession()
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    entry = build_entry()
    repository.delete(entry)

    assert session.deleted == [entry]


def test_delete_by_primary_key() -> None:
    entry = build_entry()
    session = FakeSession(get_result=entry)
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    assert repository.delete_by_primary_key("schema_owner") is True
    assert session.deleted == [entry]

    assert MetadataRepository(
        FakeSession()  # type: ignore[arg-type]
    ).delete_by_primary_key("missing") is False


def test_delete_where_returns_row_count() -> None:
    session = FakeSession(delete_rowcount=3)
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    assert repository.delete_where(metadata_key="schema_owner") == 3
    assert "DELETE" in str(session.statements[0]).upper()


def test_flush_and_refresh() -> None:
    session = FakeSession()
    repository = MetadataRepository(session)  # type: ignore[arg-type]

    entry = build_entry()

    repository.flush()
    assert repository.refresh(entry) is entry

    assert session.flushed is True
    assert session.refreshed == [entry]


def test_record_not_found_is_a_repository_error() -> None:
    assert issubclass(RecordNotFoundError, RepositoryError)
    assert issubclass(RepositoryError, RuntimeError)
