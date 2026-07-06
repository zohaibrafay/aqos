"""
Pattern memory.

Stores detected market patterns so AQOS can later retrieve,
compare, and learn from historical pattern occurrences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True, frozen=True)
class PatternRecord:
    """
    Represents a detected market pattern.
    """

    symbol: str
    timeframe: str
    pattern_name: str
    timestamp: datetime
    metadata: dict[str, Any] = field(default_factory=dict)


class PatternMemory:
    """
    In-memory storage for detected market patterns.
    """

    def __init__(self) -> None:
        self._records: list[PatternRecord] = []

    def add(
        self,
        symbol: str,
        timeframe: str,
        pattern_name: str,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PatternRecord:
        """
        Add a pattern record to memory.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

        if not timeframe:
            raise ValueError("Timeframe cannot be empty.")

        if not pattern_name:
            raise ValueError("Pattern name cannot be empty.")

        record = PatternRecord(
            symbol=symbol,
            timeframe=timeframe,
            pattern_name=pattern_name,
            timestamp=timestamp or datetime.now(timezone.utc),
            metadata=metadata or {},
        )

        self._records.append(record)

        return record

    def list(self) -> list[PatternRecord]:
        """
        Return all stored pattern records.
        """

        return list(self._records)

    def count(self) -> int:
        """
        Return the number of stored pattern records.
        """

        return len(self._records)

    def find_by_symbol(
        self,
        symbol: str,
    ) -> list[PatternRecord]:
        """
        Find pattern records by symbol.
        """

        return [
            record
            for record in self._records
            if record.symbol == symbol
        ]

    def find_by_pattern(
        self,
        pattern_name: str,
    ) -> list[PatternRecord]:
        """
        Find pattern records by pattern name.
        """

        return [
            record
            for record in self._records
            if record.pattern_name == pattern_name
        ]

    def clear(self) -> None:
        """
        Clear all pattern records.
        """

        self._records.clear()


__all__ = [
    "PatternMemory",
    "PatternRecord",
]