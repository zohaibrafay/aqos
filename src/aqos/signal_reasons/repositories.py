from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from aqos.database.repository import AqosRepository
from aqos.database.types import database_utc_now
from aqos.signals.models import SignalStatus, TradingSignal
from aqos.signals.repositories import TradingSignalRepository
from aqos.signal_reasons.models import SignalReason, build_reason_message
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonSeverity,
    resolve_minimum_severity,
    resolve_reason_category,
    severity_rank,
)
from aqos.users.repositories import build_entity_id


AQOS_SIGNAL_REASON_REPOSITORIES_VERSION = "1.0"


@dataclass(frozen=True)
class ReasonCount:
    reason_code: SignalReasonCode
    reason_category: SignalReasonCategory
    severity: SignalReasonSeverity
    count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code.value,
            "reason_category": self.reason_category.value,
            "severity": self.severity.value,
            "count": self.count,
        }


@dataclass(frozen=True)
class ReasonSummary:
    total: int
    by_reason: tuple[ReasonCount, ...] = ()
    by_status: dict[str, int] = dataclass_field(default_factory=dict)

    @property
    def by_category(self) -> dict[str, int]:
        totals: dict[str, int] = {}

        for entry in self.by_reason:
            key = entry.reason_category.value
            totals[key] = totals.get(key, 0) + entry.count

        return dict(sorted(totals.items()))

    @property
    def by_severity(self) -> dict[str, int]:
        totals: dict[str, int] = {}

        for entry in self.by_reason:
            key = entry.severity.value
            totals[key] = totals.get(key, 0) + entry.count

        return dict(sorted(totals.items()))

    @property
    def blocking_total(self) -> int:
        return sum(
            entry.count
            for entry in self.by_reason
            if severity_rank(entry.severity)
            >= severity_rank(SignalReasonSeverity.BLOCKING)
        )

    @property
    def top_reason(self) -> ReasonCount | None:
        return self.by_reason[0] if self.by_reason else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "blocking_total": self.blocking_total,
            "by_reason": [entry.to_dict() for entry in self.by_reason],
            "by_category": self.by_category,
            "by_severity": self.by_severity,
            "by_status": self.by_status,
            "top_reason": (
                self.top_reason.to_dict() if self.top_reason is not None else None
            ),
        }


class SignalReasonRepository(AqosRepository[SignalReason]):
    """Structured reasons explaining why signals did not reach the market."""

    model = SignalReason

    def record_reason(
        self,
        signal_id: str,
        user_id: str,
        signal_status: SignalStatus,
        reason_code: SignalReasonCode,
        account_id: str | None = None,
        severity: SignalReasonSeverity | None = None,
        message: str | None = None,
        source: str | None = None,
        metadata: dict[str, Any] | None = None,
        reason_id: str | None = None,
        created_at_utc: datetime | None = None,
    ) -> SignalReason:
        reason = SignalReason(
            reason_id=reason_id or build_entity_id("signalreason"),
            signal_id=signal_id,
            user_id=user_id,
            account_id=account_id,
            signal_status=signal_status,
            reason_category=resolve_reason_category(reason_code),
            reason_code=reason_code,
            severity=severity or resolve_minimum_severity(reason_code),
            message=build_reason_message(reason_code, message),
            source=source,
            created_at_utc=created_at_utc or database_utc_now(),
            extra_metadata=metadata or {},
        )
        reason.validate_taxonomy()

        self.add(reason)
        self.flush()

        return reason

    def list_reasons(
        self,
        signal_id: str | None = None,
        user_id: str | None = None,
        account_id: str | None = None,
        signal_status: SignalStatus | None = None,
        reason_code: SignalReasonCode | None = None,
        reason_category: SignalReasonCategory | None = None,
        severity: SignalReasonSeverity | None = None,
        created_since_utc: datetime | None = None,
    ) -> tuple[SignalReason, ...]:
        statement = select(SignalReason)

        if signal_id is not None:
            statement = statement.where(SignalReason.signal_id == signal_id)

        if user_id is not None:
            statement = statement.where(SignalReason.user_id == user_id)

        if account_id is not None:
            statement = statement.where(SignalReason.account_id == account_id)

        if signal_status is not None:
            statement = statement.where(SignalReason.signal_status == signal_status)

        if reason_code is not None:
            statement = statement.where(SignalReason.reason_code == reason_code)

        if reason_category is not None:
            statement = statement.where(
                SignalReason.reason_category == reason_category
            )

        if severity is not None:
            statement = statement.where(SignalReason.severity == severity)

        if created_since_utc is not None:
            statement = statement.where(
                SignalReason.created_at_utc >= created_since_utc
            )

        statement = statement.order_by(
            SignalReason.created_at_utc,
            SignalReason.reason_id,
        )

        return tuple(self.session.execute(statement).scalars().all())

    def list_blocking_reasons(
        self,
        user_id: str | None = None,
    ) -> tuple[SignalReason, ...]:
        return tuple(
            reason
            for reason in self.list_reasons(user_id=user_id)
            if reason.is_blocking
        )

    def summarize(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        signal_status: SignalStatus | None = None,
        created_since_utc: datetime | None = None,
    ) -> ReasonSummary:
        reasons = self.list_reasons(
            user_id=user_id,
            account_id=account_id,
            signal_status=signal_status,
            created_since_utc=created_since_utc,
        )

        totals: dict[
            tuple[SignalReasonCode, SignalReasonCategory, SignalReasonSeverity],
            int,
        ] = {}
        status_totals: dict[str, int] = {}

        for reason in reasons:
            key = (reason.reason_code, reason.reason_category, reason.severity)
            totals[key] = totals.get(key, 0) + 1
            status_totals[reason.signal_status.value] = (
                status_totals.get(reason.signal_status.value, 0) + 1
            )

        ordered = sorted(
            totals.items(),
            key=lambda item: (-item[1], item[0][0].value),
        )

        return ReasonSummary(
            total=len(reasons),
            by_reason=tuple(
                ReasonCount(
                    reason_code=code,
                    reason_category=category,
                    severity=severity,
                    count=count,
                )
                for (code, category, severity), count in ordered
            ),
            by_status=dict(sorted(status_totals.items())),
        )

    def count_by_category(self, user_id: str | None = None) -> dict[str, int]:
        statement = select(SignalReason.reason_category, func.count()).group_by(
            SignalReason.reason_category
        )

        if user_id is not None:
            statement = statement.where(SignalReason.user_id == user_id)

        rows = self.session.execute(statement).all()

        return dict(
            sorted(
                (
                    (
                        row[0].value if hasattr(row[0], "value") else str(row[0]),
                        int(row[1]),
                    )
                    for row in rows
                ),
            )
        )

    def delete_for_signal(self, signal_id: str) -> int:
        return self.delete_where(signal_id=signal_id)


def _record_decision_reason(
    signals: TradingSignalRepository,
    reasons: SignalReasonRepository,
    signal: TradingSignal,
    signal_status: SignalStatus,
    reason_code: SignalReasonCode,
    account_id: str | None,
    severity: SignalReasonSeverity | None,
    message: str | None,
    source: str | None,
    metadata: dict[str, Any] | None,
) -> SignalReason:
    return reasons.record_reason(
        signal_id=signal.signal_id,
        user_id=signal.user_id,
        account_id=account_id if account_id is not None else signal.account_id,
        signal_status=signal_status,
        reason_code=reason_code,
        severity=severity,
        message=message,
        source=source,
        metadata=metadata,
        created_at_utc=signal.updated_at_utc,
    )


def reject_signal_with_reason(
    signals: TradingSignalRepository,
    reasons: SignalReasonRepository,
    signal_id: str,
    reason_code: SignalReasonCode,
    message: str | None = None,
    account_id: str | None = None,
    severity: SignalReasonSeverity | None = None,
    actor: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at_utc: datetime | None = None,
) -> tuple[TradingSignal, SignalReason]:
    """
    Reject a signal and record the structured reason.

    The transition runs first: if it is refused, no reason row is written, so a
    reason can never describe a decision that did not happen.
    """

    resolved_message = build_reason_message(reason_code, message)

    signal = signals.reject_signal(
        signal_id=signal_id,
        reason=resolved_message,
        actor=actor,
        occurred_at_utc=occurred_at_utc,
    )

    reason = _record_decision_reason(
        signals=signals,
        reasons=reasons,
        signal=signal,
        signal_status=SignalStatus.REJECTED,
        reason_code=reason_code,
        account_id=account_id,
        severity=severity,
        message=message,
        source=source or actor,
        metadata=metadata,
    )

    return signal, reason


def miss_signal_with_reason(
    signals: TradingSignalRepository,
    reasons: SignalReasonRepository,
    signal_id: str,
    reason_code: SignalReasonCode,
    message: str | None = None,
    account_id: str | None = None,
    severity: SignalReasonSeverity | None = None,
    actor: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at_utc: datetime | None = None,
) -> tuple[TradingSignal, SignalReason]:
    resolved_message = build_reason_message(reason_code, message)

    signal = signals.mark_missed(
        signal_id=signal_id,
        reason=resolved_message,
        actor=actor,
        occurred_at_utc=occurred_at_utc,
    )

    reason = _record_decision_reason(
        signals=signals,
        reasons=reasons,
        signal=signal,
        signal_status=SignalStatus.MISSED,
        reason_code=reason_code,
        account_id=account_id,
        severity=severity,
        message=message,
        source=source or actor,
        metadata=metadata,
    )

    return signal, reason


def fail_signal_with_reason(
    signals: TradingSignalRepository,
    reasons: SignalReasonRepository,
    signal_id: str,
    reason_code: SignalReasonCode,
    message: str | None = None,
    account_id: str | None = None,
    severity: SignalReasonSeverity | None = None,
    actor: str | None = None,
    source: str | None = None,
    metadata: dict[str, Any] | None = None,
    occurred_at_utc: datetime | None = None,
) -> tuple[TradingSignal, SignalReason]:
    resolved_message = build_reason_message(reason_code, message)

    signal = signals.mark_failed(
        signal_id=signal_id,
        reason=resolved_message,
        actor=actor,
        occurred_at_utc=occurred_at_utc,
    )

    reason = _record_decision_reason(
        signals=signals,
        reasons=reasons,
        signal=signal,
        signal_status=SignalStatus.FAILED,
        reason_code=reason_code,
        account_id=account_id,
        severity=severity,
        message=message,
        source=source or actor,
        metadata=metadata,
    )

    return signal, reason


__all__ = [
    "AQOS_SIGNAL_REASON_REPOSITORIES_VERSION",
    "ReasonCount",
    "ReasonSummary",
    "SignalReasonRepository",
    "fail_signal_with_reason",
    "miss_signal_with_reason",
    "reject_signal_with_reason",
]
