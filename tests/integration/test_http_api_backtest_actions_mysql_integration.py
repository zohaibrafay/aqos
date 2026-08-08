"""
Backtest execution endpoint against real MySQL and real CSV datasets.

MySQL holds the users and sessions that authenticate the request; the run
itself reads a real CSV and writes real artifacts, so "the trades endpoint
returns trades" means rows the simulator generated during the test.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.types import database_utc_now
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.users.models import UserStatus
from aqos.users.repositories import (
    UserCredentialRepository,
    UserProfileRepository,
    UserSessionRepository,
)


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
PASSWORD = "Correct-Horse-Battery-9"

DATASET = "xauusd_h1"
SECRET_FILE_CONTENT = "this file is outside the dataset directory"

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so backtest execution is NOT "
            "verified against MySQL by this run. Run it with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def requires_reachable_mysql(url: str) -> None:
    database = AqosDatabase(config=parse_database_url(url))

    try:
        reachable = database.ping()
    except Exception:
        reachable = False
    finally:
        database.dispose()

    if not reachable:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is set but the MySQL server is not reachable, "
            "so backtest execution is NOT verified by this run. Start MySQL "
            "and run it with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in ("user_sessions", "user_credentials", "user_profiles"):
            session.execute(text(f"TRUNCATE TABLE {table}"))

        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def database_url() -> str:
    url = requires_mysql()
    requires_reachable_mysql(url)

    return url


@pytest.fixture
def backtest_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


def write_dataset(directory: Path, name: str, rows: int = 40) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    lines = ["timestamp,open,high,low,close,volume,signal"]
    price = 100.0

    for index in range(rows):
        price += 1.0 if index % 3 else -0.5
        signal = "buy" if index == 2 else ("close" if index == 12 else "hold")
        day = f"2026-01-{index + 1:02d}"
        lines.append(
            f"{day}T00:00:00,{price},{price + 1},{price - 1},{price},100,{signal}"
        )

    (directory / f"{name}.csv").write_text("\n".join(lines), encoding="utf-8")


@pytest.fixture
def workspace(tmp_path) -> dict:
    """Configured dataset and output directories, plus a file outside both."""

    datasets = tmp_path / "datasets"
    write_dataset(datasets, DATASET)

    secret = tmp_path / "secret.csv"
    secret.write_text(SECRET_FILE_CONTENT, encoding="utf-8")

    return {
        "datasets": datasets,
        "output": tmp_path / "out",
        "registry": tmp_path / "registry.json",
        "secret": secret,
    }


def build_app(database_url: str, workspace: dict, **overrides):
    payload = {
        "environment": ApiEnvironment.TEST,
        "database_url": database_url,
        "backtest_dataset_dir": str(workspace["datasets"]),
        "backtest_output_dir": str(workspace["output"]),
        "backtest_registry_path": str(workspace["registry"]),
    }
    payload.update(overrides)

    return create_aqos_api_app(ApiConfig(**payload))


@pytest.fixture
def client(backtest_database, workspace, database_url: str) -> TestClient:
    app = build_app(database_url, workspace)

    with TestClient(app) as test_client:
        yield test_client

    app.state.aqos_database.dispose()


def create_user(database: AqosDatabase, email: str) -> dict:
    with database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email=email,
            display_name=email,
            created_at_utc=FIXED_NOW,
        ).user_id

        UserCredentialRepository(session).set_password(
            user_id=user_id,
            password=PASSWORD,
        )

    return {"user_id": user_id, "email": email}


@pytest.fixture
def alice(backtest_database) -> dict:
    return create_user(backtest_database, "alice@example.com")


@pytest.fixture
def bob(backtest_database) -> dict:
    return create_user(backtest_database, "bob@example.com")


def login(client: TestClient, email: str) -> str:
    response = client.post(
        f"{API_V1_PREFIX}/auth/login",
        json={"email": email, "password": PASSWORD},
    )

    assert response.status_code == 201, response.text

    return response.json()["token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def backtests_url(suffix: str = "") -> str:
    base = f"{API_V1_PREFIX}/backtests"

    return f"{base}/{suffix}" if suffix else base


def run_body(**overrides) -> dict:
    payload = {
        "strategy_name": "csv_signal_strategy",
        "dataset": DATASET,
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }
    payload.update(overrides)

    return payload


def run_backtest(client: TestClient, token: str, **overrides) -> dict:
    response = client.post(
        backtests_url(),
        json=run_body(**overrides),
        headers=auth_header(token),
    )

    assert response.status_code == 201, response.text

    return response.json()["backtest"]


class TestRouteRegistration:
    def test_the_run_endpoint_exists(self, client, alice) -> None:
        token = login(client, alice["email"])
        response = client.post(
            backtests_url(),
            json=run_body(),
            headers=auth_header(token),
        )

        assert response.status_code not in (404, 405)

    def test_the_collection_reads_once_a_run_exists(self, client, alice) -> None:
        """
        Before any run the registry file does not exist yet.

        Sprint 056 reports that as unavailable rather than as an empty list,
        and running a backtest is what creates it — so both facts are asserted
        here rather than only the convenient one.
        """

        token = login(client, alice["email"])

        assert client.get(
            backtests_url(),
            headers=auth_header(token),
        ).status_code == 503

        run_backtest(client, token)

        assert client.get(
            backtests_url(),
            headers=auth_header(token),
        ).status_code == 200


class TestAuthenticationIsRequired:
    def test_no_token_is_refused(self, client) -> None:
        assert client.post(backtests_url(), json=run_body()).status_code == 401

    def test_an_invalid_token_is_refused(self, client) -> None:
        assert client.post(
            backtests_url(),
            json=run_body(),
            headers=auth_header("not-a-real-token"),
        ).status_code == 401

    def test_a_revoked_token_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])

        client.post(f"{API_V1_PREFIX}/auth/logout", headers=auth_header(token))

        assert client.post(
            backtests_url(),
            json=run_body(),
            headers=auth_header(token),
        ).status_code == 401

    def test_an_expired_token_is_refused(
        self,
        client,
        backtest_database,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        with backtest_database.session() as session:
            record = UserSessionRepository(session).find_by_token(token)
            record.expires_at_utc = database_utc_now() - timedelta(minutes=1)

        assert client.post(
            backtests_url(),
            json=run_body(),
            headers=auth_header(token),
        ).status_code == 401

    @pytest.mark.parametrize(
        "status",
        [UserStatus.SUSPENDED, UserStatus.DISABLED],
    )
    def test_an_inactive_user_cannot_run(
        self,
        client,
        backtest_database,
        workspace,
        alice,
        status: UserStatus,
    ) -> None:
        token = login(client, alice["email"])

        with backtest_database.session() as session:
            UserProfileRepository(session).set_status(
                user_id=alice["user_id"],
                status=status,
            )

        response = client.post(
            backtests_url(),
            json=run_body(),
            headers=auth_header(token),
        )

        assert response.status_code == 403
        assert not workspace["registry"].exists()


class TestRunning:
    def test_a_valid_run_completes(self, client, alice) -> None:
        backtest = run_backtest(client, login(client, alice["email"]))

        assert backtest["status"] == "completed"
        assert backtest["strategy_name"] == "csv_signal_strategy"
        assert backtest["symbol"] == "XAUUSD"
        assert backtest["failure_reason"] is None
        assert backtest["completed_at_utc"]

    def test_the_run_belongs_to_the_caller(self, client, alice) -> None:
        backtest = run_backtest(client, login(client, alice["email"]))

        assert backtest["user_id"] == alice["user_id"]

    def test_the_metrics_are_measured(self, client, alice) -> None:
        """One buy and one close in the dataset, so exactly one trade."""

        backtest = run_backtest(client, login(client, alice["email"]))

        assert backtest["metrics"]["total_trades"] == 1

    def test_the_status_is_never_a_pretend_queue(self, client, alice) -> None:
        """
        The run happens inside the request.

        Reporting ``queued`` or ``running`` would describe machinery that does
        not exist.
        """

        backtest = run_backtest(client, login(client, alice["email"]))

        assert backtest["status"] in ("completed", "failed")

    def test_a_null_profit_factor_says_which_null_it_is(
        self,
        client,
        alice,
    ) -> None:
        """
        Infinite and unavailable both serialize as null.

        The dataset wins every trade, so the profit factor is infinite — a real
        result. The registry keeps only numeric metrics, so the key drops out
        of ``metrics`` entirely rather than appearing as null, which makes the
        state field the only thing carrying the answer. Without it a client
        could not tell "won every trade" from "nothing to divide", and must
        never read either as zero.
        """

        backtest = run_backtest(client, login(client, alice["email"]))

        assert backtest["metrics"].get("profit_factor") is None
        assert backtest["metrics"].get("profit_factor") != 0
        assert backtest["profit_factor_state"] == "infinite_no_losses"

    def test_an_unknown_strategy_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])

        response = client.post(
            backtests_url(),
            json=run_body(strategy_name="my_own_strategy"),
            headers=auth_header(token),
        )

        assert response.status_code == 422

    @pytest.mark.parametrize(
        "dataset",
        ["../secret", "/etc/passwd", "nope", "xauusd_h1.csv"],
    )
    def test_an_unsafe_or_unknown_dataset_is_refused(
        self,
        client,
        alice,
        dataset: str,
    ) -> None:
        """
        A dataset is a name, so a path cannot be one.

        The file outside the configured directory is real, which is what makes
        this a test rather than a formality.
        """

        token = login(client, alice["email"])

        response = client.post(
            backtests_url(),
            json=run_body(dataset=dataset),
            headers=auth_header(token),
        )

        assert response.status_code == 422
        assert SECRET_FILE_CONTENT not in response.text

    def test_the_refusal_names_the_available_datasets(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        details = client.post(
            backtests_url(),
            json=run_body(dataset="nope"),
            headers=auth_header(token),
        ).json()["error"]["details"]

        assert details["available_datasets"] == [DATASET]

    def test_a_backwards_period_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])

        response = client.post(
            backtests_url(),
            json=run_body(
                period_start="2026-06-01T00:00:00",
                period_end="2026-01-01T00:00:00",
            ),
            headers=auth_header(token),
        )

        assert response.status_code == 422

    def test_an_unbounded_period_is_refused(self, client, alice) -> None:
        token = login(client, alice["email"])

        response = client.post(
            backtests_url(),
            json=run_body(
                period_start="1800-01-01T00:00:00",
                period_end="2026-01-01T00:00:00",
            ),
            headers=auth_header(token),
        )

        assert response.status_code == 422

    def test_an_unconfigured_deployment_reports_not_ready(
        self,
        backtest_database,
        workspace,
        database_url,
        alice,
    ) -> None:
        """Unconfigured is unavailable, never a run against a default directory."""

        app = build_app(
            database_url,
            workspace,
            backtest_dataset_dir=None,
            backtest_output_dir=None,
        )

        with TestClient(app) as client:
            token = login(client, alice["email"])
            response = client.post(
                backtests_url(),
                json=run_body(),
                headers=auth_header(token),
            )

            assert response.status_code == 503
            assert response.json()["error"]["code"] == "not_ready"
            assert response.json()["error"]["details"]["has_datasets"] is False

        app.state.aqos_database.dispose()


class TestGeneratedRunIsReadable:
    def test_the_run_appears_in_the_list(self, client, alice) -> None:
        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        payload = client.get(backtests_url(), headers=auth_header(token)).json()

        assert payload["total"] == 1
        assert payload["items"][0]["backtest_id"] == backtest["backtest_id"]

    def test_the_detail_endpoint_serves_it(self, client, alice) -> None:
        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        response = client.get(
            backtests_url(backtest["backtest_id"]),
            headers=auth_header(token),
        )

        assert response.status_code == 200
        assert response.json()["strategy_name"] == "csv_signal_strategy"

    def test_the_trades_are_real(self, client, alice) -> None:
        """
        Rows the simulator generated, not a placeholder.

        The dataset produces exactly one round trip, so one trade is the
        measured answer rather than a coincidence.
        """

        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        payload = client.get(
            backtests_url(f"{backtest['backtest_id']}/trades"),
            headers=auth_header(token),
        ).json()

        assert payload["total"] == 1
        assert payload["items"][0]

    def test_the_orders_are_real(self, client, alice) -> None:
        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        payload = client.get(
            backtests_url(f"{backtest['backtest_id']}/orders"),
            headers=auth_header(token),
        ).json()

        assert payload["total"] >= 1

    def test_the_equity_curve_is_real(self, client, alice) -> None:
        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        payload = client.get(
            backtests_url(f"{backtest['backtest_id']}/equity"),
            headers=auth_header(token),
        ).json()

        assert payload["total"] > 1

    def test_a_missing_artifact_reports_not_ready(
        self,
        client,
        workspace,
        alice,
    ) -> None:
        """
        A registered run whose report is gone is unavailable, not empty.

        An empty list would claim the run produced nothing, which is a
        different fact entirely.
        """

        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        for report in workspace["output"].rglob("*.json"):
            report.unlink()

        response = client.get(
            backtests_url(f"{backtest['backtest_id']}/trades"),
            headers=auth_header(token),
        )

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_ready"

    def test_a_configured_empty_registry_is_still_empty(
        self,
        client,
        workspace,
        alice,
    ) -> None:
        token = login(client, alice["email"])

        workspace["registry"].write_text(
            json.dumps({"registry_version": "1.0", "results": []}),
            encoding="utf-8",
        )

        payload = client.get(backtests_url(), headers=auth_header(token)).json()

        assert payload["total"] == 0
        assert payload["items"] == []


class TestOwnership:
    def test_another_users_run_is_not_listed(self, client, alice, bob) -> None:
        alice_token = login(client, alice["email"])
        run_backtest(client, alice_token)

        bob_token = login(client, bob["email"])
        payload = client.get(
            backtests_url(),
            headers=auth_header(bob_token),
        ).json()

        assert payload["total"] == 0

    def test_another_users_run_is_not_readable(self, client, alice, bob) -> None:
        alice_token = login(client, alice["email"])
        backtest = run_backtest(client, alice_token)

        bob_token = login(client, bob["email"])

        for suffix in ("", "/trades", "/orders", "/equity"):
            assert client.get(
                backtests_url(f"{backtest['backtest_id']}{suffix}"),
                headers=auth_header(bob_token),
            ).status_code == 404, suffix

    def test_the_refusal_matches_a_missing_run(self, client, alice, bob) -> None:
        alice_token = login(client, alice["email"])
        backtest = run_backtest(client, alice_token)

        bob_token = login(client, bob["email"])

        foreign = client.get(
            backtests_url(backtest["backtest_id"]),
            headers=auth_header(bob_token),
        )
        missing = client.get(
            backtests_url("backtest_nope"),
            headers=auth_header(bob_token),
        )

        assert foreign.status_code == missing.status_code == 404
        assert foreign.json()["error"]["message"] == (
            missing.json()["error"]["message"]
        )

    def test_each_user_sees_only_their_own(self, client, alice, bob) -> None:
        alice_token = login(client, alice["email"])
        bob_token = login(client, bob["email"])

        run_backtest(client, alice_token, symbol="XAUUSD")
        run_backtest(client, bob_token, symbol="XAUUSD")

        for token, user in ((alice_token, alice), (bob_token, bob)):
            payload = client.get(
                backtests_url(),
                headers=auth_header(token),
            ).json()

            assert payload["total"] == 1


class TestModelTraceability:
    def test_a_named_model_is_recorded(self, client, alice) -> None:
        backtest = run_backtest(
            client,
            login(client, alice["email"]),
            model_id="model_1",
            model_version="1.0",
        )

        assert backtest["model_identity"]["model_id"] == "model_1"
        assert backtest["model_identity"]["model_version"] == "1.0"

    def test_the_attribution_is_marked_as_claimed(self, client, alice) -> None:
        """
        A request said so; the promotion registry did not.

        Without this a reader could mistake a backtest for evidence that a
        model is fit for production.
        """

        backtest = run_backtest(
            client,
            login(client, alice["email"]),
            model_id="model_1",
        )

        assert backtest["model_identity"]["claimed_by"] == "backtest_request"

    def test_a_request_cannot_claim_promotion(self, client, alice) -> None:
        backtest = run_backtest(
            client,
            login(client, alice["email"]),
            model_id="model_1",
        )
        identity = backtest["model_identity"]

        assert "promotion_state" not in identity
        assert "is_promoted" not in identity
        assert identity.get("approved") is None

    def test_no_model_means_an_empty_identity(self, client, alice) -> None:
        """Unknown stays empty rather than collapsing into a claim."""

        backtest = run_backtest(client, login(client, alice["email"]))

        assert backtest["model_identity"] == {}

    def test_promotion_is_not_asserted_anywhere_in_the_body(
        self,
        client,
        alice,
    ) -> None:
        token = login(client, alice["email"])
        body = client.post(
            backtests_url(),
            json=run_body(model_id="model_1"),
            headers=auth_header(token),
        ).text

        assert "promoted" not in body


class TestResponseSafety:
    def test_no_filesystem_path_is_returned(
        self,
        client,
        workspace,
        alice,
    ) -> None:
        """
        Not the dataset, not the output, not the registry.

        Every one of them would tell a caller where this process can read and
        write.
        """

        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        bodies = [
            client.post(
                backtests_url(),
                json=run_body(),
                headers=auth_header(token),
            ).text,
            client.get(backtests_url(), headers=auth_header(token)).text,
            client.get(
                backtests_url(backtest["backtest_id"]),
                headers=auth_header(token),
            ).text,
            client.get(
                backtests_url(f"{backtest['backtest_id']}/trades"),
                headers=auth_header(token),
            ).text,
        ]

        for body in bodies:
            for path in (
                str(workspace["datasets"]),
                str(workspace["output"]),
                str(workspace["registry"]),
                workspace["datasets"].as_posix(),
                workspace["output"].as_posix(),
            ):
                assert path not in body

            assert "report_path" not in body
            assert ".csv" not in body

    def test_every_response_is_strict_json(self, client, alice) -> None:
        token = login(client, alice["email"])
        backtest = run_backtest(client, token)

        for url in (
            backtests_url(),
            backtests_url(backtest["backtest_id"]),
            backtests_url(f"{backtest['backtest_id']}/trades"),
            backtests_url(f"{backtest['backtest_id']}/equity"),
        ):
            body = client.get(url, headers=auth_header(token)).text

            for fragment in ("Infinity", "-Infinity", "NaN"):
                assert fragment not in body

            json.loads(body)

    def test_a_failed_run_is_strict_json_too(self, client, alice) -> None:
        token = login(client, alice["email"])

        response = client.post(
            backtests_url(),
            json=run_body(period_start="2020-01-01T00:00:00", period_end="2020-02-01T00:00:00"),
            headers=auth_header(token),
        )

        for fragment in ("Infinity", "-Infinity", "NaN"):
            assert fragment not in response.text

        json.loads(response.text)

    def test_errors_leak_nothing(self, client, workspace, alice) -> None:
        token = login(client, alice["email"])

        bodies = [
            client.post(backtests_url(), json=run_body()).text,
            client.post(
                backtests_url(),
                json=run_body(),
                headers=auth_header("bogus"),
            ).text,
            client.post(
                backtests_url(),
                json=run_body(dataset="../secret"),
                headers=auth_header(token),
            ).text,
            client.post(
                backtests_url(),
                json=run_body(strategy_name="os.system"),
                headers=auth_header(token),
            ).text,
        ]

        for body in bodies:
            for fragment in (
                PASSWORD,
                "Traceback",
                "SELECT ",
                "pymysql",
                "sqlalchemy",
                "password_hash",
                "token_hash",
                "pbkdf2",
                "BacktestCommandError",
                "BacktestDatasetError",
                "FileNotFoundError",
                str(workspace["datasets"]),
                token,
            ):
                assert fragment not in body
