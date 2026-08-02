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
    execution_mode_allows_orders,
)


AQOS_ACCOUNTS_VERSION = "1.0"

MONEY_PRECISION = 8
DEFAULT_ACCOUNT_CURRENCY = "USD"


class AccountType(str, Enum):
    """What kind of capital the account holds."""

    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"
    FUNDED = "funded"


class BrokerKind(str, Enum):
    """Where the account is executed. Independent of the account type."""

    PAPER = "paper"
    MT5 = "mt5"
    BINANCE = "binance"
    MANUAL = "manual"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


#: Account types where real capital is at stake.
REAL_MONEY_ACCOUNT_TYPES = (AccountType.LIVE, AccountType.FUNDED)

#: Account types that may never be created already auto trading.
AUTO_TRADE_GUARDED_ACCOUNT_TYPES = REAL_MONEY_ACCOUNT_TYPES

#: The only status under which an account may act on a signal.
TRADEABLE_ACCOUNT_STATUSES = (AccountStatus.ACTIVE,)


def is_real_money_account(account_type: AccountType) -> bool:
    return account_type in REAL_MONEY_ACCOUNT_TYPES


def default_execution_mode_for_account(account_type: AccountType) -> ExecutionMode:
    """Real-money accounts always start in the safest usable mode."""

    if is_real_money_account(account_type):
        return ExecutionMode.SIGNAL_ONLY

    return ExecutionMode.MANUAL_APPROVAL


def normalize_account_name(value: str) -> str:
    name = (value or "").strip()

    if not name:
        raise ValueError("name cannot be empty.")

    return name


def normalize_account_currency(value: str) -> str:
    currency = (value or "").strip().upper()

    if len(currency) != 3 or not currency.isalpha():
        raise ValueError(f"Currency must be a 3 letter code: {value}")

    return currency


def as_amount(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)

    return float(value)


class TradingAccount(AqosBase):
    """
    One trading account owned by a user.

    ``execution_mode`` is this account's ceiling on autonomy. It is combined
    with the user ceiling, and later with funded rules, model promotion status
    and the risk engine, by ``aqos.execution_policy``.
    """

    __tablename__ = "trading_accounts"
    __table_args__ = AQOS_TABLE_ARGS

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(191), nullable=False)
    account_type: Mapped[AccountType] = mapped_column(
        EnumString(AccountType),
        nullable=False,
    )
    broker: Mapped[BrokerKind] = mapped_column(
        EnumString(BrokerKind),
        nullable=False,
    )
    status: Mapped[AccountStatus] = mapped_column(
        EnumString(AccountStatus),
        nullable=False,
        default=AccountStatus.ACTIVE,
    )
    execution_mode: Mapped[ExecutionMode] = mapped_column(
        EnumString(ExecutionMode),
        nullable=False,
        default=ExecutionMode.SIGNAL_ONLY,
    )
    auto_trade_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default=DEFAULT_ACCOUNT_CURRENCY,
    )
    initial_balance: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    current_balance: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    equity: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    leverage: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    broker_account_ref: Mapped[str | None] = mapped_column(String(191), nullable=True)
    broker_credential_ref: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
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

    @validates("name")
    def _validate_name(self, key: str, value: str) -> str:
        return normalize_account_name(value)

    @validates("currency")
    def _validate_currency(self, key: str, value: str) -> str:
        return normalize_account_currency(value)

    @validates("initial_balance")
    def _validate_initial_balance(self, key: str, value: Any) -> Any:
        if as_amount(value) <= 0:
            raise ValueError("initial_balance must be positive.")

        return value

    @validates("current_balance")
    def _validate_current_balance(self, key: str, value: Any) -> Any:
        if as_amount(value) < 0:
            raise ValueError("current_balance cannot be negative.")

        return value

    @validates("equity")
    def _validate_equity(self, key: str, value: Any) -> Any:
        if as_amount(value) < 0:
            raise ValueError("equity cannot be negative.")

        return value

    @validates("leverage")
    def _validate_leverage(self, key: str, value: int) -> int:
        if value < 1:
            raise ValueError("leverage must be at least 1.")

        return value

    def validate_auto_trade_capability(self) -> None:
        """
        Auto trade is a capability, not a mode a caller can simply select.

        Field validators cannot see sibling values reliably during construction,
        so this runs explicitly before a write. MySQL enforces the same rule with
        a CHECK constraint, so bypassing Python still fails at the database.
        """

        if (
            self.execution_mode == ExecutionMode.AUTO_TRADE
            and not self.auto_trade_enabled
        ):
            raise ValueError(
                "auto_trade_enabled must be true before an account can auto trade."
            )

    @property
    def is_real_money(self) -> bool:
        return is_real_money_account(self.account_type)

    @property
    def is_tradable(self) -> bool:
        return self.status in TRADEABLE_ACCOUNT_STATUSES

    @property
    def balance(self) -> float:
        return as_amount(self.current_balance)

    @property
    def account_equity(self) -> float:
        return as_amount(self.equity)

    @property
    def open_pnl(self) -> float:
        return self.account_equity - self.balance

    @property
    def total_return_fraction(self) -> float:
        initial = as_amount(self.initial_balance)

        return (self.account_equity - initial) / initial

    @property
    def allows_orders(self) -> bool:
        """Whether this account's ceiling alone would permit orders."""

        if not self.is_tradable:
            return False

        return execution_mode_allows_orders(self.execution_mode)

    def execution_ceiling(self) -> ExecutionMode:
        """
        The strictest mode this account can contribute.

        A suspended, disabled or archived account contributes ``DISABLED``: its
        stored execution mode is irrelevant while it cannot trade.
        """

        if not self.is_tradable:
            return ExecutionMode.DISABLED

        return self.execution_mode

    def execution_constraint(self) -> ExecutionConstraint:
        """The account-level ceiling, ready for the execution mode resolver."""

        ceiling = self.execution_ceiling()

        if not self.is_tradable:
            reason = f"Account status is {self.status.value}."
        else:
            reason = f"Account execution mode is {self.execution_mode.value}."

        return ExecutionConstraint(
            source=ExecutionConstraintSource.ACCOUNT,
            ceiling=ceiling,
            reason=reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "user_id": self.user_id,
            "name": self.name,
            "account_type": (
                self.account_type.value if self.account_type else None
            ),
            "broker": self.broker.value if self.broker else None,
            "status": self.status.value if self.status else None,
            "execution_mode": (
                self.execution_mode.value if self.execution_mode else None
            ),
            "execution_ceiling": self.execution_ceiling().value,
            "auto_trade_enabled": bool(self.auto_trade_enabled),
            "is_default": bool(self.is_default),
            "currency": self.currency,
            "initial_balance": as_amount(self.initial_balance),
            "current_balance": self.balance,
            "equity": self.account_equity,
            "open_pnl": self.open_pnl,
            "total_return_fraction": self.total_return_fraction,
            "leverage": self.leverage,
            "is_real_money": self.is_real_money,
            "is_tradable": self.is_tradable,
            "allows_orders": self.allows_orders,
            "broker_account_ref": self.broker_account_ref,
            "broker_credential_ref": self.broker_credential_ref,
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
            f"TradingAccount(account_id={self.account_id!r}, name={self.name!r}, "
            f"type={self.account_type.value if self.account_type else None!r})"
        )


__all__ = [
    "AQOS_ACCOUNTS_VERSION",
    "AUTO_TRADE_GUARDED_ACCOUNT_TYPES",
    "AccountStatus",
    "AccountType",
    "BrokerKind",
    "DEFAULT_ACCOUNT_CURRENCY",
    "MONEY_PRECISION",
    "REAL_MONEY_ACCOUNT_TYPES",
    "TRADEABLE_ACCOUNT_STATUSES",
    "TradingAccount",
    "as_amount",
    "default_execution_mode_for_account",
    "is_real_money_account",
    "normalize_account_currency",
    "normalize_account_name",
]
