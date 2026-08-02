from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.types import EnumString, database_utc_now
from aqos.execution_policy.modes import (
    ExecutionConstraint,
    ExecutionMode,
    build_user_execution_constraint,
    execution_mode_allows_orders,
)


AQOS_TRADING_SETTINGS_VERSION = "1.0"

DEFAULT_RISK_PER_TRADE_FRACTION = 0.01
DEFAULT_MAX_DAILY_LOSS_FRACTION = 0.05
DEFAULT_MAX_OPEN_POSITIONS = 3
DEFAULT_MAX_DAILY_TRADES = 10
DEFAULT_TIMEFRAME = "H1"

FRACTION_PRECISION = 6


class SymbolPreferenceKind(str, Enum):
    WATCHLIST = "watchlist"
    PREFERRED = "preferred"
    BLOCKED = "blocked"
    NOTIFICATION = "notification"


#: Blocking a symbol removes it from these lists so it can never be traded or
#: alerted on by accident.
KINDS_CLEARED_ON_BLOCK = (
    SymbolPreferenceKind.PREFERRED,
    SymbolPreferenceKind.NOTIFICATION,
)


def normalize_symbol(value: str) -> str:
    symbol = re.sub(r"\s+", "", value or "").upper()

    if not symbol:
        raise ValueError("symbol cannot be empty.")

    return symbol


def normalize_symbol_list(symbols: Any) -> tuple[str, ...]:
    """Upper-case, de-duplicate and preserve the caller's ordering."""

    normalized: list[str] = []

    for symbol in symbols or ():
        clean = normalize_symbol(symbol)

        if clean not in normalized:
            normalized.append(clean)

    return tuple(normalized)


def normalize_required_text(value: str, field_name: str) -> str:
    text = (value or "").strip()

    if not text:
        raise ValueError(f"{field_name} cannot be empty.")

    return text


def as_fraction(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)

    return float(value)


class TradingSettings(AqosBase):
    """
    User-level trading settings.

    ``execution_mode`` is the user's ceiling on autonomy, not a command: the
    mode that actually applies to a signal is resolved by
    ``aqos.execution_policy`` against every constraint that applies.
    """

    __tablename__ = "trading_settings"
    __table_args__ = AQOS_TABLE_ARGS

    settings_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        EnumString(ExecutionMode),
        nullable=False,
        default=ExecutionMode.SIGNAL_ONLY,
    )
    risk_per_trade_fraction: Mapped[float] = mapped_column(
        Numeric(9, FRACTION_PRECISION),
        nullable=False,
        default=DEFAULT_RISK_PER_TRADE_FRACTION,
    )
    max_daily_loss_fraction: Mapped[float] = mapped_column(
        Numeric(9, FRACTION_PRECISION),
        nullable=False,
        default=DEFAULT_MAX_DAILY_LOSS_FRACTION,
    )
    max_open_positions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MAX_OPEN_POSITIONS,
    )
    max_daily_trades: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MAX_DAILY_TRADES,
    )
    default_timeframe: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=DEFAULT_TIMEFRAME,
    )
    allow_short: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    allow_hedging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notifications_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        onupdate=database_utc_now,
        server_default=func.now(),
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    @validates("risk_per_trade_fraction")
    def _validate_risk_per_trade(self, key: str, value: Any) -> Any:
        if not 0.0 < as_fraction(value) <= 1.0:
            raise ValueError(
                "risk_per_trade_fraction must be greater than 0 and at most 1."
            )

        return value

    @validates("max_daily_loss_fraction")
    def _validate_max_daily_loss(self, key: str, value: Any) -> Any:
        if not 0.0 < as_fraction(value) <= 1.0:
            raise ValueError(
                "max_daily_loss_fraction must be greater than 0 and at most 1."
            )

        return value

    @validates("max_open_positions")
    def _validate_max_open_positions(self, key: str, value: int) -> int:
        if value < 1:
            raise ValueError("max_open_positions must be at least 1.")

        return value

    @validates("max_daily_trades")
    def _validate_max_daily_trades(self, key: str, value: int) -> int:
        if value < 1:
            raise ValueError("max_daily_trades must be at least 1.")

        return value

    @validates("default_timeframe")
    def _validate_default_timeframe(self, key: str, value: str) -> str:
        return normalize_required_text(value, "default_timeframe")

    def validate_consistency(self) -> None:
        """
        Check rules that span more than one column.

        Field validators cannot see sibling values reliably during construction,
        so this runs explicitly before a write. MySQL enforces the same rule with
        a CHECK constraint, so a bypass still fails at the database.
        """

        if as_fraction(self.max_daily_loss_fraction) < as_fraction(
            self.risk_per_trade_fraction
        ):
            raise ValueError(
                "max_daily_loss_fraction cannot be smaller than "
                "risk_per_trade_fraction."
            )

    @property
    def risk_per_trade(self) -> float:
        return as_fraction(self.risk_per_trade_fraction)

    @property
    def max_daily_loss(self) -> float:
        return as_fraction(self.max_daily_loss_fraction)

    @property
    def allows_orders(self) -> bool:
        """Whether the user ceiling alone would permit orders."""

        return execution_mode_allows_orders(self.execution_mode)

    @property
    def max_concurrent_risk_fraction(self) -> float:
        return min(1.0, self.risk_per_trade * self.max_open_positions)

    def execution_constraint(self) -> ExecutionConstraint:
        """The user-level ceiling, ready for the execution mode resolver."""

        return build_user_execution_constraint(
            ceiling=self.execution_mode,
            reason=f"User execution mode is {self.execution_mode.value}.",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "settings_id": self.settings_id,
            "user_id": self.user_id,
            "execution_mode": (
                self.execution_mode.value if self.execution_mode else None
            ),
            "risk_per_trade_fraction": self.risk_per_trade,
            "max_daily_loss_fraction": self.max_daily_loss,
            "max_open_positions": self.max_open_positions,
            "max_daily_trades": self.max_daily_trades,
            "default_timeframe": self.default_timeframe,
            "allow_short": bool(self.allow_short),
            "allow_hedging": bool(self.allow_hedging),
            "notifications_enabled": bool(self.notifications_enabled),
            "allows_orders": self.allows_orders,
            "max_concurrent_risk_fraction": self.max_concurrent_risk_fraction,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "updated_at_utc": (
                self.updated_at_utc.isoformat() if self.updated_at_utc else None
            ),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return f"TradingSettings(user_id={self.user_id!r})"


class SymbolPreference(AqosBase):
    """One symbol on one of a user's lists."""

    __tablename__ = "symbol_preferences"
    __table_args__ = AQOS_TABLE_ARGS

    preference_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[SymbolPreferenceKind] = mapped_column(
        EnumString(SymbolPreferenceKind),
        nullable=False,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    updated_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        onupdate=database_utc_now,
        server_default=func.now(),
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    @validates("symbol")
    def _validate_symbol(self, key: str, value: str) -> str:
        return normalize_symbol(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "preference_id": self.preference_id,
            "user_id": self.user_id,
            "symbol": self.symbol,
            "kind": self.kind.value if self.kind else None,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "updated_at_utc": (
                self.updated_at_utc.isoformat() if self.updated_at_utc else None
            ),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return (
            f"SymbolPreference(user_id={self.user_id!r}, symbol={self.symbol!r}, "
            f"kind={self.kind.value if self.kind else None!r})"
        )


class SymbolPreferenceSummary:
    """Read model over a user's symbol lists."""

    def __init__(
        self,
        user_id: str,
        watchlist: tuple[str, ...] = (),
        preferred: tuple[str, ...] = (),
        blocked: tuple[str, ...] = (),
        notification: tuple[str, ...] = (),
    ) -> None:
        self.user_id = user_id
        self.watchlist = watchlist
        self.preferred = preferred
        self.blocked = blocked
        self.notification = notification

    @property
    def tradable(self) -> tuple[str, ...]:
        """Watchlist symbols that are not blocked."""

        blocked = set(self.blocked)

        return tuple(symbol for symbol in self.watchlist if symbol not in blocked)

    @property
    def notifiable(self) -> tuple[str, ...]:
        """Notification symbols that are not blocked."""

        blocked = set(self.blocked)

        return tuple(symbol for symbol in self.notification if symbol not in blocked)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "watchlist": list(self.watchlist),
            "preferred": list(self.preferred),
            "blocked": list(self.blocked),
            "notification": list(self.notification),
            "tradable": list(self.tradable),
            "notifiable": list(self.notifiable),
        }


__all__ = [
    "AQOS_TRADING_SETTINGS_VERSION",
    "DEFAULT_MAX_DAILY_LOSS_FRACTION",
    "DEFAULT_MAX_DAILY_TRADES",
    "DEFAULT_MAX_OPEN_POSITIONS",
    "DEFAULT_RISK_PER_TRADE_FRACTION",
    "DEFAULT_TIMEFRAME",
    "KINDS_CLEARED_ON_BLOCK",
    "SymbolPreference",
    "SymbolPreferenceKind",
    "SymbolPreferenceSummary",
    "TradingSettings",
    "as_fraction",
    "normalize_required_text",
    "normalize_symbol",
    "normalize_symbol_list",
]
