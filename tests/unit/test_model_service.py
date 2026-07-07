"""
Unit tests for ModelService.
"""

from pathlib import Path

import pandas as pd
import pytest

from aqos.models import BaseModel
from aqos.services import (
    ModelService,
    ModelSnapshot,
    PredictionSnapshot,
)


class DummyModel(BaseModel):

    def __init__(self) -> None:
        self.was_saved = False

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
        return pd.Series(
            [
                "buy"
                for _index in range(len(features))
            ]
        )

    def save(
        self,
        path: str,
    ) -> None:
        Path(path).write_text("dummy model", encoding="utf-8")
        self.was_saved = True

    @classmethod
    def load(
        cls,
        path: str,
    ):
        Path(path).read_text(encoding="utf-8")

        return cls()


def create_features() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open": [
                2000.0,
                2010.0,
            ],
            "close": [
                2005.0,
                2015.0,
            ],
        }
    )


def test_register_model():
    service = ModelService()

    snapshot = service.register(
        name="dummy-model",
        model=DummyModel(),
        metadata={"version": "1.0"},
    )

    assert isinstance(snapshot, ModelSnapshot)
    assert snapshot.name == "dummy-model"
    assert snapshot.model.name == "dummy"
    assert snapshot.metadata["version"] == "1.0"
    assert service.count() == 1


def test_get_model_snapshot():
    service = ModelService()

    service.register(
        name="dummy-model",
        model=DummyModel(),
    )

    snapshot = service.get("dummy-model")

    assert snapshot is not None
    assert snapshot.name == "dummy-model"


def test_get_missing_model_snapshot():
    service = ModelService()

    snapshot = service.get("missing")

    assert snapshot is None


def test_get_model_instance():
    service = ModelService()

    service.register(
        name="dummy-model",
        model=DummyModel(),
    )

    model = service.get_model("dummy-model")

    assert isinstance(model, DummyModel)


def test_get_missing_model_instance():
    service = ModelService()

    with pytest.raises(ValueError):
        service.get_model("missing")


def test_exists_true():
    service = ModelService()

    service.register(
        name="dummy-model",
        model=DummyModel(),
    )

    assert service.exists("dummy-model") is True


def test_exists_false():
    service = ModelService()

    assert service.exists("dummy-model") is False


def test_list_models():
    service = ModelService()

    service.register("model-b", DummyModel())
    service.register("model-a", DummyModel())

    models = service.list()

    assert len(models) == 2


def test_list_names():
    service = ModelService()

    service.register("model-b", DummyModel())
    service.register("model-a", DummyModel())

    assert service.list_names() == [
        "model-a",
        "model-b",
    ]


def test_remove_model():
    service = ModelService()

    service.register("dummy-model", DummyModel())

    service.remove("dummy-model")

    assert service.exists("dummy-model") is False
    assert service.count() == 0


def test_clear_models():
    service = ModelService()

    service.register("model-a", DummyModel())
    service.register("model-b", DummyModel())

    service.clear()

    assert service.count() == 0


def test_predict():
    service = ModelService()

    service.register(
        name="dummy-model",
        model=DummyModel(),
    )

    prediction = service.predict(
        name="dummy-model",
        features=create_features(),
    )

    assert isinstance(prediction, PredictionSnapshot)
    assert prediction.model_name == "dummy-model"
    assert prediction.predictions == [
        "buy",
        "buy",
    ]


def test_predict_missing_model():
    service = ModelService()

    with pytest.raises(ValueError):
        service.predict(
            name="missing",
            features=create_features(),
        )


def test_predict_empty_features():
    service = ModelService()

    service.register(
        name="dummy-model",
        model=DummyModel(),
    )

    with pytest.raises(ValueError):
        service.predict(
            name="dummy-model",
            features=pd.DataFrame(),
        )


def test_confidence():
    service = ModelService()

    confidence = service.confidence(
        probabilities=[
            0.1,
            0.8,
            0.1,
        ]
    )

    assert confidence == 0.8


def test_build_world_state():
    service = ModelService()

    world_state = service.build_world_state(
        features=create_features(),
        predictions=[
            "buy",
            "buy",
        ],
        confidence=0.8,
    )

    assert world_state["samples"] == 2
    assert world_state["prediction"] == [
        "buy",
        "buy",
    ]
    assert world_state["confidence"] == 0.8


def test_build_world_state_empty_features():
    service = ModelService()

    with pytest.raises(ValueError):
        service.build_world_state(
            features=pd.DataFrame(),
            predictions=[
                "buy",
            ],
            confidence=0.8,
        )


def test_build_world_state_empty_predictions():
    service = ModelService()

    with pytest.raises(ValueError):
        service.build_world_state(
            features=create_features(),
            predictions=[],
            confidence=0.8,
        )


def test_empty_model_name():
    service = ModelService()

    with pytest.raises(ValueError):
        service.register(
            name="",
            model=DummyModel(),
        )