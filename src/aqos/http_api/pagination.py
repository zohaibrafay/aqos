from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from aqos.http_api.errors import ValidationApiError


AQOS_HTTP_PAGINATION_VERSION = "1.0"

DEFAULT_PAGE_LIMIT = 50

#: The most rows any single request may ask for.
#:
#: Bounded so one caller cannot ask the database for an unbounded result set and
#: turn a read endpoint into a denial of service.
MAX_PAGE_LIMIT = 200

MIN_PAGE_LIMIT = 1


def validate_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_PAGE_LIMIT

    if limit < MIN_PAGE_LIMIT:
        raise ValidationApiError(
            f"limit must be at least {MIN_PAGE_LIMIT}.",
            details={"limit": limit, "minimum": MIN_PAGE_LIMIT},
        )

    if limit > MAX_PAGE_LIMIT:
        raise ValidationApiError(
            f"limit cannot exceed {MAX_PAGE_LIMIT}.",
            details={"limit": limit, "maximum": MAX_PAGE_LIMIT},
        )

    return limit


def validate_offset(offset: int | None) -> int:
    if offset is None:
        return 0

    if offset < 0:
        raise ValidationApiError(
            "offset cannot be negative.",
            details={"offset": offset},
        )

    return offset


@dataclass(frozen=True)
class Page:
    """
    One page of results.

    ``total`` is optional and stays ``None`` when a count was not run. A guessed
    or derived total would be worse than an absent one: a client cannot tell a
    real count from a fabricated one, and AQOS does not report numbers it did
    not measure.
    """

    items: Sequence[Any]
    limit: int
    offset: int
    total: int | None = None

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def has_total(self) -> bool:
        return self.total is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": list(self.items),
            "limit": self.limit,
            "offset": self.offset,
            "total": self.total,
            "count": self.count,
        }


def build_page(
    items: Sequence[Any],
    limit: int,
    offset: int,
    total: int | None = None,
) -> Page:
    return Page(items=items, limit=limit, offset=offset, total=total)


def apply_offset_limit(
    items: Sequence[Any],
    limit: int,
    offset: int,
) -> tuple[Any, ...]:
    """
    Slice an already-loaded sequence.

    Only for sources that cannot paginate in the query itself, such as the
    file-backed registries. Database reads push the window down to SQL instead.
    """

    return tuple(items[offset : offset + limit])


__all__ = [
    "AQOS_HTTP_PAGINATION_VERSION",
    "DEFAULT_PAGE_LIMIT",
    "MAX_PAGE_LIMIT",
    "MIN_PAGE_LIMIT",
    "Page",
    "apply_offset_limit",
    "build_page",
    "validate_limit",
    "validate_offset",
]
