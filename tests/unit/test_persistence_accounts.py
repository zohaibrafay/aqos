from __future__ import annotations

import pytest

from aqos.persistence.accounts import (
    AQOS_ACCOUNTS_VERSION,
    AccountStatus,
    AccountType,
    BrokerKind,
    TradingAccount,
    TradingAccountRepository,
    account_allows_execution,
    default_execution_mode_for_account,
    is_real_money_account,
    resolve_account_execution_mode,
)
from aqos.persistence.database import AqosDatabase
from aqos.persistence.trading_settings import (
    ExecutionMode,
    TradingSettingsRepository,
)
from aqos.persistence.users import UserProfileRepository


@pytest.fixture
def account_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def stored_user(account_database):
    return UserProfileRepository(account_database).create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def accounts(account_database) -> TradingAccountRepository:
    return TradingAccountRepository(account_database)


def build_account(**overrides) -> TradingAccount:
    payload = {
        "account_id": "account_1",
        "user_id": "user_1",
        "name": "Paper One",
        "account_type": AccountType.PAPER,
        "broker": BrokerKind.PAPER,
        "currency": "USD",
        "initial_balance": 10_000.0,
        "current_balance": 10_000.0,
        "equity": 10_000.0,
        "created_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)

    return TradingAccount(**payload)


def create_paper_account(
    accounts: TradingAccountRepository,
    user_id: str,
    name: str = "Paper One",
    **overrides,
):
    payload = {
        "user_id": user_id,
        "name": name,
        "account_type": AccountType.PAPER,
        "broker": BrokerKind.PAPER,
        "initial_balance": 10_000.0,
        "created_at_utc": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)

    return accounts.create_account(**payload)


def test_accounts_version_is_exposed() -> None:
    assert AQOS_ACCOUNTS_VERSION == "1.0"


def test_real_money_account_classification() -> None:
    assert is_real_money_account(AccountType.LIVE) is True
    assert is_real_money_account(AccountType.FUNDED) is True
    assert is_real_money_account(AccountType.PAPER) is False
    assert is_real_money_account(AccountType.DEMO) is False


def test_default_execution_mode_per_account_type() -> None:
    assert default_execution_mode_for_account(AccountType.LIVE) == (
        ExecutionMode.SIGNAL_ONLY
    )
    assert default_execution_mode_for_account(AccountType.FUNDED) == (
        ExecutionMode.SIGNAL_ONLY
    )
    assert default_execution_mode_for_account(AccountType.PAPER) == (
        ExecutionMode.MANUAL_APPROVAL
    )


def test_account_validation_rejects_bad_identity() -> None:
    with pytest.raises(ValueError, match="account_id cannot be empty"):
        build_account(account_id=" ")

    with pytest.raises(ValueError, match="user_id cannot be empty"):
        build_account(user_id="")

    with pytest.raises(ValueError, match="name cannot be empty"):
        build_account(name="   ")

    with pytest.raises(ValueError, match="created_at_utc cannot be empty"):
        build_account(created_at_utc=" ")


def test_account_validation_rejects_bad_numbers() -> None:
    with pytest.raises(ValueError, match="3 letter code"):
        build_account(currency="DOLLAR")

    with pytest.raises(ValueError, match="initial_balance must be positive"):
        build_account(initial_balance=0.0)

    with pytest.raises(ValueError, match="current_balance cannot be negative"):
        build_account(current_balance=-1.0)

    with pytest.raises(ValueError, match="equity cannot be negative"):
        build_account(equity=-1.0)

    with pytest.raises(ValueError, match="leverage must be at least 1"):
        build_account(leverage=0)


def test_auto_trade_requires_capability_flag() -> None:
    with pytest.raises(ValueError, match="auto_trade_enabled must be true"):
        build_account(execution_mode=ExecutionMode.AUTO_TRADE)

    account = build_account(
        execution_mode=ExecutionMode.AUTO_TRADE,
        auto_trade_enabled=True,
    )

    assert account.allows_orders() is True


def test_account_derived_values() -> None:
    account = build_account(current_balance=10_500.0, equity=10_800.0)

    assert account.open_pnl == pytest.approx(300.0)
    assert account.total_return_fraction == pytest.approx(0.08)
    assert account.is_tradable is True

    suspended = build_account(status=AccountStatus.SUSPENDED)

    assert suspended.is_tradable is False
    assert suspended.allows_orders() is False


def test_account_dict_payload() -> None:
    payload = build_account(
        execution_mode=ExecutionMode.MANUAL_APPROVAL,
    ).to_dict()

    assert payload["account_type"] == "paper"
    assert payload["broker"] == "paper"
    assert payload["is_real_money"] is False
    assert payload["allows_orders"] is True
    assert payload["open_pnl"] == 0.0


def test_resolve_account_execution_mode_uses_strictest() -> None:
    settings_repository_mode = ExecutionMode.MANUAL_APPROVAL

    class _Settings:
        execution_mode = settings_repository_mode

    account = build_account(
        execution_mode=ExecutionMode.AUTO_TRADE,
        auto_trade_enabled=True,
    )

    assert resolve_account_execution_mode(_Settings(), account) == (
        ExecutionMode.MANUAL_APPROVAL
    )


def test_resolve_account_execution_mode_disables_untradable_account() -> None:
    class _Settings:
        execution_mode = ExecutionMode.AUTO_TRADE

    account = build_account(status=AccountStatus.CLOSED)

    assert resolve_account_execution_mode(_Settings(), account) == (
        ExecutionMode.DISABLED
    )


def test_account_allows_execution(account_database, accounts, stored_user) -> None:
    settings = TradingSettingsRepository(account_database).create_settings(
        stored_user.user_id,
        execution_mode=ExecutionMode.MANUAL_APPROVAL,
    )

    tradable = create_paper_account(accounts, stored_user.user_id)
    signal_only = create_paper_account(
        accounts,
        stored_user.user_id,
        name="Signal Only",
        execution_mode=ExecutionMode.SIGNAL_ONLY,
    )

    assert account_allows_execution(settings, tradable) is True
    assert account_allows_execution(settings, signal_only) is False


def test_create_account_seeds_balances_and_default(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    assert account.account_id.startswith("account_")
    assert account.current_balance == 10_000.0
    assert account.equity == 10_000.0
    assert account.execution_mode == ExecutionMode.MANUAL_APPROVAL
    assert account.is_default is True

    stored = accounts.require_account(account.account_id)

    assert stored.to_dict() == account.to_dict()


def test_create_account_rejects_duplicate_name(accounts, stored_user) -> None:
    create_paper_account(accounts, stored_user.user_id)

    with pytest.raises(ValueError, match="Account name already exists"):
        create_paper_account(accounts, stored_user.user_id)


def test_create_live_account_defaults_to_signal_only(accounts, stored_user) -> None:
    account = accounts.create_account(
        user_id=stored_user.user_id,
        name="Live One",
        account_type=AccountType.LIVE,
        broker=BrokerKind.MT5,
        initial_balance=5_000.0,
    )

    assert account.execution_mode == ExecutionMode.SIGNAL_ONLY
    assert account.auto_trade_enabled is False
    assert account.is_real_money is True


def test_create_live_account_cannot_start_in_auto_trade(accounts, stored_user) -> None:
    with pytest.raises(ValueError, match="cannot be created in auto trade mode"):
        accounts.create_account(
            user_id=stored_user.user_id,
            name="Reckless Live",
            account_type=AccountType.LIVE,
            broker=BrokerKind.MT5,
            initial_balance=5_000.0,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
        )


def test_funded_account_cannot_start_in_auto_trade(accounts, stored_user) -> None:
    with pytest.raises(ValueError, match="cannot be created in auto trade mode"):
        accounts.create_account(
            user_id=stored_user.user_id,
            name="Reckless Funded",
            account_type=AccountType.FUNDED,
            broker=BrokerKind.MT5,
            initial_balance=100_000.0,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
        )


def test_get_account_returns_none_when_missing(accounts) -> None:
    assert accounts.get_account("account_missing") is None


def test_require_account_raises_when_missing(accounts) -> None:
    with pytest.raises(LookupError, match="does not exist"):
        accounts.require_account("account_missing")


def test_find_account_by_name(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    assert accounts.find_account_by_name(
        stored_user.user_id,
        " Paper One ",
    ).account_id == account.account_id
    assert accounts.find_account_by_name(stored_user.user_id, "Nope") is None


def test_first_account_becomes_default(accounts, stored_user) -> None:
    first = create_paper_account(accounts, stored_user.user_id, name="First")
    second = create_paper_account(accounts, stored_user.user_id, name="Second")

    assert accounts.get_default_account(stored_user.user_id).account_id == (
        first.account_id
    )
    assert second.is_default is False


def test_set_default_account_moves_the_flag(accounts, stored_user) -> None:
    first = create_paper_account(accounts, stored_user.user_id, name="First")
    second = create_paper_account(accounts, stored_user.user_id, name="Second")

    promoted = accounts.set_default_account(
        stored_user.user_id,
        second.account_id,
        updated_at_utc="2026-02-01T00:00:00Z",
    )

    assert promoted.is_default is True
    assert accounts.require_account(first.account_id).is_default is False
    assert accounts.get_default_account(stored_user.user_id).account_id == (
        second.account_id
    )


def test_set_default_account_rejects_foreign_account(
    account_database,
    accounts,
    stored_user,
) -> None:
    other_user = UserProfileRepository(account_database).create_user(
        email="other@example.com",
        display_name="Other",
    )
    account = create_paper_account(accounts, stored_user.user_id)

    with pytest.raises(ValueError, match="does not belong to this user"):
        accounts.set_default_account(other_user.user_id, account.account_id)


def test_list_accounts_filters(accounts, stored_user) -> None:
    create_paper_account(accounts, stored_user.user_id, name="Paper")
    accounts.create_account(
        user_id=stored_user.user_id,
        name="Demo",
        account_type=AccountType.DEMO,
        broker=BrokerKind.MT5,
        initial_balance=1_000.0,
        created_at_utc="2026-01-02T00:00:00Z",
    )
    accounts.create_account(
        user_id=stored_user.user_id,
        name="Closed Live",
        account_type=AccountType.LIVE,
        broker=BrokerKind.BINANCE,
        initial_balance=2_000.0,
        status=AccountStatus.CLOSED,
        created_at_utc="2026-01-03T00:00:00Z",
    )

    assert len(accounts.list_accounts(stored_user.user_id)) == 3
    assert len(
        accounts.list_accounts(stored_user.user_id, account_type=AccountType.DEMO)
    ) == 1
    assert len(
        accounts.list_accounts(stored_user.user_id, broker=BrokerKind.BINANCE)
    ) == 1
    assert len(accounts.list_tradable_accounts(stored_user.user_id)) == 2
    assert accounts.count_accounts(stored_user.user_id) == 3


def test_update_account_fields(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    updated = accounts.update_account(
        account.account_id,
        name="Renamed",
        status=AccountStatus.INACTIVE,
        leverage=30,
        broker_account_ref="mt5-12345",
        broker_credential_ref="vault://aqos/mt5/12345",
        metadata={"note": "moved"},
        updated_at_utc="2026-02-01T00:00:00Z",
    )

    assert updated.name == "Renamed"
    assert updated.status == AccountStatus.INACTIVE
    assert updated.leverage == 30
    assert updated.broker_account_ref == "mt5-12345"
    assert updated.broker_credential_ref == "vault://aqos/mt5/12345"
    assert updated.metadata == {"note": "moved"}
    assert updated.updated_at_utc == "2026-02-01T00:00:00Z"

    assert accounts.require_account(account.account_id).to_dict() == updated.to_dict()


def test_update_account_rejects_duplicate_name(accounts, stored_user) -> None:
    first = create_paper_account(accounts, stored_user.user_id, name="First")
    create_paper_account(accounts, stored_user.user_id, name="Second")

    with pytest.raises(ValueError, match="Account name already exists"):
        accounts.update_account(first.account_id, name="Second")


def test_update_account_allows_same_name(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    updated = accounts.update_account(account.account_id, name="Paper One")

    assert updated.name == "Paper One"


def test_update_account_blocks_auto_trade_without_capability(
    accounts,
    stored_user,
) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    with pytest.raises(ValueError, match="auto_trade_enabled must be true"):
        accounts.update_account(
            account.account_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
        )


def test_enable_then_switch_to_auto_trade(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    enabled = accounts.enable_auto_trade(account.account_id)

    assert enabled.auto_trade_enabled is True
    assert enabled.execution_mode == ExecutionMode.MANUAL_APPROVAL

    switched = accounts.update_account(
        account.account_id,
        execution_mode=ExecutionMode.AUTO_TRADE,
    )

    assert switched.execution_mode == ExecutionMode.AUTO_TRADE


def test_disable_auto_trade_downgrades_mode(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)
    accounts.enable_auto_trade(account.account_id)
    accounts.update_account(
        account.account_id,
        execution_mode=ExecutionMode.AUTO_TRADE,
    )

    disabled = accounts.disable_auto_trade(account.account_id)

    assert disabled.auto_trade_enabled is False
    assert disabled.execution_mode == ExecutionMode.MANUAL_APPROVAL


def test_disable_auto_trade_keeps_lower_modes(accounts, stored_user) -> None:
    account = create_paper_account(
        accounts,
        stored_user.user_id,
        execution_mode=ExecutionMode.SIGNAL_ONLY,
    )

    disabled = accounts.disable_auto_trade(account.account_id)

    assert disabled.execution_mode == ExecutionMode.SIGNAL_ONLY


def test_set_status(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    suspended = accounts.set_status(account.account_id, AccountStatus.SUSPENDED)

    assert suspended.status == AccountStatus.SUSPENDED
    assert suspended.is_tradable is False


def test_update_balances(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    updated = accounts.update_balances(
        account.account_id,
        current_balance=10_250.0,
        equity=10_400.0,
        updated_at_utc="2026-02-01T00:00:00Z",
    )

    assert updated.current_balance == 10_250.0
    assert updated.equity == 10_400.0
    assert updated.open_pnl == pytest.approx(150.0)

    stored = accounts.require_account(account.account_id)

    assert stored.equity == 10_400.0
    assert stored.updated_at_utc == "2026-02-01T00:00:00Z"


def test_update_balances_rejects_negative_values(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    with pytest.raises(ValueError, match="current_balance cannot be negative"):
        accounts.update_balances(account.account_id, current_balance=-1.0)


def test_delete_account(accounts, stored_user) -> None:
    account = create_paper_account(accounts, stored_user.user_id)

    assert accounts.delete_account(account.account_id) is True
    assert accounts.get_account(account.account_id) is None
    assert accounts.delete_account(account.account_id) is False


def test_deleting_user_cascades_to_accounts(
    account_database,
    accounts,
    stored_user,
) -> None:
    create_paper_account(accounts, stored_user.user_id)

    UserProfileRepository(account_database).delete_user(stored_user.user_id)

    assert accounts.list_accounts(stored_user.user_id) == ()


def test_accounts_are_isolated_per_user(account_database, accounts, stored_user) -> None:
    other_user = UserProfileRepository(account_database).create_user(
        email="other@example.com",
        display_name="Other",
    )

    create_paper_account(accounts, stored_user.user_id, name="Shared Name")
    create_paper_account(accounts, other_user.user_id, name="Shared Name")

    assert len(accounts.list_accounts(stored_user.user_id)) == 1
    assert len(accounts.list_accounts(other_user.user_id)) == 1
