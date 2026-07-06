"""
AQOS Technical Indicators.
"""

from __future__ import annotations

import pandas as pd

from aqos.features.base import Feature


class TechnicalIndicators(Feature):
    """
    Basic technical indicators.
    """

    @property
    def name(self) -> str:
        return "TechnicalIndicators"

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe["sma_10"] = (
            dataframe["close"]
            .rolling(window=10, min_periods=1)
            .mean()
        )

        dataframe["ema_10"] = (
            dataframe["close"]
            .ewm(span=10, adjust=False)
            .mean()
        )

        dataframe["returns"] = dataframe["close"].pct_change()

        dataframe["log_returns"] = (
            1 + dataframe["returns"]
        ).apply(lambda x: pd.NA if pd.isna(x) else __import__("math").log(x))

        return dataframe