from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any

from aqos.account_analytics.metrics import (
    ProfitFactorState,
    finite_profit_factor,
    resolve_profit_factor_state,
)
from aqos.paper_trading.contracts import PaperTradingError, require_text


AQOS_PAPER_SESSIONS_VERSION = "1.0"


class PaperSessionType(str, Enum):
    """What kind of run the session groups."""

    MANUAL_PAPER_SESSION = "manual_paper_session"
    BACKTEST_TO_PAPER_SESSION = "backtest_to_paper_session"
    MODEL_FORWARD_TEST = "model_forward_test"
    STRATEGY_FORWARD_TEST = "strategy_forward_test"
    SIGNAL_REPLAY_SESSION = "signal_replay_session"


#: Session types that are driven by a model and must name one.
#:
#: A model forward test with no model recorded could never be reproduced or
#: attributed, so the identity is required rather than optional.
MODEL_DRIVEN_SESSION_TYPES = (PaperSessionType.MODEL_FORWARD_TEST,)

#: Session types that are driven by a strategy and must name one.
STRATEGY_DRIVEN_SESSION_TYPES = (PaperSessionType.STRATEGY_FORWARD_TEST,)


#: The canonical profit factor state lives with ``calculate_profit_factor`` in
#: Sprint 046's metrics module. Paper trading re-exports it under its own name
#: rather than defining a second enum that could drift from it.
PaperProfitFactorState = ProfitFactorState


class PaperSessionStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


#: Statuses a session can never leave.
TERMINAL_PAPER_SESSION_STATUSES = (
    PaperSessionStatus.COMPLETED,
    PaperSessionStatus.FAILED,
    PaperSessionStatus.CANCELLED,
)

#: Statuses in which a session may accept new paper executions.
EXECUTABLE_PAPER_SESSION_STATUSES = (PaperSessionStatus.RUNNING,)

PAPER_SESSION_TRANSITIONS: dict[
    PaperSessionStatus,
    tuple[PaperSessionStatus, ...],
] = {
    PaperSessionStatus.CREATED: (
        PaperSessionStatus.RUNNING,
        PaperSessionStatus.CANCELLED,
        PaperSessionStatus.FAILED,
    ),
    PaperSessionStatus.RUNNING: (
        PaperSessionStatus.PAUSED,
        PaperSessionStatus.COMPLETED,
        PaperSessionStatus.FAILED,
        PaperSessionStatus.CANCELLED,
    ),
    PaperSessionStatus.PAUSED: (
        PaperSessionStatus.RUNNING,
        PaperSessionStatus.CANCELLED,
        PaperSessionStatus.FAILED,
    ),
    PaperSessionStatus.COMPLETED: (),
    PaperSessionStatus.FAILED: (),
    PaperSessionStatus.CANCELLED: (),
}

#: Statuses a session may be created in.
CREATABLE_PAPER_SESSION_STATUSES = (PaperSessionStatus.CREATED,)


class InvalidPaperSessionTransitionError(PaperTradingError):
    """Raised when a session is asked to make a transition that is not allowed."""


def is_terminal_session_status(status: PaperSessionStatus) -> bool:
    return status in TERMINAL_PAPER_SESSION_STATUSES


def can_transition_session(
    from_status: PaperSessionStatus,
    to_status: PaperSessionStatus,
) -> bool:
    return to_status in PAPER_SESSION_TRANSITIONS.get(from_status, ())


def validate_session_transition(
    from_status: PaperSessionStatus,
    to_status: PaperSessionStatus,
) -> None:
    if can_transition_session(from_status, to_status):
        return

    raise InvalidPaperSessionTransitionError(
        f"Paper session cannot move from {from_status.value} to "
        f"{to_status.value}."
    )


def normalize_session_name(value: str) -> str:
    name = " ".join((value or "").split())

    if not name:
        raise PaperTradingError("session_name cannot be empty.")

    if len(name) > 191:
        raise PaperTradingError("session_name cannot exceed 191 characters.")

    return name


def validate_session_identity(
    session_type: PaperSessionType,
    model_id: str | None,
    strategy_name: str | None,
) -> None:
    """
    A run must name whatever drove it.

    An unattributed forward test cannot be reproduced or compared later, so the
    identity is required at creation rather than patched in afterwards.
    """

    if session_type in MODEL_DRIVEN_SESSION_TYPES and not (model_id or "").strip():
        raise PaperTradingError(
            f"A {session_type.value} session must name the model it tests."
        )

    if session_type in STRATEGY_DRIVEN_SESSION_TYPES and not (
        strategy_name or ""
    ).strip():
        raise PaperTradingError(
            f"A {session_type.value} session must name the strategy it tests."
        )


@dataclass(frozen=True)
class PaperSessionResult:
    """
    A measured result for one paper session.

    Every field that could be unknown is optional and stays ``None`` when the
    session produced nothing to measure. A session with no closed trades has an
    unknown win rate, not a zero one.
    """

    session_id: str
    account_id: str
    total_orders: int = 0
    total_fills: int = 0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float | None = None
    net_pnl: float | None = None
    gross_profit: float | None = None
    gross_loss: float | None = None
    profit_factor: float | None = None
    max_drawdown: float | None = None
    ending_balance: float | None = None
    symbols_traded: tuple[str, ...] = ()
    decisions_allowed: int = 0
    decisions_rejected: int = 0
    top_rejection_reasons: tuple[tuple[str, int], ...] = ()
    calculated_at_utc: datetime | None = None
    extra_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.session_id, "session_id")

        for field_name in (
            "total_orders",
            "total_fills",
            "total_trades",
            "winning_trades",
            "losing_trades",
            "decisions_allowed",
            "decisions_rejected",
        ):
            if getattr(self, field_name) < 0:
                raise PaperTradingError(f"{field_name} cannot be negative.")

        if self.winning_trades + self.losing_trades > self.total_trades:
            raise PaperTradingError(
                "winning_trades plus losing_trades cannot exceed total_trades."
            )

        if self.total_trades == 0 and self.win_rate is not None:
            raise PaperTradingError(
                "win_rate must stay unset when no trade closed; an unknown "
                "rate is not zero."
            )

    @property
    def has_trades(self) -> bool:
        return self.total_trades > 0

    @property
    def profit_factor_state(self) -> PaperProfitFactorState:
        """
        Derived rather than stored, so it can never disagree with the value.

        ``infinite_no_losses`` means the session won and never lost; it is a
        real result, not a missing one.
        """

        return resolve_profit_factor_state(self.profit_factor)

    @property
    def has_infinite_profit_factor(self) -> bool:
        return self.profit_factor_state == (
            PaperProfitFactorState.INFINITE_NO_LOSSES
        )

    @property
    def persisted_profit_factor(self) -> float | None:
        """The value a DECIMAL column may hold; infinity is carried by state."""

        return finite_profit_factor(self.profit_factor)

    @property
    def total_decisions(self) -> int:
        return self.decisions_allowed + self.decisions_rejected

    @property
    def rejection_rate(self) -> float | None:
        """None when nothing was ever decided, rather than a misleading zero."""

        total = self.total_decisions

        if total <= 0:
            return None

        return self.decisions_rejected / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "account_id": self.account_id,
            "has_trades": self.has_trades,
            "total_orders": self.total_orders,
            "total_fills": self.total_fills,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "net_pnl": self.net_pnl,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            # JSON cannot carry infinity, so the state is what preserves the
            # meaning for a wins-only session.
            "profit_factor": self.persisted_profit_factor,
            "profit_factor_state": self.profit_factor_state.value,
            "has_infinite_profit_factor": self.has_infinite_profit_factor,
            "max_drawdown": self.max_drawdown,
            "ending_balance": self.ending_balance,
            "symbols_traded": list(self.symbols_traded),
            "decisions_allowed": self.decisions_allowed,
            "decisions_rejected": self.decisions_rejected,
            "total_decisions": self.total_decisions,
            "rejection_rate": self.rejection_rate,
            "top_rejection_reasons": [
                {"reason_code": code, "total": total}
                for code, total in self.top_rejection_reasons
            ],
            "calculated_at_utc": (
                self.calculated_at_utc.isoformat()
                if self.calculated_at_utc is not None
                else None
            ),
            "metadata": self.extra_metadata,
        }


__all__ = [
    "AQOS_PAPER_SESSIONS_VERSION",
    "CREATABLE_PAPER_SESSION_STATUSES",
    "EXECUTABLE_PAPER_SESSION_STATUSES",
    "InvalidPaperSessionTransitionError",
    "MODEL_DRIVEN_SESSION_TYPES",
    "PAPER_SESSION_TRANSITIONS",
    "PaperProfitFactorState",
    "PaperSessionResult",
    "PaperSessionStatus",
    "PaperSessionType",
    "STRATEGY_DRIVEN_SESSION_TYPES",
    "TERMINAL_PAPER_SESSION_STATUSES",
    "can_transition_session",
    "is_terminal_session_status",
    "finite_profit_factor",
    "normalize_session_name",
    "resolve_profit_factor_state",
    "validate_session_identity",
    "validate_session_transition",
]
