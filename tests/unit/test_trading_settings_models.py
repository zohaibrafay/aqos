from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from aqos.execution_policy.modes import (
    ExecutionConstraintSource,
    ExecutionMode,
    resolve_execution_mode,
)
from aqos.trading_settings.models import (
    AQOS_TRADING_SETTINGS_VERSION,
    DEFAULT_MAX_OPEN_POSITIONS,
    KINDS_CLEARED_ON_BLOCK,
    SymbolPreference,
    SymbolPreferenceKind,
    SymbolPreferenceSummary,
    TradingSettings,
    as_fraction,
    normalize_required_text,
    normalize_symbol,
    normalize_symbol_list,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_settings(**overrides) -> TradingSettings:
    payload = {
        "settings_id": "settings_1",
        "user_id": "user_1",
        "execution_mode": ExecutionMode.SIGNAL_ONLY,
        "risk_per_trade_fraction": 0.01,
        "max_daily_loss_fraction": 0.05,
        "max_open_positions": 3,
        "max_daily_trades": 10,
        "default_timeframe": "H1",
    }
    payload.update(overrides)

    return TradingSettings(**payload)


def test_trading_settings_version_is_exposed() -> None:
    assert AQOS_TRADING_SETTINGS_VERSION == "1.0"


def test_as_fraction_handles_decimal() -> None:
    assert as_fraction(Decimal("0.010000")) == pytest.approx(0.01)
    assert as_fraction(0.02) == pytest.approx(0.02)


def test_normalize_symbol() -> None:
    assert normalize_symbol(" xau usd ") == "XAUUSD"

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        normalize_symbol("   ")


def test_normalize_symbol_list_deduplicates_and_keeps_order() -> None:
    assert normalize_symbol_list([" xauusd ", "XAUUSD", "eur usd"]) == (
        "XAUUSD",
        "EURUSD",
    )
    assert normalize_symbol_list([]) == ()
    assert normalize_symbol_list(None) == ()


def test_normalize_required_text() -> None:
    assert normalize_required_text(" H1 ", "default_timeframe") == "H1"

    with pytest.raises(ValueError, match="default_timeframe cannot be empty"):
        normalize_required_text("  ", "default_timeframe")


def test_settings_validate_risk_fractions() -> None:
    with pytest.raises(ValueError, match="risk_per_trade_fraction must be"):
        build_settings(risk_per_trade_fraction=0.0)

    with pytest.raises(ValueError, match="risk_per_trade_fraction must be"):
        build_settings(risk_per_trade_fraction=1.5)

    with pytest.raises(ValueError, match="max_daily_loss_fraction must be"):
        build_settings(max_daily_loss_fraction=0.0)

    with pytest.raises(ValueError, match="max_daily_loss_fraction must be"):
        build_settings(max_daily_loss_fraction=2.0)


def test_settings_validate_limits() -> None:
    with pytest.raises(ValueError, match="max_open_positions must be at least 1"):
        build_settings(max_open_positions=0)

    with pytest.raises(ValueError, match="max_daily_trades must be at least 1"):
        build_settings(max_daily_trades=0)

    with pytest.raises(ValueError, match="default_timeframe cannot be empty"):
        build_settings(default_timeframe="  ")


def test_daily_loss_must_cover_a_single_trade() -> None:
    settings = build_settings(
        risk_per_trade_fraction=0.20,
        max_daily_loss_fraction=0.10,
    )

    with pytest.raises(ValueError, match="max_daily_loss_fraction cannot be smaller"):
        settings.validate_consistency()


def test_consistent_settings_pass_the_cross_field_check() -> None:
    build_settings().validate_consistency()
    build_settings(
        risk_per_trade_fraction=0.05,
        max_daily_loss_fraction=0.05,
    ).validate_consistency()


def test_settings_derived_values() -> None:
    settings = build_settings(risk_per_trade_fraction=0.01, max_open_positions=3)

    assert settings.risk_per_trade == pytest.approx(0.01)
    assert settings.max_daily_loss == pytest.approx(0.05)
    assert settings.max_concurrent_risk_fraction == pytest.approx(0.03)


def test_max_concurrent_risk_is_capped_at_one() -> None:
    settings = build_settings(
        risk_per_trade_fraction=0.5,
        max_daily_loss_fraction=1.0,
        max_open_positions=10,
    )

    assert settings.max_concurrent_risk_fraction == 1.0


def test_settings_allows_orders_reflects_the_user_ceiling() -> None:
    assert build_settings().allows_orders is False
    assert build_settings(
        execution_mode=ExecutionMode.MANUAL_APPROVAL
    ).allows_orders is True
    assert build_settings(
        execution_mode=ExecutionMode.AUTO_TRADE
    ).allows_orders is True


def test_settings_expose_an_execution_constraint() -> None:
    item = build_settings(
        execution_mode=ExecutionMode.MANUAL_APPROVAL
    ).execution_constraint()

    assert item.source == ExecutionConstraintSource.USER_SETTINGS
    assert item.ceiling == ExecutionMode.MANUAL_APPROVAL
    assert "manual_approval" in (item.reason or "")


def test_user_constraint_feeds_the_resolver() -> None:
    """The user ceiling is one input to the strictest-mode resolver."""

    settings = build_settings(execution_mode=ExecutionMode.SIGNAL_ONLY)

    decision = resolve_execution_mode(
        requested=ExecutionMode.AUTO_TRADE,
        constraints=(settings.execution_constraint(),),
    )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY
    assert decision.was_downgraded is True
    assert decision.binding_sources == ("user_settings",)
    assert decision.allows_orders is False


def test_settings_dict_payload() -> None:
    payload = build_settings(
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
        extra_metadata={"origin": "unit_test"},
    ).to_dict()

    assert payload["execution_mode"] == "signal_only"
    assert payload["risk_per_trade_fraction"] == pytest.approx(0.01)
    assert payload["max_open_positions"] == DEFAULT_MAX_OPEN_POSITIONS
    assert payload["allows_orders"] is False
    assert payload["created_at_utc"] == "2026-01-01T00:00:00"
    assert payload["metadata"] == {"origin": "unit_test"}
    assert "user_1" in repr(build_settings())


def test_symbol_preference_normalizes_the_symbol() -> None:
    preference = SymbolPreference(
        preference_id="pref_1",
        user_id="user_1",
        symbol=" xau usd ",
        kind=SymbolPreferenceKind.WATCHLIST,
    )

    assert preference.symbol == "XAUUSD"
    assert preference.to_dict()["kind"] == "watchlist"
    assert "XAUUSD" in repr(preference)


def test_symbol_preference_rejects_empty_symbols() -> None:
    with pytest.raises(ValueError, match="symbol cannot be empty"):
        SymbolPreference(
            preference_id="pref_1",
            user_id="user_1",
            symbol="   ",
            kind=SymbolPreferenceKind.WATCHLIST,
        )


def test_blocking_clears_preferred_and_notification_kinds() -> None:
    assert SymbolPreferenceKind.PREFERRED in KINDS_CLEARED_ON_BLOCK
    assert SymbolPreferenceKind.NOTIFICATION in KINDS_CLEARED_ON_BLOCK
    assert SymbolPreferenceKind.WATCHLIST not in KINDS_CLEARED_ON_BLOCK


def test_summary_excludes_blocked_symbols() -> None:
    summary = SymbolPreferenceSummary(
        user_id="user_1",
        watchlist=("XAUUSD", "EURUSD", "BTCUSD"),
        preferred=("XAUUSD",),
        blocked=("BTCUSD",),
        notification=("XAUUSD", "BTCUSD"),
    )

    assert summary.tradable == ("XAUUSD", "EURUSD")
    assert summary.notifiable == ("XAUUSD",)

    payload = summary.to_dict()

    assert payload["tradable"] == ["XAUUSD", "EURUSD"]
    assert payload["notifiable"] == ["XAUUSD"]


def test_empty_summary() -> None:
    summary = SymbolPreferenceSummary(user_id="user_1")

    assert summary.tradable == ()
    assert summary.notifiable == ()
