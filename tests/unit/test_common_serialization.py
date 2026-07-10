"""
Unit tests for common serialization helpers.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pytest

from aqos.common import (
    compact_dict,
    deep_merge_dicts,
    flatten_dict,
    from_json,
    merge_dicts,
    remove_none_values,
    safe_get,
    serialize_dict,
    serialize_list,
    to_json,
    to_serializable,
    unflatten_dict,
)


class SampleEnum(Enum):
    BUY = "buy"


@dataclass
class SampleRecord:
    symbol: str
    price: float


class DictLike:
    def to_dict(self):
        return {
            "symbol": "XAUUSD",
            "price": 2000.0,
        }


class ObjectLike:
    def __init__(self):
        self.symbol = "XAUUSD"
        self.price = 2000.0


def test_to_serializable_none():
    assert to_serializable(None) is None


def test_to_serializable_primitives():
    assert to_serializable("XAUUSD") == "XAUUSD"
    assert to_serializable(1) == 1
    assert to_serializable(1.5) == 1.5
    assert to_serializable(True) is True


def test_to_serializable_decimal():
    assert to_serializable(Decimal("10.5")) == 10.5


def test_to_serializable_datetime():
    value = datetime(
        2026,
        1,
        2,
        3,
        4,
        5,
        tzinfo=UTC,
    )

    assert to_serializable(value) == "2026-01-02T03:04:05+00:00"


def test_to_serializable_date():
    value = date(2026, 1, 2)

    assert to_serializable(value) == "2026-01-02"


def test_to_serializable_enum():
    assert to_serializable(SampleEnum.BUY) == "buy"


def test_to_serializable_path():
    assert to_serializable(Path("data/file.json")) == "data/file.json"


def test_to_serializable_dataclass():
    record = SampleRecord(
        symbol="XAUUSD",
        price=2000.0,
    )

    assert to_serializable(record) == {
        "symbol": "XAUUSD",
        "price": 2000.0,
    }


def test_to_serializable_dict():
    value = {
        "symbol": "XAUUSD",
        "created_at": datetime(
            2026,
            1,
            2,
            3,
            4,
            5,
            tzinfo=UTC,
        ),
    }

    assert to_serializable(value) == {
        "symbol": "XAUUSD",
        "created_at": "2026-01-02T03:04:05+00:00",
    }


def test_to_serializable_list():
    value = [
        Decimal("1.5"),
        date(2026, 1, 2),
    ]

    assert to_serializable(value) == [
        1.5,
        "2026-01-02",
    ]


def test_to_serializable_tuple():
    value = (
        "XAUUSD",
        Decimal("1.5"),
    )

    assert to_serializable(value) == [
        "XAUUSD",
        1.5,
    ]


def test_to_serializable_set():
    value = {
        "sell",
        "buy",
    }

    assert to_serializable(value) == [
        "buy",
        "sell",
    ]


def test_to_serializable_dict_like():
    value = DictLike()

    assert to_serializable(value) == {
        "symbol": "XAUUSD",
        "price": 2000.0,
    }


def test_to_serializable_object_like():
    value = ObjectLike()

    assert to_serializable(value) == {
        "symbol": "XAUUSD",
        "price": 2000.0,
    }


def test_serialize_dict():
    value = {
        "symbol": "XAUUSD",
        "price": Decimal("2000.5"),
    }

    assert serialize_dict(value) == {
        "symbol": "XAUUSD",
        "price": 2000.5,
    }


def test_serialize_dict_converts_keys_to_string():
    value = {
        1: "one",
    }

    assert serialize_dict(value) == {
        "1": "one",
    }


def test_serialize_dict_rejects_invalid_type():
    with pytest.raises(TypeError):
        serialize_dict("invalid")


def test_serialize_list():
    value = [
        Decimal("1.5"),
        date(2026, 1, 2),
    ]

    assert serialize_list(value) == [
        1.5,
        "2026-01-02",
    ]


def test_serialize_list_rejects_invalid_type():
    with pytest.raises(TypeError):
        serialize_list("invalid")


def test_to_json():
    value = {
        "symbol": "XAUUSD",
        "price": Decimal("2000.5"),
    }

    assert to_json(value) == '{"price": 2000.5, "symbol": "XAUUSD"}'


def test_to_json_with_indent():
    value = {
        "symbol": "XAUUSD",
    }

    assert to_json(value, indent=2) == '{\n  "symbol": "XAUUSD"\n}'


def test_from_json():
    assert from_json('{"symbol": "XAUUSD"}') == {
        "symbol": "XAUUSD",
    }


def test_from_json_rejects_invalid_type():
    with pytest.raises(TypeError):
        from_json(123)


def test_from_json_rejects_empty_string():
    with pytest.raises(ValueError):
        from_json("")


def test_safe_get_existing_key():
    assert safe_get(
        data={
            "symbol": "XAUUSD",
        },
        key="symbol",
    ) == "XAUUSD"


def test_safe_get_missing_key():
    assert safe_get(
        data={},
        key="symbol",
        default="UNKNOWN",
    ) == "UNKNOWN"


def test_safe_get_rejects_invalid_data_type():
    with pytest.raises(TypeError):
        safe_get(
            data="invalid",
            key="symbol",
        )


def test_safe_get_rejects_invalid_key_type():
    with pytest.raises(TypeError):
        safe_get(
            data={},
            key=123,
        )


def test_remove_none_values():
    value = {
        "symbol": "XAUUSD",
        "price": None,
    }

    assert remove_none_values(value) == {
        "symbol": "XAUUSD",
    }


def test_remove_none_values_rejects_invalid_type():
    with pytest.raises(TypeError):
        remove_none_values("invalid")


def test_compact_dict():
    value = {
        "symbol": "XAUUSD",
        "none": None,
        "empty_string": "",
        "empty_list": [],
        "empty_dict": {},
        "empty_tuple": (),
        "empty_set": set(),
        "zero": 0,
        "false": False,
    }

    assert compact_dict(value) == {
        "symbol": "XAUUSD",
        "zero": 0,
        "false": False,
    }


def test_compact_dict_rejects_invalid_type():
    with pytest.raises(TypeError):
        compact_dict("invalid")


def test_flatten_dict():
    value = {
        "market": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        "signal": "buy",
    }

    assert flatten_dict(value) == {
        "market.symbol": "XAUUSD",
        "market.timeframe": "H1",
        "signal": "buy",
    }


def test_flatten_dict_with_custom_separator():
    value = {
        "market": {
            "symbol": "XAUUSD",
        },
    }

    assert flatten_dict(value, separator="_") == {
        "market_symbol": "XAUUSD",
    }


def test_flatten_dict_rejects_invalid_data_type():
    with pytest.raises(TypeError):
        flatten_dict("invalid")


def test_flatten_dict_rejects_invalid_parent_key_type():
    with pytest.raises(TypeError):
        flatten_dict({}, parent_key=123)


def test_flatten_dict_rejects_invalid_separator_type():
    with pytest.raises(TypeError):
        flatten_dict({}, separator=123)


def test_unflatten_dict():
    value = {
        "market.symbol": "XAUUSD",
        "market.timeframe": "H1",
        "signal": "buy",
    }

    assert unflatten_dict(value) == {
        "market": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        "signal": "buy",
    }


def test_unflatten_dict_with_custom_separator():
    value = {
        "market_symbol": "XAUUSD",
    }

    assert unflatten_dict(value, separator="_") == {
        "market": {
            "symbol": "XAUUSD",
        },
    }


def test_unflatten_dict_rejects_invalid_data_type():
    with pytest.raises(TypeError):
        unflatten_dict("invalid")


def test_unflatten_dict_rejects_invalid_separator_type():
    with pytest.raises(TypeError):
        unflatten_dict({}, separator=123)


def test_merge_dicts():
    assert merge_dicts(
        {
            "symbol": "XAUUSD",
        },
        {
            "timeframe": "H1",
        },
    ) == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }


def test_merge_dicts_right_wins():
    assert merge_dicts(
        {
            "symbol": "EURUSD",
        },
        {
            "symbol": "XAUUSD",
        },
    ) == {
        "symbol": "XAUUSD",
    }


def test_merge_dicts_rejects_invalid_type():
    with pytest.raises(TypeError):
        merge_dicts(
            {
                "symbol": "XAUUSD",
            },
            "invalid",
        )


def test_deep_merge_dicts():
    base = {
        "market": {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        "signal": "buy",
    }
    override = {
        "market": {
            "timeframe": "H4",
        },
        "risk": {
            "percent": 0.01,
        },
    }

    assert deep_merge_dicts(base, override) == {
        "market": {
            "symbol": "XAUUSD",
            "timeframe": "H4",
        },
        "signal": "buy",
        "risk": {
            "percent": 0.01,
        },
    }


def test_deep_merge_dicts_rejects_invalid_base_type():
    with pytest.raises(TypeError):
        deep_merge_dicts(
            "invalid",
            {},
        )


def test_deep_merge_dicts_rejects_invalid_override_type():
    with pytest.raises(TypeError):
        deep_merge_dicts(
            {},
            "invalid",
        )