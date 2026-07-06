"""
AQOS Price Action Features.
"""

from __future__ import annotations

import pandas as pd

from aqos.features.base import Feature


class PriceActionFeatures(Feature):
    """
    Generates price action features.
    """

    @property
    def name(self) -> str:
        return "PriceActionFeatures"

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe["higher_high"] = (
            dataframe["high"] > dataframe["high"].shift(1)
        )

        dataframe["lower_low"] = (
            dataframe["low"] < dataframe["low"].shift(1)
        )

        dataframe["higher_close"] = (
            dataframe["close"] > dataframe["close"].shift(1)
        )

        dataframe["lower_close"] = (
            dataframe["close"] < dataframe["close"].shift(1)
        )

        dataframe["price_range"] = (
            dataframe["high"] - dataframe["low"]
        )

        dataframe["gap"] = (
            dataframe["open"] - dataframe["close"].shift(1)
        )

        return dataframe