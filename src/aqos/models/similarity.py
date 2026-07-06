"""
Similarity engine.

Provides similarity scoring between feature vectors.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class SimilarityEngine:
    """
    Compute similarity between two feature vectors.
    """

    def score(
        self,
        first: pd.Series,
        second: pd.Series,
    ) -> float:
        """
        Calculate similarity score.

        Parameters
        ----------
        first : pd.Series
            First feature vector.
        second : pd.Series
            Second feature vector.

        Returns
        -------
        float
            Similarity score in range [0.0, 1.0].
        """

        if first.empty or second.empty:
            raise ValueError("Input vectors cannot be empty.")

        if len(first) != len(second):
            raise ValueError("Vectors must have the same length.")

        matches = (first == second).sum()

        return matches / len(first)


__all__ = ["SimilarityEngine"]