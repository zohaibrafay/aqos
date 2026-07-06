"""
Training engine.

Provides a common interface for training AQOS models.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aqos.models.base import BaseModel


@dataclass(slots=True)
class Trainer:
    """
    Model training engine.
    """

    model: BaseModel

    def train(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> BaseModel:
        """
        Train a model.

        Parameters
        ----------
        features : pd.DataFrame
            Training features.
        target : pd.Series
            Training target.

        Returns
        -------
        BaseModel
            Trained model.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        if target.empty:
            raise ValueError("Target cannot be empty.")

        if len(features) != len(target):
            raise ValueError(
                "Features and target must have the same length."
            )

        self.model.fit(features, target)

        return self.model


__all__ = ["Trainer"]