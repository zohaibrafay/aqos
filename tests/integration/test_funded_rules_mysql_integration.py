"""
Funded rule templates and account rule assignments against real MySQL 8.

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
from aqos.database.repository import RepositoryError
from aqos.execution_policy.modes import ExecutionMode, resolve_execution_mode
from aqos.funded_rules.evaluation import FundedAccountState, FundedTradeRequest
from aqos.funded_rules.models import DrawdownBasis, FundedRuleStatus
from aqos.funded_rules.repositories import (
    FundedAccountRulesRepository,
    FundedRuleTemplateRepository,
)
from aqos.trading_settings.repositories import TradingSettingsRepository
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so funded account rules are NOT "
            "verified against MySQL by this run. Run them with:\n"
            "  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:3306/"
            "aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
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
def funded_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; funded rules NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def funded_account(funded_database) -> tuple[str, str]:
    """Return ``(user_id, account_id)`` for a funded MT5 account."""

    with funded_database.session() as session:
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


def build_state(**overrides) -> FundedAccountState:
    payload = {
        "initial_balance": 100_000.0,
        "current_balance": 100_000.0,
        "equity": 100_000.0,
    }
    payload.update(overrides)

    return FundedAccountState(**payload)


def test_funded_tables_and_procedures_exist(funded_database) -> None:
    with funded_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    assert {"funded_rule_templates", "funded_account_rules"} <= {
        str(row[0]) for row in rows
    }

    procedures = StoredProcedureService(funded_database).list_procedures()

    assert "sp_aqos_funded_account_summary" in procedures
    assert "sp_aqos_funded_rule_template_usage" in procedures


def test_create_template_round_trip(funded_database) -> None:
    with funded_database.session() as session:
        template = FundedRuleTemplateRepository(session).create_template(
            name="Conservative 100k",
            description="Configurable limits",
            max_daily_loss_fraction=0.03,
            max_total_drawdown_fraction=0.06,
            profit_target_fraction=0.08,
            max_lot_size=2.0,
            min_trading_days=10,
            allowed_symbols=["xauusd", "EURUSD"],
            created_at_utc=FIXED_NOW,
        )
        template_id = template.template_id

    with funded_database.read_session() as session:
        stored = FundedRuleTemplateRepository(session).require_template(template_id)

        assert stored.name == "Conservative 100k"
        assert float(stored.max_daily_loss_fraction) == pytest.approx(0.03)
        assert float(stored.max_lot_size) == pytest.approx(2.0)
        assert stored.min_trading_days == 10
        assert stored.allowed_symbols == ["XAUUSD", "EURUSD"]
        assert stored.is_active is True


def test_template_names_are_unique(funded_database) -> None:
    with funded_database.session() as session:
        FundedRuleTemplateRepository(session).create_template(name="Standard")

    with pytest.raises(RepositoryError, match="template name already exists"):
        with funded_database.session() as session:
            FundedRuleTemplateRepository(session).create_template(name="Standard")


def test_template_update_and_deactivate(funded_database) -> None:
    with funded_database.session() as session:
        template_id = FundedRuleTemplateRepository(session).create_template(
            name="Standard",
            created_at_utc=FIXED_NOW,
        ).template_id

    with funded_database.session() as session:
        updated = FundedRuleTemplateRepository(session).update_template(
            template_id,
            description="Updated",
            max_open_positions=5,
            is_active=False,
            updated_at_utc=datetime(2026, 2, 1),
        )

        assert updated.max_open_positions == 5
        assert updated.is_active is False

    with funded_database.read_session() as session:
        repository = FundedRuleTemplateRepository(session)

        assert len(repository.list_templates()) == 1
        assert repository.list_templates(active_only=True) == ()


def test_template_update_rejects_unknown_field(funded_database) -> None:
    with funded_database.session() as session:
        template_id = FundedRuleTemplateRepository(session).create_template(
            name="Standard",
        ).template_id

    with pytest.raises(RepositoryError, match="has no field named"):
        with funded_database.session() as session:
            FundedRuleTemplateRepository(session).update_template(
                template_id,
                not_a_field=1,
            )


def test_assign_rules_copies_template_values(funded_database, funded_account) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        template = FundedRuleTemplateRepository(session).create_template(
            name="Conservative 100k",
            max_daily_loss_fraction=0.03,
            max_total_drawdown_fraction=0.06,
            max_lot_size=2.0,
            allowed_symbols=["XAUUSD"],
            created_at_utc=FIXED_NOW,
        )
        template_id = template.template_id

        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            template=template,
            created_at_utc=FIXED_NOW,
        )

    with funded_database.read_session() as session:
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        assert rules.template_id == template_id
        assert float(rules.max_daily_loss_fraction) == pytest.approx(0.03)
        assert float(rules.max_lot_size) == pytest.approx(2.0)
        assert rules.allowed_symbols == ["XAUUSD"]
        assert rules.status == FundedRuleStatus.ACTIVE


def test_editing_a_template_does_not_change_assigned_rules(
    funded_database,
    funded_account,
) -> None:
    """Values are copied at assignment, so live accounts never shift under a user."""

    _, account_id = funded_account

    with funded_database.session() as session:
        template = FundedRuleTemplateRepository(session).create_template(
            name="Standard",
            max_daily_loss_fraction=0.05,
        )
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            template=template,
        )
        template_id = template.template_id

    with funded_database.session() as session:
        FundedRuleTemplateRepository(session).update_template(
            template_id,
            max_daily_loss_fraction=0.01,
        )

    with funded_database.read_session() as session:
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        assert float(rules.max_daily_loss_fraction) == pytest.approx(0.05)


def test_assign_rules_without_a_template_uses_defaults(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        rules = FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            created_at_utc=FIXED_NOW,
        )

        assert rules.template_id is None
        assert rules.news_restriction_enabled is True
        assert rules.execution_mode == ExecutionMode.SIGNAL_ONLY


def test_assign_rules_rejects_an_inactive_template(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        template = FundedRuleTemplateRepository(session).create_template(
            name="Retired",
            is_active=False,
        )

        with pytest.raises(RepositoryError, match="template is not active"):
            FundedAccountRulesRepository(session).assign_rules(
                account_id=account_id,
                template=template,
            )


def test_assign_rules_rejects_a_duplicate_assignment(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    with pytest.raises(RepositoryError, match="already exist"):
        with funded_database.session() as session:
            FundedAccountRulesRepository(session).assign_rules(account_id=account_id)


def test_mysql_check_constraint_rejects_daily_loss_above_drawdown(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with pytest.raises(
        DatabaseError,
        match="ck_funded_account_rules_daily_within_drawdown",
    ):
        with funded_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO funded_account_rules ("
                    "rules_id, account_id, status, execution_mode, "
                    "max_daily_loss_fraction, max_total_drawdown_fraction, "
                    "drawdown_basis, profit_target_fraction, "
                    "max_risk_per_trade_fraction, min_lot_size, max_lot_size, "
                    "max_open_positions, max_daily_trades, min_trading_days, "
                    "allowed_symbols, metadata_json) VALUES ("
                    ":rules_id, :account_id, 'active', 'signal_only', "
                    "0.200000, 0.100000, 'static_initial', 0.100000, 0.010000, "
                    "0.0100, 5.0000, 1, 1, 0, '[]', '{}')"
                ),
                {"rules_id": "rules_bypass", "account_id": account_id},
            )


def test_mysql_check_constraint_requires_a_breach_timestamp(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with pytest.raises(
        DatabaseError,
        match="ck_funded_account_rules_breach_timestamp",
    ):
        with funded_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO funded_account_rules ("
                    "rules_id, account_id, status, execution_mode, "
                    "max_daily_loss_fraction, max_total_drawdown_fraction, "
                    "drawdown_basis, profit_target_fraction, "
                    "max_risk_per_trade_fraction, min_lot_size, max_lot_size, "
                    "max_open_positions, max_daily_trades, min_trading_days, "
                    "allowed_symbols, metadata_json) VALUES ("
                    ":rules_id, :account_id, 'breached', 'signal_only', "
                    "0.050000, 0.100000, 'static_initial', 0.100000, 0.010000, "
                    "0.0100, 5.0000, 1, 1, 0, '[]', '{}')"
                ),
                {"rules_id": "rules_breach", "account_id": account_id},
            )


def test_three_ceilings_resolve_through_the_database(
    funded_database,
    funded_account,
) -> None:
    """requested=auto_trade, user=auto_trade, account=manual_approval, funded=signal_only."""

    user_id, account_id = funded_account

    with funded_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
        )
        TradingAccountRepository(session).update_account(
            account_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
        )
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            execution_mode=ExecutionMode.SIGNAL_ONLY,
        )

    with funded_database.read_session() as session:
        settings = TradingSettingsRepository(session).require_for_user(user_id)
        account = TradingAccountRepository(session).require_account(account_id)
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        decision = resolve_execution_mode(
            requested=ExecutionMode.AUTO_TRADE,
            constraints=(
                settings.execution_constraint(),
                account.execution_constraint(),
                rules.execution_constraint(),
            ),
        )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY
    assert decision.binding_sources == ("funded_rule",)
    assert (
        decision.explain()
        == "Execution mode downgraded from auto_trade to signal_only by: "
        "funded_rule=signal_only"
    )


def test_breached_rules_disable_execution_through_the_database(
    funded_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account

    with funded_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
        )
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
        )

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).mark_breached(
            account_id,
            reason="Maximum daily loss exceeded.",
            breached_at_utc=FIXED_NOW,
        )

    with funded_database.read_session() as session:
        settings = TradingSettingsRepository(session).require_for_user(user_id)
        account = TradingAccountRepository(session).require_account(account_id)
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        decision = resolve_execution_mode(
            requested=ExecutionMode.AUTO_TRADE,
            constraints=(
                settings.execution_constraint(),
                account.execution_constraint(),
                rules.execution_constraint(),
            ),
        )

    assert rules.status == FundedRuleStatus.BREACHED
    assert rules.breached_at_utc == FIXED_NOW
    assert decision.effective == ExecutionMode.DISABLED
    assert decision.allows_orders is False
    assert decision.binding_sources == ("funded_rule",)


def test_disabled_rules_disable_execution_through_the_database(
    funded_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account

    with funded_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
        )
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
        )

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).set_status(
            account_id,
            FundedRuleStatus.DISABLED,
        )

    with funded_database.read_session() as session:
        settings = TradingSettingsRepository(session).require_for_user(user_id)
        account = TradingAccountRepository(session).require_account(account_id)
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        decision = resolve_execution_mode(
            requested=ExecutionMode.MANUAL_APPROVAL,
            constraints=(
                settings.execution_constraint(),
                account.execution_constraint(),
                rules.execution_constraint(),
            ),
        )

    assert decision.effective == ExecutionMode.DISABLED
    assert decision.binding_sources == ("funded_rule",)


def test_evaluate_and_record_persists_a_breach(funded_database, funded_account) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            max_total_drawdown_fraction=0.10,
        )

    with funded_database.session() as session:
        evaluation = FundedAccountRulesRepository(session).evaluate_and_record(
            account_id=account_id,
            state=build_state(equity=88_000.0),
            occurred_at_utc=FIXED_NOW,
        )

        assert evaluation.passed is False

    with funded_database.read_session() as session:
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        assert rules.status == FundedRuleStatus.BREACHED
        assert rules.breached_at_utc == FIXED_NOW
        assert "drawdown" in (rules.breach_reason or "").lower()
        assert rules.execution_ceiling() == ExecutionMode.DISABLED


def test_evaluate_and_record_leaves_compliant_rules_active(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    with funded_database.session() as session:
        evaluation = FundedAccountRulesRepository(session).evaluate_and_record(
            account_id=account_id,
            state=build_state(equity=101_000.0),
            request=FundedTradeRequest(
                symbol="XAUUSD",
                lot_size=1.0,
                risk_fraction=0.005,
            ),
        )

        assert evaluation.passed is True

    with funded_database.read_session() as session:
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        assert rules.status == FundedRuleStatus.ACTIVE


def test_status_transitions_clear_the_breach_record(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    with funded_database.session() as session:
        repository = FundedAccountRulesRepository(session)
        repository.mark_breached(account_id, reason="Breach", breached_at_utc=FIXED_NOW)

    with funded_database.session() as session:
        restored = FundedAccountRulesRepository(session).set_status(
            account_id,
            FundedRuleStatus.ACTIVE,
        )

        assert restored.breached_at_utc is None
        assert restored.breach_reason is None
        assert restored.execution_ceiling() == ExecutionMode.SIGNAL_ONLY


def test_mark_breached_requires_a_reason(funded_database, funded_account) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    with pytest.raises(RepositoryError, match="breach reason is required"):
        with funded_database.session() as session:
            FundedAccountRulesRepository(session).mark_breached(account_id, reason=" ")


def test_update_rules_round_trip(funded_database, funded_account) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            created_at_utc=FIXED_NOW,
        )

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).update_rules(
            account_id,
            drawdown_basis=DrawdownBasis.TRAILING_EQUITY,
            max_open_positions=1,
            weekend_holding_allowed=True,
            allowed_symbols=["XAUUSD"],
            metadata={"provider": "configured"},
            updated_at_utc=datetime(2026, 2, 1),
        )

    with funded_database.read_session() as session:
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        assert rules.drawdown_basis == DrawdownBasis.TRAILING_EQUITY
        assert rules.max_open_positions == 1
        assert rules.weekend_holding_allowed is True
        assert rules.allowed_symbols == ["XAUUSD"]
        assert rules.extra_metadata == {"provider": "configured"}


def test_update_rules_still_validates(funded_database, funded_account) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    with pytest.raises(ValueError, match="cannot exceed max_total_drawdown_fraction"):
        with funded_database.session() as session:
            FundedAccountRulesRepository(session).update_rules(
                account_id,
                max_daily_loss_fraction=0.5,
            )


def test_list_rules_filters(funded_database, funded_account) -> None:
    user_id, account_id = funded_account

    with funded_database.session() as session:
        second_account = TradingAccountRepository(session).create_account(
            user_id=user_id,
            name="Funded 50k",
            account_type=AccountType.FUNDED,
            broker=BrokerKind.MT5,
            initial_balance=50_000.0,
        ).account_id

        repository = FundedAccountRulesRepository(session)
        repository.assign_rules(account_id=account_id, created_at_utc=FIXED_NOW)
        repository.assign_rules(
            account_id=second_account,
            created_at_utc=datetime(2026, 1, 2),
        )
        repository.mark_breached(second_account, reason="Breach")

    with funded_database.read_session() as session:
        repository = FundedAccountRulesRepository(session)

        assert len(repository.list_rules()) == 2
        assert len(repository.list_rules(status=FundedRuleStatus.BREACHED)) == 1
        assert len(repository.list_rules(status=FundedRuleStatus.ACTIVE)) == 1


def test_funded_account_summary_stored_procedure(
    funded_database,
    funded_account,
) -> None:
    user_id, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    result = StoredProcedureService(funded_database).call_read_only(
        "sp_aqos_funded_account_summary",
        parameters=(user_id,),
    )

    summary = {row["status"]: row for row in result.rows}

    assert summary["active"]["total"] == 1
    assert summary["active"]["active_account_total"] == 1
    assert float(summary["active"]["total_equity"]) == pytest.approx(100_000.0)


def test_template_usage_stored_procedure(funded_database, funded_account) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        template = FundedRuleTemplateRepository(session).create_template(
            name="Standard",
        )
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            template=template,
        )

    result = StoredProcedureService(funded_database).call_read_only(
        "sp_aqos_funded_rule_template_usage"
    )

    rows = {row["name"]: row for row in result.rows}

    assert rows["Standard"]["assigned_accounts"] == 1


def test_deleting_an_account_cascades_to_rules(
    funded_database,
    funded_account,
) -> None:
    _, account_id = funded_account

    with funded_database.session() as session:
        FundedAccountRulesRepository(session).assign_rules(account_id=account_id)

    with funded_database.session() as session:
        TradingAccountRepository(session).delete_account(account_id)

    with funded_database.read_session() as session:
        assert FundedAccountRulesRepository(session).get_for_account(
            account_id
        ) is None


def test_deleting_a_template_keeps_assigned_rules(
    funded_database,
    funded_account,
) -> None:
    """Rules survive template deletion because their values were copied."""

    _, account_id = funded_account

    with funded_database.session() as session:
        template = FundedRuleTemplateRepository(session).create_template(
            name="Standard",
            max_daily_loss_fraction=0.02,
        )
        FundedAccountRulesRepository(session).assign_rules(
            account_id=account_id,
            template=template,
        )
        template_id = template.template_id

    with funded_database.session() as session:
        FundedRuleTemplateRepository(session).delete_template(template_id)

    with funded_database.read_session() as session:
        rules = FundedAccountRulesRepository(session).require_for_account(account_id)

        assert rules.template_id is None
        assert float(rules.max_daily_loss_fraction) == pytest.approx(0.02)
