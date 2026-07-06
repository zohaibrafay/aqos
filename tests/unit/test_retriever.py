"""
Unit tests for MemoryRetriever.
"""

import pytest

from aqos.memory import (
    EmbeddingEngine,
    MemoryRetriever,
    VectorRecord,
    VectorSearchResult,
    VectorStore,
)


def create_retriever() -> MemoryRetriever:
    return MemoryRetriever(
        embedding_engine=EmbeddingEngine(dimensions=8),
        vector_store=VectorStore(),
    )


def test_add_memory_record():
    retriever = create_retriever()

    record = retriever.add(
        record_id="pattern-1",
        text="bullish engulfing pattern on XAUUSD H1",
        metadata={"symbol": "XAUUSD"},
    )

    assert isinstance(record, VectorRecord)
    assert record.record_id == "pattern-1"
    assert record.metadata["symbol"] == "XAUUSD"
    assert record.metadata["text"] == "bullish engulfing pattern on XAUUSD H1"
    assert retriever.count() == 1


def test_retrieve_memory_record():
    retriever = create_retriever()

    retriever.add(
        record_id="pattern-1",
        text="bullish engulfing pattern",
    )
    retriever.add(
        record_id="pattern-2",
        text="bearish engulfing pattern",
    )

    results = retriever.retrieve(
        query="bullish engulfing pattern",
        top_k=1,
    )

    assert len(results) == 1
    assert isinstance(results[0], VectorSearchResult)
    assert results[0].record.record_id == "pattern-1"


def test_retrieve_multiple_records():
    retriever = create_retriever()

    retriever.add("memory-1", "doji pattern")
    retriever.add("memory-2", "hammer pattern")
    retriever.add("memory-3", "shooting star pattern")

    results = retriever.retrieve(
        query="doji pattern",
        top_k=2,
    )

    assert len(results) == 2


def test_get_memory_record():
    retriever = create_retriever()

    retriever.add(
        record_id="trade-1",
        text="buy XAUUSD at 2000",
    )

    record = retriever.get("trade-1")

    assert record is not None
    assert record.record_id == "trade-1"


def test_get_missing_memory_record():
    retriever = create_retriever()

    record = retriever.get("missing")

    assert record is None


def test_clear_memory_records():
    retriever = create_retriever()

    retriever.add("memory-1", "test memory")

    retriever.clear()

    assert retriever.count() == 0


def test_empty_record_id():
    retriever = create_retriever()

    with pytest.raises(ValueError):
        retriever.add("", "test memory")


def test_empty_text():
    retriever = create_retriever()

    with pytest.raises(ValueError):
        retriever.add("memory-1", "")


def test_empty_query():
    retriever = create_retriever()

    with pytest.raises(ValueError):
        retriever.retrieve("")


def test_invalid_top_k():
    retriever = create_retriever()

    with pytest.raises(ValueError):
        retriever.retrieve(
            query="test memory",
            top_k=0,
        )