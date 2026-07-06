"""
Vector store.

Stores embedding vectors in memory and provides similarity search.

This Sprint 007 implementation is intentionally lightweight and uses
an in-memory dictionary. Future versions will support FAISS, Chroma,
Qdrant, Pinecone, pgvector, and persistent vector databases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import sqrt
from typing import Any


@dataclass(slots=True, frozen=True)
class VectorRecord:
    """
    Represents a stored vector record.
    """

    record_id: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class VectorSearchResult:
    """
    Represents a vector search result.
    """

    record: VectorRecord
    score: float


class VectorStore:
    """
    In-memory vector store.
    """

    def __init__(self) -> None:
        self._records: dict[str, VectorRecord] = {}

    def add(
        self,
        record_id: str,
        vector: list[float],
        metadata: dict[str, Any] | None = None,
    ) -> VectorRecord:
        """
        Add a vector record.
        """

        if not record_id:
            raise ValueError("Record ID cannot be empty.")

        if record_id in self._records:
            raise ValueError("Record ID already exists.")

        self._validate_vector(vector)
        self._validate_dimension(vector)

        record = VectorRecord(
            record_id=record_id,
            vector=list(vector),
            metadata=metadata or {},
        )

        self._records[record_id] = record

        return record

    def get(
        self,
        record_id: str,
    ) -> VectorRecord | None:
        """
        Get a vector record by ID.
        """

        return self._records.get(record_id)

    def list(self) -> list[VectorRecord]:
        """
        Return all vector records.
        """

        return list(self._records.values())

    def count(self) -> int:
        """
        Return the number of stored vectors.
        """

        return len(self._records)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
    ) -> list[VectorSearchResult]:
        """
        Search for the most similar vectors.
        """

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        self._validate_vector(query_vector)
        self._validate_dimension(query_vector)

        results = [
            VectorSearchResult(
                record=record,
                score=self._cosine_similarity(
                    query_vector,
                    record.vector,
                ),
            )
            for record in self._records.values()
        ]

        results.sort(
            key=lambda result: result.score,
            reverse=True,
        )

        return results[:top_k]

    def clear(self) -> None:
        """
        Clear all stored vectors.
        """

        self._records.clear()

    def _validate_vector(
        self,
        vector: list[float],
    ) -> None:
        """
        Validate vector input.
        """

        if not vector:
            raise ValueError("Vector cannot be empty.")

        if not all(isinstance(value, int | float) for value in vector):
            raise ValueError("Vector must contain numeric values.")

    def _validate_dimension(
        self,
        vector: list[float],
    ) -> None:
        """
        Validate vector dimension against existing records.
        """

        if not self._records:
            return

        first_record = next(iter(self._records.values()))

        if len(vector) != len(first_record.vector):
            raise ValueError(
                "Vector dimension must match existing records."
            )

    def _cosine_similarity(
        self,
        first: list[float],
        second: list[float],
    ) -> float:
        """
        Calculate cosine similarity between two vectors.
        """

        first_magnitude = sqrt(
            sum(value * value for value in first)
        )
        second_magnitude = sqrt(
            sum(value * value for value in second)
        )

        if first_magnitude == 0 or second_magnitude == 0:
            return 0.0

        dot_product = sum(
            first_value * second_value
            for first_value, second_value in zip(first, second)
        )

        return dot_product / (first_magnitude * second_magnitude)


__all__ = [
    "VectorRecord",
    "VectorSearchResult",
    "VectorStore",
]