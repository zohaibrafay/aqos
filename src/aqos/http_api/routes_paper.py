from __future__ import annotations

from datetime import datetime
from typing import Any

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
    build_paper_decision,
    build_paper_fill,
    build_paper_order,
    build_paper_position,
    build_paper_session_detail,
    build_paper_session_result,
    build_paper_session_summary,
    build_paper_trade,
    parse_enum,
)
from aqos.http_api.responses import json_response
from aqos.paper_trading.contracts import PaperOrderStatus, PaperPositionStatus
from aqos.paper_trading.repositories import (
    PaperExecutionDecisionRepository,
    PaperFillRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PaperTradeRepository,
)
from aqos.paper_trading.session_service import (
    PaperSessionRepository,
    PaperSessionResultService,
)
from aqos.paper_trading.sessions import PaperSessionStatus, PaperSessionType


AQOS_HTTP_PAPER_ROUTES_VERSION = "1.0"

PAPER_PREFIX = "/paper"


def require_session_record(session: Session, session_id: str):
    record = PaperSessionRepository(session).get(session_id)

    if record is None:
        raise NotFoundApiError(
            "Paper session was not found.",
            details={"session_id": session_id},
        )

    return record


def validate_period(
    started_from: datetime | None,
    started_to: datetime | None,
) -> None:
    if (
        started_from is not None
        and started_to is not None
        and started_to < started_from
    ):
        raise ValidationApiError(
            "started_to cannot be before started_from.",
            details={
                "started_from": started_from.isoformat(),
                "started_to": started_to.isoformat(),
            },
        )


def build_child_page(
    items: list[dict[str, Any]],
    session_id: str,
    limit: int,
    offset: int,
    total: int,
) -> dict[str, Any]:
    """A page of records belonging to one session."""

    payload = build_page(
        items=items,
        limit=limit,
        offset=offset,
        total=total,
    ).to_dict()
    payload["session_id"] = session_id

    return payload


def build_paper_router() -> APIRouter:
    router = APIRouter(prefix=PAPER_PREFIX, tags=["paper"])

    @router.get("/sessions")
    def list_sessions(
        session: Session = Depends(get_session),
        user_id: str | None = None,
        account_id: str | None = None,
        session_type: str | None = None,
        status: str | None = None,
        strategy_name: str | None = None,
        model_id: str | None = None,
        started_from: datetime | None = None,
        started_to: datetime | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)
        validate_period(started_from, started_to)

        records = PaperSessionRepository(session).list_sessions(
            user_id=user_id,
            account_id=account_id,
            session_type=parse_enum(
                session_type,
                PaperSessionType,
                "session_type",
            ),
            status=parse_enum(status, PaperSessionStatus, "status"),
            model_id=model_id,
            strategy_name=strategy_name,
            started_since_utc=started_from,
            started_until_utc=started_to,
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        page = build_page(
            items=[build_paper_session_summary(record) for record in window],
            limit=resolved_limit,
            offset=resolved_offset,
            total=len(records),
        )

        return json_response(page.to_dict())

    @router.get("/sessions/{session_id}")
    def get_session_detail(
        session_id: str,
        session: Session = Depends(get_session),
    ):
        return json_response(
            build_paper_session_detail(
                require_session_record(session, session_id)
            )
        )

    @router.get("/sessions/{session_id}/result")
    def get_session_result(
        session_id: str,
        session: Session = Depends(get_session),
    ):
        """
        The session's measured result.

        Calculated from the session's own persisted rows. A session that closed
        no trade reports unknown ratios rather than zeros it did not earn.
        """

        require_session_record(session, session_id)

        result = PaperSessionResultService(session).build_result(
            session_id=session_id,
        )

        return json_response(build_paper_session_result(result))

    @router.get("/sessions/{session_id}/orders")
    def get_session_orders(
        session_id: str,
        session: Session = Depends(get_session),
        status: str | None = None,
        symbol: str | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        record = require_session_record(session, session_id)

        # Scoped to both the session and its account, so a session id can never
        # surface another account's records.
        records = PaperOrderRepository(session).list_orders(
            session_id=record.session_id,
            account_id=record.account_id,
            status=parse_enum(status, PaperOrderStatus, "status"),
            symbol=symbol,
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        return json_response(
            build_child_page(
                items=[build_paper_order(item) for item in window],
                session_id=session_id,
                limit=resolved_limit,
                offset=resolved_offset,
                total=len(records),
            )
        )

    @router.get("/sessions/{session_id}/fills")
    def get_session_fills(
        session_id: str,
        session: Session = Depends(get_session),
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        record = require_session_record(session, session_id)

        records = PaperFillRepository(session).list_fills(
            session_id=record.session_id,
            account_id=record.account_id,
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        return json_response(
            build_child_page(
                items=[build_paper_fill(item) for item in window],
                session_id=session_id,
                limit=resolved_limit,
                offset=resolved_offset,
                total=len(records),
            )
        )

    @router.get("/sessions/{session_id}/positions")
    def get_session_positions(
        session_id: str,
        session: Session = Depends(get_session),
        status: str | None = None,
        symbol: str | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        record = require_session_record(session, session_id)

        records = PaperPositionRepository(session).list_positions(
            session_id=record.session_id,
            account_id=record.account_id,
            status=parse_enum(status, PaperPositionStatus, "status"),
            symbol=symbol,
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        return json_response(
            build_child_page(
                items=[build_paper_position(item) for item in window],
                session_id=session_id,
                limit=resolved_limit,
                offset=resolved_offset,
                total=len(records),
            )
        )

    @router.get("/sessions/{session_id}/trades")
    def get_session_trades(
        session_id: str,
        session: Session = Depends(get_session),
        symbol: str | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        record = require_session_record(session, session_id)

        records = PaperTradeRepository(session).list_trades(
            session_id=record.session_id,
            account_id=record.account_id,
            symbol=symbol,
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        return json_response(
            build_child_page(
                items=[build_paper_trade(item) for item in window],
                session_id=session_id,
                limit=resolved_limit,
                offset=resolved_offset,
                total=len(records),
            )
        )

    @router.get("/sessions/{session_id}/decisions")
    def get_session_decisions(
        session_id: str,
        session: Session = Depends(get_session),
        is_allowed: bool | None = None,
        limit: int | None = Query(default=None, le=MAX_PAGE_LIMIT * 10),
        offset: int | None = None,
    ):
        """
        Why each execution attempt was allowed or refused.

        Refusals carry their structured taxonomy code, so a blocked attempt can
        be explained without reading a log.
        """

        resolved_limit = validate_limit(limit)
        resolved_offset = validate_offset(offset)

        record = require_session_record(session, session_id)

        records = PaperExecutionDecisionRepository(session).list_decisions(
            session_id=record.session_id,
            account_id=record.account_id,
            is_allowed=is_allowed,
        )
        window = records[resolved_offset : resolved_offset + resolved_limit]

        return json_response(
            build_child_page(
                items=[build_paper_decision(item) for item in window],
                session_id=session_id,
                limit=resolved_limit,
                offset=resolved_offset,
                total=len(records),
            )
        )

    return router


__all__ = [
    "AQOS_HTTP_PAPER_ROUTES_VERSION",
    "PAPER_PREFIX",
    "build_child_page",
    "build_paper_router",
    "require_session_record",
    "validate_period",
]
