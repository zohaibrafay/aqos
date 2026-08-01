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
from aqos.persistence.trading_settings import (
    ExecutionMode,
    TradingSettings,
    execution_mode_rank,
    resolve_effective_execution_mode,
)
from aqos.persistence.user_preferences import normalize_currency


AQOS_ACCOUNTS_VERSION = "1.0"


class AccountType(str, Enum):
    PAPER = "paper"
    DEMO = "demo"
    LIVE = "live"
    FUNDED = "funded"


class BrokerKind(str, Enum):
    PAPER = "paper"
    MT5 = "mt5"
    BINANCE = "binance"
    MANUAL = "manual"


class AccountStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    CLOSED = "closed"


#: Account types where real capital is at stake.
REAL_MONEY_ACCOUNT_TYPES = (AccountType.LIVE, AccountType.FUNDED)

#: Account types that may never be created with auto trading already on.
AUTO_TRADE_GUARDED_ACCOUNT_TYPES = REAL_MONEY_ACCOUNT_TYPES

TRADEABLE_ACCOUNT_STATUSES = (AccountStatus.ACTIVE,)


def is_real_money_account(account_type: AccountType) -> bool:
    return account_type in REAL_MONEY_ACCOUNT_TYPES


def default_execution_mode_for_account(account_type: AccountType) -> ExecutionMode:
    """Real-money accounts always start in the safest usable mode."""

    if is_real_money_account(account_type):
        return ExecutionMode.SIGNAL_ONLY

    return ExecutionMode.MANUAL_APPROVAL


@dataclass(frozen=True)
class TradingAccount:
    account_id: str
    user_id: str
    name: str
    account_type: AccountType
    broker: BrokerKind
    currency: str
    initial_balance: float
    current_balance: float
    equity: float
    created_at_utc: str
    updated_at_utc: str
    status: AccountStatus = AccountStatus.ACTIVE
    execution_mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY
    auto_trade_enabled: bool = False
    is_default: bool = False
    leverage: int = 1
    broker_account_ref: str | None = None
    broker_credential_ref: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.account_id.strip():
            raise ValueError("account_id cannot be empty.")

        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.name.strip():
            raise ValueError("name cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.updated_at_utc.strip():
            raise ValueError("updated_at_utc cannot be empty.")

        normalize_currency(self.currency)

        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive.")

        if self.current_balance < 0:
            raise ValueError("current_balance cannot be negative.")

        if self.equity < 0:
            raise ValueError("equity cannot be negative.")

        if self.leverage < 1:
            raise ValueError("leverage must be at least 1.")

        if self.execution_mode == ExecutionMode.AUTO_TRADE and not self.auto_trade_enabled:
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
    def open_pnl(self) -> float:
        return self.equity - self.current_balance

    @property
    def total_return_fraction(self) -> float:
        return (self.equity - self.initial_balance) / self.initial_balance

    def allows_orders(self) -> bool:
        if not self.is_tradable:
            return False

        return self.execution_mode in (
            ExecutionMode.MANUAL_APPROVAL,
            ExecutionMode.AUTO_TRADE,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "user_id": self.user_id,
            "name": self.name,
            "account_type": self.account_type.value,
            "broker": self.broker.value,
            "currency": self.currency,
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "equity": self.equity,
            "open_pnl": self.open_pnl,
            "total_return_fraction": self.total_return_fraction,
            "status": self.status.value,
            "execution_mode": self.execution_mode.value,
            "auto_trade_enabled": self.auto_trade_enabled,
            "is_default": self.is_default,
            "is_real_money": self.is_real_money,
            "is_tradable": self.is_tradable,
            "allows_orders": self.allows_orders(),
            "leverage": self.leverage,
            "broker_account_ref": self.broker_account_ref,
            "broker_credential_ref": self.broker_credential_ref,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "metadata": self.metadata,
        }


def build_trading_account_from_row(row: dict[str, Any]) -> TradingAccount:
    return TradingAccount(
        account_id=str(row["account_id"]),
        user_id=str(row["user_id"]),
        name=str(row["name"]),
        account_type=AccountType(str(row["account_type"])),
        broker=BrokerKind(str(row["broker"])),
        currency=str(row["currency"]),
        initial_balance=float(row["initial_balance"]),
        current_balance=float(row["current_balance"]),
        equity=float(row["equity"]),
        created_at_utc=str(row["created_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        status=AccountStatus(str(row["status"])),
        execution_mode=ExecutionMode(str(row["execution_mode"])),
        auto_trade_enabled=decode_bool(row["auto_trade_enabled"]),
        is_default=decode_bool(row["is_default"]),
        leverage=int(row["leverage"]),
        broker_account_ref=row.get("broker_account_ref"),
        broker_credential_ref=row.get("broker_credential_ref"),
        metadata=decode_json_field(row.get("metadata")),
    )


def resolve_account_execution_mode(
    settings: TradingSettings,
    account: TradingAccount,
) -> ExecutionMode:
    """
    The mode that actually applies to an account.

    The user-level setting acts as a ceiling and the account setting acts as a
    second ceiling, so the strictest of the two always wins. A non-tradable
    account is always disabled.
    """

    if not account.is_tradable:
        return ExecutionMode.DISABLED

    return resolve_effective_execution_mode(
        requested=account.execution_mode,
        ceiling=settings.execution_mode,
    )


def account_allows_execution(
    settings: TradingSettings,
    account: TradingAccount,
) -> bool:
    mode = resolve_account_execution_mode(settings, account)

    return execution_mode_rank(mode) >= execution_mode_rank(
        ExecutionMode.MANUAL_APPROVAL
    )


class TradingAccountRepository:
    """Trading accounts owned by a user, one default account at a time."""

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

    def create_account(
        self,
        user_id: str,
        name: str,
        account_type: AccountType,
        broker: BrokerKind,
        initial_balance: float,
        currency: str = "USD",
        execution_mode: ExecutionMode | None = None,
        auto_trade_enabled: bool = False,
        leverage: int = 1,
        broker_account_ref: str | None = None,
        broker_credential_ref: str | None = None,
        is_default: bool = False,
        status: AccountStatus = AccountStatus.ACTIVE,
        metadata: dict[str, Any] | None = None,
        account_id: str | None = None,
        created_at_utc: str | None = None,
    ) -> TradingAccount:
        normalized_name = normalize_required_text(name, "name")

        if self.find_account_by_name(user_id, normalized_name) is not None:
            raise ValueError(
                f"Account name already exists for this user: {normalized_name}"
            )

        resolved_mode = execution_mode or default_execution_mode_for_account(
            account_type
        )

        if (
            account_type in AUTO_TRADE_GUARDED_ACCOUNT_TYPES
            and resolved_mode == ExecutionMode.AUTO_TRADE
        ):
            raise ValueError(
                "Live and funded accounts cannot be created in auto trade mode."
            )

        timestamp = created_at_utc or record_utc_now()

        account = TradingAccount(
            account_id=account_id or build_record_id("account"),
            user_id=normalize_required_text(user_id, "user_id"),
            name=normalized_name,
            account_type=account_type,
            broker=broker,
            currency=normalize_currency(currency),
            initial_balance=initial_balance,
            current_balance=initial_balance,
            equity=initial_balance,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            status=status,
            execution_mode=resolved_mode,
            auto_trade_enabled=auto_trade_enabled,
            is_default=is_default,
            leverage=leverage,
            broker_account_ref=broker_account_ref,
            broker_credential_ref=broker_credential_ref,
            metadata=metadata or {},
        )

        self._insert(account)

        if is_default or self.count_accounts(user_id) == 1:
            return self.set_default_account(user_id, account.account_id, timestamp)

        return account

    def get_account(self, account_id: str) -> TradingAccount | None:
        row = self.database.query_one(
            "SELECT * FROM trading_accounts WHERE account_id = ?;",
            (account_id,),
        )

        return build_trading_account_from_row(row) if row is not None else None

    def require_account(self, account_id: str) -> TradingAccount:
        account = self.get_account(account_id)

        if account is None:
            raise LookupError(f"Trading account does not exist: {account_id}")

        return account

    def find_account_by_name(
        self,
        user_id: str,
        name: str,
    ) -> TradingAccount | None:
        row = self.database.query_one(
            "SELECT * FROM trading_accounts WHERE user_id = ? AND name = ?;",
            (user_id, name.strip()),
        )

        return build_trading_account_from_row(row) if row is not None else None

    def get_default_account(self, user_id: str) -> TradingAccount | None:
        row = self.database.query_one(
            "SELECT * FROM trading_accounts WHERE user_id = ? AND is_default = 1;",
            (user_id,),
        )

        return build_trading_account_from_row(row) if row is not None else None

    def list_accounts(
        self,
        user_id: str,
        account_type: AccountType | None = None,
        status: AccountStatus | None = None,
        broker: BrokerKind | None = None,
    ) -> tuple[TradingAccount, ...]:
        clauses = ["user_id = ?"]
        parameters: list[Any] = [user_id]

        if account_type is not None:
            clauses.append("account_type = ?")
            parameters.append(account_type.value)

        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)

        if broker is not None:
            clauses.append("broker = ?")
            parameters.append(broker.value)

        rows = self.database.query_all(
            f"SELECT * FROM trading_accounts WHERE {' AND '.join(clauses)} "
            "ORDER BY created_at_utc, account_id;",
            tuple(parameters),
        )

        return tuple(build_trading_account_from_row(row) for row in rows)

    def list_tradable_accounts(self, user_id: str) -> tuple[TradingAccount, ...]:
        return self.list_accounts(user_id, status=AccountStatus.ACTIVE)

    def count_accounts(self, user_id: str) -> int:
        return int(
            self.database.query_scalar(
                "SELECT COUNT(*) FROM trading_accounts WHERE user_id = ?;",
                (user_id,),
            )
            or 0
        )

    def set_default_account(
        self,
        user_id: str,
        account_id: str,
        updated_at_utc: str | None = None,
    ) -> TradingAccount:
        account = self.require_account(account_id)

        if account.user_id != user_id:
            raise ValueError("Account does not belong to this user.")

        timestamp = updated_at_utc or record_utc_now()

        with self.database.transaction():
            self.database.execute(
                "UPDATE trading_accounts SET is_default = 0, updated_at_utc = ? "
                "WHERE user_id = ? AND is_default = 1;",
                (timestamp, user_id),
            )
            self.database.execute(
                "UPDATE trading_accounts SET is_default = 1, updated_at_utc = ? "
                "WHERE account_id = ?;",
                (timestamp, account_id),
            )

        return self.require_account(account_id)

    def update_account(
        self,
        account_id: str,
        name: str | None = None,
        status: AccountStatus | None = None,
        execution_mode: ExecutionMode | None = None,
        auto_trade_enabled: bool | None = None,
        leverage: int | None = None,
        broker_account_ref: str | None = None,
        broker_credential_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
        updated_at_utc: str | None = None,
    ) -> TradingAccount:
        current = self.require_account(account_id)

        if name is not None:
            normalized_name = normalize_required_text(name, "name")
            existing = self.find_account_by_name(current.user_id, normalized_name)

            if existing is not None and existing.account_id != account_id:
                raise ValueError(
                    f"Account name already exists for this user: {normalized_name}"
                )
        else:
            normalized_name = current.name

        resolved_auto_trade = (
            auto_trade_enabled
            if auto_trade_enabled is not None
            else current.auto_trade_enabled
        )
        resolved_mode = execution_mode or current.execution_mode

        if resolved_mode == ExecutionMode.AUTO_TRADE and not resolved_auto_trade:
            raise ValueError(
                "auto_trade_enabled must be true before an account can auto trade."
            )

        updated = replace(
            current,
            name=normalized_name,
            status=status or current.status,
            execution_mode=resolved_mode,
            auto_trade_enabled=resolved_auto_trade,
            leverage=leverage if leverage is not None else current.leverage,
            broker_account_ref=(
                broker_account_ref
                if broker_account_ref is not None
                else current.broker_account_ref
            ),
            broker_credential_ref=(
                broker_credential_ref
                if broker_credential_ref is not None
                else current.broker_credential_ref
            ),
            metadata=metadata if metadata is not None else current.metadata,
            updated_at_utc=updated_at_utc or record_utc_now(),
        )

        self._update(updated)

        return updated

    def set_status(
        self,
        account_id: str,
        status: AccountStatus,
        updated_at_utc: str | None = None,
    ) -> TradingAccount:
        return self.update_account(
            account_id=account_id,
            status=status,
            updated_at_utc=updated_at_utc,
        )

    def enable_auto_trade(
        self,
        account_id: str,
        updated_at_utc: str | None = None,
    ) -> TradingAccount:
        """
        Turn on auto trading.

        This only flips the capability flag; the account still has to be moved
        to ``ExecutionMode.AUTO_TRADE`` deliberately afterwards.
        """

        return self.update_account(
            account_id=account_id,
            auto_trade_enabled=True,
            updated_at_utc=updated_at_utc,
        )

    def disable_auto_trade(
        self,
        account_id: str,
        updated_at_utc: str | None = None,
    ) -> TradingAccount:
        current = self.require_account(account_id)

        downgraded_mode = (
            ExecutionMode.MANUAL_APPROVAL
            if current.execution_mode == ExecutionMode.AUTO_TRADE
            else current.execution_mode
        )

        return self.update_account(
            account_id=account_id,
            execution_mode=downgraded_mode,
            auto_trade_enabled=False,
            updated_at_utc=updated_at_utc,
        )

    def update_balances(
        self,
        account_id: str,
        current_balance: float | None = None,
        equity: float | None = None,
        updated_at_utc: str | None = None,
    ) -> TradingAccount:
        current = self.require_account(account_id)

        updated = replace(
            current,
            current_balance=(
                current_balance
                if current_balance is not None
                else current.current_balance
            ),
            equity=equity if equity is not None else current.equity,
            updated_at_utc=updated_at_utc or record_utc_now(),
        )

        self.database.execute(
            "UPDATE trading_accounts SET current_balance = ?, equity = ?, "
            "updated_at_utc = ? WHERE account_id = ?;",
            (
                updated.current_balance,
                updated.equity,
                updated.updated_at_utc,
                account_id,
            ),
        )

        return updated

    def delete_account(self, account_id: str) -> bool:
        cursor = self.database.execute(
            "DELETE FROM trading_accounts WHERE account_id = ?;",
            (account_id,),
        )

        return cursor.rowcount > 0

    def _insert(self, account: TradingAccount) -> None:
        self.database.execute(
            """
            INSERT INTO trading_accounts (
                account_id, user_id, name, account_type, broker, currency,
                initial_balance, current_balance, equity, status, execution_mode,
                auto_trade_enabled, is_default, leverage, broker_account_ref,
                broker_credential_ref, created_at_utc, updated_at_utc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                account.account_id,
                account.user_id,
                account.name,
                account.account_type.value,
                account.broker.value,
                account.currency,
                account.initial_balance,
                account.current_balance,
                account.equity,
                account.status.value,
                account.execution_mode.value,
                encode_bool(account.auto_trade_enabled),
                encode_bool(account.is_default),
                account.leverage,
                account.broker_account_ref,
                account.broker_credential_ref,
                account.created_at_utc,
                account.updated_at_utc,
                encode_json_field(account.metadata),
            ),
        )

    def _update(self, account: TradingAccount) -> None:
        self.database.execute(
            """
            UPDATE trading_accounts
            SET name = ?, status = ?, execution_mode = ?, auto_trade_enabled = ?,
                leverage = ?, broker_account_ref = ?, broker_credential_ref = ?,
                updated_at_utc = ?, metadata = ?
            WHERE account_id = ?;
            """,
            (
                account.name,
                account.status.value,
                account.execution_mode.value,
                encode_bool(account.auto_trade_enabled),
                account.leverage,
                account.broker_account_ref,
                account.broker_credential_ref,
                account.updated_at_utc,
                encode_json_field(account.metadata),
                account.account_id,
            ),
        )


__all__ = [
    "AQOS_ACCOUNTS_VERSION",
    "AUTO_TRADE_GUARDED_ACCOUNT_TYPES",
    "AccountStatus",
    "AccountType",
    "BrokerKind",
    "REAL_MONEY_ACCOUNT_TYPES",
    "TRADEABLE_ACCOUNT_STATUSES",
    "TradingAccount",
    "TradingAccountRepository",
    "account_allows_execution",
    "build_trading_account_from_row",
    "default_execution_mode_for_account",
    "is_real_money_account",
    "resolve_account_execution_mode",
]
