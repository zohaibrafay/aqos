"""
Unit tests for UncertaintyEngine.
"""

import pandas as pd
import pytest

from aqos.models.uncertainty import UncertaintyEngine


def test_confidence():
    engine = UncertaintyEngine()

    probabilities = pd.Series([0.10, 0.25, 0.85])

    confidence = engine.confidence(probabilities)

    assert confidence == pytest.approx(0.85)


def test_single_probability():
    engine = UncertaintyEngine()

    probabilities = pd.Series([0.60])

    confidence = engine.confidence(probabilities)

    assert confidence == pytest.approx(0.60)


def test_empty_probabilities():
    engine = UncertaintyEngine()

    with pytest.raises(ValueError):
        engine.confidence(pd.Series(dtype=float))


def test_probability_less_than_zero():
    engine = UncertaintyEngine()

    probabilities = pd.Series([-0.1, 0.8])

    with pytest.raises(ValueError):
        engine.confidence(probabilities)


def test_probability_greater_than_one():
    engine = UncertaintyEngine()

    probabilities = pd.Series([0.4, 1.2])

    with pytest.raises(ValueError):
        engine.confidence(probabilities)