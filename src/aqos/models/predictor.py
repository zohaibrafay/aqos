"""
Prediction engine.

Provides a common interface for generating predictions using AQOS models.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aqos.models.base import BaseModel


@dataclass(slots=True)
class Predictor:
    """
    Prediction engine.

    Wraps an AQOS model and provides a consistent prediction interface.
    """

    model: BaseModel

    def predict(
        self,
        features: pd.DataFrame,
    ) -> pd.Series:
        """
        Generate predictions.

        Parameters
        ----------
        features : pd.DataFrame
            Feature matrix.

        Returns
        -------
        pd.Series
            Predicted values.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        return self.model.predict(features)


__all__ = ["Predictor"]