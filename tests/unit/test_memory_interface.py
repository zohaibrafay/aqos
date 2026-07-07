"""
Unit tests for MemoryInterface.
"""

import pytest

from aqos.interfaces import (
    MemoryInterface,
    MemoryInterfaceRecord,
    MemoryInterfaceSearchResult,
)


class DummyMemory(MemoryInterface):
    """
    Test implementation of MemoryInterface.
    """

    def __init__(self) -> None:
        self._records: dict[str, MemoryInterfaceRecord] = {}

    @property
    def name(self) -> str:
        return "dummy-memory"

    def store(
        self,
        memory_id: str,
        content: str,
        metadata: dict | None = None,
    ) -> MemoryInterfaceRecord:
        self.validate_memory_id(memory_id)
        self.validate_content(content)

        record = MemoryInterfaceRecord(
            memory_id=memory_id,
            content=content,
            metadata=metadata or {},
        )

        self._records[memory_id] = record

        return record

    def get(
        self,
        memory_id: str,
    ) -> MemoryInterfaceRecord | None:
        self.validate_memory_id(memory_id)

        return self._records.get(memory_id)

    def search(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[MemoryInterfaceSearchResult]:
        self.validate_query(query)

        if limit is not None:
            self.validate_limit(limit)

        results = []

        for record in self._records.values():
            if query.lower() in record.content.lower():
                results.append(
                    MemoryInterfaceSearchResult(
                        record=record,
                        score=1.0,
                    )
                )

        if limit is not None:
            results = results[:limit]

        return results

    def remove(
        self,
        memory_id: str,
    ) -> None:
        self.validate_memory_id(memory_id)

        self._records.pop(memory_id, None)


def test_memory_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        MemoryInterface()


def test_dummy_memory_is_interface_instance():
    memory = DummyMemory()

    assert isinstance(memory, MemoryInterface)


def test_memory_name():
    memory = DummyMemory()

    assert memory.name == "dummy-memory"


def test_store_memory_record():
    memory = DummyMemory()

    record = memory.store(
        memory_id="memory-1",
        content="XAUUSD bullish breakout pattern",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert isinstance(record, MemoryInterfaceRecord)
    assert record.memory_id == "memory-1"
    assert record.content == "XAUUSD bullish breakout pattern"
    assert record.metadata["symbol"] == "XAUUSD"


def test_get_memory_record():
    memory = DummyMemory()

    memory.store(
        memory_id="memory-1",
        content="XAUUSD bullish breakout pattern",
    )

    record = memory.get("memory-1")

    assert record is not None
    assert record.memory_id == "memory-1"


def test_get_missing_memory_record():
    memory = DummyMemory()

    record = memory.get("missing")

    assert record is None


def test_get_required_memory_record():
    memory = DummyMemory()

    memory.store(
        memory_id="memory-1",
        content="XAUUSD bullish breakout pattern",
    )

    record = memory.get_required("memory-1")

    assert record.memory_id == "memory-1"


def test_get_required_missing_memory_record():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.get_required("missing")


def test_exists_true():
    memory = DummyMemory()

    memory.store(
        memory_id="memory-1",
        content="XAUUSD bullish breakout pattern",
    )

    assert memory.exists("memory-1") is True


def test_exists_false():
    memory = DummyMemory()

    assert memory.exists("memory-1") is False


def test_search_memory_records():
    memory = DummyMemory()

    memory.store(
        memory_id="memory-1",
        content="XAUUSD bullish breakout pattern",
    )
    memory.store(
        memory_id="memory-2",
        content="EURUSD bearish continuation pattern",
    )

    results = memory.search("bullish")

    assert len(results) == 1
    assert isinstance(results[0], MemoryInterfaceSearchResult)
    assert results[0].record.memory_id == "memory-1"
    assert results[0].score == 1.0


def test_search_memory_records_with_limit():
    memory = DummyMemory()

    memory.store("memory-1", "XAUUSD bullish breakout")
    memory.store("memory-2", "XAUUSD bullish continuation")

    results = memory.search(
        query="bullish",
        limit=1,
    )

    assert len(results) == 1


def test_search_returns_empty_list_when_no_match():
    memory = DummyMemory()

    memory.store(
        memory_id="memory-1",
        content="XAUUSD bullish breakout pattern",
    )

    results = memory.search("bearish")

    assert results == []


def test_remove_memory_record():
    memory = DummyMemory()

    memory.store(
        memory_id="memory-1",
        content="XAUUSD bullish breakout pattern",
    )

    memory.remove("memory-1")

    assert memory.exists("memory-1") is False


def test_store_many_memory_records():
    memory = DummyMemory()

    records = [
        MemoryInterfaceRecord(
            memory_id="memory-1",
            content="XAUUSD bullish breakout",
        ),
        MemoryInterfaceRecord(
            memory_id="memory-2",
            content="EURUSD bearish continuation",
        ),
    ]

    stored_records = memory.store_many(records)

    assert len(stored_records) == 2
    assert memory.exists("memory-1") is True
    assert memory.exists("memory-2") is True


def test_store_many_rejects_empty_records():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.store_many([])


def test_validate_record():
    memory = DummyMemory()

    record = MemoryInterfaceRecord(
        memory_id="memory-1",
        content="XAUUSD bullish breakout",
    )

    memory.validate_record(record)


def test_validate_record_rejects_invalid_type():
    memory = DummyMemory()

    with pytest.raises(TypeError):
        memory.validate_record("not-a-record")


def test_validate_search_result():
    memory = DummyMemory()

    result = MemoryInterfaceSearchResult(
        record=MemoryInterfaceRecord(
            memory_id="memory-1",
            content="XAUUSD bullish breakout",
        ),
        score=0.9,
    )

    memory.validate_search_result(result)


def test_validate_search_result_rejects_invalid_type():
    memory = DummyMemory()

    with pytest.raises(TypeError):
        memory.validate_search_result("not-a-result")


def test_empty_memory_id():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.store(
            memory_id="",
            content="XAUUSD bullish breakout",
        )


def test_empty_content():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.store(
            memory_id="memory-1",
            content="",
        )


def test_empty_query():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.search("")


def test_invalid_limit():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.search(
            query="bullish",
            limit=0,
        )


def test_invalid_low_score():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.validate_score(-0.1)


def test_invalid_high_score():
    memory = DummyMemory()

    with pytest.raises(ValueError):
        memory.validate_score(1.1)