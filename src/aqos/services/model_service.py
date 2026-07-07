"""
Model service.

Provides a service-level interface for registering models,
running predictions, calculating confidence, and building world states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from aqos.models import (
    BaseModel,
    Predictor,
    UncertaintyEngine,
    WorldModel,
)


@dataclass(slots=True, frozen=True)
class ModelSnapshot:
    """
    Represents a registered model.
    """

    name: str
    model: BaseModel
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class PredictionSnapshot:
    """
    Represents prediction output from a registered model.
    """

    model_name: str
    predictions: list[Any]


class ModelService:
    """
    Service layer for AQOS models.
    """

    def __init__(self) -> None:
        self._models: dict[str, ModelSnapshot] = {}
        self._uncertainty = UncertaintyEngine()
        self._world_model = WorldModel()

    def register(
        self,
        name: str,
        model: BaseModel,
        metadata: dict[str, Any] | None = None,
    ) -> ModelSnapshot:
        """
        Register a model.
        """

        self._validate_name(name)

        snapshot = ModelSnapshot(
            name=name,
            model=model,
            metadata=metadata or {},
        )

        self._models[name] = snapshot

        return snapshot

    def get(
        self,
        name: str,
    ) -> ModelSnapshot | None:
        """
        Get a registered model snapshot.
        """

        self._validate_name(name)

        return self._models.get(name)

    def get_model(
        self,
        name: str,
    ) -> BaseModel:
        """
        Get a registered model instance.
        """

        snapshot = self.get(name)

        if snapshot is None:
            raise ValueError("Model does not exist.")

        return snapshot.model

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a model exists.
        """

        self._validate_name(name)

        return name in self._models

    def list(self) -> list[ModelSnapshot]:
        """
        Return all registered model snapshots.
        """

        return list(self._models.values())

    def list_names(self) -> list[str]:
        """
        Return registered model names.
        """

        return sorted(self._models.keys())

    def count(self) -> int:
        """
        Return the number of registered models.
        """

        return len(self._models)

    def remove(
        self,
        name: str,
    ) -> None:
        """
        Remove a registered model.
        """

        self._validate_name(name)

        self._models.pop(name, None)

    def clear(self) -> None:
        """
        Clear all registered models.
        """

        self._models.clear()

    def predict(
        self,
        name: str,
        features: pd.DataFrame,
    ) -> PredictionSnapshot:
        """
        Run prediction using a registered model.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        model = self.get_model(name)

        predictor = Predictor(model=model)
        predictions = predictor.predict(features)

        return PredictionSnapshot(
            model_name=name,
            predictions=self._to_list(predictions),
        )

    def confidence(
        self,
        probabilities: list[float],
    ) -> float:
        """
        Calculate prediction confidence.
        """

        probability_series = pd.Series(probabilities)

        return self._uncertainty.confidence(probability_series)

    def build_world_state(
        self,
        features: pd.DataFrame,
        predictions: list[Any],
        confidence: float,
    ) -> dict:
        """
        Build a world-state representation.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        if not predictions:
            raise ValueError("Predictions cannot be empty.")

        prediction_series = pd.Series(predictions)

        return self._world_model.build(
            features=features,
            prediction=prediction_series,
            confidence=confidence,
        )

    def _to_list(
        self,
        values,
    ) -> list[Any]:
        """
        Convert prediction output to list.
        """

        if hasattr(values, "tolist"):
            return values.tolist()

        return list(values)

    def _validate_name(
        self,
        name: str,
    ) -> None:
        """
        Validate model name.
        """

        if not name:
            raise ValueError("Model name cannot be empty.")


__all__ = [
    "ModelService",
    "ModelSnapshot",
    "PredictionSnapshot",
]