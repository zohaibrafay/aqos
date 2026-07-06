"""
Unit tests for TradeMemory.
"""

from datetime import datetime, timezone

import pytest

from aqos.memory import TradeMemory, TradeRecord


def test_add_trade_record():
    memory = TradeMemory()

    record = memory.add(
        symbol="XAUUSD",
        timeframe="H1",
        side="buy",
        entry_price=2000.0,
        quantity=1.0,
    )

    assert isinstance(record, TradeRecord)
    assert record.symbol == "XAUUSD"
    assert record.timeframe == "H1"
    assert record.side == "buy"
    assert record.entry_price == 2000.0
    assert record.quantity == 1.0
    assert memory.count() == 1


def test_add_trade_with_exit_price():
    memory = TradeMemory()

    record = memory.add(
        symbol="XAUUSD",
        timeframe="H1",
        side="sell",
        entry_price=2000.0,
        quantity=2.0,
        exit_price=1990.0,
    )

    assert record.exit_price == 1990.0


def test_add_trade_with_metadata():
    memory = TradeMemory()

    record = memory.add(
        symbol="XAUUSD",
        timeframe="H1",
        side="buy",
        entry_price=2000.0,
        metadata={"strategy": "trend_following"},
    )

    assert record.metadata["strategy"] == "trend_following"


def test_add_trade_with_timestamp():
    memory = TradeMemory()

    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

    record = memory.add(
        symbol="EURUSD",
        timeframe="M15",
        side="sell",
        entry_price=1.1000,
        timestamp=timestamp,
    )

    assert record.timestamp == timestamp


def test_list_records():
    memory = TradeMemory()

    memory.add("XAUUSD", "H1", "buy", 2000.0)
    memory.add("EURUSD", "M15", "sell", 1.1000)

    records = memory.list()

    assert len(records) == 2


def test_find_by_symbol():
    memory = TradeMemory()

    memory.add("XAUUSD", "H1", "buy", 2000.0)
    memory.add("EURUSD", "M15", "sell", 1.1000)

    records = memory.find_by_symbol("XAUUSD")

    assert len(records) == 1
    assert records[0].symbol == "XAUUSD"


def test_find_by_side():
    memory = TradeMemory()

    memory.add("XAUUSD", "H1", "buy", 2000.0)
    memory.add("EURUSD", "M15", "sell", 1.1000)
    memory.add("GBPUSD", "M30", "buy", 1.2500)

    records = memory.find_by_side("buy")

    assert len(records) == 2


def test_open_trades():
    memory = TradeMemory()

    memory.add("XAUUSD", "H1", "buy", 2000.0)
    memory.add("EURUSD", "M15", "sell", 1.1000, exit_price=1.0900)

    records = memory.open_trades()

    assert len(records) == 1
    assert records[0].exit_price is None


def test_closed_trades():
    memory = TradeMemory()

    memory.add("XAUUSD", "H1", "buy", 2000.0)
    memory.add("EURUSD", "M15", "sell", 1.1000, exit_price=1.0900)

    records = memory.closed_trades()

    assert len(records) == 1
    assert records[0].exit_price == 1.0900


def test_clear_memory():
    memory = TradeMemory()

    memory.add("XAUUSD", "H1", "buy", 2000.0)

    memory.clear()

    assert memory.count() == 0


def test_empty_symbol():
    memory = TradeMemory()

    with pytest.raises(ValueError):
        memory.add("", "H1", "buy", 2000.0)


def test_empty_timeframe():
    memory = TradeMemory()

    with pytest.raises(ValueError):
        memory.add("XAUUSD", "", "buy", 2000.0)


def test_invalid_side():
    memory = TradeMemory()

    with pytest.raises(ValueError):
        memory.add("XAUUSD", "H1", "hold", 2000.0)


def test_invalid_entry_price():
    memory = TradeMemory()

    with pytest.raises(ValueError):
        memory.add("XAUUSD", "H1", "buy", 0)


def test_invalid_quantity():
    memory = TradeMemory()

    with pytest.raises(ValueError):
        memory.add("XAUUSD", "H1", "buy", 2000.0, quantity=0)


def test_invalid_exit_price():
    memory = TradeMemory()

    with pytest.raises(ValueError):
        memory.add(
            symbol="XAUUSD",
            timeframe="H1",
            side="buy",
            entry_price=2000.0,
            exit_price=0,
        )