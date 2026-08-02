from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update

from aqos.accounts.models import (
    AUTO_TRADE_GUARDED_ACCOUNT_TYPES,
    AccountStatus,
    AccountType,
    BrokerKind,
    DEFAULT_ACCOUNT_CURRENCY,
    TradingAccount,
    default_execution_mode_for_account,
    normalize_account_name,
)
from aqos.database.repository import AqosRepository, RepositoryError
from aqos.database.types import database_utc_now
from aqos.execution_policy.modes import ExecutionMode
from aqos.users.repositories import build_entity_id


AQOS_ACCOUNT_REPOSITORIES_VERSION = "1.0"


class TradingAccountRepository(AqosRepository[TradingAccount]):
    """Trading accounts owned by a user, with one default account at a time."""

    model = TradingAccount

    def create_account(
        self,
        user_id: str,
        name: str,
        account_type: AccountType,
        broker: BrokerKind,
        initial_balance: float,
        currency: str = DEFAULT_ACCOUNT_CURRENCY,
        execution_mode: ExecutionMode | None = None,
        auto_trade_enabled: bool = False,
        leverage: int = 1,
        broker_account_ref: str | None = None,
        broker_credential_ref: str | None = None,
        is_default: bool = False,
        status: AccountStatus = AccountStatus.ACTIVE,
        metadata: dict[str, Any] | None = None,
        account_id: str | None = None,
        created_at_utc: datetime | None = None,
    ) -> TradingAccount:
        normalized_name = normalize_account_name(name)

        if self.find_by_name(user_id, normalized_name) is not None:
            raise RepositoryError(
                f"Account name already exists for this user: {normalized_name}"
            )

        resolved_mode = execution_mode or default_execution_mode_for_account(
            account_type
        )

        if (
            account_type in AUTO_TRADE_GUARDED_ACCOUNT_TYPES
            and resolved_mode == ExecutionMode.AUTO_TRADE
        ):
            raise RepositoryError(
                "Live and funded accounts cannot be created in auto trade mode."
            )

        timestamp = created_at_utc or database_utc_now()

        account = TradingAccount(
            account_id=account_id or build_entity_id("account"),
            user_id=user_id,
            name=normalized_name,
            account_type=account_type,
            broker=broker,
            status=status,
            execution_mode=resolved_mode,
            auto_trade_enabled=auto_trade_enabled,
            is_default=False,
            currency=currency,
            initial_balance=initial_balance,
            current_balance=initial_balance,
            equity=initial_balance,
            leverage=leverage,
            broker_account_ref=broker_account_ref,
            broker_credential_ref=broker_credential_ref,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
        )
        account.validate_auto_trade_capability()

        self.add(account)
        self.flush()

        if is_default or self.count_accounts(user_id) == 1:
            return self.set_default_account(user_id, account.account_id, timestamp)

        return account

    def find_by_name(self, user_id: str, name: str) -> TradingAccount | None:
        return self.session.execute(
            select(TradingAccount).where(
                TradingAccount.user_id == user_id,
                TradingAccount.name == (name or "").strip(),
            )
        ).scalar_one_or_none()

    def require_account(self, account_id: str) -> TradingAccount:
        return self.require(account_id)

    def get_default_account(self, user_id: str) -> TradingAccount | None:
        return self.session.execute(
            select(TradingAccount).where(
                TradingAccount.user_id == user_id,
                TradingAccount.is_default.is_(True),
            )
        ).scalar_one_or_none()

    def list_accounts(
        self,
        user_id: str,
        account_type: AccountType | None = None,
        status: AccountStatus | None = None,
        broker: BrokerKind | None = None,
    ) -> tuple[TradingAccount, ...]:
        statement = select(TradingAccount).where(TradingAccount.user_id == user_id)

        if account_type is not None:
            statement = statement.where(TradingAccount.account_type == account_type)

        if status is not None:
            statement = statement.where(TradingAccount.status == status)

        if broker is not None:
            statement = statement.where(TradingAccount.broker == broker)

        statement = statement.order_by(
            TradingAccount.created_at_utc,
            TradingAccount.account_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def list_tradable_accounts(self, user_id: str) -> tuple[TradingAccount, ...]:
        return self.list_accounts(user_id, status=AccountStatus.ACTIVE)

    def count_accounts(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def set_default_account(
        self,
        user_id: str,
        account_id: str,
        updated_at_utc: datetime | None = None,
    ) -> TradingAccount:
        account = self.require_account(account_id)

        if account.user_id != user_id:
            raise RepositoryError("Account does not belong to this user.")

        timestamp = updated_at_utc or database_utc_now()

        self.session.execute(
            update(TradingAccount)
            .where(
                TradingAccount.user_id == user_id,
                TradingAccount.is_default.is_(True),
            )
            .values(is_default=False, updated_at_utc=timestamp)
        )

        account.is_default = True
        account.updated_at_utc = timestamp

        self.flush()

        return account

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
        updated_at_utc: datetime | None = None,
    ) -> TradingAccount:
        account = self.require_account(account_id)

        if name is not None:
            normalized_name = normalize_account_name(name)
            existing = self.find_by_name(account.user_id, normalized_name)

            if existing is not None and existing.account_id != account_id:
                raise RepositoryError(
                    f"Account name already exists for this user: {normalized_name}"
                )

            account.name = normalized_name

        if status is not None:
            account.status = status

        if auto_trade_enabled is not None:
            account.auto_trade_enabled = auto_trade_enabled

        if execution_mode is not None:
            account.execution_mode = execution_mode

        if leverage is not None:
            account.leverage = leverage

        if broker_account_ref is not None:
            account.broker_account_ref = broker_account_ref

        if broker_credential_ref is not None:
            account.broker_credential_ref = broker_credential_ref

        if metadata is not None:
            account.extra_metadata = metadata

        account.updated_at_utc = updated_at_utc or database_utc_now()
        account.validate_auto_trade_capability()

        self.flush()

        return account

    def set_status(
        self,
        account_id: str,
        status: AccountStatus,
        updated_at_utc: datetime | None = None,
    ) -> TradingAccount:
        return self.update_account(
            account_id=account_id,
            status=status,
            updated_at_utc=updated_at_utc,
        )

    def enable_auto_trade(
        self,
        account_id: str,
        updated_at_utc: datetime | None = None,
    ) -> TradingAccount:
        """
        Turn on the auto trade capability.

        This only grants the capability. Moving the account to
        ``ExecutionMode.AUTO_TRADE`` remains a separate, deliberate step.
        """

        return self.update_account(
            account_id=account_id,
            auto_trade_enabled=True,
            updated_at_utc=updated_at_utc,
        )

    def disable_auto_trade(
        self,
        account_id: str,
        updated_at_utc: datetime | None = None,
    ) -> TradingAccount:
        """Revoke the capability, downgrading the mode if it was in use."""

        account = self.require_account(account_id)

        downgraded_mode = (
            ExecutionMode.MANUAL_APPROVAL
            if account.execution_mode == ExecutionMode.AUTO_TRADE
            else account.execution_mode
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
        updated_at_utc: datetime | None = None,
    ) -> TradingAccount:
        account = self.require_account(account_id)

        if current_balance is not None:
            account.current_balance = current_balance

        if equity is not None:
            account.equity = equity

        account.updated_at_utc = updated_at_utc or database_utc_now()

        self.flush()

        return account

    def delete_account(self, account_id: str) -> bool:
        return self.delete_by_primary_key(account_id)


__all__ = [
    "AQOS_ACCOUNT_REPOSITORIES_VERSION",
    "TradingAccountRepository",
]
