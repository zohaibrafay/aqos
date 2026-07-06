"""
Unit tests for Trainer.
"""

import pandas as pd
import pytest

from aqos.learning.trainer import Trainer
from aqos.models.base import BaseModel


class DummyModel(BaseModel):
    def __init__(self):
        self.was_trained = False

    @property
    def name(self) -> str:
        return "dummy"

    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> None:
        self.was_trained = True

    def predict(
        self,
        features: pd.DataFrame,
    ) -> pd.Series:
        return pd.Series([1] * len(features))

    def save(
        self,
        path: str,
    ) -> None:
        pass

    @classmethod
    def load(
        cls,
        path: str,
    ):
        return cls()


def test_train():
    model = DummyModel()

    trainer = Trainer(model=model)

    x = pd.DataFrame(
        {
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        }
    )

    y = pd.Series([0, 1, 0])

    trained = trainer.train(x, y)

    assert trained is model
    assert model.was_trained is True


def test_empty_features():
    trainer = Trainer(model=DummyModel())

    with pytest.raises(ValueError):
        trainer.train(
            pd.DataFrame(),
            pd.Series([1]),
        )


def test_empty_target():
    trainer = Trainer(model=DummyModel())

    x = pd.DataFrame({"a": [1]})

    with pytest.raises(ValueError):
        trainer.train(
            x,
            pd.Series(dtype=int),
        )


def test_length_mismatch():
    trainer = Trainer(model=DummyModel())

    x = pd.DataFrame({"a": [1, 2]})

    y = pd.Series([1])

    with pytest.raises(ValueError):
        trainer.train(x, y)