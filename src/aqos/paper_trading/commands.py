"""
The only way in to paper trading from outside the package.

Everything that can actually cause a simulated fill — the simulator, the
in-memory broker, the execution service, the eligibility gate — stays private
to :mod:`aqos.paper_trading`. Callers outside the package go through this
module, which speaks in plain values and returns persisted records.

The narrowness is the point. A transport layer that could construct a
``PaperExecutionService`` for itself could also choose which safety rails to
pass; here it cannot, because the rails are not parameters. Every command runs
the same gate, books against the same session and records the same decision.

The caller still owns the SQLAlchemy session and the transaction: this module
stages work and never commits, so a refused command leaves nothing behind.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from aqos.accounts.models import AccountType, TradingAccount
from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.types import database_utc_now
from aqos.execution_policy.modes import ExecutionMode
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderStatus,
    PaperOrderType,
    PaperTradingError,
)
from aqos.paper_trading.execution_service import (
    PaperCloseOutcome,
    PaperExecutionService,
)
from aqos.paper_trading.models import (
    PaperExecutionDecisionRecord,
    PaperFillRecord,
    PaperOrderRecord,
    PaperPositionRecord,
    PaperSessionRecord,
    PaperTradeRecord,
)
from aqos.paper_trading.repositories import (
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.session_service import (
    PaperSessionRepository,
    PaperSessionService,
)
from aqos.paper_trading.sessions import (
    PaperSessionStatus,
    PaperSessionType,
)
from aqos.paper_trading.simulator import PaperExitReason, PaperMarketBar


AQOS_PAPER_COMMANDS_VERSION = "1.0"

#: The mode a command submitted by a person asks for.
#:
#: Never ``AUTO_TRADE``: an order arriving through a command is one somebody
#: chose to send, and claiming otherwise would let a manual submission satisfy
#: rules written for autonomous trading. The gate still narrows this to the
#: strictest mode the account and its settings allow.
COMMANDED_EXECUTION_MODE = ExecutionMode.MANUAL_APPROVAL


class PaperCommandError(PaperTradingError):
    """A command that cannot be carried out as asked."""


@dataclass(frozen=True)
class PaperMarketQuote:
    """
    The simulated market state one order prices against.

    Paper trading has no market feed of its own: a run is driven by whatever
    bars the caller is replaying. The values are validated as a real bar — the
    high must cover open and close, prices must be positive — so an impossible
    market cannot be used to manufacture a fill.
    """

    symbol: str
    timestamp_utc: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class PaperOrderCommand:
    """One request to place a paper order inside a running session."""

    account_id: str
    session_id: str
    symbol: str
    action: PaperAction
    order_type: PaperOrderType
    quantity: float
    market: PaperMarketQuote
    submitted_at_utc: datetime | None = None
    signal_id: str | None = None
    requested_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class PaperSessionCommand:
    """One request to open a paper session on an account."""

    account_id: str
    session_name: str
    session_type: PaperSessionType
    strategy_name: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    symbol: str | None = None
    timeframe: str | None = None
    started_at_utc: datetime | None = None


@dataclass(frozen=True)
class PaperOrderOutcome:
    """
    What one submitted order produced, as persisted rows.

    The decision is always present: a refused attempt is as auditable as an
    accepted one, and ``accepted`` says which happened. Everything else is
    ``None`` or empty when the gate refused, because a refusal must not leave
    an order, a fill, a position or a trade behind.
    """

    accepted: bool
    decision: PaperExecutionDecisionRecord
    order: PaperOrderRecord | None = None
    fills: tuple[PaperFillRecord, ...] = ()
    position: PaperPositionRecord | None = None
    trade: PaperTradeRecord | None = None
    rejection_reason: str | None = None
    rejection_message: str | None = None
    extra: dict[str, Any] = dataclass_field(default_factory=dict)


#: Session commands, as ``name -> target status``.
#:
#: An allow list rather than a free choice of status: a caller may ask for the
#: transitions written here and no others, whatever the lifecycle table would
#: otherwise permit.
PAPER_SESSION_COMMANDS: dict[str, PaperSessionStatus] = {
    "start": PaperSessionStatus.RUNNING,
    "pause": PaperSessionStatus.PAUSED,
    "resume": PaperSessionStatus.RUNNING,
    "complete": PaperSessionStatus.COMPLETED,
    "cancel": PaperSessionStatus.CANCELLED,
    "fail": PaperSessionStatus.FAILED,
}

#: Session commands that must say why, and what to say when they do not.
#:
#: Mirrors the session service, which refuses a blank reason for both. A run
#: that stopped badly has to record what went wrong.
REASON_REQUIRED_SESSION_COMMANDS: dict[str, str] = {
    "cancel": "A cancelled session must record a reason.",
    "fail": "A failed session must record a reason.",
}


class PaperCommandService:
    """
    The approved command surface for paper trading.

    Holds a session and nothing else. Each method resolves the account, proves
    it is a paper account, delegates to the existing services and returns
    persisted records.
    """

    def __init__(self, session: Session) -> None:
        if session is None:
            raise ValueError("A SQLAlchemy session is required.")

        self.session = session
        self.accounts = TradingAccountRepository(session)
        self.sessions = PaperSessionService(session)
        self.session_records = PaperSessionRepository(session)
        self.decisions = PaperExecutionDecisionRepository(session)
        self.orders = PaperOrderRepository(session)
        self.fills = PaperFillRepository(session)
        self.positions = PaperPositionRepository(session)
        self.trades = PaperTradeRepository(session)

    # -- accounts ---------------------------------------------------------

    def require_paper_account(self, account_id: str) -> TradingAccount:
        """
        The account, provided it is one simulated money may move in.

        Checked here as well as inside the gate: a live or funded account must
        never get as far as having a paper session attached to it, because the
        session is what later activity is booked against.
        """

        account = self.accounts.get(account_id)

        if account is None:
            raise PaperCommandError(f"Account {account_id} was not found.")

        if account.account_type != AccountType.PAPER:
            raise PaperCommandError(
                "Paper trading only runs on paper accounts, not "
                f"{account.account_type.value}."
            )

        return account

    # -- sessions ---------------------------------------------------------

    def open_session(self, command: PaperSessionCommand) -> PaperSessionRecord:
        """
        Create a session in ``created``, ready to be started.

        Creation and starting are kept apart so a run can be set up and
        reviewed before it begins accepting activity.
        """

        account = self.require_paper_account(command.account_id)

        return self.sessions.create_session(
            account=account,
            session_name=command.session_name,
            session_type=command.session_type,
            started_at_utc=command.started_at_utc,
            strategy_name=command.strategy_name,
            model_id=command.model_id,
            model_version=command.model_version,
            symbol=command.symbol,
            timeframe=command.timeframe,
        )

    def command_session(
        self,
        session_id: str,
        command: str,
        reason: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> PaperSessionRecord:
        """
        Move a session, through the Sprint 052 lifecycle rules.

        The transition table is not consulted here: the session service raises
        for anything it does not allow, so a refused command is refused by the
        one place that owns the rule.
        """

        if command not in PAPER_SESSION_COMMANDS:
            raise PaperCommandError(f"Unknown paper session command: {command}")

        if command in REASON_REQUIRED_SESSION_COMMANDS and not (
            reason or ""
        ).strip():
            raise PaperCommandError(REASON_REQUIRED_SESSION_COMMANDS[command])

        record = self.session_records.require_session(session_id)

        # Every branch below goes through the lifecycle rules, so an already
        # terminal session is refused by the transition table rather than by a
        # special case here.
        if command == "start":
            return self.session_records.transition_session(
                session_id=record.session_id,
                to_status=PaperSessionStatus.RUNNING,
                occurred_at_utc=occurred_at_utc,
            )

        if command == "pause":
            return self.sessions.pause_session(
                session_id=record.session_id,
                reason=reason,
                occurred_at_utc=occurred_at_utc,
            )

        if command == "resume":
            return self.sessions.resume_session(
                session_id=record.session_id,
                occurred_at_utc=occurred_at_utc,
            )

        if command == "complete":
            return self.sessions.complete_session(
                session_id=record.session_id,
                reason=reason,
                occurred_at_utc=occurred_at_utc,
            )

        if command == "cancel":
            return self.sessions.cancel_session(
                session_id=record.session_id,
                reason=reason or "",
                occurred_at_utc=occurred_at_utc,
            )

        return self.sessions.fail_session(
            session_id=record.session_id,
            reason=reason or "",
            occurred_at_utc=occurred_at_utc,
        )

    # -- orders -----------------------------------------------------------

    def submit_order(self, command: PaperOrderCommand) -> PaperOrderOutcome:
        """
        Place one paper order inside a running session.

        The session must be running and must belong to the same paper account
        the order names, so activity cannot be booked against a finished run or
        smuggled onto a different account. The eligibility gate then decides,
        and its decision is recorded whichever way it goes.
        """

        account = self.require_paper_account(command.account_id)
        record = self.sessions.require_running_session(command.session_id)

        if record.account_id != account.account_id:
            raise PaperCommandError(
                "The paper session belongs to a different account."
            )

        submitted_at_utc = command.submitted_at_utc or database_utc_now()

        request = PaperExecutionRequest(
            user_id=account.user_id,
            account_id=account.account_id,
            symbol=command.symbol,
            action=command.action,
            quantity=command.quantity,
            order_type=command.order_type,
            submitted_at_utc=submitted_at_utc,
            signal_id=command.signal_id,
            requested_price=command.requested_price,
            stop_loss=command.stop_loss,
            take_profit=command.take_profit,
        )
        bar = PaperMarketBar(
            symbol=command.market.symbol,
            timestamp_utc=command.market.timestamp_utc,
            open=command.market.open,
            high=command.market.high,
            low=command.market.low,
            close=command.market.close,
            volume=command.market.volume,
        )

        known_decision_ids = self._decision_ids(record.session_id)

        result = PaperExecutionService(
            self.session,
            session_id=record.session_id,
        ).execute(
            request=request,
            account=account,
            bar=bar,
            requested_mode=COMMANDED_EXECUTION_MODE,
        )

        return self._collect_outcome(result, record.session_id, known_decision_ids)

    def cancel_order(
        self,
        session_id: str,
        order_id: str,
        at_utc: datetime | None = None,
    ) -> PaperOrderRecord:
        """
        Withdraw an order that has not finished.

        The order transition table decides what "not finished" means, so a
        filled or already-cancelled order is refused there rather than by a
        rule invented here.
        """

        record = self.session_records.require_session(session_id)
        order = self.orders.get(order_id)

        if order is None or order.session_id != record.session_id:
            raise PaperCommandError(
                f"Order {order_id} was not found in this paper session."
            )

        return self.orders.transition_order(
            order_id=order.order_id,
            to_status=PaperOrderStatus.CANCELLED,
            updated_at_utc=at_utc,
        )

    def close_position(
        self,
        session_id: str,
        position_id: str,
        exit_price: float,
        closed_at_utc: datetime | None = None,
    ) -> PaperCloseOutcome:
        """
        Flatten one open position at a stated price.

        The price comes from the caller for the same reason an order's bar
        does: paper trading replays a market rather than subscribing to one.
        An already-closed position is refused by the execution service.
        """

        record = self.session_records.require_session(session_id)
        account = self.require_paper_account(record.account_id)
        position = self.positions.get(position_id)

        if position is None or position.session_id != record.session_id:
            raise PaperCommandError(
                f"Position {position_id} was not found in this paper session."
            )

        return PaperExecutionService(
            self.session,
            session_id=record.session_id,
        ).close_position(
            position_record=position,
            account=account,
            exit_price=exit_price,
            exit_reason=PaperExitReason.MANUAL_CLOSE,
            closed_at_utc=closed_at_utc or database_utc_now(),
        )

    def _decision_ids(self, session_id: str) -> frozenset[str]:
        return frozenset(
            decision.decision_id
            for decision in self.decisions.list_decisions(session_id=session_id)
        )

    def _collect_outcome(
        self,
        result: Any,
        session_id: str,
        known_decision_ids: frozenset[str],
    ) -> PaperOrderOutcome:
        """
        Gather the persisted rows one attempt produced.

        The decision is found by elimination rather than by taking the most
        recent row: two attempts can share a timestamp, so "latest" is not
        reliably the one this command just made. Exactly one new decision is
        expected, and anything else is a defect worth failing on rather than
        reporting a half-truth.
        """

        recorded = [
            decision
            for decision in self.decisions.list_decisions(session_id=session_id)
            if decision.decision_id not in known_decision_ids
        ]

        if len(recorded) != 1:
            raise PaperCommandError(
                "A paper execution attempt must record exactly one decision; "
                f"this one recorded {len(recorded)}."
            )

        order = (
            self.orders.get(result.order.order_id)
            if result.order is not None
            else None
        )
        position = (
            self.positions.get(result.position.position_id)
            if result.position is not None
            else None
        )
        trade = (
            self.trades.get(result.trade.trade_id)
            if result.trade is not None
            else None
        )
        fills = (
            tuple(self.fills.list_fills(order_id=order.order_id))
            if order is not None
            else ()
        )

        return PaperOrderOutcome(
            accepted=result.accepted,
            decision=recorded[0],
            order=order,
            fills=fills,
            position=position,
            trade=trade,
            rejection_reason=(
                result.rejection_reason.value
                if result.rejection_reason is not None
                else None
            ),
            rejection_message=result.rejection_message,
        )


__all__ = [
    "AQOS_PAPER_COMMANDS_VERSION",
    "COMMANDED_EXECUTION_MODE",
    "PAPER_SESSION_COMMANDS",
    "REASON_REQUIRED_SESSION_COMMANDS",
    "PaperCommandError",
    "PaperCommandService",
    "PaperMarketQuote",
    "PaperOrderCommand",
    "PaperOrderOutcome",
    "PaperSessionCommand",
]
