"""
AQOS Market Data Cleaner.
"""

from __future__ import annotations

import pandas as pd


class DataCleaner:
    """
    Cleans OHLCV market data.
    """

    def clean(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and normalize market data.
        """

        dataframe = dataframe.copy()

        dataframe.drop_duplicates(
            subset="timestamp",
            keep="first",
            inplace=True,
        )

        dataframe.dropna(inplace=True)

        dataframe.sort_values(
            "timestamp",
            inplace=True,
        )

        dataframe.reset_index(
            drop=True,
            inplace=True,
        )

        return dataframe