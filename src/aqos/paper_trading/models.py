from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, JSON, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, validates

from aqos.database.base import AQOS_TABLE_ARGS, AqosBase
from aqos.database.types import EnumString
from aqos.execution_policy.modes import ExecutionMode
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperFill,
    PaperOrder,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperPositionStatus,
    PaperRejectionReason,
    PaperSide,
    PaperTrade,
    PaperTradingError,
)
from aqos.paper_trading.simulator import PaperExitReason


AQOS_PAPER_MODELS_VERSION = "1.0"

MONEY_PRECISION = 8


def as_amount(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)

    return float(value)


class PaperOrderRecord(AqosBase):
    """A persisted paper order."""

    __tablename__ = "paper_orders"
    __table_args__ = AQOS_TABLE_ARGS

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("trading_signals.signal_id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[PaperAction] = mapped_column(
        EnumString(PaperAction, length=16),
        nullable=False,
    )
    order_type: Mapped[PaperOrderType] = mapped_column(
        EnumString(PaperOrderType, length=16),
        nullable=False,
    )
    status: Mapped[PaperOrderStatus] = mapped_column(
        EnumString(PaperOrderStatus),
        nullable=False,
        default=PaperOrderStatus.CREATED,
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    filled_quantity: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
        default=0,
    )
    average_fill_price: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    requested_price: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    stop_loss: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    take_profit: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    rejection_reason: Mapped[PaperRejectionReason | None] = mapped_column(
        EnumString(PaperRejectionReason, length=64),
        nullable=True,
    )
    rejection_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("status", PaperOrderStatus.CREATED)
        kwargs.setdefault("filled_quantity", 0)
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    def assert_rejection_is_explained(self) -> None:
        if (
            self.status == PaperOrderStatus.REJECTED
            and self.rejection_reason is None
        ):
            raise PaperTradingError(
                "A rejected paper order must carry a rejection reason."
            )

    @classmethod
    def from_contract(cls, order: PaperOrder) -> "PaperOrderRecord":
        return cls(
            order_id=order.order_id,
            user_id=order.user_id,
            account_id=order.account_id,
            signal_id=order.signal_id,
            symbol=order.symbol,
            action=order.action,
            order_type=order.order_type,
            status=order.status,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            average_fill_price=order.average_fill_price,
            requested_price=order.requested_price,
            stop_loss=order.stop_loss,
            take_profit=order.take_profit,
            rejection_reason=order.rejection_reason,
            rejection_message=order.rejection_message,
            created_at_utc=order.created_at_utc,
            updated_at_utc=order.updated_at_utc,
            extra_metadata=dict(order.extra_metadata),
        )

    def to_contract(self) -> PaperOrder:
        return PaperOrder(
            order_id=self.order_id,
            account_id=self.account_id,
            user_id=self.user_id,
            symbol=self.symbol,
            action=self.action,
            order_type=self.order_type,
            quantity=as_amount(self.quantity),
            status=self.status,
            created_at_utc=self.created_at_utc,
            updated_at_utc=self.updated_at_utc,
            signal_id=self.signal_id,
            requested_price=(
                as_amount(self.requested_price)
                if self.requested_price is not None
                else None
            ),
            stop_loss=(
                as_amount(self.stop_loss) if self.stop_loss is not None else None
            ),
            take_profit=(
                as_amount(self.take_profit) if self.take_profit is not None else None
            ),
            filled_quantity=as_amount(self.filled_quantity),
            average_fill_price=(
                as_amount(self.average_fill_price)
                if self.average_fill_price is not None
                else None
            ),
            rejection_reason=self.rejection_reason,
            rejection_message=self.rejection_message,
            extra_metadata=self.extra_metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_contract().to_dict()

    def __repr__(self) -> str:
        return f"PaperOrderRecord(order_id={self.order_id!r})"


class PaperPositionRecord(AqosBase):
    """A persisted paper position."""

    __tablename__ = "paper_positions"
    __table_args__ = AQOS_TABLE_ARGS

    position_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    order_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("paper_orders.order_id", ondelete="SET NULL"),
        nullable=True,
    )
    signal_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("trading_signals.signal_id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[PaperSide] = mapped_column(
        EnumString(PaperSide, length=16),
        nullable=False,
    )
    status: Mapped[PaperPositionStatus] = mapped_column(
        EnumString(PaperPositionStatus),
        nullable=False,
        default=PaperPositionStatus.OPEN,
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    closed_quantity: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
        default=0,
    )
    entry_price: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    stop_loss: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    take_profit: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    realized_pnl: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
        default=0,
    )
    opened_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at_utc: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("status", PaperPositionStatus.OPEN)
        kwargs.setdefault("closed_quantity", 0)
        kwargs.setdefault("realized_pnl", 0)
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    def assert_close_is_timestamped(self) -> None:
        if (
            self.status == PaperPositionStatus.CLOSED
            and self.closed_at_utc is None
        ):
            raise PaperTradingError(
                "A closed paper position must carry a close time."
            )

    @classmethod
    def from_contract(cls, position: PaperPosition) -> "PaperPositionRecord":
        return cls(
            position_id=position.position_id,
            account_id=position.account_id,
            order_id=position.order_id,
            signal_id=position.signal_id,
            symbol=position.symbol,
            side=position.side,
            status=position.status,
            quantity=position.quantity,
            closed_quantity=position.closed_quantity,
            entry_price=position.entry_price,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            realized_pnl=position.realized_pnl,
            opened_at_utc=position.opened_at_utc,
            closed_at_utc=position.closed_at_utc,
            extra_metadata=dict(position.extra_metadata),
        )

    def to_contract(self) -> PaperPosition:
        return PaperPosition(
            position_id=self.position_id,
            account_id=self.account_id,
            symbol=self.symbol,
            side=self.side,
            quantity=as_amount(self.quantity),
            entry_price=as_amount(self.entry_price),
            opened_at_utc=self.opened_at_utc,
            status=self.status,
            closed_quantity=as_amount(self.closed_quantity),
            stop_loss=(
                as_amount(self.stop_loss) if self.stop_loss is not None else None
            ),
            take_profit=(
                as_amount(self.take_profit) if self.take_profit is not None else None
            ),
            realized_pnl=as_amount(self.realized_pnl),
            closed_at_utc=self.closed_at_utc,
            order_id=self.order_id,
            signal_id=self.signal_id,
            extra_metadata=self.extra_metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_contract().to_dict()

    def __repr__(self) -> str:
        return f"PaperPositionRecord(position_id={self.position_id!r})"


class PaperFillRecord(AqosBase):
    """A persisted paper fill."""

    __tablename__ = "paper_fills"
    __table_args__ = AQOS_TABLE_ARGS

    fill_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("paper_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    position_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("paper_positions.position_id", ondelete="SET NULL"),
        nullable=True,
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    price: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    commission: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
        default=0,
    )
    filled_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("commission", 0)
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    @classmethod
    def from_contract(
        cls,
        fill: PaperFill,
        account_id: str,
        position_id: str | None = None,
    ) -> "PaperFillRecord":
        return cls(
            fill_id=fill.fill_id,
            order_id=fill.order_id,
            account_id=account_id,
            position_id=position_id,
            quantity=fill.quantity,
            price=fill.price,
            commission=fill.commission,
            filled_at_utc=fill.filled_at_utc,
        )

    def to_contract(self) -> PaperFill:
        return PaperFill(
            fill_id=self.fill_id,
            order_id=self.order_id,
            quantity=as_amount(self.quantity),
            price=as_amount(self.price),
            filled_at_utc=self.filled_at_utc,
            commission=as_amount(self.commission),
        )

    def to_dict(self) -> dict[str, Any]:
        return self.to_contract().to_dict()

    def __repr__(self) -> str:
        return f"PaperFillRecord(fill_id={self.fill_id!r})"


class PaperTradeRecord(AqosBase):
    """A persisted closed paper trade."""

    __tablename__ = "paper_trades"
    __table_args__ = AQOS_TABLE_ARGS

    trade_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    position_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("paper_positions.position_id", ondelete="SET NULL"),
        nullable=True,
    )
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("trading_signals.signal_id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[PaperSide] = mapped_column(
        EnumString(PaperSide, length=16),
        nullable=False,
    )
    quantity: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    entry_price: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    exit_price: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    gross_pnl: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    commission: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
        default=0,
    )
    net_pnl: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
    )
    exit_reason: Mapped[PaperExitReason] = mapped_column(
        EnumString(PaperExitReason),
        nullable=False,
        default=PaperExitReason.MANUAL_CLOSE,
    )
    risk_amount: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    reward_amount: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    balance_after: Mapped[float | None] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=True,
    )
    opened_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("commission", 0)
        kwargs.setdefault("exit_reason", PaperExitReason.MANUAL_CLOSE)
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    def assert_net_pnl_is_derived(self) -> None:
        """
        net_pnl must equal gross_pnl minus commission.

        A stored net that disagrees with its own inputs would corrupt every
        downstream analytic silently, so the row is refused instead.
        """

        expected = as_amount(self.gross_pnl) - as_amount(self.commission)

        if abs(as_amount(self.net_pnl) - expected) > 1e-8:
            raise PaperTradingError(
                "net_pnl must equal gross_pnl minus commission."
            )

    @classmethod
    def from_contract(
        cls,
        trade: PaperTrade,
        exit_reason: PaperExitReason = PaperExitReason.MANUAL_CLOSE,
    ) -> "PaperTradeRecord":
        return cls(
            trade_id=trade.trade_id,
            position_id=trade.position_id,
            account_id=trade.account_id,
            signal_id=trade.signal_id,
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            gross_pnl=trade.gross_pnl,
            commission=trade.commission,
            net_pnl=trade.net_pnl,
            exit_reason=exit_reason,
            risk_amount=trade.risk_amount,
            reward_amount=trade.reward_amount,
            balance_after=trade.balance_after,
            opened_at_utc=trade.opened_at_utc,
            closed_at_utc=trade.closed_at_utc,
            extra_metadata=dict(trade.extra_metadata),
        )

    def to_contract(self) -> PaperTrade:
        return PaperTrade(
            trade_id=self.trade_id,
            position_id=self.position_id or self.trade_id,
            account_id=self.account_id,
            symbol=self.symbol,
            side=self.side,
            quantity=as_amount(self.quantity),
            entry_price=as_amount(self.entry_price),
            exit_price=as_amount(self.exit_price),
            opened_at_utc=self.opened_at_utc,
            closed_at_utc=self.closed_at_utc,
            gross_pnl=as_amount(self.gross_pnl),
            commission=as_amount(self.commission),
            risk_amount=(
                as_amount(self.risk_amount) if self.risk_amount is not None else None
            ),
            reward_amount=(
                as_amount(self.reward_amount)
                if self.reward_amount is not None
                else None
            ),
            balance_after=(
                as_amount(self.balance_after)
                if self.balance_after is not None
                else None
            ),
            signal_id=self.signal_id,
            extra_metadata=self.extra_metadata or {},
        )

    def to_account_trade_record(self):
        """Persisted paper trades feed analytics through the Sprint 046 contract."""

        return self.to_contract().to_account_trade_record()

    def to_dict(self) -> dict[str, Any]:
        payload = self.to_contract().to_dict()
        payload["exit_reason"] = (
            self.exit_reason.value if self.exit_reason else None
        )

        return payload

    def __repr__(self) -> str:
        return f"PaperTradeRecord(trade_id={self.trade_id!r})"


class PaperAccountSnapshotRecord(AqosBase):
    """A point-in-time paper balance and exposure snapshot."""

    __tablename__ = "paper_account_snapshots"
    __table_args__ = AQOS_TABLE_ARGS

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    starting_balance: Mapped[float] = mapped_column(
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
    margin_used: Mapped[float] = mapped_column(
        Numeric(20, MONEY_PRECISION),
        nullable=False,
        default=0,
    )
    open_position_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    open_order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_trade_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    captured_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("currency", "USD")
        kwargs.setdefault("margin_used", 0)
        kwargs.setdefault("open_position_count", 0)
        kwargs.setdefault("open_order_count", 0)
        kwargs.setdefault("closed_trade_count", 0)
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    @validates("currency")
    def _validate_currency(self, key: str, value: str) -> str:
        currency = (value or "").strip().upper()

        if len(currency) != 3 or not currency.isalpha():
            raise PaperTradingError(f"Currency must be a 3 letter code: {value}")

        return currency

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "account_id": self.account_id,
            "currency": self.currency,
            "starting_balance": as_amount(self.starting_balance),
            "current_balance": as_amount(self.current_balance),
            "equity": as_amount(self.equity),
            "margin_used": as_amount(self.margin_used),
            "open_position_count": self.open_position_count,
            "open_order_count": self.open_order_count,
            "closed_trade_count": self.closed_trade_count,
            "captured_at_utc": self.captured_at_utc.isoformat(),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return f"PaperAccountSnapshotRecord(snapshot_id={self.snapshot_id!r})"


class PaperExecutionDecisionRecord(AqosBase):
    """
    One recorded paper execution rule decision.

    Refusals are persisted alongside approvals: an execution that never happened
    is exactly the thing a user needs explained, and a structured reason code
    survives where a log line does not.
    """

    __tablename__ = "paper_execution_decisions"
    __table_args__ = AQOS_TABLE_ARGS

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("user_profiles.user_id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("trading_accounts.account_id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("trading_signals.signal_id", ondelete="SET NULL"),
        nullable=True,
    )
    order_id: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("paper_orders.order_id", ondelete="SET NULL"),
        nullable=True,
    )
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    is_allowed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requested_execution_mode: Mapped[ExecutionMode] = mapped_column(
        EnumString(ExecutionMode),
        nullable=False,
    )
    effective_execution_mode: Mapped[ExecutionMode] = mapped_column(
        EnumString(ExecutionMode),
        nullable=False,
    )
    primary_reason_code: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    blocking_reason_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    blocking_sources_json: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    reasons_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    decided_at_utc: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata_json",
        JSON,
        nullable=False,
        default=dict,
    )

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("blocking_reason_count", 0)
        kwargs.setdefault("blocking_sources_json", [])
        kwargs.setdefault("reasons_json", [])
        kwargs.setdefault("extra_metadata", {})

        super().__init__(**kwargs)

    def assert_decision_is_explained(self) -> None:
        """
        A refusal must name a reason, and an approval must not claim one.

        MySQL enforces the same pair of rules, so bypassing Python still fails
        at the database.
        """

        if not self.is_allowed:
            if not self.primary_reason_code or self.blocking_reason_count <= 0:
                raise PaperTradingError(
                    "A refused paper execution decision must carry a blocking "
                    "reason code."
                )

            return

        if self.primary_reason_code or self.blocking_reason_count:
            raise PaperTradingError(
                "An allowed paper execution decision cannot carry blocking "
                "reasons."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "signal_id": self.signal_id,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "is_allowed": bool(self.is_allowed),
            "requested_execution_mode": self.requested_execution_mode.value,
            "effective_execution_mode": self.effective_execution_mode.value,
            "primary_reason_code": self.primary_reason_code,
            "blocking_reason_count": self.blocking_reason_count,
            "blocking_sources": list(self.blocking_sources_json or ()),
            "reasons": list(self.reasons_json or ()),
            "decided_at_utc": self.decided_at_utc.isoformat(),
            "metadata": self.extra_metadata or {},
        }

    def __repr__(self) -> str:
        return f"PaperExecutionDecisionRecord(decision_id={self.decision_id!r})"


__all__ = [
    "AQOS_PAPER_MODELS_VERSION",
    "MONEY_PRECISION",
    "PaperAccountSnapshotRecord",
    "PaperExecutionDecisionRecord",
    "PaperFillRecord",
    "PaperOrderRecord",
    "PaperPositionRecord",
    "PaperTradeRecord",
    "as_amount",
]
