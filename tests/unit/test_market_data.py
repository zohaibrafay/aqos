"""
Unit tests for MarketDataService.
"""

import pandas as pd
import pytest

from aqos.services import (
    MarketCandle,
    MarketDataFeed,
    MarketDataService,
)


def create_service() -> MarketDataService:
    return MarketDataService()


def create_candles() -> list[MarketCandle]:
    service = create_service()

    return [
        service.create_candle(
            timestamp="2026-01-02",
            open_price=2010.0,
            high_price=2020.0,
            low_price=2005.0,
            close_price=2015.0,
            volume=1500.0,
        ),
        service.create_candle(
            timestamp="2026-01-01",
            open_price=2000.0,
            high_price=2010.0,
            low_price=1990.0,
            close_price=2005.0,
            volume=1000.0,
        ),
    ]


def test_create_candle():
    service = create_service()

    candle = service.create_candle(
        timestamp="2026-01-01",
        open_price=2000.0,
        high_price=2010.0,
        low_price=1990.0,
        close_price=2005.0,
        volume=1000.0,
    )

    assert isinstance(candle, MarketCandle)
    assert candle.timestamp == "2026-01-01"
    assert candle.close == 2005.0


def test_register_feed():
    service = create_service()

    feed = service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
        source="local",
        metadata={"provider": "test"},
    )

    assert isinstance(feed, MarketDataFeed)
    assert feed.symbol == "XAUUSD"
    assert feed.timeframe == "H1"
    assert feed.source == "local"
    assert feed.metadata["provider"] == "test"
    assert service.count() == 1


def test_register_feed_sorts_candles():
    service = create_service()

    feed = service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
    )

    assert feed.candles[0].timestamp == "2026-01-01"
    assert feed.candles[1].timestamp == "2026-01-02"


def test_get_feed():
    service = create_service()

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
    )

    feed = service.get_feed(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert feed is not None
    assert feed.symbol == "XAUUSD"


def test_get_missing_feed():
    service = create_service()

    feed = service.get_feed(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert feed is None


def test_get_candles():
    service = create_service()

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
    )

    candles = service.get_candles(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert len(candles) == 2
    assert candles[0].timestamp == "2026-01-01"


def test_get_candles_missing_feed():
    service = create_service()

    with pytest.raises(ValueError):
        service.get_candles(
            symbol="XAUUSD",
            timeframe="H1",
        )


def test_latest_candle():
    service = create_service()

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
    )

    candle = service.latest_candle(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert candle.timestamp == "2026-01-02"
    assert candle.close == 2015.0


def test_close_prices():
    service = create_service()

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
    )

    prices = service.close_prices(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert prices == [
        2005.0,
        2015.0,
    ]


def test_to_dataframe():
    service = create_service()

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
    )

    dataframe = service.to_dataframe(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert isinstance(dataframe, pd.DataFrame)
    assert list(dataframe.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert len(dataframe) == 2


def test_exists_true():
    service = create_service()

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=create_candles(),
    )

    assert service.exists("XAUUSD", "H1") is True


def test_exists_false():
    service = create_service()

    assert service.exists("XAUUSD", "H1") is False


def test_list_symbols():
    service = create_service()

    service.register_feed("XAUUSD", "H1", create_candles())
    service.register_feed("EURUSD", "M15", create_candles())

    assert service.list_symbols() == [
        "EURUSD",
        "XAUUSD",
    ]


def test_list_timeframes():
    service = create_service()

    service.register_feed("XAUUSD", "H1", create_candles())
    service.register_feed("XAUUSD", "M15", create_candles())

    assert service.list_timeframes("XAUUSD") == [
        "H1",
        "M15",
    ]


def test_remove_feed():
    service = create_service()

    service.register_feed("XAUUSD", "H1", create_candles())

    service.remove("XAUUSD", "H1")

    assert service.exists("XAUUSD", "H1") is False
    assert service.count() == 0


def test_clear_feeds():
    service = create_service()

    service.register_feed("XAUUSD", "H1", create_candles())
    service.register_feed("EURUSD", "M15", create_candles())

    service.clear()

    assert service.count() == 0


def test_empty_symbol():
    service = create_service()

    with pytest.raises(ValueError):
        service.register_feed(
            symbol="",
            timeframe="H1",
            candles=create_candles(),
        )


def test_empty_timeframe():
    service = create_service()

    with pytest.raises(ValueError):
        service.register_feed(
            symbol="XAUUSD",
            timeframe="",
            candles=create_candles(),
        )


def test_empty_source():
    service = create_service()

    with pytest.raises(ValueError):
        service.register_feed(
            symbol="XAUUSD",
            timeframe="H1",
            candles=create_candles(),
            source="",
        )


def test_empty_candles():
    service = create_service()

    with pytest.raises(ValueError):
        service.register_feed(
            symbol="XAUUSD",
            timeframe="H1",
            candles=[],
        )


def test_invalid_empty_timestamp():
    service = create_service()

    with pytest.raises(ValueError):
        service.create_candle(
            timestamp="",
            open_price=2000.0,
            high_price=2010.0,
            low_price=1990.0,
            close_price=2005.0,
            volume=1000.0,
        )


def test_invalid_price():
    service = create_service()

    with pytest.raises(ValueError):
        service.create_candle(
            timestamp="2026-01-01",
            open_price=0,
            high_price=2010.0,
            low_price=1990.0,
            close_price=2005.0,
            volume=1000.0,
        )


def test_invalid_negative_volume():
    service = create_service()

    with pytest.raises(ValueError):
        service.create_candle(
            timestamp="2026-01-01",
            open_price=2000.0,
            high_price=2010.0,
            low_price=1990.0,
            close_price=2005.0,
            volume=-1.0,
        )


def test_invalid_high_price():
    service = create_service()

    with pytest.raises(ValueError):
        service.create_candle(
            timestamp="2026-01-01",
            open_price=2000.0,
            high_price=1995.0,
            low_price=1990.0,
            close_price=2005.0,
            volume=1000.0,
        )


def test_invalid_low_price():
    service = create_service()

    with pytest.raises(ValueError):
        service.create_candle(
            timestamp="2026-01-01",
            open_price=2000.0,
            high_price=2010.0,
            low_price=2006.0,
            close_price=2005.0,
            volume=1000.0,
        )