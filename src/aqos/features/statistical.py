"""
AQOS Statistical Features.
"""

from __future__ import annotations

import pandas as pd

from aqos.features.base import Feature


class StatisticalFeatures(Feature):
    """
    Generates statistical features.
    """

    @property
    def name(self) -> str:
        return "StatisticalFeatures"

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        returns = dataframe["close"].pct_change()

        dataframe["rolling_mean_10"] = (
            dataframe["close"]
            .rolling(window=10, min_periods=1)
            .mean()
        )

        dataframe["rolling_std_10"] = (
            returns
            .rolling(window=10, min_periods=1)
            .std()
        )

        dataframe["rolling_min_10"] = (
            dataframe["low"]
            .rolling(window=10, min_periods=1)
            .min()
        )

        dataframe["rolling_max_10"] = (
            dataframe["high"]
            .rolling(window=10, min_periods=1)
            .max()
        )

        dataframe["z_score"] = (
            dataframe["close"] - dataframe["rolling_mean_10"]
        ) / dataframe["rolling_std_10"]

        return dataframe