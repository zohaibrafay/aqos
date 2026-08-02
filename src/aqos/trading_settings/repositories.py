from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete as sql_delete, select

from aqos.database.repository import AqosRepository, RepositoryError
from aqos.database.types import database_utc_now
from aqos.execution_policy.modes import ExecutionMode
from aqos.trading_settings.models import (
    DEFAULT_MAX_DAILY_LOSS_FRACTION,
    DEFAULT_MAX_DAILY_TRADES,
    DEFAULT_MAX_OPEN_POSITIONS,
    DEFAULT_RISK_PER_TRADE_FRACTION,
    DEFAULT_TIMEFRAME,
    KINDS_CLEARED_ON_BLOCK,
    SymbolPreference,
    SymbolPreferenceKind,
    SymbolPreferenceSummary,
    TradingSettings,
    normalize_symbol,
    normalize_symbol_list,
)
from aqos.users.repositories import build_entity_id


AQOS_TRADING_SETTINGS_REPOSITORIES_VERSION = "1.0"


class TradingSettingsRepository(AqosRepository[TradingSettings]):
    """One trading settings row per user, created on demand with safe defaults."""

    model = TradingSettings

    def get_for_user(self, user_id: str) -> TradingSettings | None:
        return self.session.execute(
            select(TradingSettings).where(TradingSettings.user_id == user_id)
        ).scalar_one_or_none()

    def require_for_user(self, user_id: str) -> TradingSettings:
        settings = self.get_for_user(user_id)

        if settings is None:
            raise RepositoryError(f"Trading settings do not exist for user: {user_id}")

        return settings

    def create_for_user(
        self,
        user_id: str,
        execution_mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY,
        risk_per_trade_fraction: float = DEFAULT_RISK_PER_TRADE_FRACTION,
        max_daily_loss_fraction: float = DEFAULT_MAX_DAILY_LOSS_FRACTION,
        max_open_positions: int = DEFAULT_MAX_OPEN_POSITIONS,
        max_daily_trades: int = DEFAULT_MAX_DAILY_TRADES,
        default_timeframe: str = DEFAULT_TIMEFRAME,
        allow_short: bool = True,
        allow_hedging: bool = False,
        notifications_enabled: bool = True,
        metadata: dict[str, Any] | None = None,
        settings_id: str | None = None,
        created_at_utc: datetime | None = None,
    ) -> TradingSettings:
        if self.get_for_user(user_id) is not None:
            raise RepositoryError(
                f"Trading settings already exist for user: {user_id}"
            )

        timestamp = created_at_utc or database_utc_now()

        settings = TradingSettings(
            settings_id=settings_id or build_entity_id("settings"),
            user_id=user_id,
            execution_mode=execution_mode,
            risk_per_trade_fraction=risk_per_trade_fraction,
            max_daily_loss_fraction=max_daily_loss_fraction,
            max_open_positions=max_open_positions,
            max_daily_trades=max_daily_trades,
            default_timeframe=default_timeframe,
            allow_short=allow_short,
            allow_hedging=allow_hedging,
            notifications_enabled=notifications_enabled,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
        )
        settings.validate_consistency()

        self.add(settings)
        self.flush()

        return settings

    def get_or_create_for_user(
        self,
        user_id: str,
        created_at_utc: datetime | None = None,
    ) -> TradingSettings:
        existing = self.get_for_user(user_id)

        if existing is not None:
            return existing

        return self.create_for_user(user_id, created_at_utc=created_at_utc)

    def list_settings(
        self,
        execution_mode: ExecutionMode | None = None,
    ) -> tuple[TradingSettings, ...]:
        statement = select(TradingSettings)

        if execution_mode is not None:
            statement = statement.where(
                TradingSettings.execution_mode == execution_mode
            )

        statement = statement.order_by(
            TradingSettings.created_at_utc,
            TradingSettings.user_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def update_for_user(
        self,
        user_id: str,
        execution_mode: ExecutionMode | None = None,
        risk_per_trade_fraction: float | None = None,
        max_daily_loss_fraction: float | None = None,
        max_open_positions: int | None = None,
        max_daily_trades: int | None = None,
        default_timeframe: str | None = None,
        allow_short: bool | None = None,
        allow_hedging: bool | None = None,
        notifications_enabled: bool | None = None,
        metadata: dict[str, Any] | None = None,
        updated_at_utc: datetime | None = None,
    ) -> TradingSettings:
        settings = self.require_for_user(user_id)

        if execution_mode is not None:
            settings.execution_mode = execution_mode

        if risk_per_trade_fraction is not None:
            settings.risk_per_trade_fraction = risk_per_trade_fraction

        if max_daily_loss_fraction is not None:
            settings.max_daily_loss_fraction = max_daily_loss_fraction

        if max_open_positions is not None:
            settings.max_open_positions = max_open_positions

        if max_daily_trades is not None:
            settings.max_daily_trades = max_daily_trades

        if default_timeframe is not None:
            settings.default_timeframe = default_timeframe

        if allow_short is not None:
            settings.allow_short = allow_short

        if allow_hedging is not None:
            settings.allow_hedging = allow_hedging

        if notifications_enabled is not None:
            settings.notifications_enabled = notifications_enabled

        if metadata is not None:
            settings.extra_metadata = metadata

        settings.updated_at_utc = updated_at_utc or database_utc_now()
        settings.validate_consistency()

        self.flush()

        return settings

    def set_execution_mode(
        self,
        user_id: str,
        execution_mode: ExecutionMode,
        updated_at_utc: datetime | None = None,
    ) -> TradingSettings:
        return self.update_for_user(
            user_id=user_id,
            execution_mode=execution_mode,
            updated_at_utc=updated_at_utc,
        )

    def reset_for_user(
        self,
        user_id: str,
        updated_at_utc: datetime | None = None,
    ) -> TradingSettings:
        return self.update_for_user(
            user_id=user_id,
            execution_mode=ExecutionMode.SIGNAL_ONLY,
            risk_per_trade_fraction=DEFAULT_RISK_PER_TRADE_FRACTION,
            max_daily_loss_fraction=DEFAULT_MAX_DAILY_LOSS_FRACTION,
            max_open_positions=DEFAULT_MAX_OPEN_POSITIONS,
            max_daily_trades=DEFAULT_MAX_DAILY_TRADES,
            default_timeframe=DEFAULT_TIMEFRAME,
            allow_short=True,
            allow_hedging=False,
            notifications_enabled=True,
            metadata={},
            updated_at_utc=updated_at_utc,
        )

    def delete_for_user(self, user_id: str) -> bool:
        settings = self.get_for_user(user_id)

        if settings is None:
            return False

        self.session.delete(settings)
        self.flush()

        return True


class SymbolPreferenceRepository(AqosRepository[SymbolPreference]):
    """
    Per-user symbol lists.

    A blocked symbol is authoritative: blocking removes the symbol from the
    preferred and notification lists so it can never be traded or alerted on by
    accident.
    """

    model = SymbolPreference

    def add_symbol(
        self,
        user_id: str,
        symbol: str,
        kind: SymbolPreferenceKind,
        metadata: dict[str, Any] | None = None,
        created_at_utc: datetime | None = None,
    ) -> SymbolPreference:
        normalized_symbol = normalize_symbol(symbol)

        existing = self.get_symbol(user_id, normalized_symbol, kind)

        if existing is not None:
            return existing

        timestamp = created_at_utc or database_utc_now()

        preference = SymbolPreference(
            preference_id=build_entity_id("symbolpref"),
            user_id=user_id,
            symbol=normalized_symbol,
            kind=kind,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
        )

        self.add(preference)
        self.flush()

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
        return self.session.execute(
            select(SymbolPreference).where(
                SymbolPreference.user_id == user_id,
                SymbolPreference.symbol == normalize_symbol(symbol),
                SymbolPreference.kind == kind,
            )
        ).scalar_one_or_none()

    def remove_symbol(
        self,
        user_id: str,
        symbol: str,
        kind: SymbolPreferenceKind,
    ) -> bool:
        result = self.session.execute(
            sql_delete(SymbolPreference).where(
                SymbolPreference.user_id == user_id,
                SymbolPreference.symbol == normalize_symbol(symbol),
                SymbolPreference.kind == kind,
            )
        )

        return int(result.rowcount or 0) > 0

    def list_preferences(
        self,
        user_id: str,
        kind: SymbolPreferenceKind | None = None,
    ) -> tuple[SymbolPreference, ...]:
        statement = select(SymbolPreference).where(
            SymbolPreference.user_id == user_id
        )

        if kind is not None:
            statement = statement.where(SymbolPreference.kind == kind)
            statement = statement.order_by(SymbolPreference.symbol)
        else:
            statement = statement.order_by(
                SymbolPreference.kind,
                SymbolPreference.symbol,
            )

        return tuple(self.session.execute(statement).scalars().all())

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
        symbols: Any,
        created_at_utc: datetime | None = None,
    ) -> tuple[str, ...]:
        """Replace the whole list for one kind and return the stored symbols."""

        normalized = normalize_symbol_list(symbols)

        self.session.execute(
            sql_delete(SymbolPreference).where(
                SymbolPreference.user_id == user_id,
                SymbolPreference.kind == kind,
            )
        )
        self.flush()

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
        statement = sql_delete(SymbolPreference).where(
            SymbolPreference.user_id == user_id
        )

        if kind is not None:
            statement = statement.where(SymbolPreference.kind == kind)

        result = self.session.execute(statement)
        self.flush()

        return int(result.rowcount or 0)

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
    "AQOS_TRADING_SETTINGS_REPOSITORIES_VERSION",
    "SymbolPreferenceRepository",
    "TradingSettingsRepository",
]
