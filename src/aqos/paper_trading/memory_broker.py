from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import uuid4

from aqos.accounts.models import TradingAccount
from aqos.database.types import database_utc_now
from aqos.paper_trading.contracts import (
    PaperAccountState,
    PaperAction,
    PaperBalance,
    PaperExecutionRequest,
    PaperExecutionResult,
    PaperFill,
    PaperOrder,
    PaperOrderStatus,
    PaperPosition,
    PaperPositionStatus,
    PaperRejectionReason,
    PaperSide,
    PaperTrade,
    PaperTradingError,
    side_for_action,
)
from aqos.paper_trading.validation import validate_paper_execution_request


AQOS_PAPER_MEMORY_BROKER_VERSION = "1.0"


def build_paper_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


class InMemoryPaperBroker:
    """
    Reference ``PaperBroker`` implementation held entirely in memory.

    It validates and books orders, fills, positions and trades so the contracts
    can be exercised end to end. It contains no market simulation: filling is an
    explicit call, and matching, spread, slippage and stop handling arrive with
    the execution simulator in the next sprint.

    It never contacts an external venue.
    """

    def __init__(
        self,
        account: TradingAccount,
        starting_balance: float | None = None,
        currency: str | None = None,
    ) -> None:
        self.account = account
        self.currency = currency or account.currency
        self.starting_balance = float(
            starting_balance
            if starting_balance is not None
            else account.initial_balance
        )

        if self.starting_balance <= 0:
            raise PaperTradingError("starting_balance must be positive.")

        self.current_balance = self.starting_balance
        self._opened_at = account.created_at_utc or database_utc_now()
        self._orders: dict[str, PaperOrder] = {}
        self._fills: list[PaperFill] = []
        self._positions: dict[str, PaperPosition] = {}
        self._trades: list[PaperTrade] = []

    # Reads -----------------------------------------------------------------

    def get_account_state(self) -> PaperAccountState:
        open_positions = self.list_open_positions()

        return PaperAccountState(
            account_id=self.account.account_id,
            balance=PaperBalance(
                currency=self.currency,
                starting_balance=self.starting_balance,
                current_balance=self.current_balance,
                equity=self.current_balance,
            ),
            updated_at_utc=self._latest_timestamp(),
            open_position_count=len(open_positions),
            open_order_count=len(
                [order for order in self._orders.values() if order.is_open]
            ),
            closed_trade_count=len(self._trades),
        )

    def list_orders(self) -> tuple[PaperOrder, ...]:
        return tuple(
            sorted(self._orders.values(), key=lambda order: order.created_at_utc)
        )

    def list_open_positions(self) -> tuple[PaperPosition, ...]:
        return tuple(
            position
            for position in sorted(
                self._positions.values(),
                key=lambda item: item.opened_at_utc,
            )
            if position.is_open
        )

    def list_positions(self) -> tuple[PaperPosition, ...]:
        return tuple(
            sorted(self._positions.values(), key=lambda item: item.opened_at_utc)
        )

    def list_fills(self) -> tuple[PaperFill, ...]:
        return tuple(self._fills)

    def list_trades(self) -> tuple[PaperTrade, ...]:
        return tuple(self._trades)

    # Writes ----------------------------------------------------------------

    def submit_order(
        self,
        request: PaperExecutionRequest,
    ) -> PaperExecutionResult:
        validation = validate_paper_execution_request(request, self.account)

        if not validation.accepted:
            return PaperExecutionResult(
                accepted=False,
                request=request,
                account_state=self.get_account_state(),
                rejection_reason=validation.rejection_reason,
                rejection_message=validation.rejection_message,
            )

        if request.action == PaperAction.CLOSE and not self._open_positions_for(
            request.symbol
        ):
            return PaperExecutionResult(
                accepted=False,
                request=request,
                account_state=self.get_account_state(),
                rejection_reason=PaperRejectionReason.NO_OPEN_POSITION,
                rejection_message=f"No open position for {request.symbol}.",
            )

        order = PaperOrder(
            order_id=build_paper_id("paperorder"),
            account_id=request.account_id,
            user_id=request.user_id,
            symbol=request.symbol,
            action=request.action,
            order_type=request.order_type,
            quantity=request.quantity,
            status=PaperOrderStatus.CREATED,
            created_at_utc=request.submitted_at_utc,
            updated_at_utc=request.submitted_at_utc,
            signal_id=request.signal_id,
            requested_price=request.requested_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            extra_metadata=dict(request.extra_metadata),
        ).with_status(PaperOrderStatus.ACCEPTED, request.submitted_at_utc)

        self._orders[order.order_id] = order

        return PaperExecutionResult(
            accepted=True,
            request=request,
            account_state=self.get_account_state(),
            order=order,
        )

    def cancel_order(self, order_id: str) -> PaperExecutionResult:
        order = self._orders.get(order_id)

        if order is None:
            raise PaperTradingError(f"Paper order does not exist: {order_id}")

        cancelled = order.with_status(
            PaperOrderStatus.CANCELLED,
            order.updated_at_utc,
        )
        self._orders[order_id] = cancelled

        return PaperExecutionResult(
            accepted=True,
            request=self._request_from_order(cancelled),
            account_state=self.get_account_state(),
            order=cancelled,
        )

    def fill_order(
        self,
        order_id: str,
        price: float,
        quantity: float | None = None,
        filled_at_utc: datetime | None = None,
        commission: float = 0.0,
    ) -> PaperExecutionResult:
        """
        Fill an accepted order, wholly or in part.

        Filling is explicit in this sprint: deciding *when* a fill happens is
        the execution simulator's job.
        """

        order = self._orders.get(order_id)

        if order is None:
            raise PaperTradingError(f"Paper order does not exist: {order_id}")

        if order.is_terminal:
            raise PaperTradingError(
                f"Paper order is already {order.status.value}: {order_id}"
            )

        fill_quantity = order.remaining_quantity if quantity is None else quantity

        if fill_quantity <= 0:
            raise PaperTradingError("fill quantity must be positive.")

        if fill_quantity > order.remaining_quantity:
            raise PaperTradingError(
                "fill quantity cannot exceed the remaining order quantity."
            )

        timestamp = filled_at_utc or order.updated_at_utc

        fill = PaperFill(
            fill_id=build_paper_id("paperfill"),
            order_id=order_id,
            quantity=fill_quantity,
            price=price,
            filled_at_utc=timestamp,
            commission=commission,
        )
        self._fills.append(fill)

        filled_total = order.filled_quantity + fill_quantity
        average_price = self._average_fill_price(order_id)

        next_status = (
            PaperOrderStatus.FILLED
            if filled_total >= order.quantity
            else PaperOrderStatus.PARTIALLY_FILLED
        )

        updated_order = replace(
            order.with_status(next_status, timestamp),
            filled_quantity=filled_total,
            average_fill_price=average_price,
        )
        self._orders[order_id] = updated_order

        position, trade = self._apply_fill_to_positions(
            order=updated_order,
            fill=fill,
        )

        return PaperExecutionResult(
            accepted=True,
            request=self._request_from_order(updated_order),
            account_state=self.get_account_state(),
            order=updated_order,
            fills=(fill,),
            position=position,
            trade=trade,
        )

    # Internals --------------------------------------------------------------

    def _open_positions_for(self, symbol: str) -> tuple[PaperPosition, ...]:
        return tuple(
            position
            for position in self.list_open_positions()
            if position.symbol == symbol
        )

    def _average_fill_price(self, order_id: str) -> float:
        fills = [fill for fill in self._fills if fill.order_id == order_id]
        quantity = sum(fill.quantity for fill in fills)

        if quantity <= 0:
            raise PaperTradingError("Cannot average fills with no quantity.")

        return sum(fill.quantity * fill.price for fill in fills) / quantity

    def _apply_fill_to_positions(
        self,
        order: PaperOrder,
        fill: PaperFill,
    ) -> tuple[PaperPosition | None, PaperTrade | None]:
        if order.action in (PaperAction.BUY, PaperAction.SELL):
            return self._open_position(order, fill), None

        return self._close_position(order, fill)

    def _open_position(
        self,
        order: PaperOrder,
        fill: PaperFill,
    ) -> PaperPosition:
        position = PaperPosition(
            position_id=build_paper_id("paperposition"),
            account_id=order.account_id,
            symbol=order.symbol,
            side=side_for_action(order.action),
            quantity=fill.quantity,
            entry_price=fill.price,
            opened_at_utc=fill.filled_at_utc,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            order_id=order.order_id,
            signal_id=order.signal_id,
        )

        self._positions[position.position_id] = position
        self.current_balance -= fill.commission

        return position

    def _close_position(
        self,
        order: PaperOrder,
        fill: PaperFill,
    ) -> tuple[PaperPosition | None, PaperTrade | None]:
        open_positions = self._open_positions_for(order.symbol)

        if not open_positions:
            raise PaperTradingError(f"No open position for {order.symbol}.")

        position = open_positions[0]
        close_quantity = min(fill.quantity, position.open_quantity)

        direction = 1.0 if position.side == PaperSide.LONG else -1.0
        gross_pnl = (fill.price - position.entry_price) * close_quantity * direction

        closed_total = position.closed_quantity + close_quantity
        fully_closed = closed_total >= position.quantity

        updated_position = PaperPosition(
            position_id=position.position_id,
            account_id=position.account_id,
            symbol=position.symbol,
            side=position.side,
            quantity=position.quantity,
            entry_price=position.entry_price,
            opened_at_utc=position.opened_at_utc,
            status=(
                PaperPositionStatus.CLOSED
                if fully_closed
                else PaperPositionStatus.PARTIALLY_CLOSED
            ),
            closed_quantity=closed_total,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            realized_pnl=position.realized_pnl + gross_pnl,
            closed_at_utc=fill.filled_at_utc if fully_closed else None,
            order_id=position.order_id,
            signal_id=position.signal_id,
            extra_metadata=dict(position.extra_metadata),
        )
        self._positions[position.position_id] = updated_position

        self.current_balance += gross_pnl - fill.commission

        trade = PaperTrade(
            trade_id=build_paper_id("papertrade"),
            position_id=position.position_id,
            account_id=position.account_id,
            symbol=position.symbol,
            side=position.side,
            quantity=close_quantity,
            entry_price=position.entry_price,
            exit_price=fill.price,
            opened_at_utc=position.opened_at_utc,
            closed_at_utc=fill.filled_at_utc,
            gross_pnl=gross_pnl,
            commission=fill.commission,
            balance_after=self.current_balance,
            signal_id=position.signal_id,
        )
        self._trades.append(trade)

        return updated_position, trade

    def _request_from_order(self, order: PaperOrder) -> PaperExecutionRequest:
        return PaperExecutionRequest(
            user_id=order.user_id,
            account_id=order.account_id,
            symbol=order.symbol,
            action=order.action,
            quantity=order.quantity,
            order_type=order.order_type,
            submitted_at_utc=order.created_at_utc,
            signal_id=order.signal_id,
            requested_price=order.requested_price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
        )

    def _latest_timestamp(self) -> datetime:
        timestamps = [order.updated_at_utc for order in self._orders.values()]
        timestamps.extend(fill.filled_at_utc for fill in self._fills)

        if timestamps:
            return max(timestamps)

        return self._opened_at


__all__ = [
    "AQOS_PAPER_MEMORY_BROKER_VERSION",
    "InMemoryPaperBroker",
    "build_paper_id",
]
