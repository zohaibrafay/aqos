"""
Data provider interface.

Defines the contract that all AQOS market data providers must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class DataProviderInterface(ABC):
    """
    Interface for market data providers.

    Any data provider implementation must be able to fetch OHLCV data
    for a symbol and timeframe.
    """

    REQUIRED_COLUMNS = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> pd.DataFrame:
        """
        Fetch market data.

        Implementations may fetch from CSV, database, broker API,
        exchange API, or any other market data source.
        """

    @abstractmethod
    def supports(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        """
        Check whether the provider supports a symbol/timeframe pair.
        """

    def latest(
        self,
        symbol: str,
        timeframe: str,
    ) -> pd.Series:
        """
        Return the latest candle.
        """

        data = self.fetch(
            symbol=symbol,
            timeframe=timeframe,
            limit=1,
        )

        self.validate_market_data(data)

        return data.iloc[-1]

    def close_prices(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> list[float]:
        """
        Return close prices.
        """

        data = self.fetch(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        self.validate_market_data(data)

        return [
            float(value)
            for value in data["close"].tolist()
        ]

    def validate_market_data(
        self,
        data: pd.DataFrame,
    ) -> None:
        """
        Validate OHLCV market data.
        """

        if not isinstance(data, pd.DataFrame):
            raise TypeError("Market data must be a pandas DataFrame.")

        if data.empty:
            raise ValueError("Market data cannot be empty.")

        missing_columns = self.REQUIRED_COLUMNS.difference(data.columns)

        if missing_columns:
            raise ValueError(
                "Market data is missing required columns: "
                f"{sorted(missing_columns)}"
            )

    def _validate_request(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> None:
        """
        Validate a market data request.
        """

        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)

        if limit is not None:
            self._validate_limit(limit)

    def _validate_symbol(
        self,
        symbol: str,
    ) -> None:
        """
        Validate symbol.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

    def _validate_timeframe(
        self,
        timeframe: str,
    ) -> None:
        """
        Validate timeframe.
        """

        if not timeframe:
            raise ValueError("Timeframe cannot be empty.")

    def _validate_limit(
        self,
        limit: int,
    ) -> None:
        """
        Validate fetch limit.
        """

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")


__all__ = [
    "DataProviderInterface",
]