from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from aqos.account_analytics.metrics import AccountTradeRecord
from aqos.accounts.models import AccountType, TradingAccount
from aqos.paper_trading.contracts import (
    PaperOrderStatus,
    PaperPositionStatus,
    PaperSide,
    PaperTradingError,
)
from aqos.paper_trading.models import (
    PaperAccountSnapshotRecord,
    PaperFillRecord,
    PaperOrderRecord,
    PaperPositionRecord,
    PaperTradeRecord,
    as_amount,
)
from aqos.paper_trading.repositories import (
    PaperAccountSnapshotRepository,
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.simulator import PaperExitReason


AQOS_PAPER_HISTORY_VERSION = "1.0"


def validate_period(
    period_start_utc: datetime | None,
    period_end_utc: datetime | None,
) -> None:
    if (
        period_start_utc is not None
        and period_end_utc is not None
        and period_end_utc < period_start_utc
    ):
        raise PaperTradingError(
            "period_end_utc cannot be before period_start_utc."
        )


@dataclass(frozen=True)
class EquityPoint:
    """One point on the realised equity curve."""

    at_utc: datetime
    trade_id: str
    net_pnl: float
    equity: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "at_utc": self.at_utc.isoformat(),
            "trade_id": self.trade_id,
            "net_pnl": self.net_pnl,
            "equity": self.equity,
        }


@dataclass(frozen=True)
class DailyPnlPoint:
    """Realised PnL for one calendar day."""

    day: date
    net_pnl: float
    trade_count: int
    winning_trades: int
    losing_trades: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "day": self.day.isoformat(),
            "net_pnl": self.net_pnl,
            "trade_count": self.trade_count,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
        }


@dataclass(frozen=True)
class OpenRisk:
    """
    Risk currently exposed by open positions.

    ``positions_without_stop`` is reported separately because those carry no
    measurable risk figure at all; folding them in as zero would understate the
    exposure.
    """

    account_id: str
    open_position_count: int
    measured_risk: float
    positions_without_stop: int
    measured_at_utc: datetime

    @property
    def is_fully_measured(self) -> bool:
        return self.positions_without_stop == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "open_position_count": self.open_position_count,
            "measured_risk": self.measured_risk,
            "positions_without_stop": self.positions_without_stop,
            "is_fully_measured": self.is_fully_measured,
            "measured_at_utc": self.measured_at_utc.isoformat(),
        }


@dataclass(frozen=True)
class SignalExecutionHistory:
    """Everything one signal produced on one paper account."""

    signal_id: str
    orders: tuple[PaperOrderRecord, ...] = ()
    fills: tuple[PaperFillRecord, ...] = ()
    positions: tuple[PaperPositionRecord, ...] = ()
    trades: tuple[PaperTradeRecord, ...] = ()
    decisions: tuple[Any, ...] = ()
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    @property
    def was_executed(self) -> bool:
        return bool(self.fills)

    @property
    def net_pnl(self) -> float | None:
        """None when the signal produced no closed trade, rather than zero."""

        if not self.trades:
            return None

        return sum(as_amount(trade.net_pnl) for trade in self.trades)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "was_executed": self.was_executed,
            "net_pnl": self.net_pnl,
            "order_count": len(self.orders),
            "fill_count": len(self.fills),
            "position_count": len(self.positions),
            "trade_count": len(self.trades),
            "decision_count": len(self.decisions),
            "orders": [order.to_dict() for order in self.orders],
            "trades": [trade.to_dict() for trade in self.trades],
            "metadata": self.extra_metadata,
        }


class PaperTradeSource:
    """
    A live ``AccountTradeRecord`` source backed by persisted paper trades.

    Being constructed against a session is what makes trade metrics available:
    an account with no closed trades then reports a measured zero rather than
    "unknown". Nothing here invents a trade.
    """

    def __init__(
        self,
        session: Session,
        restrict_to_paper_accounts: bool = True,
    ) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        self.session = session
        self.restrict_to_paper_accounts = restrict_to_paper_accounts
        self.trades = PaperTradeRepository(session)

    def paper_account_ids(self, user_id: str) -> tuple[str, ...]:
        """Every paper account the user owns."""

        statement = select(TradingAccount.account_id).where(
            TradingAccount.user_id == user_id
        )

        if self.restrict_to_paper_accounts:
            statement = statement.where(
                TradingAccount.account_type == AccountType.PAPER
            )

        return tuple(self.session.execute(statement).scalars().all())

    def list_account_trades(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> tuple[AccountTradeRecord, ...]:
        validate_period(period_start_utc, period_end_utc)

        if account_id is not None:
            account_ids: tuple[str, ...] = (account_id,)
        elif user_id is not None:
            account_ids = self.paper_account_ids(user_id)
        else:
            account_ids = ()

        if account_id is None and user_id is not None and not account_ids:
            return ()

        records: list[AccountTradeRecord] = []

        for resolved_account_id in account_ids or (None,):
            records.extend(
                trade.to_account_trade_record()
                for trade in self.trades.list_trades(
                    account_id=resolved_account_id,
                    closed_since_utc=period_start_utc,
                    closed_until_utc=period_end_utc,
                )
            )

        return tuple(
            sorted(records, key=lambda record: record.closed_at_utc)
        )


class PaperHistoryService:
    """
    Read-only history and analytics over persisted paper trading.

    The caller owns the session. Every figure here comes from a stored row; a
    period with nothing in it returns an empty result, never a fabricated one.
    """

    def __init__(self, session: Session) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        self.session = session
        self.orders = PaperOrderRepository(session)
        self.positions = PaperPositionRepository(session)
        self.fills = PaperFillRepository(session)
        self.trades = PaperTradeRepository(session)
        self.snapshots = PaperAccountSnapshotRepository(session)
        self.decisions = PaperExecutionDecisionRepository(session)

    # -- history ----------------------------------------------------------

    def order_history(
        self,
        account_id: str | None = None,
        user_id: str | None = None,
        symbol: str | None = None,
        status: PaperOrderStatus | None = None,
        signal_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperOrderRecord, ...]:
        validate_period(period_start_utc, period_end_utc)

        return self.orders.list_orders(
            account_id=account_id,
            user_id=user_id,
            signal_id=signal_id,
            status=status,
            symbol=symbol,
            created_since_utc=period_start_utc,
            created_until_utc=period_end_utc,
            limit=limit,
        )

    def fill_history(
        self,
        account_id: str | None = None,
        order_id: str | None = None,
        position_id: str | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperFillRecord, ...]:
        validate_period(period_start_utc, period_end_utc)

        return self.fills.list_fills(
            account_id=account_id,
            order_id=order_id,
            position_id=position_id,
            filled_since_utc=period_start_utc,
            filled_until_utc=period_end_utc,
            limit=limit,
        )

    def position_history(
        self,
        account_id: str | None = None,
        symbol: str | None = None,
        side: PaperSide | None = None,
        status: PaperPositionStatus | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperPositionRecord, ...]:
        validate_period(period_start_utc, period_end_utc)

        return self.positions.list_positions(
            account_id=account_id,
            symbol=symbol,
            side=side,
            status=status,
            opened_since_utc=period_start_utc,
            opened_until_utc=period_end_utc,
            limit=limit,
        )

    def trade_history(
        self,
        account_id: str | None = None,
        symbol: str | None = None,
        side: PaperSide | None = None,
        signal_id: str | None = None,
        exit_reason: PaperExitReason | None = None,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperTradeRecord, ...]:
        validate_period(period_start_utc, period_end_utc)

        return self.trades.list_trades(
            account_id=account_id,
            symbol=symbol,
            side=side,
            signal_id=signal_id,
            exit_reason=exit_reason,
            closed_since_utc=period_start_utc,
            closed_until_utc=period_end_utc,
            limit=limit,
        )

    def account_trade_history(
        self,
        account_id: str,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> tuple[AccountTradeRecord, ...]:
        """The account's closed trades in the analytics contract's shape."""

        return tuple(
            trade.to_account_trade_record()
            for trade in self.trade_history(
                account_id=account_id,
                period_start_utc=period_start_utc,
                period_end_utc=period_end_utc,
            )
        )

    def signal_execution_history(
        self,
        signal_id: str,
        account_id: str | None = None,
    ) -> SignalExecutionHistory:
        """Everything one signal produced, including refused attempts."""

        orders = self.orders.list_orders(
            signal_id=signal_id,
            account_id=account_id,
        )
        order_ids = {order.order_id for order in orders}

        fills = tuple(
            fill
            for fill in self.fills.list_fills(account_id=account_id)
            if fill.order_id in order_ids
        )
        positions = tuple(
            position
            for position in self.positions.list_positions(account_id=account_id)
            if position.signal_id == signal_id
        )

        return SignalExecutionHistory(
            signal_id=signal_id,
            orders=orders,
            fills=fills,
            positions=positions,
            trades=self.trades.list_trades(
                signal_id=signal_id,
                account_id=account_id,
            ),
            decisions=self.decisions.list_decisions(
                signal_id=signal_id,
                account_id=account_id,
            ),
        )

    # -- balance and equity ------------------------------------------------

    def snapshot_history(
        self,
        account_id: str,
        limit: int | None = None,
    ) -> tuple[PaperAccountSnapshotRecord, ...]:
        return self.snapshots.list_snapshots(account_id=account_id, limit=limit)

    def realized_pnl(
        self,
        account_id: str,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> float | None:
        """
        Total realised PnL, or None when the account closed no trades.

        An account that never traded has an unknown result, not a zero one.
        """

        trades = self.trade_history(
            account_id=account_id,
            period_start_utc=period_start_utc,
            period_end_utc=period_end_utc,
        )

        if not trades:
            return None

        return sum(as_amount(trade.net_pnl) for trade in trades)

    def equity_curve(
        self,
        account_id: str,
        starting_balance: float,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> tuple[EquityPoint, ...]:
        """
        The realised equity curve, one point per closed trade.

        Open positions are deliberately excluded: their result is not yet real,
        and mixing unrealised movement in would make the curve unfalsifiable.
        """

        if starting_balance <= 0:
            raise PaperTradingError("starting_balance must be positive.")

        equity = starting_balance
        points: list[EquityPoint] = []

        for trade in self.trade_history(
            account_id=account_id,
            period_start_utc=period_start_utc,
            period_end_utc=period_end_utc,
        ):
            net_pnl = as_amount(trade.net_pnl)
            equity += net_pnl

            points.append(
                EquityPoint(
                    at_utc=trade.closed_at_utc,
                    trade_id=trade.trade_id,
                    net_pnl=net_pnl,
                    equity=equity,
                )
            )

        return tuple(points)

    def daily_pnl(
        self,
        account_id: str,
        period_start_utc: datetime | None = None,
        period_end_utc: datetime | None = None,
    ) -> tuple[DailyPnlPoint, ...]:
        """
        Realised PnL grouped by close date.

        Days with no closed trade are absent rather than reported as a flat
        zero, which would imply the account traded and broke even.
        """

        buckets: dict[date, list[PaperTradeRecord]] = {}

        for trade in self.trade_history(
            account_id=account_id,
            period_start_utc=period_start_utc,
            period_end_utc=period_end_utc,
        ):
            buckets.setdefault(trade.closed_at_utc.date(), []).append(trade)

        return tuple(
            DailyPnlPoint(
                day=day,
                net_pnl=sum(as_amount(trade.net_pnl) for trade in trades),
                trade_count=len(trades),
                winning_trades=sum(
                    1 for trade in trades if as_amount(trade.net_pnl) > 0
                ),
                losing_trades=sum(
                    1 for trade in trades if as_amount(trade.net_pnl) < 0
                ),
            )
            for day, trades in sorted(buckets.items())
        )

    def open_risk(
        self,
        account_id: str,
        measured_at_utc: datetime,
    ) -> OpenRisk:
        """Currency at risk across open positions that carry a stop."""

        open_positions = self.positions.list_open_positions(account_id=account_id)

        measured = 0.0
        without_stop = 0

        for position in open_positions:
            if position.stop_loss is None:
                without_stop += 1
                continue

            remaining = as_amount(position.quantity) - as_amount(
                position.closed_quantity
            )
            measured += (
                abs(as_amount(position.entry_price) - as_amount(position.stop_loss))
                * remaining
            )

        return OpenRisk(
            account_id=account_id,
            open_position_count=len(open_positions),
            measured_risk=measured,
            positions_without_stop=without_stop,
            measured_at_utc=measured_at_utc,
        )

    def build_trade_source(self) -> PaperTradeSource:
        """A live analytics trade source over the same session."""

        return PaperTradeSource(self.session)


__all__ = [
    "AQOS_PAPER_HISTORY_VERSION",
    "DailyPnlPoint",
    "EquityPoint",
    "OpenRisk",
    "PaperHistoryService",
    "PaperTradeSource",
    "SignalExecutionHistory",
    "validate_period",
]
