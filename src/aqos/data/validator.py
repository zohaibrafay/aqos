"""
AQOS Market Data Validator.
"""

from __future__ import annotations

import pandas as pd


class DataValidator:
    """
    Validates OHLCV market data.
    """

    REQUIRED_COLUMNS = (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )

    def validate(self, dataframe: pd.DataFrame) -> None:
        """
        Validate an OHLCV DataFrame.

        Raises:
            ValueError: If validation fails.
        """

        self._validate_columns(dataframe)
        self._validate_missing_values(dataframe)
        self._validate_duplicates(dataframe)
        self._validate_timestamp_order(dataframe)
        self._validate_ohlc(dataframe)

    def _validate_columns(self, dataframe: pd.DataFrame) -> None:
        missing = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in dataframe.columns
        ]

        if missing:
            raise ValueError(
                f"Missing required columns: {missing}"
            )

    def _validate_missing_values(
        self,
        dataframe: pd.DataFrame,
    ) -> None:

        if dataframe.isnull().values.any():
            raise ValueError("Data contains missing values.")

    def _validate_duplicates(
        self,
        dataframe: pd.DataFrame,
    ) -> None:

        if dataframe["timestamp"].duplicated().any():
            raise ValueError("Duplicate timestamps found.")

    def _validate_timestamp_order(
        self,
        dataframe: pd.DataFrame,
    ) -> None:

        if not dataframe["timestamp"].is_monotonic_increasing:
            raise ValueError("Timestamps are not sorted.")

    def _validate_ohlc(
        self,
        dataframe: pd.DataFrame,
    ) -> None:

        invalid = (
            (dataframe["high"] < dataframe["open"])
            | (dataframe["high"] < dataframe["close"])
            | (dataframe["high"] < dataframe["low"])
            | (dataframe["low"] > dataframe["open"])
            | (dataframe["low"] > dataframe["close"])
            | (dataframe["low"] > dataframe["high"])
        )

        if invalid.any():
            raise ValueError("Invalid OHLC values found.")