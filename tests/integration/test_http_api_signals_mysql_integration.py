"""
Read-only signal, prediction and model-promotion APIs against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from aqos.accounts.models import AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.http_api.pagination import MAX_PAGE_LIMIT
from aqos.signal_reasons.repositories import (
    SignalReasonRepository,
    reject_signal_with_reason,
)
from aqos.signal_reasons.taxonomy import SignalReasonCode
from aqos.signals.models import SignalAction, SignalSource, SignalStatus
from aqos.signals.repositories import TradingSignalRepository
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so the read-only signal APIs are "
            "NOT verified against MySQL by this run. Run them with:\n"
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
            "so the read-only signal APIs are NOT verified by this run. Start "
            "MySQL and run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "signal_reasons",
            "signal_events",
            "trading_signals",
            "trading_accounts",
            "user_profiles",
        ):
            session.execute(text(f"TRUNCATE TABLE {table}"))

        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def database_url() -> str:
    url = requires_mysql()
    requires_reachable_mysql(url)

    return url


@pytest.fixture
def signal_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def seeded(signal_database) -> dict:
    """One approved model signal, one rejected manual signal with a reason."""

    with signal_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="reader@example.com",
            display_name="Reader",
            created_at_utc=FIXED_NOW,
        ).user_id

        account_id = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper One",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            created_at_utc=FIXED_NOW,
        ).account_id

        signals = TradingSignalRepository(session)

        approved = signals.create_signal(
            user_id=user_id,
            account_id=account_id,
            symbol="XAUUSD",
            timeframe="H1",
            action=SignalAction.BUY,
            source=SignalSource.ML_MODEL,
            model_id="model_1",
            model_version="1.0",
            strategy_name="Breakout",
            confidence=0.8,
            generated_at_utc=FIXED_NOW,
        )
        signals.approve_signal(
            approved.signal_id,
            occurred_at_utc=FIXED_NOW + timedelta(minutes=1),
        )

        rejected = signals.create_signal(
            user_id=user_id,
            account_id=account_id,
            symbol="EURUSD",
            timeframe="M15",
            action=SignalAction.SELL,
            source=SignalSource.MANUAL,
            generated_at_utc=FIXED_NOW + timedelta(days=1),
        )
        reject_signal_with_reason(
            signals=signals,
            reasons=SignalReasonRepository(session),
            signal_id=rejected.signal_id,
            reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
            account_id=account_id,
        )

        return {
            "user_id": user_id,
            "account_id": account_id,
            "approved_signal_id": approved.signal_id,
            "rejected_signal_id": rejected.signal_id,
        }


@pytest.fixture
def client(signal_database, database_url: str) -> TestClient:
    app = create_aqos_api_app(
        ApiConfig(
            environment=ApiEnvironment.TEST,
            database_url=database_url,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    app.state.aqos_database.dispose()


def signals_url(**params) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items())

    return f"{API_V1_PREFIX}/signals" + (f"?{query}" if query else "")


class TestSignalList:
    def test_it_lists_seeded_signals(self, client, seeded) -> None:
        payload = client.get(signals_url()).json()

        assert payload["count"] == 2
        assert payload["limit"] == 50
        assert payload["offset"] == 0
        assert {item["symbol"] for item in payload["items"]} == {
            "XAUUSD",
            "EURUSD",
        }

    def test_the_total_is_not_invented(self, client, seeded) -> None:
        """No count was run, so none is reported."""

        assert client.get(signals_url()).json()["total"] is None

    def test_it_filters_by_status(self, client, seeded) -> None:
        payload = client.get(signals_url(status="approved")).json()

        assert payload["count"] == 1
        assert payload["items"][0]["status"] == "approved"

    def test_it_filters_by_source(self, client, seeded) -> None:
        payload = client.get(signals_url(source="manual")).json()

        assert payload["count"] == 1
        assert payload["items"][0]["source"] == "manual"

    def test_it_filters_by_action(self, client, seeded) -> None:
        payload = client.get(signals_url(action="sell")).json()

        assert payload["count"] == 1
        assert payload["items"][0]["action"] == "sell"

    def test_it_filters_by_symbol(self, client, seeded) -> None:
        payload = client.get(signals_url(symbol="XAUUSD")).json()

        assert payload["count"] == 1

    def test_it_filters_by_account(self, client, seeded) -> None:
        payload = client.get(
            signals_url(account_id=seeded["account_id"])
        ).json()

        assert payload["count"] == 2

    def test_an_unknown_account_yields_nothing(self, client, seeded) -> None:
        assert client.get(signals_url(account_id="account_missing")).json()[
            "count"
        ] == 0

    def test_it_filters_by_generated_window(self, client, seeded) -> None:
        early = client.get(
            signals_url(generated_to="2026-01-01T12:00:00")
        ).json()
        late = client.get(
            signals_url(generated_from="2026-01-01T12:00:00")
        ).json()

        assert early["count"] == 1
        assert early["items"][0]["symbol"] == "XAUUSD"
        assert late["count"] == 1
        assert late["items"][0]["symbol"] == "EURUSD"

    def test_a_reversed_window_is_refused(self, client, seeded) -> None:
        response = client.get(
            signals_url(
                generated_from="2026-02-01T00:00:00",
                generated_to="2026-01-01T00:00:00",
            )
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_pagination_windows_the_result(self, client, seeded) -> None:
        first = client.get(signals_url(limit=1, offset=0)).json()
        second = client.get(signals_url(limit=1, offset=1)).json()

        assert first["count"] == 1
        assert second["count"] == 1
        assert first["items"][0]["signal_id"] != second["items"][0]["signal_id"]

    def test_an_offset_past_the_end_is_empty_not_an_error(
        self,
        client,
        seeded,
    ) -> None:
        payload = client.get(signals_url(limit=10, offset=500)).json()

        assert payload["items"] == []
        assert payload["count"] == 0

    @pytest.mark.parametrize("limit", [0, -1])
    def test_an_invalid_limit_is_refused(self, client, seeded, limit) -> None:
        response = client.get(signals_url(limit=limit))

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_a_limit_above_the_cap_is_refused(self, client, seeded) -> None:
        response = client.get(signals_url(limit=MAX_PAGE_LIMIT + 1))

        assert response.status_code == 422

    def test_a_negative_offset_is_refused(self, client, seeded) -> None:
        assert client.get(signals_url(offset=-1)).status_code == 422

    @pytest.mark.parametrize(
        "field, value",
        [
            ("status", "almost_approved"),
            ("source", "telepathy"),
            ("action", "hodl"),
        ],
    )
    def test_an_unknown_enum_is_refused(
        self,
        client,
        seeded,
        field,
        value,
    ) -> None:
        """Silently ignoring it would look like a real empty result."""

        response = client.get(signals_url(**{field: value}))

        assert response.status_code == 422

        payload = response.json()

        assert payload["error"]["code"] == "validation_error"
        assert payload["error"]["details"]["field"] == field
        assert payload["error"]["details"]["allowed"]


class TestSignalDetail:
    def test_it_returns_the_signal(self, client, seeded) -> None:
        response = client.get(
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}"
        )

        assert response.status_code == 200

        payload = response.json()

        assert payload["signal_id"] == seeded["approved_signal_id"]
        assert payload["model_id"] == "model_1"
        assert payload["model_version"] == "1.0"
        assert payload["strategy_name"] == "Breakout"
        assert payload["status"] == "approved"

    def test_an_unknown_signal_is_a_standard_not_found(
        self,
        client,
        seeded,
    ) -> None:
        response = client.get(f"{API_V1_PREFIX}/signals/signal_missing")

        assert response.status_code == 404

        payload = response.json()

        assert payload["error"]["code"] == "not_found"
        assert payload["error"]["details"]["signal_id"] == "signal_missing"
        assert payload["error"]["request_id"]

    def test_no_orm_internals_are_exposed(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}"
        ).json()

        assert "metadata" not in payload
        assert "_sa_instance_state" not in payload


class TestSignalEvents:
    def test_it_returns_the_audit_trail(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}/events"
        ).json()

        assert payload["count"] == 2
        assert [item["to_status"] for item in payload["items"]] == [
            "generated",
            "approved",
        ]
        assert payload["items"][0]["from_status"] is None
        assert payload["items"][1]["from_status"] == "generated"

    def test_events_for_an_unknown_signal_are_not_found(
        self,
        client,
        seeded,
    ) -> None:
        """A missing signal is a 404, not an empty list that implies it exists."""

        response = client.get(
            f"{API_V1_PREFIX}/signals/signal_missing/events"
        )

        assert response.status_code == 404


class TestSignalReasons:
    def test_it_returns_structured_reasons(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/signals/{seeded['rejected_signal_id']}/reasons"
        ).json()

        assert payload["count"] == 1

        reason = payload["items"][0]

        assert reason["reason_code"] == "spread_too_high"
        assert reason["reason_category"] == "market_condition"
        assert reason["severity"] == "warning"
        assert reason["signal_status"] == "rejected"

    def test_a_signal_without_reasons_returns_an_empty_list(
        self,
        client,
        seeded,
    ) -> None:
        """The signal exists and simply has no reasons; that is not a 404."""

        payload = client.get(
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}/reasons"
        ).json()

        assert payload["count"] == 0
        assert payload["items"] == []

    def test_reasons_for_an_unknown_signal_are_not_found(
        self,
        client,
        seeded,
    ) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/signals/signal_missing/reasons"
        ).status_code == 404


class TestReadOnlyBehaviour:
    def test_a_read_request_writes_nothing(
        self,
        client,
        signal_database,
        seeded,
    ) -> None:
        """
        A GET must never become a write.

        The read dependency does not commit, so nothing a handler touched can
        survive the request.
        """

        def row_counts() -> dict[str, int]:
            with signal_database.read_session() as session:
                return {
                    table: session.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar_one()
                    for table in (
                        "trading_signals",
                        "signal_events",
                        "signal_reasons",
                    )
                }

        before = row_counts()

        for path in (
            f"{API_V1_PREFIX}/signals",
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}",
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}/events",
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}/reasons",
        ):
            assert client.get(path).status_code == 200

        # Nothing moved: in particular, reading a signal must not append a
        # lifecycle event, which is exactly what a stray commit would do.
        assert row_counts() == before

    def test_every_response_is_strict_json(self, client, seeded) -> None:
        for path in (
            f"{API_V1_PREFIX}/signals",
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}",
            f"{API_V1_PREFIX}/signals/{seeded['approved_signal_id']}/events",
            f"{API_V1_PREFIX}/signals/{seeded['rejected_signal_id']}/reasons",
            f"{API_V1_PREFIX}/signals/signal_missing",
        ):
            body = client.get(path).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)

    def test_no_response_leaks_the_connection_string(
        self,
        client,
        seeded,
        database_url,
    ) -> None:
        for path in (
            f"{API_V1_PREFIX}/signals",
            f"{API_V1_PREFIX}/signals/signal_missing",
        ):
            body = client.get(path).text

            assert database_url not in body
            assert "aqos_pw" not in body
            assert "Traceback" not in body


class TestRegistryEndpointsWithoutConfiguration:
    """An unconfigured registry is unavailable, never an empty result."""

    def test_predictions_report_unavailable(self, client, seeded) -> None:
        response = client.get(f"{API_V1_PREFIX}/predictions")

        assert response.status_code == 503

        payload = response.json()

        assert payload["error"]["code"] == "not_ready"
        assert payload["error"]["details"]["configured"] is False

    def test_promotions_report_unavailable(self, client, seeded) -> None:
        response = client.get(f"{API_V1_PREFIX}/models/promotions")

        assert response.status_code == 503
        assert response.json()["error"]["code"] == "not_ready"

    def test_promotion_status_reports_unavailable(
        self,
        client,
        seeded,
    ) -> None:
        """
        Never "not promoted" just because the registry is missing.

        Answering not_promoted here would be a guess dressed as a fact.
        """

        response = client.get(
            f"{API_V1_PREFIX}/models/model_1/promotion-status"
        )

        assert response.status_code == 503
        assert "not_promoted" not in response.text
