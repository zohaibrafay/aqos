"""
Unit tests for WorldModel.
"""

import pandas as pd
import pytest

from aqos.models.world_model import WorldModel


def test_build_world():
    world = WorldModel()

    features = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "close": [2, 3, 4],
        }
    )

    prediction = pd.Series([1, 0, 1])

    state = world.build(
        features=features,
        prediction=prediction,
        confidence=0.91,
    )

    assert state["samples"] == 3
    assert state["prediction"] == [1, 0, 1]
    assert state["confidence"] == pytest.approx(0.91)


def test_empty_features():
    world = WorldModel()

    with pytest.raises(ValueError):
        world.build(
            features=pd.DataFrame(),
            prediction=pd.Series([1]),
            confidence=0.8,
        )


def test_empty_prediction():
    world = WorldModel()

    features = pd.DataFrame({"x": [1]})

    with pytest.raises(ValueError):
        world.build(
            features=features,
            prediction=pd.Series(dtype=int),
            confidence=0.8,
        )


def test_length_mismatch():
    world = WorldModel()

    features = pd.DataFrame({"x": [1, 2]})

    prediction = pd.Series([1])

    with pytest.raises(ValueError):
        world.build(
            features=features,
            prediction=prediction,
            confidence=0.8,
        )


def test_invalid_confidence():
    world = WorldModel()

    features = pd.DataFrame({"x": [1]})

    prediction = pd.Series([1])

    with pytest.raises(ValueError):
        world.build(
            features=features,
            prediction=prediction,
            confidence=1.5,
        )