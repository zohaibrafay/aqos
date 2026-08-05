"""
Account analytics against real MySQL 8.

Run with::

    AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/aqos_test \\
        pytest -m mysql
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from aqos.account_analytics.metrics import (
    AccountTradeRecord,
    ProfitFactorState,
)
from aqos.account_analytics.models import (
    AccountAnalyticsError,
    AnalyticsScope,
)
from aqos.account_reports.artifacts import render_report_json
from aqos.account_reports.builder import build_account_performance_report
from aqos.account_reports.contracts import ReportType
from aqos.account_analytics.service import (
    AccountAnalyticsService,
    AccountAnalyticsSnapshotRepository,
)
from aqos.accounts.models import AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.signals.models import SignalAction, SignalSource, SignalStatus
from aqos.signals.repositories import TradingSignalRepository
from aqos.signal_reasons.repositories import (
    SignalReasonRepository,
    miss_signal_with_reason,
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
            f"{ENV_TEST_DB_URL} is not set, so account analytics are NOT "
            "verified against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
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
def analytics_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; analytics NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def account(analytics_database) -> tuple[str, str]:
    """Return ``(user_id, account_id)``."""

    with analytics_database.session() as session:
        user_id = UserProfileRepository(session).create_user(
            email="trader@example.com",
            display_name="Primary Trader",
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

        return user_id, account_id


def create_signal(session, user_id: str, account_id: str | None = None, **overrides):
    payload = {
        "user_id": user_id,
        "account_id": account_id,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "action": SignalAction.BUY,
        "source": SignalSource.MANUAL,
        "generated_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return TradingSignalRepository(session).create_signal(**payload)


def seed_lifecycle(analytics_database, user_id: str, account_id: str) -> None:
    """One executed, one rejected, one missed and one still generated."""

    with analytics_database.session() as session:
        signals = TradingSignalRepository(session)
        reasons = SignalReasonRepository(session)

        executed = create_signal(
            session,
            user_id,
            account_id,
            symbol="XAUUSD",
        ).signal_id
        signals.approve_signal(executed)
        signals.mark_executed(executed)

        rejected = create_signal(
            session,
            user_id,
            account_id,
            symbol="EURUSD",
        ).signal_id
        reject_signal_with_reason(
            signals=signals,
            reasons=reasons,
            signal_id=rejected,
            reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
            account_id=account_id,
        )

        missed = create_signal(
            session,
            user_id,
            account_id,
            symbol="BTCUSD",
        ).signal_id
        miss_signal_with_reason(
            signals=signals,
            reasons=reasons,
            signal_id=missed,
            reason_code=SignalReasonCode.APPROVAL_TIMEOUT,
            account_id=account_id,
        )

        create_signal(session, user_id, account_id, symbol="ETHUSD")


def test_analytics_table_and_procedures_exist(analytics_database) -> None:
    with analytics_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    assert "account_analytics_snapshots" in {str(row[0]) for row in rows}

    procedures = StoredProcedureService(analytics_database).list_procedures()

    assert "sp_aqos_account_signal_metrics" in procedures
    assert "sp_aqos_account_reason_breakdown" in procedures
    assert "sp_aqos_user_analytics_summary" in procedures


def test_signal_metrics_come_from_real_lifecycle_rows(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    with analytics_database.read_session() as session:
        metrics = AccountAnalyticsService(session).calculate_signal_metrics(
            user_id=user_id,
            account_id=account_id,
        )

    assert metrics.signals_received == 4
    assert metrics.signals_executed == 1
    assert metrics.signals_rejected == 1
    assert metrics.signals_missed == 1
    assert metrics.execution_rate == pytest.approx(0.25)
    assert metrics.rejection_rate == pytest.approx(0.25)
    assert metrics.missed_rate == pytest.approx(0.25)
    assert metrics.status_counts["generated"] == 1


def test_reason_metrics_come_from_real_reason_rows(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    with analytics_database.read_session() as session:
        metrics = AccountAnalyticsService(session).calculate_reason_metrics(
            user_id=user_id,
            account_id=account_id,
        )

    assert metrics.total == 2
    assert metrics.rejection_counts == {"spread_too_high": 1}
    assert metrics.missed_counts == {"approval_timeout": 1}
    assert metrics.by_category == {"market_condition": 1, "user_action": 1}
    assert metrics.by_severity == {"warning": 2}
    assert metrics.blocking_total == 0


def test_analytics_report_trade_metrics_as_unavailable(
    analytics_database,
    account,
) -> None:
    """Nothing produces trades yet, so nothing may report trade results."""

    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    with analytics_database.read_session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )

    assert analytics.has_trade_metrics is False
    assert analytics.trade_metrics.net_pnl is None
    assert analytics.trade_metrics.total_trades is None
    assert analytics.trade_metrics.unavailable_reason
    assert analytics.signal_metrics.signals_received == 4


def test_analytics_use_a_trade_source_when_one_is_supplied(
    analytics_database,
    account,
) -> None:
    """The calculator is ready; only the source is missing until Sprint 048."""

    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    trades = [
        AccountTradeRecord(
            trade_id="t1",
            net_pnl=120.0,
            closed_at_utc=datetime(2026, 1, 2),
        ),
        AccountTradeRecord(
            trade_id="t2",
            net_pnl=-40.0,
            closed_at_utc=datetime(2026, 1, 3),
        ),
    ]

    with analytics_database.read_session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=trades,
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            starting_balance=10_000.0,
            calculated_at_utc=FIXED_NOW,
        )

    assert analytics.has_trade_metrics is True
    assert analytics.trade_metrics.total_trades == 2
    assert analytics.trade_metrics.net_pnl == pytest.approx(80.0)
    assert analytics.trade_metrics.win_rate == pytest.approx(0.5)
    assert analytics.trade_metrics.ending_balance == pytest.approx(10_080.0)


def test_user_scoped_analytics_span_every_account(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    with analytics_database.session() as session:
        second = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Demo One",
            account_type=AccountType.DEMO,
            broker=BrokerKind.MT5,
            initial_balance=5_000.0,
        ).account_id
        create_signal(session, user_id, second, symbol="AUDUSD")

    with analytics_database.read_session() as session:
        service = AccountAnalyticsService(session)

        user_analytics = service.build_user_analytics(
            user_id=user_id,
            calculated_at_utc=FIXED_NOW,
        )
        account_analytics = service.build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )

    assert user_analytics.scope == AnalyticsScope.USER
    assert user_analytics.account_id is None
    assert user_analytics.signal_metrics.signals_received == 5
    assert account_analytics.signal_metrics.signals_received == 4


def test_analytics_respect_the_requested_period(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account

    with analytics_database.session() as session:
        create_signal(
            session,
            user_id,
            account_id,
            symbol="XAUUSD",
            generated_at_utc=datetime(2026, 1, 1),
        )
        create_signal(
            session,
            user_id,
            account_id,
            symbol="EURUSD",
            generated_at_utc=datetime(2026, 2, 1),
        )

    with analytics_database.read_session() as session:
        metrics = AccountAnalyticsService(session).calculate_signal_metrics(
            user_id=user_id,
            account_id=account_id,
            period_start_utc=datetime(2026, 1, 15),
        )

    assert metrics.signals_received == 1


def test_analytics_for_an_account_with_no_signals(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account

    with analytics_database.read_session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )

    assert analytics.signal_metrics.signals_received == 0
    assert analytics.signal_metrics.execution_rate is None
    assert analytics.reason_metrics.total == 0
    assert analytics.has_trade_metrics is False


def test_snapshot_round_trip(analytics_database, account) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )
        snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
            analytics
        ).snapshot_id

    with analytics_database.read_session() as session:
        stored = AccountAnalyticsSnapshotRepository(session).require(snapshot_id)

        assert stored.scope == AnalyticsScope.ACCOUNT
        assert stored.signals_received == 4
        assert stored.signals_executed == 1
        assert float(stored.execution_rate) == pytest.approx(0.25)
        assert stored.reason_total == 2
        assert stored.trade_metrics_available is False
        assert stored.total_trades is None
        assert stored.net_pnl is None
        assert stored.payload_json["signal_metrics"]["signals_received"] == 4


def test_snapshot_with_a_trade_source_stores_trade_metrics(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    trades = [
        AccountTradeRecord(
            trade_id="t1",
            net_pnl=200.0,
            closed_at_utc=datetime(2026, 1, 2),
        ),
        AccountTradeRecord(
            trade_id="t2",
            net_pnl=-50.0,
            closed_at_utc=datetime(2026, 1, 3),
        ),
    ]

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=trades,
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            starting_balance=10_000.0,
            calculated_at_utc=FIXED_NOW,
        )
        snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
            analytics
        ).snapshot_id

    with analytics_database.read_session() as session:
        stored = AccountAnalyticsSnapshotRepository(session).require(snapshot_id)

        assert stored.trade_metrics_available is True
        assert stored.total_trades == 2
        assert float(stored.net_pnl) == pytest.approx(150.0)
        assert float(stored.win_rate) == pytest.approx(0.5)


def test_snapshot_repository_filters(analytics_database, account) -> None:
    user_id, account_id = account

    with analytics_database.session() as session:
        service = AccountAnalyticsService(session)
        repository = AccountAnalyticsSnapshotRepository(session)

        repository.save_snapshot(
            service.build_account_analytics(
                user_id=user_id,
                account_id=account_id,
                calculated_at_utc=FIXED_NOW,
            )
        )
        repository.save_snapshot(
            service.build_user_analytics(
                user_id=user_id,
                calculated_at_utc=datetime(2026, 1, 2),
            )
        )

    with analytics_database.read_session() as session:
        repository = AccountAnalyticsSnapshotRepository(session)

        assert len(repository.list_snapshots(user_id=user_id)) == 2
        assert len(
            repository.list_snapshots(scope=AnalyticsScope.ACCOUNT)
        ) == 1
        assert repository.latest_snapshot(account_id).scope == (
            AnalyticsScope.ACCOUNT
        )


def test_python_refuses_a_dishonest_snapshot(analytics_database, account) -> None:
    user_id, _ = account

    from aqos.account_analytics.models import AccountAnalyticsSnapshot

    snapshot = AccountAnalyticsSnapshot(
        snapshot_id="snapshot_dishonest",
        user_id=user_id,
        scope=AnalyticsScope.USER,
        calculated_at_utc=FIXED_NOW,
        trade_metrics_available=False,
        net_pnl=0.0,
    )

    with pytest.raises(AccountAnalyticsError, match="must stay unset"):
        snapshot.assert_trade_metrics_are_honest()


def test_mysql_refuses_trade_metrics_without_a_source(
    analytics_database,
    account,
) -> None:
    """The database enforces the same honesty rule as the Python model."""

    user_id, _ = account

    with pytest.raises(
        DatabaseError,
        match="ck_account_analytics_no_trade_metrics_without_source",
    ):
        with analytics_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_analytics_snapshots ("
                    "snapshot_id, user_id, scope, calculated_at_utc, "
                    "trade_metrics_available, net_pnl, payload_json, "
                    "metadata_json) VALUES ("
                    ":snapshot_id, :user_id, 'user', :calculated_at, 0, 0, "
                    "'{}', '{}')"
                ),
                {
                    "snapshot_id": "snapshot_bypass",
                    "user_id": user_id,
                    "calculated_at": FIXED_NOW,
                },
            )


def test_mysql_refuses_an_account_scope_without_an_account(
    analytics_database,
    account,
) -> None:
    user_id, _ = account

    with pytest.raises(
        DatabaseError,
        match="ck_account_analytics_account_scope_has_account",
    ):
        with analytics_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_analytics_snapshots ("
                    "snapshot_id, user_id, scope, calculated_at_utc, "
                    "payload_json, metadata_json) VALUES ("
                    ":snapshot_id, :user_id, 'account', :calculated_at, "
                    "'{}', '{}')"
                ),
                {
                    "snapshot_id": "snapshot_scope",
                    "user_id": user_id,
                    "calculated_at": FIXED_NOW,
                },
            )


def test_mysql_refuses_a_rate_above_one(analytics_database, account) -> None:
    user_id, _ = account

    with pytest.raises(
        DatabaseError,
        match="ck_account_analytics_rates_are_fractions",
    ):
        with analytics_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_analytics_snapshots ("
                    "snapshot_id, user_id, scope, calculated_at_utc, "
                    "execution_rate, payload_json, metadata_json) VALUES ("
                    ":snapshot_id, :user_id, 'user', :calculated_at, 1.5, "
                    "'{}', '{}')"
                ),
                {
                    "snapshot_id": "snapshot_rate",
                    "user_id": user_id,
                    "calculated_at": FIXED_NOW,
                },
            )


def test_mysql_refuses_a_reversed_period(analytics_database, account) -> None:
    user_id, _ = account

    with pytest.raises(DatabaseError, match="ck_account_analytics_period_order"):
        with analytics_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO account_analytics_snapshots ("
                    "snapshot_id, user_id, scope, period_start_utc, "
                    "period_end_utc, calculated_at_utc, payload_json, "
                    "metadata_json) VALUES ("
                    ":snapshot_id, :user_id, 'user', :period_start, "
                    ":period_end, :calculated_at, '{}', '{}')"
                ),
                {
                    "snapshot_id": "snapshot_period",
                    "user_id": user_id,
                    "period_start": datetime(2026, 2, 1),
                    "period_end": datetime(2026, 1, 1),
                    "calculated_at": FIXED_NOW,
                },
            )


def test_account_signal_metrics_stored_procedure(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    result = StoredProcedureService(analytics_database).call_read_only(
        "sp_aqos_account_signal_metrics",
        parameters=(account_id,),
    )

    counts = {row["status"]: row["total"] for row in result.rows}

    assert counts == {
        "executed": 1,
        "generated": 1,
        "missed": 1,
        "rejected": 1,
    }


def test_account_reason_breakdown_stored_procedure(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    result = StoredProcedureService(analytics_database).call_read_only(
        "sp_aqos_account_reason_breakdown",
        parameters=(account_id,),
    )

    codes = {row["reason_code"]: row for row in result.rows}

    assert set(codes) == {"spread_too_high", "approval_timeout"}
    assert codes["spread_too_high"]["signal_status"] == "rejected"
    assert codes["approval_timeout"]["signal_status"] == "missed"


def test_user_analytics_summary_stored_procedure(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    with analytics_database.session() as session:
        TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Empty Account",
            account_type=AccountType.DEMO,
            broker=BrokerKind.MT5,
            initial_balance=1_000.0,
        )

    result = StoredProcedureService(analytics_database).call_read_only(
        "sp_aqos_user_analytics_summary",
        parameters=(user_id,),
    )

    rows = {row["account_name"]: row for row in result.rows}

    assert rows["Paper One"]["signals_received"] == 4
    assert rows["Paper One"]["signals_executed"] == 1
    assert rows["Empty Account"]["signals_received"] == 0


def test_deleting_an_account_cascades_to_snapshots(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )
        AccountAnalyticsSnapshotRepository(session).save_snapshot(analytics)

    with analytics_database.session() as session:
        TradingAccountRepository(session).delete_account(account_id)

    with analytics_database.read_session() as session:
        assert AccountAnalyticsSnapshotRepository(session).list_snapshots(
            account_id=account_id
        ) == ()


def test_analytics_service_requires_a_session() -> None:
    with pytest.raises(ValueError, match="session is required"):
        AccountAnalyticsService(None)  # type: ignore[arg-type]

def test_mysql_refuses_a_finite_state_without_a_value(
    analytics_database,
    account,
) -> None:
    """A finite state must carry the number it claims to have measured."""

    user_id, _ = account

    with pytest.raises(
        DatabaseError,
        match="ck_account_analytics_finite_profit_factor_has_value",
    ):
        with analytics_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO account_analytics_snapshots ("
                        "snapshot_id, user_id, scope, calculated_at_utc, "
                        "trade_metrics_available, profit_factor, "
                        "profit_factor_state, payload_json, metadata_json"
                        ") VALUES (:snapshot_id, :user_id, 'user', "
                        ":calculated_at, 1, NULL, 'finite', "
                        "'{}', '{}')"
                    ),
                    {
                        "snapshot_id": "snapshot_pf1",
                        "user_id": user_id,
                        "calculated_at": FIXED_NOW,
                    },
                )


def test_mysql_refuses_an_infinite_state_carrying_a_number(
    analytics_database,
    account,
) -> None:
    user_id, _ = account

    with pytest.raises(
        DatabaseError,
        match="ck_account_analytics_non_finite_profit_factor_is_null",
    ):
        with analytics_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO account_analytics_snapshots ("
                        "snapshot_id, user_id, scope, calculated_at_utc, "
                        "trade_metrics_available, profit_factor, "
                        "profit_factor_state, payload_json, metadata_json"
                        ") VALUES (:snapshot_id, :user_id, 'user', "
                        ":calculated_at, 1, 2.5, 'infinite_no_losses', "
                        "'{}', '{}')"
                    ),
                    {
                        "snapshot_id": "snapshot_pf2",
                        "user_id": user_id,
                        "calculated_at": FIXED_NOW,
                    },
                )


def test_mysql_refuses_an_unknown_profit_factor_state(
    analytics_database,
    account,
) -> None:
    user_id, _ = account

    with pytest.raises(
        DatabaseError,
        match="ck_account_analytics_profit_factor_state",
    ):
        with analytics_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO account_analytics_snapshots ("
                        "snapshot_id, user_id, scope, calculated_at_utc, "
                        "trade_metrics_available, profit_factor, "
                        "profit_factor_state, payload_json, metadata_json"
                        ") VALUES (:snapshot_id, :user_id, 'user', "
                        ":calculated_at, 1, NULL, 'made_up', "
                        "'{}', '{}')"
                    ),
                    {
                        "snapshot_id": "snapshot_pf3",
                        "user_id": user_id,
                        "calculated_at": FIXED_NOW,
                    },
                )


def test_mysql_refuses_a_state_without_trade_metrics(
    analytics_database,
    account,
) -> None:
    """No trade source means no profit factor state either."""

    user_id, _ = account

    with pytest.raises(
        DatabaseError,
        match="ck_account_analytics_no_state_without_trade_metrics",
    ):
        with analytics_database.session() as session:
                session.execute(
                    text(
                        "INSERT INTO account_analytics_snapshots ("
                        "snapshot_id, user_id, scope, calculated_at_utc, "
                        "trade_metrics_available, profit_factor, "
                        "profit_factor_state, payload_json, metadata_json"
                        ") VALUES (:snapshot_id, :user_id, 'user', "
                        ":calculated_at, 0, NULL, 'infinite_no_losses', "
                        "'{}', '{}')"
                    ),
                    {
                        "snapshot_id": "snapshot_pf4",
                        "user_id": user_id,
                        "calculated_at": FIXED_NOW,
                    },
                )


def test_a_wins_only_account_snapshot_keeps_its_meaning(
    analytics_database,
    account,
) -> None:
    """
    The case the API layer would otherwise expose as 'no result'.

    Every trade won, so the profit factor is unbounded rather than absent.
    """

    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    trades = [
        AccountTradeRecord("t1", 120.0, datetime(2026, 1, 2)),
        AccountTradeRecord("t2", 80.0, datetime(2026, 1, 3)),
    ]

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=trades,
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            starting_balance=10_000.0,
            calculated_at_utc=FIXED_NOW,
        )
        snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
            analytics
        ).snapshot_id

    with analytics_database.read_session() as session:
        stored = AccountAnalyticsSnapshotRepository(session).require(snapshot_id)

        assert stored.trade_metrics_available is True
        assert stored.total_trades == 2
        assert stored.profit_factor is None
        assert stored.profit_factor_state == (
            ProfitFactorState.INFINITE_NO_LOSSES
        )
        assert stored.has_infinite_profit_factor is True


def test_a_mixed_account_snapshot_stores_a_finite_profit_factor(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    trades = [
        AccountTradeRecord("t1", 200.0, datetime(2026, 1, 2)),
        AccountTradeRecord("t2", -50.0, datetime(2026, 1, 3)),
    ]

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=trades,
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            starting_balance=10_000.0,
            calculated_at_utc=FIXED_NOW,
        )
        snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
            analytics
        ).snapshot_id

    with analytics_database.read_session() as session:
        stored = AccountAnalyticsSnapshotRepository(session).require(snapshot_id)

        assert float(stored.profit_factor) == pytest.approx(4.0)
        assert stored.profit_factor_state == ProfitFactorState.FINITE


def test_a_snapshot_without_a_trade_source_stays_unavailable(
    analytics_database,
    account,
) -> None:
    user_id, account_id = account

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(session).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            calculated_at_utc=FIXED_NOW,
        )
        snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
            analytics
        ).snapshot_id

    with analytics_database.read_session() as session:
        stored = AccountAnalyticsSnapshotRepository(session).require(snapshot_id)

        assert stored.trade_metrics_available is False
        assert stored.profit_factor is None
        assert stored.profit_factor_state == ProfitFactorState.UNAVAILABLE
        assert stored.has_infinite_profit_factor is False


def test_profit_factor_state_procedure(analytics_database, account) -> None:
    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    trades = [
        AccountTradeRecord("t1", 120.0, datetime(2026, 1, 2)),
    ]

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=trades,
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            starting_balance=10_000.0,
            calculated_at_utc=FIXED_NOW,
        )
        AccountAnalyticsSnapshotRepository(session).save_snapshot(analytics)

    result = StoredProcedureService(analytics_database).call_read_only(
        "sp_aqos_account_profit_factor_states",
        parameters=(account_id,),
    )

    assert len(result.rows) == 1
    assert result.rows[0]["profit_factor"] is None
    assert result.rows[0]["profit_factor_state"] == "infinite_no_losses"


def test_stored_payload_json_contains_no_non_json_numbers(
    analytics_database,
    account,
) -> None:
    """
    The exact failure that made MySQL reject the insert.

    Python renders infinity as the bare token ``Infinity``, which is not JSON.
    The stored payload must be parseable by anything that reads the column.
    """

    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    trades = [
        AccountTradeRecord("t1", 120.0, datetime(2026, 1, 2)),
        AccountTradeRecord("t2", 80.0, datetime(2026, 1, 3)),
    ]

    with analytics_database.session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=trades,
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            starting_balance=10_000.0,
            calculated_at_utc=FIXED_NOW,
        )
        snapshot_id = AccountAnalyticsSnapshotRepository(session).save_snapshot(
            analytics
        ).snapshot_id

    with analytics_database.read_session() as session:
        raw = session.execute(
            text(
                "SELECT CAST(payload_json AS CHAR) FROM "
                "account_analytics_snapshots WHERE snapshot_id = :snapshot_id"
            ),
            {"snapshot_id": snapshot_id},
        ).scalar_one()

    for token in ("Infinity", "-Infinity", "NaN"):
        assert token not in raw

    payload = json.loads(raw)

    assert payload["trade_metrics"]["profit_factor"] is None
    assert payload["trade_metrics"]["profit_factor_state"] == (
        "infinite_no_losses"
    )
    assert payload["trade_metrics"]["has_infinite_profit_factor"] is True


def test_a_wins_only_report_artifact_is_valid_json(
    analytics_database,
    account,
) -> None:
    """The report artifact a consumer would download must parse."""

    user_id, account_id = account
    seed_lifecycle(analytics_database, user_id, account_id)

    trades = [
        AccountTradeRecord("t1", 120.0, datetime(2026, 1, 2)),
    ]

    with analytics_database.read_session() as session:
        analytics = AccountAnalyticsService(
            session,
            trade_source=trades,
        ).build_account_analytics(
            user_id=user_id,
            account_id=account_id,
            starting_balance=10_000.0,
            calculated_at_utc=FIXED_NOW,
        )
        trading_account = TradingAccountRepository(session).require(account_id)

        report = build_account_performance_report(
            analytics=analytics,
            account=trading_account,
            report_type=ReportType.TRADE_PERFORMANCE,
            generated_at_utc=FIXED_NOW,
        )

    rendered = render_report_json(report)

    for token in ("Infinity", "-Infinity", "NaN"):
        assert token not in rendered

    restored = json.loads(rendered)

    assert restored["trade_metrics"]["profit_factor"] is None
    assert restored["trade_metrics"]["profit_factor_state"] == (
        "infinite_no_losses"
    )
