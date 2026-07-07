"""
Unit tests for DataProviderInterface.
"""

import pandas as pd
import pytest

from aqos.interfaces import DataProviderInterface


class DummyDataProvider(DataProviderInterface):
    """
    Test implementation of DataProviderInterface.
    """

    def __init__(self) -> None:
        self._data = pd.DataFrame(
            {
                "timestamp": [
                    "2026-01-02",
                    "2026-01-01",
                ],
                "open": [
                    2010.0,
                    2000.0,
                ],
                "high": [
                    2020.0,
                    2010.0,
                ],
                "low": [
                    2005.0,
                    1990.0,
                ],
                "close": [
                    2015.0,
                    2005.0,
                ],
                "volume": [
                    1500.0,
                    1000.0,
                ],
            }
        )

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
    ) -> pd.DataFrame:
        self._validate_request(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
        )

        if not self.supports(symbol, timeframe):
            raise ValueError("Symbol/timeframe is not supported.")

        data = self._data.copy()
        data = data.sort_values("timestamp")
        data = data.reset_index(drop=True)

        if limit is not None:
            data = data.tail(limit)
            data = data.reset_index(drop=True)

        return data

    def supports(
        self,
        symbol: str,
        timeframe: str,
    ) -> bool:
        return symbol == "XAUUSD" and timeframe == "H1"


def test_data_provider_interface_cannot_be_instantiated():
    with pytest.raises(TypeError):
        DataProviderInterface()


def test_dummy_provider_is_interface_instance():
    provider = DummyDataProvider()

    assert isinstance(provider, DataProviderInterface)


def test_fetch_market_data():
    provider = DummyDataProvider()

    data = provider.fetch(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert isinstance(data, pd.DataFrame)
    assert len(data) == 2
    assert data.iloc[0]["timestamp"] == "2026-01-01"
    assert data.iloc[1]["timestamp"] == "2026-01-02"


def test_fetch_market_data_with_limit():
    provider = DummyDataProvider()

    data = provider.fetch(
        symbol="XAUUSD",
        timeframe="H1",
        limit=1,
    )

    assert len(data) == 1
    assert data.iloc[0]["timestamp"] == "2026-01-02"


def test_supports_true():
    provider = DummyDataProvider()

    assert provider.supports("XAUUSD", "H1") is True


def test_supports_false():
    provider = DummyDataProvider()

    assert provider.supports("EURUSD", "H1") is False


def test_fetch_unsupported_symbol_timeframe():
    provider = DummyDataProvider()

    with pytest.raises(ValueError):
        provider.fetch(
            symbol="EURUSD",
            timeframe="H1",
        )


def test_latest():
    provider = DummyDataProvider()

    latest = provider.latest(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert latest["timestamp"] == "2026-01-02"
    assert latest["close"] == 2015.0


def test_close_prices():
    provider = DummyDataProvider()

    prices = provider.close_prices(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert prices == [
        2005.0,
        2015.0,
    ]


def test_close_prices_with_limit():
    provider = DummyDataProvider()

    prices = provider.close_prices(
        symbol="XAUUSD",
        timeframe="H1",
        limit=1,
    )

    assert prices == [
        2015.0,
    ]


def test_validate_market_data():
    provider = DummyDataProvider()

    data = provider.fetch(
        symbol="XAUUSD",
        timeframe="H1",
    )

    provider.validate_market_data(data)


def test_validate_market_data_rejects_non_dataframe():
    provider = DummyDataProvider()

    with pytest.raises(TypeError):
        provider.validate_market_data(["not", "a", "dataframe"])


def test_validate_market_data_rejects_empty_dataframe():
    provider = DummyDataProvider()

    with pytest.raises(ValueError):
        provider.validate_market_data(pd.DataFrame())


def test_validate_market_data_rejects_missing_columns():
    provider = DummyDataProvider()

    data = pd.DataFrame(
        {
            "timestamp": [
                "2026-01-01",
            ],
            "close": [
                2000.0,
            ],
        }
    )

    with pytest.raises(ValueError):
        provider.validate_market_data(data)


def test_empty_symbol():
    provider = DummyDataProvider()

    with pytest.raises(ValueError):
        provider.fetch(
            symbol="",
            timeframe="H1",
        )


def test_empty_timeframe():
    provider = DummyDataProvider()

    with pytest.raises(ValueError):
        provider.fetch(
            symbol="XAUUSD",
            timeframe="",
        )


def test_invalid_limit():
    provider = DummyDataProvider()

    with pytest.raises(ValueError):
        provider.fetch(
            symbol="XAUUSD",
            timeframe="H1",
            limit=0,
        )