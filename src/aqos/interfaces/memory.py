"""
Memory interface.

Defines the contract that all AQOS memory implementations must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class MemoryInterfaceRecord:
    """
    Represents a generic memory record.
    """

    memory_id: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class MemoryInterfaceSearchResult:
    """
    Represents a generic memory search result.
    """

    record: MemoryInterfaceRecord
    score: float


class MemoryInterface(ABC):
    """
    Interface for AQOS memory systems.

    Any memory implementation must be able to store, retrieve,
    search, and remove memory records.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return memory system name.
        """

    @abstractmethod
    def store(
        self,
        memory_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryInterfaceRecord:
        """
        Store a memory record.
        """

    @abstractmethod
    def get(
        self,
        memory_id: str,
    ) -> MemoryInterfaceRecord | None:
        """
        Get a memory record by ID.
        """

    @abstractmethod
    def search(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[MemoryInterfaceSearchResult]:
        """
        Search memory records.
        """

    @abstractmethod
    def remove(
        self,
        memory_id: str,
    ) -> None:
        """
        Remove a memory record.
        """

    def get_required(
        self,
        memory_id: str,
    ) -> MemoryInterfaceRecord:
        """
        Get a memory record or raise if it does not exist.
        """

        self.validate_memory_id(memory_id)

        record = self.get(memory_id)

        if record is None:
            raise ValueError("Memory record does not exist.")

        return record

    def exists(
        self,
        memory_id: str,
    ) -> bool:
        """
        Check whether a memory record exists.
        """

        self.validate_memory_id(memory_id)

        return self.get(memory_id) is not None

    def store_many(
        self,
        records: list[MemoryInterfaceRecord],
    ) -> list[MemoryInterfaceRecord]:
        """
        Store multiple memory records.
        """

        if not records:
            raise ValueError("Memory records cannot be empty.")

        stored_records = []

        for record in records:
            self.validate_record(record)

            stored_records.append(
                self.store(
                    memory_id=record.memory_id,
                    content=record.content,
                    metadata=record.metadata,
                )
            )

        return stored_records

    def validate_record(
        self,
        record: MemoryInterfaceRecord,
    ) -> None:
        """
        Validate memory record.
        """

        if not isinstance(record, MemoryInterfaceRecord):
            raise TypeError("Record must be a MemoryInterfaceRecord.")

        self.validate_memory_id(record.memory_id)
        self.validate_content(record.content)

    def validate_search_result(
        self,
        result: MemoryInterfaceSearchResult,
    ) -> None:
        """
        Validate memory search result.
        """

        if not isinstance(result, MemoryInterfaceSearchResult):
            raise TypeError("Result must be a MemoryInterfaceSearchResult.")

        self.validate_record(result.record)
        self.validate_score(result.score)

    def validate_memory_id(
        self,
        memory_id: str,
    ) -> None:
        """
        Validate memory ID.
        """

        if not memory_id:
            raise ValueError("Memory ID cannot be empty.")

    def validate_content(
        self,
        content: str,
    ) -> None:
        """
        Validate memory content.
        """

        if not content:
            raise ValueError("Memory content cannot be empty.")

    def validate_query(
        self,
        query: str,
    ) -> None:
        """
        Validate memory search query.
        """

        if not query:
            raise ValueError("Search query cannot be empty.")

    def validate_limit(
        self,
        limit: int,
    ) -> None:
        """
        Validate search limit.
        """

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")

    def validate_score(
        self,
        score: float,
    ) -> None:
        """
        Validate search score.
        """

        if score < 0 or score > 1:
            raise ValueError("Score must be between 0.0 and 1.0.")


__all__ = [
    "MemoryInterface",
    "MemoryInterfaceRecord",
    "MemoryInterfaceSearchResult",
]