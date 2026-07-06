"""
Trade memory.

Stores historical trade records so AQOS can later analyze outcomes,
retrieve previous trades, and learn from execution history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True, frozen=True)
class TradeRecord:
    """
    Represents a stored trade record.
    """

    symbol: str
    timeframe: str
    side: str
    entry_price: float
    quantity: float
    timestamp: datetime
    exit_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TradeMemory:
    """
    In-memory storage for historical trades.
    """

    def __init__(self) -> None:
        self._records: list[TradeRecord] = []

    def add(
        self,
        symbol: str,
        timeframe: str,
        side: str,
        entry_price: float,
        quantity: float = 1.0,
        timestamp: datetime | None = None,
        exit_price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TradeRecord:
        """
        Add a trade record to memory.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

        if not timeframe:
            raise ValueError("Timeframe cannot be empty.")

        if side not in {"buy", "sell"}:
            raise ValueError("Side must be either 'buy' or 'sell'.")

        if entry_price <= 0:
            raise ValueError("Entry price must be greater than zero.")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if exit_price is not None and exit_price <= 0:
            raise ValueError("Exit price must be greater than zero.")

        record = TradeRecord(
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            timestamp=timestamp or datetime.now(timezone.utc),
            exit_price=exit_price,
            metadata=metadata or {},
        )

        self._records.append(record)

        return record

    def list(self) -> list[TradeRecord]:
        """
        Return all stored trade records.
        """

        return list(self._records)

    def count(self) -> int:
        """
        Return the number of stored trade records.
        """

        return len(self._records)

    def find_by_symbol(
        self,
        symbol: str,
    ) -> list[TradeRecord]:
        """
        Find trade records by symbol.
        """

        return [
            record
            for record in self._records
            if record.symbol == symbol
        ]

    def find_by_side(
        self,
        side: str,
    ) -> list[TradeRecord]:
        """
        Find trade records by side.
        """

        return [
            record
            for record in self._records
            if record.side == side
        ]

    def open_trades(self) -> list[TradeRecord]:
        """
        Return trades without an exit price.
        """

        return [
            record
            for record in self._records
            if record.exit_price is None
        ]

    def closed_trades(self) -> list[TradeRecord]:
        """
        Return trades with an exit price.
        """

        return [
            record
            for record in self._records
            if record.exit_price is not None
        ]

    def clear(self) -> None:
        """
        Clear all trade records.
        """

        self._records.clear()


__all__ = [
    "TradeMemory",
    "TradeRecord",
]