from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from aqos.http_api.dependencies import get_session
from aqos.http_api.errors import NotFoundApiError, ValidationApiError
from aqos.http_api.pagination import (
    MAX_PAGE_LIMIT,
    build_page,
    validate_limit,
    validate_offset,
)
from aqos.http_api.read_schemas import (
    build_signal_detail,
    build_signal_event,
    build_signal_reason,
    build_signal_summary,
    parse_enum,
)
from aqos.http_api.responses import json_response
from aqos.signal_reasons.repositories import SignalReasonRepository
from aqos.signals.models import SignalAction, SignalSource, SignalStatus
from aqos.signals.repositories import TradingSignalRepository


AQOS_HTTP_SIGNAL_ROUTES_VERSION = "1.0"

SIGNALS_PREFIX = "/signals"


def require_signal(session: Session, signal_id: str):
    """
    Load a signal or raise the standard not-found error.

    The repository raises its own domain error; translating it here keeps the
    HTTP layer's error contract in one shape.
    """

    signal = TradingSignalRepository(session).get(signal_id)

    if signal is None:
        raise NotFoundApiError(
            "Signal was not found.",
            details={"signal_id": signal_id},
        )

    return signal


def validate_period(
    generated_from: datetime | None,
    generated_to: datetime | None,
) -> None:
    if (
        generated_from is not None
        and generated_to is not None
        and generated_to < generated_from
    ):
        raise ValidationApiError(
            "generated_to cannot be before generated_from.",
            details={
                "generated_from": generated_from.isoformat(),
                "generated_to": generated_to.isoformat(),
            },
        )


def build_signals_router() -> APIRouter:
    router = APIRouter(prefix=SIGNALS_PREFIX, tags=["signals"])

    @router.get("")
    def list_signals(
        session: Session = Depends(get_session),
        user_id: str | None = None,
        account_id: str | None = None,
        symbol: str | None = None,
        status: str | None = None,
        source: str | None = None,
        action: str | None = None,
        generated_from: datetime | None = None,
        generated_to: datetime | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        """
        Signals matching the given filters.

        ``total`` is left unset: counting every match is a second full scan and
        the value is not needed to render a page. An absent total is honest; a
        derived one would not be.
        """

        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)
        validate_period(generated_from, generated_to)

        records = TradingSignalRepository(session).list_signals(
            user_id=user_id,
            account_id=account_id,
            symbol=symbol,
            status=parse_enum(status, SignalStatus, "status"),
            source=parse_enum(source, SignalSource, "source"),
            generated_since_utc=generated_from,
        )

        if generated_to is not None:
            records = tuple(
                record
                for record in records
                if record.generated_at_utc <= generated_to
            )

        resolved_action = parse_enum(action, SignalAction, "action")

        if resolved_action is not None:
            records = tuple(
                record for record in records if record.action == resolved_action
            )

        window = records[resolved_offset : resolved_offset + resolved_limit]

        page = build_page(
            items=[build_signal_summary(record) for record in window],
            limit=resolved_limit,
            offset=resolved_offset,
            total=None,
        )

        return json_response(page.to_dict())

    @router.get("/{signal_id}")
    def get_signal(
        signal_id: str,
        session: Session = Depends(get_session),
    ):
        return json_response(build_signal_detail(require_signal(session, signal_id)))

    @router.get("/{signal_id}/events")
    def get_signal_events(
        signal_id: str,
        session: Session = Depends(get_session),
    ):
        """The signal's lifecycle audit trail, oldest first."""

        require_signal(session, signal_id)

        events = TradingSignalRepository(session).list_events(signal_id)

        return json_response(
            {
                "signal_id": signal_id,
                "items": [build_signal_event(event) for event in events],
                "count": len(events),
            }
        )

    @router.get("/{signal_id}/reasons")
    def get_signal_reasons(
        signal_id: str,
        session: Session = Depends(get_session),
    ):
        """Structured reasons explaining why the signal ended as it did."""

        require_signal(session, signal_id)

        reasons = SignalReasonRepository(session).list_reasons(
            signal_id=signal_id,
        )

        return json_response(
            {
                "signal_id": signal_id,
                "items": [build_signal_reason(reason) for reason in reasons],
                "count": len(reasons),
            }
        )

    return router


__all__ = [
    "AQOS_HTTP_SIGNAL_ROUTES_VERSION",
    "SIGNALS_PREFIX",
    "build_signals_router",
    "require_signal",
    "validate_period",
]
