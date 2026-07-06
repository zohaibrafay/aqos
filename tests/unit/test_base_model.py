"""
Unit tests for BaseModel.
"""

import pandas as pd
import pytest

from aqos.models.base import BaseModel


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


def test_name():
    model = DummyModel()

    assert model.name == "dummy"


def test_predict_returns_series():
    model = DummyModel()

    df = pd.DataFrame({"x": [1, 2, 3]})

    prediction = model.predict(df)

    assert isinstance(prediction, pd.Series)
    assert len(prediction) == 3


def test_load():
    model = DummyModel.load("dummy.pkl")

    assert isinstance(model, DummyModel)


def test_fit():
    model = DummyModel()

    x = pd.DataFrame({"x": [1, 2]})
    y = pd.Series([0, 1])

    model.fit(x, y)


def test_save():
    model = DummyModel()

    model.save("dummy.pkl")