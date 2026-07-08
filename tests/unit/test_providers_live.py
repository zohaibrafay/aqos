"""
Unit tests for AQOS live market data provider adapter.
"""

import pytest

from aqos.providers import (
    LiveMarketDataAdapter,
    LiveMarketDataSnapshot,
    MarketQuote,
    MarketTick,
    ProviderCapability,
    ProviderStatus,
    ProviderType,
    build_live_market_data_adapter,
    build_live_market_data_snapshot,
    build_live_quote_request_for_adapter,
    build_market_quote,
    build_market_tick,
    build_provider_config,
    build_tick_data_request_for_adapter,
    create_sample_live_adapter,
    fetch_live_quote,
    fetch_market_ticks,
    live_symbol_key,
    quote_payload_to_market_quote,
    tick_payload_to_market_tick,
    validate_live_provider_config,
    validate_live_quotes_dict,
    validate_live_ticks_dict,
    validate_market_quotes,
    validate_symbol_list,
)


def build_quote(symbol: str = "XAUUSD") -> MarketQuote:
    return build_market_quote(
        provider_id="provider-1",
        symbol=symbol,
        bid=2000,
        ask=2002,
        last=2001,
        timestamp="2026-01-01T00:00:00+00:00",
    )


def build_tick(symbol: str = "XAUUSD", price: float = 2001) -> MarketTick:
    return build_market_tick(
        provider_id="provider-1",
        symbol=symbol,
        price=price,
        volume=10,
        timestamp="2026-01-01T00:00:01+00:00",
    )


def build_adapter() -> LiveMarketDataAdapter:
    adapter = build_live_market_data_adapter(
        provider_id="provider-1",
        name="Provider 1",
        metadata={
            "source": "test",
        },
    )
    adapter.update_quote(build_quote())
    adapter.add_tick(build_tick(price=2001))
    adapter.add_tick(build_tick(price=2002))
    return adapter


def test_live_market_data_snapshot_to_dict():
    snapshot = LiveMarketDataSnapshot(
        provider_id=" provider-1 ",
        quotes=[build_quote()],
        ticks=[build_tick()],
        metadata={
            "source": "test",
        },
    )

    payload = snapshot.to_dict()

    assert snapshot.quote_count == 1
    assert snapshot.tick_count == 1
    assert snapshot.empty is False
    assert payload["provider_id"] == "provider-1"
    assert payload["quote_count"] == 1
    assert payload["tick_count"] == 1
    assert payload["empty"] is False
    assert payload["metadata"] == {
        "source": "test",
    }


def test_live_market_data_snapshot_rejects_invalid_values():
    with pytest.raises(ValueError):
        LiveMarketDataSnapshot(provider_id="")

    with pytest.raises(ValueError):
        LiveMarketDataSnapshot(provider_id="provider-1", quotes=["bad"])

    with pytest.raises(ValueError):
        LiveMarketDataSnapshot(provider_id="provider-1", ticks=["bad"])

    with pytest.raises(ValueError):
        LiveMarketDataSnapshot(provider_id="provider-1", metadata=[])


def test_build_live_market_data_snapshot():
    snapshot = build_live_market_data_snapshot(
        provider_id="provider-1",
    )

    assert isinstance(snapshot, LiveMarketDataSnapshot)
    assert snapshot.empty is True


def test_validate_live_provider_config():
    config = build_provider_config(
        provider_id="provider-1",
        name="Provider",
        provider_type="market_data",
        capabilities=["live_quotes"],
    )

    assert validate_live_provider_config(config) == config

    with pytest.raises(ValueError):
        validate_live_provider_config("bad")

    with pytest.raises(ValueError):
        validate_live_provider_config(
            build_provider_config(
                provider_id="broker-1",
                name="Broker",
                provider_type=ProviderType.BROKER,
                capabilities=["live_quotes"],
            ),
        )

    with pytest.raises(ValueError):
        validate_live_provider_config(
            build_provider_config(
                provider_id="provider-1",
                name="Provider",
                provider_type="market_data",
                capabilities=["historical_ohlcv"],
            ),
        )


def test_live_validators_and_key():
    quote = build_quote()
    tick = build_tick()

    assert live_symbol_key("xauusd") == "XAUUSD"
    assert validate_market_quotes([quote]) == [quote]
    assert validate_live_quotes_dict({"XAUUSD": quote}) == {"XAUUSD": quote}
    assert validate_live_ticks_dict({"XAUUSD": [tick]}) == {"XAUUSD": [tick]}
    assert validate_symbol_list(["xauusd", "btc/usdt"]) == ["xauusd", "btc/usdt"]

    with pytest.raises(ValueError):
        validate_market_quotes("bad")

    with pytest.raises(ValueError):
        validate_market_quotes(["bad"])

    with pytest.raises(ValueError):
        validate_live_quotes_dict("bad")

    with pytest.raises(ValueError):
        validate_live_quotes_dict({"": quote})

    with pytest.raises(ValueError):
        validate_live_quotes_dict({"XAUUSD": "bad"})

    with pytest.raises(ValueError):
        validate_live_ticks_dict("bad")

    with pytest.raises(ValueError):
        validate_live_ticks_dict({"": [tick]})

    with pytest.raises(ValueError):
        validate_live_ticks_dict({"XAUUSD": ["bad"]})

    with pytest.raises(ValueError):
        validate_symbol_list("bad")

    with pytest.raises(ValueError):
        validate_symbol_list(["bad symbol"])


def test_build_live_market_data_adapter():
    adapter = build_live_market_data_adapter(
        provider_id="provider-1",
        name="Provider 1",
    )

    assert isinstance(adapter, LiveMarketDataAdapter)
    assert adapter.provider_id == "provider-1"
    assert adapter.active is True
    assert adapter.quote_count() == 0
    assert adapter.tick_count() == 0
    assert adapter.provider_config.supports(ProviderCapability.LIVE_QUOTES)
    assert adapter.provider_config.supports(ProviderCapability.TICKS)


def test_live_adapter_rejects_invalid_values():
    valid_config = build_provider_config(
        provider_id="provider-1",
        name="Provider",
        provider_type="market_data",
        capabilities=["live_quotes"],
    )

    with pytest.raises(ValueError):
        LiveMarketDataAdapter(provider_config="bad")

    with pytest.raises(ValueError):
        LiveMarketDataAdapter(provider_config=valid_config, quotes=[])

    with pytest.raises(ValueError):
        LiveMarketDataAdapter(provider_config=valid_config, ticks=[])

    with pytest.raises(ValueError):
        LiveMarketDataAdapter(provider_config=valid_config, metadata=[])


def test_live_adapter_update_quote_and_tick_flow():
    adapter = build_live_market_data_adapter(provider_id="provider-1")

    quote = adapter.update_quote_from_values(
        symbol="xauusd",
        bid=2000,
        ask=2002,
        last=2001,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    tick_1 = adapter.add_tick_from_values(
        symbol="xauusd",
        price=2001,
        volume=10,
        timestamp="2026-01-01T00:00:01+00:00",
    )
    tick_2 = adapter.add_tick_from_values(
        symbol="xauusd",
        price=2002,
        volume=12,
        timestamp="2026-01-01T00:00:02+00:00",
    )

    assert quote.symbol == "xauusd"
    assert tick_1.price == 2001
    assert tick_2.price == 2002
    assert adapter.quote_count() == 1
    assert adapter.tick_count() == 2
    assert adapter.get_quote("XAUUSD") == quote
    assert adapter.get_price(symbol="XAUUSD", price_type="bid") == 2000.0
    assert adapter.get_price(symbol="XAUUSD", price_type="mid") == 2001.0
    assert [tick.price for tick in adapter.get_ticks(symbol="XAUUSD", limit=1)] == [2002]
    assert adapter.list_symbols() == ["XAUUSD"]


def test_live_adapter_update_rejects_wrong_provider_or_type():
    adapter = build_live_market_data_adapter(provider_id="provider-1")
    wrong_quote = build_market_quote(
        provider_id="other",
        symbol="XAUUSD",
        bid=2000,
        ask=2002,
    )
    wrong_tick = build_market_tick(
        provider_id="other",
        symbol="XAUUSD",
        price=2001,
    )

    with pytest.raises(ValueError):
        adapter.update_quote("bad")

    with pytest.raises(ValueError):
        adapter.update_quote(wrong_quote)

    with pytest.raises(ValueError):
        adapter.add_tick("bad")

    with pytest.raises(ValueError):
        adapter.add_tick(wrong_tick)


def test_live_adapter_fetch_quote_success():
    adapter = build_adapter()
    request = build_live_quote_request_for_adapter(
        adapter=adapter,
        symbol="xauusd",
        price_type="mid",
    )

    result = adapter.fetch_quote(request)

    assert result.success is True
    assert result.provider_id == "provider-1"
    assert result.metadata["capability"] == "live_quotes"
    assert result.data["quote"]["symbol"] == "XAUUSD"
    assert result.data["quote"]["mid"] == 2001.0


def test_fetch_live_quote_helper():
    adapter = build_adapter()
    request = build_live_quote_request_for_adapter(
        adapter=adapter,
        symbol="xauusd",
    )

    result = fetch_live_quote(
        adapter=adapter,
        request=request,
    )

    assert result.success is True

    with pytest.raises(ValueError):
        fetch_live_quote(
            adapter="bad",
            request=request,
        )


def test_live_adapter_fetch_ticks_success():
    adapter = build_adapter()
    request = build_tick_data_request_for_adapter(
        adapter=adapter,
        symbol="xauusd",
        limit=1,
    )

    result = adapter.fetch_ticks(request)

    assert result.success is True
    assert result.provider_id == "provider-1"
    assert result.metadata["capability"] == "ticks"
    assert result.data["count"] == 1
    assert result.data["ticks"][0]["price"] == 2002.0


def test_fetch_market_ticks_helper():
    adapter = build_adapter()
    request = build_tick_data_request_for_adapter(
        adapter=adapter,
        symbol="xauusd",
    )

    result = fetch_market_ticks(
        adapter=adapter,
        request=request,
    )

    assert result.success is True

    with pytest.raises(ValueError):
        fetch_market_ticks(
            adapter="bad",
            request=request,
        )


def test_live_adapter_fetch_failures():
    adapter = build_adapter()

    wrong_quote_request = build_live_quote_request_for_adapter(
        adapter=adapter,
        symbol="XAUUSD",
    )
    wrong_quote_request = type(wrong_quote_request)(
        provider_id="other",
        symbol="XAUUSD",
    )

    wrong_provider_result = adapter.fetch_quote(wrong_quote_request)

    missing_quote_result = adapter.fetch_quote(
        build_live_quote_request_for_adapter(
            adapter=adapter,
            symbol="BTCUSDT",
        ),
    )

    inactive_adapter = build_live_market_data_adapter(
        provider_config=build_provider_config(
            provider_id="inactive",
            name="Inactive",
            provider_type="market_data",
            status=ProviderStatus.INACTIVE,
            capabilities=["live_quotes", "ticks"],
        ),
    )

    inactive_result = inactive_adapter.fetch_quote(
        build_live_quote_request_for_adapter(
            adapter=inactive_adapter,
            symbol="XAUUSD",
        ),
    )

    assert wrong_provider_result.success is False
    assert missing_quote_result.success is False
    assert missing_quote_result.error == "Live quote not found."
    assert inactive_result.success is False

    with pytest.raises(ValueError):
        adapter.fetch_quote("bad")


def test_live_adapter_fetch_tick_failures():
    adapter = build_adapter()

    wrong_tick_request = build_tick_data_request_for_adapter(
        adapter=adapter,
        symbol="XAUUSD",
    )
    wrong_tick_request = type(wrong_tick_request)(
        provider_id="other",
        symbol="XAUUSD",
    )

    wrong_provider_result = adapter.fetch_ticks(wrong_tick_request)

    missing_ticks_result = adapter.fetch_ticks(
        build_tick_data_request_for_adapter(
            adapter=adapter,
            symbol="BTCUSDT",
        ),
    )

    inactive_adapter = build_live_market_data_adapter(
        provider_config=build_provider_config(
            provider_id="inactive",
            name="Inactive",
            provider_type="market_data",
            status=ProviderStatus.INACTIVE,
            capabilities=["live_quotes", "ticks"],
        ),
    )

    inactive_result = inactive_adapter.fetch_ticks(
        build_tick_data_request_for_adapter(
            adapter=inactive_adapter,
            symbol="XAUUSD",
        ),
    )

    assert wrong_provider_result.success is False
    assert missing_ticks_result.success is False
    assert missing_ticks_result.error == "Market ticks not found."
    assert inactive_result.success is False

    with pytest.raises(ValueError):
        adapter.fetch_ticks("bad")


def test_live_adapter_snapshot_and_clear():
    adapter = build_adapter()

    snapshot = adapter.snapshot()
    filtered_snapshot = adapter.snapshot(symbols=["xauusd"])

    assert snapshot.quote_count == 1
    assert snapshot.tick_count == 2
    assert filtered_snapshot.quote_count == 1
    assert filtered_snapshot.tick_count == 2

    with pytest.raises(ValueError):
        adapter.snapshot(symbols="bad")

    adapter.clear_quotes()

    assert adapter.quote_count() == 0
    assert adapter.tick_count() == 2

    adapter.clear_ticks()

    assert adapter.tick_count() == 0

    adapter.update_quote(build_quote())
    adapter.add_tick(build_tick())
    adapter.clear()

    assert adapter.quote_count() == 0
    assert adapter.tick_count() == 0


def test_build_request_helpers():
    adapter = build_adapter()

    quote_request = build_live_quote_request_for_adapter(
        adapter=adapter,
        symbol="xauusd",
    )
    tick_request = build_tick_data_request_for_adapter(
        adapter=adapter,
        symbol="xauusd",
    )

    assert quote_request.provider_id == "provider-1"
    assert tick_request.provider_id == "provider-1"

    with pytest.raises(ValueError):
        build_live_quote_request_for_adapter(
            adapter="bad",
            symbol="XAUUSD",
        )

    with pytest.raises(ValueError):
        build_tick_data_request_for_adapter(
            adapter="bad",
            symbol="XAUUSD",
        )


def test_payload_conversion_helpers():
    quote = quote_payload_to_market_quote(
        provider_id="provider-1",
        payload={
            "symbol": "xauusd",
            "bid": 2000,
            "ask": 2002,
            "last": 2001,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "metadata": {
                "source": "test",
            },
        },
    )
    tick = tick_payload_to_market_tick(
        provider_id="provider-1",
        payload={
            "symbol": "xauusd",
            "price": 2001,
            "volume": 10,
            "price_type": "last",
            "timestamp": "2026-01-01T00:00:01+00:00",
        },
    )

    assert isinstance(quote, MarketQuote)
    assert isinstance(tick, MarketTick)
    assert quote.to_dict()["symbol"] == "XAUUSD"
    assert tick.to_dict()["price"] == 2001.0

    with pytest.raises(ValueError):
        quote_payload_to_market_quote(
            provider_id="provider-1",
            payload=[],
        )

    with pytest.raises(KeyError):
        quote_payload_to_market_quote(
            provider_id="provider-1",
            payload={},
        )

    with pytest.raises(ValueError):
        tick_payload_to_market_tick(
            provider_id="provider-1",
            payload=[],
        )

    with pytest.raises(KeyError):
        tick_payload_to_market_tick(
            provider_id="provider-1",
            payload={},
        )


def test_create_sample_live_adapter():
    adapter = create_sample_live_adapter()

    assert isinstance(adapter, LiveMarketDataAdapter)
    assert adapter.provider_id == "sample-live"
    assert adapter.quote_count() == 1
    assert adapter.tick_count() == 2
    assert adapter.get_price(symbol="XAUUSD") == 2001.0


def test_live_exports_exist():
    import aqos.providers as providers

    expected_exports = [
        "LiveMarketDataAdapter",
        "LiveMarketDataSnapshot",
        "build_live_market_data_adapter",
        "build_live_market_data_snapshot",
        "build_live_quote_request_for_adapter",
        "build_tick_data_request_for_adapter",
        "create_sample_live_adapter",
        "fetch_live_quote",
        "fetch_market_ticks",
        "live_symbol_key",
        "quote_payload_to_market_quote",
        "tick_payload_to_market_tick",
        "validate_live_provider_config",
        "validate_live_quotes_dict",
        "validate_live_ticks_dict",
        "validate_market_quotes",
        "validate_symbol_list",
    ]

    for export_name in expected_exports:
        assert hasattr(providers, export_name), export_name