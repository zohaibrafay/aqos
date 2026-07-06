"""
Unit tests for Encoder.
"""

import pandas as pd
import pytest

from aqos.models.encoder import Encoder


def test_encode_returns_dataframe():
    encoder = Encoder()

    features = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "close": [2, 3, 4],
        }
    )

    encoded = encoder.encode(features)

    assert isinstance(encoded, pd.DataFrame)


def test_shape_preserved():
    encoder = Encoder()

    features = pd.DataFrame(
        {
            "a": [1, 2],
            "b": [3, 4],
        }
    )

    encoded = encoder.encode(features)

    assert encoded.shape == features.shape


def test_columns_preserved():
    encoder = Encoder()

    features = pd.DataFrame(
        {
            "x": [1],
            "y": [2],
        }
    )

    encoded = encoder.encode(features)

    assert list(encoded.columns) == ["x", "y"]


def test_values_preserved():
    encoder = Encoder()

    features = pd.DataFrame(
        {
            "a": [10, 20],
            "b": [30, 40],
        }
    )

    encoded = encoder.encode(features)

    assert encoded.equals(features)


def test_empty_dataframe():
    encoder = Encoder()

    with pytest.raises(ValueError):
        encoder.encode(pd.DataFrame())