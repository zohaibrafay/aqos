"""
Unit tests for MemoryPipeline.
"""

import pytest

from aqos.memory import (
    EmbeddingEngine,
    MemoryPipeline,
    MemoryRetriever,
    PatternMemory,
    PatternRecord,
    TradeMemory,
    TradeRecord,
    VectorSearchResult,
    VectorStore,
)


def create_pipeline() -> MemoryPipeline:
    return MemoryPipeline(
        pattern_memory=PatternMemory(),
        trade_memory=TradeMemory(),
        retriever=MemoryRetriever(
            embedding_engine=EmbeddingEngine(dimensions=8),
            vector_store=VectorStore(),
        ),
    )


def test_remember_pattern():
    pipeline = create_pipeline()

    record = pipeline.remember_pattern(
        record_id="pattern-1",
        symbol="XAUUSD",
        timeframe="H1",
        pattern_name="bullish_engulfing",
    )

    counts = pipeline.counts()

    assert isinstance(record, PatternRecord)
    assert counts["patterns"] == 1
    assert counts["trades"] == 0
    assert counts["vectors"] == 1


def test_remember_pattern_with_metadata():
    pipeline = create_pipeline()

    pipeline.remember_pattern(
        record_id="pattern-1",
        symbol="XAUUSD",
        timeframe="H1",
        pattern_name="doji",
        metadata={"confidence": 0.8},
    )

    result = pipeline.retrieve(
        query="doji pattern on XAUUSD H1",
        top_k=1,
    )[0]

    assert result.record.metadata["confidence"] == 0.8
    assert result.record.metadata["memory_type"] == "pattern"


def test_remember_trade():
    pipeline = create_pipeline()

    record = pipeline.remember_trade(
        record_id="trade-1",
        symbol="XAUUSD",
        timeframe="H1",
        side="buy",
        entry_price=2000.0,
        quantity=1.0,
    )

    counts = pipeline.counts()

    assert isinstance(record, TradeRecord)
    assert counts["patterns"] == 0
    assert counts["trades"] == 1
    assert counts["vectors"] == 1


def test_remember_closed_trade():
    pipeline = create_pipeline()

    pipeline.remember_trade(
        record_id="trade-1",
        symbol="XAUUSD",
        timeframe="H1",
        side="sell",
        entry_price=2000.0,
        quantity=1.0,
        exit_price=1990.0,
    )

    result = pipeline.retrieve(
        query="sell trade on XAUUSD H1",
        top_k=1,
    )[0]

    assert result.record.metadata["memory_type"] == "trade"
    assert result.record.metadata["exit_price"] == 1990.0


def test_retrieve_memory():
    pipeline = create_pipeline()

    pipeline.remember_pattern(
        record_id="pattern-1",
        symbol="XAUUSD",
        timeframe="H1",
        pattern_name="bullish_engulfing",
    )

    results = pipeline.retrieve(
        query="bullish engulfing pattern on XAUUSD H1",
        top_k=1,
    )

    assert len(results) == 1
    assert isinstance(results[0], VectorSearchResult)
    assert results[0].record.record_id == "pattern-1"


def test_counts_empty_pipeline():
    pipeline = create_pipeline()

    counts = pipeline.counts()

    assert counts["patterns"] == 0
    assert counts["trades"] == 0
    assert counts["vectors"] == 0


def test_clear_pipeline():
    pipeline = create_pipeline()

    pipeline.remember_pattern(
        record_id="pattern-1",
        symbol="XAUUSD",
        timeframe="H1",
        pattern_name="doji",
    )

    pipeline.remember_trade(
        record_id="trade-1",
        symbol="XAUUSD",
        timeframe="H1",
        side="buy",
        entry_price=2000.0,
    )

    pipeline.clear()

    counts = pipeline.counts()

    assert counts["patterns"] == 0
    assert counts["trades"] == 0
    assert counts["vectors"] == 0


def test_empty_pattern_record_id():
    pipeline = create_pipeline()

    with pytest.raises(ValueError):
        pipeline.remember_pattern(
            record_id="",
            symbol="XAUUSD",
            timeframe="H1",
            pattern_name="doji",
        )


def test_empty_trade_record_id():
    pipeline = create_pipeline()

    with pytest.raises(ValueError):
        pipeline.remember_trade(
            record_id="",
            symbol="XAUUSD",
            timeframe="H1",
            side="buy",
            entry_price=2000.0,
        )


def test_invalid_pattern_data():
    pipeline = create_pipeline()

    with pytest.raises(ValueError):
        pipeline.remember_pattern(
            record_id="pattern-1",
            symbol="",
            timeframe="H1",
            pattern_name="doji",
        )


def test_invalid_trade_data():
    pipeline = create_pipeline()

    with pytest.raises(ValueError):
        pipeline.remember_trade(
            record_id="trade-1",
            symbol="XAUUSD",
            timeframe="H1",
            side="hold",
            entry_price=2000.0,
        )