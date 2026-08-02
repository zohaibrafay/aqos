"""
Signal lifecycle and audit trail against real MySQL 8.

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

from aqos.accounts.models import AccountType, BrokerKind
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.database.repository import RecordNotFoundError, RepositoryError
from aqos.signals.models import (
    InvalidSignalTransitionError,
    SignalAction,
    SignalSource,
    SignalStatus,
)
from aqos.signals.repositories import TradingSignalRepository
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so the signal lifecycle is NOT "
            "verified against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
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
def signal_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; signals NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(signal_database) -> str:
    with signal_database.session() as session:
        return UserProfileRepository(session).create_user(
            email="trader@example.com",
            display_name="Primary Trader",
            created_at_utc=FIXED_NOW,
        ).user_id


def create_signal(session, user_id: str, **overrides):
    payload = {
        "user_id": user_id,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "action": SignalAction.BUY,
        "source": SignalSource.MANUAL,
        "generated_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return TradingSignalRepository(session).create_signal(**payload)


def test_signal_tables_and_procedures_exist(signal_database) -> None:
    with signal_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    assert {"trading_signals", "signal_events"} <= {str(row[0]) for row in rows}

    procedures = StoredProcedureService(signal_database).list_procedures()

    assert "sp_aqos_signal_status_counts" in procedures
    assert "sp_aqos_user_signal_summary" in procedures
    assert "sp_aqos_expire_due_signals" in procedures


def test_create_signal_persists_and_logs_creation(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal = create_signal(
            session,
            user_id,
            symbol=" xau usd ",
            confidence=0.72,
            entry_price=2300.0,
            stop_loss=2290.0,
            take_profit=2320.0,
            source=SignalSource.RULE_BASED,
            strategy_name="close_momentum",
            actor="strategy_engine",
        )
        signal_id = signal.signal_id

    with signal_database.read_session() as session:
        repository = TradingSignalRepository(session)
        stored = repository.require_signal(signal_id)

        assert stored.symbol == "XAUUSD"
        assert stored.status == SignalStatus.GENERATED
        assert float(stored.confidence) == pytest.approx(0.72)
        assert stored.strategy_name == "close_momentum"

        events = repository.list_events(signal_id)

        assert len(events) == 1
        assert events[0].is_creation is True
        assert events[0].to_status == SignalStatus.GENERATED
        assert events[0].actor == "strategy_engine"


def test_create_signal_rejects_a_terminal_start_status(
    signal_database,
    user_id,
) -> None:
    with pytest.raises(RepositoryError, match="cannot be created as executed"):
        with signal_database.session() as session:
            create_signal(session, user_id, status=SignalStatus.EXECUTED)


def test_create_signal_can_start_pending_approval(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal = create_signal(
            session,
            user_id,
            status=SignalStatus.PENDING_APPROVAL,
        )

        assert signal.status == SignalStatus.PENDING_APPROVAL


def test_model_signal_requires_traceability(signal_database, user_id) -> None:
    with pytest.raises(ValueError, match="model_id is required"):
        with signal_database.session() as session:
            create_signal(session, user_id, source=SignalSource.ML_MODEL)


def test_mysql_check_constraint_enforces_model_traceability(
    signal_database,
    user_id,
) -> None:
    """The database enforces model traceability, so bypassing Python still fails."""

    with pytest.raises(
        DatabaseError,
        match="ck_trading_signals_model_traceability",
    ):
        with signal_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO trading_signals ("
                    "signal_id, user_id, symbol, timeframe, action, status, "
                    "source, generated_at_utc, metadata_json) VALUES ("
                    ":signal_id, :user_id, 'XAUUSD', 'H1', 'buy', 'generated', "
                    "'ml_model', :generated_at, '{}')"
                ),
                {
                    "signal_id": "signal_bypass",
                    "user_id": user_id,
                    "generated_at": FIXED_NOW,
                },
            )


def test_mysql_check_constraint_enforces_expiry_ordering(
    signal_database,
    user_id,
) -> None:
    with pytest.raises(
        DatabaseError,
        match="ck_trading_signals_expiry_after_generation",
    ):
        with signal_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO trading_signals ("
                    "signal_id, user_id, symbol, timeframe, action, status, "
                    "source, generated_at_utc, expires_at_utc, metadata_json) "
                    "VALUES (:signal_id, :user_id, 'XAUUSD', 'H1', 'buy', "
                    "'generated', 'manual', :generated_at, :expires_at, '{}')"
                ),
                {
                    "signal_id": "signal_expiry",
                    "user_id": user_id,
                    "generated_at": FIXED_NOW,
                    "expires_at": datetime(2025, 12, 31),
                },
            )


def test_full_lifecycle_records_every_transition(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with signal_database.session() as session:
        repository = TradingSignalRepository(session)
        repository.mark_pending_approval(
            signal_id,
            actor="system",
            occurred_at_utc=datetime(2026, 1, 1, 0, 1, 0),
        )
        repository.approve_signal(
            signal_id,
            reason="Approved by trader.",
            actor="user",
            occurred_at_utc=datetime(2026, 1, 1, 0, 2, 0),
        )
        repository.mark_executed(
            signal_id,
            actor="paper_broker",
            occurred_at_utc=datetime(2026, 1, 1, 0, 3, 0),
        )

    with signal_database.read_session() as session:
        repository = TradingSignalRepository(session)
        stored = repository.require_signal(signal_id)

        assert stored.status == SignalStatus.EXECUTED
        assert stored.is_terminal is True
        assert stored.updated_at_utc == datetime(2026, 1, 1, 0, 3, 0)

        assert repository.build_status_history(signal_id) == (
            "generated",
            "pending_approval",
            "approved",
            "executed",
        )

        events = repository.list_events(signal_id)

        assert events[1].from_status == SignalStatus.GENERATED
        assert events[2].reason == "Approved by trader."
        assert events[3].actor == "paper_broker"


def test_rejected_signal_cannot_be_executed(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id
        TradingSignalRepository(session).reject_signal(
            signal_id,
            reason="Risk limit reached.",
        )

    with pytest.raises(
        InvalidSignalTransitionError,
        match="cannot move from rejected to executed",
    ):
        with signal_database.session() as session:
            TradingSignalRepository(session).mark_executed(signal_id)


def test_expired_signal_cannot_be_executed(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(
            session,
            user_id,
            expires_at_utc=datetime(2026, 1, 1, 0, 30, 0),
        ).signal_id

    with signal_database.session() as session:
        TradingSignalRepository(session).expire_due_signals(
            now_utc=datetime(2026, 1, 1, 1, 0, 0)
        )

    with pytest.raises(
        InvalidSignalTransitionError,
        match="cannot move from expired to executed",
    ):
        with signal_database.session() as session:
            TradingSignalRepository(session).mark_executed(signal_id)


def test_failed_signal_cannot_be_executed(signal_database, user_id) -> None:
    with signal_database.session() as session:
        repository = TradingSignalRepository(session)
        signal_id = create_signal(session, user_id).signal_id
        repository.approve_signal(signal_id)
        repository.mark_failed(signal_id, reason="Broker disconnected.")

    with pytest.raises(
        InvalidSignalTransitionError,
        match="cannot move from failed to executed",
    ):
        with signal_database.session() as session:
            TradingSignalRepository(session).mark_executed(signal_id)


def test_generated_signal_cannot_jump_to_executed(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(
        InvalidSignalTransitionError,
        match="cannot move from generated to executed",
    ):
        with signal_database.session() as session:
            TradingSignalRepository(session).mark_executed(signal_id)


def test_a_rejected_transition_leaves_no_audit_row(signal_database, user_id) -> None:
    """A refused transition must not appear in the audit trail."""

    with signal_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(InvalidSignalTransitionError):
        with signal_database.session() as session:
            TradingSignalRepository(session).mark_executed(signal_id)

    with signal_database.read_session() as session:
        repository = TradingSignalRepository(session)

        assert repository.require_signal(signal_id).status == SignalStatus.GENERATED
        assert repository.build_status_history(signal_id) == ("generated",)


def test_reject_and_miss_require_a_reason(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(ValueError, match="reason cannot be empty"):
        with signal_database.session() as session:
            TradingSignalRepository(session).reject_signal(signal_id, reason="  ")

    with pytest.raises(ValueError, match="reason cannot be empty"):
        with signal_database.session() as session:
            TradingSignalRepository(session).mark_missed(signal_id, reason="")


def test_cancel_signal(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id
        cancelled = TradingSignalRepository(session).cancel_signal(
            signal_id,
            reason="Superseded by a newer signal.",
        )

        assert cancelled.status == SignalStatus.CANCELLED
        assert cancelled.is_terminal is True


def test_require_signal_raises_when_missing(signal_database) -> None:
    with signal_database.read_session() as session:
        with pytest.raises(RecordNotFoundError, match="does not exist"):
            TradingSignalRepository(session).require_signal("signal_missing")


def test_list_signals_filters(signal_database, user_id) -> None:
    with signal_database.session() as session:
        account_id = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper One",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
        ).account_id

        create_signal(session, user_id, symbol="XAUUSD")
        create_signal(
            session,
            user_id,
            symbol="EURUSD",
            account_id=account_id,
            source=SignalSource.ML_MODEL,
            model_id="model_abc",
            generated_at_utc=datetime(2026, 1, 2),
        )
        rejected = create_signal(
            session,
            user_id,
            symbol="BTCUSD",
            generated_at_utc=datetime(2026, 1, 3),
        )
        TradingSignalRepository(session).reject_signal(
            rejected.signal_id,
            reason="Blocked symbol.",
        )

    with signal_database.read_session() as session:
        repository = TradingSignalRepository(session)

        assert len(repository.list_signals(user_id=user_id)) == 3
        assert len(repository.list_signals(symbol="eurusd")) == 1
        assert len(repository.list_signals(account_id=account_id)) == 1
        assert len(repository.list_signals(source=SignalSource.ML_MODEL)) == 1
        assert len(repository.list_signals(status=SignalStatus.REJECTED)) == 1
        assert len(
            repository.list_signals(generated_since_utc=datetime(2026, 1, 2))
        ) == 2
        assert len(repository.list_signals(limit=2)) == 2
        assert len(repository.list_open_signals(user_id=user_id)) == 2


def test_list_signals_is_ordered_by_generation_time(signal_database, user_id) -> None:
    with signal_database.session() as session:
        create_signal(
            session,
            user_id,
            symbol="BTCUSD",
            generated_at_utc=datetime(2026, 1, 3),
        )
        create_signal(session, user_id, symbol="XAUUSD", generated_at_utc=FIXED_NOW)

    with signal_database.read_session() as session:
        assert [
            signal.symbol
            for signal in TradingSignalRepository(session).list_signals()
        ] == ["XAUUSD", "BTCUSD"]


def test_count_by_status(signal_database, user_id) -> None:
    with signal_database.session() as session:
        first = create_signal(session, user_id, symbol="XAUUSD")
        create_signal(session, user_id, symbol="EURUSD")
        TradingSignalRepository(session).reject_signal(
            first.signal_id,
            reason="Risk.",
        )

    with signal_database.read_session() as session:
        counts = TradingSignalRepository(session).count_by_status(user_id=user_id)

    assert counts == {"generated": 1, "rejected": 1}


def test_expire_due_signals_in_python(signal_database, user_id) -> None:
    with signal_database.session() as session:
        expiring = create_signal(
            session,
            user_id,
            symbol="XAUUSD",
            expires_at_utc=datetime(2026, 1, 1, 0, 30, 0),
        ).signal_id
        still_valid = create_signal(
            session,
            user_id,
            symbol="EURUSD",
            expires_at_utc=datetime(2026, 1, 1, 6, 0, 0),
        ).signal_id
        no_expiry = create_signal(session, user_id, symbol="BTCUSD").signal_id

    with signal_database.session() as session:
        expired = TradingSignalRepository(session).expire_due_signals(
            now_utc=datetime(2026, 1, 1, 1, 0, 0)
        )

        assert [signal.signal_id for signal in expired] == [expiring]

    with signal_database.read_session() as session:
        repository = TradingSignalRepository(session)

        assert repository.require_signal(expiring).status == SignalStatus.EXPIRED
        assert repository.require_signal(still_valid).status == (
            SignalStatus.GENERATED
        )
        assert repository.require_signal(no_expiry).status == SignalStatus.GENERATED
        assert repository.build_status_history(expiring) == ("generated", "expired")


def test_expire_due_signals_skips_terminal_signals(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(
            session,
            user_id,
            expires_at_utc=datetime(2026, 1, 1, 0, 30, 0),
        ).signal_id
        TradingSignalRepository(session).reject_signal(signal_id, reason="Risk.")

    with signal_database.session() as session:
        assert TradingSignalRepository(session).expire_due_signals(
            now_utc=datetime(2026, 1, 1, 2, 0, 0)
        ) == ()

    with signal_database.read_session() as session:
        assert TradingSignalRepository(session).require_signal(
            signal_id
        ).status == SignalStatus.REJECTED


def test_expire_due_signals_stored_procedure_writes_audit_rows(
    signal_database,
    user_id,
) -> None:
    with signal_database.session() as session:
        expiring = create_signal(
            session,
            user_id,
            symbol="XAUUSD",
            expires_at_utc=datetime(2026, 1, 1, 0, 30, 0),
        ).signal_id
        create_signal(
            session,
            user_id,
            symbol="EURUSD",
            expires_at_utc=datetime(2026, 1, 1, 6, 0, 0),
        )

    result = StoredProcedureService(signal_database).call(
        "sp_aqos_expire_due_signals",
        parameters=(datetime(2026, 1, 1, 1, 0, 0), "expiry_job"),
        out_parameters=("expired",),
    )

    assert result.out_values["expired"] == 1

    with signal_database.read_session() as session:
        repository = TradingSignalRepository(session)

        assert repository.require_signal(expiring).status == SignalStatus.EXPIRED
        assert repository.build_status_history(expiring) == ("generated", "expired")
        assert repository.list_events(expiring)[-1].actor == "expiry_job"


def test_signal_status_counts_stored_procedure(signal_database, user_id) -> None:
    with signal_database.session() as session:
        first = create_signal(session, user_id, symbol="XAUUSD")
        create_signal(session, user_id, symbol="EURUSD")
        TradingSignalRepository(session).reject_signal(
            first.signal_id,
            reason="Risk.",
        )

    result = StoredProcedureService(signal_database).call_read_only(
        "sp_aqos_signal_status_counts",
        parameters=(user_id,),
    )

    counts = {row["status"]: row["total"] for row in result.rows}

    assert counts == {"generated": 1, "rejected": 1}


def test_user_signal_summary_stored_procedure(signal_database, user_id) -> None:
    with signal_database.session() as session:
        repository = TradingSignalRepository(session)

        executed = create_signal(
            session,
            user_id,
            symbol="XAUUSD",
            confidence=0.8,
            source=SignalSource.ML_MODEL,
            model_id="model_abc",
        ).signal_id
        repository.approve_signal(executed)
        repository.mark_executed(executed)

        rejected = create_signal(
            session,
            user_id,
            symbol="EURUSD",
            confidence=0.6,
            source=SignalSource.ML_MODEL,
            model_id="model_abc",
        ).signal_id
        repository.reject_signal(rejected, reason="Risk.")

        create_signal(session, user_id, symbol="BTCUSD", confidence=0.5)

    result = StoredProcedureService(signal_database).call_read_only(
        "sp_aqos_user_signal_summary",
        parameters=(user_id,),
    )

    summary = {row["source"]: row for row in result.rows}

    assert summary["ml_model"]["total"] == 2
    assert summary["ml_model"]["executed_total"] == 1
    assert summary["ml_model"]["rejected_total"] == 1
    assert float(summary["ml_model"]["average_confidence"]) == pytest.approx(0.7)
    assert summary["manual"]["total"] == 1


def test_deleting_a_signal_cascades_to_events(signal_database, user_id) -> None:
    with signal_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id
        TradingSignalRepository(session).approve_signal(signal_id)

    with signal_database.session() as session:
        assert TradingSignalRepository(session).delete_signal(signal_id) is True

    with signal_database.read_session() as session:
        repository = TradingSignalRepository(session)

        assert repository.get(signal_id) is None
        assert repository.list_events(signal_id) == ()


def test_deleting_a_user_cascades_to_signals(signal_database, user_id) -> None:
    with signal_database.session() as session:
        create_signal(session, user_id)

    with signal_database.session() as session:
        UserProfileRepository(session).delete_user(user_id)

    with signal_database.read_session() as session:
        assert TradingSignalRepository(session).list_signals(user_id=user_id) == ()


def test_deleting_an_account_detaches_signals(signal_database, user_id) -> None:
    with signal_database.session() as session:
        account_id = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper One",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
        ).account_id
        signal_id = create_signal(session, user_id, account_id=account_id).signal_id

    with signal_database.session() as session:
        TradingAccountRepository(session).delete_account(account_id)

    with signal_database.read_session() as session:
        assert TradingSignalRepository(session).require_signal(
            signal_id
        ).account_id is None


def test_rollback_leaves_no_signal_or_event(signal_database, user_id) -> None:
    with pytest.raises(RuntimeError, match="deliberate failure"):
        with signal_database.session() as session:
            create_signal(session, user_id, symbol="ROLLBACK")
            raise RuntimeError("deliberate failure")

    with signal_database.read_session() as session:
        assert TradingSignalRepository(session).list_signals(symbol="ROLLBACK") == ()

        rows = session.execute(text("SELECT COUNT(*) FROM signal_events")).first()

        assert rows[0] == 0
