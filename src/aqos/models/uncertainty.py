"""
Uncertainty engine.

Provides confidence estimation for model predictions.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class UncertaintyEngine:
    """
    Estimate prediction confidence.
    """

    def confidence(
        self,
        probabilities: pd.Series,
    ) -> float:
        """
        Calculate prediction confidence.

        Parameters
        ----------
        probabilities : pd.Series
            Probability scores.

        Returns
        -------
        float
            Confidence score between 0.0 and 1.0.
        """

        if probabilities.empty:
            raise ValueError("Probabilities cannot be empty.")

        if ((probabilities < 0) | (probabilities > 1)).any():
            raise ValueError(
                "Probability values must be between 0 and 1."
            )

        return float(probabilities.max())


__all__ = ["UncertaintyEngine"]