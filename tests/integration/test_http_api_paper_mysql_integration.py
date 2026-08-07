"""
Read-only paper trading APIs against real MySQL 8.

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
from aqos.execution_policy.modes import ExecutionMode
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.http_api.pagination import MAX_PAGE_LIMIT
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderType,
)
from aqos.paper_trading.execution_service import PaperExecutionService
from aqos.paper_trading.session_service import PaperSessionService
from aqos.paper_trading.sessions import PaperSessionType
from aqos.paper_trading.simulator import PaperMarketBar
from aqos.trading_settings.models import SymbolPreferenceKind
from aqos.trading_settings.repositories import (
    SymbolPreferenceRepository,
    TradingSettingsRepository,
)
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
STARTING_BALANCE = 10_000.0

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so the read-only paper APIs are "
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
            "so the read-only paper APIs are NOT verified by this run. Start "
            "MySQL and run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "paper_execution_decisions",
            "paper_account_snapshots",
            "paper_trades",
            "paper_fills",
            "paper_positions",
            "paper_orders",
            "paper_sessions",
            "trading_accounts",
            "symbol_preferences",
            "trading_settings",
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
def paper_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


def build_bar(minutes: int = 0, symbol: str = "XAUUSD", price: float = 100.0):
    return PaperMarketBar(
        symbol=symbol,
        timestamp_utc=FIXED_NOW + timedelta(minutes=minutes),
        open=price,
        high=price + 5,
        low=price - 5,
        close=price,
        volume=1_000.0,
    )


@pytest.fixture
def seeded(paper_database) -> dict:
    """
    One running session with a real winning trade and one refused attempt,
    plus a second session on the same account for isolation checks.
    """

    with paper_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="paper-api@example.com",
            display_name="Paper Reader",
            created_at_utc=FIXED_NOW,
        ).user_id

        TradingSettingsRepository(session).create_for_user(
            user_id=user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
            created_at_utc=FIXED_NOW,
        )

        SymbolPreferenceRepository(session).add_symbol(
            user_id=user_id,
            symbol="GBPUSD",
            kind=SymbolPreferenceKind.BLOCKED,
        )

        account_id = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper API",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=STARTING_BALANCE,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
            created_at_utc=FIXED_NOW,
        ).account_id

    with paper_database.session() as session:
        account = TradingAccountRepository(session).require(account_id)
        service = PaperSessionService(session)

        primary = service.start_session(
            account=account,
            session_name="Forward test one",
            session_type=PaperSessionType.MODEL_FORWARD_TEST,
            model_id="model_1",
            model_version="1.0",
            symbol="XAUUSD",
            timeframe="H1",
            started_at_utc=FIXED_NOW,
        ).session_id

        other = service.start_session(
            account=account,
            session_name="Strategy run",
            session_type=PaperSessionType.STRATEGY_FORWARD_TEST,
            strategy_name="Breakout",
            started_at_utc=FIXED_NOW + timedelta(days=1),
        ).session_id

    with paper_database.session() as session:
        account = TradingAccountRepository(session).require(account_id)
        execution = PaperExecutionService(session, session_id=primary)

        execution.execute(
            request=PaperExecutionRequest(
                user_id=user_id,
                account_id=account_id,
                symbol="XAUUSD",
                action=PaperAction.BUY,
                quantity=1.0,
                order_type=PaperOrderType.MARKET,
                submitted_at_utc=FIXED_NOW,
            ),
            account=account,
            bar=build_bar(),
        ).raise_if_rejected()

        execution.close_all_positions(
            account,
            build_bar(minutes=60, price=110.0),
        )

        # A refused attempt, so the decisions endpoint has a rejection to show.
        execution.execute(
            request=PaperExecutionRequest(
                user_id=user_id,
                account_id=account_id,
                symbol="GBPUSD",
                action=PaperAction.BUY,
                quantity=1.0,
                order_type=PaperOrderType.MARKET,
                submitted_at_utc=FIXED_NOW + timedelta(minutes=90),
            ),
            account=account,
            bar=build_bar(minutes=90, symbol="GBPUSD"),
        )

    return {
        "user_id": user_id,
        "account_id": account_id,
        "session_id": primary,
        "other_session_id": other,
    }


@pytest.fixture
def client(paper_database, database_url: str) -> TestClient:
    app = create_aqos_api_app(
        ApiConfig(
            environment=ApiEnvironment.TEST,
            database_url=database_url,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    app.state.aqos_database.dispose()


def sessions_url(**params) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items())

    return f"{API_V1_PREFIX}/paper/sessions" + (f"?{query}" if query else "")


class TestSessionList:
    def test_it_lists_sessions(self, client, seeded) -> None:
        payload = client.get(sessions_url()).json()

        assert payload["total"] == 2
        assert {item["session_name"] for item in payload["items"]} == {
            "Forward test one",
            "Strategy run",
        }

    def test_it_filters_by_session_type(self, client, seeded) -> None:
        payload = client.get(
            sessions_url(session_type="model_forward_test")
        ).json()

        assert payload["total"] == 1
        assert payload["items"][0]["session_type"] == "model_forward_test"

    def test_it_filters_by_status(self, client, seeded) -> None:
        assert client.get(sessions_url(status="running")).json()["total"] == 2
        assert client.get(sessions_url(status="completed")).json()["total"] == 0

    def test_it_filters_by_model_and_strategy(self, client, seeded) -> None:
        assert client.get(sessions_url(model_id="model_1")).json()["total"] == 1
        assert client.get(
            sessions_url(strategy_name="Breakout")
        ).json()["total"] == 1

    def test_it_filters_by_account_and_user(self, client, seeded) -> None:
        assert client.get(
            sessions_url(account_id=seeded["account_id"])
        ).json()["total"] == 2
        assert client.get(
            sessions_url(user_id="user_missing")
        ).json()["total"] == 0

    def test_it_filters_by_started_window(self, client, seeded) -> None:
        early = client.get(sessions_url(started_to="2026-01-01T12:00:00")).json()
        late = client.get(sessions_url(started_from="2026-01-01T12:00:00")).json()

        assert early["total"] == 1
        assert late["total"] == 1

    def test_a_reversed_window_is_refused(self, client, seeded) -> None:
        response = client.get(
            sessions_url(
                started_from="2026-02-01T00:00:00",
                started_to="2026-01-01T00:00:00",
            )
        )

        assert response.status_code == 422

    @pytest.mark.parametrize("limit", [0, -1, MAX_PAGE_LIMIT + 1])
    def test_an_invalid_limit_is_refused(self, client, seeded, limit) -> None:
        assert client.get(sessions_url(limit=limit)).status_code == 422

    @pytest.mark.parametrize(
        "field, value",
        [("session_type", "vibes_test"), ("status", "napping")],
    )
    def test_an_unknown_enum_is_refused(
        self,
        client,
        seeded,
        field,
        value,
    ) -> None:
        response = client.get(sessions_url(**{field: value}))

        assert response.status_code == 422
        assert response.json()["error"]["details"]["field"] == field


class TestSessionDetail:
    def test_it_returns_the_session(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}"
        ).json()

        assert payload["session_name"] == "Forward test one"
        assert payload["model_id"] == "model_1"
        assert payload["symbol"] == "XAUUSD"
        assert payload["initial_balance"] == pytest.approx(STARTING_BALANCE)
        assert payload["status"] == "running"

    def test_no_raw_metadata_or_orm_internals(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}"
        ).json()

        assert "metadata" not in payload
        assert "_sa_instance_state" not in payload

    def test_an_unknown_session_is_not_found(self, client, seeded) -> None:
        response = client.get(
            f"{API_V1_PREFIX}/paper/sessions/session_missing"
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"


class TestSessionResult:
    def test_it_measures_the_sessions_own_activity(
        self,
        client,
        seeded,
    ) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/result"
        ).json()

        assert payload["total_trades"] == 1
        assert payload["winning_trades"] == 1
        assert payload["win_rate"] == pytest.approx(1.0)
        assert payload["net_pnl"] == pytest.approx(10.0)
        assert payload["symbols_traded"] == ["XAUUSD"]
        assert payload["decisions_allowed"] == 1
        assert payload["decisions_rejected"] == 1

    def test_a_wins_only_result_is_json_safe(self, client, seeded) -> None:
        """
        Unbounded, not unmeasured.

        The number is null because infinity has no JSON form; the state is what
        keeps it distinguishable from a run that measured nothing.
        """

        response = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/result"
        )

        for token in ("Infinity", "-Infinity", "NaN"):
            assert token not in response.text

        payload = json.loads(response.text)

        assert payload["profit_factor"] is None
        assert payload["profit_factor_state"] == "infinite_no_losses"
        assert payload["has_infinite_profit_factor"] is True

    def test_a_session_with_no_activity_reports_unknowns(
        self,
        client,
        seeded,
    ) -> None:
        """Nothing traded means unknown ratios, never zeros."""

        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['other_session_id']}"
            "/result"
        ).json()

        assert payload["total_trades"] == 0
        assert payload["has_trades"] is False
        assert payload["win_rate"] is None
        assert payload["net_pnl"] is None
        assert payload["profit_factor"] is None
        assert payload["profit_factor_state"] == "unavailable"
        assert payload["max_drawdown"] is None
        assert payload["ending_balance"] is None
        assert payload["rejection_rate"] is None

    def test_top_rejection_reasons_are_reported(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/result"
        ).json()

        assert payload["top_rejection_reasons"] == [
            {"reason_code": "symbol_blocked", "total": 1}
        ]

    def test_a_result_for_an_unknown_session_is_not_found(
        self,
        client,
        seeded,
    ) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/paper/sessions/session_missing/result"
        ).status_code == 404


class TestSessionRecords:
    def test_orders_are_listed(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/orders"
        ).json()

        assert payload["session_id"] == seeded["session_id"]
        # Entry plus the broker-generated exit. The refused GBPUSD attempt
        # produced no order row: an invalid symbol is one of the rejections
        # Sprint 049 refuses to write to paper_orders.
        assert payload["total"] == 2

    def test_an_unpersistable_rejection_leaves_no_order_row(
        self,
        client,
        seeded,
    ) -> None:
        """
        The refusal is still auditable, just not as an order.

        An invalid symbol is one of the rejections Sprint 049 refuses to write
        to ``paper_orders``; the decision record carries the reason instead, so
        nothing about the refusal is lost.
        """

        orders = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}"
            "/orders?status=rejected"
        ).json()
        decisions = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}"
            "/decisions?is_allowed=false"
        ).json()

        assert orders["total"] == 0
        assert decisions["total"] == 1
        assert decisions["items"][0]["primary_reason_code"] == "symbol_blocked"

    def test_the_order_schema_carries_a_rejection_field(
        self,
        client,
        seeded,
    ) -> None:
        """Persistable rejections have somewhere to report their reason."""

        order = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/orders"
        ).json()["items"][0]

        assert "rejection_reason" in order
        assert "rejection_message" in order
        assert order["rejection_reason"] is None

    def test_fills_are_listed(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/fills"
        ).json()

        assert payload["total"] == 2
        assert {float(item["price"]) for item in payload["items"]} == {
            100.0,
            110.0,
        }

    def test_positions_are_listed(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/positions"
        ).json()

        assert payload["total"] == 1
        assert payload["items"][0]["status"] == "closed"
        assert payload["items"][0]["side"] == "long"

    def test_trades_are_listed(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/trades"
        ).json()

        assert payload["total"] == 1

        trade = payload["items"][0]

        assert trade["symbol"] == "XAUUSD"
        assert trade["net_pnl"] == pytest.approx(10.0)
        assert trade["exit_reason"] == "end_of_data"

    def test_decisions_are_listed_with_reasons(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/decisions"
        ).json()

        assert payload["total"] == 2

        refused = [
            item for item in payload["items"] if item["is_allowed"] is False
        ]

        assert len(refused) == 1
        assert refused[0]["primary_reason_code"] == "symbol_blocked"
        assert refused[0]["reasons"][0]["category"] == "account_rule"
        assert refused[0]["reasons"][0]["severity"] == "blocking"

    def test_decisions_can_be_filtered_by_outcome(self, client, seeded) -> None:
        allowed = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}"
            "/decisions?is_allowed=true"
        ).json()

        assert allowed["total"] == 1
        assert allowed["items"][0]["is_allowed"] is True

    @pytest.mark.parametrize(
        "section",
        ["orders", "fills", "positions", "trades", "decisions"],
    )
    def test_records_for_an_unknown_session_are_not_found(
        self,
        client,
        seeded,
        section,
    ) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/paper/sessions/session_missing/{section}"
        ).status_code == 404

    @pytest.mark.parametrize(
        "section",
        ["orders", "fills", "positions", "trades", "decisions"],
    )
    def test_another_session_sees_none_of_this_activity(
        self,
        client,
        seeded,
        section,
    ) -> None:
        """
        Records are scoped to their own session.

        Both sessions share an account, so an unscoped query would leak one
        run's activity into the other's history.
        """

        payload = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['other_session_id']}"
            f"/{section}"
        ).json()

        assert payload["total"] == 0
        assert payload["items"] == []

    def test_pagination_windows_the_records(self, client, seeded) -> None:
        first = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}"
            "/orders?limit=1&offset=0"
        ).json()

        assert first["count"] == 1
        assert first["total"] == 2

    def test_an_invalid_limit_is_refused(self, client, seeded) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}"
            "/orders?limit=0"
        ).status_code == 422


class TestReadOnlyBehaviour:
    def test_reads_write_nothing(self, client, paper_database, seeded) -> None:
        def row_counts() -> dict[str, int]:
            with paper_database.read_session() as session:
                return {
                    table: session.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar_one()
                    for table in (
                        "paper_sessions",
                        "paper_orders",
                        "paper_fills",
                        "paper_positions",
                        "paper_trades",
                        "paper_execution_decisions",
                    )
                }

        before = row_counts()

        for path in (
            f"{API_V1_PREFIX}/paper/sessions",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/result",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/orders",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/fills",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/positions",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/trades",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/decisions",
        ):
            assert client.get(path).status_code == 200

        # Building a result must not persist one as a side effect.
        assert row_counts() == before

    def test_every_response_is_strict_json(self, client, seeded) -> None:
        for path in (
            f"{API_V1_PREFIX}/paper/sessions",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/result",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/trades",
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/decisions",
            f"{API_V1_PREFIX}/paper/sessions/session_missing",
        ):
            body = client.get(path).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)

    def test_decimal_values_render_as_numbers(self, client, seeded) -> None:
        trade = client.get(
            f"{API_V1_PREFIX}/paper/sessions/{seeded['session_id']}/trades"
        ).json()["items"][0]

        for field in ("quantity", "entry_price", "exit_price", "net_pnl"):
            assert isinstance(trade[field], (int, float)), field

    def test_no_response_leaks_infrastructure(
        self,
        client,
        seeded,
        database_url,
    ) -> None:
        for path in (
            f"{API_V1_PREFIX}/paper/sessions",
            f"{API_V1_PREFIX}/paper/sessions/session_missing",
        ):
            body = client.get(path).text

            assert database_url not in body
            assert "aqos_pw" not in body
            assert "Traceback" not in body
