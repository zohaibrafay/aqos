from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, TypeVar

from sqlalchemy import String
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


AQOS_DATABASE_TYPES_VERSION = "1.0"

DEFAULT_ENUM_LENGTH = 32

EnumT = TypeVar("EnumT", bound=Enum)


def database_utc_now() -> datetime:
    """
    Current UTC time as a naive datetime.

    MySQL ``DATETIME`` columns do not carry a timezone, so AQOS stores naive
    UTC values and never mixes aware and naive datetimes.
    """

    return datetime.now(tz=UTC).replace(tzinfo=None, microsecond=0)


def to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(microsecond=0)

    return value.astimezone(UTC).replace(tzinfo=None, microsecond=0)


class EnumString(TypeDecorator):
    """
    Stores a Python enum as its string value in a ``VARCHAR`` column.

    Hand-written AQOS migrations use ``VARCHAR`` rather than MySQL ``ENUM`` so
    that adding a new member is a code change instead of a table rewrite. This
    type keeps the Python side strict: unknown values are rejected on the way
    in and on the way out.
    """

    impl = String
    cache_ok = True

    def __init__(
        self,
        enum_class: type[Enum],
        length: int = DEFAULT_ENUM_LENGTH,
        **kwargs: Any,
    ) -> None:
        if not issubclass(enum_class, Enum):
            raise TypeError("EnumString requires an Enum subclass.")

        self.enum_class = enum_class

        super().__init__(length=length, **kwargs)

    def process_bind_param(
        self,
        value: Enum | str | None,
        dialect: Dialect,
    ) -> str | None:
        if value is None:
            return None

        if isinstance(value, self.enum_class):
            return str(value.value)

        return str(self.enum_class(value).value)

    def process_result_value(
        self,
        value: str | None,
        dialect: Dialect,
    ) -> Enum | None:
        if value is None:
            return None

        return self.enum_class(value)

    def copy(self, **kwargs: Any) -> "EnumString":
        return EnumString(self.enum_class, length=self.impl.length)


__all__ = [
    "AQOS_DATABASE_TYPES_VERSION",
    "DEFAULT_ENUM_LENGTH",
    "EnumString",
    "database_utc_now",
    "to_naive_utc",
]
