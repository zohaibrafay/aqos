from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from aqos.persistence.database import AqosDatabase
from aqos.persistence.records import (
    build_record_id,
    decode_json_field,
    encode_json_field,
    normalize_required_text,
    normalize_symbol,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema


AQOS_SYMBOL_PREFERENCES_VERSION = "1.0"


class SymbolPreferenceKind(str, Enum):
    WATCHLIST = "watchlist"
    PREFERRED = "preferred"
    BLOCKED = "blocked"
    NOTIFICATION = "notification"


#: Kinds that a blocked symbol is automatically removed from.
KINDS_CLEARED_ON_BLOCK = (
    SymbolPreferenceKind.PREFERRED,
    SymbolPreferenceKind.NOTIFICATION,
)


@dataclass(frozen=True)
class SymbolPreference:
    preference_id: str
    user_id: str
    symbol: str
    kind: SymbolPreferenceKind
    created_at_utc: str
    updated_at_utc: str
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.preference_id.strip():
            raise ValueError("preference_id cannot be empty.")

        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if self.symbol != self.symbol.upper():
            raise ValueError("symbol must be stored in upper case.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.updated_at_utc.strip():
            raise ValueError("updated_at_utc cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "kind": self.kind.value,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SymbolPreferenceSummary:
    user_id: str
    watchlist: tuple[str, ...] = ()
    preferred: tuple[str, ...] = ()
    blocked: tuple[str, ...] = ()
    notification: tuple[str, ...] = ()

    @property
    def tradable(self) -> tuple[str, ...]:
        """Watchlist symbols that are not blocked."""

        blocked = set(self.blocked)

        return tuple(symbol for symbol in self.watchlist if symbol not in blocked)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "watchlist": list(self.watchlist),
            "preferred": list(self.preferred),
            "blocked": list(self.blocked),
            "notification": list(self.notification),
            "tradable": list(self.tradable),
        }


def build_symbol_preference_from_row(row: dict[str, Any]) -> SymbolPreference:
    return SymbolPreference(
        preference_id=str(row["preference_id"]),
        user_id=str(row["user_id"]),
        symbol=str(row["symbol"]),
        kind=SymbolPreferenceKind(str(row["kind"])),
        created_at_utc=str(row["created_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        metadata=decode_json_field(row.get("metadata")),
    )


def normalize_symbol_list(symbols: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Upper-case, de-duplicate and preserve the caller's ordering."""

    normalized: list[str] = []

    for symbol in symbols:
        clean = normalize_symbol(symbol)

        if clean not in normalized:
            normalized.append(clean)

    return tuple(normalized)


class SymbolPreferenceRepository:
    """
    Per-user symbol lists.

    A blocked symbol is authoritative: blocking removes the symbol from the
    preferred and notification lists so it can never be traded or alerted on by
    accident.
    """

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

    def add_symbol(
        self,
        user_id: str,
        symbol: str,
        kind: SymbolPreferenceKind,
        metadata: dict[str, Any] | None = None,
        created_at_utc: str | None = None,
    ) -> SymbolPreference:
        normalized_symbol = normalize_symbol(symbol)
        timestamp = created_at_utc or record_utc_now()

        existing = self.get_symbol(user_id, normalized_symbol, kind)

        if existing is not None:
            return existing

        preference = SymbolPreference(
            preference_id=build_record_id("symbolpref"),
            user_id=normalize_required_text(user_id, "user_id"),
            symbol=normalized_symbol,
            kind=kind,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            metadata=metadata or {},
        )

        self.database.execute(
            """
            INSERT INTO symbol_preferences (
                preference_id, user_id, symbol, kind,
                created_at_utc, updated_at_utc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (
                preference.preference_id,
                preference.user_id,
                preference.symbol,
                preference.kind.value,
                preference.created_at_utc,
                preference.updated_at_utc,
                encode_json_field(preference.metadata),
            ),
        )

        if kind == SymbolPreferenceKind.BLOCKED:
            for cleared_kind in KINDS_CLEARED_ON_BLOCK:
                self.remove_symbol(user_id, normalized_symbol, cleared_kind)

        return preference

    def get_symbol(
        self,
        user_id: str,
        symbol: str,
        kind: SymbolPreferenceKind,
    ) -> SymbolPreference | None:
        row = self.database.query_one(
            "SELECT * FROM symbol_preferences "
            "WHERE user_id = ? AND symbol = ? AND kind = ?;",
            (user_id, normalize_symbol(symbol), kind.value),
        )

        return build_symbol_preference_from_row(row) if row is not None else None

    def remove_symbol(
        self,
        user_id: str,
        symbol: str,
        kind: SymbolPreferenceKind,
    ) -> bool:
        cursor = self.database.execute(
            "DELETE FROM symbol_preferences "
            "WHERE user_id = ? AND symbol = ? AND kind = ?;",
            (user_id, normalize_symbol(symbol), kind.value),
        )

        return cursor.rowcount > 0

    def list_preferences(
        self,
        user_id: str,
        kind: SymbolPreferenceKind | None = None,
    ) -> tuple[SymbolPreference, ...]:
        if kind is None:
            rows = self.database.query_all(
                "SELECT * FROM symbol_preferences WHERE user_id = ? "
                "ORDER BY kind, symbol;",
                (user_id,),
            )
        else:
            rows = self.database.query_all(
                "SELECT * FROM symbol_preferences WHERE user_id = ? AND kind = ? "
                "ORDER BY symbol;",
                (user_id, kind.value),
            )

        return tuple(build_symbol_preference_from_row(row) for row in rows)

    def list_symbols(
        self,
        user_id: str,
        kind: SymbolPreferenceKind,
    ) -> tuple[str, ...]:
        return tuple(
            preference.symbol
            for preference in self.list_preferences(user_id, kind)
        )

    def set_symbols(
        self,
        user_id: str,
        kind: SymbolPreferenceKind,
        symbols: tuple[str, ...] | list[str],
        created_at_utc: str | None = None,
    ) -> tuple[str, ...]:
        """Replace the whole list for one kind and return the stored symbols."""

        normalized = normalize_symbol_list(symbols)

        with self.database.transaction():
            self.database.execute(
                "DELETE FROM symbol_preferences WHERE user_id = ? AND kind = ?;",
                (user_id, kind.value),
            )

        for symbol in normalized:
            self.add_symbol(
                user_id=user_id,
                symbol=symbol,
                kind=kind,
                created_at_utc=created_at_utc,
            )

        return self.list_symbols(user_id, kind)

    def clear_symbols(
        self,
        user_id: str,
        kind: SymbolPreferenceKind | None = None,
    ) -> int:
        if kind is None:
            cursor = self.database.execute(
                "DELETE FROM symbol_preferences WHERE user_id = ?;",
                (user_id,),
            )
        else:
            cursor = self.database.execute(
                "DELETE FROM symbol_preferences WHERE user_id = ? AND kind = ?;",
                (user_id, kind.value),
            )

        return int(cursor.rowcount)

    def has_symbol(
        self,
        user_id: str,
        symbol: str,
        kind: SymbolPreferenceKind,
    ) -> bool:
        return self.get_symbol(user_id, symbol, kind) is not None

    def is_blocked(self, user_id: str, symbol: str) -> bool:
        return self.has_symbol(user_id, symbol, SymbolPreferenceKind.BLOCKED)

    def is_symbol_allowed(self, user_id: str, symbol: str) -> bool:
        return not self.is_blocked(user_id, symbol)

    def should_notify(self, user_id: str, symbol: str) -> bool:
        if self.is_blocked(user_id, symbol):
            return False

        return self.has_symbol(user_id, symbol, SymbolPreferenceKind.NOTIFICATION)

    def build_summary(self, user_id: str) -> SymbolPreferenceSummary:
        return SymbolPreferenceSummary(
            user_id=user_id,
            watchlist=self.list_symbols(user_id, SymbolPreferenceKind.WATCHLIST),
            preferred=self.list_symbols(user_id, SymbolPreferenceKind.PREFERRED),
            blocked=self.list_symbols(user_id, SymbolPreferenceKind.BLOCKED),
            notification=self.list_symbols(
                user_id,
                SymbolPreferenceKind.NOTIFICATION,
            ),
        )

    def resolve_tradable_symbols(self, user_id: str) -> tuple[str, ...]:
        return self.build_summary(user_id).tradable


__all__ = [
    "AQOS_SYMBOL_PREFERENCES_VERSION",
    "KINDS_CLEARED_ON_BLOCK",
    "SymbolPreference",
    "SymbolPreferenceKind",
    "SymbolPreferenceRepository",
    "SymbolPreferenceSummary",
    "build_symbol_preference_from_row",
    "normalize_symbol_list",
]
