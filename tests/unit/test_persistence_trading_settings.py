from __future__ import annotations

import pytest

from aqos.persistence.database import AqosDatabase
from aqos.persistence.trading_settings import (
    AQOS_TRADING_SETTINGS_VERSION,
    DEFAULT_MAX_OPEN_POSITIONS,
    DEFAULT_RISK_PER_TRADE_FRACTION,
    ExecutionMode,
    TradingSettings,
    TradingSettingsRepository,
    build_default_trading_settings,
    execution_mode_allows_orders,
    execution_mode_rank,
    resolve_effective_execution_mode,
)
from aqos.persistence.users import UserProfileRepository


@pytest.fixture
def settings_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def stored_user(settings_database):
    return UserProfileRepository(settings_database).create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def settings(settings_database) -> TradingSettingsRepository:
    return TradingSettingsRepository(settings_database)


def build_settings(**overrides) -> TradingSettings:
    payload = {
        "settings_id": "settings_1",
        "user_id": "user_1",
        "created_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)

    return TradingSettings(**payload)


def test_trading_settings_version_is_exposed() -> None:
    assert AQOS_TRADING_SETTINGS_VERSION == "1.0"


def test_execution_mode_rank_is_ordered() -> None:
    assert execution_mode_rank(ExecutionMode.DISABLED) == 0
    assert execution_mode_rank(ExecutionMode.SIGNAL_ONLY) == 1
    assert execution_mode_rank(ExecutionMode.MANUAL_APPROVAL) == 2
    assert execution_mode_rank(ExecutionMode.AUTO_TRADE) == 3


def test_execution_mode_allows_orders() -> None:
    assert execution_mode_allows_orders(ExecutionMode.AUTO_TRADE) is True
    assert execution_mode_allows_orders(ExecutionMode.MANUAL_APPROVAL) is True
    assert execution_mode_allows_orders(ExecutionMode.SIGNAL_ONLY) is False
    assert execution_mode_allows_orders(ExecutionMode.DISABLED) is False


def test_resolve_effective_execution_mode_clamps_to_ceiling() -> None:
    assert resolve_effective_execution_mode(
        ExecutionMode.AUTO_TRADE,
        ExecutionMode.MANUAL_APPROVAL,
    ) == ExecutionMode.MANUAL_APPROVAL

    assert resolve_effective_execution_mode(
        ExecutionMode.SIGNAL_ONLY,
        ExecutionMode.AUTO_TRADE,
    ) == ExecutionMode.SIGNAL_ONLY

    assert resolve_effective_execution_mode(
        ExecutionMode.AUTO_TRADE,
        ExecutionMode.DISABLED,
    ) == ExecutionMode.DISABLED


def test_settings_validation_rejects_bad_identity() -> None:
    with pytest.raises(ValueError, match="settings_id cannot be empty"):
        build_settings(settings_id=" ")

    with pytest.raises(ValueError, match="user_id cannot be empty"):
        build_settings(user_id="")

    with pytest.raises(ValueError, match="created_at_utc cannot be empty"):
        build_settings(created_at_utc=" ")

    with pytest.raises(ValueError, match="updated_at_utc cannot be empty"):
        build_settings(updated_at_utc=" ")


def test_settings_validation_rejects_bad_risk_values() -> None:
    with pytest.raises(ValueError, match="risk_per_trade_fraction must be"):
        build_settings(risk_per_trade_fraction=0.0)

    with pytest.raises(ValueError, match="risk_per_trade_fraction must be"):
        build_settings(risk_per_trade_fraction=1.5)

    with pytest.raises(ValueError, match="max_daily_loss_fraction must be"):
        build_settings(max_daily_loss_fraction=0.0)

    with pytest.raises(ValueError, match="max_daily_loss_fraction cannot be smaller"):
        build_settings(risk_per_trade_fraction=0.2, max_daily_loss_fraction=0.1)


def test_settings_validation_rejects_bad_limits() -> None:
    with pytest.raises(ValueError, match="max_open_positions must be at least 1"):
        build_settings(max_open_positions=0)

    with pytest.raises(ValueError, match="max_daily_trades must be at least 1"):
        build_settings(max_daily_trades=0)

    with pytest.raises(ValueError, match="default_timeframe cannot be empty"):
        build_settings(default_timeframe=" ")


def test_settings_derived_properties() -> None:
    manual = build_settings(execution_mode=ExecutionMode.MANUAL_APPROVAL)

    assert manual.allows_orders is True
    assert manual.requires_manual_approval is True

    signal_only = build_settings()

    assert signal_only.allows_orders is False
    assert signal_only.requires_manual_approval is False


def test_max_concurrent_risk_is_capped_at_one() -> None:
    assert build_settings(
        risk_per_trade_fraction=0.01,
        max_open_positions=3,
    ).max_concurrent_risk_fraction == pytest.approx(0.03)

    assert build_settings(
        risk_per_trade_fraction=0.5,
        max_daily_loss_fraction=1.0,
        max_open_positions=10,
    ).max_concurrent_risk_fraction == 1.0


def test_settings_dict_payload() -> None:
    payload = build_settings().to_dict()

    assert payload["execution_mode"] == "signal_only"
    assert payload["risk_per_trade_fraction"] == DEFAULT_RISK_PER_TRADE_FRACTION
    assert payload["max_open_positions"] == DEFAULT_MAX_OPEN_POSITIONS
    assert payload["allows_orders"] is False


def test_build_default_settings() -> None:
    defaults = build_default_trading_settings(
        "user_1",
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert defaults.settings_id.startswith("settings_")
    assert defaults.execution_mode == ExecutionMode.SIGNAL_ONLY
    assert defaults.created_at_utc == defaults.updated_at_utc


def test_get_or_create_is_idempotent(settings, stored_user) -> None:
    first = settings.get_or_create_settings(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    second = settings.get_or_create_settings(stored_user.user_id)

    assert first.settings_id == second.settings_id
    assert second.created_at_utc == "2026-01-01T00:00:00Z"


def test_create_settings_with_explicit_values(settings, stored_user) -> None:
    created = settings.create_settings(
        stored_user.user_id,
        execution_mode=ExecutionMode.MANUAL_APPROVAL,
        risk_per_trade_fraction=0.02,
        max_daily_loss_fraction=0.08,
        max_open_positions=5,
        max_daily_trades=25,
        default_timeframe="M15",
        allow_short=False,
        allow_hedging=True,
        notifications_enabled=False,
        metadata={"origin": "unit_test"},
        created_at_utc="2026-01-01T00:00:00Z",
    )

    stored = settings.require_settings(stored_user.user_id)

    assert stored.to_dict() == created.to_dict()
    assert stored.allow_short is False
    assert stored.allow_hedging is True
    assert stored.notifications_enabled is False
    assert stored.metadata == {"origin": "unit_test"}


def test_create_settings_rejects_duplicate(settings, stored_user) -> None:
    settings.create_settings(stored_user.user_id)

    with pytest.raises(ValueError, match="already exist"):
        settings.create_settings(stored_user.user_id)


def test_get_settings_returns_none_when_missing(settings) -> None:
    assert settings.get_settings("user_missing") is None


def test_require_settings_raises_when_missing(settings) -> None:
    with pytest.raises(LookupError, match="do not exist"):
        settings.require_settings("user_missing")


def test_update_settings_round_trip(settings, stored_user) -> None:
    settings.get_or_create_settings(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    updated = settings.update_settings(
        stored_user.user_id,
        execution_mode=ExecutionMode.AUTO_TRADE,
        risk_per_trade_fraction=0.005,
        max_open_positions=2,
        allow_hedging=True,
        metadata={"reviewed": True},
        updated_at_utc="2026-02-01T00:00:00Z",
    )

    assert updated.execution_mode == ExecutionMode.AUTO_TRADE
    assert updated.risk_per_trade_fraction == 0.005
    assert updated.max_open_positions == 2
    assert updated.allow_hedging is True
    assert updated.metadata == {"reviewed": True}
    assert updated.created_at_utc == "2026-01-01T00:00:00Z"
    assert updated.updated_at_utc == "2026-02-01T00:00:00Z"

    assert settings.require_settings(stored_user.user_id).to_dict() == updated.to_dict()


def test_update_settings_keeps_unspecified_fields(settings, stored_user) -> None:
    settings.create_settings(stored_user.user_id, max_daily_trades=7)

    updated = settings.update_settings(
        stored_user.user_id,
        execution_mode=ExecutionMode.MANUAL_APPROVAL,
    )

    assert updated.max_daily_trades == 7
    assert updated.default_timeframe == "H1"


def test_update_settings_still_validates(settings, stored_user) -> None:
    settings.get_or_create_settings(stored_user.user_id)

    with pytest.raises(ValueError, match="risk_per_trade_fraction must be"):
        settings.update_settings(stored_user.user_id, risk_per_trade_fraction=2.0)

    with pytest.raises(ValueError, match="max_daily_loss_fraction cannot be smaller"):
        settings.update_settings(stored_user.user_id, risk_per_trade_fraction=0.9)


def test_set_execution_mode(settings, stored_user) -> None:
    settings.get_or_create_settings(stored_user.user_id)

    updated = settings.set_execution_mode(
        stored_user.user_id,
        ExecutionMode.DISABLED,
        updated_at_utc="2026-03-01T00:00:00Z",
    )

    assert updated.execution_mode == ExecutionMode.DISABLED
    assert updated.allows_orders is False
    assert updated.updated_at_utc == "2026-03-01T00:00:00Z"


def test_reset_settings(settings, stored_user) -> None:
    created = settings.get_or_create_settings(
        stored_user.user_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    settings.update_settings(
        stored_user.user_id,
        execution_mode=ExecutionMode.AUTO_TRADE,
        max_open_positions=9,
    )

    reset = settings.reset_settings(
        stored_user.user_id,
        updated_at_utc="2026-04-01T00:00:00Z",
    )

    assert reset.settings_id == created.settings_id
    assert reset.created_at_utc == created.created_at_utc
    assert reset.execution_mode == ExecutionMode.SIGNAL_ONLY
    assert reset.max_open_positions == DEFAULT_MAX_OPEN_POSITIONS
    assert reset.updated_at_utc == "2026-04-01T00:00:00Z"


def test_list_settings_filters_by_execution_mode(
    settings_database,
    settings,
) -> None:
    users = UserProfileRepository(settings_database)

    first = users.create_user(
        email="a@example.com",
        display_name="A",
        created_at_utc="2026-01-01T00:00:00Z",
    )
    second = users.create_user(
        email="b@example.com",
        display_name="B",
        created_at_utc="2026-01-02T00:00:00Z",
    )

    settings.create_settings(first.user_id, created_at_utc="2026-01-01T00:00:00Z")
    settings.create_settings(
        second.user_id,
        execution_mode=ExecutionMode.AUTO_TRADE,
        created_at_utc="2026-01-02T00:00:00Z",
    )

    assert len(settings.list_settings()) == 2
    assert [
        item.user_id
        for item in settings.list_settings(execution_mode=ExecutionMode.AUTO_TRADE)
    ] == [second.user_id]


def test_delete_settings(settings, stored_user) -> None:
    settings.get_or_create_settings(stored_user.user_id)

    assert settings.delete_settings(stored_user.user_id) is True
    assert settings.get_settings(stored_user.user_id) is None
    assert settings.delete_settings(stored_user.user_id) is False


def test_deleting_user_cascades_to_settings(
    settings_database,
    settings,
    stored_user,
) -> None:
    settings.get_or_create_settings(stored_user.user_id)

    UserProfileRepository(settings_database).delete_user(stored_user.user_id)

    assert settings.get_settings(stored_user.user_id) is None
