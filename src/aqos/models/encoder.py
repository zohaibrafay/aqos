"""
Feature encoder.

Encodes feature data into a numeric representation suitable for
machine learning models.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class Encoder:
    """
    Feature encoder.
    """

    def encode(
        self,
        features: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Encode feature matrix.

        Parameters
        ----------
        features : pd.DataFrame
            Raw feature matrix.

        Returns
        -------
        pd.DataFrame
            Encoded feature matrix.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        return features.copy()


__all__ = ["Encoder"]