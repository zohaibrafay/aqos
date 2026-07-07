"""
Model interface.

Defines the contract that all AQOS model implementations must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import pandas as pd


class ModelInterface(ABC):
    """
    Interface for AQOS models.

    Any model implementation must support training, prediction,
    persistence, and loading.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return model name.
        """

    @abstractmethod
    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> None:
        """
        Train the model.
        """

    @abstractmethod
    def predict(
        self,
        features: pd.DataFrame,
    ) -> pd.Series:
        """
        Run model prediction.
        """

    @abstractmethod
    def save(
        self,
        path: str,
    ) -> None:
        """
        Save the model.
        """

    @classmethod
    @abstractmethod
    def load(
        cls,
        path: str,
    ) -> "ModelInterface":
        """
        Load the model.
        """

    def predict_one(
        self,
        features: pd.DataFrame,
    ) -> Any:
        """
        Predict a single output from one-row features.
        """

        self.validate_features(features)

        if len(features) != 1:
            raise ValueError("predict_one requires exactly one feature row.")

        predictions = self.predict(features)

        if predictions.empty:
            raise ValueError("Prediction output cannot be empty.")

        return predictions.iloc[0]

    def validate_features(
        self,
        features: pd.DataFrame,
    ) -> None:
        """
        Validate model features.
        """

        if not isinstance(features, pd.DataFrame):
            raise TypeError("Features must be a pandas DataFrame.")

        if features.empty:
            raise ValueError("Features cannot be empty.")

    def validate_target(
        self,
        target: pd.Series,
    ) -> None:
        """
        Validate model target.
        """

        if not isinstance(target, pd.Series):
            raise TypeError("Target must be a pandas Series.")

        if target.empty:
            raise ValueError("Target cannot be empty.")

    def validate_training_data(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> None:
        """
        Validate model training data.
        """

        self.validate_features(features)
        self.validate_target(target)

        if len(features) != len(target):
            raise ValueError("Features and target must have the same length.")

    def validate_model_path(
        self,
        path: str,
    ) -> None:
        """
        Validate model path.
        """

        if not path:
            raise ValueError("Model path cannot be empty.")

    def ensure_parent_directory(
        self,
        path: str,
    ) -> None:
        """
        Ensure the parent directory exists for a model path.
        """

        self.validate_model_path(path)

        Path(path).parent.mkdir(
            parents=True,
            exist_ok=True,
        )


__all__ = [
    "ModelInterface",
]