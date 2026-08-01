from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from aqos.persistence.database import AqosDatabase
from aqos.persistence.records import (
    build_record_id,
    decode_json_field,
    encode_json_field,
    normalize_required_text,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema
from aqos.persistence.signals import (
    SignalStatus,
    TradingSignal,
    TradingSignalRepository,
)


AQOS_SIGNAL_REASONS_VERSION = "1.0"


class SignalReasonCategory(str, Enum):
    RISK = "risk"
    ACCOUNT = "account"
    MARKET = "market"
    BROKER = "broker"
    WORKFLOW = "workflow"
    MODEL = "model"
    OTHER = "other"


class SignalReasonCode(str, Enum):
    """Why a signal never turned into a filled trade."""

    SPREAD_TOO_WIDE = "spread_too_wide"
    SLIPPAGE_TOO_HIGH = "slippage_too_high"
    MARKET_CLOSED = "market_closed"
    LATE_SIGNAL = "late_signal"
    RISK_LIMIT_REACHED = "risk_limit_reached"
    DAILY_LOSS_LIMIT = "daily_loss_limit"
    DAILY_TRADE_LIMIT = "daily_trade_limit"
    MAX_OPEN_POSITIONS = "max_open_positions"
    INSUFFICIENT_MARGIN = "insufficient_margin"
    ACCOUNT_RULE = "account_rule"
    FUNDED_RULE = "funded_rule"
    SYMBOL_BLOCKED = "symbol_blocked"
    EXECUTION_MODE_DISABLED = "execution_mode_disabled"
    MANUAL_APPROVAL_TIMEOUT = "manual_approval_timeout"
    MANUALLY_REJECTED = "manually_rejected"
    DUPLICATE_SIGNAL = "duplicate_signal"
    BROKER_DISCONNECTED = "broker_disconnected"
    BROKER_REJECTED = "broker_rejected"
    LOW_CONFIDENCE = "low_confidence"
    MODEL_NOT_PROMOTED = "model_not_promoted"
    OTHER = "other"


SIGNAL_REASON_CATEGORIES: dict[SignalReasonCode, SignalReasonCategory] = {
    SignalReasonCode.SPREAD_TOO_WIDE: SignalReasonCategory.MARKET,
    SignalReasonCode.SLIPPAGE_TOO_HIGH: SignalReasonCategory.MARKET,
    SignalReasonCode.MARKET_CLOSED: SignalReasonCategory.MARKET,
    SignalReasonCode.LATE_SIGNAL: SignalReasonCategory.WORKFLOW,
    SignalReasonCode.RISK_LIMIT_REACHED: SignalReasonCategory.RISK,
    SignalReasonCode.DAILY_LOSS_LIMIT: SignalReasonCategory.RISK,
    SignalReasonCode.DAILY_TRADE_LIMIT: SignalReasonCategory.RISK,
    SignalReasonCode.MAX_OPEN_POSITIONS: SignalReasonCategory.RISK,
    SignalReasonCode.INSUFFICIENT_MARGIN: SignalReasonCategory.ACCOUNT,
    SignalReasonCode.ACCOUNT_RULE: SignalReasonCategory.ACCOUNT,
    SignalReasonCode.FUNDED_RULE: SignalReasonCategory.ACCOUNT,
    SignalReasonCode.SYMBOL_BLOCKED: SignalReasonCategory.ACCOUNT,
    SignalReasonCode.EXECUTION_MODE_DISABLED: SignalReasonCategory.ACCOUNT,
    SignalReasonCode.MANUAL_APPROVAL_TIMEOUT: SignalReasonCategory.WORKFLOW,
    SignalReasonCode.MANUALLY_REJECTED: SignalReasonCategory.WORKFLOW,
    SignalReasonCode.DUPLICATE_SIGNAL: SignalReasonCategory.WORKFLOW,
    SignalReasonCode.BROKER_DISCONNECTED: SignalReasonCategory.BROKER,
    SignalReasonCode.BROKER_REJECTED: SignalReasonCategory.BROKER,
    SignalReasonCode.LOW_CONFIDENCE: SignalReasonCategory.MODEL,
    SignalReasonCode.MODEL_NOT_PROMOTED: SignalReasonCategory.MODEL,
    SignalReasonCode.OTHER: SignalReasonCategory.OTHER,
}

#: Outcomes that a reason record can describe.
REASON_OUTCOME_STATUSES = (
    SignalStatus.REJECTED,
    SignalStatus.MISSED,
    SignalStatus.FAILED,
    SignalStatus.EXPIRED,
    SignalStatus.CANCELLED,
)

DEFAULT_REASON_MESSAGES: dict[SignalReasonCode, str] = {
    SignalReasonCode.SPREAD_TOO_WIDE: "Spread was wider than the allowed maximum.",
    SignalReasonCode.SLIPPAGE_TOO_HIGH: "Expected slippage exceeded the limit.",
    SignalReasonCode.MARKET_CLOSED: "Market was closed for this symbol.",
    SignalReasonCode.LATE_SIGNAL: "Signal arrived too late to be actionable.",
    SignalReasonCode.RISK_LIMIT_REACHED: "Risk limit reached for this account.",
    SignalReasonCode.DAILY_LOSS_LIMIT: "Daily loss limit reached.",
    SignalReasonCode.DAILY_TRADE_LIMIT: "Daily trade limit reached.",
    SignalReasonCode.MAX_OPEN_POSITIONS: "Maximum open positions reached.",
    SignalReasonCode.INSUFFICIENT_MARGIN: "Account had insufficient margin.",
    SignalReasonCode.ACCOUNT_RULE: "Blocked by an account rule.",
    SignalReasonCode.FUNDED_RULE: "Blocked by a funded account rule.",
    SignalReasonCode.SYMBOL_BLOCKED: "Symbol is blocked for this user.",
    SignalReasonCode.EXECUTION_MODE_DISABLED: "Execution mode does not allow orders.",
    SignalReasonCode.MANUAL_APPROVAL_TIMEOUT: "Manual approval was not given in time.",
    SignalReasonCode.MANUALLY_REJECTED: "Rejected manually.",
    SignalReasonCode.DUPLICATE_SIGNAL: "Duplicate of an existing signal.",
    SignalReasonCode.BROKER_DISCONNECTED: "Broker connection was unavailable.",
    SignalReasonCode.BROKER_REJECTED: "Broker rejected the order.",
    SignalReasonCode.LOW_CONFIDENCE: "Model confidence was below the threshold.",
    SignalReasonCode.MODEL_NOT_PROMOTED: "Model is not promoted for this stage.",
    SignalReasonCode.OTHER: "Signal was not executed.",
}


def resolve_reason_category(reason_code: SignalReasonCode) -> SignalReasonCategory:
    return SIGNAL_REASON_CATEGORIES[reason_code]


def default_reason_message(reason_code: SignalReasonCode) -> str:
    return DEFAULT_REASON_MESSAGES[reason_code]


def validate_reason_outcome_status(status: SignalStatus) -> None:
    if status in REASON_OUTCOME_STATUSES:
        return

    raise ValueError(
        f"Signal outcome reasons cannot be recorded for status: {status.value}"
    )


@dataclass(frozen=True)
class SignalOutcome:
    """
    Why one signal did not reach the market for one account.

    The same signal can produce different outcomes on different accounts, so
    ``account_id`` is part of the record rather than the signal.
    """

    outcome_id: str
    signal_id: str
    status: SignalStatus
    reason_code: SignalReasonCode
    category: SignalReasonCategory
    occurred_at_utc: str
    account_id: str | None = None
    detail: str | None = None
    actor: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.outcome_id.strip():
            raise ValueError("outcome_id cannot be empty.")

        if not self.signal_id.strip():
            raise ValueError("signal_id cannot be empty.")

        if not self.occurred_at_utc.strip():
            raise ValueError("occurred_at_utc cannot be empty.")

        validate_reason_outcome_status(self.status)

        if self.category != resolve_reason_category(self.reason_code):
            raise ValueError(
                "category does not match the reason code category."
            )

    @property
    def message(self) -> str:
        return self.detail or default_reason_message(self.reason_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "signal_id": self.signal_id,
            "account_id": self.account_id,
            "status": self.status.value,
            "reason_code": self.reason_code.value,
            "category": self.category.value,
            "occurred_at_utc": self.occurred_at_utc,
            "detail": self.detail,
            "message": self.message,
            "actor": self.actor,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SignalReasonCount:
    reason_code: SignalReasonCode
    category: SignalReasonCategory
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code.value,
            "category": self.category.value,
            "count": self.count,
        }


@dataclass(frozen=True)
class SignalReasonSummary:
    total: int
    by_reason: tuple[SignalReasonCount, ...] = ()
    by_status: dict[str, int] = dataclass_field(default_factory=dict)

    @property
    def by_category(self) -> dict[str, int]:
        totals: dict[str, int] = {}

        for entry in self.by_reason:
            totals[entry.category.value] = (
                totals.get(entry.category.value, 0) + entry.count
            )

        return dict(sorted(totals.items()))

    @property
    def top_reason(self) -> SignalReasonCount | None:
        return self.by_reason[0] if self.by_reason else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_reason": [entry.to_dict() for entry in self.by_reason],
            "by_category": self.by_category,
            "by_status": self.by_status,
            "top_reason": (
                self.top_reason.to_dict() if self.top_reason is not None else None
            ),
        }


def build_signal_outcome_from_row(row: dict[str, Any]) -> SignalOutcome:
    return SignalOutcome(
        outcome_id=str(row["outcome_id"]),
        signal_id=str(row["signal_id"]),
        status=SignalStatus(str(row["status"])),
        reason_code=SignalReasonCode(str(row["reason_code"])),
        category=SignalReasonCategory(str(row["category"])),
        occurred_at_utc=str(row["occurred_at_utc"]),
        account_id=row.get("account_id"),
        detail=row.get("detail"),
        actor=row.get("actor"),
        metadata=decode_json_field(row.get("metadata")),
    )


class SignalOutcomeRepository:
    """Reason records for signals that never became trades."""

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

    def record_outcome(
        self,
        signal_id: str,
        status: SignalStatus,
        reason_code: SignalReasonCode,
        account_id: str | None = None,
        detail: str | None = None,
        actor: str | None = None,
        metadata: dict[str, Any] | None = None,
        outcome_id: str | None = None,
        occurred_at_utc: str | None = None,
    ) -> SignalOutcome:
        outcome = SignalOutcome(
            outcome_id=outcome_id or build_record_id("signaloutcome"),
            signal_id=normalize_required_text(signal_id, "signal_id"),
            status=status,
            reason_code=reason_code,
            category=resolve_reason_category(reason_code),
            occurred_at_utc=occurred_at_utc or record_utc_now(),
            account_id=account_id,
            detail=detail,
            actor=actor,
            metadata=metadata or {},
        )

        self.database.execute(
            """
            INSERT INTO signal_outcomes (
                outcome_id, signal_id, account_id, status, reason_code,
                category, occurred_at_utc, detail, actor, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                outcome.outcome_id,
                outcome.signal_id,
                outcome.account_id,
                outcome.status.value,
                outcome.reason_code.value,
                outcome.category.value,
                outcome.occurred_at_utc,
                outcome.detail,
                outcome.actor,
                encode_json_field(outcome.metadata),
            ),
        )

        return outcome

    def get_outcome(self, outcome_id: str) -> SignalOutcome | None:
        row = self.database.query_one(
            "SELECT * FROM signal_outcomes WHERE outcome_id = ?;",
            (outcome_id,),
        )

        return build_signal_outcome_from_row(row) if row is not None else None

    def list_outcomes(
        self,
        signal_id: str | None = None,
        account_id: str | None = None,
        status: SignalStatus | None = None,
        reason_code: SignalReasonCode | None = None,
        category: SignalReasonCategory | None = None,
        occurred_since_utc: str | None = None,
    ) -> tuple[SignalOutcome, ...]:
        clauses: list[str] = []
        parameters: list[Any] = []

        if signal_id is not None:
            clauses.append("signal_id = ?")
            parameters.append(signal_id)

        if account_id is not None:
            clauses.append("account_id = ?")
            parameters.append(account_id)

        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)

        if reason_code is not None:
            clauses.append("reason_code = ?")
            parameters.append(reason_code.value)

        if category is not None:
            clauses.append("category = ?")
            parameters.append(category.value)

        if occurred_since_utc is not None:
            clauses.append("occurred_at_utc >= ?")
            parameters.append(occurred_since_utc)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self.database.query_all(
            f"SELECT * FROM signal_outcomes{where} "
            "ORDER BY occurred_at_utc, outcome_id;",
            tuple(parameters),
        )

        return tuple(build_signal_outcome_from_row(row) for row in rows)

    def summarize_reasons(
        self,
        account_id: str | None = None,
        status: SignalStatus | None = None,
        occurred_since_utc: str | None = None,
    ) -> SignalReasonSummary:
        outcomes = self.list_outcomes(
            account_id=account_id,
            status=status,
            occurred_since_utc=occurred_since_utc,
        )

        reason_totals: dict[SignalReasonCode, int] = {}
        status_totals: dict[str, int] = {}

        for outcome in outcomes:
            reason_totals[outcome.reason_code] = (
                reason_totals.get(outcome.reason_code, 0) + 1
            )
            status_totals[outcome.status.value] = (
                status_totals.get(outcome.status.value, 0) + 1
            )

        ordered = sorted(
            reason_totals.items(),
            key=lambda item: (-item[1], item[0].value),
        )

        return SignalReasonSummary(
            total=len(outcomes),
            by_reason=tuple(
                SignalReasonCount(
                    reason_code=reason_code,
                    category=resolve_reason_category(reason_code),
                    count=count,
                )
                for reason_code, count in ordered
            ),
            by_status=dict(sorted(status_totals.items())),
        )

    def delete_outcomes_for_signal(self, signal_id: str) -> int:
        cursor = self.database.execute(
            "DELETE FROM signal_outcomes WHERE signal_id = ?;",
            (signal_id,),
        )

        return int(cursor.rowcount)


def reject_signal_with_reason(
    signals: TradingSignalRepository,
    outcomes: SignalOutcomeRepository,
    signal_id: str,
    reason_code: SignalReasonCode,
    detail: str | None = None,
    account_id: str | None = None,
    actor: str | None = None,
    occurred_at_utc: str | None = None,
) -> tuple[TradingSignal, SignalOutcome]:
    """Reject a signal and record why, keeping both stores in step."""

    message = detail or default_reason_message(reason_code)

    signal = signals.reject_signal(
        signal_id=signal_id,
        reason=message,
        actor=actor,
        occurred_at_utc=occurred_at_utc,
    )
    outcome = outcomes.record_outcome(
        signal_id=signal_id,
        status=SignalStatus.REJECTED,
        reason_code=reason_code,
        account_id=account_id or signal.account_id,
        detail=detail,
        actor=actor,
        occurred_at_utc=occurred_at_utc or signal.updated_at_utc,
    )

    return signal, outcome


def miss_signal_with_reason(
    signals: TradingSignalRepository,
    outcomes: SignalOutcomeRepository,
    signal_id: str,
    reason_code: SignalReasonCode,
    detail: str | None = None,
    account_id: str | None = None,
    actor: str | None = None,
    occurred_at_utc: str | None = None,
) -> tuple[TradingSignal, SignalOutcome]:
    message = detail or default_reason_message(reason_code)

    signal = signals.mark_missed(
        signal_id=signal_id,
        reason=message,
        actor=actor,
        occurred_at_utc=occurred_at_utc,
    )
    outcome = outcomes.record_outcome(
        signal_id=signal_id,
        status=SignalStatus.MISSED,
        reason_code=reason_code,
        account_id=account_id or signal.account_id,
        detail=detail,
        actor=actor,
        occurred_at_utc=occurred_at_utc or signal.updated_at_utc,
    )

    return signal, outcome


def fail_signal_with_reason(
    signals: TradingSignalRepository,
    outcomes: SignalOutcomeRepository,
    signal_id: str,
    reason_code: SignalReasonCode,
    detail: str | None = None,
    account_id: str | None = None,
    actor: str | None = None,
    occurred_at_utc: str | None = None,
) -> tuple[TradingSignal, SignalOutcome]:
    message = detail or default_reason_message(reason_code)

    signal = signals.mark_failed(
        signal_id=signal_id,
        reason=message,
        actor=actor,
        occurred_at_utc=occurred_at_utc,
    )
    outcome = outcomes.record_outcome(
        signal_id=signal_id,
        status=SignalStatus.FAILED,
        reason_code=reason_code,
        account_id=account_id or signal.account_id,
        detail=detail,
        actor=actor,
        occurred_at_utc=occurred_at_utc or signal.updated_at_utc,
    )

    return signal, outcome


__all__ = [
    "AQOS_SIGNAL_REASONS_VERSION",
    "DEFAULT_REASON_MESSAGES",
    "REASON_OUTCOME_STATUSES",
    "SIGNAL_REASON_CATEGORIES",
    "SignalOutcome",
    "SignalOutcomeRepository",
    "SignalReasonCategory",
    "SignalReasonCode",
    "SignalReasonCount",
    "SignalReasonSummary",
    "build_signal_outcome_from_row",
    "default_reason_message",
    "fail_signal_with_reason",
    "miss_signal_with_reason",
    "reject_signal_with_reason",
    "resolve_reason_category",
    "validate_reason_outcome_status",
]
