"""
AQOS Market Structure Features.
"""

from __future__ import annotations

import pandas as pd

from aqos.features.base import Feature


class MarketStructureFeatures(Feature):
    """
    Generates market structure features.
    """

    @property
    def name(self) -> str:
        return "MarketStructureFeatures"

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe["swing_high"] = (
            (dataframe["high"] > dataframe["high"].shift(1))
            & (dataframe["high"] > dataframe["high"].shift(-1))
        )

        dataframe["swing_low"] = (
            (dataframe["low"] < dataframe["low"].shift(1))
            & (dataframe["low"] < dataframe["low"].shift(-1))
        )

        dataframe["higher_high"] = (
            dataframe["high"] > dataframe["high"].cummax().shift(1)
        )

        dataframe["lower_low"] = (
            dataframe["low"] < dataframe["low"].cummin().shift(1)
        )

        dataframe["trend"] = "sideways"

        dataframe.loc[
            dataframe["higher_high"],
            "trend",
        ] = "uptrend"

        dataframe.loc[
            dataframe["lower_low"],
            "trend",
        ] = "downtrend"

        return dataframe