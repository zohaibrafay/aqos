"""
Trend structure detection.

This module detects market structure using swing highs and swing lows,
and classifies the market as Uptrend, Downtrend, or Sideways.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class TrendStructure:
    """
    Detect market trend structure.
    """

    high_column: str = "high"
    low_column: str = "low"

    REQUIRED_COLUMNS = ("high", "low")

    def detect(self, dataframe: pd.DataFrame) -> str:
        """
        Detect market trend.

        Returns
        -------
        str
            "uptrend", "downtrend", or "sideways".
        """

        self._validate(dataframe)

        highs = dataframe[self.high_column]
        lows = dataframe[self.low_column]

        higher_highs = highs.is_monotonic_increasing
        higher_lows = lows.is_monotonic_increasing

        lower_highs = highs.is_monotonic_decreasing
        lower_lows = lows.is_monotonic_decreasing

        if higher_highs and higher_lows:
            return "uptrend"

        if lower_highs and lower_lows:
            return "downtrend"

        return "sideways"

    @staticmethod
    def _validate(dataframe: pd.DataFrame) -> None:
        if dataframe.empty:
            raise ValueError("DataFrame cannot be empty.")

        required = {"high", "low"}

        missing = required.difference(dataframe.columns)

        if missing:
            raise ValueError(
                f"Missing required columns: {sorted(missing)}"
            )


__all__ = ["TrendStructure"]