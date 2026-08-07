"""
Read-only account, analytics and report APIs against real MySQL 8.

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

from aqos.account_analytics.metrics import AccountTradeRecord
from aqos.account_analytics.service import (
    AccountAnalyticsService,
    AccountAnalyticsSnapshotRepository,
)
from aqos.account_reports.builder import build_account_performance_report
from aqos.account_reports.artifacts import ReportArtifact
from aqos.account_reports.contracts import ReportFormat, ReportType
from aqos.account_reports.repositories import (
    AccountPerformanceReportRepository,
)
from aqos.accounts.models import AccountStatus, AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.execution_policy.modes import ExecutionMode
from aqos.funded_rules.models import FundedRuleStatus
from aqos.funded_rules.repositories import FundedAccountRulesRepository
from aqos.http_api.app import create_aqos_api_app
from aqos.http_api.config import API_V1_PREFIX, ApiConfig, ApiEnvironment
from aqos.http_api.pagination import MAX_PAGE_LIMIT
from aqos.http_api.routes_accounts import (
    TRADE_SOURCE_NOT_CONNECTED_CODE,
)
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderType,
)
from aqos.paper_trading.execution_service import PaperExecutionService
from aqos.paper_trading.history import PaperTradeSource
from aqos.paper_trading.simulator import PaperMarketBar
from aqos.trading_settings.repositories import TradingSettingsRepository
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

SECRET_CREDENTIAL = "broker-secret-token-value"

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so the read-only account APIs are "
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
            "so the read-only account APIs are NOT verified by this run. Start "
            "MySQL and run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "account_performance_reports",
            "account_analytics_snapshots",
            "signal_reasons",
            "signal_events",
            "trading_signals",
            "paper_execution_decisions",
            "paper_account_snapshots",
            "paper_trades",
            "paper_fills",
            "paper_positions",
            "paper_orders",
            "paper_sessions",
            "funded_account_rules",
            "funded_rule_templates",
            "trading_accounts",
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
def account_database(database_url: str) -> AqosDatabase:
    database = AqosDatabase(config=parse_database_url(database_url))

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def seeded(account_database) -> dict:
    """A paper account and a funded account, one with rules assigned."""

    with account_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="accounts@example.com",
            display_name="Account Reader",
            created_at_utc=FIXED_NOW,
        ).user_id

        TradingSettingsRepository(session).create_for_user(
            user_id=user_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
            created_at_utc=FIXED_NOW,
        )

        accounts = TradingAccountRepository(session)

        paper = accounts.create_account(
            user_id=user_id,
            name="Paper One",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
            created_at_utc=FIXED_NOW,
        )

        funded = accounts.create_account(
            user_id=user_id,
            name="Funded One",
            account_type=AccountType.FUNDED,
            broker=BrokerKind.MT5,
            initial_balance=50_000.0,
            broker_credential_ref=SECRET_CREDENTIAL,
            broker_account_ref="MT5-123456",
            created_at_utc=FIXED_NOW,
        )

        FundedAccountRulesRepository(session).assign_rules(
            account_id=funded.account_id,
            max_daily_loss_fraction=0.05,
            max_total_drawdown_fraction=0.10,
            profit_target_fraction=0.08,
            created_at_utc=FIXED_NOW,
        )

        return {
            "user_id": user_id,
            "paper_account_id": paper.account_id,
            "funded_account_id": funded.account_id,
        }


@pytest.fixture
def client(account_database, database_url: str) -> TestClient:
    app = create_aqos_api_app(
        ApiConfig(
            environment=ApiEnvironment.TEST,
            database_url=database_url,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    app.state.aqos_database.dispose()


def accounts_url(**params) -> str:
    query = "&".join(f"{key}={value}" for key, value in params.items())

    return f"{API_V1_PREFIX}/accounts" + (f"?{query}" if query else "")


class TestAccountList:
    def test_it_lists_accounts(self, client, seeded) -> None:
        payload = client.get(accounts_url()).json()

        assert payload["count"] == 2
        assert payload["total"] is None
        assert {item["account_name"] for item in payload["items"]} == {
            "Paper One",
            "Funded One",
        }

    def test_it_filters_by_account_type(self, client, seeded) -> None:
        payload = client.get(accounts_url(account_type="paper")).json()

        assert payload["count"] == 1
        assert payload["items"][0]["account_type"] == "paper"

    def test_it_filters_by_venue(self, client, seeded) -> None:
        payload = client.get(accounts_url(venue="mt5")).json()

        assert payload["count"] == 1
        assert payload["items"][0]["venue"] == "mt5"

    def test_it_filters_by_execution_mode(self, client, seeded) -> None:
        payload = client.get(accounts_url(execution_mode="auto_trade")).json()

        assert payload["count"] == 1
        assert payload["items"][0]["account_name"] == "Paper One"

    def test_it_filters_by_status(self, client, seeded) -> None:
        assert client.get(accounts_url(status="active")).json()["count"] == 2
        assert client.get(accounts_url(status="suspended")).json()["count"] == 0

    def test_it_filters_by_user(self, client, seeded) -> None:
        assert client.get(
            accounts_url(user_id=seeded["user_id"])
        ).json()["count"] == 2
        assert client.get(
            accounts_url(user_id="user_missing")
        ).json()["count"] == 0

    def test_pagination_windows_the_result(self, client, seeded) -> None:
        first = client.get(accounts_url(limit=1, offset=0)).json()
        second = client.get(accounts_url(limit=1, offset=1)).json()

        assert first["count"] == 1
        assert second["count"] == 1
        assert first["items"][0]["account_id"] != second["items"][0][
            "account_id"
        ]

    @pytest.mark.parametrize("limit", [0, -1, MAX_PAGE_LIMIT + 1])
    def test_an_invalid_limit_is_refused(self, client, seeded, limit) -> None:
        response = client.get(accounts_url(limit=limit))

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "validation_error"

    def test_a_negative_offset_is_refused(self, client, seeded) -> None:
        assert client.get(accounts_url(offset=-1)).status_code == 422

    @pytest.mark.parametrize(
        "field, value",
        [
            ("account_type", "crypto_wallet"),
            ("venue", "carrier_pigeon"),
            ("status", "hibernating"),
            ("execution_mode", "yolo"),
        ],
    )
    def test_an_unknown_enum_is_refused(
        self,
        client,
        seeded,
        field,
        value,
    ) -> None:
        response = client.get(accounts_url(**{field: value}))

        assert response.status_code == 422
        assert response.json()["error"]["details"]["field"] == field


class TestAccountDetail:
    def test_it_returns_the_account(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
        ).json()

        assert payload["account_type"] == "paper"
        assert payload["venue"] == "internal_paper"
        assert payload["currency"] == "USD"
        assert payload["initial_balance"] == pytest.approx(10_000.0)
        assert payload["leverage"] == 1
        assert payload["auto_trade_enabled"] is True

    def test_broker_credentials_are_never_exposed(
        self,
        client,
        seeded,
    ) -> None:
        """A credential reference must not reach a read API."""

        body = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
        ).text

        assert SECRET_CREDENTIAL not in body
        assert "MT5-123456" not in body
        assert "credential" not in body.lower()

    def test_no_orm_internals_or_metadata_are_exposed(
        self,
        client,
        seeded,
    ) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
        ).json()

        assert "metadata" not in payload
        assert "_sa_instance_state" not in payload

    def test_an_unknown_account_is_not_found(self, client, seeded) -> None:
        response = client.get(f"{API_V1_PREFIX}/accounts/account_missing")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"

    def test_decimal_balances_serialise_as_numbers(
        self,
        client,
        seeded,
    ) -> None:
        """MySQL returns DECIMAL; the API must render real JSON numbers."""

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
        ).json()

        for field in ("initial_balance", "current_balance", "equity"):
            assert isinstance(payload[field], (int, float))

        assert payload["current_balance"] == pytest.approx(50_000.0)


class TestExecutionConstraints:
    def test_the_strictest_ceiling_wins(self, client, seeded) -> None:
        """Account allows auto_trade, user settings cap at manual_approval."""

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/execution-constraints"
        ).json()

        assert payload["stored_execution_mode"] == "auto_trade"
        assert payload["effective_execution_mode"] == "manual_approval"
        assert payload["was_downgraded"] is True
        assert "user_settings" in payload["binding_sources"]
        assert "user_settings=manual_approval" in payload["explanation"]

    def test_a_funded_rule_contributes_a_ceiling(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/execution-constraints"
        ).json()
        sources = {item["source"] for item in payload["constraints"]}

        assert "funded_rule" in sources
        assert "account" in sources

    def test_a_breached_funded_rule_forces_the_floor(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        with account_database.session() as session:
            FundedAccountRulesRepository(session).mark_breached(
                account_id=seeded["funded_account_id"],
                reason="Daily loss limit breached.",
            )

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/execution-constraints"
        ).json()

        assert payload["allows_orders"] is False
        assert "funded_rule" in payload["binding_sources"]

    def test_it_is_not_found_for_an_unknown_account(
        self,
        client,
        seeded,
    ) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/accounts/account_missing/execution-constraints"
        ).status_code == 404


class TestFundedRules:
    def test_it_returns_the_copied_limits(self, client, seeded) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/funded-rules"
        ).json()

        assert payload["max_daily_loss_fraction"] == pytest.approx(0.05)
        assert payload["max_total_drawdown_fraction"] == pytest.approx(0.10)
        assert payload["profit_target_fraction"] == pytest.approx(0.08)
        assert payload["status"] == FundedRuleStatus.ACTIVE.value
        assert payload["is_breached"] is False

    def test_it_names_no_prop_firm(self, client, seeded) -> None:
        """Rules are generic limits; no firm is hardcoded anywhere."""

        body = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/funded-rules"
        ).text.lower()

        for firm in ("ftmo", "the5ers", "myforexfunds", "mff"):
            assert firm not in body

    def test_an_account_without_rules_is_not_found(
        self,
        client,
        seeded,
    ) -> None:
        response = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/funded-rules"
        )

        assert response.status_code == 404
        assert "no funded rules" in response.json()["error"]["message"]

    def test_a_breach_is_reported(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        with account_database.session() as session:
            FundedAccountRulesRepository(session).mark_breached(
                account_id=seeded["funded_account_id"],
                reason="Daily loss limit breached.",
            )

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/funded-rules"
        ).json()

        assert payload["is_breached"] is True
        assert payload["breached_at_utc"]
        assert payload["breach_reason"] == "Daily loss limit breached."


class TestAccountAnalytics:
    def test_a_live_account_has_no_trade_source(
        self,
        client,
        seeded,
    ) -> None:
        """Unknown, not zero: nothing supplies trades for a funded account."""

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}/analytics"
        ).json()
        metrics = payload["trade_metrics"]

        assert payload["has_trade_metrics"] is False
        assert metrics["total_trades"] is None
        assert metrics["net_pnl"] is None
        assert metrics["profit_factor"] is None
        assert metrics["profit_factor_state"] == "unavailable"
        assert metrics["unavailable_reason"]

    def test_a_paper_account_also_reports_no_trade_source(
        self,
        client,
        seeded,
    ) -> None:
        """
        This endpoint connects no trade source, so it says so.

        Wiring the simulated-trade source in would make this package depend on
        the paper simulator, which the isolation guard forbids. Reporting
        "unavailable" is the honest description of what was measured here;
        measured trade metrics are available through stored snapshots.
        """

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics"
        ).json()
        metrics = payload["trade_metrics"]

        assert payload["has_trade_metrics"] is False
        assert metrics["total_trades"] is None
        assert metrics["net_pnl"] is None
        assert metrics["unavailable_reason"]

    def test_signal_metrics_are_still_measured(
        self,
        client,
        seeded,
    ) -> None:
        """The lifecycle half of analytics is real regardless."""

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics"
        ).json()

        assert payload["signal_metrics"]["signals_received"] == 0
        assert payload["reason_metrics"]["total"] == 0

    def test_the_response_is_strict_json(self, client, seeded) -> None:
        for account_id in (
            seeded["paper_account_id"],
            seeded["funded_account_id"],
        ):
            body = client.get(
                f"{API_V1_PREFIX}/accounts/{account_id}/analytics"
            ).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)


class TestAnalyticsSnapshots:
    def test_it_lists_stored_snapshots(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        with account_database.session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=[
                    AccountTradeRecord("t1", 120.0, datetime(2026, 1, 2)),
                    AccountTradeRecord("t2", -40.0, datetime(2026, 1, 3)),
                ],
            ).build_account_analytics(
                user_id=seeded["user_id"],
                account_id=seeded["paper_account_id"],
                starting_balance=10_000.0,
                calculated_at_utc=FIXED_NOW,
            )
            AccountAnalyticsSnapshotRepository(session).save_snapshot(analytics)

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/analytics/snapshots"
        ).json()

        assert payload["total"] == 1

        snapshot = payload["items"][0]

        assert snapshot["trade_metrics_available"] is True
        assert snapshot["total_trades"] == 2
        assert snapshot["net_pnl"] == pytest.approx(80.0)
        assert snapshot["profit_factor_state"] == "finite"

    def test_a_wins_only_snapshot_keeps_its_state(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """The case where the number alone would read as "no result"."""

        with account_database.session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=[
                    AccountTradeRecord("t1", 120.0, datetime(2026, 1, 2)),
                    AccountTradeRecord("t2", 80.0, datetime(2026, 1, 3)),
                ],
            ).build_account_analytics(
                user_id=seeded["user_id"],
                account_id=seeded["paper_account_id"],
                starting_balance=10_000.0,
                calculated_at_utc=FIXED_NOW,
            )
            AccountAnalyticsSnapshotRepository(session).save_snapshot(analytics)

        snapshot = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/analytics/snapshots"
        ).json()["items"][0]

        assert snapshot["profit_factor"] is None
        assert snapshot["profit_factor_state"] == "infinite_no_losses"
        assert snapshot["has_infinite_profit_factor"] is True

    def test_an_account_without_snapshots_is_empty_not_missing(
        self,
        client,
        seeded,
    ) -> None:
        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/analytics/snapshots"
        ).json()

        assert payload["items"] == []
        assert payload["total"] == 0


class TestReports:
    def register_report(self, account_database, seeded, report_type):
        with account_database.session() as session:
            account = TradingAccountRepository(session).require(
                seeded["paper_account_id"]
            )
            analytics = AccountAnalyticsService(
                session,
                trade_source=[
                    AccountTradeRecord("t1", 120.0, datetime(2026, 1, 2)),
                ],
            ).build_account_analytics(
                user_id=seeded["user_id"],
                account_id=account.account_id,
                starting_balance=10_000.0,
                calculated_at_utc=FIXED_NOW,
            )
            report = build_account_performance_report(
                analytics=analytics,
                account=account,
                report_type=report_type,
                generated_at_utc=FIXED_NOW,
            )

            return AccountPerformanceReportRepository(session).register_report(
                report=report,
                artifact=ReportArtifact(
                    path=Path("/srv/aqos/reports/secret-report.json"),
                    artifact_format=ReportFormat.JSON,
                    checksum="a" * 64,
                    size_bytes=1024,
                ),
            ).report_id

    def test_it_lists_reports(self, client, account_database, seeded) -> None:
        self.register_report(
            account_database,
            seeded,
            ReportType.ACCOUNT_SUMMARY,
        )

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/reports"
        ).json()

        assert payload["total"] == 1
        assert payload["items"][0]["report_type"] == "account_summary"

    def test_no_filesystem_path_or_checksum_is_exposed(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """The artifact lives on the server's disk; clients get neither."""

        self.register_report(
            account_database,
            seeded,
            ReportType.ACCOUNT_SUMMARY,
        )

        body = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/reports"
        ).text

        assert "secret-report.json" not in body
        assert "/srv/aqos" not in body
        assert "a" * 64 not in body
        assert "checksum" not in body
        assert "artifact_path" not in body

    def test_the_detail_carries_the_stored_payload(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        report_id = self.register_report(
            account_database,
            seeded,
            ReportType.ACCOUNT_SUMMARY,
        )

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            f"/reports/{report_id}"
        ).json()

        assert payload["report_id"] == report_id
        assert payload["has_artifact"] is True
        assert payload["payload"]["report_type"] == "account_summary"

    def test_a_report_cannot_be_read_through_another_account(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """A report id alone must not reach across accounts."""

        report_id = self.register_report(
            account_database,
            seeded,
            ReportType.ACCOUNT_SUMMARY,
        )

        response = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            f"/reports/{report_id}"
        )

        assert response.status_code == 404

    def test_an_unknown_report_is_not_found(self, client, seeded) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/reports/report_missing"
        ).status_code == 404

    def test_it_filters_by_report_type(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        self.register_report(
            account_database,
            seeded,
            ReportType.ACCOUNT_SUMMARY,
        )

        matching = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/reports?report_type=account_summary"
        ).json()
        other = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/reports?report_type=rejection_analysis"
        ).json()

        assert matching["total"] == 1
        assert other["total"] == 0

    def test_an_unknown_report_type_is_refused(self, client, seeded) -> None:
        assert client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/reports?report_type=fantasy"
        ).status_code == 422


class TestReadOnlyBehaviour:
    def test_reads_write_nothing(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        def row_counts() -> dict[str, int]:
            with account_database.read_session() as session:
                return {
                    table: session.execute(
                        text(f"SELECT COUNT(*) FROM {table}")
                    ).scalar_one()
                    for table in (
                        "trading_accounts",
                        "account_analytics_snapshots",
                        "account_performance_reports",
                        "funded_account_rules",
                    )
                }

        before = row_counts()

        for path in (
            f"{API_V1_PREFIX}/accounts",
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}",
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics",
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/analytics/snapshots",
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/reports",
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/execution-constraints",
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/funded-rules",
        ):
            assert client.get(path).status_code == 200

        # Calculating analytics must not persist a snapshot as a side effect.
        assert row_counts() == before

    def test_no_response_leaks_infrastructure(
        self,
        client,
        seeded,
        database_url,
    ) -> None:
        for path in (
            f"{API_V1_PREFIX}/accounts",
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}",
            f"{API_V1_PREFIX}/accounts/account_missing",
        ):
            body = client.get(path).text

            assert database_url not in body
            assert "aqos_pw" not in body
            assert "Traceback" not in body
            assert SECRET_CREDENTIAL not in body

    def test_every_response_is_strict_json(self, client, seeded) -> None:
        for path in (
            f"{API_V1_PREFIX}/accounts",
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}",
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/execution-constraints",
            f"{API_V1_PREFIX}/accounts/{seeded['funded_account_id']}"
            "/funded-rules",
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics",
            f"{API_V1_PREFIX}/accounts/account_missing",
        ):
            body = client.get(path).text

            for token in ("Infinity", "-Infinity", "NaN"):
                assert token not in body

            json.loads(body)


class TestTradeSourceBoundary:
    """
    The case the isolation guard forces: real paper trades exist, but this
    endpoint does not connect the simulator, so it must say "unknown" rather
    than report a zero the account did not earn.
    """

    def run_paper_trade(self, account_database, seeded) -> float:
        """Execute and close one real winning paper trade. Returns its net PnL."""

        with account_database.session() as session:
            account = TradingAccountRepository(session).require(
                seeded["paper_account_id"]
            )
            service = PaperExecutionService(session)

            service.execute(
                request=PaperExecutionRequest(
                    user_id=seeded["user_id"],
                    account_id=account.account_id,
                    symbol="XAUUSD",
                    action=PaperAction.BUY,
                    quantity=1.0,
                    order_type=PaperOrderType.MARKET,
                    submitted_at_utc=FIXED_NOW,
                ),
                account=account,
                bar=PaperMarketBar(
                    symbol="XAUUSD",
                    timestamp_utc=FIXED_NOW,
                    open=100.0,
                    high=105.0,
                    low=95.0,
                    close=100.0,
                    volume=1_000.0,
                ),
            ).raise_if_rejected()

            outcome = service.close_all_positions(
                account,
                PaperMarketBar(
                    symbol="XAUUSD",
                    timestamp_utc=FIXED_NOW + timedelta(hours=1),
                    open=110.0,
                    high=111.0,
                    low=109.0,
                    close=110.0,
                    volume=1_000.0,
                ),
            )[0]

            return float(outcome.trade.net_pnl)

    def store_snapshot(self, account_database, seeded):
        """Persist a snapshot built from the account's real paper trades."""

        with account_database.session() as session:
            analytics = AccountAnalyticsService(
                session,
                trade_source=PaperTradeSource(session),
            ).build_account_analytics(
                user_id=seeded["user_id"],
                account_id=seeded["paper_account_id"],
                starting_balance=10_000.0,
                calculated_at_utc=FIXED_NOW,
            )

            return AccountAnalyticsSnapshotRepository(session).save_snapshot(
                analytics
            ).snapshot_id

    def test_live_analytics_reports_unknown_despite_real_trades(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """
        The account genuinely traded and genuinely profited.

        This endpoint still reports the trade source as unavailable, because it
        connects none — and it must never dress that up as a measured zero.
        """

        net_pnl = self.run_paper_trade(account_database, seeded)

        assert net_pnl > 0

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics"
        ).json()
        metrics = payload["trade_metrics"]

        assert payload["has_trade_metrics"] is False
        assert metrics["total_trades"] is None
        assert metrics["net_pnl"] is None
        assert metrics["win_rate"] is None
        assert metrics["profit_factor"] is None
        assert metrics["profit_factor_state"] == "unavailable"

    def test_the_reason_is_explicit_and_machine_readable(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        self.run_paper_trade(account_database, seeded)

        source = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics"
        ).json()["trade_metrics_source"]

        assert source["connected"] is False
        assert source["reason_code"] == TRADE_SOURCE_NOT_CONNECTED_CODE
        assert "snapshots" in source["measured_metrics_endpoint"]

    def test_nothing_is_faked_as_zero(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """
        Unknown must not be dressed as measured.

        Every trade figure stays null; a zero anywhere here would claim the
        account traded and broke even, which is false.
        """

        self.run_paper_trade(account_database, seeded)

        metrics = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics"
        ).json()["trade_metrics"]

        for field in (
            "total_trades",
            "winning_trades",
            "losing_trades",
            "net_pnl",
            "gross_profit",
            "gross_loss",
            "win_rate",
            "profit_factor",
            "max_drawdown",
        ):
            assert metrics[field] is None, field

    def test_snapshots_carry_the_measured_trade_metrics(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """The stored snapshot is where the real numbers live."""

        net_pnl = self.run_paper_trade(account_database, seeded)
        self.store_snapshot(account_database, seeded)

        payload = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/analytics/snapshots"
        ).json()

        assert payload["total"] == 1

        snapshot = payload["items"][0]

        assert snapshot["trade_metrics_available"] is True
        assert snapshot["total_trades"] == 1
        assert snapshot["net_pnl"] == pytest.approx(net_pnl)
        assert snapshot["win_rate"] == pytest.approx(1.0)

    def test_a_wins_only_snapshot_stays_json_safe(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """
        One winning trade and no losses: the profit factor is unbounded.

        Infinity has no JSON form, so the number is null and the state carries
        the meaning — otherwise this would be indistinguishable from a snapshot
        with nothing measured.
        """

        self.run_paper_trade(account_database, seeded)
        self.store_snapshot(account_database, seeded)

        response = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/analytics/snapshots"
        )

        for token in ("Infinity", "-Infinity", "NaN"):
            assert token not in response.text

        snapshot = json.loads(response.text)["items"][0]

        assert snapshot["profit_factor"] is None
        assert snapshot["profit_factor_state"] == "infinite_no_losses"
        assert snapshot["has_infinite_profit_factor"] is True

    def test_the_two_endpoints_disagree_for_a_documented_reason(
        self,
        client,
        account_database,
        seeded,
    ) -> None:
        """
        One says unknown, the other reports measured numbers.

        That is not a contradiction: they are different sources, and the live
        endpoint states which one it lacks.
        """

        self.run_paper_trade(account_database, seeded)
        self.store_snapshot(account_database, seeded)

        live = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}/analytics"
        ).json()
        stored = client.get(
            f"{API_V1_PREFIX}/accounts/{seeded['paper_account_id']}"
            "/analytics/snapshots"
        ).json()["items"][0]

        assert live["has_trade_metrics"] is False
        assert live["trade_metrics_source"]["reason_code"] == (
            TRADE_SOURCE_NOT_CONNECTED_CODE
        )
        assert stored["trade_metrics_available"] is True
        assert stored["total_trades"] == 1
