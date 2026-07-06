"""
AQOS Market Regime Detector.
"""

from __future__ import annotations

import pandas as pd

from aqos.strategy.base import Strategy


class MarketRegime(Strategy):
    """
    Detect the current market regime.
    """

    @property
    def name(self) -> str:
        return "MarketRegime"

    def generate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        sma20 = dataframe["close"].rolling(
            window=20,
            min_periods=1,
        ).mean()

        sma50 = dataframe["close"].rolling(
            window=50,
            min_periods=1,
        ).mean()

        dataframe["market_regime"] = "SIDEWAYS"

        dataframe.loc[
            sma20 > sma50,
            "market_regime",
        ] = "BULL"

        dataframe.loc[
            sma20 < sma50,
            "market_regime",
        ] = "BEAR"

        dataframe["trend_strength"] = (
            (sma20 - sma50).abs()
        )

        return dataframe