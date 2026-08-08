"""
Request body for the backtest run endpoint.

Nothing here can name a file, a module or a URL. The dataset is a name the
deployment configured, the strategy is one of a fixed list, and every numeric
knob is bounded. What a client may vary is which historical data to replay and
how the simulated account behaves — never where code or data comes from.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


AQOS_HTTP_BACKTEST_ACTION_SCHEMAS_VERSION = "1.0"

MAX_NAME_LENGTH = 64
MAX_SYMBOL_LENGTH = 32
MAX_TIMEFRAME_LENGTH = 16
MAX_TIMESTAMP_LENGTH = 32

#: Bounds on the simulated account.
#:
#: Not risk policy — a backtest risks nothing. These stop a number large enough
#: to be a mistake, or to overflow the arithmetic, from reaching the simulator.
MIN_INITIAL_BALANCE = 0.01
MAX_INITIAL_BALANCE = 1_000_000_000.0
MAX_QUANTITY = 1_000_000.0
MAX_POINTS = 1_000_000.0
MAX_OPEN_POSITIONS = 100


class BacktestRunRequest(BaseModel):
    """One historical backtest to run now."""

    model_config = {"extra": "forbid"}

    strategy_name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    dataset: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    symbol: str = Field(min_length=1, max_length=MAX_SYMBOL_LENGTH)
    timeframe: str = Field(min_length=1, max_length=MAX_TIMEFRAME_LENGTH)
    period_start: str | None = Field(default=None, max_length=MAX_TIMESTAMP_LENGTH)
    period_end: str | None = Field(default=None, max_length=MAX_TIMESTAMP_LENGTH)
    initial_balance: float = Field(
        default=10_000.0,
        ge=MIN_INITIAL_BALANCE,
        le=MAX_INITIAL_BALANCE,
    )
    risk_fraction: float = Field(default=0.01, gt=0.0, le=1.0)
    fixed_quantity: float | None = Field(default=1.0, gt=0.0, le=MAX_QUANTITY)
    spread_points: float = Field(default=0.0, ge=0.0, le=MAX_POINTS)
    slippage_points: float = Field(default=0.0, ge=0.0, le=MAX_POINTS)
    commission_per_trade: float = Field(default=0.0, ge=0.0, le=MAX_POINTS)
    allow_short: bool = True
    max_open_positions: int = Field(default=1, ge=1, le=MAX_OPEN_POSITIONS)
    #: Traceability only.
    #:
    #: Naming a model records what a run was attributed to. It never claims the
    #: model is promoted, and a backtest result never implies one is fit for
    #: production.
    model_id: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    model_version: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)


__all__ = [
    "AQOS_HTTP_BACKTEST_ACTION_SCHEMAS_VERSION",
    "MAX_INITIAL_BALANCE",
    "MAX_NAME_LENGTH",
    "MAX_OPEN_POSITIONS",
    "MAX_POINTS",
    "MAX_QUANTITY",
    "MAX_SYMBOL_LENGTH",
    "MAX_TIMEFRAME_LENGTH",
    "MAX_TIMESTAMP_LENGTH",
    "MIN_INITIAL_BALANCE",
    "BacktestRunRequest",
]
