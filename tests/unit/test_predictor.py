"""
Unit tests for Predictor.
"""

import pandas as pd
import pytest

from aqos.models.base import BaseModel
from aqos.models.predictor import Predictor


class DummyModel(BaseModel):

    @property
    def name(self) -> str:
        return "dummy"

    def fit(self, features: pd.DataFrame, target: pd.Series) -> None:
        pass

    def predict(self, features: pd.DataFrame) -> pd.Series:
        return pd.Series([1] * len(features))

    def save(self, path: str) -> None:
        pass

    @classmethod
    def load(cls, path: str):
        return cls()


def test_predict():
    predictor = Predictor(model=DummyModel())

    features = pd.DataFrame(
        {
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        }
    )

    predictions = predictor.predict(features)

    assert isinstance(predictions, pd.Series)
    assert predictions.tolist() == [1, 1, 1]


def test_empty_features():
    predictor = Predictor(model=DummyModel())

    with pytest.raises(ValueError):
        predictor.predict(pd.DataFrame())


def test_prediction_length():
    predictor = Predictor(model=DummyModel())

    features = pd.DataFrame(
        {
            "x": [10, 20, 30, 40],
        }
    )

    predictions = predictor.predict(features)

    assert len(predictions) == len(features)