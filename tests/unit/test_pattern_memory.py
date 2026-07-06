"""
Unit tests for PatternMemory.
"""

from datetime import datetime, timezone

import pytest

from aqos.memory import PatternMemory, PatternRecord


def test_add_pattern_record():
    memory = PatternMemory()

    record = memory.add(
        symbol="XAUUSD",
        timeframe="H1",
        pattern_name="bullish_engulfing",
    )

    assert isinstance(record, PatternRecord)
    assert record.symbol == "XAUUSD"
    assert record.timeframe == "H1"
    assert record.pattern_name == "bullish_engulfing"
    assert memory.count() == 1


def test_add_pattern_with_metadata():
    memory = PatternMemory()

    record = memory.add(
        symbol="XAUUSD",
        timeframe="H1",
        pattern_name="doji",
        metadata={"confidence": 0.75},
    )

    assert record.metadata["confidence"] == 0.75


def test_add_pattern_with_timestamp():
    memory = PatternMemory()

    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    record = memory.add(
        symbol="EURUSD",
        timeframe="M15",
        pattern_name="hammer",
        timestamp=timestamp,
    )

    assert record.timestamp == timestamp


def test_list_records():
    memory = PatternMemory()

    memory.add("XAUUSD", "H1", "doji")
    memory.add("EURUSD", "M15", "hammer")

    records = memory.list()

    assert len(records) == 2


def test_find_by_symbol():
    memory = PatternMemory()

    memory.add("XAUUSD", "H1", "doji")
    memory.add("EURUSD", "M15", "hammer")

    records = memory.find_by_symbol("XAUUSD")

    assert len(records) == 1
    assert records[0].symbol == "XAUUSD"


def test_find_by_pattern():
    memory = PatternMemory()

    memory.add("XAUUSD", "H1", "doji")
    memory.add("EURUSD", "M15", "doji")
    memory.add("GBPUSD", "M30", "hammer")

    records = memory.find_by_pattern("doji")

    assert len(records) == 2


def test_clear_memory():
    memory = PatternMemory()

    memory.add("XAUUSD", "H1", "doji")

    memory.clear()

    assert memory.count() == 0


def test_empty_symbol():
    memory = PatternMemory()

    with pytest.raises(ValueError):
        memory.add("", "H1", "doji")


def test_empty_timeframe():
    memory = PatternMemory()

    with pytest.raises(ValueError):
        memory.add("XAUUSD", "", "doji")


def test_empty_pattern_name():
    memory = PatternMemory()

    with pytest.raises(ValueError):
        memory.add("XAUUSD", "H1", "")