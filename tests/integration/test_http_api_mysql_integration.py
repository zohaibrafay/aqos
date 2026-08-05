"""
FastAPI readiness against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.http_api.dependencies import get_session, get_write_session
from aqos.http_api.middleware import REQUEST_ID_HEADER


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so API database readiness is NOT "
            "verified against MySQL by this run. Run it with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


@pytest.fixture
def database_url() -> str:
    return requires_mysql()


@pytest.fixture
def client(database_url: str) -> TestClient:
    app = create_aqos_api_app(
        ApiConfig(
            environment=ApiEnvironment.TEST,
            database_url=database_url,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    app.state.aqos_database.dispose()


class TestReadinessAgainstMysql:
    def test_ready_reports_healthy_with_a_reachable_database(
        self,
        client,
    ) -> None:
        response = client.get("/health/ready")

        assert response.status_code == 200

        payload = response.json()
        database = payload["checks"]["database"]

        assert payload["ready"] is True
        assert payload["status"] == "ok"
        assert database["configured"] is True
        assert database["reachable"] is True
        assert database["server_version"]

    def test_live_stays_ok_and_does_no_database_work(self, client) -> None:
        response = client.get("/health/live")

        assert response.status_code == 200
        assert "checks" not in response.json()

    def test_readiness_leaks_no_credentials(self, client, database_url) -> None:
        """A probe is frequently public and needs none of the connection detail."""

        body = client.get("/health/ready").text

        assert database_url not in body

        for fragment in ("aqos_pw", "password", "@127.0.0.1", "@localhost"):
            assert fragment not in body

    def test_system_info_masks_the_configured_url(self, client) -> None:
        payload = client.get(f"{API_V1_PREFIX}/system/info").json()

        assert payload["api"]["has_database"] is True
        assert payload["api"]["database_url"] == "mysql+pymysql://***"

    def test_a_pointed_at_dead_port_reports_not_ready(self) -> None:
        """A configured but unreachable database is running yet useless."""

        app = create_aqos_api_app(
            ApiConfig(
                environment=ApiEnvironment.TEST,
                database_url="mysql+pymysql://u:p@127.0.0.1:1/none",
            )
        )
        response = TestClient(app).get("/health/ready")

        assert response.status_code == 503
        assert response.json()["ready"] is False

        app.state.aqos_database.dispose()

    def test_every_response_is_strict_json(self, client) -> None:
        for path in (
            "/health/live",
            "/health/ready",
            f"{API_V1_PREFIX}/system/info",
        ):
            body = client.get(path).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)

    def test_every_response_carries_a_request_id(self, client) -> None:
        for path in ("/health/live", "/health/ready"):
            assert client.get(path).headers[REQUEST_ID_HEADER]


class TestSessionDependency:
    def test_a_read_session_reaches_mysql(self, client) -> None:
        request = _FakeRequest(client.app)
        generator = get_session(request)
        session = next(generator)

        try:
            assert session.execute(text("SELECT 1")).scalar_one() == 1
        finally:
            generator.close()

    def test_a_read_session_does_not_commit(self, client) -> None:
        """
        A GET must never become a write by accident.

        The row written inside the read session is rolled back when the session
        closes, so nothing survives.
        """

        request = _FakeRequest(client.app)

        with client.app.state.aqos_database.session() as setup:
            setup.execute(text("DROP TABLE IF EXISTS aqos_api_session_probe"))
            setup.execute(
                text(
                    "CREATE TABLE aqos_api_session_probe ("
                    "probe_id VARCHAR(32) NOT NULL, PRIMARY KEY (probe_id)"
                    ") ENGINE=InnoDB"
                )
            )

        generator = get_session(request)
        session = next(generator)
        session.execute(
            text("INSERT INTO aqos_api_session_probe (probe_id) VALUES ('a')")
        )
        generator.close()

        with client.app.state.aqos_database.read_session() as check:
            remaining = check.execute(
                text("SELECT COUNT(*) FROM aqos_api_session_probe")
            ).scalar_one()

        with client.app.state.aqos_database.session() as cleanup:
            cleanup.execute(text("DROP TABLE IF EXISTS aqos_api_session_probe"))

        assert remaining == 0

    def test_a_write_session_commits_on_success(self, client) -> None:
        request = _FakeRequest(client.app)

        with client.app.state.aqos_database.session() as setup:
            setup.execute(text("DROP TABLE IF EXISTS aqos_api_session_probe"))
            setup.execute(
                text(
                    "CREATE TABLE aqos_api_session_probe ("
                    "probe_id VARCHAR(32) NOT NULL, PRIMARY KEY (probe_id)"
                    ") ENGINE=InnoDB"
                )
            )

        generator = get_write_session(request)
        session = next(generator)
        session.execute(
            text("INSERT INTO aqos_api_session_probe (probe_id) VALUES ('a')")
        )
        # Exhausting the generator runs the commit.
        next(generator, None)

        with client.app.state.aqos_database.read_session() as check:
            remaining = check.execute(
                text("SELECT COUNT(*) FROM aqos_api_session_probe")
            ).scalar_one()

        with client.app.state.aqos_database.session() as cleanup:
            cleanup.execute(text("DROP TABLE IF EXISTS aqos_api_session_probe"))

        assert remaining == 1

    def test_a_write_session_rolls_back_on_failure(self, client) -> None:
        request = _FakeRequest(client.app)

        with client.app.state.aqos_database.session() as setup:
            setup.execute(text("DROP TABLE IF EXISTS aqos_api_session_probe"))
            setup.execute(
                text(
                    "CREATE TABLE aqos_api_session_probe ("
                    "probe_id VARCHAR(32) NOT NULL, PRIMARY KEY (probe_id)"
                    ") ENGINE=InnoDB"
                )
            )

        generator = get_write_session(request)
        session = next(generator)
        session.execute(
            text("INSERT INTO aqos_api_session_probe (probe_id) VALUES ('a')")
        )

        with pytest.raises(RuntimeError):
            generator.throw(RuntimeError("handler failed"))

        with client.app.state.aqos_database.read_session() as check:
            remaining = check.execute(
                text("SELECT COUNT(*) FROM aqos_api_session_probe")
            ).scalar_one()

        with client.app.state.aqos_database.session() as cleanup:
            cleanup.execute(text("DROP TABLE IF EXISTS aqos_api_session_probe"))

        assert remaining == 0

    def test_each_request_gets_its_own_session(self, client) -> None:
        """No global session reuse: one request must not see another's work."""

        request = _FakeRequest(client.app)

        first_generator = get_session(request)
        second_generator = get_session(request)

        first = next(first_generator)
        second = next(second_generator)

        try:
            assert first is not second
        finally:
            first_generator.close()
            second_generator.close()


class _FakeRequest:
    """The minimum a dependency needs: an app carrying the database handle."""

    def __init__(self, app) -> None:
        self.app = app
