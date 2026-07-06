"""
AQOS Support & Resistance Detection.
"""

from __future__ import annotations

import pandas as pd

from aqos.strategy.base import Strategy


class SupportResistance(Strategy):
    """
    Detect support and resistance levels using rolling highs and lows.
    """

    def __init__(self, window: int = 20) -> None:
        self.window = window

    @property
    def name(self) -> str:
        return "SupportResistance"

    def generate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe["support"] = (
            dataframe["low"]
            .rolling(
                window=self.window,
                min_periods=1,
            )
            .min()
        )

        dataframe["resistance"] = (
            dataframe["high"]
            .rolling(
                window=self.window,
                min_periods=1,
            )
            .max()
        )

        dataframe["distance_to_support"] = (
            dataframe["close"]
            - dataframe["support"]
        )

        dataframe["distance_to_resistance"] = (
            dataframe["resistance"]
            - dataframe["close"]
        )

        return dataframe