"""
Unit tests for common ID helpers.
"""

from datetime import UTC, datetime

import pytest

from aqos.common import (
    ID_SEPARATOR,
    build_compound_id,
    build_timestamp_id,
    ensure_unique_id,
    generate_prefixed_id,
    generate_short_id,
    generate_uuid,
    is_valid_id,
    normalize_id,
    normalize_id_part,
    validate_id,
    validate_prefix,
    validate_separator,
)


def test_id_separator():
    assert ID_SEPARATOR == "-"


def test_generate_uuid():
    value = generate_uuid()

    assert isinstance(value, str)
    assert len(value) == 32
    assert value.isalnum()


def test_generate_short_id_default_length():
    value = generate_short_id()

    assert isinstance(value, str)
    assert len(value) == 8


def test_generate_short_id_custom_length():
    value = generate_short_id(length=12)

    assert isinstance(value, str)
    assert len(value) == 12


def test_generate_short_id_from_source():
    value = generate_short_id(
        length=6,
        source="XAUUSD Bullish Breakout",
    )

    assert value == "xauusd"


def test_generate_short_id_source_shorter_than_length():
    value = generate_short_id(
        length=20,
        source="XAUUSD",
    )

    assert value == "xauusd"


def test_generate_short_id_rejects_invalid_length():
    with pytest.raises(ValueError):
        generate_short_id(length=0)


def test_generate_prefixed_id_with_unique_value():
    value = generate_prefixed_id(
        prefix="order",
        unique_value="123",
    )

    assert value == "order-123"


def test_generate_prefixed_id_normalizes_values():
    value = generate_prefixed_id(
        prefix="Trade Order",
        unique_value="XAUUSD BUY",
    )

    assert value == "trade-order-xauusd-buy"


def test_generate_prefixed_id_with_custom_separator():
    value = generate_prefixed_id(
        prefix="order",
        unique_value="123",
        separator="_",
    )

    assert value == "order_123"


def test_generate_prefixed_id_without_unique_value():
    value = generate_prefixed_id("order")

    assert value.startswith("order-")
    assert len(value) > len("order-")


def test_build_compound_id():
    value = build_compound_id(
        "XAUUSD",
        "H1",
        "Bullish Breakout",
    )

    assert value == "xauusd-h1-bullish-breakout"


def test_build_compound_id_with_custom_separator():
    value = build_compound_id(
        "XAUUSD",
        "H1",
        "Signal",
        separator=":",
    )

    assert value == "xauusd:h1:signal"


def test_build_compound_id_rejects_empty_parts():
    with pytest.raises(ValueError):
        build_compound_id()


def test_build_timestamp_id_with_timestamp():
    timestamp = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )

    value = build_timestamp_id(
        prefix="run",
        timestamp=timestamp,
    )

    assert value == "run-20260102030405"


def test_build_timestamp_id_without_timestamp():
    value = build_timestamp_id("run")

    assert value.startswith("run-")
    assert len(value) == len("run-") + 14


def test_build_timestamp_id_rejects_invalid_timestamp():
    with pytest.raises(TypeError):
        build_timestamp_id(
            prefix="run",
            timestamp="invalid",
        )


def test_normalize_id_part():
    assert normalize_id_part(" XAUUSD Bullish Breakout ") == "xauusd-bullish-breakout"


def test_normalize_id_part_removes_special_characters():
    assert normalize_id_part("XAUUSD/@Bullish///Breakout!") == "xauusd-bullish-breakout"


def test_normalize_id_part_rejects_empty_value():
    with pytest.raises(ValueError):
        normalize_id_part("")


def test_normalize_id_part_rejects_value_empty_after_normalization():
    with pytest.raises(ValueError):
        normalize_id_part("!!!")


def test_normalize_id():
    assert normalize_id(" Trade Signal 001 ") == "trade-signal-001"


def test_validate_id():
    assert validate_id("order-1") == "order-1"
    assert validate_id("order_1") == "order_1"


def test_validate_id_rejects_empty_value():
    with pytest.raises(ValueError):
        validate_id("")


def test_validate_id_rejects_invalid_characters():
    with pytest.raises(ValueError):
        validate_id("order/1")


def test_validate_id_rejects_invalid_start():
    with pytest.raises(ValueError):
        validate_id("-order-1")


def test_validate_prefix():
    assert validate_prefix(" Trade Order ") == "trade-order"


def test_validate_separator():
    assert validate_separator("-") == "-"
    assert validate_separator("_") == "_"
    assert validate_separator(":") == ":"
    assert validate_separator(".") == "."


def test_validate_separator_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_separator(1)


def test_validate_separator_rejects_invalid_value():
    with pytest.raises(ValueError):
        validate_separator("/")


def test_ensure_unique_id_when_candidate_is_unique():
    existing_ids = {
        "order-1",
    }

    value = ensure_unique_id(
        candidate_id="order-2",
        existing_ids=existing_ids,
    )

    assert value == "order-2"


def test_ensure_unique_id_when_candidate_exists():
    existing_ids = {
        "order-1",
        "order-1-2",
    }

    value = ensure_unique_id(
        candidate_id="order-1",
        existing_ids=existing_ids,
    )

    assert value == "order-1-3"


def test_ensure_unique_id_normalizes_candidate():
    existing_ids = {
        "order-1",
    }

    value = ensure_unique_id(
        candidate_id="Order 1",
        existing_ids=existing_ids,
    )

    assert value == "order-1-2"


def test_ensure_unique_id_rejects_invalid_existing_ids_type():
    with pytest.raises(TypeError):
        ensure_unique_id(
            candidate_id="order-1",
            existing_ids=["order-1"],
        )


def test_is_valid_id_true():
    assert is_valid_id("order-1") is True
    assert is_valid_id("order_1") is True


def test_is_valid_id_false():
    assert is_valid_id("order/1") is False
    assert is_valid_id("") is False