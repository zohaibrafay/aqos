from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from aqos.database.repository import AqosRepository, RepositoryError
from aqos.database.types import database_utc_now
from aqos.paper_trading.contracts import (
    PaperFill,
    PaperOrder,
    PaperOrderStatus,
    PaperPosition,
    PaperPositionStatus,
    PaperRejectionReason,
    PaperSide,
    PaperTrade,
    TERMINAL_PAPER_ORDER_STATUSES,
    validate_order_transition,
    validate_position_transition,
)
from aqos.paper_trading.eligibility import PaperExecutionEligibilityDecision
from aqos.paper_trading.models import (
    PaperAccountSnapshotRecord,
    PaperExecutionDecisionRecord,
    PaperFillRecord,
    PaperOrderRecord,
    PaperPositionRecord,
    PaperTradeRecord,
    as_amount,
)
from aqos.paper_trading.simulator import PaperExitReason
from aqos.users.repositories import build_entity_id


AQOS_PAPER_REPOSITORIES_VERSION = "1.0"


class PaperOrderRepository(AqosRepository[PaperOrderRecord]):
    """
    Paper order store.

    Status changes go through the same transition table the in-memory broker
    uses, so persistence can never reach a state the contracts forbid.
    """

    model = PaperOrderRecord

    def create_order(
        self,
        order: PaperOrder,
    ) -> PaperOrderRecord:
        record = PaperOrderRecord.from_contract(order)
        record.assert_rejection_is_explained()

        self.add(record)

        # Fills and positions reference the order row, so it must exist first.
        self.flush()

        return record

    def require_order(self, order_id: str) -> PaperOrderRecord:
        return self.require(order_id)

    def transition_order(
        self,
        order_id: str,
        to_status: PaperOrderStatus,
        updated_at_utc: datetime | None = None,
        rejection_reason: PaperRejectionReason | None = None,
        rejection_message: str | None = None,
    ) -> PaperOrderRecord:
        record = self.require_order(order_id)

        validate_order_transition(record.status, to_status)

        record.status = to_status
        record.updated_at_utc = updated_at_utc or database_utc_now()

        if rejection_reason is not None:
            record.rejection_reason = rejection_reason

        if rejection_message is not None:
            record.rejection_message = rejection_message

        record.assert_rejection_is_explained()
        self.flush()

        return record

    def record_fill_on_order(
        self,
        order_id: str,
        quantity: float,
        price: float,
        filled_at_utc: datetime,
    ) -> PaperOrderRecord:
        """Fold one fill into the order's filled quantity and average price."""

        record = self.require_order(order_id)

        if quantity <= 0:
            raise RepositoryError("Fill quantity must be positive.")

        already_filled = as_amount(record.filled_quantity)
        total_quantity = as_amount(record.quantity)

        if already_filled + quantity > total_quantity + 1e-9:
            raise RepositoryError(
                f"Fill of {quantity} would exceed order quantity {total_quantity}."
            )

        previous_notional = already_filled * as_amount(
            record.average_fill_price or 0.0
        )
        new_filled = already_filled + quantity

        record.filled_quantity = new_filled
        record.average_fill_price = (previous_notional + quantity * price) / new_filled

        target = (
            PaperOrderStatus.FILLED
            if abs(new_filled - total_quantity) <= 1e-9
            else PaperOrderStatus.PARTIALLY_FILLED
        )

        validate_order_transition(record.status, target)
        record.status = target
        record.updated_at_utc = filled_at_utc

        self.flush()

        return record

    def list_orders(
        self,
        account_id: str | None = None,
        user_id: str | None = None,
        signal_id: str | None = None,
        status: PaperOrderStatus | None = None,
        symbol: str | None = None,
        created_since_utc: datetime | None = None,
        created_until_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperOrderRecord, ...]:
        statement = select(PaperOrderRecord)

        if account_id is not None:
            statement = statement.where(PaperOrderRecord.account_id == account_id)

        if user_id is not None:
            statement = statement.where(PaperOrderRecord.user_id == user_id)

        if signal_id is not None:
            statement = statement.where(PaperOrderRecord.signal_id == signal_id)

        if status is not None:
            statement = statement.where(PaperOrderRecord.status == status)

        if symbol is not None:
            statement = statement.where(
                PaperOrderRecord.symbol == "".join(str(symbol).split()).upper()
            )

        if created_since_utc is not None:
            statement = statement.where(
                PaperOrderRecord.created_at_utc >= created_since_utc
            )

        if created_until_utc is not None:
            statement = statement.where(
                PaperOrderRecord.created_at_utc <= created_until_utc
            )

        statement = statement.order_by(
            PaperOrderRecord.created_at_utc,
            PaperOrderRecord.order_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def list_open_orders(
        self,
        account_id: str | None = None,
    ) -> tuple[PaperOrderRecord, ...]:
        statement = select(PaperOrderRecord).where(
            PaperOrderRecord.status.not_in(tuple(TERMINAL_PAPER_ORDER_STATUSES))
        )

        if account_id is not None:
            statement = statement.where(PaperOrderRecord.account_id == account_id)

        statement = statement.order_by(
            PaperOrderRecord.created_at_utc,
            PaperOrderRecord.order_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def count_open_orders(self, account_id: str) -> int:
        return len(self.list_open_orders(account_id=account_id))

    def has_execution_for_signal(self, account_id: str, signal_id: str) -> bool:
        """
        Whether a signal already produced a live or filled order on this account.

        Rejected and cancelled orders do not count: those never consumed the
        signal, so retrying after a rejection stays allowed.
        """

        blocking = tuple(
            status
            for status in PaperOrderStatus
            if status
            not in (
                PaperOrderStatus.REJECTED,
                PaperOrderStatus.CANCELLED,
                PaperOrderStatus.EXPIRED,
                PaperOrderStatus.FAILED,
            )
        )

        statement = (
            select(func.count())
            .select_from(PaperOrderRecord)
            .where(PaperOrderRecord.account_id == account_id)
            .where(PaperOrderRecord.signal_id == signal_id)
            .where(PaperOrderRecord.status.in_(blocking))
        )

        return int(self.session.execute(statement).scalar_one()) > 0

    def count_by_status(self, account_id: str | None = None) -> dict[str, int]:
        statement = select(PaperOrderRecord.status, func.count()).group_by(
            PaperOrderRecord.status
        )

        if account_id is not None:
            statement = statement.where(PaperOrderRecord.account_id == account_id)

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

    def delete_order(self, order_id: str) -> bool:
        return self.delete_by_primary_key(order_id)


class PaperPositionRepository(AqosRepository[PaperPositionRecord]):
    """Paper position store."""

    model = PaperPositionRecord

    def open_position(self, position: PaperPosition) -> PaperPositionRecord:
        record = PaperPositionRecord.from_contract(position)
        record.assert_close_is_timestamped()

        self.add(record)

        # Fills and trades reference the position row.
        self.flush()

        return record

    def require_position(self, position_id: str) -> PaperPositionRecord:
        return self.require(position_id)

    def close_position(
        self,
        position_id: str,
        closed_quantity: float,
        realized_pnl: float,
        closed_at_utc: datetime,
    ) -> PaperPositionRecord:
        record = self.require_position(position_id)

        if closed_quantity <= 0:
            raise RepositoryError("closed_quantity must be positive.")

        total_quantity = as_amount(record.quantity)
        already_closed = as_amount(record.closed_quantity)
        new_closed = already_closed + closed_quantity

        if new_closed > total_quantity + 1e-9:
            raise RepositoryError(
                f"Closing {closed_quantity} would exceed position quantity "
                f"{total_quantity}."
            )

        target = (
            PaperPositionStatus.CLOSED
            if abs(new_closed - total_quantity) <= 1e-9
            else PaperPositionStatus.PARTIALLY_CLOSED
        )

        validate_position_transition(record.status, target)

        record.closed_quantity = new_closed
        record.realized_pnl = as_amount(record.realized_pnl) + realized_pnl
        record.status = target

        if target == PaperPositionStatus.CLOSED:
            record.closed_at_utc = closed_at_utc

        record.assert_close_is_timestamped()
        self.flush()

        return record

    def list_positions(
        self,
        account_id: str | None = None,
        symbol: str | None = None,
        side: PaperSide | None = None,
        status: PaperPositionStatus | None = None,
        opened_since_utc: datetime | None = None,
        opened_until_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperPositionRecord, ...]:
        statement = select(PaperPositionRecord)

        if account_id is not None:
            statement = statement.where(PaperPositionRecord.account_id == account_id)

        if symbol is not None:
            statement = statement.where(
                PaperPositionRecord.symbol == "".join(str(symbol).split()).upper()
            )

        if side is not None:
            statement = statement.where(PaperPositionRecord.side == side)

        if status is not None:
            statement = statement.where(PaperPositionRecord.status == status)

        if opened_since_utc is not None:
            statement = statement.where(
                PaperPositionRecord.opened_at_utc >= opened_since_utc
            )

        if opened_until_utc is not None:
            statement = statement.where(
                PaperPositionRecord.opened_at_utc <= opened_until_utc
            )

        statement = statement.order_by(
            PaperPositionRecord.opened_at_utc,
            PaperPositionRecord.position_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def list_open_positions(
        self,
        account_id: str | None = None,
        symbol: str | None = None,
    ) -> tuple[PaperPositionRecord, ...]:
        statement = select(PaperPositionRecord).where(
            PaperPositionRecord.status != PaperPositionStatus.CLOSED
        )

        if account_id is not None:
            statement = statement.where(PaperPositionRecord.account_id == account_id)

        if symbol is not None:
            statement = statement.where(
                PaperPositionRecord.symbol == "".join(str(symbol).split()).upper()
            )

        statement = statement.order_by(
            PaperPositionRecord.opened_at_utc,
            PaperPositionRecord.position_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def count_open_positions(self, account_id: str) -> int:
        return len(self.list_open_positions(account_id=account_id))

    def delete_position(self, position_id: str) -> bool:
        return self.delete_by_primary_key(position_id)


class PaperFillRepository(AqosRepository[PaperFillRecord]):
    """Paper fill store."""

    model = PaperFillRecord

    def record_fill(
        self,
        fill: PaperFill,
        account_id: str,
        position_id: str | None = None,
    ) -> PaperFillRecord:
        record = PaperFillRecord.from_contract(
            fill,
            account_id=account_id,
            position_id=position_id,
        )

        self.add(record)
        self.flush()

        return record

    def list_fills(
        self,
        account_id: str | None = None,
        order_id: str | None = None,
        position_id: str | None = None,
        filled_since_utc: datetime | None = None,
        filled_until_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperFillRecord, ...]:
        statement = select(PaperFillRecord)

        if account_id is not None:
            statement = statement.where(PaperFillRecord.account_id == account_id)

        if order_id is not None:
            statement = statement.where(PaperFillRecord.order_id == order_id)

        if position_id is not None:
            statement = statement.where(PaperFillRecord.position_id == position_id)

        if filled_since_utc is not None:
            statement = statement.where(
                PaperFillRecord.filled_at_utc >= filled_since_utc
            )

        if filled_until_utc is not None:
            statement = statement.where(
                PaperFillRecord.filled_at_utc <= filled_until_utc
            )

        statement = statement.order_by(
            PaperFillRecord.filled_at_utc,
            PaperFillRecord.fill_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def total_commission(self, account_id: str) -> float:
        statement = (
            select(func.sum(PaperFillRecord.commission))
            .select_from(PaperFillRecord)
            .where(PaperFillRecord.account_id == account_id)
        )

        total = self.session.execute(statement).scalar_one_or_none()

        return as_amount(total) if total is not None else 0.0


class PaperTradeRepository(AqosRepository[PaperTradeRecord]):
    """
    Closed paper trade store.

    These rows are the only source analytics reads from; nothing here invents
    a trade that was not actually simulated.
    """

    model = PaperTradeRecord

    def record_trade(
        self,
        trade: PaperTrade,
        exit_reason: PaperExitReason = PaperExitReason.MANUAL_CLOSE,
    ) -> PaperTradeRecord:
        record = PaperTradeRecord.from_contract(trade, exit_reason=exit_reason)
        record.assert_net_pnl_is_derived()

        self.add(record)
        self.flush()

        return record

    def list_trades(
        self,
        account_id: str | None = None,
        symbol: str | None = None,
        signal_id: str | None = None,
        exit_reason: PaperExitReason | None = None,
        side: PaperSide | None = None,
        closed_since_utc: datetime | None = None,
        closed_until_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[PaperTradeRecord, ...]:
        statement = select(PaperTradeRecord)

        if account_id is not None:
            statement = statement.where(PaperTradeRecord.account_id == account_id)

        if symbol is not None:
            statement = statement.where(
                PaperTradeRecord.symbol == "".join(str(symbol).split()).upper()
            )

        if signal_id is not None:
            statement = statement.where(PaperTradeRecord.signal_id == signal_id)

        if exit_reason is not None:
            statement = statement.where(PaperTradeRecord.exit_reason == exit_reason)

        if side is not None:
            statement = statement.where(PaperTradeRecord.side == side)

        if closed_since_utc is not None:
            statement = statement.where(
                PaperTradeRecord.closed_at_utc >= closed_since_utc
            )

        if closed_until_utc is not None:
            statement = statement.where(
                PaperTradeRecord.closed_at_utc <= closed_until_utc
            )

        statement = statement.order_by(
            PaperTradeRecord.closed_at_utc,
            PaperTradeRecord.trade_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def build_account_trade_records(self, account_id: str) -> tuple[Any, ...]:
        """Hand persisted trades to the Sprint 046 analytics contract."""

        return tuple(
            record.to_account_trade_record()
            for record in self.list_trades(account_id=account_id)
        )

    def count_trades(self, account_id: str) -> int:
        statement = (
            select(func.count())
            .select_from(PaperTradeRecord)
            .where(PaperTradeRecord.account_id == account_id)
        )

        return int(self.session.execute(statement).scalar_one())

    def net_pnl(self, account_id: str) -> float | None:
        """
        Total net PnL, or None when the account has no closed trades.

        A missing history is not a zero result, so the two stay distinguishable.
        """

        if self.count_trades(account_id) == 0:
            return None

        statement = (
            select(func.sum(PaperTradeRecord.net_pnl))
            .select_from(PaperTradeRecord)
            .where(PaperTradeRecord.account_id == account_id)
        )

        total = self.session.execute(statement).scalar_one_or_none()

        return as_amount(total) if total is not None else 0.0

    def count_by_exit_reason(self, account_id: str) -> dict[str, int]:
        statement = (
            select(PaperTradeRecord.exit_reason, func.count())
            .where(PaperTradeRecord.account_id == account_id)
            .group_by(PaperTradeRecord.exit_reason)
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


class PaperAccountSnapshotRepository(AqosRepository[PaperAccountSnapshotRecord]):
    """Paper balance snapshot store."""

    model = PaperAccountSnapshotRecord

    def capture_snapshot(
        self,
        account_id: str,
        starting_balance: float,
        current_balance: float,
        equity: float,
        captured_at_utc: datetime | None = None,
        currency: str = "USD",
        margin_used: float = 0.0,
        open_position_count: int = 0,
        open_order_count: int = 0,
        closed_trade_count: int = 0,
        metadata: dict[str, Any] | None = None,
        snapshot_id: str | None = None,
    ) -> PaperAccountSnapshotRecord:
        record = PaperAccountSnapshotRecord(
            snapshot_id=snapshot_id or build_entity_id("papersnap"),
            account_id=account_id,
            currency=currency,
            starting_balance=starting_balance,
            current_balance=current_balance,
            equity=equity,
            margin_used=margin_used,
            open_position_count=open_position_count,
            open_order_count=open_order_count,
            closed_trade_count=closed_trade_count,
            captured_at_utc=captured_at_utc or database_utc_now(),
            extra_metadata=metadata or {},
        )

        self.add(record)
        self.flush()

        return record

    def list_snapshots(
        self,
        account_id: str | None = None,
        limit: int | None = None,
    ) -> tuple[PaperAccountSnapshotRecord, ...]:
        statement = select(PaperAccountSnapshotRecord)

        if account_id is not None:
            statement = statement.where(
                PaperAccountSnapshotRecord.account_id == account_id
            )

        statement = statement.order_by(
            PaperAccountSnapshotRecord.captured_at_utc,
            PaperAccountSnapshotRecord.snapshot_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def latest_snapshot(
        self,
        account_id: str,
    ) -> PaperAccountSnapshotRecord | None:
        snapshots = self.list_snapshots(account_id=account_id)

        return snapshots[-1] if snapshots else None


class PaperExecutionDecisionRepository(AqosRepository[PaperExecutionDecisionRecord]):
    """
    Audit trail for paper execution rule decisions.

    Refusals are stored too, so "why did nothing happen?" is answerable from
    structured reason codes rather than from logs.
    """

    model = PaperExecutionDecisionRecord

    def record_decision(
        self,
        decision: PaperExecutionEligibilityDecision,
        decided_at_utc: datetime | None = None,
        order_id: str | None = None,
        decision_id: str | None = None,
    ) -> PaperExecutionDecisionRecord:
        primary = decision.primary_reason

        record = PaperExecutionDecisionRecord(
            decision_id=decision_id or build_entity_id("paperdecision"),
            user_id=decision.user_id,
            account_id=decision.account_id,
            signal_id=decision.signal_id,
            order_id=order_id,
            symbol=decision.symbol,
            is_allowed=decision.is_allowed,
            requested_execution_mode=decision.requested_execution_mode,
            effective_execution_mode=decision.effective_execution_mode,
            primary_reason_code=primary.code.value if primary else None,
            blocking_reason_count=len(decision.blocking_reasons),
            blocking_sources_json=list(decision.blocking_sources),
            reasons_json=[reason.to_dict() for reason in decision.reasons],
            decided_at_utc=decided_at_utc or database_utc_now(),
            extra_metadata=dict(decision.decision_metadata),
        )
        record.assert_decision_is_explained()

        self.add(record)
        self.flush()

        return record

    def attach_order(
        self,
        decision_id: str,
        order_id: str,
    ) -> PaperExecutionDecisionRecord:
        record = self.require(decision_id)
        record.order_id = order_id

        self.flush()

        return record

    def list_decisions(
        self,
        account_id: str | None = None,
        user_id: str | None = None,
        signal_id: str | None = None,
        is_allowed: bool | None = None,
        primary_reason_code: str | None = None,
        limit: int | None = None,
    ) -> tuple[PaperExecutionDecisionRecord, ...]:
        statement = select(PaperExecutionDecisionRecord)

        if account_id is not None:
            statement = statement.where(
                PaperExecutionDecisionRecord.account_id == account_id
            )

        if user_id is not None:
            statement = statement.where(
                PaperExecutionDecisionRecord.user_id == user_id
            )

        if signal_id is not None:
            statement = statement.where(
                PaperExecutionDecisionRecord.signal_id == signal_id
            )

        if is_allowed is not None:
            statement = statement.where(
                PaperExecutionDecisionRecord.is_allowed == is_allowed
            )

        if primary_reason_code is not None:
            statement = statement.where(
                PaperExecutionDecisionRecord.primary_reason_code
                == primary_reason_code
            )

        statement = statement.order_by(
            PaperExecutionDecisionRecord.decided_at_utc,
            PaperExecutionDecisionRecord.decision_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def latest_decision(
        self,
        account_id: str,
    ) -> PaperExecutionDecisionRecord | None:
        decisions = self.list_decisions(account_id=account_id)

        return decisions[-1] if decisions else None

    def count_by_reason_code(self, account_id: str) -> dict[str, int]:
        statement = (
            select(
                PaperExecutionDecisionRecord.primary_reason_code,
                func.count(),
            )
            .where(PaperExecutionDecisionRecord.account_id == account_id)
            .where(PaperExecutionDecisionRecord.primary_reason_code.is_not(None))
            .group_by(PaperExecutionDecisionRecord.primary_reason_code)
        )

        rows = self.session.execute(statement).all()

        return {str(row[0]): int(row[1]) for row in sorted(rows, key=lambda r: str(r[0]))}

    def count_refusals(self, account_id: str) -> int:
        return len(self.list_decisions(account_id=account_id, is_allowed=False))


__all__ = [
    "AQOS_PAPER_REPOSITORIES_VERSION",
    "PaperAccountSnapshotRepository",
    "PaperExecutionDecisionRepository",
    "PaperFillRepository",
    "PaperOrderRepository",
    "PaperPositionRepository",
    "PaperTradeRepository",
]
