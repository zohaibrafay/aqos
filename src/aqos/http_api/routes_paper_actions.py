"""
Paper trading action endpoints.

Simulated activity only. Every route here goes through
:class:`aqos.paper_trading.commands.PaperCommandService`, which is the one
approved way into paper trading from outside the package; the simulator, the
in-memory broker, the execution service and the eligibility gate are all
unreachable from this module by design, and a guard test proves it.

Nothing here can move real money. A session may only be opened on a paper
account, and an order may only be booked into a running session on that same
paper account.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aqos.accounts.repositories import TradingAccountRepository
from aqos.database.types import database_utc_now
from aqos.http_api.auth import AuthenticatedCaller
from aqos.http_api.authz import require_owned_record
from aqos.http_api.dependencies import get_write_session
from aqos.http_api.errors import ApiErrorCode, AqosApiError, ValidationApiError
from aqos.http_api.paper_action_schemas import (
    PaperOrderRequest,
    PaperPositionCloseRequest,
    PaperSessionActionRequest,
    PaperSessionCreateRequest,
)
from aqos.http_api.read_schemas import (
    build_paper_decision,
    build_paper_fill,
    build_paper_order,
    build_paper_position,
    build_paper_session_detail,
    build_paper_trade,
    parse_enum,
)
from aqos.http_api.responses import json_response
from aqos.http_api.routes_auth import get_current_caller
from aqos.http_api.routes_paper import PAPER_PREFIX
from aqos.paper_trading.commands import (
    PAPER_SESSION_COMMANDS,
    PaperCommandService,
    PaperMarketQuote,
    PaperOrderCommand,
    PaperOrderOutcome,
    PaperSessionCommand,
)
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperOrderType,
    PaperTradingError,
)
from aqos.paper_trading.sessions import PaperSessionType


AQOS_HTTP_PAPER_ACTION_ROUTES_VERSION = "1.0"

#: Paper actions a session must be in a particular state to accept.
#:
#: Not re-stated from the lifecycle table: this only names the commands the
#: HTTP layer offers. Whether one is legal right now is decided by Sprint 052.
PAPER_ACTION_COMMANDS = tuple(PAPER_SESSION_COMMANDS)


def refuse_paper_command(error: PaperTradingError) -> AqosApiError:
    """
    Translate a refused paper command into the API error contract.

    Always a conflict: everything the command layer refuses is about the state
    of a real resource — a session that has finished, an account that is not a
    paper account, a position that is already closed — rather than about the
    shape of the request, which pydantic has already checked.

    The domain messages name accounts, sessions and statuses and nothing else,
    so they are safe to show; the exception type itself never is.
    """

    return AqosApiError(ApiErrorCode.CONFLICT, str(error))


def build_session_transition(
    record: Any,
    command: str,
    from_status: str | None,
) -> dict[str, Any]:
    """What the command did to the session, as a flat block."""

    return {
        "command": command,
        "from_status": from_status,
        "to_status": record.status.value,
        "reason": record.status_reason,
        "occurred_at_utc": (
            record.updated_at_utc.isoformat()
            if record.updated_at_utc is not None
            else None
        ),
        "ended_at_utc": (
            record.ended_at_utc.isoformat()
            if record.ended_at_utc is not None
            else None
        ),
    }


def build_order_outcome(outcome: PaperOrderOutcome) -> dict[str, Any]:
    """
    One submitted order, as the API describes it.

    The decision is always present, accepted or not: a refused attempt has to
    be as explainable as a successful one. Everything else is null or empty
    when the gate refused, because a refusal leaves nothing behind.
    """

    return {
        "accepted": outcome.accepted,
        "decision": build_paper_decision(outcome.decision),
        "order": (
            build_paper_order(outcome.order)
            if outcome.order is not None
            else None
        ),
        "fills": [build_paper_fill(fill) for fill in outcome.fills],
        "position": (
            build_paper_position(outcome.position)
            if outcome.position is not None
            else None
        ),
        "trade": (
            build_paper_trade(outcome.trade)
            if outcome.trade is not None
            else None
        ),
        "rejection_reason": outcome.rejection_reason,
        "rejection_message": outcome.rejection_message,
    }


def require_owned_session(
    session: Session,
    session_id: str,
    caller: AuthenticatedCaller,
):
    """
    Load a paper session the caller owns, or refuse.

    Another user's session answers exactly like one that does not exist, so
    session ids cannot be probed across accounts.
    """

    return require_owned_record(
        caller=caller,
        record=PaperCommandService(session).session_records.get(session_id),
        resource="paper_session",
        resource_id=session_id,
    )


def require_owned_account(
    session: Session,
    account_id: str,
    caller: AuthenticatedCaller,
):
    return require_owned_record(
        caller=caller,
        record=TradingAccountRepository(session).get(account_id),
        resource="account",
        resource_id=account_id,
    )


def require_enum(value: str, enum_type, field_name: str):
    """A required enum field, refused rather than defaulted when unknown."""

    parsed = parse_enum(value, enum_type, field_name)

    if parsed is None:
        raise ValidationApiError(f"{field_name} is required.")

    return parsed


def build_paper_actions_router() -> APIRouter:
    router = APIRouter(prefix=PAPER_PREFIX, tags=["paper-actions"])

    def run(command):
        """
        Run one paper command, translating its refusals.

        Every refusal from the command layer becomes a conflict rather than an
        unhandled error, so no internal exception name or traceback reaches a
        caller and the write session rolls back cleanly.
        """

        try:
            return command()
        except PaperTradingError as error:
            raise refuse_paper_command(error) from error

    @router.post("/sessions", status_code=201)
    def create_paper_session(
        payload: PaperSessionCreateRequest,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """
        Open a paper run on an account the caller owns.

        The account must be a paper account. A live or funded one is refused
        here and again inside the command layer: a session is what later
        activity is booked against, so it must never attach to real capital.
        """

        account = require_owned_account(session, payload.account_id, caller)
        session_type = require_enum(
            payload.session_type,
            PaperSessionType,
            "session_type",
        )

        record = run(
            lambda: PaperCommandService(session).open_session(
                PaperSessionCommand(
                    account_id=account.account_id,
                    session_name=payload.session_name,
                    session_type=session_type,
                    strategy_name=payload.strategy_name,
                    model_id=payload.model_id,
                    model_version=payload.model_version,
                    symbol=payload.symbol,
                    timeframe=payload.timeframe,
                )
            )
        )

        return json_response(
            {
                "session": build_paper_session_detail(record),
                "transition": build_session_transition(record, "create", None),
            },
            status_code=201,
        )

    def session_command_route(command: str):
        def handler(
            session_id: str,
            payload: PaperSessionActionRequest | None = None,
            session: Session = Depends(get_write_session),
            caller: AuthenticatedCaller = Depends(get_current_caller),
        ):
            record = require_owned_session(session, session_id, caller)
            from_status = record.status.value
            reason = payload.reason if payload is not None else None

            updated = run(
                lambda: PaperCommandService(session).command_session(
                    session_id=record.session_id,
                    command=command,
                    reason=reason,
                )
            )

            return json_response(
                {
                    "session": build_paper_session_detail(updated),
                    "transition": build_session_transition(
                        updated,
                        command,
                        from_status,
                    ),
                }
            )

        handler.__name__ = f"{command}_paper_session"
        handler.__doc__ = (
            f"Move a paper session to {PAPER_SESSION_COMMANDS[command].value}."
        )

        return handler

    for command in PAPER_ACTION_COMMANDS:
        router.post(f"/sessions/{{session_id}}/{command}")(
            session_command_route(command)
        )

    @router.post("/sessions/{session_id}/orders", status_code=201)
    def submit_paper_order(
        session_id: str,
        payload: PaperOrderRequest,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """
        Submit one simulated order into a running session.

        The eligibility gate decides, and its decision is recorded either way.
        A refusal is a normal answer with a 201 body saying ``accepted: false``
        rather than an error: the attempt happened, was audited, and produced
        no order.
        """

        record = require_owned_session(session, session_id, caller)
        action = require_enum(payload.action, PaperAction, "action")
        order_type = require_enum(
            payload.order_type,
            PaperOrderType,
            "order_type",
        )

        outcome = run(
            lambda: PaperCommandService(session).submit_order(
                PaperOrderCommand(
                    account_id=record.account_id,
                    session_id=record.session_id,
                    symbol=payload.symbol,
                    action=action,
                    order_type=order_type,
                    quantity=payload.quantity,
                    market=PaperMarketQuote(
                        symbol=payload.market.symbol,
                        timestamp_utc=payload.market.timestamp_utc,
                        open=payload.market.open,
                        high=payload.market.high,
                        low=payload.market.low,
                        close=payload.market.close,
                        volume=payload.market.volume,
                    ),
                    submitted_at_utc=(
                        payload.submitted_at_utc or database_utc_now()
                    ),
                    signal_id=payload.signal_id,
                    requested_price=payload.requested_price,
                    stop_loss=payload.stop_loss,
                    take_profit=payload.take_profit,
                )
            )
        )

        return json_response(build_order_outcome(outcome), status_code=201)

    @router.post("/sessions/{session_id}/orders/{order_id}/cancel")
    def cancel_paper_order(
        session_id: str,
        order_id: str,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """Withdraw an order this session placed but that has not finished."""

        record = require_owned_session(session, session_id, caller)

        order = run(
            lambda: PaperCommandService(session).cancel_order(
                session_id=record.session_id,
                order_id=order_id,
            )
        )

        return json_response({"order": build_paper_order(order)})

    @router.post("/sessions/{session_id}/positions/{position_id}/close")
    def close_paper_position(
        session_id: str,
        position_id: str,
        payload: PaperPositionCloseRequest,
        session: Session = Depends(get_write_session),
        caller: AuthenticatedCaller = Depends(get_current_caller),
    ):
        """Flatten one open position at the price the caller states."""

        record = require_owned_session(session, session_id, caller)

        outcome = run(
            lambda: PaperCommandService(session).close_position(
                session_id=record.session_id,
                position_id=position_id,
                exit_price=payload.exit_price,
                closed_at_utc=payload.closed_at_utc,
            )
        )

        return json_response(
            {
                "position": build_paper_position(outcome.position),
                "trade": build_paper_trade(outcome.trade),
                "exit_reason": outcome.exit_reason.value,
                "exit_price": outcome.exit_price,
            }
        )

    return router


__all__ = [
    "AQOS_HTTP_PAPER_ACTION_ROUTES_VERSION",
    "PAPER_ACTION_COMMANDS",
    "build_order_outcome",
    "build_paper_actions_router",
    "build_session_transition",
    "refuse_paper_command",
    "require_enum",
    "require_owned_account",
    "require_owned_session",
]
