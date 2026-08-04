from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aqos.accounts.models import AccountType, TradingAccount
from aqos.database.repository import AqosRepository, RepositoryError
from aqos.database.types import database_utc_now
from aqos.paper_trading.contracts import PaperTradingError
from aqos.paper_trading.models import (
    PaperSessionRecord,
    PaperTradeRecord,
    as_amount,
)
from aqos.paper_trading.repositories import (
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.sessions import (
    CREATABLE_PAPER_SESSION_STATUSES,
    EXECUTABLE_PAPER_SESSION_STATUSES,
    PaperSessionResult,
    PaperSessionStatus,
    PaperSessionType,
    normalize_session_name,
    validate_session_identity,
    validate_session_transition,
)
from aqos.users.repositories import build_entity_id


AQOS_PAPER_SESSION_SERVICE_VERSION = "1.0"

#: How many rejection reasons a result reports before truncating.
DEFAULT_TOP_REJECTION_LIMIT = 5


class PaperSessionRepository(AqosRepository[PaperSessionRecord]):
    """
    Paper session store.

    Status changes go through the transition table, so a completed session can
    never be restarted and a run can never skip straight past ``running``.
    """

    model = PaperSessionRecord

    def create_session(
        self,
        user_id: str,
        account_id: str,
        session_name: str,
        session_type: PaperSessionType,
        initial_balance: float,
        started_at_utc: datetime | None = None,
        status: PaperSessionStatus = PaperSessionStatus.CREATED,
        strategy_name: str | None = None,
        model_id: str | None = None,
        model_version: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> PaperSessionRecord:
        if status not in CREATABLE_PAPER_SESSION_STATUSES:
            raise RepositoryError(
                f"Paper sessions cannot be created as {status.value}."
            )

        if initial_balance <= 0:
            raise RepositoryError("initial_balance must be positive.")

        validate_session_identity(
            session_type=session_type,
            model_id=model_id,
            strategy_name=strategy_name,
        )

        timestamp = started_at_utc or database_utc_now()

        record = PaperSessionRecord(
            session_id=session_id or build_entity_id("papersession"),
            user_id=user_id,
            account_id=account_id,
            session_name=normalize_session_name(session_name),
            session_type=session_type,
            status=status,
            strategy_name=strategy_name,
            model_id=model_id,
            model_version=model_version,
            symbol=symbol,
            timeframe=timeframe,
            initial_balance=initial_balance,
            started_at_utc=timestamp,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
        )
        record.assert_identity_is_recorded()
        record.assert_lifecycle_is_consistent()

        self.add(record)

        # Orders, fills, trades and decisions all reference the session row.
        self.flush()

        return record

    def require_session(self, session_id: str) -> PaperSessionRecord:
        return self.require(session_id)

    def transition_session(
        self,
        session_id: str,
        to_status: PaperSessionStatus,
        occurred_at_utc: datetime | None = None,
        reason: str | None = None,
    ) -> PaperSessionRecord:
        record = self.require_session(session_id)

        validate_session_transition(record.status, to_status)

        timestamp = occurred_at_utc or database_utc_now()

        record.status = to_status
        record.status_reason = reason
        record.updated_at_utc = timestamp

        if to_status in (
            PaperSessionStatus.COMPLETED,
            PaperSessionStatus.FAILED,
            PaperSessionStatus.CANCELLED,
        ):
            record.ended_at_utc = timestamp

        record.assert_lifecycle_is_consistent()
        self.flush()

        return record

    def list_sessions(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        session_type: PaperSessionType | None = None,
        status: PaperSessionStatus | None = None,
        model_id: str | None = None,
        strategy_name: str | None = None,
        started_since_utc: datetime | None = None,
        started_until_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperSessionRecord, ...]:
        statement = select(PaperSessionRecord)

        if user_id is not None:
            statement = statement.where(PaperSessionRecord.user_id == user_id)

        if account_id is not None:
            statement = statement.where(
                PaperSessionRecord.account_id == account_id
            )

        if session_type is not None:
            statement = statement.where(
                PaperSessionRecord.session_type == session_type
            )

        if status is not None:
            statement = statement.where(PaperSessionRecord.status == status)

        if model_id is not None:
            statement = statement.where(PaperSessionRecord.model_id == model_id)

        if strategy_name is not None:
            statement = statement.where(
                PaperSessionRecord.strategy_name == strategy_name
            )

        if started_since_utc is not None:
            statement = statement.where(
                PaperSessionRecord.started_at_utc >= started_since_utc
            )

        if started_until_utc is not None:
            statement = statement.where(
                PaperSessionRecord.started_at_utc <= started_until_utc
            )

        statement = statement.order_by(
            PaperSessionRecord.started_at_utc,
            PaperSessionRecord.session_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def list_active_sessions(
        self,
        account_id: str | None = None,
    ) -> tuple[PaperSessionRecord, ...]:
        return tuple(
            record
            for record in self.list_sessions(account_id=account_id)
            if not record.is_terminal
        )

    def latest_session(self, account_id: str) -> PaperSessionRecord | None:
        sessions = self.list_sessions(account_id=account_id)

        return sessions[-1] if sessions else None

    def count_by_status(self, account_id: str | None = None) -> dict[str, int]:
        statement = select(PaperSessionRecord.status, func.count()).group_by(
            PaperSessionRecord.status
        )

        if account_id is not None:
            statement = statement.where(
                PaperSessionRecord.account_id == account_id
            )

        rows = self.session.execute(statement).all()

        return {
            (row[0].value if hasattr(row[0], "value") else str(row[0])): int(row[1])
            for row in sorted(
                rows,
                key=lambda item: (
                    item[0].value if hasattr(item[0], "value") else str(item[0])
                ),
            )
        }

    def record_result(
        self,
        session_id: str,
        result: PaperSessionResult,
        final_balance: float | None = None,
        updated_at_utc: datetime | None = None,
    ) -> PaperSessionRecord:
        """
        Store a measured result on the session row.

        Only what was actually measured is written: a session that closed no
        trade keeps ``net_pnl`` unset rather than recording a zero.
        """

        record = self.require_session(session_id)

        record.total_trades = result.total_trades
        record.net_pnl = result.net_pnl
        record.max_drawdown = result.max_drawdown
        record.updated_at_utc = updated_at_utc or database_utc_now()

        if final_balance is not None:
            record.final_balance = final_balance
        elif result.ending_balance is not None:
            record.final_balance = result.ending_balance

        self.flush()

        return record

    def delete_session(self, session_id: str) -> bool:
        return self.delete_by_primary_key(session_id)


class PaperSessionService:
    """
    Session lifecycle on top of the repository.

    The caller owns the session and the transaction. Paper sessions only ever
    attach to paper accounts: a session on a live account would let real capital
    be grouped under a simulated run.
    """

    def __init__(self, session: Session) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        self.session = session
        self.sessions = PaperSessionRepository(session)

    def start_session(
        self,
        account: TradingAccount,
        session_name: str,
        session_type: PaperSessionType,
        started_at_utc: datetime | None = None,
        strategy_name: str | None = None,
        model_id: str | None = None,
        model_version: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> PaperSessionRecord:
        """Create a session and move it straight to ``running``."""

        record = self.create_session(
            account=account,
            session_name=session_name,
            session_type=session_type,
            started_at_utc=started_at_utc,
            strategy_name=strategy_name,
            model_id=model_id,
            model_version=model_version,
            symbol=symbol,
            timeframe=timeframe,
            metadata=metadata,
            session_id=session_id,
        )

        return self.sessions.transition_session(
            session_id=record.session_id,
            to_status=PaperSessionStatus.RUNNING,
            occurred_at_utc=started_at_utc or record.started_at_utc,
        )

    def create_session(
        self,
        account: TradingAccount,
        session_name: str,
        session_type: PaperSessionType,
        started_at_utc: datetime | None = None,
        strategy_name: str | None = None,
        model_id: str | None = None,
        model_version: str | None = None,
        symbol: str | None = None,
        timeframe: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
    ) -> PaperSessionRecord:
        self.assert_account_is_paper(account)

        return self.sessions.create_session(
            user_id=account.user_id,
            account_id=account.account_id,
            session_name=session_name,
            session_type=session_type,
            initial_balance=as_amount(account.current_balance),
            started_at_utc=started_at_utc,
            strategy_name=strategy_name,
            model_id=model_id,
            model_version=model_version,
            symbol=symbol,
            timeframe=timeframe,
            metadata=metadata,
            session_id=session_id,
        )

    def assert_account_is_paper(self, account: TradingAccount) -> None:
        if account.account_type != AccountType.PAPER:
            raise PaperTradingError(
                f"Paper sessions only run on paper accounts, not "
                f"{account.account_type.value}."
            )

    def pause_session(
        self,
        session_id: str,
        reason: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> PaperSessionRecord:
        return self.sessions.transition_session(
            session_id=session_id,
            to_status=PaperSessionStatus.PAUSED,
            occurred_at_utc=occurred_at_utc,
            reason=reason,
        )

    def resume_session(
        self,
        session_id: str,
        occurred_at_utc: datetime | None = None,
    ) -> PaperSessionRecord:
        return self.sessions.transition_session(
            session_id=session_id,
            to_status=PaperSessionStatus.RUNNING,
            occurred_at_utc=occurred_at_utc,
        )

    def complete_session(
        self,
        session_id: str,
        occurred_at_utc: datetime | None = None,
        reason: str | None = None,
    ) -> PaperSessionRecord:
        return self.sessions.transition_session(
            session_id=session_id,
            to_status=PaperSessionStatus.COMPLETED,
            occurred_at_utc=occurred_at_utc,
            reason=reason,
        )

    def fail_session(
        self,
        session_id: str,
        reason: str,
        occurred_at_utc: datetime | None = None,
    ) -> PaperSessionRecord:
        if not (reason or "").strip():
            raise PaperTradingError("A failed session must record a reason.")

        return self.sessions.transition_session(
            session_id=session_id,
            to_status=PaperSessionStatus.FAILED,
            occurred_at_utc=occurred_at_utc,
            reason=reason,
        )

    def cancel_session(
        self,
        session_id: str,
        reason: str,
        occurred_at_utc: datetime | None = None,
    ) -> PaperSessionRecord:
        if not (reason or "").strip():
            raise PaperTradingError("A cancelled session must record a reason.")

        return self.sessions.transition_session(
            session_id=session_id,
            to_status=PaperSessionStatus.CANCELLED,
            occurred_at_utc=occurred_at_utc,
            reason=reason,
        )

    def require_running_session(self, session_id: str) -> PaperSessionRecord:
        """
        The session a new execution may be booked against.

        A paused or finished run must not silently accept more activity.
        """

        record = self.sessions.require_session(session_id)

        if record.status not in EXECUTABLE_PAPER_SESSION_STATUSES:
            raise PaperTradingError(
                f"Paper session {session_id} is {record.status.value}, so it "
                "cannot accept new executions."
            )

        return record


class PaperSessionResultService:
    """
    Builds a measured result for one session from its persisted rows.

    Nothing is estimated. Every figure comes from an order, fill, trade or
    decision that the session actually produced, and anything with nothing
    behind it stays unset.
    """

    def __init__(self, session: Session) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        self.session = session
        self.sessions = PaperSessionRepository(session)
        self.orders = PaperOrderRepository(session)
        self.fills = PaperFillRepository(session)
        self.trades = PaperTradeRepository(session)
        self.decisions = PaperExecutionDecisionRepository(session)

    def build_result(
        self,
        session_id: str,
        calculated_at_utc: datetime | None = None,
        top_rejection_limit: int = DEFAULT_TOP_REJECTION_LIMIT,
    ) -> PaperSessionResult:
        record = self.sessions.require_session(session_id)

        orders = self.orders.list_orders(session_id=session_id)
        fills = self.fills.list_fills(session_id=session_id)
        trades = self.trades.list_trades(session_id=session_id)
        decisions = self.decisions.list_decisions(session_id=session_id)

        allowed = sum(1 for decision in decisions if decision.is_allowed)
        rejected = len(decisions) - allowed

        return PaperSessionResult(
            session_id=session_id,
            account_id=record.account_id,
            total_orders=len(orders),
            total_fills=len(fills),
            symbols_traded=tuple(
                sorted({trade.symbol for trade in trades})
            ),
            decisions_allowed=allowed,
            decisions_rejected=rejected,
            top_rejection_reasons=self.top_rejection_reasons(
                decisions,
                limit=top_rejection_limit,
            ),
            calculated_at_utc=calculated_at_utc or database_utc_now(),
            **self.trade_figures(trades, as_amount(record.initial_balance)),
        )

    def trade_figures(
        self,
        trades: tuple[PaperTradeRecord, ...],
        starting_balance: float,
    ) -> dict[str, Any]:
        """
        Trade-derived figures, or unset ones when there is nothing to measure.

        A session with no closed trade has an unknown win rate and an unknown
        profit factor; reporting either as zero would read as a measured result.
        """

        if not trades:
            return {
                "total_trades": 0,
                "winning_trades": 0,
                "losing_trades": 0,
                "win_rate": None,
                "net_pnl": None,
                "gross_profit": None,
                "gross_loss": None,
                "profit_factor": None,
                "max_drawdown": None,
                "ending_balance": None,
            }

        net_pnls = [as_amount(trade.net_pnl) for trade in trades]
        winning = [value for value in net_pnls if value > 0]
        losing = [value for value in net_pnls if value < 0]

        gross_profit = sum(winning)
        gross_loss = abs(sum(losing))

        equity = starting_balance
        peak = starting_balance
        max_drawdown = 0.0

        for value in net_pnls:
            equity += value
            peak = max(peak, equity)
            max_drawdown = max(max_drawdown, peak - equity)

        return {
            "total_trades": len(trades),
            "winning_trades": len(winning),
            "losing_trades": len(losing),
            "win_rate": len(winning) / len(trades),
            "net_pnl": sum(net_pnls),
            "gross_profit": gross_profit,
            "gross_loss": gross_loss,
            # A run with no losing trade has no meaningful ratio, so it stays
            # unset rather than becoming infinity.
            "profit_factor": (
                gross_profit / gross_loss if gross_loss > 0 else None
            ),
            "max_drawdown": max_drawdown,
            "ending_balance": equity,
        }

    def top_rejection_reasons(
        self,
        decisions: tuple[Any, ...],
        limit: int = DEFAULT_TOP_REJECTION_LIMIT,
    ) -> tuple[tuple[str, int], ...]:
        if limit <= 0:
            raise PaperTradingError("limit must be positive.")

        counts: dict[str, int] = {}

        for decision in decisions:
            if decision.is_allowed or not decision.primary_reason_code:
                continue

            code = str(decision.primary_reason_code)
            counts[code] = counts.get(code, 0) + 1

        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))

        return tuple(ranked[:limit])

    def build_and_store_result(
        self,
        session_id: str,
        calculated_at_utc: datetime | None = None,
    ) -> PaperSessionResult:
        """Measure the session and write the summary back onto its row."""

        result = self.build_result(
            session_id=session_id,
            calculated_at_utc=calculated_at_utc,
        )

        self.sessions.record_result(
            session_id=session_id,
            result=result,
            updated_at_utc=calculated_at_utc,
        )

        return result


__all__ = [
    "AQOS_PAPER_SESSION_SERVICE_VERSION",
    "DEFAULT_TOP_REJECTION_LIMIT",
    "PaperSessionRepository",
    "PaperSessionResultService",
    "PaperSessionService",
]
