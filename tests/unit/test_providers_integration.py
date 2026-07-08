"""
Unit tests for AQOS provider integration helpers.
"""

import pytest

from aqos.providers import (
    AqosMarketDataPayload,
    ProviderIntegrationHub,
    build_aqos_market_data_payload,
    build_historical_ohlcv_adapter,
    build_market_data_batch,
    build_market_quote,
    build_market_tick,
    build_ohlcv_candle,
    build_provider_integration_hub,
    build_provider_registry,
    build_sample_provider_integration_hub,
    build_sample_provider_registry,
    fetch_historical_market_data,
    fetch_live_market_quote,
    fetch_live_market_ticks,
    integration_failure,
    market_data_batch_to_service_payload,
    provider_result_batch,
    provider_result_quote,
    provider_result_ticks,
    register_historical_adapter,
    register_live_adapter,
    validate_aqos_market_data_rows,
    validate_aqos_market_data_ticks,
    validate_provider_integration_hub,
)


def build_batch():
    candle = build_ohlcv_candle(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp="2026-01-01T00:00:00+00:00",
        open=2000,
        high=2020,
        low=1990,
        close=2010,
        volume=100,
    )

    return build_market_data_batch(
        provider_id="provider-1",
        symbol="XAUUSD",
        timeframe="H1",
        candles=[candle],
    )


def test_aqos_market_data_payload_to_dict():
    payload = AqosMarketDataPayload(
        provider_id=" provider-1 ",
        symbol=" xauusd ",
        timeframe=" H1 ",
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
        quote={
            "symbol": "XAUUSD",
            "mid": 2001,
        },
        ticks=[
            {
                "symbol": "XAUUSD",
                "price": 2001,
            }
        ],
        metadata={
            "source": "test",
        },
    )

    result = payload.to_dict()

    assert payload.row_count == 1
    assert payload.tick_count == 1
    assert payload.has_quote is True
    assert payload.latest_close == 2010.0
    assert result["provider_id"] == "provider-1"
    assert result["symbol"] == "XAUUSD"
    assert result["timeframe"] == "H1"
    assert result["metadata"] == {
        "source": "test",
    }


def test_aqos_market_data_payload_rejects_invalid_values():
    with pytest.raises(ValueError):
        AqosMarketDataPayload(provider_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        AqosMarketDataPayload(provider_id="provider-1", symbol="bad symbol")

    with pytest.raises(ValueError):
        AqosMarketDataPayload(provider_id="provider-1", symbol="XAUUSD", timeframe=123)

    with pytest.raises(ValueError):
        AqosMarketDataPayload(provider_id="provider-1", symbol="XAUUSD", rows="bad")

    with pytest.raises(ValueError):
        AqosMarketDataPayload(provider_id="provider-1", symbol="XAUUSD", quote=[])

    with pytest.raises(ValueError):
        AqosMarketDataPayload(provider_id="provider-1", symbol="XAUUSD", ticks="bad")

    with pytest.raises(ValueError):
        AqosMarketDataPayload(provider_id="provider-1", symbol="XAUUSD", metadata=[])


def test_validate_aqos_market_data_helpers():
    rows = [{"close": 2010}]
    ticks = [{"price": 2001}]

    assert validate_aqos_market_data_rows(rows) == rows
    assert validate_aqos_market_data_ticks(ticks) == ticks

    with pytest.raises(ValueError):
        validate_aqos_market_data_rows("bad")

    with pytest.raises(ValueError):
        validate_aqos_market_data_rows(["bad"])

    with pytest.raises(ValueError):
        validate_aqos_market_data_ticks("bad")

    with pytest.raises(ValueError):
        validate_aqos_market_data_ticks(["bad"])


def test_build_aqos_market_data_payload():
    payload = build_aqos_market_data_payload(
        provider_id="provider-1",
        symbol="xauusd",
    )

    assert isinstance(payload, AqosMarketDataPayload)
    assert payload.to_dict()["symbol"] == "XAUUSD"


def test_market_data_batch_to_service_payload():
    batch = build_batch()
    quote = build_market_quote(
        provider_id="provider-1",
        symbol="XAUUSD",
        bid=2000,
        ask=2002,
    )
    tick = build_market_tick(
        provider_id="provider-1",
        symbol="XAUUSD",
        price=2001,
    )

    payload = market_data_batch_to_service_payload(
        batch=batch,
        quote=quote,
        ticks=[tick],
        metadata={
            "source": "test",
        },
    )

    assert isinstance(payload, AqosMarketDataPayload)
    assert payload.row_count == 1
    assert payload.has_quote is True
    assert payload.tick_count == 1
    assert payload.latest_close == 2010.0
    assert payload.metadata == {
        "source": "test",
    }

    with pytest.raises(ValueError):
        market_data_batch_to_service_payload(batch="bad")

    with pytest.raises(ValueError):
        market_data_batch_to_service_payload(batch=batch, quote="bad")

    with pytest.raises(ValueError):
        market_data_batch_to_service_payload(batch=batch, ticks=["bad"])


def test_register_adapters_and_hub_summary():
    registry = build_provider_registry()
    historical_adapter = build_historical_ohlcv_adapter(provider_id="provider-1")

    historical_entry = register_historical_adapter(
        registry=registry,
        adapter=historical_adapter,
    )

    assert historical_entry.provider_id == "provider-1"
    assert registry.count() == 1

    from aqos.providers import build_live_market_data_adapter

    live_adapter = build_live_market_data_adapter(provider_id="live-1")
    live_entry = register_live_adapter(
        registry=registry,
        adapter=live_adapter,
    )

    assert live_entry.provider_id == "live-1"
    assert registry.count() == 2

    hub = build_provider_integration_hub(
        registry=registry,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(hub, ProviderIntegrationHub)
    assert hub.summary()["registry"]["total"] == 2
    assert hub.summary()["metadata"] == {
        "source": "test",
    }

    with pytest.raises(ValueError):
        register_historical_adapter(registry="bad", adapter=historical_adapter)

    with pytest.raises(ValueError):
        register_historical_adapter(registry=registry, adapter="bad")

    with pytest.raises(ValueError):
        register_live_adapter(registry="bad", adapter=live_adapter)

    with pytest.raises(ValueError):
        register_live_adapter(registry=registry, adapter="bad")


def test_validate_provider_integration_hub():
    hub = build_provider_integration_hub()

    assert validate_provider_integration_hub(hub) == hub

    with pytest.raises(ValueError):
        validate_provider_integration_hub("bad")


def test_sample_registry_and_hub_fetches():
    registry = build_sample_provider_registry()
    hub = build_provider_integration_hub(registry=registry)

    historical_result = hub.fetch_historical(
        symbol="XAUUSD",
        timeframe="H1",
    )
    quote_result = hub.fetch_quote(
        symbol="XAUUSD",
    )
    ticks_result = hub.fetch_ticks(
        symbol="XAUUSD",
        limit=1,
    )

    assert historical_result.success is True
    assert historical_result.data["batch"]["count"] == 2
    assert quote_result.success is True
    assert quote_result.data["quote"]["symbol"] == "XAUUSD"
    assert ticks_result.success is True
    assert ticks_result.data["count"] == 1


def test_fetch_helper_functions():
    hub = build_sample_provider_integration_hub()

    historical_result = fetch_historical_market_data(
        hub=hub,
        symbol="XAUUSD",
        timeframe="H1",
    )
    quote_result = fetch_live_market_quote(
        hub=hub,
        symbol="XAUUSD",
    )
    ticks_result = fetch_live_market_ticks(
        hub=hub,
        symbol="XAUUSD",
        limit=1,
    )

    assert historical_result.success is True
    assert quote_result.success is True
    assert ticks_result.success is True

    with pytest.raises(ValueError):
        fetch_historical_market_data(
            hub="bad",
            symbol="XAUUSD",
            timeframe="H1",
        )

    with pytest.raises(ValueError):
        fetch_live_market_quote(
            hub="bad",
            symbol="XAUUSD",
        )

    with pytest.raises(ValueError):
        fetch_live_market_ticks(
            hub="bad",
            symbol="XAUUSD",
        )


def test_provider_result_extractors():
    hub = build_sample_provider_integration_hub()

    historical_result = hub.fetch_historical(symbol="XAUUSD", timeframe="H1")
    quote_result = hub.fetch_quote(symbol="XAUUSD")
    ticks_result = hub.fetch_ticks(symbol="XAUUSD")

    batch = provider_result_batch(historical_result)
    quote = provider_result_quote(quote_result)
    ticks = provider_result_ticks(ticks_result)

    assert batch is not None
    assert batch["symbol"] == "XAUUSD"
    assert quote is not None
    assert quote["symbol"] == "XAUUSD"
    assert ticks is not None
    assert len(ticks) == 2

    failed = integration_failure(error="failed", operation="test")

    assert provider_result_batch(failed) is None
    assert provider_result_quote(failed) is None
    assert provider_result_ticks(failed) is None

    with pytest.raises(ValueError):
        provider_result_batch("bad")

    with pytest.raises(ValueError):
        provider_result_quote("bad")

    with pytest.raises(ValueError):
        provider_result_ticks("bad")


def test_historical_and_combined_payloads():
    hub = build_sample_provider_integration_hub()

    historical_payload = hub.historical_payload(
        symbol="XAUUSD",
        timeframe="H1",
    )
    combined_payload = hub.combined_payload(
        symbol="XAUUSD",
        timeframe="H1",
        historical_limit=1,
        tick_limit=1,
    )

    assert historical_payload is not None
    assert historical_payload.row_count == 2
    assert historical_payload.latest_close == 2015.0

    assert combined_payload is not None
    assert combined_payload.row_count == 1
    assert combined_payload.has_quote is True
    assert combined_payload.tick_count == 1


def test_missing_adapters_return_failure_results():
    hub = build_provider_integration_hub()

    historical_result = hub.fetch_historical(
        symbol="XAUUSD",
        timeframe="H1",
    )
    quote_result = hub.fetch_quote(
        symbol="XAUUSD",
    )
    ticks_result = hub.fetch_ticks(
        symbol="XAUUSD",
    )

    assert historical_result.success is False
    assert historical_result.error == "Historical adapter is not registered."
    assert quote_result.success is False
    assert quote_result.error == "Live adapter is not registered."
    assert ticks_result.success is False
    assert ticks_result.error == "Live adapter is not registered."

    assert hub.historical_payload(symbol="XAUUSD", timeframe="H1") is None
    assert hub.combined_payload(symbol="XAUUSD", timeframe="H1") is None


def test_integration_failure():
    result = integration_failure(
        error="failed",
        operation="unit-test",
    )

    assert result.success is False
    assert result.provider_id == "provider-integration"
    assert result.error == "failed"
    assert result.metadata["operation"] == "unit-test"

    with pytest.raises(ValueError):
        integration_failure(error="failed", operation="")


def test_provider_integration_exports_exist():
    import aqos.providers as providers

    expected_exports = [
        "AqosMarketDataPayload",
        "ProviderIntegrationHub",
        "build_aqos_market_data_payload",
        "build_provider_integration_hub",
        "build_sample_provider_integration_hub",
        "build_sample_provider_registry",
        "fetch_historical_market_data",
        "fetch_live_market_quote",
        "fetch_live_market_ticks",
        "integration_failure",
        "market_data_batch_to_service_payload",
        "provider_result_batch",
        "provider_result_quote",
        "provider_result_ticks",
        "register_historical_adapter",
        "register_live_adapter",
        "validate_aqos_market_data_rows",
        "validate_aqos_market_data_ticks",
        "validate_provider_integration_hub",
    ]

    for export_name in expected_exports:
        assert hasattr(providers, export_name), export_name