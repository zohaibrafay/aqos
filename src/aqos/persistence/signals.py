from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from enum import Enum
from typing import Any

from aqos.common.time_utils import parse_datetime, utc_now
from aqos.persistence.database import AqosDatabase
from aqos.persistence.records import (
    build_record_id,
    decode_json_field,
    encode_json_field,
    normalize_required_text,
    normalize_symbol,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema


AQOS_SIGNALS_VERSION = "1.0"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    CLOSE = "close"


class SignalSource(str, Enum):
    RULE_STRATEGY = "rule_strategy"
    ML_MODEL = "ml_model"
    MANUAL = "manual"
    EXTERNAL = "external"


class SignalStatus(str, Enum):
    GENERATED = "generated"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"
    MISSED = "missed"
    CANCELLED = "cancelled"


#: Statuses a signal can never leave.
TERMINAL_SIGNAL_STATUSES = (
    SignalStatus.REJECTED,
    SignalStatus.EXPIRED,
    SignalStatus.EXECUTED,
    SignalStatus.FAILED,
    SignalStatus.MISSED,
    SignalStatus.CANCELLED,
)

#: Statuses that mean the signal never reached the market.
UNFILLED_SIGNAL_STATUSES = (
    SignalStatus.REJECTED,
    SignalStatus.EXPIRED,
    SignalStatus.MISSED,
    SignalStatus.FAILED,
    SignalStatus.CANCELLED,
)

SIGNAL_TRANSITIONS: dict[SignalStatus, tuple[SignalStatus, ...]] = {
    SignalStatus.GENERATED: (
        SignalStatus.PENDING_APPROVAL,
        SignalStatus.APPROVED,
        SignalStatus.REJECTED,
        SignalStatus.EXPIRED,
        SignalStatus.MISSED,
        SignalStatus.CANCELLED,
    ),
    SignalStatus.PENDING_APPROVAL: (
        SignalStatus.APPROVED,
        SignalStatus.REJECTED,
        SignalStatus.EXPIRED,
        SignalStatus.MISSED,
        SignalStatus.CANCELLED,
    ),
    SignalStatus.APPROVED: (
        SignalStatus.EXECUTED,
        SignalStatus.FAILED,
        SignalStatus.EXPIRED,
        SignalStatus.MISSED,
        SignalStatus.CANCELLED,
    ),
    SignalStatus.REJECTED: (),
    SignalStatus.EXPIRED: (),
    SignalStatus.EXECUTED: (),
    SignalStatus.FAILED: (),
    SignalStatus.MISSED: (),
    SignalStatus.CANCELLED: (),
}


def is_terminal_signal_status(status: SignalStatus) -> bool:
    return status in TERMINAL_SIGNAL_STATUSES


def can_transition_signal(
    from_status: SignalStatus,
    to_status: SignalStatus,
) -> bool:
    return to_status in SIGNAL_TRANSITIONS.get(from_status, ())


def validate_signal_transition(
    from_status: SignalStatus,
    to_status: SignalStatus,
) -> None:
    if can_transition_signal(from_status, to_status):
        return

    raise ValueError(
        f"Signal cannot move from {from_status.value} to {to_status.value}."
    )


@dataclass(frozen=True)
class TradingSignal:
    signal_id: str
    user_id: str
    symbol: str
    timeframe: str
    action: SignalAction
    source: SignalSource
    status: SignalStatus
    generated_at_utc: str
    updated_at_utc: str
    account_id: str | None = None
    confidence: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    expires_at_utc: str | None = None
    source_ref: str | None = None
    model_id: str | None = None
    model_version: str | None = None
    status_reason: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.signal_id.strip():
            raise ValueError("signal_id cannot be empty.")

        if not self.user_id.strip():
            raise ValueError("user_id cannot be empty.")

        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if self.symbol != self.symbol.upper():
            raise ValueError("symbol must be stored in upper case.")

        if not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty.")

        if not self.generated_at_utc.strip():
            raise ValueError("generated_at_utc cannot be empty.")

        if not self.updated_at_utc.strip():
            raise ValueError("updated_at_utc cannot be empty.")

        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")

        for price_field, value in (
            ("entry_price", self.entry_price),
            ("stop_loss", self.stop_loss),
            ("take_profit", self.take_profit),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{price_field} must be positive.")

        if self.expires_at_utc is not None and parse_datetime(
            self.expires_at_utc
        ) <= parse_datetime(self.generated_at_utc):
            raise ValueError("expires_at_utc must be after generated_at_utc.")

        if self.source == SignalSource.ML_MODEL and not self.model_id:
            raise ValueError("model_id is required for model generated signals.")

    @property
    def is_terminal(self) -> bool:
        return is_terminal_signal_status(self.status)

    @property
    def is_actionable(self) -> bool:
        return self.status in (
            SignalStatus.GENERATED,
            SignalStatus.PENDING_APPROVAL,
            SignalStatus.APPROVED,
        )

    @property
    def reached_market(self) -> bool:
        return self.status == SignalStatus.EXECUTED

    def is_expired(self, now_utc: str | None = None) -> bool:
        if self.expires_at_utc is None:
            return False

        reference = parse_datetime(now_utc) if now_utc else utc_now()

        return parse_datetime(self.expires_at_utc) <= reference

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "action": self.action.value,
            "source": self.source.value,
            "status": self.status.value,
            "confidence": self.confidence,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "generated_at_utc": self.generated_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "expires_at_utc": self.expires_at_utc,
            "source_ref": self.source_ref,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "status_reason": self.status_reason,
            "is_terminal": self.is_terminal,
            "is_actionable": self.is_actionable,
            "reached_market": self.reached_market,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class SignalEvent:
    """One immutable row of a signal's audit trail."""

    event_id: str
    signal_id: str
    from_status: SignalStatus | None
    to_status: SignalStatus
    occurred_at_utc: str
    reason: str | None = None
    actor: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id cannot be empty.")

        if not self.signal_id.strip():
            raise ValueError("signal_id cannot be empty.")

        if not self.occurred_at_utc.strip():
            raise ValueError("occurred_at_utc cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "signal_id": self.signal_id,
            "from_status": self.from_status.value if self.from_status else None,
            "to_status": self.to_status.value,
            "occurred_at_utc": self.occurred_at_utc,
            "reason": self.reason,
            "actor": self.actor,
            "metadata": self.metadata,
        }


def build_trading_signal_from_row(row: dict[str, Any]) -> TradingSignal:
    return TradingSignal(
        signal_id=str(row["signal_id"]),
        user_id=str(row["user_id"]),
        symbol=str(row["symbol"]),
        timeframe=str(row["timeframe"]),
        action=SignalAction(str(row["action"])),
        source=SignalSource(str(row["source"])),
        status=SignalStatus(str(row["status"])),
        generated_at_utc=str(row["generated_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        account_id=row.get("account_id"),
        confidence=(
            float(row["confidence"]) if row.get("confidence") is not None else None
        ),
        entry_price=(
            float(row["entry_price"]) if row.get("entry_price") is not None else None
        ),
        stop_loss=(
            float(row["stop_loss"]) if row.get("stop_loss") is not None else None
        ),
        take_profit=(
            float(row["take_profit"]) if row.get("take_profit") is not None else None
        ),
        expires_at_utc=row.get("expires_at_utc"),
        source_ref=row.get("source_ref"),
        model_id=row.get("model_id"),
        model_version=row.get("model_version"),
        status_reason=row.get("status_reason"),
        metadata=decode_json_field(row.get("metadata")),
    )


def build_signal_event_from_row(row: dict[str, Any]) -> SignalEvent:
    from_status = row.get("from_status")

    return SignalEvent(
        event_id=str(row["event_id"]),
        signal_id=str(row["signal_id"]),
        from_status=SignalStatus(str(from_status)) if from_status else None,
        to_status=SignalStatus(str(row["to_status"])),
        occurred_at_utc=str(row["occurred_at_utc"]),
        reason=row.get("reason"),
        actor=row.get("actor"),
        metadata=decode_json_field(row.get("metadata")),
    )


class TradingSignalRepository:
    """
    Signal lifecycle store.

    Every status change is validated against the transition table and appended
    to an immutable event log, so a signal's history is always auditable.
    """

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

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
        expires_at_utc: str | None = None,
        source_ref: str | None = None,
        model_id: str | None = None,
        model_version: str | None = None,
        metadata: dict[str, Any] | None = None,
        signal_id: str | None = None,
        generated_at_utc: str | None = None,
        actor: str | None = None,
    ) -> TradingSignal:
        if status != SignalStatus.GENERATED and not can_transition_signal(
            SignalStatus.GENERATED,
            status,
        ):
            raise ValueError(f"Signals cannot be created as {status.value}.")

        timestamp = generated_at_utc or record_utc_now()

        signal = TradingSignal(
            signal_id=signal_id or build_record_id("signal"),
            user_id=normalize_required_text(user_id, "user_id"),
            symbol=normalize_symbol(symbol),
            timeframe=normalize_required_text(timeframe, "timeframe"),
            action=action,
            source=source,
            status=status,
            generated_at_utc=timestamp,
            updated_at_utc=timestamp,
            account_id=account_id,
            confidence=confidence,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            expires_at_utc=expires_at_utc,
            source_ref=source_ref,
            model_id=model_id,
            model_version=model_version,
            metadata=metadata or {},
        )

        self._insert(signal)
        self._append_event(
            signal_id=signal.signal_id,
            from_status=None,
            to_status=signal.status,
            occurred_at_utc=timestamp,
            reason="Signal created.",
            actor=actor,
        )

        return signal

    def get_signal(self, signal_id: str) -> TradingSignal | None:
        row = self.database.query_one(
            "SELECT * FROM trading_signals WHERE signal_id = ?;",
            (signal_id,),
        )

        return build_trading_signal_from_row(row) if row is not None else None

    def require_signal(self, signal_id: str) -> TradingSignal:
        signal = self.get_signal(signal_id)

        if signal is None:
            raise LookupError(f"Trading signal does not exist: {signal_id}")

        return signal

    def list_signals(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
        symbol: str | None = None,
        status: SignalStatus | None = None,
        source: SignalSource | None = None,
        generated_since_utc: str | None = None,
        limit: int | None = None,
    ) -> tuple[TradingSignal, ...]:
        clauses: list[str] = []
        parameters: list[Any] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            parameters.append(user_id)

        if account_id is not None:
            clauses.append("account_id = ?")
            parameters.append(account_id)

        if symbol is not None:
            clauses.append("symbol = ?")
            parameters.append(normalize_symbol(symbol))

        if status is not None:
            clauses.append("status = ?")
            parameters.append(status.value)

        if source is not None:
            clauses.append("source = ?")
            parameters.append(source.value)

        if generated_since_utc is not None:
            clauses.append("generated_at_utc >= ?")
            parameters.append(generated_since_utc)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_clause = f" LIMIT {int(limit)}" if limit is not None else ""

        rows = self.database.query_all(
            f"SELECT * FROM trading_signals{where} "
            f"ORDER BY generated_at_utc, signal_id{limit_clause};",
            tuple(parameters),
        )

        return tuple(build_trading_signal_from_row(row) for row in rows)

    def count_signals_by_status(
        self,
        user_id: str | None = None,
        account_id: str | None = None,
    ) -> dict[str, int]:
        clauses: list[str] = []
        parameters: list[Any] = []

        if user_id is not None:
            clauses.append("user_id = ?")
            parameters.append(user_id)

        if account_id is not None:
            clauses.append("account_id = ?")
            parameters.append(account_id)

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self.database.query_all(
            f"SELECT status, COUNT(*) AS total FROM trading_signals{where} "
            "GROUP BY status ORDER BY status;",
            tuple(parameters),
        )

        return {str(row["status"]): int(row["total"]) for row in rows}

    def transition_signal(
        self,
        signal_id: str,
        to_status: SignalStatus,
        reason: str | None = None,
        actor: str | None = None,
        occurred_at_utc: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TradingSignal:
        current = self.require_signal(signal_id)

        validate_signal_transition(current.status, to_status)

        timestamp = occurred_at_utc or record_utc_now()

        updated = replace(
            current,
            status=to_status,
            status_reason=reason,
            updated_at_utc=timestamp,
            metadata=metadata if metadata is not None else current.metadata,
        )

        self.database.execute(
            "UPDATE trading_signals SET status = ?, status_reason = ?, "
            "updated_at_utc = ?, metadata = ? WHERE signal_id = ?;",
            (
                updated.status.value,
                updated.status_reason,
                updated.updated_at_utc,
                encode_json_field(updated.metadata),
                signal_id,
            ),
        )

        self._append_event(
            signal_id=signal_id,
            from_status=current.status,
            to_status=to_status,
            occurred_at_utc=timestamp,
            reason=reason,
            actor=actor,
        )

        return updated

    def mark_pending_approval(
        self,
        signal_id: str,
        reason: str | None = None,
        actor: str | None = None,
        occurred_at_utc: str | None = None,
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
        occurred_at_utc: str | None = None,
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
        occurred_at_utc: str | None = None,
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
        occurred_at_utc: str | None = None,
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
        occurred_at_utc: str | None = None,
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
        occurred_at_utc: str | None = None,
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
        occurred_at_utc: str | None = None,
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
        now_utc: str | None = None,
        user_id: str | None = None,
        actor: str | None = None,
    ) -> tuple[TradingSignal, ...]:
        """Expire every non-terminal signal whose expiry time has passed."""

        reference = now_utc or record_utc_now()

        expired: list[TradingSignal] = []

        for signal in self.list_signals(user_id=user_id):
            if signal.is_terminal or signal.expires_at_utc is None:
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

    def list_events(self, signal_id: str) -> tuple[SignalEvent, ...]:
        rows = self.database.query_all(
            "SELECT * FROM signal_events WHERE signal_id = ? "
            "ORDER BY occurred_at_utc, event_id;",
            (signal_id,),
        )

        return tuple(build_signal_event_from_row(row) for row in rows)

    def delete_signal(self, signal_id: str) -> bool:
        cursor = self.database.execute(
            "DELETE FROM trading_signals WHERE signal_id = ?;",
            (signal_id,),
        )

        return cursor.rowcount > 0

    def _append_event(
        self,
        signal_id: str,
        from_status: SignalStatus | None,
        to_status: SignalStatus,
        occurred_at_utc: str,
        reason: str | None = None,
        actor: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SignalEvent:
        event = SignalEvent(
            event_id=build_record_id("signalevent"),
            signal_id=signal_id,
            from_status=from_status,
            to_status=to_status,
            occurred_at_utc=occurred_at_utc,
            reason=reason,
            actor=actor,
            metadata=metadata or {},
        )

        self.database.execute(
            """
            INSERT INTO signal_events (
                event_id, signal_id, from_status, to_status,
                occurred_at_utc, reason, actor, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                event.event_id,
                event.signal_id,
                event.from_status.value if event.from_status else None,
                event.to_status.value,
                event.occurred_at_utc,
                event.reason,
                event.actor,
                encode_json_field(event.metadata),
            ),
        )

        return event

    def _insert(self, signal: TradingSignal) -> None:
        self.database.execute(
            """
            INSERT INTO trading_signals (
                signal_id, user_id, account_id, symbol, timeframe, action, source,
                status, confidence, entry_price, stop_loss, take_profit,
                generated_at_utc, updated_at_utc, expires_at_utc, source_ref,
                model_id, model_version, status_reason, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                signal.signal_id,
                signal.user_id,
                signal.account_id,
                signal.symbol,
                signal.timeframe,
                signal.action.value,
                signal.source.value,
                signal.status.value,
                signal.confidence,
                signal.entry_price,
                signal.stop_loss,
                signal.take_profit,
                signal.generated_at_utc,
                signal.updated_at_utc,
                signal.expires_at_utc,
                signal.source_ref,
                signal.model_id,
                signal.model_version,
                signal.status_reason,
                encode_json_field(signal.metadata),
            ),
        )


__all__ = [
    "AQOS_SIGNALS_VERSION",
    "SIGNAL_TRANSITIONS",
    "SignalAction",
    "SignalEvent",
    "SignalSource",
    "SignalStatus",
    "TERMINAL_SIGNAL_STATUSES",
    "TradingSignal",
    "TradingSignalRepository",
    "UNFILLED_SIGNAL_STATUSES",
    "build_signal_event_from_row",
    "build_trading_signal_from_row",
    "can_transition_signal",
    "is_terminal_signal_status",
    "validate_signal_transition",
]
