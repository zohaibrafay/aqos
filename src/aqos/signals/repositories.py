from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select

from aqos.database.repository import AqosRepository, RepositoryError
from aqos.database.types import database_utc_now
from aqos.signals.models import (
    CREATABLE_SIGNAL_STATUSES,
    SignalAction,
    SignalEvent,
    SignalSource,
    SignalStatus,
    TradingSignal,
    normalize_required_text,
    validate_signal_transition,
)
from aqos.users.repositories import build_entity_id


AQOS_SIGNAL_REPOSITORIES_VERSION = "1.0"


class TradingSignalRepository(AqosRepository[TradingSignal]):
    """
    Signal lifecycle store.

    Every status change is validated against the transition table and appended
    to the event log in the same unit of work, so a signal can never change
    status without a matching audit row.
    """

    model = TradingSignal

    def create_signal(
        self,
        user_id: str,
        symbol: str,
        timeframe: str,
        action: SignalAction,
        source: SignalSource,
        account_id: str | None = None,
        status: SignalStatus = SignalStatus.GENERATED,
        confidence: float | None = None,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        strategy_name: str | None = None,
        model_id: str | None = None,
        model_version: str | None = None,
        expires_at_utc: datetime | None = None,
        metadata: dict[str, Any] | None = None,
        signal_id: str | None = None,
        generated_at_utc: datetime | None = None,
        actor: str | None = None,
    ) -> TradingSignal:
        if status not in CREATABLE_SIGNAL_STATUSES:
            raise RepositoryError(
                f"Signals cannot be created as {status.value}."
            )

        timestamp = generated_at_utc or database_utc_now()

        signal = TradingSignal(
            signal_id=signal_id or build_entity_id("signal"),
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            timeframe=timeframe,
            action=action,
            status=status,
            source=source,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy_name=strategy_name,
            model_id=model_id,
            model_version=model_version,
            generated_at_utc=timestamp,
            expires_at_utc=expires_at_utc,
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            extra_metadata=metadata or {},
        )
        signal.validate_traceability()

        self.add(signal)

        # The signal row must exist before its audit row references it.
        self.flush()

        self.append_event(
            signal_id=signal.signal_id,
            from_status=None,
            to_status=signal.status,
            occurred_at_utc=timestamp,
            reason="Signal created.",
            actor=actor,
        )
        self.flush()

        return signal

    def require_signal(self, signal_id: str) -> TradingSignal:
        return self.require(signal_id)

    def list_signals(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        symbol: str | None = None,
        status: SignalStatus | None = None,
        source: SignalSource | None = None,
        generated_since_utc: datetime | None = None,
        limit: int | None = None,
    ) -> tuple[TradingSignal, ...]:
        statement = select(TradingSignal)

        if user_id is not None:
            statement = statement.where(TradingSignal.user_id == user_id)

        if account_id is not None:
            statement = statement.where(TradingSignal.account_id == account_id)

        if symbol is not None:
            statement = statement.where(
                TradingSignal.symbol == "".join(str(symbol).split()).upper()
            )

        if status is not None:
            statement = statement.where(TradingSignal.status == status)

        if source is not None:
            statement = statement.where(TradingSignal.source == source)

        if generated_since_utc is not None:
            statement = statement.where(
                TradingSignal.generated_at_utc >= generated_since_utc
            )

        statement = statement.order_by(
            TradingSignal.generated_at_utc,
            TradingSignal.signal_id,
        )

        if limit is not None:
            statement = statement.limit(limit)

        return tuple(self.session.execute(statement).scalars().all())

    def list_open_signals(
        self,
        user_id: str | None = None,
    ) -> tuple[TradingSignal, ...]:
        return tuple(
            signal
            for signal in self.list_signals(user_id=user_id)
            if signal.is_open
        )

    def count_by_status(self, user_id: str | None = None) -> dict[str, int]:
        statement = select(TradingSignal.status, func.count()).group_by(
            TradingSignal.status
        )

        if user_id is not None:
            statement = statement.where(TradingSignal.user_id == user_id)

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

    def transition_signal(
        self,
        signal_id: str,
        to_status: SignalStatus,
        reason: str | None = None,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TradingSignal:
        signal = self.require_signal(signal_id)

        validate_signal_transition(signal.status, to_status)

        timestamp = occurred_at_utc or database_utc_now()
        from_status = signal.status

        signal.status = to_status
        signal.status_reason = reason
        signal.updated_at_utc = timestamp

        if metadata is not None:
            signal.extra_metadata = metadata

        self.append_event(
            signal_id=signal_id,
            from_status=from_status,
            to_status=to_status,
            occurred_at_utc=timestamp,
            reason=reason,
            actor=actor,
        )
        self.flush()

        return signal

    def mark_pending_approval(
        self,
        signal_id: str,
        reason: str | None = None,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> TradingSignal:
        return self.transition_signal(
            signal_id=signal_id,
            to_status=SignalStatus.PENDING_APPROVAL,
            reason=reason or "Awaiting manual approval.",
            actor=actor,
            occurred_at_utc=occurred_at_utc,
        )

    def approve_signal(
        self,
        signal_id: str,
        reason: str | None = None,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> TradingSignal:
        return self.transition_signal(
            signal_id=signal_id,
            to_status=SignalStatus.APPROVED,
            reason=reason,
            actor=actor,
            occurred_at_utc=occurred_at_utc,
        )

    def reject_signal(
        self,
        signal_id: str,
        reason: str,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> TradingSignal:
        return self.transition_signal(
            signal_id=signal_id,
            to_status=SignalStatus.REJECTED,
            reason=normalize_required_text(reason, "reason"),
            actor=actor,
            occurred_at_utc=occurred_at_utc,
        )

    def mark_missed(
        self,
        signal_id: str,
        reason: str,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> TradingSignal:
        return self.transition_signal(
            signal_id=signal_id,
            to_status=SignalStatus.MISSED,
            reason=normalize_required_text(reason, "reason"),
            actor=actor,
            occurred_at_utc=occurred_at_utc,
        )

    def mark_executed(
        self,
        signal_id: str,
        reason: str | None = None,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> TradingSignal:
        return self.transition_signal(
            signal_id=signal_id,
            to_status=SignalStatus.EXECUTED,
            reason=reason,
            actor=actor,
            occurred_at_utc=occurred_at_utc,
        )

    def mark_failed(
        self,
        signal_id: str,
        reason: str,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> TradingSignal:
        return self.transition_signal(
            signal_id=signal_id,
            to_status=SignalStatus.FAILED,
            reason=normalize_required_text(reason, "reason"),
            actor=actor,
            occurred_at_utc=occurred_at_utc,
        )

    def cancel_signal(
        self,
        signal_id: str,
        reason: str,
        actor: str | None = None,
        occurred_at_utc: datetime | None = None,
    ) -> TradingSignal:
        return self.transition_signal(
            signal_id=signal_id,
            to_status=SignalStatus.CANCELLED,
            reason=normalize_required_text(reason, "reason"),
            actor=actor,
            occurred_at_utc=occurred_at_utc,
        )

    def expire_due_signals(
        self,
        now_utc: datetime | None = None,
        user_id: str | None = None,
        actor: str | None = None,
    ) -> tuple[TradingSignal, ...]:
        """Expire every open signal whose expiry time has passed."""

        reference = now_utc or database_utc_now()

        expired: list[TradingSignal] = []

        for signal in self.list_signals(user_id=user_id):
            if not signal.is_open or signal.expires_at_utc is None:
                continue

            if not signal.is_expired(reference):
                continue

            expired.append(
                self.transition_signal(
                    signal_id=signal.signal_id,
                    to_status=SignalStatus.EXPIRED,
                    reason="Signal expiry time passed.",
                    actor=actor,
                    occurred_at_utc=reference,
                )
            )

        return tuple(expired)

    def append_event(
        self,
        signal_id: str,
        from_status: SignalStatus | None,
        to_status: SignalStatus,
        occurred_at_utc: datetime,
        reason: str | None = None,
        actor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SignalEvent:
        event = SignalEvent(
            event_id=build_entity_id("signalevent"),
            signal_id=signal_id,
            from_status=from_status,
            to_status=to_status,
            occurred_at_utc=occurred_at_utc,
            reason=reason,
            actor=actor,
            created_at_utc=occurred_at_utc,
            extra_metadata=metadata or {},
        )

        self.session.add(event)

        return event

    def list_events(self, signal_id: str) -> tuple[SignalEvent, ...]:
        statement = (
            select(SignalEvent)
            .where(SignalEvent.signal_id == signal_id)
            .order_by(SignalEvent.occurred_at_utc, SignalEvent.event_id)
        )

        return tuple(self.session.execute(statement).scalars().all())

    def build_status_history(self, signal_id: str) -> tuple[str, ...]:
        return tuple(
            event.to_status.value for event in self.list_events(signal_id)
        )

    def delete_signal(self, signal_id: str) -> bool:
        return self.delete_by_primary_key(signal_id)


__all__ = [
    "AQOS_SIGNAL_REPOSITORIES_VERSION",
    "TradingSignalRepository",
]
