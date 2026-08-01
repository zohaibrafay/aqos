from __future__ import annotations

import pytest

from aqos.persistence.database import AqosDatabase
from aqos.persistence.symbol_preferences import (
    AQOS_SYMBOL_PREFERENCES_VERSION,
    SymbolPreference,
    SymbolPreferenceKind,
    SymbolPreferenceRepository,
    SymbolPreferenceSummary,
    normalize_symbol_list,
)
from aqos.persistence.users import UserProfileRepository


@pytest.fixture
def symbol_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def stored_user(symbol_database):
    return UserProfileRepository(symbol_database).create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def symbols(symbol_database) -> SymbolPreferenceRepository:
    return SymbolPreferenceRepository(symbol_database)


def test_symbol_preferences_version_is_exposed() -> None:
    assert AQOS_SYMBOL_PREFERENCES_VERSION == "1.0"


def test_normalize_symbol_list_upper_cases_and_deduplicates() -> None:
    assert normalize_symbol_list([" xauusd ", "XAUUSD", "eur usd"]) == (
        "XAUUSD",
        "EURUSD",
    )
    assert normalize_symbol_list([]) == ()


def test_normalize_symbol_list_rejects_empty_symbol() -> None:
    with pytest.raises(ValueError, match="symbol cannot be empty"):
        normalize_symbol_list(["  "])


def test_symbol_preference_validation() -> None:
    valid = {
        "preference_id": "pref_1",
        "user_id": "user_1",
        "symbol": "XAUUSD",
        "kind": SymbolPreferenceKind.WATCHLIST,
        "created_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(ValueError, match="preference_id cannot be empty"):
        SymbolPreference(**{**valid, "preference_id": " "})

    with pytest.raises(ValueError, match="user_id cannot be empty"):
        SymbolPreference(**{**valid, "user_id": ""})

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        SymbolPreference(**{**valid, "symbol": " "})

    with pytest.raises(ValueError, match="upper case"):
        SymbolPreference(**{**valid, "symbol": "xauusd"})

    with pytest.raises(ValueError, match="created_at_utc cannot be empty"):
        SymbolPreference(**{**valid, "created_at_utc": " "})

    with pytest.raises(ValueError, match="updated_at_utc cannot be empty"):
        SymbolPreference(**{**valid, "updated_at_utc": " "})


def test_summary_tradable_excludes_blocked() -> None:
    summary = SymbolPreferenceSummary(
        user_id="user_1",
        watchlist=("XAUUSD", "EURUSD", "BTCUSD"),
        blocked=("EURUSD",),
    )

    assert summary.tradable == ("XAUUSD", "BTCUSD")
    assert summary.to_dict()["tradable"] == ["XAUUSD", "BTCUSD"]


def test_add_symbol_normalizes_and_persists(symbols, stored_user) -> None:
    preference = symbols.add_symbol(
        stored_user.user_id,
        " xau usd ",
        SymbolPreferenceKind.WATCHLIST,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    assert preference.symbol == "XAUUSD"
    assert preference.kind == SymbolPreferenceKind.WATCHLIST
    assert preference.preference_id.startswith("symbolpref_")

    stored = symbols.get_symbol(
        stored_user.user_id,
        "xauusd",
        SymbolPreferenceKind.WATCHLIST,
    )

    assert stored is not None
    assert stored.to_dict() == preference.to_dict()


def test_add_symbol_is_idempotent(symbols, stored_user) -> None:
    first = symbols.add_symbol(
        stored_user.user_id,
        "XAUUSD",
        SymbolPreferenceKind.WATCHLIST,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    second = symbols.add_symbol(
        stored_user.user_id,
        "xauusd",
        SymbolPreferenceKind.WATCHLIST,
        created_at_utc="2026-02-01T00:00:00Z",
    )

    assert second.preference_id == first.preference_id
    assert second.created_at_utc == "2026-01-01T00:00:00Z"
    assert len(symbols.list_symbols(stored_user.user_id, SymbolPreferenceKind.WATCHLIST)) == 1


def test_same_symbol_can_exist_in_multiple_kinds(symbols, stored_user) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.PREFERRED)

    assert symbols.has_symbol(
        stored_user.user_id,
        "XAUUSD",
        SymbolPreferenceKind.WATCHLIST,
    )
    assert symbols.has_symbol(
        stored_user.user_id,
        "XAUUSD",
        SymbolPreferenceKind.PREFERRED,
    )


def test_blocking_clears_preferred_and_notification(symbols, stored_user) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.PREFERRED)
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.NOTIFICATION)

    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.BLOCKED)

    assert symbols.is_blocked(stored_user.user_id, "XAUUSD") is True
    assert symbols.has_symbol(
        stored_user.user_id,
        "XAUUSD",
        SymbolPreferenceKind.PREFERRED,
    ) is False
    assert symbols.has_symbol(
        stored_user.user_id,
        "XAUUSD",
        SymbolPreferenceKind.NOTIFICATION,
    ) is False
    assert symbols.has_symbol(
        stored_user.user_id,
        "XAUUSD",
        SymbolPreferenceKind.WATCHLIST,
    ) is True


def test_remove_symbol(symbols, stored_user) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)

    assert symbols.remove_symbol(
        stored_user.user_id,
        "xauusd",
        SymbolPreferenceKind.WATCHLIST,
    ) is True
    assert symbols.remove_symbol(
        stored_user.user_id,
        "XAUUSD",
        SymbolPreferenceKind.WATCHLIST,
    ) is False


def test_list_symbols_is_sorted(symbols, stored_user) -> None:
    for symbol in ("XAUUSD", "AUDUSD", "EURUSD"):
        symbols.add_symbol(stored_user.user_id, symbol, SymbolPreferenceKind.WATCHLIST)

    assert symbols.list_symbols(stored_user.user_id, SymbolPreferenceKind.WATCHLIST) == (
        "AUDUSD",
        "EURUSD",
        "XAUUSD",
    )


def test_list_preferences_across_kinds(symbols, stored_user) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
    symbols.add_symbol(stored_user.user_id, "BTCUSD", SymbolPreferenceKind.BLOCKED)

    all_preferences = symbols.list_preferences(stored_user.user_id)

    assert len(all_preferences) == 2
    assert all_preferences[0].kind == SymbolPreferenceKind.BLOCKED
    assert all_preferences[1].kind == SymbolPreferenceKind.WATCHLIST


def test_set_symbols_replaces_list(symbols, stored_user) -> None:
    symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.WATCHLIST,
        ["XAUUSD", "EURUSD"],
    )

    replaced = symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.WATCHLIST,
        ["btcusd", "BTCUSD", " ethusd "],
    )

    assert replaced == ("BTCUSD", "ETHUSD")
    assert symbols.list_symbols(stored_user.user_id, SymbolPreferenceKind.WATCHLIST) == (
        "BTCUSD",
        "ETHUSD",
    )


def test_set_symbols_to_empty_clears_kind(symbols, stored_user) -> None:
    symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.NOTIFICATION,
        ["XAUUSD"],
    )

    assert symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.NOTIFICATION,
        [],
    ) == ()


def test_set_blocked_symbols_clears_dependent_kinds(symbols, stored_user) -> None:
    symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.NOTIFICATION,
        ["XAUUSD", "EURUSD"],
    )

    symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.BLOCKED,
        ["XAUUSD"],
    )

    assert symbols.list_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.NOTIFICATION,
    ) == ("EURUSD",)


def test_clear_symbols(symbols, stored_user) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
    symbols.add_symbol(stored_user.user_id, "BTCUSD", SymbolPreferenceKind.BLOCKED)

    assert symbols.clear_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.WATCHLIST,
    ) == 1
    assert symbols.clear_symbols(stored_user.user_id) == 1
    assert symbols.list_preferences(stored_user.user_id) == ()


def test_symbol_allowance_rules(symbols, stored_user) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)
    symbols.add_symbol(stored_user.user_id, "BTCUSD", SymbolPreferenceKind.BLOCKED)

    assert symbols.is_symbol_allowed(stored_user.user_id, "XAUUSD") is True
    assert symbols.is_symbol_allowed(stored_user.user_id, "BTCUSD") is False


def test_should_notify_respects_block(symbols, stored_user) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.NOTIFICATION)

    assert symbols.should_notify(stored_user.user_id, "XAUUSD") is True
    assert symbols.should_notify(stored_user.user_id, "EURUSD") is False

    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.BLOCKED)

    assert symbols.should_notify(stored_user.user_id, "XAUUSD") is False


def test_build_summary_and_tradable_symbols(symbols, stored_user) -> None:
    symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.WATCHLIST,
        ["XAUUSD", "EURUSD", "BTCUSD"],
    )
    symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.PREFERRED,
        ["XAUUSD"],
    )
    symbols.set_symbols(
        stored_user.user_id,
        SymbolPreferenceKind.BLOCKED,
        ["BTCUSD"],
    )

    summary = symbols.build_summary(stored_user.user_id)

    assert summary.watchlist == ("BTCUSD", "EURUSD", "XAUUSD")
    assert summary.preferred == ("XAUUSD",)
    assert summary.blocked == ("BTCUSD",)
    assert summary.tradable == ("EURUSD", "XAUUSD")
    assert symbols.resolve_tradable_symbols(stored_user.user_id) == (
        "EURUSD",
        "XAUUSD",
    )


def test_summary_for_user_without_preferences(symbols) -> None:
    summary = symbols.build_summary("user_missing")

    assert summary.watchlist == ()
    assert summary.tradable == ()


def test_deleting_user_cascades_to_symbol_preferences(
    symbol_database,
    symbols,
    stored_user,
) -> None:
    symbols.add_symbol(stored_user.user_id, "XAUUSD", SymbolPreferenceKind.WATCHLIST)

    UserProfileRepository(symbol_database).delete_user(stored_user.user_id)

    assert symbols.list_preferences(stored_user.user_id) == ()
