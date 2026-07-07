"""
Market data service.

Provides a lightweight external-style market data service for storing
and retrieving OHLCV candles before they are passed into DataService.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(slots=True, frozen=True)
class MarketCandle:
    """
    Represents a single OHLCV market candle.
    """

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True, frozen=True)
class MarketDataFeed:
    """
    Represents market data for a symbol and timeframe.
    """

    symbol: str
    timeframe: str
    source: str
    candles: list[MarketCandle]
    metadata: dict[str, Any] = field(default_factory=dict)


class MarketDataService:
    """
    Service layer for external-style market data feeds.
    """

    def __init__(self) -> None:
        self._feeds: dict[tuple[str, str], MarketDataFeed] = {}

    def register_feed(
        self,
        symbol: str,
        timeframe: str,
        candles: list[MarketCandle],
        source: str = "local",
        metadata: dict[str, Any] | None = None,
    ) -> MarketDataFeed:
        """
        Register market candles for a symbol and timeframe.
        """

        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)
        self._validate_source(source)
        self._validate_candles(candles)

        sorted_candles = sorted(
            candles,
            key=lambda candle: candle.timestamp,
        )

        feed = MarketDataFeed(
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            candles=sorted_candles,
            metadata=metadata or {},
        )

        self._feeds[(symbol, timeframe)] = feed

        return feed

    def create_candle(
        self,
        timestamp: str,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        volume: float,
    ) -> MarketCandle:
        """
        Create a validated market candle.
        """

        candle = MarketCandle(
            timestamp=timestamp,
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )

        self._validate_candle(candle)

        return candle

    def get_feed(
        self,
        symbol: str,
        timeframe: str,
    ) -> MarketDataFeed | None:
        """
        Get a market data feed.
        """

        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)

        return self._feeds.get((symbol, timeframe))

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
    ) -> list[MarketCandle]:
        """
        Get candles for a symbol and timeframe.
        """

        feed = self.get_feed(
            symbol=symbol,
            timeframe=timeframe,
        )

        if feed is None:
            raise ValueError("Market data feed does not exist.")

        return list(feed.candles)

    def latest_candle(
        self,
        symbol: str,
        timeframe: str,
    ) -> MarketCandle:
        """
        Get the latest candle.
        """

        candles = self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
        )

        return candles[-1]

    def close_prices(
        self,
        symbol: str,
        timeframe: str,
    ) -> list[float]:
        """
        Return close prices.
        """

        candles = self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
        )

        return [
            candle.close
            for candle in candles
        ]

    def to_dataframe(
        self,
        symbol: str,
        timeframe: str,
    ) -> pd.DataFrame:
        """
        Convert a feed to a pandas DataFrame.
        """

        candles = self.get_candles(
            symbol=symbol,
            timeframe=timeframe,
        )

        return pd.DataFrame(
            [
                {
                    "timestamp": candle.timestamp,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in candles
            ]
        )

    def exists(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        """
        Check whether a feed exists.
        """

        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)

        return (symbol, timeframe) in self._feeds

    def list_symbols(self) -> list[str]:
        """
        Return registered symbols.
        """

        symbols = {
            symbol
            for symbol, _timeframe in self._feeds
        }

        return sorted(symbols)

    def list_timeframes(
        self,
        symbol: str,
    ) -> list[str]:
        """
        Return registered timeframes for a symbol.
        """

        self._validate_symbol(symbol)

        timeframes = {
            timeframe
            for feed_symbol, timeframe in self._feeds
            if feed_symbol == symbol
        }

        return sorted(timeframes)

    def count(self) -> int:
        """
        Return number of registered feeds.
        """

        return len(self._feeds)

    def remove(
        self,
        symbol: str,
        timeframe: str,
    ) -> None:
        """
        Remove a market data feed.
        """

        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)

        self._feeds.pop((symbol, timeframe), None)

    def clear(self) -> None:
        """
        Clear all market data feeds.
        """

        self._feeds.clear()

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

    def _validate_source(
        self,
        source: str,
    ) -> None:
        """
        Validate data source.
        """

        if not source:
            raise ValueError("Source cannot be empty.")

    def _validate_candles(
        self,
        candles: list[MarketCandle],
    ) -> None:
        """
        Validate candle list.
        """

        if not candles:
            raise ValueError("Candles cannot be empty.")

        for candle in candles:
            self._validate_candle(candle)

    def _validate_candle(
        self,
        candle: MarketCandle,
    ) -> None:
        """
        Validate a single OHLCV candle.
        """

        if not candle.timestamp:
            raise ValueError("Timestamp cannot be empty.")

        prices = [
            candle.open,
            candle.high,
            candle.low,
            candle.close,
        ]

        if any(price <= 0 for price in prices):
            raise ValueError("Candle prices must be greater than zero.")

        if candle.volume < 0:
            raise ValueError("Volume cannot be negative.")

        if candle.high < max(candle.open, candle.close, candle.low):
            raise ValueError("High price is invalid.")

        if candle.low > min(candle.open, candle.close, candle.high):
            raise ValueError("Low price is invalid.")


__all__ = [
    "MarketCandle",
    "MarketDataFeed",
    "MarketDataService",
]