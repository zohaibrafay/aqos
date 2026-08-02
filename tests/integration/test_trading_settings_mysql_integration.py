"""
Trading settings and symbol preference repositories against real MySQL 8.

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

from aqos.database.config import parse_database_url
from aqos.database.engine import AqosDatabase
from aqos.database.migration_runner import apply_migrations
from aqos.database.procedures import StoredProcedureService
from aqos.database.repository import RepositoryError
from aqos.execution_policy.modes import (
    ExecutionConstraint,
    ExecutionConstraintSource,
    ExecutionMode,
    resolve_execution_mode,
)
from aqos.trading_settings.models import SymbolPreferenceKind
from aqos.trading_settings.repositories import (
    SymbolPreferenceRepository,
    TradingSettingsRepository,
)
from aqos.users.repositories import UserProfileRepository


ENV_TEST_DB_URL = "AQOS_TEST_DB_URL"

FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

pytestmark = pytest.mark.mysql


def requires_mysql() -> str:
    url = os.environ.get(ENV_TEST_DB_URL, "").strip()

    if not url:
        pytest.skip(
            f"{ENV_TEST_DB_URL} is not set, so trading settings and symbol "
            "preferences are NOT verified against MySQL by this run. Run them "
            "with:\n  AQOS_TEST_DB_URL=mysql+pymysql://user:password@localhost:"
            "3306/aqos_test pytest -m mysql"
        )

    return url


def reset_tables(database: AqosDatabase) -> None:
    with database.session() as session:
        session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))

        for table in (
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
def settings_database() -> AqosDatabase:
    url = requires_mysql()
    database = AqosDatabase(config=parse_database_url(url))

    if not database.ping():
        database.dispose()
        pytest.skip("MySQL server is not reachable; settings NOT verified.")

    apply_migrations(database)
    reset_tables(database)

    yield database

    reset_tables(database)
    database.dispose()


@pytest.fixture
def user_id(settings_database) -> str:
    with settings_database.session() as session:
        profile = UserProfileRepository(session).create_user(
            email="trader@example.com",
            display_name="Primary Trader",
            created_at_utc=FIXED_NOW,
        )

        return profile.user_id


def test_tables_and_procedures_exist(settings_database) -> None:
    with settings_database.read_session() as session:
        rows = session.execute(
            text(
                "SELECT TABLE_NAME FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = DATABASE()"
            )
        ).all()

    assert {"trading_settings", "symbol_preferences"} <= {
        str(row[0]) for row in rows
    }

    procedures = StoredProcedureService(settings_database).list_procedures()

    assert "sp_aqos_symbol_preference_counts" in procedures
    assert "sp_aqos_tradable_symbols" in procedures


def test_get_or_create_settings_is_idempotent(settings_database, user_id) -> None:
    with settings_database.session() as session:
        first = TradingSettingsRepository(session).get_or_create_for_user(
            user_id,
            created_at_utc=FIXED_NOW,
        )
        settings_id = first.settings_id

    with settings_database.session() as session:
        second = TradingSettingsRepository(session).get_or_create_for_user(user_id)

        assert second.settings_id == settings_id
        assert second.execution_mode == ExecutionMode.SIGNAL_ONLY


def test_create_settings_round_trip(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
            risk_per_trade_fraction=0.02,
            max_daily_loss_fraction=0.08,
            max_open_positions=5,
            max_daily_trades=25,
            default_timeframe="M15",
            allow_short=False,
            allow_hedging=True,
            notifications_enabled=False,
            metadata={"origin": "integration"},
            created_at_utc=FIXED_NOW,
        )

    with settings_database.read_session() as session:
        stored = TradingSettingsRepository(session).require_for_user(user_id)

        assert stored.execution_mode == ExecutionMode.MANUAL_APPROVAL
        assert stored.risk_per_trade == pytest.approx(0.02)
        assert stored.max_daily_loss == pytest.approx(0.08)
        assert stored.max_open_positions == 5
        assert stored.default_timeframe == "M15"
        assert stored.allow_short is False
        assert stored.allow_hedging is True
        assert stored.notifications_enabled is False
        assert stored.extra_metadata == {"origin": "integration"}


def test_duplicate_settings_are_rejected(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).create_for_user(user_id)

    with pytest.raises(RepositoryError, match="already exist"):
        with settings_database.session() as session:
            TradingSettingsRepository(session).create_for_user(user_id)


def test_require_settings_raises_when_missing(settings_database, user_id) -> None:
    with settings_database.read_session() as session:
        with pytest.raises(RepositoryError, match="do not exist"):
            TradingSettingsRepository(session).require_for_user(user_id)


def test_update_settings_round_trip(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).get_or_create_for_user(
            user_id,
            created_at_utc=FIXED_NOW,
        )

    with settings_database.session() as session:
        TradingSettingsRepository(session).update_for_user(
            user_id,
            execution_mode=ExecutionMode.AUTO_TRADE,
            risk_per_trade_fraction=0.005,
            max_open_positions=2,
            allow_hedging=True,
            metadata={"reviewed": True},
            updated_at_utc=datetime(2026, 2, 1),
        )

    with settings_database.read_session() as session:
        stored = TradingSettingsRepository(session).require_for_user(user_id)

        assert stored.execution_mode == ExecutionMode.AUTO_TRADE
        assert stored.risk_per_trade == pytest.approx(0.005)
        assert stored.max_open_positions == 2
        assert stored.updated_at_utc == datetime(2026, 2, 1)
        assert stored.extra_metadata == {"reviewed": True}


def test_update_keeps_unspecified_fields(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            max_daily_trades=7,
        )

    with settings_database.session() as session:
        updated = TradingSettingsRepository(session).update_for_user(
            user_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
        )

        assert updated.max_daily_trades == 7
        assert updated.default_timeframe == "H1"


def test_python_rejects_inconsistent_risk_limits(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).get_or_create_for_user(user_id)

    with pytest.raises(ValueError, match="max_daily_loss_fraction cannot be smaller"):
        with settings_database.session() as session:
            TradingSettingsRepository(session).update_for_user(
                user_id,
                risk_per_trade_fraction=0.9,
            )


def test_mysql_check_constraint_rejects_inconsistent_risk_limits(
    settings_database,
    user_id,
) -> None:
    """The database enforces the same rule, so bypassing Python still fails."""

    with pytest.raises(
        DatabaseError,
        match="ck_trading_settings_daily_loss_covers_trade_risk",
    ):
        with settings_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO trading_settings ("
                    "settings_id, user_id, execution_mode, "
                    "risk_per_trade_fraction, max_daily_loss_fraction, "
                    "max_open_positions, max_daily_trades, default_timeframe, "
                    "metadata_json) VALUES ("
                    ":settings_id, :user_id, 'signal_only', 0.900000, 0.100000, "
                    "1, 1, 'H1', '{}')"
                ),
                {"settings_id": "settings_bypass", "user_id": user_id},
            )


def test_mysql_check_constraint_rejects_zero_risk(
    settings_database,
    user_id,
) -> None:
    with pytest.raises(
        DatabaseError,
        match="ck_trading_settings_risk_per_trade_range",
    ):
        with settings_database.session() as session:
            session.execute(
                text(
                    "INSERT INTO trading_settings ("
                    "settings_id, user_id, execution_mode, "
                    "risk_per_trade_fraction, max_daily_loss_fraction, "
                    "max_open_positions, max_daily_trades, default_timeframe, "
                    "metadata_json) VALUES ("
                    ":settings_id, :user_id, 'signal_only', 0.000000, 0.100000, "
                    "1, 1, 'H1', '{}')"
                ),
                {"settings_id": "settings_zero", "user_id": user_id},
            )


def test_set_execution_mode_and_reset(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).get_or_create_for_user(
            user_id,
            created_at_utc=FIXED_NOW,
        )

    with settings_database.session() as session:
        disabled = TradingSettingsRepository(session).set_execution_mode(
            user_id,
            ExecutionMode.DISABLED,
        )

        assert disabled.allows_orders is False

    with settings_database.session() as session:
        reset = TradingSettingsRepository(session).reset_for_user(user_id)

        assert reset.execution_mode == ExecutionMode.SIGNAL_ONLY
        assert reset.max_open_positions == 3
        assert reset.extra_metadata == {}


def test_list_settings_filters_by_execution_mode(settings_database) -> None:
    with settings_database.session() as session:
        users = UserProfileRepository(session)
        first = users.create_user(
            email="a@example.com",
            display_name="A",
            created_at_utc=FIXED_NOW,
        ).user_id
        second = users.create_user(
            email="b@example.com",
            display_name="B",
            created_at_utc=datetime(2026, 1, 2),
        ).user_id

        settings = TradingSettingsRepository(session)
        settings.create_for_user(first, created_at_utc=FIXED_NOW)
        settings.create_for_user(
            second,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
            created_at_utc=datetime(2026, 1, 2),
        )

    with settings_database.read_session() as session:
        repository = TradingSettingsRepository(session)

        assert len(repository.list_settings()) == 2
        assert [
            item.user_id
            for item in repository.list_settings(
                execution_mode=ExecutionMode.MANUAL_APPROVAL
            )
        ] == [second]


def test_user_constraint_resolves_against_a_later_account_ceiling(
    settings_database,
    user_id,
) -> None:
    """
    The user ceiling is one input; 042 adds the account ceiling.

    Here the account ceiling is supplied directly to prove the resolver already
    combines sources correctly before accounts exist.
    """

    with settings_database.session() as session:
        TradingSettingsRepository(session).create_for_user(
            user_id,
            execution_mode=ExecutionMode.MANUAL_APPROVAL,
        )

    with settings_database.read_session() as session:
        settings = TradingSettingsRepository(session).require_for_user(user_id)

        decision = resolve_execution_mode(
            requested=ExecutionMode.AUTO_TRADE,
            constraints=(
                settings.execution_constraint(),
                ExecutionConstraint(
                    source=ExecutionConstraintSource.ACCOUNT,
                    ceiling=ExecutionMode.AUTO_TRADE,
                ),
            ),
        )

    assert decision.effective == ExecutionMode.MANUAL_APPROVAL
    assert decision.binding_sources == ("user_settings",)
    assert decision.requires_manual_approval is True


def test_delete_settings(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).get_or_create_for_user(user_id)

    with settings_database.session() as session:
        repository = TradingSettingsRepository(session)

        assert repository.delete_for_user(user_id) is True
        assert repository.delete_for_user(user_id) is False


def test_deleting_a_user_cascades_to_settings(settings_database, user_id) -> None:
    with settings_database.session() as session:
        TradingSettingsRepository(session).get_or_create_for_user(user_id)
        SymbolPreferenceRepository(session).add_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.WATCHLIST,
        )

    with settings_database.session() as session:
        UserProfileRepository(session).delete_user(user_id)

    with settings_database.read_session() as session:
        assert TradingSettingsRepository(session).get_for_user(user_id) is None
        assert SymbolPreferenceRepository(session).list_preferences(user_id) == ()


def test_add_symbol_normalizes_and_is_idempotent(settings_database, user_id) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)

        first = repository.add_symbol(
            user_id,
            " xau usd ",
            SymbolPreferenceKind.WATCHLIST,
            created_at_utc=FIXED_NOW,
        )
        second = repository.add_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.WATCHLIST,
        )

        assert first.symbol == "XAUUSD"
        assert second.preference_id == first.preference_id

    with settings_database.read_session() as session:
        assert SymbolPreferenceRepository(session).list_symbols(
            user_id,
            SymbolPreferenceKind.WATCHLIST,
        ) == ("XAUUSD",)


def test_same_symbol_can_sit_on_several_lists(settings_database, user_id) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.PREFERRED)

    with settings_database.read_session() as session:
        repository = SymbolPreferenceRepository(session)

        assert repository.has_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.WATCHLIST,
        ) is True
        assert repository.has_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.PREFERRED,
        ) is True


def test_blocking_clears_preferred_and_notification(
    settings_database,
    user_id,
) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.PREFERRED)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.NOTIFICATION)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.BLOCKED)

    with settings_database.read_session() as session:
        repository = SymbolPreferenceRepository(session)

        assert repository.is_blocked(user_id, "XAUUSD") is True
        assert repository.has_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.PREFERRED,
        ) is False
        assert repository.has_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.NOTIFICATION,
        ) is False
        assert repository.has_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.WATCHLIST,
        ) is True


def test_set_symbols_replaces_a_list(settings_database, user_id) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.set_symbols(
            user_id,
            SymbolPreferenceKind.WATCHLIST,
            ["XAUUSD", "EURUSD"],
        )

    with settings_database.session() as session:
        replaced = SymbolPreferenceRepository(session).set_symbols(
            user_id,
            SymbolPreferenceKind.WATCHLIST,
            ["btcusd", "BTCUSD", " ethusd "],
        )

        assert replaced == ("BTCUSD", "ETHUSD")


def test_set_blocked_symbols_clears_dependent_lists(
    settings_database,
    user_id,
) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.set_symbols(
            user_id,
            SymbolPreferenceKind.NOTIFICATION,
            ["XAUUSD", "EURUSD"],
        )

    with settings_database.session() as session:
        SymbolPreferenceRepository(session).set_symbols(
            user_id,
            SymbolPreferenceKind.BLOCKED,
            ["XAUUSD"],
        )

    with settings_database.read_session() as session:
        assert SymbolPreferenceRepository(session).list_symbols(
            user_id,
            SymbolPreferenceKind.NOTIFICATION,
        ) == ("EURUSD",)


def test_remove_and_clear_symbols(settings_database, user_id) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
        repository.add_symbol(user_id, "BTCUSD", SymbolPreferenceKind.BLOCKED)

    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)

        assert repository.remove_symbol(
            user_id,
            "xauusd",
            SymbolPreferenceKind.WATCHLIST,
        ) is True
        assert repository.remove_symbol(
            user_id,
            "XAUUSD",
            SymbolPreferenceKind.WATCHLIST,
        ) is False

    with settings_database.session() as session:
        assert SymbolPreferenceRepository(session).clear_symbols(user_id) == 1


def test_symbol_allowance_and_notification_rules(
    settings_database,
    user_id,
) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.add_symbol(user_id, "XAUUSD", SymbolPreferenceKind.NOTIFICATION)
        repository.add_symbol(user_id, "BTCUSD", SymbolPreferenceKind.BLOCKED)

    with settings_database.read_session() as session:
        repository = SymbolPreferenceRepository(session)

        assert repository.is_symbol_allowed(user_id, "XAUUSD") is True
        assert repository.is_symbol_allowed(user_id, "BTCUSD") is False
        assert repository.should_notify(user_id, "XAUUSD") is True
        assert repository.should_notify(user_id, "EURUSD") is False
        assert repository.should_notify(user_id, "BTCUSD") is False


def test_summary_and_tradable_symbols(settings_database, user_id) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.set_symbols(
            user_id,
            SymbolPreferenceKind.WATCHLIST,
            ["XAUUSD", "EURUSD", "BTCUSD"],
        )
        repository.set_symbols(
            user_id,
            SymbolPreferenceKind.PREFERRED,
            ["XAUUSD"],
        )
        repository.set_symbols(
            user_id,
            SymbolPreferenceKind.BLOCKED,
            ["BTCUSD"],
        )

    with settings_database.read_session() as session:
        summary = SymbolPreferenceRepository(session).build_summary(user_id)

        assert summary.watchlist == ("BTCUSD", "EURUSD", "XAUUSD")
        assert summary.blocked == ("BTCUSD",)
        assert summary.tradable == ("EURUSD", "XAUUSD")
        assert SymbolPreferenceRepository(session).resolve_tradable_symbols(
            user_id
        ) == ("EURUSD", "XAUUSD")


def test_symbol_preference_counts_stored_procedure(
    settings_database,
    user_id,
) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.set_symbols(
            user_id,
            SymbolPreferenceKind.WATCHLIST,
            ["XAUUSD", "EURUSD"],
        )
        repository.set_symbols(user_id, SymbolPreferenceKind.BLOCKED, ["BTCUSD"])

    result = StoredProcedureService(settings_database).call_read_only(
        "sp_aqos_symbol_preference_counts",
        parameters=(user_id,),
    )

    counts = {row["kind"]: row["total"] for row in result.rows}

    assert counts == {"blocked": 1, "watchlist": 2}


def test_tradable_symbols_stored_procedure_matches_python(
    settings_database,
    user_id,
) -> None:
    with settings_database.session() as session:
        repository = SymbolPreferenceRepository(session)
        repository.set_symbols(
            user_id,
            SymbolPreferenceKind.WATCHLIST,
            ["XAUUSD", "EURUSD", "BTCUSD"],
        )
        repository.set_symbols(user_id, SymbolPreferenceKind.BLOCKED, ["BTCUSD"])

    result = StoredProcedureService(settings_database).call_read_only(
        "sp_aqos_tradable_symbols",
        parameters=(user_id,),
    )

    procedure_symbols = tuple(row["symbol"] for row in result.rows)

    with settings_database.read_session() as session:
        python_symbols = SymbolPreferenceRepository(session).resolve_tradable_symbols(
            user_id
        )

    assert procedure_symbols == ("EURUSD", "XAUUSD")
    assert procedure_symbols == python_symbols


def test_symbol_preferences_are_isolated_per_user(settings_database) -> None:
    with settings_database.session() as session:
        users = UserProfileRepository(session)
        first = users.create_user(
            email="a@example.com",
            display_name="A",
        ).user_id
        second = users.create_user(
            email="b@example.com",
            display_name="B",
        ).user_id

        repository = SymbolPreferenceRepository(session)
        repository.add_symbol(first, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
        repository.add_symbol(second, "XAUUSD", SymbolPreferenceKind.BLOCKED)

    with settings_database.read_session() as session:
        repository = SymbolPreferenceRepository(session)

        assert repository.is_symbol_allowed(first, "XAUUSD") is True
        assert repository.is_symbol_allowed(second, "XAUUSD") is False
