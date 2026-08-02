from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.types import EnumString, database_utc_now


AQOS_SIGNALS_VERSION = "1.0"

MONEY_PRECISION = 8
CONFIDENCE_PRECISION = 6


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class SignalSource(str, Enum):
    RULE_BASED = "rule_based"
    ML_MODEL = "ml_model"
    MANUAL = "manual"
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"
    EXTERNAL_WEBHOOK = "external_webhook"


class SignalStatus(str, Enum):
    GENERATED = "generated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    MISSED = "missed"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: The only statuses a signal may still move on from.
OPEN_SIGNAL_STATUSES = (
    SignalStatus.GENERATED,
    SignalStatus.PENDING_APPROVAL,
    SignalStatus.APPROVED,
)

#: Statuses a signal can never leave.
TERMINAL_SIGNAL_STATUSES = (
    SignalStatus.REJECTED,
    SignalStatus.MISSED,
    SignalStatus.EXPIRED,
    SignalStatus.EXECUTED,
    SignalStatus.FAILED,
    SignalStatus.CANCELLED,
)

#: Statuses that mean the signal never reached the market.
UNFILLED_SIGNAL_STATUSES = (
    SignalStatus.REJECTED,
    SignalStatus.MISSED,
    SignalStatus.EXPIRED,
    SignalStatus.FAILED,
    SignalStatus.CANCELLED,
)

#: Statuses a signal may be created in.
CREATABLE_SIGNAL_STATUSES = (
    SignalStatus.GENERATED,
    SignalStatus.PENDING_APPROVAL,
)

SIGNAL_TRANSITIONS: dict[SignalStatus, tuple[SignalStatus, ...]] = {
    SignalStatus.GENERATED: (
        SignalStatus.PENDING_APPROVAL,
        SignalStatus.APPROVED,
        SignalStatus.REJECTED,
        SignalStatus.MISSED,
        SignalStatus.EXPIRED,
        SignalStatus.CANCELLED,
    ),
    SignalStatus.PENDING_APPROVAL: (
        SignalStatus.APPROVED,
        SignalStatus.REJECTED,
        SignalStatus.MISSED,
        SignalStatus.EXPIRED,
        SignalStatus.CANCELLED,
    ),
    SignalStatus.APPROVED: (
        SignalStatus.EXECUTED,
        SignalStatus.FAILED,
        SignalStatus.MISSED,
        SignalStatus.EXPIRED,
        SignalStatus.CANCELLED,
    ),
    SignalStatus.REJECTED: (),
    SignalStatus.MISSED: (),
    SignalStatus.EXPIRED: (),
    SignalStatus.EXECUTED: (),
    SignalStatus.FAILED: (),
    SignalStatus.CANCELLED: (),
}


class InvalidSignalTransitionError(ValueError):
    """Raised when a signal is asked to make a transition that is not allowed."""


def is_terminal_signal_status(status: SignalStatus) -> bool:
    return status in TERMINAL_SIGNAL_STATUSES


def can_transition_signal(
    from_status: SignalStatus,
    to_status: SignalStatus,
) -> bool:
    return to_status in SIGNAL_TRANSITIONS.get(from_status, ())


def validate_signal_transition(
    from_status: SignalStatus,
    to_status: SignalStatus,
) -> None:
    if can_transition_signal(from_status, to_status):
        return

    raise InvalidSignalTransitionError(
        f"Signal cannot move from {from_status.value} to {to_status.value}."
    )


def normalize_signal_symbol(value: str) -> str:
    symbol = re.sub(r"\s+", "", value or "").upper()

    if not symbol:
        raise ValueError("symbol cannot be empty.")

    return symbol


def normalize_required_text(value: str, field_name: str) -> str:
    text = (value or "").strip()

    if not text:
        raise ValueError(f"{field_name} cannot be empty.")

    return text


def as_number(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)

    return float(value)


def signal_field_defaults() -> dict[str, Any]:
    """
    Python-side defaults for signal fields.

    SQLAlchemy ``default=`` only applies at flush time, so a transient signal
    would otherwise carry ``None`` for its status and every lifecycle check
    would misread it. Safety-relevant fields are filled in ``__init__``.
    """

    return {
        "status": SignalStatus.GENERATED,
        "extra_metadata": {},
    }


class TradingSignal(AqosBase):
    """
    One trading signal and its current lifecycle status.

    Status only ever changes through the repository, which validates the
    transition and appends a ``SignalEvent``.
    """

    __tablename__ = "trading_signals"
    __table_args__ = AQOS_TABLE_ARGS

    signal_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(16), nullable=False)
    action: Mapped[SignalAction] = mapped_column(
        EnumString(SignalAction, length=16),
        nullable=False,
    )
    status: Mapped[SignalStatus] = mapped_column(
        EnumString(SignalStatus),
        nullable=False,
        default=SignalStatus.GENERATED,
    )
    source: Mapped[SignalSource] = mapped_column(
        EnumString(SignalSource),
        nullable=False,
    )
    confidence: Mapped[float | None] = mapped_column(
        Numeric(9, CONFIDENCE_PRECISION),
        nullable=True,
    )
    entry_price: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    stop_loss: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    take_profit: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    strategy_name: Mapped[str | None] = mapped_column(String(191), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(191), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(191), nullable=True)
    generated_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
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

    #: The audit trail. Declaring the relationship tells the unit of work that a
    #: signal must be inserted before any event that references it.
    events: Mapped[list["SignalEvent"]] = relationship(
        back_populates="signal",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SignalEvent.occurred_at_utc",
    )

    def __init__(self, **kwargs: Any) -> None:
        for field_name, value in signal_field_defaults().items():
            kwargs.setdefault(field_name, value)

        super().__init__(**kwargs)

    @validates("symbol")
    def _validate_symbol(self, key: str, value: str) -> str:
        return normalize_signal_symbol(value)

    @validates("timeframe")
    def _validate_timeframe(self, key: str, value: str) -> str:
        return normalize_required_text(value, "timeframe")

    @validates("confidence")
    def _validate_confidence(self, key: str, value: Any) -> Any:
        if value is None:
            return value

        if not 0.0 <= as_number(value) <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")

        return value

    @validates("entry_price", "stop_loss", "take_profit")
    def _validate_price(self, key: str, value: Any) -> Any:
        if value is None:
            return value

        if as_number(value) <= 0:
            raise ValueError(f"{key} must be positive.")

        return value

    def assert_no_unset_lifecycle_fields(self) -> None:
        """
        Guard against a lifecycle field silently reading as absent.

        A signal with no status or source cannot be evaluated safely, so an
        unset value is rejected rather than defaulted at read time.
        """

        unset = [
            field_name
            for field_name in (
                "signal_id",
                "user_id",
                "symbol",
                "timeframe",
                "action",
                "status",
                "source",
                "generated_at_utc",
            )
            if getattr(self, field_name, None) is None
        ]

        if unset:
            raise ValueError(
                "Signal lifecycle fields must never be unset: "
                + ", ".join(sorted(unset))
            )

    def validate_traceability(self) -> None:
        """A signal must be traceable back to whatever produced it."""

        self.assert_no_unset_lifecycle_fields()

        if self.source == SignalSource.ML_MODEL and not self.model_id:
            raise ValueError("model_id is required for model generated signals.")

        if self.source == SignalSource.RULE_BASED and not self.strategy_name:
            raise ValueError(
                "strategy_name is required for rule based signals."
            )

        if (
            self.expires_at_utc is not None
            and self.expires_at_utc <= self.generated_at_utc
        ):
            raise ValueError("expires_at_utc must be after generated_at_utc.")

    @property
    def is_terminal(self) -> bool:
        return is_terminal_signal_status(self.status)

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_SIGNAL_STATUSES

    @property
    def reached_market(self) -> bool:
        return self.status == SignalStatus.EXECUTED

    @property
    def allowed_transitions(self) -> tuple[SignalStatus, ...]:
        return SIGNAL_TRANSITIONS.get(self.status, ())

    def is_expired(self, now_utc: datetime | None = None) -> bool:
        if self.expires_at_utc is None:
            return False

        return self.expires_at_utc <= (now_utc or database_utc_now())

    def can_transition_to(self, to_status: SignalStatus) -> bool:
        return can_transition_signal(self.status, to_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "action": self.action.value if self.action else None,
            "status": self.status.value if self.status else None,
            "source": self.source.value if self.source else None,
            "confidence": (
                as_number(self.confidence) if self.confidence is not None else None
            ),
            "entry_price": (
                as_number(self.entry_price) if self.entry_price is not None else None
            ),
            "stop_loss": (
                as_number(self.stop_loss) if self.stop_loss is not None else None
            ),
            "take_profit": (
                as_number(self.take_profit) if self.take_profit is not None else None
            ),
            "strategy_name": self.strategy_name,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "generated_at_utc": (
                self.generated_at_utc.isoformat() if self.generated_at_utc else None
            ),
            "expires_at_utc": (
                self.expires_at_utc.isoformat() if self.expires_at_utc else None
            ),
            "status_reason": self.status_reason,
            "is_terminal": self.is_terminal,
            "is_open": self.is_open,
            "reached_market": self.reached_market,
            "allowed_transitions": [
                status.value for status in self.allowed_transitions
            ],
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
            f"TradingSignal(signal_id={self.signal_id!r}, symbol={self.symbol!r}, "
            f"status={self.status.value if self.status else None!r})"
        )


class SignalEvent(AqosBase):
    """
    One immutable row of a signal's audit trail.

    Events are appended, never updated: they are the record of how a signal
    reached its current status.
    """

    __tablename__ = "signal_events"
    __table_args__ = AQOS_TABLE_ARGS

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    signal_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_signals.signal_id", ondelete="CASCADE"),
        nullable=False,
    )
    from_status: Mapped[SignalStatus | None] = mapped_column(
        EnumString(SignalStatus),
        nullable=True,
    )
    to_status: Mapped[SignalStatus] = mapped_column(
        EnumString(SignalStatus),
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
    actor: Mapped[str | None] = mapped_column(String(191), nullable=True)
    occurred_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
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

    signal: Mapped["TradingSignal"] = relationship(back_populates="events")

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    @property
    def is_creation(self) -> bool:
        return self.from_status is None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "signal_id": self.signal_id,
            "from_status": self.from_status.value if self.from_status else None,
            "to_status": self.to_status.value if self.to_status else None,
            "reason": self.reason,
            "actor": self.actor,
            "is_creation": self.is_creation,
            "occurred_at_utc": (
                self.occurred_at_utc.isoformat() if self.occurred_at_utc else None
            ),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return (
            f"SignalEvent(signal_id={self.signal_id!r}, "
            f"to_status={self.to_status.value if self.to_status else None!r})"
        )


__all__ = [
    "AQOS_SIGNALS_VERSION",
    "CREATABLE_SIGNAL_STATUSES",
    "InvalidSignalTransitionError",
    "OPEN_SIGNAL_STATUSES",
    "SIGNAL_TRANSITIONS",
    "SignalAction",
    "SignalEvent",
    "SignalSource",
    "SignalStatus",
    "TERMINAL_SIGNAL_STATUSES",
    "TradingSignal",
    "UNFILLED_SIGNAL_STATUSES",
    "as_number",
    "can_transition_signal",
    "is_terminal_signal_status",
    "normalize_required_text",
    "normalize_signal_symbol",
    "signal_field_defaults",
    "validate_signal_transition",
]
