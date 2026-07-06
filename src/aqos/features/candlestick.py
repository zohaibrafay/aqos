"""
AQOS Candlestick Features.
"""

from __future__ import annotations

import pandas as pd

from aqos.features.base import Feature


class CandlestickFeatures(Feature):
    """
    Generates candlestick-based features.
    """

    @property
    def name(self) -> str:
        return "CandlestickFeatures"

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe["body"] = (
            dataframe["close"] - dataframe["open"]
        )

        dataframe["body_size"] = dataframe["body"].abs()

        dataframe["upper_wick"] = (
            dataframe["high"]
            - dataframe[["open", "close"]].max(axis=1)
        )

        dataframe["lower_wick"] = (
            dataframe[["open", "close"]].min(axis=1)
            - dataframe["low"]
        )

        dataframe["bullish"] = (
            dataframe["close"] > dataframe["open"]
        )

        dataframe["bearish"] = (
            dataframe["close"] < dataframe["open"]
        )

        return dataframe