"""
Structured signal reasons against real MySQL 8.

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
from aqos.signals.models import (
    InvalidSignalTransitionError,
    SignalAction,
    SignalSource,
    SignalStatus,
)
from aqos.signals.repositories import TradingSignalRepository
from aqos.signal_reasons.repositories import (
    SignalReasonRepository,
    fail_signal_with_reason,
    miss_signal_with_reason,
    reject_signal_with_reason,
)
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonError,
    SignalReasonSeverity,
    default_reason_message,
)
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so structured signal reasons are "
            "NOT verified against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
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
def reason_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; reasons NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(reason_database) -> str:
    with reason_database.session() as session:
        return UserProfileRepository(session).create_user(
            email="trader@example.com",
            display_name="Primary Trader",
            created_at_utc=FIXED_NOW,
        ).user_id


@pytest.fixture
def account_id(reason_database, user_id) -> str:
    with reason_database.session() as session:
        return TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Paper One",
            account_type=AccountType.PAPER,
            broker=BrokerKind.INTERNAL_PAPER,
            initial_balance=10_000.0,
            created_at_utc=FIXED_NOW,
        ).account_id


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


def test_reason_table_and_procedures_exist(reason_database) -> None:
    with reason_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    assert "signal_reasons" in {str(row[0]) for row in rows}

    procedures = StoredProcedureService(reason_database).list_procedures()

    assert "sp_aqos_signal_reason_counts" in procedures
    assert "sp_aqos_rejected_missed_summary" in procedures
    assert "sp_aqos_account_rejection_summary" in procedures


def test_reject_with_reason_writes_status_event_and_reason(
    reason_database,
    user_id,
    account_id,
) -> None:
    """The reason complements the audit trail rather than replacing it."""

    with reason_database.session() as session:
        signal_id = create_signal(
            session,
            user_id,
            account_id=account_id,
        ).signal_id

    with reason_database.session() as session:
        signal, reason = reject_signal_with_reason(
            signals=TradingSignalRepository(session),
            reasons=SignalReasonRepository(session),
            signal_id=signal_id,
            reason_code=SignalReasonCode.RISK_LIMIT_EXCEEDED,
            message="Daily risk budget already used.",
            actor="risk_engine",
            occurred_at_utc=datetime(2026, 1, 1, 0, 5, 0),
        )

        assert signal.status == SignalStatus.REJECTED
        assert reason.severity == SignalReasonSeverity.BLOCKING

    with reason_database.read_session() as session:
        signals = TradingSignalRepository(session)
        reasons = SignalReasonRepository(session)

        stored_signal = signals.require_signal(signal_id)
        stored_reasons = reasons.list_reasons(signal_id=signal_id)

        assert stored_signal.status == SignalStatus.REJECTED
        assert signals.build_status_history(signal_id) == ("generated", "rejected")

        assert len(stored_reasons) == 1
        assert stored_reasons[0].reason_code == SignalReasonCode.RISK_LIMIT_EXCEEDED
        assert stored_reasons[0].reason_category == SignalReasonCategory.RISK
        assert stored_reasons[0].message == "Daily risk budget already used."
        assert stored_reasons[0].account_id == account_id
        assert stored_reasons[0].source == "risk_engine"
        assert stored_reasons[0].created_at_utc == datetime(2026, 1, 1, 0, 5, 0)


def test_reject_with_reason_uses_the_canonical_message(
    reason_database,
    user_id,
) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with reason_database.session() as session:
        signal, reason = reject_signal_with_reason(
            signals=TradingSignalRepository(session),
            reasons=SignalReasonRepository(session),
            signal_id=signal_id,
            reason_code=SignalReasonCode.SYMBOL_BLOCKED,
        )

        expected = default_reason_message(SignalReasonCode.SYMBOL_BLOCKED)

        assert reason.message == expected
        assert signal.status_reason == expected


def test_miss_with_reason(reason_database, user_id) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with reason_database.session() as session:
        signal, reason = miss_signal_with_reason(
            signals=TradingSignalRepository(session),
            reasons=SignalReasonRepository(session),
            signal_id=signal_id,
            reason_code=SignalReasonCode.APPROVAL_TIMEOUT,
        )

        assert signal.status == SignalStatus.MISSED
        assert reason.signal_status == SignalStatus.MISSED
        assert reason.reason_category == SignalReasonCategory.USER_ACTION


def test_fail_with_reason(reason_database, user_id) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id
        TradingSignalRepository(session).approve_signal(signal_id)

    with reason_database.session() as session:
        signal, reason = fail_signal_with_reason(
            signals=TradingSignalRepository(session),
            reasons=SignalReasonRepository(session),
            signal_id=signal_id,
            reason_code=SignalReasonCode.BROKER_DISCONNECTED,
        )

        assert signal.status == SignalStatus.FAILED
        assert reason.is_critical is True


def test_a_refused_transition_writes_no_reason(reason_database, user_id) -> None:
    """A reason must never describe a decision that did not happen."""

    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id
        TradingSignalRepository(session).reject_signal(signal_id, reason="Risk.")

    with pytest.raises(InvalidSignalTransitionError):
        with reason_database.session() as session:
            reject_signal_with_reason(
                signals=TradingSignalRepository(session),
                reasons=SignalReasonRepository(session),
                signal_id=signal_id,
                reason_code=SignalReasonCode.MANUAL_REJECTION,
            )

    with reason_database.read_session() as session:
        assert SignalReasonRepository(session).list_reasons(
            signal_id=signal_id
        ) == ()


def test_a_mismatched_reason_code_is_refused(reason_database, user_id) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(SignalReasonError, match="cannot explain status rejected"):
        with reason_database.session() as session:
            reject_signal_with_reason(
                signals=TradingSignalRepository(session),
                reasons=SignalReasonRepository(session),
                signal_id=signal_id,
                reason_code=SignalReasonCode.APPROVAL_TIMEOUT,
            )


def test_a_downgraded_severity_is_refused(reason_database, user_id) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(SignalReasonError, match="cannot be recorded below"):
        with reason_database.session() as session:
            reject_signal_with_reason(
                signals=TradingSignalRepository(session),
                reasons=SignalReasonRepository(session),
                signal_id=signal_id,
                reason_code=SignalReasonCode.FUNDED_RULE_BREACHED,
                severity=SignalReasonSeverity.INFO,
            )


def test_severity_can_be_escalated(reason_database, user_id) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with reason_database.session() as session:
        _, reason = reject_signal_with_reason(
            signals=TradingSignalRepository(session),
            reasons=SignalReasonRepository(session),
            signal_id=signal_id,
            reason_code=SignalReasonCode.MARKET_CLOSED,
            severity=SignalReasonSeverity.CRITICAL,
        )

        assert reason.severity == SignalReasonSeverity.CRITICAL


def test_mysql_check_constraint_rejects_a_blank_message(
    reason_database,
    user_id,
) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(DatabaseError, match="ck_signal_reasons_message_present"):
        with reason_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO signal_reasons ("
                    "reason_id, signal_id, user_id, signal_status, "
                    "reason_category, reason_code, severity, message, "
                    "created_at_utc, metadata_json) VALUES ("
                    ":reason_id, :signal_id, :user_id, 'rejected', 'risk', "
                    "'risk_limit_exceeded', 'blocking', '   ', :created_at, '{}')"
                ),
                {
                    "reason_id": "reason_blank",
                    "signal_id": signal_id,
                    "user_id": user_id,
                    "created_at": FIXED_NOW,
                },
            )


def test_mysql_check_constraint_rejects_a_non_reason_bearing_status(
    reason_database,
    user_id,
) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(DatabaseError, match="ck_signal_reasons_status_bearing"):
        with reason_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO signal_reasons ("
                    "reason_id, signal_id, user_id, signal_status, "
                    "reason_category, reason_code, severity, message, "
                    "created_at_utc, metadata_json) VALUES ("
                    ":reason_id, :signal_id, :user_id, 'executed', 'risk', "
                    "'risk_limit_exceeded', 'blocking', 'Nope', :created_at, '{}')"
                ),
                {
                    "reason_id": "reason_executed",
                    "signal_id": signal_id,
                    "user_id": user_id,
                    "created_at": FIXED_NOW,
                },
            )


def test_mysql_check_constraint_rejects_an_unknown_severity(
    reason_database,
    user_id,
) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(DatabaseError, match="ck_signal_reasons_severity_known"):
        with reason_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO signal_reasons ("
                    "reason_id, signal_id, user_id, signal_status, "
                    "reason_category, reason_code, severity, message, "
                    "created_at_utc, metadata_json) VALUES ("
                    ":reason_id, :signal_id, :user_id, 'rejected', 'risk', "
                    "'risk_limit_exceeded', 'whatever', 'Nope', :created_at, '{}')"
                ),
                {
                    "reason_id": "reason_severity",
                    "signal_id": signal_id,
                    "user_id": user_id,
                    "created_at": FIXED_NOW,
                },
            )


def test_one_signal_can_carry_a_reason_per_account(
    reason_database,
    user_id,
    account_id,
) -> None:
    """The same signal can be refused differently on different accounts."""

    with reason_database.session() as session:
        second_account = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Funded 100k",
            account_type=AccountType.FUNDED,
            broker=BrokerKind.MT5,
            initial_balance=100_000.0,
        ).account_id
        signal_id = create_signal(session, user_id).signal_id

    with reason_database.session() as session:
        reasons = SignalReasonRepository(session)
        reasons.record_reason(
            signal_id=signal_id,
            user_id=user_id,
            account_id=account_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
            created_at_utc=FIXED_NOW,
        )
        reasons.record_reason(
            signal_id=signal_id,
            user_id=user_id,
            account_id=second_account,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.FUNDED_RULE_BREACHED,
            created_at_utc=datetime(2026, 1, 1, 0, 1, 0),
        )

    with reason_database.read_session() as session:
        repository = SignalReasonRepository(session)

        assert len(repository.list_reasons(signal_id=signal_id)) == 2
        assert repository.list_reasons(account_id=account_id)[0].reason_code == (
            SignalReasonCode.SPREAD_TOO_HIGH
        )
        assert repository.list_reasons(account_id=second_account)[0].reason_code == (
            SignalReasonCode.FUNDED_RULE_BREACHED
        )


def test_list_reasons_filters(reason_database, user_id, account_id) -> None:
    with reason_database.session() as session:
        first = create_signal(session, user_id, symbol="XAUUSD").signal_id
        second = create_signal(session, user_id, symbol="EURUSD").signal_id

        reasons = SignalReasonRepository(session)
        reasons.record_reason(
            signal_id=first,
            user_id=user_id,
            account_id=account_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.RISK_LIMIT_EXCEEDED,
            created_at_utc=FIXED_NOW,
        )
        reasons.record_reason(
            signal_id=second,
            user_id=user_id,
            signal_status=SignalStatus.MISSED,
            reason_code=SignalReasonCode.SIGNAL_ARRIVED_LATE,
            created_at_utc=datetime(2026, 1, 2),
        )

    with reason_database.read_session() as session:
        repository = SignalReasonRepository(session)

        assert len(repository.list_reasons(user_id=user_id)) == 2
        assert len(repository.list_reasons(signal_status=SignalStatus.MISSED)) == 1
        assert len(
            repository.list_reasons(reason_code=SignalReasonCode.RISK_LIMIT_EXCEEDED)
        ) == 1
        assert len(
            repository.list_reasons(reason_category=SignalReasonCategory.RISK)
        ) == 1
        assert len(
            repository.list_reasons(severity=SignalReasonSeverity.BLOCKING)
        ) == 1
        assert len(
            repository.list_reasons(created_since_utc=datetime(2026, 1, 2))
        ) == 1
        assert len(repository.list_blocking_reasons(user_id=user_id)) == 1


def test_summarize_ranks_by_count(reason_database, user_id, account_id) -> None:
    with reason_database.session() as session:
        reasons = SignalReasonRepository(session)

        for index in range(3):
            signal_id = create_signal(
                session,
                user_id,
                symbol=f"SYM{index}",
            ).signal_id
            reasons.record_reason(
                signal_id=signal_id,
                user_id=user_id,
                account_id=account_id,
                signal_status=SignalStatus.REJECTED,
                reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
                created_at_utc=FIXED_NOW,
            )

        other = create_signal(session, user_id, symbol="OTHER").signal_id
        reasons.record_reason(
            signal_id=other,
            user_id=user_id,
            signal_status=SignalStatus.MISSED,
            reason_code=SignalReasonCode.BROKER_DISCONNECTED,
            created_at_utc=FIXED_NOW,
        )

    with reason_database.read_session() as session:
        summary = SignalReasonRepository(session).summarize(user_id=user_id)

    assert summary.total == 4
    assert summary.top_reason is not None
    assert summary.top_reason.reason_code == SignalReasonCode.SPREAD_TOO_HIGH
    assert summary.top_reason.count == 3
    assert summary.by_category == {"broker_unavailable": 1, "market_condition": 3}
    assert summary.by_status == {"missed": 1, "rejected": 3}
    assert summary.by_severity == {"critical": 1, "warning": 3}
    assert summary.blocking_total == 1

    payload = summary.to_dict()

    assert payload["total"] == 4
    assert payload["top_reason"]["reason_code"] == "spread_too_high"


def test_summarize_for_an_empty_store(reason_database, user_id) -> None:
    with reason_database.read_session() as session:
        summary = SignalReasonRepository(session).summarize(user_id=user_id)

    assert summary.total == 0
    assert summary.top_reason is None
    assert summary.by_category == {}
    assert summary.blocking_total == 0


def test_count_by_category(reason_database, user_id) -> None:
    with reason_database.session() as session:
        reasons = SignalReasonRepository(session)
        first = create_signal(session, user_id, symbol="XAUUSD").signal_id
        second = create_signal(session, user_id, symbol="EURUSD").signal_id

        reasons.record_reason(
            signal_id=first,
            user_id=user_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.RISK_LIMIT_EXCEEDED,
        )
        reasons.record_reason(
            signal_id=second,
            user_id=user_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.ACCOUNT_DISABLED,
        )

    with reason_database.read_session() as session:
        counts = SignalReasonRepository(session).count_by_category(user_id=user_id)

    assert counts == {"account_rule": 1, "risk": 1}


def test_signal_reason_counts_stored_procedure(reason_database, user_id) -> None:
    with reason_database.session() as session:
        reasons = SignalReasonRepository(session)
        first = create_signal(session, user_id, symbol="XAUUSD").signal_id
        second = create_signal(session, user_id, symbol="EURUSD").signal_id

        reasons.record_reason(
            signal_id=first,
            user_id=user_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.FUNDED_RULE_BREACHED,
        )
        reasons.record_reason(
            signal_id=second,
            user_id=user_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.RISK_LIMIT_EXCEEDED,
        )

    result = StoredProcedureService(reason_database).call_read_only(
        "sp_aqos_signal_reason_counts",
        parameters=(user_id,),
    )

    rows = {row["reason_category"]: row for row in result.rows}

    assert rows["funded_rule"]["critical_total"] == 1
    assert rows["risk"]["blocking_total"] == 1


def test_rejected_missed_summary_stored_procedure(reason_database, user_id) -> None:
    with reason_database.session() as session:
        reasons = SignalReasonRepository(session)

        for index in range(2):
            signal_id = create_signal(
                session,
                user_id,
                symbol=f"SYM{index}",
            ).signal_id
            reasons.record_reason(
                signal_id=signal_id,
                user_id=user_id,
                signal_status=SignalStatus.REJECTED,
                reason_code=SignalReasonCode.SYMBOL_BLOCKED,
            )

        missed = create_signal(session, user_id, symbol="MISS").signal_id
        reasons.record_reason(
            signal_id=missed,
            user_id=user_id,
            signal_status=SignalStatus.MISSED,
            reason_code=SignalReasonCode.APPROVAL_TIMEOUT,
        )

    result = StoredProcedureService(reason_database).call_read_only(
        "sp_aqos_rejected_missed_summary",
        parameters=(user_id,),
    )

    assert result.rows[0]["reason_code"] == "symbol_blocked"
    assert result.rows[0]["total"] == 2
    assert {row["signal_status"] for row in result.rows} == {"rejected", "missed"}


def test_account_rejection_summary_stored_procedure(
    reason_database,
    user_id,
    account_id,
) -> None:
    with reason_database.session() as session:
        reasons = SignalReasonRepository(session)

        for index in range(2):
            signal_id = create_signal(
                session,
                user_id,
                symbol=f"SYM{index}",
            ).signal_id
            reasons.record_reason(
                signal_id=signal_id,
                user_id=user_id,
                account_id=account_id,
                signal_status=SignalStatus.REJECTED,
                reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
                created_at_utc=datetime(2026, 1, 1, index, 0, 0),
            )

    result = StoredProcedureService(reason_database).call_read_only(
        "sp_aqos_account_rejection_summary",
        parameters=(account_id,),
    )

    assert result.rows[0]["reason_code"] == "spread_too_high"
    assert result.rows[0]["total"] == 2
    assert result.rows[0]["last_seen_at_utc"] == datetime(2026, 1, 1, 1, 0, 0)


def test_deleting_a_signal_cascades_to_reasons(reason_database, user_id) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id
        SignalReasonRepository(session).record_reason(
            signal_id=signal_id,
            user_id=user_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.MANUAL_REJECTION,
        )

    with reason_database.session() as session:
        TradingSignalRepository(session).delete_signal(signal_id)

    with reason_database.read_session() as session:
        assert SignalReasonRepository(session).list_reasons(
            signal_id=signal_id
        ) == ()


def test_deleting_an_account_detaches_reasons(
    reason_database,
    user_id,
    account_id,
) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id
        reason_id = SignalReasonRepository(session).record_reason(
            signal_id=signal_id,
            user_id=user_id,
            account_id=account_id,
            signal_status=SignalStatus.REJECTED,
            reason_code=SignalReasonCode.SPREAD_TOO_HIGH,
        ).reason_id

    with reason_database.session() as session:
        TradingAccountRepository(session).delete_account(account_id)

    with reason_database.read_session() as session:
        assert SignalReasonRepository(session).require(reason_id).account_id is None


def test_rollback_leaves_no_reason_or_status_change(
    reason_database,
    user_id,
) -> None:
    with reason_database.session() as session:
        signal_id = create_signal(session, user_id).signal_id

    with pytest.raises(RuntimeError, match="deliberate failure"):
        with reason_database.session() as session:
            reject_signal_with_reason(
                signals=TradingSignalRepository(session),
                reasons=SignalReasonRepository(session),
                signal_id=signal_id,
                reason_code=SignalReasonCode.MANUAL_REJECTION,
            )
            raise RuntimeError("deliberate failure")

    with reason_database.read_session() as session:
        signals = TradingSignalRepository(session)

        assert signals.require_signal(signal_id).status == SignalStatus.GENERATED
        assert signals.build_status_history(signal_id) == ("generated",)
        assert SignalReasonRepository(session).list_reasons(
            signal_id=signal_id
        ) == ()
