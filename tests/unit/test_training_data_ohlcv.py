"""
Unit tests for AQOS historical OHLCV training dataset contracts.
"""

import pytest

from aqos.training_data import (
    HistoricalOhlcvDataset,
    HistoricalOhlcvRow,
    HistoricalOhlcvSummary,
    TrainingDataConfig,
    TrainingDataStatus,
    build_historical_ohlcv_dataset,
    build_historical_ohlcv_row,
    build_training_data_config,
    ensure_ohlcv_dataset_not_empty,
    ohlcv_dataset_to_feature_rows,
    raw_row_to_historical_ohlcv_row,
    raw_rows_to_historical_ohlcv_dataset,
    raw_rows_to_historical_ohlcv_rows,
    slice_historical_ohlcv_dataset,
    summarize_historical_ohlcv_dataset,
    validate_historical_ohlcv_rows,
    validate_raw_ohlcv_rows,
)


def sample_raw_rows():
    return [
        {
            "timestamp": "2020-01-01T00:00:00+00:00",
            "open": 1500,
            "high": 1510,
            "low": 1495,
            "close": 1505,
            "volume": 100,
        },
        {
            "timestamp": "2020-01-01T01:00:00+00:00",
            "open": 1505,
            "high": 1520,
            "low": 1500,
            "close": 1515,
            "volume": 150,
        },
        {
            "timestamp": "2020-01-01T02:00:00+00:00",
            "open": 1515,
            "high": 1518,
            "low": 1508,
            "close": 1510,
            "volume": 120,
        },
    ]


def sample_rows():
    return raw_rows_to_historical_ohlcv_rows(
        sample_raw_rows(),
        symbol="XAUUSD",
    )


def sample_dataset():
    return raw_rows_to_historical_ohlcv_dataset(
        dataset_id="xauusd-h1",
        symbol="XAUUSD",
        rows=sample_raw_rows(),
        asset_type="commodity",
        timeframe="1h",
        source="test",
    )


def test_historical_ohlcv_row_to_dict():
    row = HistoricalOhlcvRow(
        timestamp=" 2020-01-01 ",
        symbol=" xauusd ",
        open=1500,
        high=1510,
        low=1495,
        close=1505,
        volume=100,
        metadata={
            "source": "test",
        },
    )

    payload = row.to_dict()

    assert row.bullish is True
    assert row.bearish is False
    assert row.body_size == 5
    assert row.range_size == 15
    assert row.typical_price == 1503.3333333333
    assert payload["timestamp"] == "2020-01-01"
    assert payload["symbol"] == "XAUUSD"
    assert payload["open"] == 1500.0
    assert payload["high"] == 1510.0
    assert payload["low"] == 1495.0
    assert payload["close"] == 1505.0
    assert payload["volume"] == 100.0


def test_historical_ohlcv_row_rejects_invalid_values():
    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="", open=1, high=1, low=1, close=1)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=-1, high=1, low=1, close=1)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=1, high=-1, low=1, close=1)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=1, high=1, low=-1, close=1)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=1, high=1, low=1, close=-1)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=1, high=1, low=1, close=1, volume=-1)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=1, high=1, low=1, close=1, symbol=123)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=1, high=1, low=1, close=1, symbol="bad symbol")

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=1, high=1, low=1, close=1, metadata=[])

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=10, high=9, low=8, close=9)

    with pytest.raises(ValueError):
        HistoricalOhlcvRow(timestamp="t", open=10, high=12, low=11, close=12)


def test_build_historical_ohlcv_row():
    row = build_historical_ohlcv_row(
        timestamp="2020-01-01",
        open=1,
        high=2,
        low=0.5,
        close=1.5,
        symbol="BTCUSDT",
    )

    assert isinstance(row, HistoricalOhlcvRow)
    assert row.symbol == "BTCUSDT"
    assert row.bullish is True


def test_raw_row_converters():
    row = raw_row_to_historical_ohlcv_row(
        {
            "timestamp": "2020-01-01",
            "open": "1",
            "high": "2",
            "low": "0.5",
            "close": "1.5",
            "volume": "10",
        },
        symbol="BTCUSDT",
    )
    rows = raw_rows_to_historical_ohlcv_rows(
        sample_raw_rows(),
        symbol="XAUUSD",
    )

    assert isinstance(row, HistoricalOhlcvRow)
    assert row.close == 1.5
    assert row.volume == 10
    assert row.symbol == "BTCUSDT"
    assert len(rows) == 3
    assert rows[0].symbol == "XAUUSD"

    with pytest.raises(ValueError):
        raw_row_to_historical_ohlcv_row([])

    with pytest.raises(KeyError):
        raw_row_to_historical_ohlcv_row({"timestamp": "t"})

    with pytest.raises(ValueError):
        raw_rows_to_historical_ohlcv_rows("bad")

    with pytest.raises(ValueError):
        raw_rows_to_historical_ohlcv_rows(["bad"])


def test_historical_ohlcv_dataset_to_dict_and_health():
    dataset = sample_dataset()
    payload = dataset.to_dict()
    health = dataset.health()

    assert isinstance(dataset.config, TrainingDataConfig)
    assert dataset.dataset_id == "xauusd-h1"
    assert dataset.symbol == "XAUUSD"
    assert dataset.timeframe.value == "1h"
    assert dataset.row_count == 3
    assert dataset.empty is False
    assert dataset.first_timestamp == "2020-01-01T00:00:00+00:00"
    assert dataset.last_timestamp == "2020-01-01T02:00:00+00:00"
    assert dataset.close_prices == [1505.0, 1515.0, 1510.0]
    assert dataset.volumes == [100.0, 150.0, 120.0]
    assert health.status == TrainingDataStatus.READY
    assert health.row_count == 3
    assert payload["dataset_id"] == "xauusd-h1"
    assert payload["row_count"] == 3
    assert payload["health"]["status"] == "ready"


def test_empty_historical_ohlcv_dataset_health():
    dataset = build_historical_ohlcv_dataset(
        dataset_id="empty",
        symbol="EURUSD",
        timeframe="1h",
    )

    assert dataset.empty is True
    assert dataset.health().status == TrainingDataStatus.EMPTY
    assert dataset.first_timestamp == ""
    assert dataset.last_timestamp == ""
    assert dataset.close_prices == []


def test_historical_ohlcv_dataset_rejects_invalid_values():
    config = build_training_data_config(
        dataset_id="dataset",
        symbol="XAUUSD",
    )
    row = sample_rows()[0]

    with pytest.raises(ValueError):
        HistoricalOhlcvDataset(config="bad")

    with pytest.raises(ValueError):
        HistoricalOhlcvDataset(config=config, rows="bad")

    with pytest.raises(ValueError):
        HistoricalOhlcvDataset(config=config, rows=["bad"])

    with pytest.raises(ValueError):
        HistoricalOhlcvDataset(config=config, source=123)

    with pytest.raises(ValueError):
        HistoricalOhlcvDataset(config=config, metadata=[])

    assert validate_historical_ohlcv_rows([row]) == [row]


def test_raw_rows_to_historical_ohlcv_dataset():
    dataset = raw_rows_to_historical_ohlcv_dataset(
        dataset_id="xauusd-h1",
        symbol="XAUUSD",
        rows=sample_raw_rows(),
        asset_type="commodity",
        timeframe="1h",
        source="csv",
    )

    assert isinstance(dataset, HistoricalOhlcvDataset)
    assert dataset.row_count == 3
    assert dataset.source == "csv"
    assert dataset.config.asset_type == "commodity"


def test_historical_ohlcv_summary():
    dataset = sample_dataset()
    summary = summarize_historical_ohlcv_dataset(dataset)
    payload = summary.to_dict()

    assert isinstance(summary, HistoricalOhlcvSummary)
    assert summary.has_data is True
    assert summary.dataset_id == "xauusd-h1"
    assert summary.symbol == "XAUUSD"
    assert summary.row_count == 3
    assert summary.min_close == 1505.0
    assert summary.max_close == 1515.0
    assert summary.average_close == 1510.0
    assert summary.total_volume == 370.0
    assert payload["timeframe"] == "1h"

    with pytest.raises(ValueError):
        summarize_historical_ohlcv_dataset("bad")


def test_historical_ohlcv_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        HistoricalOhlcvSummary(dataset_id="", symbol="XAUUSD", timeframe="1h")

    with pytest.raises(ValueError):
        HistoricalOhlcvSummary(dataset_id="dataset", symbol="bad symbol", timeframe="1h")

    with pytest.raises(ValueError):
        HistoricalOhlcvSummary(dataset_id="dataset", symbol="XAUUSD", timeframe="bad")

    with pytest.raises(ValueError):
        HistoricalOhlcvSummary(dataset_id="dataset", symbol="XAUUSD", timeframe="1h", row_count=-1)

    with pytest.raises(ValueError):
        HistoricalOhlcvSummary(dataset_id="dataset", symbol="XAUUSD", timeframe="1h", min_close=-1)

    with pytest.raises(ValueError):
        HistoricalOhlcvSummary(dataset_id="dataset", symbol="XAUUSD", timeframe="1h", metadata=[])


def test_slice_historical_ohlcv_dataset():
    dataset = sample_dataset()
    sliced = slice_historical_ohlcv_dataset(
        dataset,
        start_index=1,
        end_index=3,
    )

    assert isinstance(sliced, HistoricalOhlcvDataset)
    assert sliced.row_count == 2
    assert sliced.rows[0].timestamp == "2020-01-01T01:00:00+00:00"
    assert sliced.metadata["slice_start_index"] == 1
    assert sliced.metadata["slice_end_index"] == 3

    with pytest.raises(ValueError):
        slice_historical_ohlcv_dataset("bad")

    with pytest.raises(ValueError):
        slice_historical_ohlcv_dataset(dataset, start_index=-1)

    with pytest.raises(ValueError):
        slice_historical_ohlcv_dataset(dataset, start_index=2, end_index=1)


def test_ensure_dataset_not_empty():
    dataset = sample_dataset()
    empty_dataset = build_historical_ohlcv_dataset(
        dataset_id="empty",
        symbol="EURUSD",
    )

    assert ensure_ohlcv_dataset_not_empty(dataset) == dataset

    with pytest.raises(ValueError):
        ensure_ohlcv_dataset_not_empty("bad")

    with pytest.raises(ValueError):
        ensure_ohlcv_dataset_not_empty(empty_dataset)


def test_ohlcv_dataset_to_feature_rows():
    feature_rows = ohlcv_dataset_to_feature_rows(sample_dataset())

    assert len(feature_rows) == 3
    assert feature_rows[0]["symbol"] == "XAUUSD"
    assert feature_rows[0]["open"] == 1500
    assert feature_rows[0]["close"] == 1505
    assert feature_rows[0]["body_size"] == 5
    assert feature_rows[0]["range_size"] == 15
    assert feature_rows[0]["bullish"] == 1
    assert feature_rows[0]["bearish"] == 0

    with pytest.raises(ValueError):
        ohlcv_dataset_to_feature_rows(
            build_historical_ohlcv_dataset(
                dataset_id="empty",
                symbol="EURUSD",
            )
        )


def test_raw_row_validators():
    rows = sample_raw_rows()

    assert validate_raw_ohlcv_rows(rows) == rows

    with pytest.raises(ValueError):
        validate_raw_ohlcv_rows("bad")

    with pytest.raises(ValueError):
        validate_raw_ohlcv_rows(["bad"])


def test_training_data_ohlcv_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "HistoricalOhlcvDataset",
        "HistoricalOhlcvRow",
        "HistoricalOhlcvSummary",
        "build_historical_ohlcv_dataset",
        "build_historical_ohlcv_row",
        "ensure_ohlcv_dataset_not_empty",
        "ohlcv_dataset_to_feature_rows",
        "raw_row_to_historical_ohlcv_row",
        "raw_rows_to_historical_ohlcv_dataset",
        "raw_rows_to_historical_ohlcv_rows",
        "slice_historical_ohlcv_dataset",
        "summarize_historical_ohlcv_dataset",
        "validate_historical_ohlcv_rows",
        "validate_raw_ohlcv_rows",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name