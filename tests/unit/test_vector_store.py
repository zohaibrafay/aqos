"""
Unit tests for VectorStore.
"""

import pytest

from aqos.memory import VectorRecord, VectorSearchResult, VectorStore


def test_add_vector_record():
    store = VectorStore()

    record = store.add(
        record_id="pattern-1",
        vector=[1.0, 0.0, 0.0],
        metadata={"symbol": "XAUUSD"},
    )

    assert isinstance(record, VectorRecord)
    assert record.record_id == "pattern-1"
    assert record.vector == [1.0, 0.0, 0.0]
    assert record.metadata["symbol"] == "XAUUSD"
    assert store.count() == 1


def test_get_vector_record():
    store = VectorStore()

    store.add(
        record_id="trade-1",
        vector=[0.0, 1.0, 0.0],
    )

    record = store.get("trade-1")

    assert record is not None
    assert record.record_id == "trade-1"


def test_get_missing_vector_record():
    store = VectorStore()

    record = store.get("missing")

    assert record is None


def test_list_records():
    store = VectorStore()

    store.add("record-1", [1.0, 0.0])
    store.add("record-2", [0.0, 1.0])

    records = store.list()

    assert len(records) == 2


def test_search_vectors():
    store = VectorStore()

    store.add("record-1", [1.0, 0.0])
    store.add("record-2", [0.0, 1.0])
    store.add("record-3", [0.9, 0.1])

    results = store.search(
        query_vector=[1.0, 0.0],
        top_k=2,
    )

    assert len(results) == 2
    assert isinstance(results[0], VectorSearchResult)
    assert results[0].record.record_id == "record-1"
    assert results[0].score >= results[1].score


def test_search_empty_store():
    store = VectorStore()

    results = store.search(
        query_vector=[1.0, 0.0],
        top_k=3,
    )

    assert results == []


def test_clear_store():
    store = VectorStore()

    store.add("record-1", [1.0, 0.0])

    store.clear()

    assert store.count() == 0


def test_empty_record_id():
    store = VectorStore()

    with pytest.raises(ValueError):
        store.add("", [1.0, 0.0])


def test_duplicate_record_id():
    store = VectorStore()

    store.add("record-1", [1.0, 0.0])

    with pytest.raises(ValueError):
        store.add("record-1", [0.0, 1.0])


def test_empty_vector():
    store = VectorStore()

    with pytest.raises(ValueError):
        store.add("record-1", [])


def test_non_numeric_vector():
    store = VectorStore()

    with pytest.raises(ValueError):
        store.add("record-1", [1.0, "bad"])


def test_dimension_mismatch():
    store = VectorStore()

    store.add("record-1", [1.0, 0.0])

    with pytest.raises(ValueError):
        store.add("record-2", [1.0, 0.0, 0.0])


def test_invalid_top_k():
    store = VectorStore()

    with pytest.raises(ValueError):
        store.search(
            query_vector=[1.0, 0.0],
            top_k=0,
        )