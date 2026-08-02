"""
Account performance report persistence against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import os
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from aqos.account_analytics.metrics import AccountTradeRecord
from aqos.account_analytics.service import (
    AccountAnalyticsService,
    AccountAnalyticsSnapshotRepository,
)
from aqos.account_reports.artifacts import (
    verify_report_artifact,
    write_report_json,
    write_report_summary_csv,
)
from aqos.account_reports.builder import build_account_performance_report
from aqos.account_reports.contracts import AccountReportError, ReportFormat, ReportType
from aqos.account_reports.repositories import (
    AccountPerformanceReportRecord,
    AccountPerformanceReportRepository,
)
from aqos.accounts.models import AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.funded_rules.repositories import FundedAccountRulesRepository
from aqos.signals.models import SignalAction, SignalSource
from aqos.signals.repositories import TradingSignalRepository
from aqos.signal_reasons.repositories import (
    SignalReasonRepository,
    reject_signal_with_reason,
)
from aqos.signal_reasons.taxonomy import SignalReasonCode
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so account performance reports are "
            "NOT verified against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
            "account_performance_reports",
            "account_analytics_snapshots",
            "signal_reasons",
            "signal_events",
            "trading_signals",
            "funded_account_rules",
            "funded_rule_templates",
            "trading_accounts",
            "symbol_preferences",
            "trading_settings",
            "user_preferences",
            "user_sessions",
            "user_credentials",
            "user_profiles",
        ):
            session.execute(text(f"TRUNCATE TABLE {table}"))

        session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))


@pytest.fixture
def report_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; reports NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def funded_account(report_database) -> tuple[str, str]:
    with report_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="trader@example.com",
            display_name="Primary Trader",
            created_at_utc=FIXED_NOW,
        ).user_id

        account_id = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Funded 100k",
            account_type=AccountType.FUNDED,
            broker=BrokerKind.MT5,
            initial_balance=100_000.0,
            created_at_utc=FIXED_NOW,
        ).account_id

        return user_id, account_id


def seed_signals(report_database, user_id: str, account_id: str) -> None:
    with report_database.session() as session:
        signals = TradingSignalRepository(session)
        reasons = SignalReasonRepository(session)

        executed = signals.create_signal(
            user_id=user_id,
            account_id=account_id,
            symbol="XAUUSD",
            timeframe="H1",
            action=SignalAction.BUY,
            source=SignalSource.MANUAL,
            generated_at_utc=FIXED_NOW,
        ).signal_id
        signals.approve_signal(executed)
        signals.mark_executed(executed)

        rejected = signals.create_signal(
            user_id=user_id,
            account_id=account_id,
            symbol="EURUSD",
            timeframe="H1",
            action=SignalAction.SELL,
            source=SignalSource.MANUAL,
            generated_at_utc=FIXED_NOW,
        ).signal_id
        reject_signal_with_reason(
            signals=signals,
            reasons=reasons,
            signal_id=rejected,
            reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
            account_id=account_id,
        )


def build_report_for(report_database, user_id: str, account_id: str, **overrides):
    with report_database.read_session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=overrides.pop("trade_source", None),
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
            starting_balance=overrides.pop("starting_balance", None),
        )
        account = TradingAccountRepository(session).require_account(account_id)

        return build_account_performance_report(
            analytics=analytics,
            account=account,
            generated_at_utc=FIXED_NOW,
            **overrides,
        )


def test_report_table_and_procedures_exist(report_database) -> None:
    with report_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    assert "account_performance_reports" in {str(row[0]) for row in rows}

    procedures = StoredProcedureService(report_database).list_procedures()

    assert "sp_aqos_account_report_summary" in procedures
    assert "sp_aqos_latest_report_per_account" in procedures
    assert "sp_aqos_report_counts_by_type" in procedures


def test_report_built_from_real_database_analytics(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    report = build_report_for(report_database, user_id, account_id)

    assert report.account_type == AccountType.FUNDED
    assert report.signal_metrics.signals_received == 2
    assert report.signal_metrics.signals_executed == 1
    assert report.reason_metrics.rejection_counts == {"spread_too_high": 1}
    assert report.trade_metrics_available is False
    assert report.trade_metrics.net_pnl is None


def test_register_report_with_artifact(report_database, funded_account, tmp_path) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    report = build_report_for(report_database, user_id, account_id)
    artifact = write_report_json(tmp_path / "report.json", report)

    with report_database.session() as session:
        AccountPerformanceReportRepository(session).register_report(
            report=report,
            artifact=artifact,
        )

    with report_database.read_session() as session:
        stored = AccountPerformanceReportRepository(session).require(report.report_id)

        assert stored.report_type == ReportType.ACCOUNT_SUMMARY
        assert stored.account_type == AccountType.FUNDED
        assert stored.artifact_format == ReportFormat.JSON
        assert stored.artifact_checksum == artifact.checksum
        assert stored.trade_metrics_available is False
        assert stored.payload_json["signal_metrics"]["signals_received"] == 2

    assert verify_report_artifact(artifact) is True


def test_register_report_links_an_analytics_snapshot(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    with report_database.session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )
        snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
            analytics
        ).snapshot_id
        account = TradingAccountRepository(session).require_account(account_id)

        report = build_account_performance_report(
            analytics=analytics,
            account=account,
            generated_at_utc=FIXED_NOW,
            analytics_snapshot_id=snapshot_id,
        )
        AccountPerformanceReportRepository(session).register_report(report=report)

    with report_database.read_session() as session:
        stored = AccountPerformanceReportRepository(session).require(report.report_id)

        assert stored.analytics_snapshot_id == snapshot_id


def test_funded_rule_summary_report_round_trip(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    with report_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    with report_database.session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )
        account = TradingAccountRepository(session).require_account(account_id)
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        report = build_account_performance_report(
            analytics=analytics,
            account=account,
            report_type=ReportType.FUNDED_RULE_SUMMARY,
            funded_rules=rules,
            generated_at_utc=FIXED_NOW,
        )
        AccountPerformanceReportRepository(session).register_report(report=report)

    with report_database.read_session() as session:
        stored = AccountPerformanceReportRepository(session).require(report.report_id)

        assert stored.report_type == ReportType.FUNDED_RULE_SUMMARY
        assert stored.payload_json["risk_summary"]["rules_status"] == "active"


def test_python_refuses_to_store_a_trade_report_without_trade_metrics(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account

    record = AccountPerformanceReportRecord(
        report_id="report_no_trades",
        user_id=user_id,
        account_id=account_id,
        account_type=AccountType.FUNDED,
        report_type=ReportType.TRADE_PERFORMANCE,
        generated_at_utc=FIXED_NOW,
        trade_metrics_available=False,
    )

    with pytest.raises(AccountReportError, match="cannot be stored without"):
        record.assert_report_is_supportable()


def test_mysql_refuses_a_trade_report_without_trade_metrics(
    report_database,
    funded_account,
) -> None:
    """The database enforces the same rule as the Python guard."""

    user_id, account_id = funded_account

    with pytest.raises(
        DatabaseError,
        match="ck_account_reports_trade_report_needs_trade_metrics",
    ):
        with report_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_performance_reports ("
                    "report_id, user_id, account_id, account_type, report_type, "
                    "generated_at_utc, trade_metrics_available, payload_json, "
                    "metadata_json) VALUES ("
                    ":report_id, :user_id, :account_id, 'funded', "
                    "'trade_performance', :generated_at, 0, '{}', '{}')"
                ),
                {
                    "report_id": "report_bypass",
                    "user_id": user_id,
                    "account_id": account_id,
                    "generated_at": FIXED_NOW,
                },
            )


def test_mysql_refuses_an_unknown_report_type(report_database, funded_account) -> None:
    user_id, account_id = funded_account

    with pytest.raises(DatabaseError, match="ck_account_reports_type_known"):
        with report_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_performance_reports ("
                    "report_id, user_id, account_id, account_type, report_type, "
                    "generated_at_utc, payload_json, metadata_json) VALUES ("
                    ":report_id, :user_id, :account_id, 'funded', 'astrology', "
                    ":generated_at, '{}', '{}')"
                ),
                {
                    "report_id": "report_type",
                    "user_id": user_id,
                    "account_id": account_id,
                    "generated_at": FIXED_NOW,
                },
            )


def test_mysql_refuses_a_short_checksum(report_database, funded_account) -> None:
    user_id, account_id = funded_account

    with pytest.raises(DatabaseError, match="ck_account_reports_checksum_length"):
        with report_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_performance_reports ("
                    "report_id, user_id, account_id, account_type, report_type, "
                    "generated_at_utc, artifact_checksum, payload_json, "
                    "metadata_json) VALUES ("
                    ":report_id, :user_id, :account_id, 'funded', "
                    "'account_summary', :generated_at, 'abc', '{}', '{}')"
                ),
                {
                    "report_id": "report_checksum",
                    "user_id": user_id,
                    "account_id": account_id,
                    "generated_at": FIXED_NOW,
                },
            )


def test_mysql_refuses_a_reversed_period(report_database, funded_account) -> None:
    user_id, account_id = funded_account

    with pytest.raises(DatabaseError, match="ck_account_reports_period_order"):
        with report_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_performance_reports ("
                    "report_id, user_id, account_id, account_type, report_type, "
                    "period_start_utc, period_end_utc, generated_at_utc, "
                    "payload_json, metadata_json) VALUES ("
                    ":report_id, :user_id, :account_id, 'funded', "
                    "'account_summary', :period_start, :period_end, "
                    ":generated_at, '{}', '{}')"
                ),
                {
                    "report_id": "report_period",
                    "user_id": user_id,
                    "account_id": account_id,
                    "period_start": datetime(2026, 2, 1),
                    "period_end": datetime(2026, 1, 1),
                    "generated_at": FIXED_NOW,
                },
            )


def test_trade_performance_report_is_storable_with_a_trade_source(
    report_database,
    funded_account,
    tmp_path,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    report = build_report_for(
        report_database,
        user_id,
        account_id,
        report_type=ReportType.TRADE_PERFORMANCE,
        trade_source=[
            AccountTradeRecord(
                trade_id="t1",
                net_pnl=900.0,
                closed_at_utc=datetime(2026, 1, 2),
            ),
            AccountTradeRecord(
                trade_id="t2",
                net_pnl=-300.0,
                closed_at_utc=datetime(2026, 1, 3),
            ),
        ],
        starting_balance=100_000.0,
    )
    artifact = write_report_json(tmp_path / "trade_report.json", report)

    with report_database.session() as session:
        AccountPerformanceReportRepository(session).register_report(
            report=report,
            artifact=artifact,
        )

    with report_database.read_session() as session:
        stored = AccountPerformanceReportRepository(session).require(report.report_id)

        assert stored.report_type == ReportType.TRADE_PERFORMANCE
        assert stored.trade_metrics_available is True
        assert stored.payload_json["trade_metrics"]["net_pnl"] == pytest.approx(600.0)


def test_report_repository_filters_and_latest(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    first = build_report_for(report_database, user_id, account_id)
    second = build_report_for(
        report_database,
        user_id,
        account_id,
        report_type=ReportType.REJECTION_ANALYSIS,
    )

    with report_database.session() as session:
        repository = AccountPerformanceReportRepository(session)
        repository.register_report(report=first)
        repository.register_report(report=second)

    with report_database.read_session() as session:
        repository = AccountPerformanceReportRepository(session)

        assert len(repository.list_reports(user_id=user_id)) == 2
        assert len(
            repository.list_reports(report_type=ReportType.REJECTION_ANALYSIS)
        ) == 1
        assert repository.latest_report(account_id) is not None
        assert repository.count_by_type(user_id) == {
            "account_summary": 1,
            "rejection_analysis": 1,
        }


def test_csv_summary_artifact_from_stored_reports(
    report_database,
    funded_account,
    tmp_path,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    reports = [
        build_report_for(report_database, user_id, account_id),
        build_report_for(
            report_database,
            user_id,
            account_id,
            report_type=ReportType.MISSED_SIGNAL_ANALYSIS,
        ),
    ]

    artifact = write_report_summary_csv(tmp_path / "summary.csv", reports)
    lines = artifact.path.read_text(encoding="utf-8").splitlines()
    values = dict(zip(lines[0].split(","), lines[1].split(",")))

    assert len(lines) == 3
    assert verify_report_artifact(artifact) is True
    assert values["total_trades"] == ""
    assert values["trade_metrics_available"] == "false"


def test_account_report_summary_stored_procedure(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    with report_database.session() as session:
        repository = AccountPerformanceReportRepository(session)
        repository.register_report(
            report=build_report_for(report_database, user_id, account_id)
        )
        repository.register_report(
            report=build_report_for(
                report_database,
                user_id,
                account_id,
                report_type=ReportType.SIGNAL_PERFORMANCE,
            )
        )

    result = StoredProcedureService(report_database).call_read_only(
        "sp_aqos_account_report_summary",
        parameters=(account_id,),
    )

    rows = {row["report_type"]: row for row in result.rows}

    assert set(rows) == {"account_summary", "signal_performance"}
    assert rows["account_summary"]["total"] == 1
    assert int(rows["account_summary"]["with_trade_metrics"]) == 0


def test_latest_report_per_account_stored_procedure(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    with report_database.session() as session:
        repository = AccountPerformanceReportRepository(session)
        repository.register_report(
            report=build_report_for(report_database, user_id, account_id)
        )

    result = StoredProcedureService(report_database).call_read_only(
        "sp_aqos_latest_report_per_account",
        parameters=(user_id,),
    )

    assert result.rows
    assert result.rows[0]["account_name"] == "Funded 100k"
    assert result.rows[0]["report_type"] == "account_summary"


def test_report_counts_by_type_stored_procedure(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    with report_database.session() as session:
        AccountPerformanceReportRepository(session).register_report(
            report=build_report_for(report_database, user_id, account_id)
        )

    result = StoredProcedureService(report_database).call_read_only(
        "sp_aqos_report_counts_by_type",
        parameters=(user_id,),
    )

    assert result.rows[0]["report_type"] == "account_summary"
    assert result.rows[0]["account_type"] == "funded"
    assert result.rows[0]["total"] == 1


def test_deleting_an_account_cascades_to_reports(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    with report_database.session() as session:
        AccountPerformanceReportRepository(session).register_report(
            report=build_report_for(report_database, user_id, account_id)
        )

    with report_database.session() as session:
        TradingAccountRepository(session).delete_account(account_id)

    with report_database.read_session() as session:
        assert AccountPerformanceReportRepository(session).list_reports(
            account_id=account_id
        ) == ()


def test_deleting_a_snapshot_detaches_the_report(
    report_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account
    seed_signals(report_database, user_id, account_id)

    with report_database.session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )
        snapshots = AccountAnalyticsSnapshotRepository(session)
        snapshot_id = snapshots.save_snapshot(analytics).snapshot_id
        account = TradingAccountRepository(session).require_account(account_id)

        report = build_account_performance_report(
            analytics=analytics,
            account=account,
            generated_at_utc=FIXED_NOW,
            analytics_snapshot_id=snapshot_id,
        )
        AccountPerformanceReportRepository(session).register_report(report=report)

    with report_database.session() as session:
        AccountAnalyticsSnapshotRepository(session).delete_by_primary_key(snapshot_id)

    with report_database.read_session() as session:
        stored = AccountPerformanceReportRepository(session).require(report.report_id)

        assert stored.analytics_snapshot_id is None
