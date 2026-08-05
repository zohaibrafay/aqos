from __future__ import annotations

from typing import Any, Iterator

from sqlalchemy.orm import Session
from starlette.requests import Request

from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.http_api.config import ApiConfig
from aqos.http_api.errors import DatabaseUnavailableApiError


AQOS_HTTP_DEPENDENCIES_VERSION = "1.0"

#: Where the shared database handle lives on the app.
DATABASE_STATE_KEY = "aqos_database"

#: Where the resolved config lives on the app.
CONFIG_STATE_KEY = "aqos_api_config"


def build_database(config: ApiConfig) -> AqosDatabase | None:
    """
    Create the database handle for an app, or None when none is configured.

    Creating an ``AqosDatabase`` does not connect: SQLAlchemy pools lazily, so
    an app can still start and serve its liveness endpoint while MySQL is down.
    """

    if not config.has_database:
        return None

    return AqosDatabase(config=parse_database_url(config.database_url))


def get_api_config(request: Request) -> ApiConfig:
    config = getattr(request.app.state, CONFIG_STATE_KEY, None)

    if config is None:
        raise RuntimeError(
            "The API app has no configuration; build it with "
            "create_aqos_api_app()."
        )

    return config


def get_database(request: Request) -> AqosDatabase:
    """The app's database handle, or a 503 when the API has none."""

    database = getattr(request.app.state, DATABASE_STATE_KEY, None)

    if database is None:
        raise DatabaseUnavailableApiError(
            "This deployment has no database configured."
        )

    return database


def get_optional_database(request: Request) -> AqosDatabase | None:
    """The database handle without raising, for readiness reporting."""

    return getattr(request.app.state, DATABASE_STATE_KEY, None)


def get_session(request: Request) -> Iterator[Session]:
    """
    One SQLAlchemy session per request.

    The request owns the lifecycle. Nothing is committed here: a read handler
    that accidentally committed would turn a GET into a write, so a handler that
    means to write has to say so itself. A failure rolls back, and the session
    is always closed.
    """

    database = get_database(request)
    session = database.session_factory()

    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_write_session(request: Request) -> Iterator[Session]:
    """
    A session that commits when the handler returns without raising.

    Kept separate from :func:`get_session` so that committing is always a choice
    the handler made, never something a read path inherited.
    """

    database = get_database(request)
    session = database.session_factory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def describe_database_readiness(
    database: AqosDatabase | None,
) -> dict[str, Any]:
    """
    Report whether the database can be reached, without leaking how.

    No URL, host or credential appears in the result: a readiness probe is
    frequently public, and "is it up?" does not require any of that.
    """

    if database is None:
        return {
            "configured": False,
            "reachable": None,
            "server_version": None,
        }

    try:
        reachable = database.ping()
    except Exception:
        # A driver error here means "not reachable"; the detail belongs in the
        # server log, not in a probe response.
        return {
            "configured": True,
            "reachable": False,
            "server_version": None,
        }

    if not reachable:
        return {
            "configured": True,
            "reachable": False,
            "server_version": None,
        }

    try:
        server_version = database.server_version()
    except Exception:
        server_version = None

    return {
        "configured": True,
        "reachable": True,
        "server_version": server_version,
    }


__all__ = [
    "AQOS_HTTP_DEPENDENCIES_VERSION",
    "CONFIG_STATE_KEY",
    "DATABASE_STATE_KEY",
    "build_database",
    "describe_database_readiness",
    "get_api_config",
    "get_database",
    "get_optional_database",
    "get_session",
    "get_write_session",
]
