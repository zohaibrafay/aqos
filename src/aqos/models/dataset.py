"""
Dataset preparation utilities.

Converts feature and target data into a format suitable for model training.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class Dataset:
    """
    Dataset preparation utility.
    """

    target_column: str = "target"

    def prepare(
        self,
        dataframe: pd.DataFrame,
    ) -> tuple[pd.DataFrame, pd.Series]:
        """
        Split a DataFrame into features and target.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Input dataset.

        Returns
        -------
        tuple[pd.DataFrame, pd.Series]
            Features and target.
        """

        self._validate(dataframe)

        features = dataframe.drop(columns=[self.target_column]).copy()

        target = dataframe[self.target_column].copy()

        return features, target

    def _validate(
        self,
        dataframe: pd.DataFrame,
    ) -> None:
        """
        Validate dataset.
        """

        if dataframe.empty:
            raise ValueError("Dataset cannot be empty.")

        if self.target_column not in dataframe.columns:
            raise ValueError(
                f"Missing target column: '{self.target_column}'."
            )


__all__ = ["Dataset"]