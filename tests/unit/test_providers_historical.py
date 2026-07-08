"""
Unit tests for AQOS historical OHLCV provider adapter.
"""

import pytest

from aqos.providers import (
    HistoricalDataCoverage,
    HistoricalOhlcvAdapter,
    MarketDataBatch,
    MarketDataQuality,
    ProviderCapability,
    ProviderStatus,
    ProviderType,
    build_historical_batch_request,
    build_historical_data_coverage,
    build_historical_ohlcv_adapter,
    build_market_data_batch,
    build_ohlcv_candle,
    build_provider_config,
    create_sample_historical_adapter,
    fetch_historical_ohlcv,
    filter_historical_candles,
    historical_batch_from_rows,
    historical_batch_key,
    historical_batch_to_rows,
    validate_historical_batches,
    validate_historical_provider_config,
)


def build_candle(timestamp: str, close: float = 2010):
    return build_ohlcv_candle(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp=timestamp,
        open=2000,
        high=2020,
        low=1990,
        close=close,
        volume=100,
        quality="validated",
    )


def build_adapter() -> HistoricalOhlcvAdapter:
    adapter = build_historical_ohlcv_adapter(
        provider_id="provider-1",
        name="Provider 1",
        metadata={
            "source": "test",
        },
    )
    adapter.add_candles(
        symbol="XAUUSD",
        timeframe="H1",
        candles=[
            build_candle("2026-01-01T00:00:00+00:00", 2005),
            build_candle("2026-01-01T01:00:00+00:00", 2010),
            build_candle("2026-01-01T02:00:00+00:00", 2015),
        ],
        quality="validated",
        metadata={
            "dataset": "demo",
        },
    )
    return adapter


def test_historical_data_coverage_to_dict():
    coverage = HistoricalDataCoverage(
        provider_id=" provider-1 ",
        symbol=" xauusd ",
        timeframe=" h1 ",
        start=" 2026-01-01 ",
        end=" 2026-01-02 ",
        count=10,
        metadata={
            "source": "test",
        },
    )

    assert coverage.empty is False
    assert coverage.to_dict() == {
        "provider_id": "provider-1",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "start": "2026-01-01",
        "end": "2026-01-02",
        "count": 10,
        "empty": False,
        "metadata": {
            "source": "test",
        },
    }


def test_historical_data_coverage_rejects_invalid_values():
    with pytest.raises(ValueError):
        HistoricalDataCoverage(provider_id="", symbol="XAUUSD", timeframe="H1")

    with pytest.raises(ValueError):
        HistoricalDataCoverage(provider_id="provider-1", symbol="bad symbol", timeframe="H1")

    with pytest.raises(ValueError):
        HistoricalDataCoverage(provider_id="provider-1", symbol="XAUUSD", timeframe="H2")

    with pytest.raises(ValueError):
        HistoricalDataCoverage(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", start=123)

    with pytest.raises(ValueError):
        HistoricalDataCoverage(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", count=-1)

    with pytest.raises(ValueError):
        HistoricalDataCoverage(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", metadata=[])


def test_build_historical_data_coverage():
    coverage = build_historical_data_coverage(
        provider_id="provider-1",
        symbol="xauusd",
        timeframe="h1",
    )

    assert isinstance(coverage, HistoricalDataCoverage)
    assert coverage.empty is True
    assert coverage.to_dict()["symbol"] == "XAUUSD"


def test_validate_historical_provider_config():
    config = build_provider_config(
        provider_id="provider-1",
        name="Provider",
        provider_type="market_data",
        capabilities=["historical_ohlcv"],
    )

    assert validate_historical_provider_config(config) == config

    with pytest.raises(ValueError):
        validate_historical_provider_config("bad")

    with pytest.raises(ValueError):
        validate_historical_provider_config(
            build_provider_config(
                provider_id="broker-1",
                name="Broker",
                provider_type=ProviderType.BROKER,
                capabilities=["historical_ohlcv"],
            ),
        )

    with pytest.raises(ValueError):
        validate_historical_provider_config(
            build_provider_config(
                provider_id="provider-1",
                name="Provider",
                provider_type="market_data",
                capabilities=["live_quotes"],
            ),
        )


def test_validate_historical_batches_and_key():
    batch = build_market_data_batch(
        provider_id="provider-1",
        symbol="XAUUSD",
        timeframe="H1",
    )
    key = historical_batch_key("xauusd", "h1")

    assert key == "XAUUSD::H1"
    assert validate_historical_batches({key: batch}) == {key: batch}

    with pytest.raises(ValueError):
        validate_historical_batches("bad")

    with pytest.raises(ValueError):
        validate_historical_batches({"": batch})

    with pytest.raises(ValueError):
        validate_historical_batches({key: "bad"})


def test_build_historical_ohlcv_adapter():
    adapter = build_historical_ohlcv_adapter(
        provider_id="provider-1",
        name="Provider 1",
    )

    assert isinstance(adapter, HistoricalOhlcvAdapter)
    assert adapter.provider_id == "provider-1"
    assert adapter.active is True
    assert adapter.count() == 0
    assert adapter.provider_config.supports(ProviderCapability.HISTORICAL_OHLCV)


def test_historical_adapter_rejects_invalid_values():
    valid_config = build_provider_config(
        provider_id="provider-1",
        name="Provider",
        provider_type="market_data",
        capabilities=["historical_ohlcv"],
    )

    with pytest.raises(ValueError):
        HistoricalOhlcvAdapter(provider_config="bad")

    with pytest.raises(ValueError):
        HistoricalOhlcvAdapter(provider_config=valid_config, batches=[])

    with pytest.raises(ValueError):
        HistoricalOhlcvAdapter(provider_config=valid_config, metadata=[])


def test_historical_adapter_add_get_list_and_clear():
    adapter = build_adapter()

    assert adapter.count() == 1
    assert adapter.has_data(symbol="xauusd", timeframe="h1") is True
    assert adapter.has_data(symbol="xauusd", timeframe="m5") is False
    assert adapter.list_symbols() == ["XAUUSD"]
    assert adapter.list_timeframes() == ["H1"]
    assert adapter.list_timeframes(symbol="xauusd") == ["H1"]

    batch = adapter.get_batch(symbol="XAUUSD", timeframe="H1")

    assert isinstance(batch, MarketDataBatch)
    assert batch.count == 3
    assert adapter.latest_candle(symbol="XAUUSD", timeframe="H1").close == 2015
    assert adapter.close_prices(symbol="XAUUSD", timeframe="H1") == [2005.0, 2010.0, 2015.0]

    adapter.clear()

    assert adapter.count() == 0


def test_historical_adapter_add_batch_rejects_invalid_values():
    adapter = build_historical_ohlcv_adapter(provider_id="provider-1")
    wrong_provider_batch = build_market_data_batch(
        provider_id="other",
        symbol="XAUUSD",
        timeframe="H1",
    )

    with pytest.raises(ValueError):
        adapter.add_batch("bad")

    with pytest.raises(ValueError):
        adapter.add_batch(wrong_provider_batch)


def test_historical_batch_from_rows_and_to_rows():
    rows = [
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "open": 2000,
            "high": 2020,
            "low": 1990,
            "close": 2010,
            "volume": 100,
        }
    ]

    batch = historical_batch_from_rows(
        provider_id="provider-1",
        symbol="xauusd",
        timeframe="h1",
        rows=rows,
        quality="validated",
    )

    assert isinstance(batch, MarketDataBatch)
    assert batch.provider_id == "provider-1"
    assert batch.to_dict()["symbol"] == "XAUUSD"
    assert historical_batch_to_rows(batch) == rows

    with pytest.raises(ValueError):
        historical_batch_to_rows("bad")


def test_historical_adapter_add_rows():
    adapter = build_historical_ohlcv_adapter(provider_id="provider-1")

    adapter.add_rows(
        symbol="XAUUSD",
        timeframe="H1",
        rows=[
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "open": 2000,
                "high": 2020,
                "low": 1990,
                "close": 2010,
                "volume": 100,
            }
        ],
        quality="validated",
    )

    assert adapter.count() == 1
    assert adapter.latest_candle(symbol="XAUUSD", timeframe="H1").close == 2010


def test_filter_historical_candles():
    candles = [
        build_candle("2026-01-01T00:00:00+00:00", 2005),
        build_candle("2026-01-01T01:00:00+00:00", 2010),
        build_candle("2026-01-01T02:00:00+00:00", 2015),
    ]

    filtered = filter_historical_candles(
        candles=candles,
        start="2026-01-01T01:00:00+00:00",
        end="2026-01-01T02:00:00+00:00",
        limit=1,
    )

    assert len(filtered) == 1
    assert filtered[0].close == 2010

    with pytest.raises(ValueError):
        filter_historical_candles(candles=["bad"])

    with pytest.raises(ValueError):
        filter_historical_candles(candles=candles, start=123)

    with pytest.raises(ValueError):
        filter_historical_candles(candles=candles, limit=0)


def test_build_historical_batch_request():
    adapter = build_adapter()

    request = build_historical_batch_request(
        adapter=adapter,
        symbol="xauusd",
        timeframe="h1",
        limit=2,
    )

    assert request.provider_id == "provider-1"
    assert request.to_dict()["symbol"] == "XAUUSD"

    with pytest.raises(ValueError):
        build_historical_batch_request(
            adapter="bad",
            symbol="XAUUSD",
            timeframe="H1",
        )


def test_historical_adapter_fetch_success():
    adapter = build_adapter()
    request = build_historical_batch_request(
        adapter=adapter,
        symbol="XAUUSD",
        timeframe="H1",
        start="2026-01-01T01:00:00+00:00",
        limit=2,
    )

    result = adapter.fetch(request)

    assert result.success is True
    assert result.provider_id == "provider-1"
    assert result.metadata["capability"] == "historical_ohlcv"
    assert result.data["batch"]["count"] == 2
    assert result.data["batch"]["latest_close"] == 2015.0


def test_fetch_historical_ohlcv_helper():
    adapter = build_adapter()
    request = build_historical_batch_request(
        adapter=adapter,
        symbol="XAUUSD",
        timeframe="H1",
    )

    result = fetch_historical_ohlcv(
        adapter=adapter,
        request=request,
    )

    assert result.success is True
    assert result.data["batch"]["count"] == 3

    with pytest.raises(ValueError):
        fetch_historical_ohlcv(
            adapter="bad",
            request=request,
        )


def test_historical_adapter_fetch_failures():
    adapter = build_adapter()

    wrong_provider_request = build_historical_batch_request(
        adapter=adapter,
        symbol="XAUUSD",
        timeframe="H1",
    )
    wrong_provider_request = type(wrong_provider_request)(
        provider_id="other",
        symbol="XAUUSD",
        timeframe="H1",
    )

    wrong_provider_result = adapter.fetch(wrong_provider_request)

    missing_result = adapter.fetch(
        build_historical_batch_request(
            adapter=adapter,
            symbol="BTCUSDT",
            timeframe="H1",
        ),
    )

    inactive_adapter = build_historical_ohlcv_adapter(
        provider_config=build_provider_config(
            provider_id="inactive",
            name="Inactive",
            provider_type="market_data",
            status=ProviderStatus.INACTIVE,
            capabilities=["historical_ohlcv"],
        ),
    )
    inactive_result = inactive_adapter.fetch(
        build_historical_batch_request(
            adapter=inactive_adapter,
            symbol="XAUUSD",
            timeframe="H1",
        ),
    )

    assert wrong_provider_result.success is False
    assert missing_result.success is False
    assert missing_result.error == "Historical OHLCV data not found."
    assert inactive_result.success is False

    with pytest.raises(ValueError):
        adapter.fetch("bad")


def test_historical_adapter_coverage():
    adapter = build_adapter()

    coverage = adapter.coverage(
        symbol="XAUUSD",
        timeframe="H1",
    )
    missing = adapter.coverage(
        symbol="BTCUSDT",
        timeframe="H1",
    )

    assert coverage.count == 3
    assert coverage.start == "2026-01-01T00:00:00+00:00"
    assert coverage.end == "2026-01-01T02:00:00+00:00"
    assert missing.empty is True


def test_create_sample_historical_adapter():
    adapter = create_sample_historical_adapter()

    assert isinstance(adapter, HistoricalOhlcvAdapter)
    assert adapter.provider_id == "sample-historical"
    assert adapter.count() == 1
    assert adapter.close_prices(symbol="XAUUSD", timeframe="H1") == [2005.0, 2015.0]


def test_historical_exports_exist():
    import aqos.providers as providers

    expected_exports = [
        "HistoricalDataCoverage",
        "HistoricalOhlcvAdapter",
        "build_historical_batch_request",
        "build_historical_data_coverage",
        "build_historical_ohlcv_adapter",
        "create_sample_historical_adapter",
        "fetch_historical_ohlcv",
        "filter_historical_candles",
        "historical_batch_from_rows",
        "historical_batch_key",
        "historical_batch_to_rows",
        "validate_historical_batches",
        "validate_historical_provider_config",
    ]

    for export_name in expected_exports:
        assert hasattr(providers, export_name), export_name