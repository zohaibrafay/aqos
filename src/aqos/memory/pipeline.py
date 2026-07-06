"""
Memory pipeline.

Coordinates pattern memory, trade memory, embedding, vector storage,
and retrieval for AQOS memory operations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aqos.memory.pattern_memory import PatternMemory, PatternRecord
from aqos.memory.retriever import MemoryRetriever
from aqos.memory.trade_memory import TradeMemory, TradeRecord
from aqos.memory.vector_store import VectorSearchResult


@dataclass(slots=True)
class MemoryPipeline:
    """
    Unified memory pipeline.
    """

    pattern_memory: PatternMemory
    trade_memory: TradeMemory
    retriever: MemoryRetriever

    def remember_pattern(
        self,
        record_id: str,
        symbol: str,
        timeframe: str,
        pattern_name: str,
        timestamp: datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> PatternRecord:
        """
        Store a pattern record and index it for retrieval.
        """

        if not record_id:
            raise ValueError("Record ID cannot be empty.")

        record = self.pattern_memory.add(
            symbol=symbol,
            timeframe=timeframe,
            pattern_name=pattern_name,
            timestamp=timestamp,
            metadata=metadata,
        )

        memory_metadata = metadata.copy() if metadata else {}
        memory_metadata.update(
            {
                "memory_type": "pattern",
                "symbol": symbol,
                "timeframe": timeframe,
                "pattern_name": pattern_name,
            }
        )

        self.retriever.add(
            record_id=record_id,
            text=self._pattern_text(record),
            metadata=memory_metadata,
        )

        return record

    def remember_trade(
        self,
        record_id: str,
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
        Store a trade record and index it for retrieval.
        """

        if not record_id:
            raise ValueError("Record ID cannot be empty.")

        record = self.trade_memory.add(
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            timestamp=timestamp,
            exit_price=exit_price,
            metadata=metadata,
        )

        memory_metadata = metadata.copy() if metadata else {}
        memory_metadata.update(
            {
                "memory_type": "trade",
                "symbol": symbol,
                "timeframe": timeframe,
                "side": side,
                "entry_price": entry_price,
                "quantity": quantity,
                "exit_price": exit_price,
            }
        )

        self.retriever.add(
            record_id=record_id,
            text=self._trade_text(record),
            metadata=memory_metadata,
        )

        return record

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[VectorSearchResult]:
        """
        Retrieve relevant memory records.
        """

        return self.retriever.retrieve(
            query=query,
            top_k=top_k,
        )

    def counts(self) -> dict[str, int]:
        """
        Return memory counts.
        """

        return {
            "patterns": self.pattern_memory.count(),
            "trades": self.trade_memory.count(),
            "vectors": self.retriever.count(),
        }

    def clear(self) -> None:
        """
        Clear all memory stores.
        """

        self.pattern_memory.clear()
        self.trade_memory.clear()
        self.retriever.clear()

    def _pattern_text(
        self,
        record: PatternRecord,
    ) -> str:
        """
        Convert a pattern record into retrievable text.
        """

        return (
            f"{record.pattern_name} pattern "
            f"on {record.symbol} {record.timeframe}"
        )

    def _trade_text(
        self,
        record: TradeRecord,
    ) -> str:
        """
        Convert a trade record into retrievable text.
        """

        text = (
            f"{record.side} trade on {record.symbol} "
            f"{record.timeframe} entry {record.entry_price} "
            f"quantity {record.quantity}"
        )

        if record.exit_price is not None:
            text = f"{text} exit {record.exit_price}"

        return text


__all__ = ["MemoryPipeline"]