"""
Unit tests for Dataset.
"""

import pandas as pd
import pytest

from aqos.models.dataset import Dataset


def test_prepare_dataset():
    dataset = Dataset()

    df = pd.DataFrame(
        {
            "open": [1, 2, 3],
            "close": [2, 3, 4],
            "target": [1, 0, 1],
        }
    )

    features, target = dataset.prepare(df)

    assert list(features.columns) == ["open", "close"]
    assert len(features) == 3
    assert len(target) == 3


def test_target_values():
    dataset = Dataset()

    df = pd.DataFrame(
        {
            "feature": [10, 20],
            "target": [0, 1],
        }
    )

    _, target = dataset.prepare(df)

    assert target.tolist() == [0, 1]


def test_empty_dataframe():
    dataset = Dataset()

    with pytest.raises(ValueError):
        dataset.prepare(pd.DataFrame())


def test_missing_target():
    dataset = Dataset()

    df = pd.DataFrame(
        {
            "feature": [1, 2, 3],
        }
    )

    with pytest.raises(ValueError):
        dataset.prepare(df)


def test_custom_target_column():
    dataset = Dataset(target_column="label")

    df = pd.DataFrame(
        {
            "x": [1, 2],
            "y": [3, 4],
            "label": [0, 1],
        }
    )

    features, target = dataset.prepare(df)

    assert list(features.columns) == ["x", "y"]
    assert target.tolist() == [0, 1]