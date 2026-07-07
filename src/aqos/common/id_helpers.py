"""
Common ID helpers.

Defines reusable helpers for generating, normalizing, and validating
identifier strings across AQOS modules.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from aqos.common.validators import (
    validate_non_empty_string,
    validate_positive_integer,
)


ID_SEPARATOR = "-"


def generate_uuid() -> str:
    """
    Generate a compact UUID string.
    """

    return uuid4().hex


def generate_short_id(
    length: int = 8,
    source: str | None = None,
) -> str:
    """
    Generate a short ID.

    If source is provided, the short ID is derived from the normalized source.
    Otherwise, it is derived from a random UUID.
    """

    validate_positive_integer(length, "Length")

    if source is not None:
        normalized_source = normalize_id_part(source)

        if len(normalized_source) < length:
            return normalized_source

        return normalized_source[:length]

    return generate_uuid()[:length]


def generate_prefixed_id(
    prefix: str,
    unique_value: str | None = None,
    separator: str = ID_SEPARATOR,
) -> str:
    """
    Generate a prefixed ID.

    Example:
        generate_prefixed_id("order", "123") -> "order-123"
    """

    normalized_prefix = normalize_id_part(prefix)
    normalized_separator = validate_separator(separator)

    value = unique_value or generate_uuid()
    normalized_value = normalize_id_part(value)

    return f"{normalized_prefix}{normalized_separator}{normalized_value}"


def build_compound_id(
    *parts: str,
    separator: str = ID_SEPARATOR,
) -> str:
    """
    Build a compound ID from multiple parts.
    """

    if not parts:
        raise ValueError("ID parts cannot be empty.")

    normalized_separator = validate_separator(separator)

    normalized_parts = [
        normalize_id_part(part)
        for part in parts
    ]

    return normalized_separator.join(normalized_parts)


def build_timestamp_id(
    prefix: str,
    timestamp: datetime | None = None,
    separator: str = ID_SEPARATOR,
) -> str:
    """
    Build an ID using a UTC timestamp.
    """

    normalized_prefix = normalize_id_part(prefix)
    normalized_separator = validate_separator(separator)

    timestamp_value = timestamp or datetime.now(UTC)

    if not isinstance(timestamp_value, datetime):
        raise TypeError("Timestamp must be a datetime.")

    timestamp_text = timestamp_value.strftime("%Y%m%d%H%M%S")

    return f"{normalized_prefix}{normalized_separator}{timestamp_text}"


def normalize_id_part(
    value: str,
) -> str:
    """
    Normalize a value so it is safe for IDs.
    """

    text = validate_non_empty_string(value, "ID part").lower()

    text = re.sub(r"[^a-z0-9]+", ID_SEPARATOR, text)
    text = re.sub(r"-+", ID_SEPARATOR, text)
    text = text.strip(ID_SEPARATOR)

    if not text:
        raise ValueError("ID part cannot be empty after normalization.")

    return text


def normalize_id(
    value: str,
) -> str:
    """
    Normalize a complete ID.
    """

    return normalize_id_part(value)


def validate_id(
    value: str,
    name: str = "ID",
) -> str:
    """
    Validate an ID and return the normalized ID.
    """

    normalized = validate_non_empty_string(value, name)

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", normalized):
        raise ValueError(
            f"{name} may only contain letters, numbers, underscores, and hyphens."
        )

    return normalized


def validate_prefix(
    prefix: str,
) -> str:
    """
    Validate and normalize an ID prefix.
    """

    return normalize_id_part(prefix)


def validate_separator(
    separator: str,
) -> str:
    """
    Validate ID separator.
    """

    if not isinstance(separator, str):
        raise TypeError("ID separator must be a string.")

    if separator not in {
        "-",
        "_",
        ":",
        ".",
    }:
        raise ValueError("ID separator must be one of: -, _, :, .")

    return separator


def ensure_unique_id(
    candidate_id: str,
    existing_ids: set[str],
) -> str:
    """
    Ensure an ID is unique against an existing ID set.

    If the candidate is already present, a numeric suffix is appended.
    """

    normalized_candidate = normalize_id(candidate_id)

    if not isinstance(existing_ids, set):
        raise TypeError("Existing IDs must be a set.")

    if normalized_candidate not in existing_ids:
        return normalized_candidate

    counter = 2

    while True:
        next_candidate = f"{normalized_candidate}-{counter}"

        if next_candidate not in existing_ids:
            return next_candidate

        counter += 1


def is_valid_id(
    value: str,
) -> bool:
    """
    Return True if value is a valid ID.
    """

    try:
        validate_id(value)
    except (TypeError, ValueError):
        return False

    return True


__all__ = [
    "ID_SEPARATOR",
    "build_compound_id",
    "build_timestamp_id",
    "ensure_unique_id",
    "generate_prefixed_id",
    "generate_short_id",
    "generate_uuid",
    "is_valid_id",
    "normalize_id",
    "normalize_id_part",
    "validate_id",
    "validate_prefix",
    "validate_separator",
]