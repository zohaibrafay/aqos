from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from enum import Enum
from typing import Any

from aqos.persistence.database import AqosDatabase
from aqos.persistence.records import (
    build_record_id,
    decode_bool,
    decode_json_field,
    encode_bool,
    encode_json_field,
    normalize_required_text,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema


AQOS_TRADING_SETTINGS_VERSION = "1.0"


class ExecutionMode(str, Enum):
    """How far AQOS may act on a signal without a human in the loop."""

    DISABLED = "disabled"
    SIGNAL_ONLY = "signal_only"
    MANUAL_APPROVAL = "manual_approval"
    AUTO_TRADE = "auto_trade"


EXECUTION_MODE_RANK: dict[ExecutionMode, int] = {
    ExecutionMode.DISABLED: 0,
    ExecutionMode.SIGNAL_ONLY: 1,
    ExecutionMode.MANUAL_APPROVAL: 2,
    ExecutionMode.AUTO_TRADE: 3,
}

DEFAULT_RISK_PER_TRADE_FRACTION = 0.01
DEFAULT_MAX_DAILY_LOSS_FRACTION = 0.05
DEFAULT_MAX_OPEN_POSITIONS = 3
DEFAULT_MAX_DAILY_TRADES = 10
DEFAULT_TIMEFRAME = "H1"


def execution_mode_rank(mode: ExecutionMode) -> int:
    return EXECUTION_MODE_RANK[mode]


def execution_mode_allows_orders(mode: ExecutionMode) -> bool:
    return mode in (ExecutionMode.MANUAL_APPROVAL, ExecutionMode.AUTO_TRADE)


def resolve_effective_execution_mode(
    requested: ExecutionMode,
    ceiling: ExecutionMode,
) -> ExecutionMode:
    """Clamp a requested execution mode to the strictest configured ceiling."""

    if execution_mode_rank(requested) <= execution_mode_rank(ceiling):
        return requested

    return ceiling


@dataclass(frozen=True)
class TradingSettings:
    settings_id: str
    user_id: str
    created_at_utc: str
    updated_at_utc: str
    execution_mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY
    risk_per_trade_fraction: float = DEFAULT_RISK_PER_TRADE_FRACTION
    max_daily_loss_fraction: float = DEFAULT_MAX_DAILY_LOSS_FRACTION
    max_open_positions: int = DEFAULT_MAX_OPEN_POSITIONS
    max_daily_trades: int = DEFAULT_MAX_DAILY_TRADES
    default_timeframe: str = DEFAULT_TIMEFRAME
    allow_short: bool = True
    allow_hedging: bool = False
    notifications_enabled: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.settings_id.strip():
            raise ValueError("settings_id cannot be empty.")

        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.updated_at_utc.strip():
            raise ValueError("updated_at_utc cannot be empty.")

        if not 0.0 < self.risk_per_trade_fraction <= 1.0:
            raise ValueError(
                "risk_per_trade_fraction must be greater than 0 and at most 1."
            )

        if not 0.0 < self.max_daily_loss_fraction <= 1.0:
            raise ValueError(
                "max_daily_loss_fraction must be greater than 0 and at most 1."
            )

        if self.max_daily_loss_fraction < self.risk_per_trade_fraction:
            raise ValueError(
                "max_daily_loss_fraction cannot be smaller than "
                "risk_per_trade_fraction."
            )

        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1.")

        if self.max_daily_trades < 1:
            raise ValueError("max_daily_trades must be at least 1.")

        if not self.default_timeframe.strip():
            raise ValueError("default_timeframe cannot be empty.")

    @property
    def allows_orders(self) -> bool:
        return execution_mode_allows_orders(self.execution_mode)

    @property
    def requires_manual_approval(self) -> bool:
        return self.execution_mode == ExecutionMode.MANUAL_APPROVAL

    @property
    def max_concurrent_risk_fraction(self) -> float:
        return min(1.0, self.risk_per_trade_fraction * self.max_open_positions)

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings_id": self.settings_id,
            "user_id": self.user_id,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "execution_mode": self.execution_mode.value,
            "risk_per_trade_fraction": self.risk_per_trade_fraction,
            "max_daily_loss_fraction": self.max_daily_loss_fraction,
            "max_open_positions": self.max_open_positions,
            "max_daily_trades": self.max_daily_trades,
            "default_timeframe": self.default_timeframe,
            "allow_short": self.allow_short,
            "allow_hedging": self.allow_hedging,
            "notifications_enabled": self.notifications_enabled,
            "allows_orders": self.allows_orders,
            "requires_manual_approval": self.requires_manual_approval,
            "max_concurrent_risk_fraction": self.max_concurrent_risk_fraction,
            "metadata": self.metadata,
        }


def build_trading_settings_from_row(row: dict[str, Any]) -> TradingSettings:
    return TradingSettings(
        settings_id=str(row["settings_id"]),
        user_id=str(row["user_id"]),
        created_at_utc=str(row["created_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        execution_mode=ExecutionMode(str(row["execution_mode"])),
        risk_per_trade_fraction=float(row["risk_per_trade_fraction"]),
        max_daily_loss_fraction=float(row["max_daily_loss_fraction"]),
        max_open_positions=int(row["max_open_positions"]),
        max_daily_trades=int(row["max_daily_trades"]),
        default_timeframe=str(row["default_timeframe"]),
        allow_short=decode_bool(row["allow_short"]),
        allow_hedging=decode_bool(row["allow_hedging"]),
        notifications_enabled=decode_bool(row["notifications_enabled"]),
        metadata=decode_json_field(row.get("metadata")),
    )


def build_default_trading_settings(
    user_id: str,
    settings_id: str | None = None,
    created_at_utc: str | None = None,
) -> TradingSettings:
    timestamp = created_at_utc or record_utc_now()

    return TradingSettings(
        settings_id=settings_id or build_record_id("settings"),
        user_id=normalize_required_text(user_id, "user_id"),
        created_at_utc=timestamp,
        updated_at_utc=timestamp,
    )


class TradingSettingsRepository:
    """One trading settings row per user, created on demand with safe defaults."""

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

    def get_settings(self, user_id: str) -> TradingSettings | None:
        row = self.database.query_one(
            "SELECT * FROM trading_settings WHERE user_id = ?;",
            (user_id,),
        )

        return build_trading_settings_from_row(row) if row is not None else None

    def require_settings(self, user_id: str) -> TradingSettings:
        settings = self.get_settings(user_id)

        if settings is None:
            raise LookupError(f"Trading settings do not exist for user: {user_id}")

        return settings

    def create_settings(
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
        created_at_utc: str | None = None,
    ) -> TradingSettings:
        if self.get_settings(user_id) is not None:
            raise ValueError(f"Trading settings already exist for user: {user_id}")

        timestamp = created_at_utc or record_utc_now()

        settings = TradingSettings(
            settings_id=settings_id or build_record_id("settings"),
            user_id=normalize_required_text(user_id, "user_id"),
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            execution_mode=execution_mode,
            risk_per_trade_fraction=risk_per_trade_fraction,
            max_daily_loss_fraction=max_daily_loss_fraction,
            max_open_positions=max_open_positions,
            max_daily_trades=max_daily_trades,
            default_timeframe=normalize_required_text(
                default_timeframe,
                "default_timeframe",
            ),
            allow_short=allow_short,
            allow_hedging=allow_hedging,
            notifications_enabled=notifications_enabled,
            metadata=metadata or {},
        )

        self._insert(settings)

        return settings

    def get_or_create_settings(
        self,
        user_id: str,
        created_at_utc: str | None = None,
    ) -> TradingSettings:
        existing = self.get_settings(user_id)

        if existing is not None:
            return existing

        settings = build_default_trading_settings(
            user_id=user_id,
            created_at_utc=created_at_utc,
        )
        self._insert(settings)

        return settings

    def list_settings(
        self,
        execution_mode: ExecutionMode | None = None,
    ) -> tuple[TradingSettings, ...]:
        if execution_mode is None:
            rows = self.database.query_all(
                "SELECT * FROM trading_settings ORDER BY created_at_utc, user_id;"
            )
        else:
            rows = self.database.query_all(
                "SELECT * FROM trading_settings WHERE execution_mode = ? "
                "ORDER BY created_at_utc, user_id;",
                (execution_mode.value,),
            )

        return tuple(build_trading_settings_from_row(row) for row in rows)

    def update_settings(
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
        updated_at_utc: str | None = None,
    ) -> TradingSettings:
        current = self.require_settings(user_id)

        updated = replace(
            current,
            execution_mode=execution_mode or current.execution_mode,
            risk_per_trade_fraction=(
                risk_per_trade_fraction
                if risk_per_trade_fraction is not None
                else current.risk_per_trade_fraction
            ),
            max_daily_loss_fraction=(
                max_daily_loss_fraction
                if max_daily_loss_fraction is not None
                else current.max_daily_loss_fraction
            ),
            max_open_positions=(
                max_open_positions
                if max_open_positions is not None
                else current.max_open_positions
            ),
            max_daily_trades=(
                max_daily_trades
                if max_daily_trades is not None
                else current.max_daily_trades
            ),
            default_timeframe=(
                normalize_required_text(default_timeframe, "default_timeframe")
                if default_timeframe is not None
                else current.default_timeframe
            ),
            allow_short=allow_short if allow_short is not None else current.allow_short,
            allow_hedging=(
                allow_hedging if allow_hedging is not None else current.allow_hedging
            ),
            notifications_enabled=(
                notifications_enabled
                if notifications_enabled is not None
                else current.notifications_enabled
            ),
            metadata=metadata if metadata is not None else current.metadata,
            updated_at_utc=updated_at_utc or record_utc_now(),
        )

        self._update(updated)

        return updated

    def set_execution_mode(
        self,
        user_id: str,
        execution_mode: ExecutionMode,
        updated_at_utc: str | None = None,
    ) -> TradingSettings:
        return self.update_settings(
            user_id=user_id,
            execution_mode=execution_mode,
            updated_at_utc=updated_at_utc,
        )

    def reset_settings(
        self,
        user_id: str,
        updated_at_utc: str | None = None,
    ) -> TradingSettings:
        current = self.require_settings(user_id)

        defaults = build_default_trading_settings(
            user_id=user_id,
            settings_id=current.settings_id,
            created_at_utc=current.created_at_utc,
        )
        reset = replace(defaults, updated_at_utc=updated_at_utc or record_utc_now())

        self._update(reset)

        return reset

    def delete_settings(self, user_id: str) -> bool:
        cursor = self.database.execute(
            "DELETE FROM trading_settings WHERE user_id = ?;",
            (user_id,),
        )

        return cursor.rowcount > 0

    def _insert(self, settings: TradingSettings) -> None:
        self.database.execute(
            """
            INSERT INTO trading_settings (
                settings_id, user_id, execution_mode, risk_per_trade_fraction,
                max_daily_loss_fraction, max_open_positions, max_daily_trades,
                default_timeframe, allow_short, allow_hedging,
                notifications_enabled, created_at_utc, updated_at_utc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                settings.settings_id,
                settings.user_id,
                settings.execution_mode.value,
                settings.risk_per_trade_fraction,
                settings.max_daily_loss_fraction,
                settings.max_open_positions,
                settings.max_daily_trades,
                settings.default_timeframe,
                encode_bool(settings.allow_short),
                encode_bool(settings.allow_hedging),
                encode_bool(settings.notifications_enabled),
                settings.created_at_utc,
                settings.updated_at_utc,
                encode_json_field(settings.metadata),
            ),
        )

    def _update(self, settings: TradingSettings) -> None:
        self.database.execute(
            """
            UPDATE trading_settings
            SET execution_mode = ?, risk_per_trade_fraction = ?,
                max_daily_loss_fraction = ?, max_open_positions = ?,
                max_daily_trades = ?, default_timeframe = ?, allow_short = ?,
                allow_hedging = ?, notifications_enabled = ?,
                updated_at_utc = ?, metadata = ?
            WHERE user_id = ?;
            """,
            (
                settings.execution_mode.value,
                settings.risk_per_trade_fraction,
                settings.max_daily_loss_fraction,
                settings.max_open_positions,
                settings.max_daily_trades,
                settings.default_timeframe,
                encode_bool(settings.allow_short),
                encode_bool(settings.allow_hedging),
                encode_bool(settings.notifications_enabled),
                settings.updated_at_utc,
                encode_json_field(settings.metadata),
                settings.user_id,
            ),
        )


__all__ = [
    "AQOS_TRADING_SETTINGS_VERSION",
    "DEFAULT_MAX_DAILY_LOSS_FRACTION",
    "DEFAULT_MAX_DAILY_TRADES",
    "DEFAULT_MAX_OPEN_POSITIONS",
    "DEFAULT_RISK_PER_TRADE_FRACTION",
    "DEFAULT_TIMEFRAME",
    "EXECUTION_MODE_RANK",
    "ExecutionMode",
    "TradingSettings",
    "TradingSettingsRepository",
    "build_default_trading_settings",
    "build_trading_settings_from_row",
    "execution_mode_allows_orders",
    "execution_mode_rank",
    "resolve_effective_execution_mode",
]
