from __future__ import annotations

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
    ExecutionConstraintSource,
    ExecutionMode,
)


AQOS_FUNDED_RULES_VERSION = "1.0"

FRACTION_PRECISION = 6
LOT_PRECISION = 4

DEFAULT_MAX_DAILY_LOSS_FRACTION = 0.05
DEFAULT_MAX_TOTAL_DRAWDOWN_FRACTION = 0.10
DEFAULT_PROFIT_TARGET_FRACTION = 0.10
DEFAULT_MAX_RISK_PER_TRADE_FRACTION = 0.01
DEFAULT_MIN_LOT_SIZE = 0.01
DEFAULT_MAX_LOT_SIZE = 5.0
DEFAULT_MAX_OPEN_POSITIONS = 3
DEFAULT_MAX_DAILY_TRADES = 10
DEFAULT_MIN_TRADING_DAYS = 5
DEFAULT_NEWS_BLACKOUT_MINUTES = 2
DEFAULT_CONSISTENCY_FRACTION = 0.40


class DrawdownBasis(str, Enum):
    """What the maximum drawdown limit is measured against."""

    STATIC_INITIAL = "static_initial"
    TRAILING_EQUITY = "trailing_equity"
    TRAILING_BALANCE = "trailing_balance"


class FundedRuleStatus(str, Enum):
    ACTIVE = "active"
    BREACHED = "breached"
    PASSED = "passed"
    DISABLED = "disabled"


#: Statuses under which a funded rule set permits no execution at all.
BLOCKING_FUNDED_RULE_STATUSES = (
    FundedRuleStatus.BREACHED,
    FundedRuleStatus.DISABLED,
)


def as_fraction(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)

    return float(value)


def normalize_rule_name(value: str) -> str:
    name = (value or "").strip()

    if not name:
        raise ValueError("name cannot be empty.")

    return name


def normalize_allowed_symbols(symbols: Any) -> list[str]:
    normalized: list[str] = []

    for symbol in symbols or ():
        clean = "".join(str(symbol).split()).upper()

        if not clean:
            raise ValueError("allowed symbol cannot be empty.")

        if clean not in normalized:
            normalized.append(clean)

    return normalized


def funded_rule_field_defaults() -> dict[str, Any]:
    """
    Python-side defaults for the configurable limits.

    SQLAlchemy ``default=`` values are only applied at flush time, so a
    transient rule set would otherwise carry ``None`` for anything the caller
    omitted. For a safety engine that fails in the dangerous direction: a
    ``None`` news restriction reads as "off". These defaults are applied in
    ``__init__`` so an unsaved rule set behaves exactly like a saved one.
    """

    return {
        "execution_mode": ExecutionMode.SIGNAL_ONLY,
        "max_daily_loss_fraction": DEFAULT_MAX_DAILY_LOSS_FRACTION,
        "max_total_drawdown_fraction": DEFAULT_MAX_TOTAL_DRAWDOWN_FRACTION,
        "drawdown_basis": DrawdownBasis.STATIC_INITIAL,
        "profit_target_fraction": DEFAULT_PROFIT_TARGET_FRACTION,
        "max_risk_per_trade_fraction": DEFAULT_MAX_RISK_PER_TRADE_FRACTION,
        "min_lot_size": DEFAULT_MIN_LOT_SIZE,
        "max_lot_size": DEFAULT_MAX_LOT_SIZE,
        "max_open_positions": DEFAULT_MAX_OPEN_POSITIONS,
        "max_daily_trades": DEFAULT_MAX_DAILY_TRADES,
        "min_trading_days": DEFAULT_MIN_TRADING_DAYS,
        "news_restriction_enabled": True,
        "news_blackout_minutes_before": DEFAULT_NEWS_BLACKOUT_MINUTES,
        "news_blackout_minutes_after": DEFAULT_NEWS_BLACKOUT_MINUTES,
        "weekend_holding_allowed": False,
        "consistency_fraction": DEFAULT_CONSISTENCY_FRACTION,
        "allowed_symbols": [],
        "extra_metadata": {},
    }


class FundedRuleFieldsMixin:
    """
    The configurable limits shared by templates and account assignments.

    Keeping them in one mixin means a template and the rules actually applied to
    an account can never drift apart in shape or validation.
    """

    @classmethod
    def field_defaults(cls) -> dict[str, Any]:
        return funded_rule_field_defaults()

    def __init__(self, **kwargs: Any) -> None:
        for field_name, value in self.field_defaults().items():
            kwargs.setdefault(field_name, value)

        super().__init__(**kwargs)

    def assert_no_unset_rule_fields(self) -> None:
        """Guard against a rule silently reading as 'off' because it is None."""

        unset = [
            field_name
            for field_name in funded_rule_field_defaults()
            if field_name != "consistency_fraction"
            and getattr(self, field_name, None) is None
        ]

        if unset:
            raise ValueError(
                "Funded rule fields must never be unset: " + ", ".join(sorted(unset))
            )

    execution_mode: Mapped[ExecutionMode] = mapped_column(
        EnumString(ExecutionMode),
        nullable=False,
        default=ExecutionMode.SIGNAL_ONLY,
    )
    max_daily_loss_fraction: Mapped[float] = mapped_column(
        Numeric(9, FRACTION_PRECISION),
        nullable=False,
        default=DEFAULT_MAX_DAILY_LOSS_FRACTION,
    )
    max_total_drawdown_fraction: Mapped[float] = mapped_column(
        Numeric(9, FRACTION_PRECISION),
        nullable=False,
        default=DEFAULT_MAX_TOTAL_DRAWDOWN_FRACTION,
    )
    drawdown_basis: Mapped[DrawdownBasis] = mapped_column(
        EnumString(DrawdownBasis),
        nullable=False,
        default=DrawdownBasis.STATIC_INITIAL,
    )
    profit_target_fraction: Mapped[float] = mapped_column(
        Numeric(9, FRACTION_PRECISION),
        nullable=False,
        default=DEFAULT_PROFIT_TARGET_FRACTION,
    )
    max_risk_per_trade_fraction: Mapped[float] = mapped_column(
        Numeric(9, FRACTION_PRECISION),
        nullable=False,
        default=DEFAULT_MAX_RISK_PER_TRADE_FRACTION,
    )
    min_lot_size: Mapped[float] = mapped_column(
        Numeric(12, LOT_PRECISION),
        nullable=False,
        default=DEFAULT_MIN_LOT_SIZE,
    )
    max_lot_size: Mapped[float] = mapped_column(
        Numeric(12, LOT_PRECISION),
        nullable=False,
        default=DEFAULT_MAX_LOT_SIZE,
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
    min_trading_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_MIN_TRADING_DAYS,
    )
    news_restriction_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    news_blackout_minutes_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_NEWS_BLACKOUT_MINUTES,
    )
    news_blackout_minutes_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=DEFAULT_NEWS_BLACKOUT_MINUTES,
    )
    weekend_holding_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    consistency_fraction: Mapped[float | None] = mapped_column(
        Numeric(9, FRACTION_PRECISION),
        nullable=True,
        default=DEFAULT_CONSISTENCY_FRACTION,
    )
    allowed_symbols: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    @validates("max_daily_loss_fraction")
    def _validate_daily_loss(self, key: str, value: Any) -> Any:
        if not 0.0 < as_fraction(value) <= 1.0:
            raise ValueError(
                "max_daily_loss_fraction must be greater than 0 and at most 1."
            )

        return value

    @validates("max_total_drawdown_fraction")
    def _validate_total_drawdown(self, key: str, value: Any) -> Any:
        if not 0.0 < as_fraction(value) <= 1.0:
            raise ValueError(
                "max_total_drawdown_fraction must be greater than 0 and at most 1."
            )

        return value

    @validates("max_risk_per_trade_fraction")
    def _validate_risk_per_trade(self, key: str, value: Any) -> Any:
        if not 0.0 < as_fraction(value) <= 1.0:
            raise ValueError(
                "max_risk_per_trade_fraction must be greater than 0 and at most 1."
            )

        return value

    @validates("profit_target_fraction")
    def _validate_profit_target(self, key: str, value: Any) -> Any:
        if as_fraction(value) <= 0.0:
            raise ValueError("profit_target_fraction must be positive.")

        return value

    @validates("min_lot_size")
    def _validate_min_lot_size(self, key: str, value: Any) -> Any:
        if as_fraction(value) <= 0.0:
            raise ValueError("min_lot_size must be positive.")

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

    @validates("min_trading_days")
    def _validate_min_trading_days(self, key: str, value: int) -> int:
        if value < 0:
            raise ValueError("min_trading_days cannot be negative.")

        return value

    @validates("news_blackout_minutes_before", "news_blackout_minutes_after")
    def _validate_news_windows(self, key: str, value: int) -> int:
        if value < 0:
            raise ValueError(f"{key} cannot be negative.")

        return value

    @validates("consistency_fraction")
    def _validate_consistency(self, key: str, value: Any) -> Any:
        if value is None:
            return value

        if not 0.0 < as_fraction(value) <= 1.0:
            raise ValueError(
                "consistency_fraction must be greater than 0 and at most 1."
            )

        return value

    @validates("allowed_symbols")
    def _validate_allowed_symbols(self, key: str, value: Any) -> list[str]:
        return normalize_allowed_symbols(value)

    def validate_consistency(self) -> None:
        """
        Check rules that span more than one column.

        MySQL enforces the same rules with CHECK constraints, so bypassing
        Python still fails at the database.
        """

        if as_fraction(self.max_daily_loss_fraction) > as_fraction(
            self.max_total_drawdown_fraction
        ):
            raise ValueError(
                "max_daily_loss_fraction cannot exceed max_total_drawdown_fraction."
            )

        self.assert_no_unset_rule_fields()

        if as_fraction(self.max_lot_size) < as_fraction(self.min_lot_size):
            raise ValueError("max_lot_size cannot be smaller than min_lot_size.")

    def allows_symbol(self, symbol: str) -> bool:
        if not self.allowed_symbols:
            return True

        return "".join(str(symbol).split()).upper() in self.allowed_symbols

    def rule_values(self) -> dict[str, Any]:
        """The configurable limits, ready to copy from a template to an account."""

        return {
            "execution_mode": self.execution_mode,
            "max_daily_loss_fraction": as_fraction(self.max_daily_loss_fraction),
            "max_total_drawdown_fraction": as_fraction(
                self.max_total_drawdown_fraction
            ),
            "drawdown_basis": self.drawdown_basis,
            "profit_target_fraction": as_fraction(self.profit_target_fraction),
            "max_risk_per_trade_fraction": as_fraction(
                self.max_risk_per_trade_fraction
            ),
            "min_lot_size": as_fraction(self.min_lot_size),
            "max_lot_size": as_fraction(self.max_lot_size),
            "max_open_positions": self.max_open_positions,
            "max_daily_trades": self.max_daily_trades,
            "min_trading_days": self.min_trading_days,
            "news_restriction_enabled": bool(self.news_restriction_enabled),
            "news_blackout_minutes_before": self.news_blackout_minutes_before,
            "news_blackout_minutes_after": self.news_blackout_minutes_after,
            "weekend_holding_allowed": bool(self.weekend_holding_allowed),
            "consistency_fraction": (
                as_fraction(self.consistency_fraction)
                if self.consistency_fraction is not None
                else None
            ),
            "allowed_symbols": list(self.allowed_symbols or []),
        }

    def rule_values_dict(self) -> dict[str, Any]:
        payload = self.rule_values()
        payload["execution_mode"] = (
            self.execution_mode.value if self.execution_mode else None
        )
        payload["drawdown_basis"] = (
            self.drawdown_basis.value if self.drawdown_basis else None
        )

        return payload


class FundedRuleTemplate(FundedRuleFieldsMixin, AqosBase):
    """
    A reusable, named set of funded account limits.

    AQOS ships no firm-specific templates: a template is whatever a user or
    admin configures and names.
    """

    __tablename__ = "funded_rule_templates"
    __table_args__ = AQOS_TABLE_ARGS

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(191), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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

    @classmethod
    def field_defaults(cls) -> dict[str, Any]:
        return {**funded_rule_field_defaults(), "is_active": True}

    @validates("name")
    def _validate_name(self, key: str, value: str) -> str:
        return normalize_rule_name(value)

    def to_dict(self) -> dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "is_active": bool(self.is_active),
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "updated_at_utc": (
                self.updated_at_utc.isoformat() if self.updated_at_utc else None
            ),
            "metadata": self.extra_metadata or {},
            **self.rule_values_dict(),
        }

    def __repr__(self) -> str:
        return f"FundedRuleTemplate(name={self.name!r})"


class FundedAccountRules(FundedRuleFieldsMixin, AqosBase):
    """
    The funded limits applied to one trading account.

    Values are copied from a template rather than referenced, so editing a
    template never silently changes the rules an account is already trading
    under. ``template_id`` is kept only for provenance.
    """

    __tablename__ = "funded_account_rules"
    __table_args__ = AQOS_TABLE_ARGS

    rules_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    template_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("funded_rule_templates.template_id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[FundedRuleStatus] = mapped_column(
        EnumString(FundedRuleStatus),
        nullable=False,
        default=FundedRuleStatus.ACTIVE,
    )
    breached_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    breach_reason: Mapped[str | None] = mapped_column(String(512), nullable=True)
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

    @classmethod
    def field_defaults(cls) -> dict[str, Any]:
        return {
            **funded_rule_field_defaults(),
            "status": FundedRuleStatus.ACTIVE,
        }

    @property
    def is_blocking(self) -> bool:
        return self.status in BLOCKING_FUNDED_RULE_STATUSES

    @property
    def is_breached(self) -> bool:
        return self.status == FundedRuleStatus.BREACHED

    def validate_breach_record(self) -> None:
        """A breached rule set must always carry the moment it broke."""

        if self.status == FundedRuleStatus.BREACHED and self.breached_at_utc is None:
            raise ValueError(
                "breached_at_utc is required when funded rules are breached."
            )

    def execution_ceiling(self) -> ExecutionMode:
        """
        The strictest mode these funded rules can contribute.

        Breached or disabled rules contribute ``DISABLED``: a funded account
        that has broken its limits must never become executable again just
        because another constraint was relaxed.
        """

        if self.is_blocking:
            return ExecutionMode.DISABLED

        return self.execution_mode

    def execution_constraint(self) -> ExecutionConstraint:
        """The funded-rule ceiling, ready for the execution mode resolver."""

        if self.status == FundedRuleStatus.BREACHED:
            reason = self.breach_reason or "Funded account rules are breached."
        elif self.status == FundedRuleStatus.DISABLED:
            reason = "Funded account rules are disabled."
        else:
            reason = f"Funded rule execution mode is {self.execution_mode.value}."

        return ExecutionConstraint(
            source=ExecutionConstraintSource.FUNDED_RULE,
            ceiling=self.execution_ceiling(),
            reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_id": self.rules_id,
            "account_id": self.account_id,
            "template_id": self.template_id,
            "status": self.status.value if self.status else None,
            "execution_ceiling": self.execution_ceiling().value,
            "is_blocking": self.is_blocking,
            "is_breached": self.is_breached,
            "breached_at_utc": (
                self.breached_at_utc.isoformat() if self.breached_at_utc else None
            ),
            "breach_reason": self.breach_reason,
            "created_at_utc": (
                self.created_at_utc.isoformat() if self.created_at_utc else None
            ),
            "updated_at_utc": (
                self.updated_at_utc.isoformat() if self.updated_at_utc else None
            ),
            "metadata": self.extra_metadata or {},
            **self.rule_values_dict(),
        }

    def __repr__(self) -> str:
        return (
            f"FundedAccountRules(account_id={self.account_id!r}, "
            f"status={self.status.value if self.status else None!r})"
        )


__all__ = [
    "AQOS_FUNDED_RULES_VERSION",
    "BLOCKING_FUNDED_RULE_STATUSES",
    "DEFAULT_CONSISTENCY_FRACTION",
    "DEFAULT_MAX_DAILY_TRADES",
    "DEFAULT_MAX_DAILY_LOSS_FRACTION",
    "DEFAULT_MAX_LOT_SIZE",
    "DEFAULT_MAX_OPEN_POSITIONS",
    "DEFAULT_MAX_RISK_PER_TRADE_FRACTION",
    "DEFAULT_MAX_TOTAL_DRAWDOWN_FRACTION",
    "DEFAULT_MIN_LOT_SIZE",
    "DEFAULT_MIN_TRADING_DAYS",
    "DEFAULT_NEWS_BLACKOUT_MINUTES",
    "DEFAULT_PROFIT_TARGET_FRACTION",
    "DrawdownBasis",
    "FundedAccountRules",
    "FundedRuleFieldsMixin",
    "FundedRuleStatus",
    "FundedRuleTemplate",
    "as_fraction",
    "normalize_allowed_symbols",
    "normalize_rule_name",
]
