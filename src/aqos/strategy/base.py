"""
AQOS Strategy Base Interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """
    Base interface for all trading strategies.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the strategy name.
        """
        ...

    @abstractmethod
    def generate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Generate trading signals.

        Parameters
        ----------
        dataframe : pd.DataFrame
            Market data with engineered features.

        Returns
        -------
        pd.DataFrame
            Market data enriched with trading signals.
        """
        raise NotImplementedError