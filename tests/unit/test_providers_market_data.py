"""
Unit tests for AQOS market data provider contracts.
"""

import pytest

from aqos.providers import (
    HistoricalOhlcvRequest,
    LiveQuoteRequest,
    MarketDataBatch,
    MarketDataPriceType,
    MarketDataQuality,
    MarketDataRequestType,
    MarketDataTimeframe,
    MarketQuote,
    MarketTick,
    OhlcvCandle,
    ProviderCapability,
    TickDataRequest,
    build_historical_ohlcv_request,
    build_live_quote_request,
    build_market_data_batch,
    build_market_quote,
    build_market_tick,
    build_ohlcv_candle,
    build_tick_data_request,
    candles_to_ohlcv_rows,
    market_data_batch_to_provider_result,
    market_data_error_result,
    market_quote_to_provider_result,
    market_ticks_to_provider_result,
    normalize_market_data_price_type,
    normalize_market_data_quality,
    normalize_market_data_request_type,
    normalize_market_data_timeframe,
    ohlcv_rows_to_candles,
    validate_market_data_limit,
    validate_market_symbol,
    validate_market_ticks,
    validate_ohlcv_candles,
)


def build_candle(timestamp: str = "2026-01-01T00:00:00+00:00") -> OhlcvCandle:
    return build_ohlcv_candle(
        symbol="XAUUSD",
        timeframe="H1",
        timestamp=timestamp,
        open=2000,
        high=2020,
        low=1990,
        close=2010,
        volume=100,
        quality="validated",
        metadata={
            "source": "test",
        },
    )


def test_market_data_enum_values():
    assert MarketDataTimeframe.M1.value == "M1"
    assert MarketDataTimeframe.M5.value == "M5"
    assert MarketDataTimeframe.M15.value == "M15"
    assert MarketDataTimeframe.M30.value == "M30"
    assert MarketDataTimeframe.H1.value == "H1"
    assert MarketDataTimeframe.H4.value == "H4"
    assert MarketDataTimeframe.D1.value == "D1"
    assert MarketDataTimeframe.W1.value == "W1"

    assert MarketDataPriceType.BID.value == "bid"
    assert MarketDataPriceType.ASK.value == "ask"
    assert MarketDataPriceType.MID.value == "mid"
    assert MarketDataPriceType.LAST.value == "last"

    assert MarketDataQuality.RAW.value == "raw"
    assert MarketDataQuality.VALIDATED.value == "validated"
    assert MarketDataQuality.ADJUSTED.value == "adjusted"
    assert MarketDataQuality.SYNTHETIC.value == "synthetic"

    assert MarketDataRequestType.HISTORICAL_OHLCV.value == "historical_ohlcv"
    assert MarketDataRequestType.LIVE_QUOTE.value == "live_quote"
    assert MarketDataRequestType.TICKS.value == "ticks"


def test_market_data_normalizers_accept_enum_and_string():
    assert normalize_market_data_timeframe(MarketDataTimeframe.H1) == MarketDataTimeframe.H1
    assert normalize_market_data_timeframe(" h1 ") == MarketDataTimeframe.H1
    assert normalize_market_data_price_type(MarketDataPriceType.BID) == MarketDataPriceType.BID
    assert normalize_market_data_price_type(" ASK ") == MarketDataPriceType.ASK
    assert normalize_market_data_quality(MarketDataQuality.RAW) == MarketDataQuality.RAW
    assert normalize_market_data_quality(" VALIDATED ") == MarketDataQuality.VALIDATED
    assert normalize_market_data_request_type(MarketDataRequestType.TICKS) == MarketDataRequestType.TICKS
    assert normalize_market_data_request_type(" LIVE_QUOTE ") == MarketDataRequestType.LIVE_QUOTE


def test_market_data_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_market_data_timeframe("H2")

    with pytest.raises(ValueError):
        normalize_market_data_price_type("bad")

    with pytest.raises(ValueError):
        normalize_market_data_quality("bad")

    with pytest.raises(ValueError):
        normalize_market_data_request_type("bad")


def test_validate_market_symbol_and_limit():
    assert validate_market_symbol("xauusd") == "XAUUSD"
    assert validate_market_symbol("btc/usdt") == "BTC/USDT"
    assert validate_market_symbol("eth-usdt") == "ETH-USDT"
    assert validate_market_data_limit(1) == 1
    assert validate_market_data_limit(100000) == 100000

    with pytest.raises(ValueError):
        validate_market_symbol("")

    with pytest.raises(ValueError):
        validate_market_symbol("BAD SYMBOL")

    with pytest.raises(ValueError):
        validate_market_symbol("BTC_USDT")

    with pytest.raises(ValueError):
        validate_market_data_limit(0)

    with pytest.raises(ValueError):
        validate_market_data_limit(100001)


def test_historical_ohlcv_request_to_dict():
    request = HistoricalOhlcvRequest(
        provider_id=" provider-1 ",
        symbol=" xauusd ",
        timeframe=" h1 ",
        start=" 2026-01-01 ",
        end=" 2026-01-02 ",
        limit=100,
        metadata={
            "source": "test",
        },
    )

    assert request.to_dict() == {
        "request_type": "historical_ohlcv",
        "provider_id": "provider-1",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "start": "2026-01-01",
        "end": "2026-01-02",
        "limit": 100,
        "metadata": {
            "source": "test",
        },
    }


def test_historical_ohlcv_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        HistoricalOhlcvRequest(provider_id="", symbol="XAUUSD", timeframe="H1")

    with pytest.raises(ValueError):
        HistoricalOhlcvRequest(provider_id="provider-1", symbol="bad symbol", timeframe="H1")

    with pytest.raises(ValueError):
        HistoricalOhlcvRequest(provider_id="provider-1", symbol="XAUUSD", timeframe="H2")

    with pytest.raises(ValueError):
        HistoricalOhlcvRequest(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", limit=0)

    with pytest.raises(ValueError):
        HistoricalOhlcvRequest(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", metadata=[])


def test_build_historical_ohlcv_request():
    request = build_historical_ohlcv_request(
        provider_id="provider-1",
        symbol="xauusd",
        timeframe="h1",
    )

    assert isinstance(request, HistoricalOhlcvRequest)
    assert request.to_dict()["symbol"] == "XAUUSD"


def test_live_quote_and_tick_requests():
    quote_request = LiveQuoteRequest(
        provider_id=" provider-1 ",
        symbol=" xauusd ",
        price_type=" BID ",
        metadata={
            "source": "test",
        },
    )
    tick_request = TickDataRequest(
        provider_id=" provider-1 ",
        symbol=" btc/usdt ",
        limit=50,
    )

    assert quote_request.to_dict() == {
        "request_type": "live_quote",
        "provider_id": "provider-1",
        "symbol": "XAUUSD",
        "price_type": "bid",
        "metadata": {
            "source": "test",
        },
    }
    assert tick_request.to_dict()["symbol"] == "BTC/USDT"
    assert tick_request.to_dict()["limit"] == 50


def test_live_quote_and_tick_requests_reject_invalid_values():
    with pytest.raises(ValueError):
        LiveQuoteRequest(provider_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        LiveQuoteRequest(provider_id="provider-1", symbol="XAUUSD", price_type="bad")

    with pytest.raises(ValueError):
        TickDataRequest(provider_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TickDataRequest(provider_id="provider-1", symbol="XAUUSD", limit=0)


def test_build_live_quote_and_tick_requests():
    quote_request = build_live_quote_request(
        provider_id="provider-1",
        symbol="xauusd",
    )
    tick_request = build_tick_data_request(
        provider_id="provider-1",
        symbol="xauusd",
    )

    assert isinstance(quote_request, LiveQuoteRequest)
    assert isinstance(tick_request, TickDataRequest)


def test_ohlcv_candle_to_dict():
    candle = build_candle()

    payload = candle.to_dict()

    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "H1"
    assert payload["timestamp"] == "2026-01-01T00:00:00+00:00"
    assert payload["open"] == 2000.0
    assert payload["high"] == 2020.0
    assert payload["low"] == 1990.0
    assert payload["close"] == 2010.0
    assert payload["volume"] == 100.0
    assert payload["quality"] == "validated"
    assert payload["typical_price"] == 2006.666667
    assert payload["range"] == 30.0
    assert payload["bullish"] is True
    assert payload["bearish"] is False


def test_ohlcv_candle_rejects_invalid_values():
    with pytest.raises(ValueError):
        OhlcvCandle(symbol="", timeframe="H1", timestamp="2026-01-01", open=1, high=2, low=1, close=1)

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H2", timestamp="2026-01-01", open=1, high=2, low=1, close=1)

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H1", timestamp="", open=1, high=2, low=1, close=1)

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H1", timestamp="2026-01-01", open=0, high=2, low=1, close=1)

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H1", timestamp="2026-01-01", open=2, high=1, low=1, close=2)

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H1", timestamp="2026-01-01", open=1, high=2, low=2, close=1)

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H1", timestamp="2026-01-01", open=1, high=2, low=1, close=1, volume=-1)

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H1", timestamp="2026-01-01", open=1, high=2, low=1, close=1, quality="bad")

    with pytest.raises(ValueError):
        OhlcvCandle(symbol="XAUUSD", timeframe="H1", timestamp="2026-01-01", open=1, high=2, low=1, close=1, metadata=[])


def test_market_quote_to_dict_and_prices():
    quote = MarketQuote(
        provider_id=" provider-1 ",
        symbol=" xauusd ",
        bid=2000,
        ask=2002,
        last=2001,
        timestamp="2026-01-01T00:00:00+00:00",
        quality="VALIDATED",
        metadata={
            "source": "test",
        },
    )

    assert quote.spread == 2.0
    assert quote.mid == 2001.0
    assert quote.effective_last == 2001.0
    assert quote.price("bid") == 2000.0
    assert quote.price("ask") == 2002.0
    assert quote.price("mid") == 2001.0
    assert quote.price("last") == 2001.0

    payload = quote.to_dict()

    assert payload["provider_id"] == "provider-1"
    assert payload["symbol"] == "XAUUSD"
    assert payload["quality"] == "validated"


def test_market_quote_rejects_invalid_values():
    with pytest.raises(ValueError):
        MarketQuote(provider_id="", symbol="XAUUSD", bid=1, ask=2)

    with pytest.raises(ValueError):
        MarketQuote(provider_id="provider-1", symbol="bad symbol", bid=1, ask=2)

    with pytest.raises(ValueError):
        MarketQuote(provider_id="provider-1", symbol="XAUUSD", bid=0, ask=2)

    with pytest.raises(ValueError):
        MarketQuote(provider_id="provider-1", symbol="XAUUSD", bid=2, ask=1)

    with pytest.raises(ValueError):
        MarketQuote(provider_id="provider-1", symbol="XAUUSD", bid=1, ask=2, last=-1)

    with pytest.raises(ValueError):
        MarketQuote(provider_id="provider-1", symbol="XAUUSD", bid=1, ask=2, timestamp="")

    with pytest.raises(ValueError):
        MarketQuote(provider_id="provider-1", symbol="XAUUSD", bid=1, ask=2, metadata=[])


def test_build_market_quote():
    quote = build_market_quote(
        provider_id="provider-1",
        symbol="xauusd",
        bid=2000,
        ask=2002,
    )

    assert isinstance(quote, MarketQuote)
    assert quote.effective_last == 2001.0


def test_market_tick_to_dict():
    tick = MarketTick(
        provider_id=" provider-1 ",
        symbol=" xauusd ",
        price=2000,
        volume=10,
        price_type=" BID ",
        timestamp="2026-01-01T00:00:00+00:00",
    )

    assert tick.to_dict() == {
        "provider_id": "provider-1",
        "symbol": "XAUUSD",
        "price": 2000.0,
        "volume": 10.0,
        "price_type": "bid",
        "timestamp": "2026-01-01T00:00:00+00:00",
        "metadata": {},
    }


def test_market_tick_rejects_invalid_values():
    with pytest.raises(ValueError):
        MarketTick(provider_id="", symbol="XAUUSD", price=1)

    with pytest.raises(ValueError):
        MarketTick(provider_id="provider-1", symbol="bad symbol", price=1)

    with pytest.raises(ValueError):
        MarketTick(provider_id="provider-1", symbol="XAUUSD", price=0)

    with pytest.raises(ValueError):
        MarketTick(provider_id="provider-1", symbol="XAUUSD", price=1, volume=-1)

    with pytest.raises(ValueError):
        MarketTick(provider_id="provider-1", symbol="XAUUSD", price=1, price_type="bad")

    with pytest.raises(ValueError):
        MarketTick(provider_id="provider-1", symbol="XAUUSD", price=1, timestamp="")

    with pytest.raises(ValueError):
        MarketTick(provider_id="provider-1", symbol="XAUUSD", price=1, metadata=[])


def test_market_data_batch_to_dict():
    candles = [
        build_candle("2026-01-01T00:00:00+00:00"),
        build_candle("2026-01-01T01:00:00+00:00"),
    ]
    batch = MarketDataBatch(
        provider_id=" provider-1 ",
        symbol=" xauusd ",
        timeframe=" h1 ",
        candles=candles,
        quality="VALIDATED",
        metadata={
            "source": "test",
        },
    )

    payload = batch.to_dict()

    assert batch.count == 2
    assert batch.empty is False
    assert batch.latest_close == 2010.0
    assert batch.close_prices() == [2010.0, 2010.0]
    assert payload["provider_id"] == "provider-1"
    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "H1"
    assert payload["count"] == 2
    assert payload["first_timestamp"] == "2026-01-01T00:00:00+00:00"
    assert payload["latest_timestamp"] == "2026-01-01T01:00:00+00:00"
    assert len(payload["candles"]) == 2


def test_market_data_batch_rejects_invalid_values():
    candle = build_candle()
    wrong_symbol = build_ohlcv_candle(
        symbol="BTCUSDT",
        timeframe="H1",
        timestamp="2026-01-01",
        open=1,
        high=2,
        low=1,
        close=1,
    )
    wrong_timeframe = build_ohlcv_candle(
        symbol="XAUUSD",
        timeframe="M5",
        timestamp="2026-01-01",
        open=1,
        high=2,
        low=1,
        close=1,
    )

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="", symbol="XAUUSD", timeframe="H1")

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="provider-1", symbol="bad symbol", timeframe="H1")

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="provider-1", symbol="XAUUSD", timeframe="H2")

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", candles=["bad"])

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", candles=[wrong_symbol])

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", candles=[wrong_timeframe])

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", candles=[candle], quality="bad")

    with pytest.raises(ValueError):
        MarketDataBatch(provider_id="provider-1", symbol="XAUUSD", timeframe="H1", candles=[candle], metadata=[])


def test_empty_market_data_batch():
    batch = build_market_data_batch(
        provider_id="provider-1",
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert batch.empty is True
    assert batch.count == 0
    assert batch.latest_close == 0.0
    assert batch.first_timestamp == ""
    assert batch.latest_timestamp == ""


def test_validate_candles_and_ticks():
    candle = build_candle()
    tick = build_market_tick(
        provider_id="provider-1",
        symbol="XAUUSD",
        price=2000,
    )

    assert validate_ohlcv_candles([candle]) == [candle]
    assert validate_market_ticks([tick]) == [tick]

    with pytest.raises(ValueError):
        validate_ohlcv_candles("bad")

    with pytest.raises(ValueError):
        validate_ohlcv_candles(["bad"])

    with pytest.raises(ValueError):
        validate_market_ticks("bad")

    with pytest.raises(ValueError):
        validate_market_ticks(["bad"])


def test_provider_result_helpers():
    batch = build_market_data_batch(
        provider_id="provider-1",
        symbol="XAUUSD",
        timeframe="H1",
        candles=[build_candle()],
    )
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

    batch_result = market_data_batch_to_provider_result(batch)
    quote_result = market_quote_to_provider_result(quote)
    ticks_result = market_ticks_to_provider_result(
        provider_id="provider-1",
        ticks=[tick],
    )
    error_result = market_data_error_result(
        provider_id="provider-1",
        error="failed",
        request_type="historical_ohlcv",
    )

    assert batch_result.success is True
    assert batch_result.metadata["capability"] == ProviderCapability.HISTORICAL_OHLCV.value
    assert quote_result.success is True
    assert quote_result.metadata["capability"] == ProviderCapability.LIVE_QUOTES.value
    assert ticks_result.success is True
    assert ticks_result.data["count"] == 1
    assert error_result.success is False
    assert error_result.metadata["request_type"] == "historical_ohlcv"

    with pytest.raises(ValueError):
        market_data_batch_to_provider_result("bad")

    with pytest.raises(ValueError):
        market_quote_to_provider_result("bad")

    with pytest.raises(ValueError):
        market_ticks_to_provider_result(provider_id="provider-1", ticks=["bad"])


def test_candle_row_conversion_helpers():
    candles = [build_candle()]
    rows = candles_to_ohlcv_rows(candles)

    assert rows == [
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "open": 2000.0,
            "high": 2020.0,
            "low": 1990.0,
            "close": 2010.0,
            "volume": 100.0,
        },
    ]

    converted = ohlcv_rows_to_candles(
        rows=rows,
        symbol="xauusd",
        timeframe="h1",
        quality="validated",
    )

    assert len(converted) == 1
    assert converted[0].symbol == "xauusd"
    assert converted[0].to_dict()["symbol"] == "XAUUSD"
    assert converted[0].quality == "validated"

    with pytest.raises(ValueError):
        ohlcv_rows_to_candles(
            rows="bad",
            symbol="XAUUSD",
            timeframe="H1",
        )

    with pytest.raises(KeyError):
        ohlcv_rows_to_candles(
            rows=[{}],
            symbol="XAUUSD",
            timeframe="H1",
        )


def test_market_data_exports_exist():
    import aqos.providers as providers

    expected_exports = [
        "HistoricalOhlcvRequest",
        "LiveQuoteRequest",
        "MarketDataBatch",
        "MarketDataPriceType",
        "MarketDataQuality",
        "MarketDataRequestType",
        "MarketDataTimeframe",
        "MarketQuote",
        "MarketTick",
        "OhlcvCandle",
        "TickDataRequest",
        "build_historical_ohlcv_request",
        "build_live_quote_request",
        "build_market_data_batch",
        "build_market_quote",
        "build_market_tick",
        "build_ohlcv_candle",
        "build_tick_data_request",
        "candles_to_ohlcv_rows",
        "market_data_batch_to_provider_result",
        "market_data_error_result",
        "market_quote_to_provider_result",
        "market_ticks_to_provider_result",
        "normalize_market_data_price_type",
        "normalize_market_data_quality",
        "normalize_market_data_request_type",
        "normalize_market_data_timeframe",
        "ohlcv_rows_to_candles",
        "validate_market_data_limit",
        "validate_market_symbol",
        "validate_market_ticks",
        "validate_ohlcv_candles",
    ]

    for export_name in expected_exports:
        assert hasattr(providers, export_name), export_name