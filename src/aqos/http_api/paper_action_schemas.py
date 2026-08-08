"""
Request bodies for the paper trading action endpoints.

These describe a simulated run and a simulated market. Nothing here reaches a
broker: the market values are the bar the caller is replaying, validated as a
real bar before anything prices against it.

Fields a client must not decide are absent rather than ignored — the owning
user, the session's account once it is created, the execution mode the gate
runs at, and any free-form metadata.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


AQOS_HTTP_PAPER_ACTION_SCHEMAS_VERSION = "1.0"

MAX_NAME_LENGTH = 191
MAX_REASON_LENGTH = 512
MAX_IDENTIFIER_LENGTH = 64
MAX_SYMBOL_LENGTH = 32
MAX_TIMEFRAME_LENGTH = 16

#: Upper bound on a single paper order.
#:
#: Not a risk rule — the eligibility gate owns those. This only stops a number
#: large enough to be a mistake or an overflow probe from reaching the
#: simulator's arithmetic.
MAX_ORDER_QUANTITY = 1_000_000.0

#: Upper bound on any submitted price.
MAX_PRICE = 1_000_000_000.0


class PaperSessionCreateRequest(BaseModel):
    """A new paper run on an account the caller owns."""

    model_config = {"extra": "forbid"}

    account_id: str = Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)
    session_name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    session_type: str = Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)
    strategy_name: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    model_id: str | None = Field(
        default=None,
        max_length=MAX_IDENTIFIER_LENGTH,
    )
    model_version: str | None = Field(
        default=None,
        max_length=MAX_IDENTIFIER_LENGTH,
    )
    symbol: str | None = Field(default=None, max_length=MAX_SYMBOL_LENGTH)
    timeframe: str | None = Field(default=None, max_length=MAX_TIMEFRAME_LENGTH)


class PaperSessionActionRequest(BaseModel):
    """
    A lifecycle command, with an optional note.

    ``cancel`` and ``fail`` need the note; the session service refuses a blank
    reason for both, and the route makes that a validation error rather than a
    failure from deeper down.
    """

    model_config = {"extra": "forbid"}

    reason: str | None = Field(default=None, max_length=MAX_REASON_LENGTH)


class PaperMarketBarRequest(BaseModel):
    """
    The bar an order prices against.

    Paper trading replays a market rather than subscribing to one, so the bar
    comes from the caller. It is validated as a real bar — positive prices, a
    high that covers open and close — before the simulator sees it, so an
    impossible market cannot be used to manufacture a favourable fill.
    """

    model_config = {"extra": "forbid"}

    symbol: str = Field(min_length=1, max_length=MAX_SYMBOL_LENGTH)
    timestamp_utc: datetime
    open: float = Field(gt=0, le=MAX_PRICE)
    high: float = Field(gt=0, le=MAX_PRICE)
    low: float = Field(gt=0, le=MAX_PRICE)
    close: float = Field(gt=0, le=MAX_PRICE)
    volume: float = Field(default=0.0, ge=0)


class PaperOrderRequest(BaseModel):
    """One paper order submitted into a running session."""

    model_config = {"extra": "forbid"}

    symbol: str = Field(min_length=1, max_length=MAX_SYMBOL_LENGTH)
    action: str = Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)
    order_type: str = Field(min_length=1, max_length=MAX_IDENTIFIER_LENGTH)
    quantity: float = Field(gt=0, le=MAX_ORDER_QUANTITY)
    market: PaperMarketBarRequest
    signal_id: str | None = Field(
        default=None,
        max_length=MAX_IDENTIFIER_LENGTH,
    )
    requested_price: float | None = Field(default=None, gt=0, le=MAX_PRICE)
    stop_loss: float | None = Field(default=None, gt=0, le=MAX_PRICE)
    take_profit: float | None = Field(default=None, gt=0, le=MAX_PRICE)
    submitted_at_utc: datetime | None = None


class PaperPositionCloseRequest(BaseModel):
    """
    A manual flatten at a stated price.

    The price comes from the caller for the same reason an order's bar does:
    there is no feed behind a replayed run.
    """

    model_config = {"extra": "forbid"}

    exit_price: float = Field(gt=0, le=MAX_PRICE)
    closed_at_utc: datetime | None = None


__all__ = [
    "AQOS_HTTP_PAPER_ACTION_SCHEMAS_VERSION",
    "MAX_IDENTIFIER_LENGTH",
    "MAX_NAME_LENGTH",
    "MAX_ORDER_QUANTITY",
    "MAX_PRICE",
    "MAX_REASON_LENGTH",
    "MAX_SYMBOL_LENGTH",
    "MAX_TIMEFRAME_LENGTH",
    "PaperMarketBarRequest",
    "PaperOrderRequest",
    "PaperPositionCloseRequest",
    "PaperSessionActionRequest",
    "PaperSessionCreateRequest",
]
