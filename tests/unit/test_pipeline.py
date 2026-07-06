"""
Unit tests for LearningPipeline.
"""

import pandas as pd
import pytest

from aqos.learning.cross_validation import CrossValidation
from aqos.learning.loss import Loss
from aqos.learning.optimizer import Optimizer
from aqos.learning.pipeline import LearningPipeline
from aqos.learning.scheduler import Scheduler
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


def create_pipeline() -> LearningPipeline:
    return LearningPipeline(
        trainer=Trainer(model=DummyModel()),
        optimizer=Optimizer(),
        scheduler=Scheduler(),
        loss=Loss(),
        cross_validation=CrossValidation(),
    )


def test_run_pipeline():
    pipeline = create_pipeline()

    features = pd.DataFrame(
        {
            "a": [1, 2, 3],
            "b": [4, 5, 6],
        }
    )

    target = pd.Series([0, 1, 0])

    model = pipeline.run(
        features=features,
        target=target,
    )

    assert model.was_trained is True


def test_empty_features():
    pipeline = create_pipeline()

    with pytest.raises(ValueError):
        pipeline.run(
            pd.DataFrame(),
            pd.Series([1]),
        )


def test_empty_target():
    pipeline = create_pipeline()

    features = pd.DataFrame({"a": [1]})

    with pytest.raises(ValueError):
        pipeline.run(
            features,
            pd.Series(dtype=int),
        )


def test_length_mismatch():
    pipeline = create_pipeline()

    features = pd.DataFrame({"a": [1, 2]})

    target = pd.Series([1])

    with pytest.raises(ValueError):
        pipeline.run(
            features,
            target,
        )


def test_invalid_optimizer():
    pipeline = create_pipeline()

    pipeline.optimizer.learning_rate = 0

    features = pd.DataFrame({"a": [1]})
    target = pd.Series([1])

    with pytest.raises(ValueError):
        pipeline.run(
            features,
            target,
        )