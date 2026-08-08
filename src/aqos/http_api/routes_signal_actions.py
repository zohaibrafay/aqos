"""
Signal lifecycle action endpoints.

The only endpoints in the API that change business state. They decide what a
signal *means* — approved, rejected, missed, expired, cancelled — and nothing
about what happens next: no order is placed, no broker is contacted and no
account is touched. Execution is a separate concern with its own safety rails.

Every transition rule lives in :mod:`aqos.signals.models` and every reason rule
in :mod:`aqos.signal_reasons.taxonomy`. Nothing here re-states either: this
module authenticates the caller, proves ownership, hands the decision to the
existing services and translates their refusals into the API error contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aqos.database.types import database_utc_now
from aqos.http_api.action_schemas import (
    SignalActionRequest,
    SignalCancelRequest,
    SignalDecisionRequest,
)
from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.dependencies import get_write_session
from aqos.http_api.errors import ApiErrorCode, AqosApiError, ValidationApiError
from aqos.http_api.read_schemas import (
    build_signal_detail,
    build_signal_event,
    build_signal_reason,
    parse_enum,
)
from aqos.http_api.responses import json_response
from aqos.http_api.routes_auth import get_current_caller
from aqos.http_api.routes_signals import SIGNALS_PREFIX, require_signal
from aqos.signal_reasons.repositories import (
    SignalReasonRepository,
    miss_signal_with_reason,
    reject_signal_with_reason,
)
from aqos.signal_reasons.taxonomy import (
    SignalReasonCode,
    SignalReasonError,
    codes_for_status,
    validate_reason_status,
)
from aqos.signals.models import (
    InvalidSignalTransitionError,
    SignalStatus,
    TradingSignal,
)
from aqos.signals.repositories import TradingSignalRepository


AQOS_HTTP_SIGNAL_ACTION_ROUTES_VERSION = "1.0"

#: What a manually expired signal records as its reason.
#:
#: Word for word what the scheduled sweep in ``expire_due_signals`` writes, so
#: the audit trail reads the same however the expiry was triggered.
EXPIRY_REASON_MESSAGE = "Signal expiry time passed."

NOT_DUE_MESSAGE = (
    "This signal is not due to expire. Cancel it instead if it should no "
    "longer be acted on."
)

#: The action endpoints, as ``suffix -> target status``.
#:
#: Written down so the tests can assert the surface is exactly this and no
#: further transition quietly becomes reachable over HTTP. ``executed`` and
#: ``failed`` are deliberately absent: those describe what a broker did, and
#: nothing here talks to a broker.
SIGNAL_ACTION_STATUSES: dict[str, SignalStatus] = {
    "approve": SignalStatus.APPROVED,
    "reject": SignalStatus.REJECTED,
    "miss": SignalStatus.MISSED,
    "expire": SignalStatus.EXPIRED,
    "cancel": SignalStatus.CANCELLED,
    "mark-pending-approval": SignalStatus.PENDING_APPROVAL,
}

#: Actions that must be explained with a taxonomy reason code.
REASON_BEARING_ACTIONS = ("reject", "miss")


def refuse_invalid_transition(
    error: InvalidSignalTransitionError,
    signal: TradingSignal,
    to_status: SignalStatus,
) -> AqosApiError:
    """
    Translate a refused transition into the API error contract.

    The domain message names only statuses, so it is safe to show. Repeating a
    terminal action lands here, which is why it cannot create a second event or
    reason row: the refusal is raised before anything is written, and the write
    session rolls back regardless.
    """

    return AqosApiError(
        ApiErrorCode.CONFLICT,
        str(error),
        details={
            "signal_id": signal.signal_id,
            "from_status": signal.status.value,
            "to_status": to_status.value,
            "allowed_transitions": [
                status.value for status in signal.allowed_transitions
            ],
        },
    )


def resolve_reason_code(value: str, to_status: SignalStatus) -> SignalReasonCode:
    """
    Turn a submitted reason code into a taxonomy member fit for this decision.

    Checked before the transition runs so an unusable code is a plain
    validation error rather than a rollback of work already done. The category
    and the severity are never read from the request: they are resolved from
    the code when the row is written.
    """

    code = parse_enum(value, SignalReasonCode, "reason_code")

    if code is None:
        raise ValidationApiError(
            "reason_code is required for this action.",
            details={"to_status": to_status.value},
        )

    try:
        validate_reason_status(code, to_status)
    except SignalReasonError as error:
        raise ValidationApiError(
            str(error),
            details={
                "reason_code": code.value,
                "to_status": to_status.value,
                "allowed_reason_codes": [
                    allowed.value for allowed in codes_for_status(to_status)
                ],
            },
        ) from error

    return code


def collect_event_ids(session: Session, signal_id: str) -> frozenset[str]:
    """The audit trail as it stands before an action is attempted."""

    return frozenset(
        event.event_id
        for event in TradingSignalRepository(session).list_events(signal_id)
    )


def build_action_response(
    session: Session,
    signal: TradingSignal,
    known_event_ids: frozenset[str],
    reason: Any | None = None,
) -> dict[str, Any]:
    """
    The signal as it now stands, with the audit rows the action produced.

    The new event is found by elimination rather than by taking the last row:
    two transitions can share a timestamp, so "most recent" is not reliably the
    one this request just wrote.
    """

    events = TradingSignalRepository(session).list_events(signal.signal_id)
    recorded = [
        event for event in events if event.event_id not in known_event_ids
    ]

    return {
        "signal": build_signal_detail(signal),
        "event": build_signal_event(recorded[-1]) if recorded else None,
        "reason": build_signal_reason(reason) if reason is not None else None,
    }


def require_due_expiry(signal: TradingSignal, now_utc: datetime) -> None:
    """
    Refuse to call a signal expired when its time has not come.

    ``expired`` means the market moved on before anybody acted. Letting a
    caller stamp it on a live signal would make it a synonym for ``cancelled``
    and would put a false statement in the audit trail; the reason recorded
    here says time passed, so time must actually have passed.
    """

    if signal.is_expired(now_utc):
        return

    raise AqosApiError(
        ApiErrorCode.CONFLICT,
        NOT_DUE_MESSAGE,
        details={
            "signal_id": signal.signal_id,
            "has_expiry": signal.expires_at_utc is not None,
        },
    )


def build_signal_actions_router() -> APIRouter:
    router = APIRouter(prefix=SIGNALS_PREFIX, tags=["signal-actions"])

    def act(
        session: Session,
        signal_id: str,
        caller: AuthenticatedCaller,
        to_status: SignalStatus,
        apply,
    ):
        """
        Run one lifecycle action end to end.

        Ownership first, then the action, then the response. The signal is
        loaded through the same helper the read endpoints use, so a signal
        belonging to somebody else answers exactly like one that does not
        exist here too.
        """

        signal = require_signal(session, signal_id, caller)
        known_event_ids = collect_event_ids(session, signal.signal_id)

        try:
            updated, reason = apply(signal)
        except InvalidSignalTransitionError as error:
            raise refuse_invalid_transition(error, signal, to_status) from error
        except SignalReasonError as error:
            raise ValidationApiError(str(error)) from error

        return json_response(
            build_action_response(
                session=session,
                signal=updated,
                known_event_ids=known_event_ids,
                reason=reason,
            )
        )

    @router.post("/{signal_id}/approve")
    def approve_signal(
        signal_id: str,
        payload: SignalActionRequest | None = None,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """Accept the signal for trading. No order is placed by doing so."""

        note = payload.note if payload is not None else None

        def apply(signal: TradingSignal):
            updated = TradingSignalRepository(session).approve_signal(
                signal_id=signal.signal_id,
                reason=note,
                actor=caller.user_id,
            )

            return updated, None

        return act(
            session,
            signal_id,
            caller,
            SignalStatus.APPROVED,
            apply,
        )

    @router.post("/{signal_id}/mark-pending-approval")
    def mark_signal_pending_approval(
        signal_id: str,
        payload: SignalActionRequest | None = None,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """Park a generated signal until a human decides."""

        note = payload.note if payload is not None else None

        def apply(signal: TradingSignal):
            updated = TradingSignalRepository(session).mark_pending_approval(
                signal_id=signal.signal_id,
                reason=note,
                actor=caller.user_id,
            )

            return updated, None

        return act(
            session,
            signal_id,
            caller,
            SignalStatus.PENDING_APPROVAL,
            apply,
        )

    @router.post("/{signal_id}/reject")
    def reject_signal(
        signal_id: str,
        payload: SignalDecisionRequest,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """
        Refuse the signal, on the record.

        The transition runs before the reason row is written, so a reason can
        never describe a decision that was refused.
        """

        code = resolve_reason_code(payload.reason_code, SignalStatus.REJECTED)

        def apply(signal: TradingSignal):
            return reject_signal_with_reason(
                signals=TradingSignalRepository(session),
                reasons=SignalReasonRepository(session),
                signal_id=signal.signal_id,
                reason_code=code,
                message=payload.message,
                actor=caller.user_id,
            )

        return act(
            session,
            signal_id,
            caller,
            SignalStatus.REJECTED,
            apply,
        )

    @router.post("/{signal_id}/miss")
    def miss_signal(
        signal_id: str,
        payload: SignalDecisionRequest,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """Record that the opportunity passed unacted on, and why."""

        code = resolve_reason_code(payload.reason_code, SignalStatus.MISSED)

        def apply(signal: TradingSignal):
            return miss_signal_with_reason(
                signals=TradingSignalRepository(session),
                reasons=SignalReasonRepository(session),
                signal_id=signal.signal_id,
                reason_code=code,
                message=payload.message,
                actor=caller.user_id,
            )

        return act(
            session,
            signal_id,
            caller,
            SignalStatus.MISSED,
            apply,
        )

    @router.post("/{signal_id}/expire")
    def expire_signal(
        signal_id: str,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """Retire a signal whose expiry time has already passed."""

        now_utc = database_utc_now()

        def apply(signal: TradingSignal):
            require_due_expiry(signal, now_utc)

            updated = TradingSignalRepository(session).transition_signal(
                signal_id=signal.signal_id,
                to_status=SignalStatus.EXPIRED,
                reason=EXPIRY_REASON_MESSAGE,
                actor=caller.user_id,
                occurred_at_utc=now_utc,
            )

            return updated, None

        return act(
            session,
            signal_id,
            caller,
            SignalStatus.EXPIRED,
            apply,
        )

    @router.post("/{signal_id}/cancel")
    def cancel_signal(
        signal_id: str,
        payload: SignalCancelRequest,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """Withdraw the signal deliberately. The note is required."""

        def apply(signal: TradingSignal):
            updated = TradingSignalRepository(session).cancel_signal(
                signal_id=signal.signal_id,
                reason=payload.note,
                actor=caller.user_id,
            )

            return updated, None

        return act(
            session,
            signal_id,
            caller,
            SignalStatus.CANCELLED,
            apply,
        )

    return router


__all__ = [
    "AQOS_HTTP_SIGNAL_ACTION_ROUTES_VERSION",
    "EXPIRY_REASON_MESSAGE",
    "NOT_DUE_MESSAGE",
    "REASON_BEARING_ACTIONS",
    "SIGNAL_ACTION_STATUSES",
    "build_action_response",
    "build_signal_actions_router",
    "collect_event_ids",
    "refuse_invalid_transition",
    "require_due_expiry",
    "resolve_reason_code",
]
