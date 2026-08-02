from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import Engine

from aqos.database.base import (
    AQOS_METADATA,
    AQOS_TABLE_ARGS,
    AqosBase,
    AqosMetadataEntry,
    SchemaMigration,
    list_aqos_model_tables,
)
from aqos.database.config import ENV_DB_URL, MySQLDatabaseConfig
from aqos.database.engine import (
    AQOS_DATABASE_ENGINE_VERSION,
    AqosDatabase,
    build_aqos_database_from_env,
    create_aqos_engine,
    create_aqos_session_factory,
)


class FakeSession:
    """Session double so unit tests never need a running MySQL server."""

    def __init__(self, fail_on_execute: bool = False) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False
        self.executed: list[Any] = []
        self.fail_on_execute = fail_on_execute

    def execute(self, statement: Any, parameters: Any = None) -> Any:
        if self.fail_on_execute:
            raise RuntimeError("connection refused")

        self.executed.append(statement)

        return FakeResult()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakeResult:
    returns_rows = True

    def first(self) -> tuple[Any, ...]:
        return ("8.0.36",)


class FakeSessionFactory:
    def __init__(self, fail_on_execute: bool = False) -> None:
        self.sessions: list[FakeSession] = []
        self.fail_on_execute = fail_on_execute

    def __call__(self) -> FakeSession:
        session = FakeSession(fail_on_execute=self.fail_on_execute)
        self.sessions.append(session)

        return session


def build_config(**overrides) -> MySQLDatabaseConfig:
    payload = {
        "host": "db.internal",
        "database": "aqos",
        "user": "aqos_app",
        "password": "s3cret",
    }
    payload.update(overrides)

    return MySQLDatabaseConfig(**payload)


def test_engine_version_is_exposed() -> None:
    assert AQOS_DATABASE_ENGINE_VERSION == "1.0"


def test_create_engine_uses_mysql_dialect_without_connecting() -> None:
    engine = create_aqos_engine(build_config())

    assert isinstance(engine, Engine)
    assert engine.dialect.name == "mysql"
    assert engine.url.database == "aqos"
    assert engine.url.host == "db.internal"

    engine.dispose()


def test_create_engine_applies_pool_options() -> None:
    engine = create_aqos_engine(build_config(pool_size=7, max_overflow=2))

    assert engine.pool.size() == 7

    engine.dispose()


def test_create_session_factory_is_bound_to_engine() -> None:
    engine = create_aqos_engine(build_config())
    factory = create_aqos_session_factory(engine)

    assert factory.kw["bind"] is engine
    assert factory.kw["expire_on_commit"] is False

    engine.dispose()


def test_database_builds_engine_lazily() -> None:
    database = AqosDatabase(config=build_config())

    assert database.describe()["engine_created"] is False

    engine = database.engine

    assert isinstance(engine, Engine)
    assert database.describe()["engine_created"] is True

    database.dispose()


def test_database_requires_a_config_to_build_an_engine() -> None:
    database = AqosDatabase(session_factory=FakeSessionFactory())

    with pytest.raises(ValueError, match="config is required"):
        _ = database.engine


def test_describe_masks_the_password() -> None:
    payload = AqosDatabase(config=build_config()).describe()

    assert "s3cret" not in str(payload)
    assert payload["config"]["safe_url"].endswith("/aqos?charset=utf8mb4")


def test_session_commits_on_success() -> None:
    factory = FakeSessionFactory()
    database = AqosDatabase(session_factory=factory)

    with database.session() as session:
        session.execute("SELECT 1")

    assert factory.sessions[0].committed is True
    assert factory.sessions[0].rolled_back is False
    assert factory.sessions[0].closed is True


def test_session_rolls_back_on_error() -> None:
    factory = FakeSessionFactory()
    database = AqosDatabase(session_factory=factory)

    with pytest.raises(RuntimeError, match="boom"):
        with database.session():
            raise RuntimeError("boom")

    assert factory.sessions[0].committed is False
    assert factory.sessions[0].rolled_back is True
    assert factory.sessions[0].closed is True


def test_read_session_never_commits() -> None:
    factory = FakeSessionFactory()
    database = AqosDatabase(session_factory=factory)

    with database.read_session() as session:
        session.execute("SELECT 1")

    assert factory.sessions[0].committed is False
    assert factory.sessions[0].closed is True


def test_ping_returns_true_when_the_query_succeeds() -> None:
    database = AqosDatabase(session_factory=FakeSessionFactory())

    assert database.ping() is True


def test_ping_returns_false_when_the_database_is_unreachable() -> None:
    database = AqosDatabase(session_factory=FakeSessionFactory(fail_on_execute=True))

    assert database.ping() is False


def test_server_version_reads_the_first_column() -> None:
    database = AqosDatabase(session_factory=FakeSessionFactory())

    assert database.server_version() == "8.0.36"


def test_dispose_resets_engine_state() -> None:
    database = AqosDatabase(config=build_config())
    _ = database.engine

    database.dispose()

    assert database.describe()["engine_created"] is False


def test_context_manager_disposes_the_engine() -> None:
    with AqosDatabase(config=build_config()) as database:
        _ = database.engine

    assert database.describe()["engine_created"] is False


def test_build_database_from_env(monkeypatch) -> None:
    monkeypatch.setenv(
        ENV_DB_URL,
        "mysql+pymysql://aqos_app:pw@db.internal:3306/aqos_prod",
    )

    database = build_aqos_database_from_env()

    assert database.config is not None
    assert database.config.database == "aqos_prod"


def test_base_metadata_uses_naming_conventions_and_innodb() -> None:
    assert AQOS_METADATA.naming_convention["pk"] == "pk_%(table_name)s"
    assert AQOS_TABLE_ARGS["mysql_engine"] == "InnoDB"
    assert AQOS_TABLE_ARGS["mysql_charset"] == "utf8mb4"


def test_baseline_models_are_registered() -> None:
    tables = list_aqos_model_tables()

    assert "schema_migrations" in tables
    assert "aqos_metadata" in tables


def test_models_expose_to_dict() -> None:
    migration = SchemaMigration(version=1, name="baseline", checksum="abc")

    payload = migration.to_dict()

    assert payload["version"] == 1
    assert payload["name"] == "baseline"
    assert "SchemaMigration(version=1" in repr(migration)


def test_models_reject_the_reserved_metadata_keyword() -> None:
    """
    ``metadata`` is SQLAlchemy's MetaData on every declarative class.

    Passing it as a column value would shadow the mapper registry instead of
    raising, silently losing the value, so it is refused outright.
    """

    with pytest.raises(TypeError, match="reserved by SQLAlchemy"):
        AqosMetadataEntry(
            metadata_key="k",
            metadata_value="v",
            metadata={"oops": True},
        )


def test_metadata_entry_repr() -> None:
    entry = AqosMetadataEntry(metadata_key="schema_owner", metadata_value="aqos")

    assert "schema_owner" in repr(entry)
    assert issubclass(AqosMetadataEntry, AqosBase)
