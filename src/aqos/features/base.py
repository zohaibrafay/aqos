"""
AQOS Feature Base Interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Feature(ABC):
    """
    Base interface for all feature engineering components.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the feature name.
        """
        ...

    @abstractmethod
    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Transform the input DataFrame by adding feature columns.

        Args:
            dataframe: OHLCV market data.

        Returns:
            DataFrame with engineered features.
        """
        raise NotImplementedError