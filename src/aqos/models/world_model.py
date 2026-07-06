"""
World model.

Maintains a high-level representation of the current market state by
combining the outputs of the encoder, transformer, predictor,
similarity engine, and uncertainty engine.

This is intentionally lightweight in Sprint 005 and will be expanded
during later AI and Learning sprints.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class WorldModel:
    """
    World model.

    Represents the current market understanding.
    """

    def build(
        self,
        features: pd.DataFrame,
        prediction: pd.Series,
        confidence: float,
    ) -> dict:
        """
        Build the current world state.

        Parameters
        ----------
        features : pd.DataFrame
            Current feature matrix.

        prediction : pd.Series
            Model predictions.

        confidence : float
            Prediction confidence.

        Returns
        -------
        dict
            World state.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        if prediction.empty:
            raise ValueError("Prediction cannot be empty.")

        if len(features) != len(prediction):
            raise ValueError(
                "Features and prediction must have the same length."
            )

        if not 0.0 <= confidence <= 1.0:
            raise ValueError(
                "Confidence must be between 0 and 1."
            )

        return {
            "samples": len(features),
            "prediction": prediction.tolist(),
            "confidence": confidence,
        }


__all__ = ["WorldModel"]