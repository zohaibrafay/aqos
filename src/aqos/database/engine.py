from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from aqos.database.config import (
    MySQLDatabaseConfig,
    load_database_config_from_env,
    validate_mysql_driver,
)


AQOS_DATABASE_ENGINE_VERSION = "1.0"


def create_aqos_engine(config: MySQLDatabaseConfig) -> Engine:
    """
    Build a SQLAlchemy engine for the AQOS MySQL database.

    The engine is lazy: no connection is opened until it is first used.
    """

    validate_mysql_driver(config.driver)

    return create_engine(config.url(), **config.engine_options())


def create_aqos_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
        future=True,
    )


class AqosDatabase:
    """
    Owns the SQLAlchemy engine and hands out sessions.

    ``session()`` commits on success and rolls back on failure, so callers
    never leave a half-applied unit of work behind.
    """

    def __init__(
        self,
        config: MySQLDatabaseConfig | None = None,
        engine: Engine | None = None,
        session_factory: sessionmaker[Session] | None = None,
    ) -> None:
        if config is None and engine is None and session_factory is None:
            config = load_database_config_from_env()

        self.config = config
        self._engine = engine
        self._session_factory = session_factory

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            if self.config is None:
                raise ValueError("A database config is required to build an engine.")

            self._engine = create_aqos_engine(self.config)

        return self._engine

    @property
    def session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            self._session_factory = create_aqos_session_factory(self.engine)

        return self._session_factory

    def new_session(self) -> Session:
        return self.session_factory()

    @contextmanager
    def session(self) -> Iterator[Session]:
        session = self.new_session()

        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @contextmanager
    def read_session(self) -> Iterator[Session]:
        """A session that never commits, for queries and reports."""

        session = self.new_session()

        try:
            yield session
        finally:
            session.close()

    def ping(self) -> bool:
        """Return True when the database answers a trivial query."""

        try:
            with self.read_session() as session:
                session.execute(text("SELECT 1"))
        except Exception:
            return False

        return True

    def server_version(self) -> str | None:
        with self.read_session() as session:
            row = session.execute(text("SELECT VERSION()")).first()

        return str(row[0]) if row is not None else None

    def dispose(self) -> None:
        if self._engine is not None:
            self._engine.dispose()

        self._engine = None
        self._session_factory = None

    def describe(self) -> dict[str, Any]:
        return {
            "config": self.config.to_dict() if self.config is not None else None,
            "engine_created": self._engine is not None,
        }

    def __enter__(self) -> "AqosDatabase":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.dispose()


def build_aqos_database_from_env() -> AqosDatabase:
    return AqosDatabase(config=load_database_config_from_env())


__all__ = [
    "AQOS_DATABASE_ENGINE_VERSION",
    "AqosDatabase",
    "build_aqos_database_from_env",
    "create_aqos_engine",
    "create_aqos_session_factory",
]
