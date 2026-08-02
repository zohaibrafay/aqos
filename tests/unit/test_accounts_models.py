from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from aqos.accounts.models import (
    AQOS_ACCOUNTS_VERSION,
    AUTO_TRADE_GUARDED_ACCOUNT_TYPES,
    AccountStatus,
    AccountType,
    BrokerKind,
    REAL_MONEY_ACCOUNT_TYPES,
    TradingAccount,
    as_amount,
    default_execution_mode_for_account,
    is_real_money_account,
    normalize_account_currency,
    normalize_account_name,
)
from aqos.execution_policy.modes import (
    ExecutionConstraintSource,
    ExecutionMode,
    resolve_execution_mode,
)
from aqos.trading_settings.models import TradingSettings


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_account(**overrides) -> TradingAccount:
    payload = {
        "account_id": "account_1",
        "user_id": "user_1",
        "name": "Paper One",
        "account_type": AccountType.PAPER,
        "broker": BrokerKind.PAPER,
        "status": AccountStatus.ACTIVE,
        "execution_mode": ExecutionMode.MANUAL_APPROVAL,
        "currency": "USD",
        "initial_balance": 10_000.0,
        "current_balance": 10_000.0,
        "equity": 10_000.0,
        "leverage": 1,
    }
    payload.update(overrides)

    return TradingAccount(**payload)


def build_settings(execution_mode: ExecutionMode) -> TradingSettings:
    return TradingSettings(
        settings_id="settings_1",
        user_id="user_1",
        execution_mode=execution_mode,
        risk_per_trade_fraction=0.01,
        max_daily_loss_fraction=0.05,
        max_open_positions=3,
        max_daily_trades=10,
        default_timeframe="H1",
    )


def test_accounts_version_is_exposed() -> None:
    assert AQOS_ACCOUNTS_VERSION == "1.0"


def test_account_type_and_broker_are_independent() -> None:
    """A live account can sit on MT5 or Binance; a paper account has no venue."""

    assert {item.value for item in AccountType} == {
        "paper",
        "demo",
        "live",
        "funded",
    }
    assert {item.value for item in BrokerKind} == {
        "paper",
        "mt5",
        "binance",
        "manual",
    }


def test_account_statuses_cover_the_required_set() -> None:
    assert {item.value for item in AccountStatus} == {
        "active",
        "disabled",
        "suspended",
        "archived",
    }


def test_real_money_classification() -> None:
    assert is_real_money_account(AccountType.LIVE) is True
    assert is_real_money_account(AccountType.FUNDED) is True
    assert is_real_money_account(AccountType.PAPER) is False
    assert is_real_money_account(AccountType.DEMO) is False
    assert AUTO_TRADE_GUARDED_ACCOUNT_TYPES == REAL_MONEY_ACCOUNT_TYPES


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
    assert default_execution_mode_for_account(AccountType.DEMO) == (
        ExecutionMode.MANUAL_APPROVAL
    )


def test_normalize_account_name() -> None:
    assert normalize_account_name("  Paper One  ") == "Paper One"

    with pytest.raises(ValueError, match="name cannot be empty"):
        normalize_account_name("   ")


def test_normalize_account_currency() -> None:
    assert normalize_account_currency(" usd ") == "USD"

    with pytest.raises(ValueError, match="3 letter code"):
        normalize_account_currency("DOLLARS")


def test_as_amount_handles_decimal() -> None:
    assert as_amount(Decimal("10000.00000000")) == pytest.approx(10_000.0)
    assert as_amount(1.5) == pytest.approx(1.5)


def test_account_validates_money_and_leverage() -> None:
    with pytest.raises(ValueError, match="initial_balance must be positive"):
        build_account(initial_balance=0.0)

    with pytest.raises(ValueError, match="current_balance cannot be negative"):
        build_account(current_balance=-1.0)

    with pytest.raises(ValueError, match="equity cannot be negative"):
        build_account(equity=-1.0)

    with pytest.raises(ValueError, match="leverage must be at least 1"):
        build_account(leverage=0)

    with pytest.raises(ValueError, match="name cannot be empty"):
        build_account(name="   ")

    with pytest.raises(ValueError, match="3 letter code"):
        build_account(currency="DOLLARS")


def test_auto_trade_requires_the_capability_flag() -> None:
    account = build_account(execution_mode=ExecutionMode.AUTO_TRADE)

    with pytest.raises(ValueError, match="auto_trade_enabled must be true"):
        account.validate_auto_trade_capability()

    enabled = build_account(
        execution_mode=ExecutionMode.AUTO_TRADE,
        auto_trade_enabled=True,
    )
    enabled.validate_auto_trade_capability()

    assert enabled.allows_orders is True


def test_capability_check_passes_for_lower_modes() -> None:
    build_account(execution_mode=ExecutionMode.SIGNAL_ONLY).validate_auto_trade_capability()
    build_account(
        execution_mode=ExecutionMode.MANUAL_APPROVAL
    ).validate_auto_trade_capability()


def test_account_money_derivations() -> None:
    account = build_account(current_balance=10_500.0, equity=10_800.0)

    assert account.balance == pytest.approx(10_500.0)
    assert account.account_equity == pytest.approx(10_800.0)
    assert account.open_pnl == pytest.approx(300.0)
    assert account.total_return_fraction == pytest.approx(0.08)


def test_only_active_accounts_are_tradable() -> None:
    assert build_account().is_tradable is True

    for status in (
        AccountStatus.DISABLED,
        AccountStatus.SUSPENDED,
        AccountStatus.ARCHIVED,
    ):
        account = build_account(status=status)

        assert account.is_tradable is False
        assert account.allows_orders is False


def test_execution_ceiling_uses_the_stored_mode_when_active() -> None:
    assert build_account(
        execution_mode=ExecutionMode.SIGNAL_ONLY
    ).execution_ceiling() == ExecutionMode.SIGNAL_ONLY

    assert build_account(
        execution_mode=ExecutionMode.AUTO_TRADE,
        auto_trade_enabled=True,
    ).execution_ceiling() == ExecutionMode.AUTO_TRADE


def test_non_active_account_ceiling_is_disabled() -> None:
    for status in (
        AccountStatus.DISABLED,
        AccountStatus.SUSPENDED,
        AccountStatus.ARCHIVED,
    ):
        account = build_account(
            status=status,
            execution_mode=ExecutionMode.AUTO_TRADE,
            auto_trade_enabled=True,
        )

        assert account.execution_ceiling() == ExecutionMode.DISABLED


def test_account_execution_constraint_payload() -> None:
    constraint = build_account(
        execution_mode=ExecutionMode.MANUAL_APPROVAL
    ).execution_constraint()

    assert constraint.source == ExecutionConstraintSource.ACCOUNT
    assert constraint.ceiling == ExecutionMode.MANUAL_APPROVAL
    assert "manual_approval" in (constraint.reason or "")


def test_suspended_account_constraint_explains_the_status() -> None:
    constraint = build_account(
        status=AccountStatus.SUSPENDED,
        execution_mode=ExecutionMode.AUTO_TRADE,
        auto_trade_enabled=True,
    ).execution_constraint()

    assert constraint.ceiling == ExecutionMode.DISABLED
    assert "suspended" in (constraint.reason or "")


def test_account_ceiling_combines_with_the_user_ceiling() -> None:
    """The scenario from the Sprint 042 brief."""

    settings = build_settings(ExecutionMode.MANUAL_APPROVAL)
    account = build_account(execution_mode=ExecutionMode.SIGNAL_ONLY)

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


def test_user_ceiling_binds_when_it_is_the_stricter_one() -> None:
    settings = build_settings(ExecutionMode.SIGNAL_ONLY)
    account = build_account(
        execution_mode=ExecutionMode.AUTO_TRADE,
        auto_trade_enabled=True,
    )

    decision = resolve_execution_mode(
        requested=ExecutionMode.AUTO_TRADE,
        constraints=(
            settings.execution_constraint(),
            account.execution_constraint(),
        ),
    )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY
    assert decision.binding_sources == ("user_settings",)


def test_suspended_account_disables_execution_entirely() -> None:
    settings = build_settings(ExecutionMode.AUTO_TRADE)
    account = build_account(
        status=AccountStatus.SUSPENDED,
        execution_mode=ExecutionMode.AUTO_TRADE,
        auto_trade_enabled=True,
    )

    decision = resolve_execution_mode(
        requested=ExecutionMode.AUTO_TRADE,
        constraints=(
            settings.execution_constraint(),
            account.execution_constraint(),
        ),
    )

    assert decision.effective == ExecutionMode.DISABLED
    assert decision.allows_orders is False
    assert decision.binding_sources == ("account",)


def test_both_ceilings_bind_when_equal() -> None:
    settings = build_settings(ExecutionMode.MANUAL_APPROVAL)
    account = build_account(execution_mode=ExecutionMode.MANUAL_APPROVAL)

    decision = resolve_execution_mode(
        requested=ExecutionMode.AUTO_TRADE,
        constraints=(
            settings.execution_constraint(),
            account.execution_constraint(),
        ),
    )

    assert decision.effective == ExecutionMode.MANUAL_APPROVAL
    assert set(decision.binding_sources) == {"user_settings", "account"}


def test_account_dict_payload() -> None:
    payload = build_account(
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
        extra_metadata={"origin": "unit_test"},
    ).to_dict()

    assert payload["account_type"] == "paper"
    assert payload["broker"] == "paper"
    assert payload["status"] == "active"
    assert payload["execution_mode"] == "manual_approval"
    assert payload["execution_ceiling"] == "manual_approval"
    assert payload["is_real_money"] is False
    assert payload["allows_orders"] is True
    assert payload["open_pnl"] == pytest.approx(0.0)
    assert payload["metadata"] == {"origin": "unit_test"}
    assert "account_1" in repr(build_account())


def test_archived_account_dict_reports_disabled_ceiling() -> None:
    payload = build_account(status=AccountStatus.ARCHIVED).to_dict()

    assert payload["execution_ceiling"] == "disabled"
    assert payload["is_tradable"] is False
    assert payload["allows_orders"] is False
