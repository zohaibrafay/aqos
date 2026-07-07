"""
Common validators.

Defines reusable validation helpers used across AQOS modules.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from aqos.common.constants import (
    OHLCV_COLUMNS,
    VALID_IMPACTS,
    VALID_MEMORY_TYPES,
    VALID_ORDER_TYPES,
    VALID_SENTIMENTS,
    VALID_SIDES,
    VALID_SIGNALS,
    VALID_TIMEFRAMES,
)


def validate_non_empty_string(
    value: str,
    name: str,
) -> str:
    """
    Validate a non-empty string and return the stripped value.
    """

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{name} cannot be empty.")

    return normalized


def validate_non_empty_list(
    value: list,
    name: str,
) -> list:
    """
    Validate a non-empty list.
    """

    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list.")

    if not value:
        raise ValueError(f"{name} cannot be empty.")

    return value


def validate_non_empty_dict(
    value: dict,
    name: str,
) -> dict:
    """
    Validate a non-empty dictionary.
    """

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dictionary.")

    if not value:
        raise ValueError(f"{name} cannot be empty.")

    return value


def validate_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate payload dictionary.
    """

    if not isinstance(payload, dict):
        raise TypeError("Payload must be a dictionary.")

    return payload


def validate_metadata(
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate metadata dictionary.
    """

    if not isinstance(metadata, dict):
        raise TypeError("Metadata must be a dictionary.")

    return metadata


def validate_positive_number(
    value: int | float,
    name: str,
) -> float:
    """
    Validate a positive number.
    """

    if not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric.")

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return float(value)


def validate_non_negative_number(
    value: int | float,
    name: str,
) -> float:
    """
    Validate a non-negative number.
    """

    if not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric.")

    if value < 0:
        raise ValueError(f"{name} cannot be negative.")

    return float(value)


def validate_positive_integer(
    value: int,
    name: str,
) -> int:
    """
    Validate a positive integer.
    """

    if not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


def validate_ratio(
    value: int | float,
    name: str,
) -> float:
    """
    Validate a ratio between 0 and 1.
    """

    if not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric.")

    if value < 0 or value > 1:
        raise ValueError(f"{name} must be between 0 and 1.")

    return float(value)


def validate_one_of(
    value: str,
    allowed_values: Iterable[str],
    name: str,
) -> str:
    """
    Validate that a string is one of the allowed values.

    Returns the lowercase normalized value.
    """

    normalized = validate_non_empty_string(value, name).lower()

    allowed = tuple(allowed_values)

    if normalized not in allowed:
        allowed_text = ", ".join(allowed)
        raise ValueError(f"{name} must be one of: {allowed_text}.")

    return normalized


def validate_required_keys(
    data: dict[str, Any],
    required_keys: Iterable[str],
    name: str,
) -> None:
    """
    Validate that a dictionary contains required keys.
    """

    if not isinstance(data, dict):
        raise TypeError(f"{name} must be a dictionary.")

    missing_keys = sorted(
        key
        for key in required_keys
        if key not in data
    )

    if missing_keys:
        raise ValueError(f"{name} is missing required keys: {missing_keys}")


def validate_required_columns(
    columns: Iterable[str],
    required_columns: Iterable[str],
    name: str = "Columns",
) -> None:
    """
    Validate that columns include required columns.
    """

    available_columns = set(columns)
    missing_columns = sorted(
        set(required_columns).difference(available_columns)
    )

    if missing_columns:
        raise ValueError(f"{name} is missing required columns: {missing_columns}")


def validate_ohlcv_columns(
    columns: Iterable[str],
) -> None:
    """
    Validate OHLCV columns.
    """

    validate_required_columns(
        columns=columns,
        required_columns=OHLCV_COLUMNS,
        name="OHLCV data",
    )


def validate_symbol(
    symbol: str,
) -> str:
    """
    Validate and normalize symbol.
    """

    return validate_non_empty_string(symbol, "Symbol").upper()


def validate_timeframe(
    timeframe: str,
) -> str:
    """
    Validate and normalize timeframe.
    """

    normalized = validate_non_empty_string(timeframe, "Timeframe").upper()

    if normalized not in VALID_TIMEFRAMES:
        allowed_text = ", ".join(VALID_TIMEFRAMES)
        raise ValueError(f"Timeframe must be one of: {allowed_text}.")

    return normalized


def validate_signal(
    signal: str,
) -> str:
    """
    Validate and normalize strategy signal.
    """

    return validate_one_of(
        value=signal,
        allowed_values=VALID_SIGNALS,
        name="Signal",
    )


def validate_side(
    side: str,
) -> str:
    """
    Validate and normalize trade side.
    """

    return validate_one_of(
        value=side,
        allowed_values=VALID_SIDES,
        name="Side",
    )


def validate_order_type(
    order_type: str,
) -> str:
    """
    Validate and normalize order type.
    """

    return validate_one_of(
        value=order_type,
        allowed_values=VALID_ORDER_TYPES,
        name="Order type",
    )


def validate_sentiment(
    sentiment: str,
) -> str:
    """
    Validate and normalize sentiment.
    """

    return validate_one_of(
        value=sentiment,
        allowed_values=VALID_SENTIMENTS,
        name="Sentiment",
    )


def validate_impact(
    impact: str,
) -> str:
    """
    Validate and normalize impact.
    """

    return validate_one_of(
        value=impact,
        allowed_values=VALID_IMPACTS,
        name="Impact",
    )


def validate_memory_type(
    memory_type: str,
) -> str:
    """
    Validate and normalize memory type.
    """

    return validate_one_of(
        value=memory_type,
        allowed_values=VALID_MEMORY_TYPES,
        name="Memory type",
    )


def validate_account_balance(
    account_balance: int | float,
) -> float:
    """
    Validate account balance.
    """

    return validate_positive_number(
        value=account_balance,
        name="Account balance",
    )


def validate_risk_percent(
    risk_percent: int | float,
) -> float:
    """
    Validate risk percent.
    """

    value = validate_ratio(
        value=risk_percent,
        name="Risk percent",
    )

    if value == 0:
        raise ValueError("Risk percent must be greater than zero.")

    return value


def validate_price(
    price: int | float,
    name: str = "Price",
) -> float:
    """
    Validate price.
    """

    return validate_positive_number(
        value=price,
        name=name,
    )


def validate_quantity(
    quantity: int | float,
) -> float:
    """
    Validate quantity.
    """

    return validate_positive_number(
        value=quantity,
        name="Quantity",
    )


def validate_ohlcv_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate a single OHLCV record.
    """

    validate_required_keys(
        data=record,
        required_keys=OHLCV_COLUMNS,
        name="OHLCV record",
    )

    validate_non_empty_string(
        value=str(record["timestamp"]),
        name="Timestamp",
    )

    validate_price(record["open"], "Open price")
    validate_price(record["high"], "High price")
    validate_price(record["low"], "Low price")
    validate_price(record["close"], "Close price")
    validate_non_negative_number(record["volume"], "Volume")

    return record


__all__ = [
    "validate_account_balance",
    "validate_impact",
    "validate_memory_type",
    "validate_metadata",
    "validate_non_empty_dict",
    "validate_non_empty_list",
    "validate_non_empty_string",
    "validate_non_negative_number",
    "validate_ohlcv_columns",
    "validate_ohlcv_record",
    "validate_one_of",
    "validate_order_type",
    "validate_payload",
    "validate_positive_integer",
    "validate_positive_number",
    "validate_price",
    "validate_quantity",
    "validate_ratio",
    "validate_required_columns",
    "validate_required_keys",
    "validate_risk_percent",
    "validate_sentiment",
    "validate_side",
    "validate_signal",
    "validate_symbol",
    "validate_timeframe",
]