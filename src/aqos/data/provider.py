"""
AQOS Data Provider Interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataProvider(ABC):
    """
    Abstract base class for all market data providers.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the provider name.
        """
        ...

    @abstractmethod
    def load(
        self,
        symbol: str,
        timeframe: str,
    ) -> pd.DataFrame:
        """
        Load market data.

        Args:
            symbol: Trading symbol (e.g. XAUUSD)
            timeframe: Timeframe (e.g. M1, H1, D1)

        Returns:
            Pandas DataFrame containing OHLCV data.
        """
        raise NotImplementedError