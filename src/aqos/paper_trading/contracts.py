from __future__ import annotations

import re
from dataclasses import dataclass, field as dataclass_field, replace
from datetime import datetime
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from aqos.account_analytics.metrics import AccountTradeRecord


AQOS_PAPER_TRADING_VERSION = "1.0"


class PaperSide(str, Enum):
    LONG = "long"
    SHORT = "short"


class PaperAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class PaperOrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


#: Order types the paper broker accepts today. Anything else is refused rather
#: than silently treated as a market order.
SUPPORTED_PAPER_ORDER_TYPES = (
    PaperOrderType.MARKET,
    PaperOrderType.LIMIT,
    PaperOrderType.STOP,
)

#: Actions that open exposure. CLOSE reduces it instead.
OPENING_PAPER_ACTIONS = (PaperAction.BUY, PaperAction.SELL)


class PaperOrderStatus(str, Enum):
    CREATED = "created"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    FAILED = "failed"


class PaperPositionStatus(str, Enum):
    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"


class PaperRejectionReason(str, Enum):
    INVALID_QUANTITY = "invalid_quantity"
    INVALID_SYMBOL = "invalid_symbol"
    INVALID_PRICE = "invalid_price"
    MISSING_REQUIRED_FIELD = "missing_required_field"
    UNSUPPORTED_ORDER_TYPE = "unsupported_order_type"
    UNSAFE_ACTION = "unsafe_action"
    ACCOUNT_NOT_ACTIVE = "account_not_active"
    ACCOUNT_NOT_PAPER = "account_not_paper"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    NO_OPEN_POSITION = "no_open_position"
    ORDER_NOT_FOUND = "order_not_found"


TERMINAL_PAPER_ORDER_STATUSES = (
    PaperOrderStatus.REJECTED,
    PaperOrderStatus.FILLED,
    PaperOrderStatus.CANCELLED,
    PaperOrderStatus.EXPIRED,
    PaperOrderStatus.FAILED,
)

PAPER_ORDER_TRANSITIONS: dict[PaperOrderStatus, tuple[PaperOrderStatus, ...]] = {
    PaperOrderStatus.CREATED: (
        PaperOrderStatus.ACCEPTED,
        PaperOrderStatus.REJECTED,
        PaperOrderStatus.CANCELLED,
        PaperOrderStatus.FAILED,
    ),
    PaperOrderStatus.ACCEPTED: (
        PaperOrderStatus.PARTIALLY_FILLED,
        PaperOrderStatus.FILLED,
        PaperOrderStatus.CANCELLED,
        PaperOrderStatus.EXPIRED,
        PaperOrderStatus.FAILED,
    ),
    PaperOrderStatus.PARTIALLY_FILLED: (
        PaperOrderStatus.PARTIALLY_FILLED,
        PaperOrderStatus.FILLED,
        PaperOrderStatus.CANCELLED,
        PaperOrderStatus.EXPIRED,
        PaperOrderStatus.FAILED,
    ),
    PaperOrderStatus.REJECTED: (),
    PaperOrderStatus.FILLED: (),
    PaperOrderStatus.CANCELLED: (),
    PaperOrderStatus.EXPIRED: (),
    PaperOrderStatus.FAILED: (),
}

PAPER_POSITION_TRANSITIONS: dict[
    PaperPositionStatus,
    tuple[PaperPositionStatus, ...],
] = {
    PaperPositionStatus.OPEN: (
        PaperPositionStatus.PARTIALLY_CLOSED,
        PaperPositionStatus.CLOSED,
    ),
    PaperPositionStatus.PARTIALLY_CLOSED: (
        PaperPositionStatus.PARTIALLY_CLOSED,
        PaperPositionStatus.CLOSED,
    ),
    PaperPositionStatus.CLOSED: (),
}


class PaperTradingError(ValueError):
    """Raised when a paper trading contract is used incorrectly."""


class InvalidPaperOrderTransitionError(PaperTradingError):
    """Raised when an order is asked to make a transition that is not allowed."""


class InvalidPaperPositionTransitionError(PaperTradingError):
    """Raised when a position is asked to make a transition that is not allowed."""


def normalize_paper_symbol(value: str) -> str:
    symbol = re.sub(r"\s+", "", value or "").upper()

    if not symbol:
        raise PaperTradingError("symbol cannot be empty.")

    return symbol


def require_text(value: str | None, field_name: str) -> str:
    text = (value or "").strip()

    if not text:
        raise PaperTradingError(f"{field_name} cannot be empty.")

    return text


def side_for_action(action: PaperAction) -> PaperSide:
    if action == PaperAction.BUY:
        return PaperSide.LONG

    if action == PaperAction.SELL:
        return PaperSide.SHORT

    raise PaperTradingError(f"{action.value} does not open a position.")


def can_transition_order(
    from_status: PaperOrderStatus,
    to_status: PaperOrderStatus,
) -> bool:
    return to_status in PAPER_ORDER_TRANSITIONS.get(from_status, ())


def validate_order_transition(
    from_status: PaperOrderStatus,
    to_status: PaperOrderStatus,
) -> None:
    if can_transition_order(from_status, to_status):
        return

    raise InvalidPaperOrderTransitionError(
        f"Paper order cannot move from {from_status.value} to {to_status.value}."
    )


def can_transition_position(
    from_status: PaperPositionStatus,
    to_status: PaperPositionStatus,
) -> bool:
    return to_status in PAPER_POSITION_TRANSITIONS.get(from_status, ())


def validate_position_transition(
    from_status: PaperPositionStatus,
    to_status: PaperPositionStatus,
) -> None:
    if can_transition_position(from_status, to_status):
        return

    raise InvalidPaperPositionTransitionError(
        f"Paper position cannot move from {from_status.value} to "
        f"{to_status.value}."
    )


@dataclass(frozen=True)
class PaperExecutionRequest:
    """A request to place a paper order."""

    user_id: str
    account_id: str
    symbol: str
    action: PaperAction
    quantity: float
    order_type: PaperOrderType
    submitted_at_utc: datetime
    signal_id: str | None = None
    requested_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "user_id", require_text(self.user_id, "user_id"))
        object.__setattr__(
            self,
            "account_id",
            require_text(self.account_id, "account_id"),
        )
        object.__setattr__(self, "symbol", normalize_paper_symbol(self.symbol))

    @property
    def is_opening(self) -> bool:
        return self.action in OPENING_PAPER_ACTIONS

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "account_id": self.account_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "requested_price": self.requested_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "submitted_at_utc": self.submitted_at_utc.isoformat(),
            "is_opening": self.is_opening,
            "metadata": self.extra_metadata,
        }


@dataclass(frozen=True)
class PaperFill:
    fill_id: str
    order_id: str
    quantity: float
    price: float
    filled_at_utc: datetime
    commission: float = 0.0

    def __post_init__(self) -> None:
        require_text(self.fill_id, "fill_id")
        require_text(self.order_id, "order_id")

        if self.quantity <= 0:
            raise PaperTradingError("fill quantity must be positive.")

        if self.price <= 0:
            raise PaperTradingError("fill price must be positive.")

        if self.commission < 0:
            raise PaperTradingError("commission cannot be negative.")

    @property
    def notional(self) -> float:
        return self.quantity * self.price

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "quantity": self.quantity,
            "price": self.price,
            "notional": self.notional,
            "commission": self.commission,
            "filled_at_utc": self.filled_at_utc.isoformat(),
        }


@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    account_id: str
    user_id: str
    symbol: str
    action: PaperAction
    order_type: PaperOrderType
    quantity: float
    status: PaperOrderStatus
    created_at_utc: datetime
    updated_at_utc: datetime
    signal_id: str | None = None
    requested_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    rejection_reason: PaperRejectionReason | None = None
    rejection_message: str | None = None
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.order_id, "order_id")
        require_text(self.account_id, "account_id")

        if self.quantity <= 0:
            raise PaperTradingError("order quantity must be positive.")

        if self.filled_quantity < 0:
            raise PaperTradingError("filled_quantity cannot be negative.")

        if self.filled_quantity > self.quantity:
            raise PaperTradingError("filled_quantity cannot exceed quantity.")

        if (
            self.status == PaperOrderStatus.REJECTED
            and self.rejection_reason is None
        ):
            raise PaperTradingError(
                "A rejected paper order must carry a rejection reason."
            )

    @property
    def remaining_quantity(self) -> float:
        return self.quantity - self.filled_quantity

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_PAPER_ORDER_STATUSES

    @property
    def is_open(self) -> bool:
        return not self.is_terminal

    def with_status(
        self,
        status: PaperOrderStatus,
        updated_at_utc: datetime,
        rejection_reason: PaperRejectionReason | None = None,
        rejection_message: str | None = None,
    ) -> "PaperOrder":
        validate_order_transition(self.status, status)

        return replace(
            self,
            status=status,
            updated_at_utc=updated_at_utc,
            rejection_reason=rejection_reason or self.rejection_reason,
            rejection_message=rejection_message or self.rejection_message,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "account_id": self.account_id,
            "user_id": self.user_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "action": self.action.value,
            "order_type": self.order_type.value,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_fill_price": self.average_fill_price,
            "requested_price": self.requested_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "status": self.status.value,
            "is_terminal": self.is_terminal,
            "rejection_reason": (
                self.rejection_reason.value if self.rejection_reason else None
            ),
            "rejection_message": self.rejection_message,
            "created_at_utc": self.created_at_utc.isoformat(),
            "updated_at_utc": self.updated_at_utc.isoformat(),
            "metadata": self.extra_metadata,
        }


@dataclass(frozen=True)
class PaperPosition:
    position_id: str
    account_id: str
    symbol: str
    side: PaperSide
    quantity: float
    entry_price: float
    opened_at_utc: datetime
    status: PaperPositionStatus = PaperPositionStatus.OPEN
    closed_quantity: float = 0.0
    stop_loss: float | None = None
    take_profit: float | None = None
    realized_pnl: float = 0.0
    closed_at_utc: datetime | None = None
    order_id: str | None = None
    signal_id: str | None = None
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.position_id, "position_id")

        if self.quantity <= 0:
            raise PaperTradingError("position quantity must be positive.")

        if self.entry_price <= 0:
            raise PaperTradingError("entry_price must be positive.")

        if self.closed_quantity < 0:
            raise PaperTradingError("closed_quantity cannot be negative.")

        if self.closed_quantity > self.quantity:
            raise PaperTradingError("closed_quantity cannot exceed quantity.")

        if (
            self.status == PaperPositionStatus.CLOSED
            and self.closed_at_utc is None
        ):
            raise PaperTradingError(
                "A closed paper position must carry a close time."
            )

    @property
    def open_quantity(self) -> float:
        return self.quantity - self.closed_quantity

    @property
    def is_open(self) -> bool:
        return self.status != PaperPositionStatus.CLOSED

    def unrealized_pnl(self, current_price: float) -> float:
        if current_price <= 0:
            raise PaperTradingError("current_price must be positive.")

        direction = 1.0 if self.side == PaperSide.LONG else -1.0

        return (current_price - self.entry_price) * self.open_quantity * direction

    def to_dict(self) -> dict[str, Any]:
        return {
            "position_id": self.position_id,
            "account_id": self.account_id,
            "order_id": self.order_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "closed_quantity": self.closed_quantity,
            "open_quantity": self.open_quantity,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "status": self.status.value,
            "realized_pnl": self.realized_pnl,
            "is_open": self.is_open,
            "opened_at_utc": self.opened_at_utc.isoformat(),
            "closed_at_utc": (
                self.closed_at_utc.isoformat() if self.closed_at_utc else None
            ),
            "metadata": self.extra_metadata,
        }


@dataclass(frozen=True)
class PaperTrade:
    """
    A closed paper trade.

    This is the first real producer of ``AccountTradeRecord``: analytics read
    these, never invented numbers.
    """

    trade_id: str
    position_id: str
    account_id: str
    symbol: str
    side: PaperSide
    quantity: float
    entry_price: float
    exit_price: float
    opened_at_utc: datetime
    closed_at_utc: datetime
    gross_pnl: float
    commission: float = 0.0
    risk_amount: float | None = None
    reward_amount: float | None = None
    balance_after: float | None = None
    signal_id: str | None = None
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.trade_id, "trade_id")
        require_text(self.position_id, "position_id")

        if self.quantity <= 0:
            raise PaperTradingError("trade quantity must be positive.")

        if self.entry_price <= 0 or self.exit_price <= 0:
            raise PaperTradingError("trade prices must be positive.")

        if self.commission < 0:
            raise PaperTradingError("commission cannot be negative.")

        if self.closed_at_utc < self.opened_at_utc:
            raise PaperTradingError("closed_at_utc cannot be before opened_at_utc.")

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.commission

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0

    def to_account_trade_record(self) -> AccountTradeRecord:
        """Convert to the analytics contract from Sprint 046."""

        return AccountTradeRecord(
            trade_id=self.trade_id,
            net_pnl=self.net_pnl,
            closed_at_utc=self.closed_at_utc,
            opened_at_utc=self.opened_at_utc,
            symbol=self.symbol,
            risk_amount=self.risk_amount,
            reward_amount=self.reward_amount,
            balance_after=self.balance_after,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "trade_id": self.trade_id,
            "position_id": self.position_id,
            "account_id": self.account_id,
            "signal_id": self.signal_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "gross_pnl": self.gross_pnl,
            "commission": self.commission,
            "net_pnl": self.net_pnl,
            "is_win": self.is_win,
            "risk_amount": self.risk_amount,
            "reward_amount": self.reward_amount,
            "balance_after": self.balance_after,
            "opened_at_utc": self.opened_at_utc.isoformat(),
            "closed_at_utc": self.closed_at_utc.isoformat(),
            "metadata": self.extra_metadata,
        }


@dataclass(frozen=True)
class PaperBalance:
    currency: str
    starting_balance: float
    current_balance: float
    equity: float
    margin_used: float = 0.0

    def __post_init__(self) -> None:
        if self.starting_balance <= 0:
            raise PaperTradingError("starting_balance must be positive.")

        if self.current_balance < 0:
            raise PaperTradingError("current_balance cannot be negative.")

        if self.equity < 0:
            raise PaperTradingError("equity cannot be negative.")

        if self.margin_used < 0:
            raise PaperTradingError("margin_used cannot be negative.")

    @property
    def free_margin(self) -> float:
        return max(0.0, self.equity - self.margin_used)

    @property
    def realized_pnl(self) -> float:
        return self.current_balance - self.starting_balance

    @property
    def open_pnl(self) -> float:
        return self.equity - self.current_balance

    def to_dict(self) -> dict[str, Any]:
        return {
            "currency": self.currency,
            "starting_balance": self.starting_balance,
            "current_balance": self.current_balance,
            "equity": self.equity,
            "margin_used": self.margin_used,
            "free_margin": self.free_margin,
            "realized_pnl": self.realized_pnl,
            "open_pnl": self.open_pnl,
        }


@dataclass(frozen=True)
class PaperAccountState:
    account_id: str
    balance: PaperBalance
    updated_at_utc: datetime
    open_position_count: int = 0
    open_order_count: int = 0
    closed_trade_count: int = 0

    def __post_init__(self) -> None:
        require_text(self.account_id, "account_id")

        for field_name in (
            "open_position_count",
            "open_order_count",
            "closed_trade_count",
        ):
            if getattr(self, field_name) < 0:
                raise PaperTradingError(f"{field_name} cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "balance": self.balance.to_dict(),
            "open_position_count": self.open_position_count,
            "open_order_count": self.open_order_count,
            "closed_trade_count": self.closed_trade_count,
            "updated_at_utc": self.updated_at_utc.isoformat(),
        }


@dataclass(frozen=True)
class PaperExecutionResult:
    accepted: bool
    request: PaperExecutionRequest
    account_state: PaperAccountState
    order: PaperOrder | None = None
    fills: tuple[PaperFill, ...] = ()
    position: PaperPosition | None = None
    trade: PaperTrade | None = None
    rejection_reason: PaperRejectionReason | None = None
    rejection_message: str | None = None
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.accepted and self.rejection_reason is None:
            raise PaperTradingError(
                "A rejected paper execution must carry a rejection reason."
            )

        if self.accepted and self.order is None:
            raise PaperTradingError(
                "An accepted paper execution must carry an order."
            )

    @property
    def order_id(self) -> str | None:
        return self.order.order_id if self.order is not None else None

    @property
    def filled_quantity(self) -> float:
        return sum(fill.quantity for fill in self.fills)

    def raise_if_rejected(self) -> None:
        if self.accepted:
            return

        raise PaperTradingError(
            f"Paper execution rejected "
            f"({self.rejection_reason.value if self.rejection_reason else 'unknown'}): "
            f"{self.rejection_message or 'no message'}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "order_id": self.order_id,
            "rejection_reason": (
                self.rejection_reason.value if self.rejection_reason else None
            ),
            "rejection_message": self.rejection_message,
            "filled_quantity": self.filled_quantity,
            "request": self.request.to_dict(),
            "order": self.order.to_dict() if self.order is not None else None,
            "fills": [fill.to_dict() for fill in self.fills],
            "position": (
                self.position.to_dict() if self.position is not None else None
            ),
            "trade": self.trade.to_dict() if self.trade is not None else None,
            "account_state": self.account_state.to_dict(),
            "metadata": self.extra_metadata,
        }


@runtime_checkable
class PaperBroker(Protocol):
    """
    The paper broker contract.

    An implementation must never contact an external venue: paper trading is
    simulated entirely inside AQOS.
    """

    def get_account_state(self) -> PaperAccountState:
        ...

    def submit_order(self, request: PaperExecutionRequest) -> PaperExecutionResult:
        ...

    def cancel_order(self, order_id: str) -> PaperExecutionResult:
        ...

    def list_open_positions(self) -> tuple[PaperPosition, ...]:
        ...

    def list_orders(self) -> tuple[PaperOrder, ...]:
        ...

    def list_fills(self) -> tuple[PaperFill, ...]:
        ...

    def list_trades(self) -> tuple[PaperTrade, ...]:
        ...


__all__ = [
    "AQOS_PAPER_TRADING_VERSION",
    "InvalidPaperOrderTransitionError",
    "InvalidPaperPositionTransitionError",
    "OPENING_PAPER_ACTIONS",
    "PAPER_ORDER_TRANSITIONS",
    "PAPER_POSITION_TRANSITIONS",
    "PaperAccountState",
    "PaperAction",
    "PaperBalance",
    "PaperBroker",
    "PaperExecutionRequest",
    "PaperExecutionResult",
    "PaperFill",
    "PaperOrder",
    "PaperOrderStatus",
    "PaperOrderType",
    "PaperPosition",
    "PaperPositionStatus",
    "PaperRejectionReason",
    "PaperSide",
    "PaperTrade",
    "PaperTradingError",
    "SUPPORTED_PAPER_ORDER_TYPES",
    "TERMINAL_PAPER_ORDER_STATUSES",
    "can_transition_order",
    "can_transition_position",
    "normalize_paper_symbol",
    "require_text",
    "side_for_action",
    "validate_order_transition",
    "validate_position_transition",
]
