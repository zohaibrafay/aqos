"""
AQOS Liquidity Zone Detection.
"""

from __future__ import annotations

import pandas as pd

from aqos.strategy.base import Strategy


class LiquidityDetector(Strategy):
    """
    Detect potential liquidity zones.
    """

    def __init__(self, window: int = 20) -> None:
        self.window = window

    @property
    def name(self) -> str:
        return "LiquidityDetector"

    def generate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        dataframe["buy_side_liquidity"] = (
            dataframe["high"]
            .rolling(
                window=self.window,
                min_periods=1,
            )
            .max()
        )

        dataframe["sell_side_liquidity"] = (
            dataframe["low"]
            .rolling(
                window=self.window,
                min_periods=1,
            )
            .min()
        )

        dataframe["near_buy_liquidity"] = (
            dataframe["close"]
            >= dataframe["buy_side_liquidity"] * 0.995
        )

        dataframe["near_sell_liquidity"] = (
            dataframe["close"]
            <= dataframe["sell_side_liquidity"] * 1.005
        )

        return dataframe