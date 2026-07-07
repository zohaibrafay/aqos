"""
Unit tests for DataService.
"""

import pandas as pd
import pytest

from aqos.services import DataService, DatasetSnapshot


def create_market_data() -> pd.DataFrame:
    return pd.DataFrame(
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
                1500,
                1000,
            ],
        }
    )


def test_register_dataset():
    service = DataService()

    snapshot = service.register(
        name="xauusd-h1",
        symbol="XAUUSD",
        timeframe="H1",
        data=create_market_data(),
    )

    assert isinstance(snapshot, DatasetSnapshot)
    assert snapshot.name == "xauusd-h1"
    assert snapshot.symbol == "XAUUSD"
    assert snapshot.timeframe == "H1"
    assert service.count() == 1


def test_register_sorts_data_by_timestamp():
    service = DataService()

    snapshot = service.register(
        name="xauusd-h1",
        symbol="XAUUSD",
        timeframe="H1",
        data=create_market_data(),
    )

    assert snapshot.data.iloc[0]["timestamp"] == "2026-01-01"
    assert snapshot.data.iloc[1]["timestamp"] == "2026-01-02"


def test_get_dataset():
    service = DataService()

    service.register(
        name="xauusd-h1",
        symbol="XAUUSD",
        timeframe="H1",
        data=create_market_data(),
    )

    snapshot = service.get("xauusd-h1")

    assert snapshot is not None
    assert snapshot.symbol == "XAUUSD"


def test_get_missing_dataset():
    service = DataService()

    snapshot = service.get("missing")

    assert snapshot is None


def test_exists_true():
    service = DataService()

    service.register(
        name="xauusd-h1",
        symbol="XAUUSD",
        timeframe="H1",
        data=create_market_data(),
    )

    assert service.exists("xauusd-h1") is True


def test_exists_false():
    service = DataService()

    assert service.exists("xauusd-h1") is False


def test_list_datasets():
    service = DataService()

    service.register("xauusd-h1", "XAUUSD", "H1", create_market_data())
    service.register("eurusd-m15", "EURUSD", "M15", create_market_data())

    datasets = service.list()

    assert len(datasets) == 2


def test_list_names():
    service = DataService()

    service.register("xauusd-h1", "XAUUSD", "H1", create_market_data())
    service.register("eurusd-m15", "EURUSD", "M15", create_market_data())

    assert service.list_names() == [
        "eurusd-m15",
        "xauusd-h1",
    ]


def test_list_symbols():
    service = DataService()

    service.register("xauusd-h1", "XAUUSD", "H1", create_market_data())
    service.register("eurusd-m15", "EURUSD", "M15", create_market_data())

    assert service.list_symbols() == [
        "EURUSD",
        "XAUUSD",
    ]


def test_list_timeframes():
    service = DataService()

    service.register("xauusd-h1", "XAUUSD", "H1", create_market_data())
    service.register("xauusd-m15", "XAUUSD", "M15", create_market_data())

    assert service.list_timeframes("XAUUSD") == [
        "H1",
        "M15",
    ]


def test_latest_row():
    service = DataService()

    service.register(
        name="xauusd-h1",
        symbol="XAUUSD",
        timeframe="H1",
        data=create_market_data(),
    )

    latest = service.latest_row("xauusd-h1")

    assert latest["timestamp"] == "2026-01-02"
    assert latest["close"] == 2015.0


def test_close_prices():
    service = DataService()

    service.register(
        name="xauusd-h1",
        symbol="XAUUSD",
        timeframe="H1",
        data=create_market_data(),
    )

    prices = service.close_prices("xauusd-h1")

    assert prices == [
        2005.0,
        2015.0,
    ]


def test_remove_dataset():
    service = DataService()

    service.register("xauusd-h1", "XAUUSD", "H1", create_market_data())

    service.remove("xauusd-h1")

    assert service.exists("xauusd-h1") is False
    assert service.count() == 0


def test_clear_datasets():
    service = DataService()

    service.register("xauusd-h1", "XAUUSD", "H1", create_market_data())
    service.register("eurusd-m15", "EURUSD", "M15", create_market_data())

    service.clear()

    assert service.count() == 0


def test_empty_name():
    service = DataService()

    with pytest.raises(ValueError):
        service.register(
            name="",
            symbol="XAUUSD",
            timeframe="H1",
            data=create_market_data(),
        )


def test_empty_symbol():
    service = DataService()

    with pytest.raises(ValueError):
        service.register(
            name="xauusd-h1",
            symbol="",
            timeframe="H1",
            data=create_market_data(),
        )


def test_empty_timeframe():
    service = DataService()

    with pytest.raises(ValueError):
        service.register(
            name="xauusd-h1",
            symbol="XAUUSD",
            timeframe="",
            data=create_market_data(),
        )


def test_empty_data():
    service = DataService()

    with pytest.raises(ValueError):
        service.register(
            name="xauusd-h1",
            symbol="XAUUSD",
            timeframe="H1",
            data=pd.DataFrame(),
        )


def test_missing_required_columns():
    service = DataService()

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
        service.register(
            name="xauusd-h1",
            symbol="XAUUSD",
            timeframe="H1",
            data=data,
        )


def test_latest_row_missing_dataset():
    service = DataService()

    with pytest.raises(ValueError):
        service.latest_row("missing")


def test_close_prices_missing_dataset():
    service = DataService()

    with pytest.raises(ValueError):
        service.close_prices("missing")