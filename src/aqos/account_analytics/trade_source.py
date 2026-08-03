from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence, runtime_checkable

from aqos.account_analytics.metrics import AccountTradeRecord


AQOS_ACCOUNT_TRADE_SOURCE_VERSION = "1.0"


@runtime_checkable
class AccountTradeSource(Protocol):
    """
    A live source of closed trades for analytics.

    A plain sequence of records is still accepted everywhere a source is, but a
    source object can answer for a specific account and period, which a fixed
    sequence cannot. Being connected is what makes trade metrics *available*;
    returning no trades is a measured zero, not a missing source.
    """

    def list_account_trades(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> Sequence[AccountTradeRecord]:
        ...


def is_trade_source(candidate: object) -> bool:
    """
    Whether an object answers scoped trade queries.

    A sequence of records is not one: it cannot be filtered by account or
    period, so it is used as-is instead.
    """

    return isinstance(candidate, AccountTradeSource) and not isinstance(
        candidate, (list, tuple)
    )


def resolve_trades(
    source: Sequence[AccountTradeRecord] | AccountTradeSource,
    user_id: str | None = None,
    account_id: str | None = None,
    period_start_utc: datetime | None = None,
    period_end_utc: datetime | None = None,
) -> Sequence[AccountTradeRecord]:
    """Read trades from either a live source or a fixed sequence."""

    if is_trade_source(source):
        return source.list_account_trades(
            user_id=user_id,
            account_id=account_id,
            period_start_utc=period_start_utc,
            period_end_utc=period_end_utc,
        )

    return source


__all__ = [
    "AQOS_ACCOUNT_TRADE_SOURCE_VERSION",
    "AccountTradeSource",
    "is_trade_source",
    "resolve_trades",
]
