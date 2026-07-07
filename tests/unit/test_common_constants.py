"""
Unit tests for common constants.
"""

from aqos.common import (
    AQOS_FULL_NAME,
    AQOS_NAME,
    BUY_SIGNAL,
    DEFAULT_ACCOUNT_BALANCE,
    DEFAULT_MAX_RISK_PERCENT,
    DEFAULT_MEMORY_IMPORTANCE,
    DEFAULT_NAMESPACE,
    DEFAULT_RISK_PERCENT,
    DEFAULT_SEARCH_LIMIT,
    DEFAULT_SOURCE,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    EXPERIMENT_NAMESPACE,
    HOLD_SIGNAL,
    LONG_POSITION,
    MEMORY_NAMESPACE,
    MESSAGE_NOT_CONFIGURED,
    MESSAGE_NOT_FOUND,
    MESSAGE_TRADE_ALLOWED,
    MODEL_NAMESPACE,
    NO_POSITION,
    OHLCV_COLUMNS,
    PRICE_COLUMNS,
    RESEARCH_NAMESPACE,
    SELL_SIGNAL,
    SHORT_POSITION,
    STATUS_ERROR,
    STATUS_OK,
    VALID_EXPERIMENT_STATUSES,
    VALID_IMPACTS,
    VALID_MEMORY_TYPES,
    VALID_ORDER_STATUSES,
    VALID_ORDER_TYPES,
    VALID_POSITION_STATUSES,
    VALID_SENTIMENTS,
    VALID_SIDES,
    VALID_SIGNALS,
    VALID_TIMEFRAMES,
)


def test_project_constants():
    assert AQOS_NAME == "AQOS"
    assert AQOS_FULL_NAME == "AI Quant Operating System"


def test_default_constants():
    assert DEFAULT_SYMBOL == "XAUUSD"
    assert DEFAULT_TIMEFRAME == "H1"
    assert DEFAULT_SOURCE == "local"
    assert DEFAULT_ACCOUNT_BALANCE == 10_000.0
    assert DEFAULT_RISK_PERCENT == 0.01
    assert DEFAULT_MAX_RISK_PERCENT == 0.02
    assert DEFAULT_MEMORY_IMPORTANCE == 0.5
    assert DEFAULT_SEARCH_LIMIT == 5


def test_valid_signals():
    assert VALID_SIGNALS == (
        "buy",
        "sell",
        "hold",
    )
    assert BUY_SIGNAL in VALID_SIGNALS
    assert SELL_SIGNAL in VALID_SIGNALS
    assert HOLD_SIGNAL in VALID_SIGNALS


def test_valid_sides():
    assert VALID_SIDES == (
        "buy",
        "sell",
    )


def test_valid_order_types():
    assert VALID_ORDER_TYPES == (
        "market",
        "limit",
        "stop",
    )


def test_valid_order_statuses():
    assert VALID_ORDER_STATUSES == (
        "open",
        "filled",
        "cancelled",
    )


def test_valid_position_statuses():
    assert VALID_POSITION_STATUSES == (
        "open",
        "closed",
    )


def test_valid_experiment_statuses():
    assert VALID_EXPERIMENT_STATUSES == (
        "created",
        "running",
        "completed",
        "failed",
    )


def test_valid_sentiments():
    assert VALID_SENTIMENTS == (
        "positive",
        "negative",
        "neutral",
    )


def test_valid_impacts():
    assert VALID_IMPACTS == (
        "low",
        "medium",
        "high",
    )


def test_valid_memory_types():
    assert VALID_MEMORY_TYPES == (
        "observation",
        "pattern",
        "trade",
        "research",
        "strategy",
        "risk",
        "execution",
        "evaluation",
    )


def test_valid_timeframes():
    assert VALID_TIMEFRAMES == (
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


def test_ohlcv_columns():
    assert OHLCV_COLUMNS == (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )


def test_price_columns():
    assert PRICE_COLUMNS == (
        "open",
        "high",
        "low",
        "close",
    )


def test_namespaces():
    assert DEFAULT_NAMESPACE == "default"
    assert RESEARCH_NAMESPACE == "research"
    assert MEMORY_NAMESPACE == "memory"
    assert EXPERIMENT_NAMESPACE == "experiments"
    assert MODEL_NAMESPACE == "models"


def test_status_constants():
    assert STATUS_OK == "ok"
    assert STATUS_ERROR == "error"


def test_message_constants():
    assert MESSAGE_TRADE_ALLOWED == "Trade allowed."
    assert MESSAGE_NOT_CONFIGURED == "Not configured."
    assert MESSAGE_NOT_FOUND == "Record does not exist."


def test_position_constants():
    assert LONG_POSITION == "long"
    assert SHORT_POSITION == "short"
    assert NO_POSITION == "none"