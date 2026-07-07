"""
Common constants.

Defines shared constants used across AQOS modules.
"""

from __future__ import annotations

from typing import Final


AQOS_NAME: Final[str] = "AQOS"
AQOS_FULL_NAME: Final[str] = "AI Quant Operating System"

DEFAULT_TIMEFRAME: Final[str] = "H1"
DEFAULT_SYMBOL: Final[str] = "XAUUSD"
DEFAULT_SOURCE: Final[str] = "local"

DEFAULT_ACCOUNT_BALANCE: Final[float] = 10_000.0
DEFAULT_RISK_PERCENT: Final[float] = 0.01
DEFAULT_MAX_RISK_PERCENT: Final[float] = 0.02
DEFAULT_MEMORY_IMPORTANCE: Final[float] = 0.5
DEFAULT_SEARCH_LIMIT: Final[int] = 5

VALID_SIGNALS: Final[tuple[str, ...]] = (
    "buy",
    "sell",
    "hold",
)

VALID_SIDES: Final[tuple[str, ...]] = (
    "buy",
    "sell",
)

VALID_ORDER_TYPES: Final[tuple[str, ...]] = (
    "market",
    "limit",
    "stop",
)

VALID_ORDER_STATUSES: Final[tuple[str, ...]] = (
    "open",
    "filled",
    "cancelled",
)

VALID_POSITION_STATUSES: Final[tuple[str, ...]] = (
    "open",
    "closed",
)

VALID_EXPERIMENT_STATUSES: Final[tuple[str, ...]] = (
    "created",
    "running",
    "completed",
    "failed",
)

VALID_SENTIMENTS: Final[tuple[str, ...]] = (
    "positive",
    "negative",
    "neutral",
)

VALID_IMPACTS: Final[tuple[str, ...]] = (
    "low",
    "medium",
    "high",
)

VALID_MEMORY_TYPES: Final[tuple[str, ...]] = (
    "observation",
    "pattern",
    "trade",
    "research",
    "strategy",
    "risk",
    "execution",
    "evaluation",
)

VALID_TIMEFRAMES: Final[tuple[str, ...]] = (
    "M1",
    "M5",
    "M15",
    "M30",
    "H1",
    "H4",
    "D1",
    "W1",
    "MN1",
)

OHLCV_COLUMNS: Final[tuple[str, ...]] = (
    "timestamp",
    "open",
    "high",
    "low",
    "close",
    "volume",
)

PRICE_COLUMNS: Final[tuple[str, ...]] = (
    "open",
    "high",
    "low",
    "close",
)

DEFAULT_NAMESPACE: Final[str] = "default"
RESEARCH_NAMESPACE: Final[str] = "research"
MEMORY_NAMESPACE: Final[str] = "memory"
EXPERIMENT_NAMESPACE: Final[str] = "experiments"
MODEL_NAMESPACE: Final[str] = "models"

STATUS_OK: Final[str] = "ok"
STATUS_ERROR: Final[str] = "error"

MESSAGE_TRADE_ALLOWED: Final[str] = "Trade allowed."
MESSAGE_NOT_CONFIGURED: Final[str] = "Not configured."
MESSAGE_NOT_FOUND: Final[str] = "Record does not exist."

BUY_SIGNAL: Final[str] = "buy"
SELL_SIGNAL: Final[str] = "sell"
HOLD_SIGNAL: Final[str] = "hold"

LONG_POSITION: Final[str] = "long"
SHORT_POSITION: Final[str] = "short"
NO_POSITION: Final[str] = "none"


__all__ = [
    "AQOS_FULL_NAME",
    "AQOS_NAME",
    "BUY_SIGNAL",
    "DEFAULT_ACCOUNT_BALANCE",
    "DEFAULT_MAX_RISK_PERCENT",
    "DEFAULT_MEMORY_IMPORTANCE",
    "DEFAULT_NAMESPACE",
    "DEFAULT_RISK_PERCENT",
    "DEFAULT_SEARCH_LIMIT",
    "DEFAULT_SOURCE",
    "DEFAULT_SYMBOL",
    "DEFAULT_TIMEFRAME",
    "EXPERIMENT_NAMESPACE",
    "HOLD_SIGNAL",
    "LONG_POSITION",
    "MEMORY_NAMESPACE",
    "MESSAGE_NOT_CONFIGURED",
    "MESSAGE_NOT_FOUND",
    "MESSAGE_TRADE_ALLOWED",
    "MODEL_NAMESPACE",
    "NO_POSITION",
    "OHLCV_COLUMNS",
    "PRICE_COLUMNS",
    "RESEARCH_NAMESPACE",
    "SELL_SIGNAL",
    "SHORT_POSITION",
    "STATUS_ERROR",
    "STATUS_OK",
    "VALID_EXPERIMENT_STATUSES",
    "VALID_IMPACTS",
    "VALID_MEMORY_TYPES",
    "VALID_ORDER_STATUSES",
    "VALID_ORDER_TYPES",
    "VALID_POSITION_STATUSES",
    "VALID_SENTIMENTS",
    "VALID_SIDES",
    "VALID_SIGNALS",
    "VALID_TIMEFRAMES",
]