"""
Unit tests for ModelInterface.
"""

from pathlib import Path

import pandas as pd
import pytest

from aqos.interfaces import ModelInterface


class DummyModel(ModelInterface):
    """
    Test implementation of ModelInterface.
    """

    def __init__(self) -> None:
        self.was_trained = False
        self.was_saved = False

    @property
    def name(self) -> str:
        return "dummy-model"

    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> None:
        self.validate_training_data(
            features=features,
            target=target,
        )

        self.was_trained = True

    def predict(
        self,
        features: pd.DataFrame,
    ) -> pd.Series:
        self.validate_features(features)

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
        self.ensure_parent_directory(path)

        Path(path).write_text(
            "dummy model",
            encoding="utf-8",
        )

        self.was_saved = True

    @classmethod
    def load(
        cls,
        path: str,
    ) -> "DummyModel":
        if not path:
            raise ValueError("Model path cannot be empty.")

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


def create_target() -> pd.Series:
    return pd.Series(
        [
            "buy",
            "sell",
        ]
    )


def test_model_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ModelInterface()


def test_dummy_model_is_interface_instance():
    model = DummyModel()

    assert isinstance(model, ModelInterface)


def test_model_name():
    model = DummyModel()

    assert model.name == "dummy-model"


def test_fit_model():
    model = DummyModel()

    model.fit(
        features=create_features(),
        target=create_target(),
    )

    assert model.was_trained is True


def test_predict_model():
    model = DummyModel()

    predictions = model.predict(
        features=create_features(),
    )

    assert predictions.tolist() == [
        "buy",
        "buy",
    ]


def test_predict_one():
    model = DummyModel()

    prediction = model.predict_one(
        features=pd.DataFrame(
            {
                "open": [
                    2000.0,
                ],
                "close": [
                    2005.0,
                ],
            }
        )
    )

    assert prediction == "buy"


def test_predict_one_rejects_multiple_rows():
    model = DummyModel()

    with pytest.raises(ValueError):
        model.predict_one(
            features=create_features(),
        )


def test_save_model(tmp_path):
    model = DummyModel()

    path = tmp_path / "models" / "dummy.txt"

    model.save(str(path))

    assert model.was_saved is True
    assert path.exists() is True


def test_load_model(tmp_path):
    path = tmp_path / "dummy.txt"
    path.write_text(
        "dummy model",
        encoding="utf-8",
    )

    model = DummyModel.load(str(path))

    assert isinstance(model, DummyModel)


def test_validate_features():
    model = DummyModel()

    model.validate_features(create_features())


def test_validate_features_rejects_non_dataframe():
    model = DummyModel()

    with pytest.raises(TypeError):
        model.validate_features(["not", "a", "dataframe"])


def test_validate_features_rejects_empty_dataframe():
    model = DummyModel()

    with pytest.raises(ValueError):
        model.validate_features(pd.DataFrame())


def test_validate_target():
    model = DummyModel()

    model.validate_target(create_target())


def test_validate_target_rejects_non_series():
    model = DummyModel()

    with pytest.raises(TypeError):
        model.validate_target(["buy", "sell"])


def test_validate_target_rejects_empty_series():
    model = DummyModel()

    with pytest.raises(ValueError):
        model.validate_target(pd.Series(dtype=str))


def test_validate_training_data():
    model = DummyModel()

    model.validate_training_data(
        features=create_features(),
        target=create_target(),
    )


def test_validate_training_data_rejects_length_mismatch():
    model = DummyModel()

    with pytest.raises(ValueError):
        model.validate_training_data(
            features=create_features(),
            target=pd.Series(["buy"]),
        )


def test_validate_model_path():
    model = DummyModel()

    model.validate_model_path("models/dummy.txt")


def test_validate_model_path_rejects_empty_path():
    model = DummyModel()

    with pytest.raises(ValueError):
        model.validate_model_path("")


def test_ensure_parent_directory(tmp_path):
    model = DummyModel()

    path = tmp_path / "models" / "dummy.txt"

    model.ensure_parent_directory(str(path))

    assert path.parent.exists() is True


def test_save_rejects_empty_path():
    model = DummyModel()

    with pytest.raises(ValueError):
        model.save("")


def test_load_rejects_empty_path():
    with pytest.raises(ValueError):
        DummyModel.load("")