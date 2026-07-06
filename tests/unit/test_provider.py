"""
Unit tests for AQOS Data Provider.
"""

import pandas as pd

from aqos.data import DataProvider


class MockProvider(DataProvider):
    @property
    def name(self) -> str:
        return "MockProvider"

    def load(
        self,
        symbol: str,
        timeframe: str,
    ) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "open": [1.0],
                "high": [2.0],
                "low": [0.5],
                "close": [1.5],
                "volume": [100],
            }
        )


def test_provider_name():

    provider = MockProvider()

    assert provider.name == "MockProvider"


def test_provider_load():

    provider = MockProvider()

    data = provider.load("XAUUSD", "H1")

    assert isinstance(data, pd.DataFrame)
    assert len(data) == 1


def test_provider_columns():

    provider = MockProvider()

    data = provider.load("XAUUSD", "H1")

    assert list(data.columns) == [
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]