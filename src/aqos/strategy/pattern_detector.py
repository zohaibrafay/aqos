"""
AQOS Pattern Detector.

Detects classical candlestick patterns.
"""

from __future__ import annotations

import pandas as pd

from aqos.strategy.base import Strategy


class PatternDetector(Strategy):
    """
    Detect classical candlestick patterns.
    """

    @property
    def name(self) -> str:
        return "PatternDetector"

    def generate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()

        # -------------------------------------------------
        # Candle Properties
        # -------------------------------------------------

        body = (
            dataframe["close"] - dataframe["open"]
        ).abs()

        candle_range = (
            dataframe["high"] - dataframe["low"]
        )

        upper_wick = (
            dataframe["high"]
            - dataframe[["open", "close"]].max(axis=1)
        )

        lower_wick = (
            dataframe[["open", "close"]].min(axis=1)
            - dataframe["low"]
        )

        # -------------------------------------------------
        # Doji
        # -------------------------------------------------

        dataframe["doji"] = (
            body <= candle_range * 0.10
        )

        # -------------------------------------------------
        # Hammer
        # -------------------------------------------------

        dataframe["hammer"] = (
            (lower_wick >= body * 2)
            & (upper_wick <= body)
        )

        # -------------------------------------------------
        # Shooting Star
        # -------------------------------------------------

        dataframe["shooting_star"] = (
            (upper_wick >= body * 2)
            & (lower_wick <= body)
        )

        # -------------------------------------------------
        # Bullish Engulfing
        # -------------------------------------------------

        dataframe["bullish_engulfing"] = (
            (dataframe["close"] > dataframe["open"])
            &
            (dataframe["close"].shift(1)
             < dataframe["open"].shift(1))
            &
            (dataframe["open"]
             < dataframe["close"].shift(1))
            &
            (dataframe["close"]
             > dataframe["open"].shift(1))
        )

        # -------------------------------------------------
        # Bearish Engulfing
        # -------------------------------------------------

        dataframe["bearish_engulfing"] = (
            (dataframe["close"] < dataframe["open"])
            &
            (dataframe["close"].shift(1)
             > dataframe["open"].shift(1))
            &
            (dataframe["open"]
             > dataframe["close"].shift(1))
            &
            (dataframe["close"]
             < dataframe["open"].shift(1))
        )

        return dataframe