"""
Feature transformer.

Applies transformations to encoded features before they are passed
to prediction models.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class Transformer:
    """
    Feature transformer.
    """

    def transform(
        self,
        features: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Transform feature matrix.

        Parameters
        ----------
        features : pd.DataFrame
            Encoded feature matrix.

        Returns
        -------
        pd.DataFrame
            Transformed feature matrix.
        """

        if features.empty:
            raise ValueError("Features cannot be empty.")

        return features.copy()


__all__ = ["Transformer"]