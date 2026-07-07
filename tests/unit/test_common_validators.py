"""
Unit tests for common validators.
"""

import pytest

from aqos.common import (
    validate_account_balance,
    validate_impact,
    validate_memory_type,
    validate_metadata,
    validate_non_empty_dict,
    validate_non_empty_list,
    validate_non_empty_string,
    validate_non_negative_number,
    validate_ohlcv_columns,
    validate_ohlcv_record,
    validate_one_of,
    validate_order_type,
    validate_payload,
    validate_positive_integer,
    validate_positive_number,
    validate_price,
    validate_quantity,
    validate_ratio,
    validate_required_columns,
    validate_required_keys,
    validate_risk_percent,
    validate_sentiment,
    validate_side,
    validate_signal,
    validate_symbol,
    validate_timeframe,
)


def test_validate_non_empty_string():
    assert validate_non_empty_string(" XAUUSD ", "Symbol") == "XAUUSD"


def test_validate_non_empty_string_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_non_empty_string(123, "Symbol")


def test_validate_non_empty_string_rejects_empty_string():
    with pytest.raises(ValueError):
        validate_non_empty_string(" ", "Symbol")


def test_validate_non_empty_list():
    assert validate_non_empty_list([1], "Values") == [1]


def test_validate_non_empty_list_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_non_empty_list("invalid", "Values")


def test_validate_non_empty_list_rejects_empty_list():
    with pytest.raises(ValueError):
        validate_non_empty_list([], "Values")


def test_validate_non_empty_dict():
    assert validate_non_empty_dict({"a": 1}, "Payload") == {"a": 1}


def test_validate_non_empty_dict_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_non_empty_dict("invalid", "Payload")


def test_validate_non_empty_dict_rejects_empty_dict():
    with pytest.raises(ValueError):
        validate_non_empty_dict({}, "Payload")


def test_validate_payload():
    assert validate_payload({"symbol": "XAUUSD"}) == {"symbol": "XAUUSD"}


def test_validate_payload_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_payload("invalid")


def test_validate_metadata():
    assert validate_metadata({"request_id": "req-1"}) == {"request_id": "req-1"}


def test_validate_metadata_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_metadata("invalid")


def test_validate_positive_number():
    assert validate_positive_number(10, "Value") == 10.0


def test_validate_positive_number_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_positive_number("10", "Value")


def test_validate_positive_number_rejects_zero():
    with pytest.raises(ValueError):
        validate_positive_number(0, "Value")


def test_validate_non_negative_number():
    assert validate_non_negative_number(0, "Value") == 0.0
    assert validate_non_negative_number(10, "Value") == 10.0


def test_validate_non_negative_number_rejects_negative():
    with pytest.raises(ValueError):
        validate_non_negative_number(-1, "Value")


def test_validate_positive_integer():
    assert validate_positive_integer(5, "Limit") == 5


def test_validate_positive_integer_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_positive_integer(1.5, "Limit")


def test_validate_positive_integer_rejects_zero():
    with pytest.raises(ValueError):
        validate_positive_integer(0, "Limit")


def test_validate_ratio():
    assert validate_ratio(0, "Score") == 0.0
    assert validate_ratio(0.5, "Score") == 0.5
    assert validate_ratio(1, "Score") == 1.0


def test_validate_ratio_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_ratio("0.5", "Score")


def test_validate_ratio_rejects_out_of_range():
    with pytest.raises(ValueError):
        validate_ratio(1.1, "Score")


def test_validate_one_of():
    assert validate_one_of(" BUY ", ("buy", "sell"), "Side") == "buy"


def test_validate_one_of_rejects_invalid_value():
    with pytest.raises(ValueError):
        validate_one_of("hold", ("buy", "sell"), "Side")


def test_validate_required_keys():
    validate_required_keys(
        data={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        required_keys=[
            "symbol",
            "timeframe",
        ],
        name="Request",
    )


def test_validate_required_keys_rejects_invalid_data_type():
    with pytest.raises(TypeError):
        validate_required_keys(
            data="invalid",
            required_keys=[
                "symbol",
            ],
            name="Request",
        )


def test_validate_required_keys_rejects_missing_keys():
    with pytest.raises(ValueError):
        validate_required_keys(
            data={
                "symbol": "XAUUSD",
            },
            required_keys=[
                "symbol",
                "timeframe",
            ],
            name="Request",
        )


def test_validate_required_columns():
    validate_required_columns(
        columns=[
            "timestamp",
            "open",
            "close",
        ],
        required_columns=[
            "timestamp",
            "open",
        ],
    )


def test_validate_required_columns_rejects_missing_columns():
    with pytest.raises(ValueError):
        validate_required_columns(
            columns=[
                "timestamp",
                "open",
            ],
            required_columns=[
                "timestamp",
                "open",
                "close",
            ],
        )


def test_validate_ohlcv_columns():
    validate_ohlcv_columns(
        [
            "timestamp",
            "open",
            "high",
            "low",
            "close",
            "volume",
        ]
    )


def test_validate_ohlcv_columns_rejects_missing_columns():
    with pytest.raises(ValueError):
        validate_ohlcv_columns(
            [
                "timestamp",
                "open",
                "close",
            ]
        )


def test_validate_symbol():
    assert validate_symbol(" xauusd ") == "XAUUSD"


def test_validate_symbol_rejects_empty_symbol():
    with pytest.raises(ValueError):
        validate_symbol("")


def test_validate_timeframe():
    assert validate_timeframe(" h1 ") == "H1"


def test_validate_timeframe_rejects_invalid_timeframe():
    with pytest.raises(ValueError):
        validate_timeframe("H2")


def test_validate_signal():
    assert validate_signal(" BUY ") == "buy"
    assert validate_signal("sell") == "sell"
    assert validate_signal("hold") == "hold"


def test_validate_signal_rejects_invalid_signal():
    with pytest.raises(ValueError):
        validate_signal("invalid")


def test_validate_side():
    assert validate_side(" BUY ") == "buy"
    assert validate_side("sell") == "sell"


def test_validate_side_rejects_invalid_side():
    with pytest.raises(ValueError):
        validate_side("hold")


def test_validate_order_type():
    assert validate_order_type(" MARKET ") == "market"
    assert validate_order_type("limit") == "limit"
    assert validate_order_type("stop") == "stop"


def test_validate_order_type_rejects_invalid_order_type():
    with pytest.raises(ValueError):
        validate_order_type("invalid")


def test_validate_sentiment():
    assert validate_sentiment(" POSITIVE ") == "positive"
    assert validate_sentiment("negative") == "negative"
    assert validate_sentiment("neutral") == "neutral"


def test_validate_sentiment_rejects_invalid_sentiment():
    with pytest.raises(ValueError):
        validate_sentiment("mixed")


def test_validate_impact():
    assert validate_impact(" HIGH ") == "high"
    assert validate_impact("medium") == "medium"
    assert validate_impact("low") == "low"


def test_validate_impact_rejects_invalid_impact():
    with pytest.raises(ValueError):
        validate_impact("critical")


def test_validate_memory_type():
    assert validate_memory_type(" RESEARCH ") == "research"
    assert validate_memory_type("trade") == "trade"


def test_validate_memory_type_rejects_invalid_memory_type():
    with pytest.raises(ValueError):
        validate_memory_type("invalid")


def test_validate_account_balance():
    assert validate_account_balance(10_000) == 10_000.0


def test_validate_account_balance_rejects_zero():
    with pytest.raises(ValueError):
        validate_account_balance(0)


def test_validate_risk_percent():
    assert validate_risk_percent(0.01) == 0.01


def test_validate_risk_percent_rejects_zero():
    with pytest.raises(ValueError):
        validate_risk_percent(0)


def test_validate_risk_percent_rejects_over_one():
    with pytest.raises(ValueError):
        validate_risk_percent(1.1)


def test_validate_price():
    assert validate_price(2000, "Entry price") == 2000.0


def test_validate_price_rejects_zero():
    with pytest.raises(ValueError):
        validate_price(0, "Entry price")


def test_validate_quantity():
    assert validate_quantity(10) == 10.0


def test_validate_quantity_rejects_zero():
    with pytest.raises(ValueError):
        validate_quantity(0)


def test_validate_ohlcv_record():
    record = {
        "timestamp": "2026-01-01",
        "open": 2000.0,
        "high": 2010.0,
        "low": 1990.0,
        "close": 2005.0,
        "volume": 1000.0,
    }

    assert validate_ohlcv_record(record) == record


def test_validate_ohlcv_record_rejects_missing_key():
    record = {
        "timestamp": "2026-01-01",
        "open": 2000.0,
        "high": 2010.0,
        "low": 1990.0,
        "close": 2005.0,
    }

    with pytest.raises(ValueError):
        validate_ohlcv_record(record)


def test_validate_ohlcv_record_rejects_invalid_price():
    record = {
        "timestamp": "2026-01-01",
        "open": 0,
        "high": 2010.0,
        "low": 1990.0,
        "close": 2005.0,
        "volume": 1000.0,
    }

    with pytest.raises(ValueError):
        validate_ohlcv_record(record)


def test_validate_ohlcv_record_rejects_invalid_volume():
    record = {
        "timestamp": "2026-01-01",
        "open": 2000.0,
        "high": 2010.0,
        "low": 1990.0,
        "close": 2005.0,
        "volume": -1,
    }

    with pytest.raises(ValueError):
        validate_ohlcv_record(record)