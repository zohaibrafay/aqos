from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from aqos.account_analytics.metrics import (
    ReasonMetrics,
    SignalMetrics,
    TradeMetrics,
)
from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.types import EnumString, database_utc_now


AQOS_ACCOUNT_ANALYTICS_MODELS_VERSION = "1.0"


class AnalyticsScope(str, Enum):
    ACCOUNT = "account"
    USER = "user"


class AccountAnalyticsError(ValueError):
    """Raised when an analytics result cannot be represented honestly."""


@dataclass(frozen=True)
class AccountAnalytics:
    """
    A calculated analytics result.

    Trade metrics carry their own availability, so a consumer can always tell a
    measured zero from an absent measurement.
    """

    scope: AnalyticsScope
    user_id: str
    calculated_at_utc: datetime
    account_id: str | None = None
    period_start_utc: datetime | None = None
    period_end_utc: datetime | None = None
    signal_metrics: SignalMetrics = dataclass_field(default_factory=SignalMetrics)
    reason_metrics: ReasonMetrics = dataclass_field(default_factory=ReasonMetrics)
    trade_metrics: TradeMetrics = dataclass_field(
        default_factory=TradeMetrics.unavailable
    )
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise AccountAnalyticsError("user_id cannot be empty.")

        if self.scope == AnalyticsScope.ACCOUNT and not self.account_id:
            raise AccountAnalyticsError(
                "account_id is required for account scoped analytics."
            )

        if (
            self.period_start_utc is not None
            and self.period_end_utc is not None
            and self.period_end_utc < self.period_start_utc
        ):
            raise AccountAnalyticsError(
                "period_end_utc cannot be before period_start_utc."
            )

    @property
    def has_trade_metrics(self) -> bool:
        return self.trade_metrics.is_available

    def to_dict(self) -> dict[str, Any]:
        return {
            "scope": self.scope.value,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "period_start_utc": (
                self.period_start_utc.isoformat() if self.period_start_utc else None
            ),
            "period_end_utc": (
                self.period_end_utc.isoformat() if self.period_end_utc else None
            ),
            "calculated_at_utc": self.calculated_at_utc.isoformat(),
            "has_trade_metrics": self.has_trade_metrics,
            "signal_metrics": self.signal_metrics.to_dict(),
            "reason_metrics": self.reason_metrics.to_dict(),
            "trade_metrics": self.trade_metrics.to_dict(),
            "metadata": self.extra_metadata,
        }


class AccountAnalyticsSnapshot(AqosBase):
    """
    A persisted analytics result.

    Headline metrics are columns so they can be queried and constrained; the
    full result is kept in ``payload_json``.
    """

    __tablename__ = "account_analytics_snapshots"
    __table_args__ = AQOS_TABLE_ARGS

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=True,
    )
    scope: Mapped[AnalyticsScope] = mapped_column(
        EnumString(AnalyticsScope, length=16),
        nullable=False,
    )
    period_start_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    period_end_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    calculated_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    signals_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_approved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_missed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_expired: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_executed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    execution_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    rejection_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    missed_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    reason_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason_blocking_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    reason_critical_total: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    trade_metrics_available: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    total_trades: Mapped[int | None] = mapped_column(Integer, nullable=True)
    win_rate: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    net_pnl: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    profit_factor: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    max_drawdown: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    created_at_utc: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=database_utc_now,
        server_default=func.now(),
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("trade_metrics_available", False)
        kwargs.setdefault("payload_json", {})
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    @validates("execution_rate", "rejection_rate", "missed_rate", "win_rate")
    def _validate_fraction(self, key: str, value: Any) -> Any:
        if value is None:
            return value

        number = float(value) if not isinstance(value, Decimal) else float(value)

        if not 0.0 <= number <= 1.0:
            raise AccountAnalyticsError(f"{key} must be between 0 and 1.")

        return value

    def assert_trade_metrics_are_honest(self) -> None:
        """
        Refuse a snapshot that reports trade results it does not have.

        Storing zeros without a trade source would make an account with no
        trading history indistinguishable from one that traded and broke even.
        """

        if self.trade_metrics_available:
            return

        populated = [
            field_name
            for field_name in (
                "total_trades",
                "win_rate",
                "net_pnl",
                "profit_factor",
                "max_drawdown",
            )
            if getattr(self, field_name, None) is not None
        ]

        if populated:
            raise AccountAnalyticsError(
                "Trade metrics are unavailable, so these must stay unset: "
                + ", ".join(sorted(populated))
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "scope": self.scope.value if self.scope else None,
            "period_start_utc": (
                self.period_start_utc.isoformat() if self.period_start_utc else None
            ),
            "period_end_utc": (
                self.period_end_utc.isoformat() if self.period_end_utc else None
            ),
            "calculated_at_utc": (
                self.calculated_at_utc.isoformat() if self.calculated_at_utc else None
            ),
            "signals_received": self.signals_received,
            "signals_approved": self.signals_approved,
            "signals_rejected": self.signals_rejected,
            "signals_missed": self.signals_missed,
            "signals_expired": self.signals_expired,
            "signals_executed": self.signals_executed,
            "signals_failed": self.signals_failed,
            "execution_rate": (
                float(self.execution_rate) if self.execution_rate is not None else None
            ),
            "rejection_rate": (
                float(self.rejection_rate) if self.rejection_rate is not None else None
            ),
            "missed_rate": (
                float(self.missed_rate) if self.missed_rate is not None else None
            ),
            "reason_total": self.reason_total,
            "reason_blocking_total": self.reason_blocking_total,
            "reason_critical_total": self.reason_critical_total,
            "trade_metrics_available": bool(self.trade_metrics_available),
            "total_trades": self.total_trades,
            "win_rate": float(self.win_rate) if self.win_rate is not None else None,
            "net_pnl": float(self.net_pnl) if self.net_pnl is not None else None,
            "profit_factor": (
                float(self.profit_factor) if self.profit_factor is not None else None
            ),
            "max_drawdown": (
                float(self.max_drawdown) if self.max_drawdown is not None else None
            ),
            "payload": self.payload_json or {},
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return (
            f"AccountAnalyticsSnapshot(snapshot_id={self.snapshot_id!r}, "
            f"scope={self.scope.value if self.scope else None!r})"
        )


__all__ = [
    "AQOS_ACCOUNT_ANALYTICS_MODELS_VERSION",
    "AccountAnalytics",
    "AccountAnalyticsError",
    "AccountAnalyticsSnapshot",
    "AnalyticsScope",
]
