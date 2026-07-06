"""
Unit tests for EmbeddingEngine.
"""

import pytest

from aqos.memory import EmbeddingEngine


def test_encode_text():
    engine = EmbeddingEngine(dimensions=8)

    vector = engine.encode("bullish engulfing on XAUUSD H1")

    assert isinstance(vector, list)
    assert len(vector) == 8
    assert all(isinstance(value, float) for value in vector)


def test_encode_is_deterministic():
    engine = EmbeddingEngine(dimensions=8)

    first = engine.encode("doji pattern")
    second = engine.encode("doji pattern")

    assert first == second


def test_different_texts_create_different_vectors():
    engine = EmbeddingEngine(dimensions=8)

    first = engine.encode("bullish pattern")
    second = engine.encode("bearish pattern")

    assert first != second


def test_vector_is_normalized():
    engine = EmbeddingEngine(dimensions=8)

    vector = engine.encode("trend continuation")

    magnitude = sum(value * value for value in vector) ** 0.5

    assert magnitude == pytest.approx(1.0)


def test_encode_many():
    engine = EmbeddingEngine(dimensions=4)

    vectors = engine.encode_many(
        [
            "bullish engulfing",
            "bearish engulfing",
        ]
    )

    assert len(vectors) == 2
    assert len(vectors[0]) == 4
    assert len(vectors[1]) == 4


def test_invalid_dimensions():
    with pytest.raises(ValueError):
        EmbeddingEngine(dimensions=0)


def test_empty_text():
    engine = EmbeddingEngine()

    with pytest.raises(ValueError):
        engine.encode("")


def test_empty_texts():
    engine = EmbeddingEngine()

    with pytest.raises(ValueError):
        engine.encode_many([])