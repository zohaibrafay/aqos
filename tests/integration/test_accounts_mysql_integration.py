"""
Trading account repositories against real MySQL 8.

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

from aqos.accounts.models import (
    AccountStatus,
    AccountType,
    BrokerKind,
    TradingAccount,
)
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.database.repository import RecordNotFoundError, RepositoryError
from aqos.execution_policy.modes import ExecutionMode, resolve_execution_mode
from aqos.trading_settings.repositories import TradingSettingsRepository
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so trading accounts are NOT verified "
            "against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
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
def account_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; accounts NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(account_database) -> str:
    with account_database.session() as session:
        return UserProfileRepository(session).create_user(
            email="trader@example.com",
            display_name="Primary Trader",
            created_at_utc=FIXED_NOW,
        ).user_id


def create_paper_account(session, user_id: str, name: str = "Paper One", **overrides):
    payload = {
        "user_id": user_id,
        "name": name,
        "account_type": AccountType.PAPER,
        "broker": BrokerKind.PAPER,
        "initial_balance": 10_000.0,
        "created_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return TradingAccountRepository(session).create_account(**payload)


def test_account_table_and_procedures_exist(account_database) -> None:
    with account_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    assert "trading_accounts" in {str(row[0]) for row in rows}

    procedures = StoredProcedureService(account_database).list_procedures()

    assert "sp_aqos_account_status_counts" in procedures
    assert "sp_aqos_account_type_summary" in procedures


def test_create_account_seeds_balances_and_default(account_database, user_id) -> None:
    with account_database.session() as session:
        account = create_paper_account(session, user_id)
        account_id = account.account_id

        assert account.is_default is True

    with account_database.read_session() as session:
        stored = TradingAccountRepository(session).require_account(account_id)

        assert stored.balance == pytest.approx(10_000.0)
        assert stored.account_equity == pytest.approx(10_000.0)
        assert stored.execution_mode == ExecutionMode.MANUAL_APPROVAL
        assert stored.status == AccountStatus.ACTIVE
        assert stored.currency == "USD"


def test_duplicate_account_name_is_rejected(account_database, user_id) -> None:
    with account_database.session() as session:
        create_paper_account(session, user_id)

    with pytest.raises(RepositoryError, match="Account name already exists"):
        with account_database.session() as session:
            create_paper_account(session, user_id)


def test_account_names_are_isolated_per_user(account_database, user_id) -> None:
    with account_database.session() as session:
        other = UserProfileRepository(session).create_user(
            email="other@example.com",
            display_name="Other",
        ).user_id

        create_paper_account(session, user_id, name="Shared Name")
        create_paper_account(session, other, name="Shared Name")

    with account_database.read_session() as session:
        repository = TradingAccountRepository(session)

        assert len(repository.list_accounts(user_id)) == 1
        assert len(repository.list_accounts(other)) == 1


def test_live_account_defaults_to_signal_only(account_database, user_id) -> None:
    with account_database.session() as session:
        account = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Live One",
            account_type=AccountType.LIVE,
            broker=BrokerKind.MT5,
            initial_balance=5_000.0,
        )

        assert account.execution_mode == ExecutionMode.SIGNAL_ONLY
        assert account.auto_trade_enabled is False
        assert account.is_real_money is True


def test_live_account_cannot_be_created_auto_trading(account_database, user_id) -> None:
    with pytest.raises(RepositoryError, match="cannot be created in auto trade mode"):
        with account_database.session() as session:
            TradingAccountRepository(session).create_account(
                user_id=user_id,
                name="Reckless Live",
                account_type=AccountType.LIVE,
                broker=BrokerKind.MT5,
                initial_balance=5_000.0,
                execution_mode=ExecutionMode.AUTO_TRADE,
                auto_trade_enabled=True,
            )


def test_funded_account_cannot_be_created_auto_trading(
    account_database,
    user_id,
) -> None:
    with pytest.raises(RepositoryError, match="cannot be created in auto trade mode"):
        with account_database.session() as session:
            TradingAccountRepository(session).create_account(
                user_id=user_id,
                name="Reckless Funded",
                account_type=AccountType.FUNDED,
                broker=BrokerKind.MT5,
                initial_balance=100_000.0,
                execution_mode=ExecutionMode.AUTO_TRADE,
                auto_trade_enabled=True,
            )


def test_auto_trade_without_capability_is_rejected(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id

    with pytest.raises(ValueError, match="auto_trade_enabled must be true"):
        with account_database.session() as session:
            TradingAccountRepository(session).update_account(
                account_id,
                execution_mode=ExecutionMode.AUTO_TRADE,
            )


def test_mysql_check_constraint_blocks_auto_trade_without_capability(
    account_database,
    user_id,
) -> None:
    """The database enforces the capability rail, so bypassing Python still fails."""

    with pytest.raises(
        DatabaseError,
        match="ck_trading_accounts_auto_trade_requires_capability",
    ):
        with account_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO trading_accounts ("
                    "account_id, user_id, name, account_type, broker, status, "
                    "execution_mode, auto_trade_enabled, is_default, currency, "
                    "initial_balance, current_balance, equity, leverage, "
                    "metadata_json) VALUES ("
                    ":account_id, :user_id, 'Bypass', 'live', 'mt5', 'active', "
                    "'auto_trade', 0, 0, 'USD', 1000, 1000, 1000, 1, '{}')"
                ),
                {"account_id": "account_bypass", "user_id": user_id},
            )


def test_mysql_check_constraint_blocks_non_positive_initial_balance(
    account_database,
    user_id,
) -> None:
    with pytest.raises(
        DatabaseError,
        match="ck_trading_accounts_initial_balance",
    ):
        with account_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO trading_accounts ("
                    "account_id, user_id, name, account_type, broker, status, "
                    "execution_mode, auto_trade_enabled, is_default, currency, "
                    "initial_balance, current_balance, equity, leverage, "
                    "metadata_json) VALUES ("
                    ":account_id, :user_id, 'Zero', 'paper', 'paper', 'active', "
                    "'signal_only', 0, 0, 'USD', 0, 0, 0, 1, '{}')"
                ),
                {"account_id": "account_zero", "user_id": user_id},
            )


def test_enable_then_switch_to_auto_trade(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id

    with account_database.session() as session:
        enabled = TradingAccountRepository(session).enable_auto_trade(account_id)

        assert enabled.auto_trade_enabled is True
        assert enabled.execution_mode == ExecutionMode.MANUAL_APPROVAL

    with account_database.session() as session:
        switched = TradingAccountRepository(session).update_account(
            account_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
        )

        assert switched.execution_mode == ExecutionMode.AUTO_TRADE


def test_disable_auto_trade_downgrades_the_mode(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id
        repository = TradingAccountRepository(session)
        repository.enable_auto_trade(account_id)
        repository.update_account(account_id, execution_mode=ExecutionMode.AUTO_TRADE)

    with account_database.session() as session:
        disabled = TradingAccountRepository(session).disable_auto_trade(account_id)

        assert disabled.auto_trade_enabled is False
        assert disabled.execution_mode == ExecutionMode.MANUAL_APPROVAL


def test_disable_auto_trade_keeps_lower_modes(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(
            session,
            user_id,
            execution_mode=ExecutionMode.SIGNAL_ONLY,
        ).account_id

    with account_database.session() as session:
        disabled = TradingAccountRepository(session).disable_auto_trade(account_id)

        assert disabled.execution_mode == ExecutionMode.SIGNAL_ONLY


def test_first_account_becomes_default_and_can_be_moved(
    account_database,
    user_id,
) -> None:
    with account_database.session() as session:
        first = create_paper_account(session, user_id, name="First").account_id
        second = create_paper_account(session, user_id, name="Second").account_id

    with account_database.read_session() as session:
        assert TradingAccountRepository(session).get_default_account(
            user_id
        ).account_id == first

    with account_database.session() as session:
        TradingAccountRepository(session).set_default_account(user_id, second)

    with account_database.read_session() as session:
        repository = TradingAccountRepository(session)

        assert repository.get_default_account(user_id).account_id == second
        assert repository.require_account(first).is_default is False


def test_set_default_rejects_a_foreign_account(account_database, user_id) -> None:
    with account_database.session() as session:
        other = UserProfileRepository(session).create_user(
            email="other@example.com",
            display_name="Other",
        ).user_id
        account_id = create_paper_account(session, user_id).account_id

    with pytest.raises(RepositoryError, match="does not belong to this user"):
        with account_database.session() as session:
            TradingAccountRepository(session).set_default_account(other, account_id)


def test_list_accounts_filters(account_database, user_id) -> None:
    with account_database.session() as session:
        repository = TradingAccountRepository(session)
        create_paper_account(session, user_id, name="Paper")
        repository.create_account(
            user_id=user_id,
            name="Demo",
            account_type=AccountType.DEMO,
            broker=BrokerKind.MT5,
            initial_balance=1_000.0,
            created_at_utc=datetime(2026, 1, 2),
        )
        repository.create_account(
            user_id=user_id,
            name="Archived Live",
            account_type=AccountType.LIVE,
            broker=BrokerKind.BINANCE,
            initial_balance=2_000.0,
            status=AccountStatus.ARCHIVED,
            created_at_utc=datetime(2026, 1, 3),
        )

    with account_database.read_session() as session:
        repository = TradingAccountRepository(session)

        assert len(repository.list_accounts(user_id)) == 3
        assert len(
            repository.list_accounts(user_id, account_type=AccountType.DEMO)
        ) == 1
        assert len(
            repository.list_accounts(user_id, broker=BrokerKind.BINANCE)
        ) == 1
        assert len(repository.list_tradable_accounts(user_id)) == 2
        assert repository.count_accounts(user_id) == 3


def test_update_account_fields(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id

    with account_database.session() as session:
        TradingAccountRepository(session).update_account(
            account_id,
            name="Renamed",
            status=AccountStatus.DISABLED,
            leverage=30,
            broker_account_ref="mt5-12345",
            broker_credential_ref="vault://aqos/mt5/12345",
            metadata={"note": "moved"},
            updated_at_utc=datetime(2026, 2, 1),
        )

    with account_database.read_session() as session:
        stored = TradingAccountRepository(session).require_account(account_id)

        assert stored.name == "Renamed"
        assert stored.status == AccountStatus.DISABLED
        assert stored.leverage == 30
        assert stored.broker_account_ref == "mt5-12345"
        assert stored.broker_credential_ref == "vault://aqos/mt5/12345"
        assert stored.extra_metadata == {"note": "moved"}
        assert stored.updated_at_utc == datetime(2026, 2, 1)


def test_update_rejects_a_duplicate_name(account_database, user_id) -> None:
    with account_database.session() as session:
        first = create_paper_account(session, user_id, name="First").account_id
        create_paper_account(session, user_id, name="Second")

    with pytest.raises(RepositoryError, match="Account name already exists"):
        with account_database.session() as session:
            TradingAccountRepository(session).update_account(first, name="Second")


def test_update_balances(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id

    with account_database.session() as session:
        updated = TradingAccountRepository(session).update_balances(
            account_id,
            current_balance=10_250.0,
            equity=10_400.0,
            updated_at_utc=datetime(2026, 2, 1),
        )

        assert updated.open_pnl == pytest.approx(150.0)

    with account_database.read_session() as session:
        stored = TradingAccountRepository(session).require_account(account_id)

        assert stored.account_equity == pytest.approx(10_400.0)


def test_update_balances_rejects_negative_values(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id

    with pytest.raises(ValueError, match="current_balance cannot be negative"):
        with account_database.session() as session:
            TradingAccountRepository(session).update_balances(
                account_id,
                current_balance=-1.0,
            )


def test_require_account_raises_when_missing(account_database) -> None:
    with account_database.read_session() as session:
        with pytest.raises(RecordNotFoundError, match="does not exist"):
            TradingAccountRepository(session).require_account("account_missing")


def test_set_status_blocks_execution(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id

    with account_database.session() as session:
        suspended = TradingAccountRepository(session).set_status(
            account_id,
            AccountStatus.SUSPENDED,
        )

        assert suspended.is_tradable is False
        assert suspended.execution_ceiling() == ExecutionMode.DISABLED


def test_account_and_user_ceilings_resolve_together(account_database, user_id) -> None:
    """requested=auto_trade, user=manual_approval, account=signal_only."""

    with account_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
        )
        create_paper_account(
            session,
            user_id,
            execution_mode=ExecutionMode.SIGNAL_ONLY,
        )

    with account_database.read_session() as session:
        settings = TradingSettingsRepository(session).require_for_user(user_id)
        account = TradingAccountRepository(session).list_accounts(user_id)[0]

        decision = resolve_execution_mode(
            requested=ExecutionMode.AUTO_TRADE,
            constraints=(
                settings.execution_constraint(),
                account.execution_constraint(),
            ),
        )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY
    assert decision.was_downgraded is True
    assert decision.allows_orders is False
    assert decision.binding_sources == ("account",)
    assert "account=signal_only" in decision.explain()


def test_suspended_account_disables_execution_end_to_end(
    account_database,
    user_id,
) -> None:
    with account_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
        )
        account_id = create_paper_account(session, user_id).account_id
        TradingAccountRepository(session).set_status(
            account_id,
            AccountStatus.SUSPENDED,
        )

    with account_database.read_session() as session:
        settings = TradingSettingsRepository(session).require_for_user(user_id)
        account = TradingAccountRepository(session).require_account(account_id)

        decision = resolve_execution_mode(
            requested=ExecutionMode.MANUAL_APPROVAL,
            constraints=(
                settings.execution_constraint(),
                account.execution_constraint(),
            ),
        )

    assert decision.effective == ExecutionMode.DISABLED
    assert decision.binding_sources == ("account",)


def test_account_status_counts_stored_procedure(account_database, user_id) -> None:
    with account_database.session() as session:
        repository = TradingAccountRepository(session)
        create_paper_account(session, user_id, name="Active One")
        second = create_paper_account(session, user_id, name="Suspended One")
        repository.set_status(second.account_id, AccountStatus.SUSPENDED)

    result = StoredProcedureService(account_database).call_read_only(
        "sp_aqos_account_status_counts",
        parameters=(user_id,),
    )

    counts = {row["status"]: row["total"] for row in result.rows}

    assert counts == {"active": 1, "suspended": 1}


def test_account_type_summary_stored_procedure(account_database, user_id) -> None:
    with account_database.session() as session:
        create_paper_account(session, user_id, name="Paper One")
        TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Live One",
            account_type=AccountType.LIVE,
            broker=BrokerKind.MT5,
            initial_balance=5_000.0,
        )

    result = StoredProcedureService(account_database).call_read_only(
        "sp_aqos_account_type_summary",
        parameters=(user_id,),
    )

    summary = {row["account_type"]: row for row in result.rows}

    assert set(summary) == {"paper", "live"}
    assert summary["paper"]["total"] == 1
    assert summary["paper"]["active_total"] == 1
    assert summary["live"]["auto_trade_total"] == 0
    assert float(summary["live"]["total_equity"]) == pytest.approx(5_000.0)


def test_delete_account(account_database, user_id) -> None:
    with account_database.session() as session:
        account_id = create_paper_account(session, user_id).account_id

    with account_database.session() as session:
        assert TradingAccountRepository(session).delete_account(account_id) is True

    with account_database.session() as session:
        assert TradingAccountRepository(session).delete_account(account_id) is False


def test_deleting_a_user_cascades_to_accounts(account_database, user_id) -> None:
    with account_database.session() as session:
        create_paper_account(session, user_id)

    with account_database.session() as session:
        UserProfileRepository(session).delete_user(user_id)

    with account_database.read_session() as session:
        assert TradingAccountRepository(session).list_accounts(user_id) == ()


def test_rollback_leaves_no_partial_account(account_database, user_id) -> None:
    with pytest.raises(RuntimeError, match="deliberate failure"):
        with account_database.session() as session:
            create_paper_account(session, user_id, name="Rollback")
            raise RuntimeError("deliberate failure")

    with account_database.read_session() as session:
        assert TradingAccountRepository(session).find_by_name(
            user_id,
            "Rollback",
        ) is None
