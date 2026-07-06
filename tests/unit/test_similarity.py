"""
Unit tests for SimilarityEngine.
"""

import pandas as pd
import pytest

from aqos.models.similarity import SimilarityEngine


def test_identical_vectors():
    engine = SimilarityEngine()

    a = pd.Series([1, 2, 3, 4])
    b = pd.Series([1, 2, 3, 4])

    assert engine.score(a, b) == pytest.approx(1.0)


def test_partial_similarity():
    engine = SimilarityEngine()

    a = pd.Series([1, 2, 3, 4])
    b = pd.Series([1, 5, 3, 6])

    assert engine.score(a, b) == pytest.approx(0.5)


def test_no_similarity():
    engine = SimilarityEngine()

    a = pd.Series([1, 2, 3])
    b = pd.Series([4, 5, 6])

    assert engine.score(a, b) == pytest.approx(0.0)


def test_empty_vector():
    engine = SimilarityEngine()

    with pytest.raises(ValueError):
        engine.score(pd.Series(dtype=float), pd.Series(dtype=float))


def test_different_lengths():
    engine = SimilarityEngine()

    a = pd.Series([1, 2, 3])
    b = pd.Series([1, 2])

    with pytest.raises(ValueError):
        engine.score(a, b)