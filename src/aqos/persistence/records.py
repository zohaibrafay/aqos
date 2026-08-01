from __future__ import annotations

import json
import re
from typing import Any

from aqos.common.id_helpers import generate_uuid
from aqos.common.time_utils import utc_now_iso


AQOS_RECORDS_VERSION = "1.0"

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def record_utc_now() -> str:
    return utc_now_iso()


def build_record_id(prefix: str) -> str:
    clean_prefix = prefix.strip().lower()

    if not clean_prefix:
        raise ValueError("Record id prefix cannot be empty.")

    return f"{clean_prefix}_{generate_uuid()}"


def encode_json_field(value: dict[str, Any] | None) -> str:
    if value is None:
        return "{}"

    if not isinstance(value, dict):
        raise ValueError("JSON record fields must be dictionaries.")

    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def decode_json_field(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}

    if isinstance(value, dict):
        return value

    decoded = json.loads(str(value))

    if not isinstance(decoded, dict):
        raise ValueError("JSON record fields must decode to dictionaries.")

    return decoded


def encode_string_list(values: tuple[str, ...] | list[str] | None) -> str:
    if not values:
        return "[]"

    return json.dumps([str(value) for value in values], separators=(",", ":"))


def decode_string_list(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()

    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)

    decoded = json.loads(str(value))

    if not isinstance(decoded, list):
        raise ValueError("String list record fields must decode to lists.")

    return tuple(str(item) for item in decoded)


def encode_bool(value: bool) -> int:
    return 1 if value else 0


def decode_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if value in (None, ""):
        return False

    return bool(int(value))


def normalize_email(value: str) -> str:
    email = value.strip().lower()

    if not email:
        raise ValueError("email cannot be empty.")

    if not EMAIL_PATTERN.match(email):
        raise ValueError(f"email is not valid: {value}")

    return email


def normalize_required_text(value: str, field_name: str) -> str:
    text = value.strip()

    if not text:
        raise ValueError(f"{field_name} cannot be empty.")

    return text


def normalize_symbol(value: str) -> str:
    symbol = re.sub(r"\s+", "", value).upper()

    if not symbol:
        raise ValueError("symbol cannot be empty.")

    return symbol


def apply_optional_updates(
    current: dict[str, Any],
    updates: dict[str, Any],
) -> dict[str, Any]:
    """
    Return ``current`` merged with every non-``None`` entry of ``updates``.
    """

    merged = dict(current)

    for key, value in updates.items():
        if value is None:
            continue

        merged[key] = value

    return merged


__all__ = [
    "AQOS_RECORDS_VERSION",
    "EMAIL_PATTERN",
    "apply_optional_updates",
    "build_record_id",
    "decode_bool",
    "decode_json_field",
    "decode_string_list",
    "encode_bool",
    "encode_json_field",
    "encode_string_list",
    "normalize_email",
    "normalize_required_text",
    "normalize_symbol",
    "record_utc_now",
]
