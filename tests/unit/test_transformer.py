"""
Unit tests for Transformer.
"""

import pandas as pd
import pytest

from aqos.models.transformer import Transformer


def test_transform_returns_dataframe():
    transformer = Transformer()

    features = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "close": [2, 3, 4],
        }
    )

    transformed = transformer.transform(features)

    assert isinstance(transformed, pd.DataFrame)


def test_shape_preserved():
    transformer = Transformer()

    features = pd.DataFrame(
        {
            "a": [1, 2],
            "b": [3, 4],
        }
    )

    transformed = transformer.transform(features)

    assert transformed.shape == features.shape


def test_columns_preserved():
    transformer = Transformer()

    features = pd.DataFrame(
        {
            "x": [1],
            "y": [2],
        }
    )

    transformed = transformer.transform(features)

    assert list(transformed.columns) == ["x", "y"]


def test_values_preserved():
    transformer = Transformer()

    features = pd.DataFrame(
        {
            "a": [10, 20],
            "b": [30, 40],
        }
    )

    transformed = transformer.transform(features)

    assert transformed.equals(features)


def test_empty_dataframe():
    transformer = Transformer()

    with pytest.raises(ValueError):
        transformer.transform(pd.DataFrame())