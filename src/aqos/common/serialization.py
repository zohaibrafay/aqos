"""
Common serialization helpers.

Defines reusable helpers for converting AQOS objects into JSON-safe
dictionaries, lists, strings, and primitive values.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any


def to_serializable(
    value: Any,
) -> Any:
    """
    Convert a value into a JSON-safe value.
    """

    if value is None:
        return None

    if isinstance(value, str | int | float | bool):
        return value

    if isinstance(value, Decimal):
        return float(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Enum):
        return value.value

    if isinstance(value, Path):
        return value.as_posix()

    if is_dataclass(value):
        return to_serializable(asdict(value))

    if isinstance(value, dict):
        return serialize_dict(value)

    if isinstance(value, list):
        return serialize_list(value)

    if isinstance(value, tuple):
        return serialize_list(list(value))

    if isinstance(value, set):
        return serialize_list(sorted(value))

    if hasattr(value, "to_dict") and callable(value.to_dict):
        return to_serializable(value.to_dict())

    if hasattr(value, "__dict__"):
        return serialize_dict(value.__dict__)

    return str(value)


def serialize_dict(
    value: dict[Any, Any],
) -> dict[str, Any]:
    """
    Serialize dictionary keys and values.
    """

    if not isinstance(value, dict):
        raise TypeError("Value must be a dictionary.")

    serialized: dict[str, Any] = {}

    for key, item in value.items():
        serialized[str(key)] = to_serializable(item)

    return serialized


def serialize_list(
    value: list[Any],
) -> list[Any]:
    """
    Serialize list values.
    """

    if not isinstance(value, list):
        raise TypeError("Value must be a list.")

    return [
        to_serializable(item)
        for item in value
    ]


def to_json(
    value: Any,
    indent: int | None = None,
    sort_keys: bool = True,
) -> str:
    """
    Convert value to JSON string.
    """

    return json.dumps(
        to_serializable(value),
        indent=indent,
        sort_keys=sort_keys,
    )


def from_json(
    value: str,
) -> Any:
    """
    Parse JSON string.
    """

    if not isinstance(value, str):
        raise TypeError("JSON value must be a string.")

    if not value.strip():
        raise ValueError("JSON value cannot be empty.")

    return json.loads(value)


def safe_get(
    data: dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    """
    Safely get a value from a dictionary.
    """

    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary.")

    if not isinstance(key, str):
        raise TypeError("Key must be a string.")

    return data.get(key, default)


def remove_none_values(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Remove keys with None values from a dictionary.
    """

    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary.")

    return {
        key: value
        for key, value in data.items()
        if value is not None
    }


def compact_dict(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Remove empty values from a dictionary.

    Removes:
    - None
    - empty strings
    - empty lists
    - empty dictionaries
    - empty tuples
    - empty sets
    """

    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary.")

    return {
        key: value
        for key, value in data.items()
        if value not in (None, "", [], {}, (), set())
    }


def flatten_dict(
    data: dict[str, Any],
    parent_key: str = "",
    separator: str = ".",
) -> dict[str, Any]:
    """
    Flatten nested dictionary keys.
    """

    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary.")

    if not isinstance(parent_key, str):
        raise TypeError("Parent key must be a string.")

    if not isinstance(separator, str):
        raise TypeError("Separator must be a string.")

    flattened: dict[str, Any] = {}

    for key, value in data.items():
        new_key = f"{parent_key}{separator}{key}" if parent_key else str(key)

        if isinstance(value, dict):
            flattened.update(
                flatten_dict(
                    data=value,
                    parent_key=new_key,
                    separator=separator,
                )
            )
        else:
            flattened[new_key] = value

    return flattened


def unflatten_dict(
    data: dict[str, Any],
    separator: str = ".",
) -> dict[str, Any]:
    """
    Convert flattened dictionary keys into nested dictionaries.
    """

    if not isinstance(data, dict):
        raise TypeError("Data must be a dictionary.")

    if not isinstance(separator, str):
        raise TypeError("Separator must be a string.")

    result: dict[str, Any] = {}

    for key, value in data.items():
        parts = str(key).split(separator)
        current = result

        for part in parts[:-1]:
            current = current.setdefault(part, {})

        current[parts[-1]] = value

    return result


def merge_dicts(
    *dicts: dict[str, Any],
) -> dict[str, Any]:
    """
    Merge dictionaries from left to right.
    """

    merged: dict[str, Any] = {}

    for data in dicts:
        if not isinstance(data, dict):
            raise TypeError("All values must be dictionaries.")

        merged.update(data)

    return merged


def deep_merge_dicts(
    base: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    """
    Recursively merge two dictionaries.
    """

    if not isinstance(base, dict):
        raise TypeError("Base must be a dictionary.")

    if not isinstance(override, dict):
        raise TypeError("Override must be a dictionary.")

    result = dict(base)

    for key, value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


__all__ = [
    "compact_dict",
    "deep_merge_dicts",
    "flatten_dict",
    "from_json",
    "merge_dicts",
    "remove_none_values",
    "safe_get",
    "serialize_dict",
    "serialize_list",
    "to_json",
    "to_serializable",
    "unflatten_dict",
]