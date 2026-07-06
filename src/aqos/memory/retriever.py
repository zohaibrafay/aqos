"""
Memory retriever.

Combines embedding generation with vector search so AQOS can store
and retrieve relevant memory records by semantic-like similarity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aqos.memory.embedding import EmbeddingEngine
from aqos.memory.vector_store import (
    VectorRecord,
    VectorSearchResult,
    VectorStore,
)


@dataclass(slots=True)
class MemoryRetriever:
    """
    Memory retrieval engine.
    """

    embedding_engine: EmbeddingEngine
    vector_store: VectorStore

    def add(
        self,
        record_id: str,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> VectorRecord:
        """
        Add a text memory record to the vector store.
        """

        if not record_id:
            raise ValueError("Record ID cannot be empty.")

        if not text:
            raise ValueError("Text cannot be empty.")

        vector = self.embedding_engine.encode(text)

        record_metadata = metadata.copy() if metadata else {}
        record_metadata["text"] = text

        return self.vector_store.add(
            record_id=record_id,
            vector=vector,
            metadata=record_metadata,
        )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[VectorSearchResult]:
        """
        Retrieve the most relevant memory records for a query.
        """

        if not query:
            raise ValueError("Query cannot be empty.")

        if top_k <= 0:
            raise ValueError("top_k must be greater than zero.")

        query_vector = self.embedding_engine.encode(query)

        return self.vector_store.search(
            query_vector=query_vector,
            top_k=top_k,
        )

    def get(
        self,
        record_id: str,
    ) -> VectorRecord | None:
        """
        Get a stored memory record by ID.
        """

        return self.vector_store.get(record_id)

    def count(self) -> int:
        """
        Return the number of stored memory records.
        """

        return self.vector_store.count()

    def clear(self) -> None:
        """
        Clear all stored memory records.
        """

        self.vector_store.clear()


__all__ = ["MemoryRetriever"]