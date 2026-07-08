"""
Unit tests for AQOS HTTP market data provider.
"""

import pytest

from aqos.providers import (
    HttpMarketDataProvider,
    HttpProviderMethod,
    HttpProviderRequest,
    HttpProviderResponse,
    MarketQuote,
    MarketTick,
    ProviderStatus,
    build_historical_ohlcv_request,
    build_http_market_data_provider,
    build_http_provider_request,
    build_http_provider_response,
    build_live_quote_request,
    build_provider_config,
    build_tick_data_request,
    fetch_http_historical_ohlcv,
    fetch_http_live_quote,
    fetch_http_market_ticks,
    http_provider_error_result,
    is_success_http_status,
    join_http_url,
    json_payload_to_market_quote,
    json_payload_to_market_ticks,
    json_payload_to_ohlcv_rows,
    normalize_http_provider_method,
    validate_http_headers,
    validate_http_params,
    validate_http_provider_config,
    validate_http_status_code,
    validate_http_url,
)


def fake_transport(request: HttpProviderRequest) -> HttpProviderResponse:
    if request.url.endswith("/ohlcv"):
        return build_http_provider_response(
            provider_id=request.provider_id,
            status_code=200,
            payload={
                "data": [
                    {
                        "timestamp": "2026-01-01T00:00:00+00:00",
                        "open": 2000,
                        "high": 2020,
                        "low": 1990,
                        "close": 2010,
                        "volume": 100,
                    },
                    {
                        "timestamp": "2026-01-01T01:00:00+00:00",
                        "open": 2010,
                        "high": 2030,
                        "low": 2000,
                        "close": 2025,
                        "volume": 120,
                    },
                ],
            },
            elapsed_ms=12.5,
        )

    if request.url.endswith("/quote"):
        return build_http_provider_response(
            provider_id=request.provider_id,
            status_code=200,
            payload={
                "quote": {
                    "symbol": "XAUUSD",
                    "bid": 2000,
                    "ask": 2002,
                    "last": 2001,
                    "timestamp": "2026-01-01T00:00:00+00:00",
                },
            },
        )

    if request.url.endswith("/ticks"):
        return build_http_provider_response(
            provider_id=request.provider_id,
            status_code=200,
            payload={
                "ticks": [
                    {
                        "symbol": "XAUUSD",
                        "price": 2001,
                        "volume": 10,
                        "price_type": "last",
                        "timestamp": "2026-01-01T00:00:01+00:00",
                    },
                    {
                        "symbol": "XAUUSD",
                        "price": 2002,
                        "volume": 12,
                        "price_type": "last",
                        "timestamp": "2026-01-01T00:00:02+00:00",
                    },
                ],
            },
        )

    return build_http_provider_response(
        provider_id=request.provider_id,
        status_code=404,
        payload={
            "error": "not found",
        },
    )


def failing_transport(request: HttpProviderRequest) -> HttpProviderResponse:
    return build_http_provider_response(
        provider_id=request.provider_id,
        status_code=500,
        payload={
            "error": "failed",
        },
    )


def build_provider(transport=fake_transport) -> HttpMarketDataProvider:
    return build_http_market_data_provider(
        provider_id="http-1",
        base_url="https://example.com/api",
        transport=transport,
    )


def test_http_method_enum_and_normalizer():
    assert HttpProviderMethod.GET.value == "GET"
    assert HttpProviderMethod.POST.value == "POST"

    assert normalize_http_provider_method(HttpProviderMethod.GET) == HttpProviderMethod.GET
    assert normalize_http_provider_method(" post ") == HttpProviderMethod.POST

    with pytest.raises(ValueError):
        normalize_http_provider_method("PATCH")


def test_http_validators():
    assert validate_http_url("https://example.com") == "https://example.com"
    assert validate_http_status_code(200) == 200
    assert validate_http_params({"symbol": "XAUUSD"}) == {"symbol": "XAUUSD"}
    assert validate_http_headers({"Accept": "application/json"}) == {"Accept": "application/json"}

    assert is_success_http_status(200) is True
    assert is_success_http_status(299) is True
    assert is_success_http_status(300) is False

    with pytest.raises(ValueError):
        validate_http_url("ftp://example.com")

    with pytest.raises(ValueError):
        validate_http_status_code(99)

    with pytest.raises(ValueError):
        validate_http_status_code(600)

    with pytest.raises(ValueError):
        validate_http_status_code(True)

    with pytest.raises(ValueError):
        validate_http_params([])

    with pytest.raises(ValueError):
        validate_http_params({"": "bad"})

    with pytest.raises(ValueError):
        validate_http_headers([])

    with pytest.raises(ValueError):
        validate_http_headers({"": "bad"})

    with pytest.raises(ValueError):
        validate_http_headers({"Accept": 123})


def test_join_http_url():
    assert join_http_url("https://example.com/api", "/ohlcv") == "https://example.com/api/ohlcv"
    assert join_http_url("https://example.com/api/", "ohlcv") == "https://example.com/api/ohlcv"
    assert join_http_url("https://example.com", "https://other.com/quote") == "https://other.com/quote"

    with pytest.raises(ValueError):
        join_http_url("bad", "/ohlcv")

    with pytest.raises(ValueError):
        join_http_url("https://example.com", "")


def test_http_provider_request_to_dict():
    request = HttpProviderRequest(
        provider_id=" provider-1 ",
        method=" get ",
        url="https://example.com/ohlcv",
        params={
            "symbol": "XAUUSD",
            "empty": "",
        },
        headers={
            "Accept": "application/json",
        },
        timeout_seconds=10,
        metadata={
            "source": "test",
        },
    )

    payload = request.to_dict()

    assert payload["provider_id"] == "provider-1"
    assert payload["method"] == "GET"
    assert payload["url"] == "https://example.com/ohlcv"
    assert payload["resolved_url"] == "https://example.com/ohlcv?symbol=XAUUSD"
    assert payload["timeout_seconds"] == 10.0


def test_http_provider_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="", method="GET", url="https://example.com")

    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="provider-1", method="BAD", url="https://example.com")

    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="provider-1", method="GET", url="bad")

    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="provider-1", method="GET", url="https://example.com", params=[])

    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="provider-1", method="GET", url="https://example.com", headers=[])

    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="provider-1", method="GET", url="https://example.com", body=[])

    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="provider-1", method="GET", url="https://example.com", timeout_seconds=0)

    with pytest.raises(ValueError):
        HttpProviderRequest(provider_id="provider-1", method="GET", url="https://example.com", metadata=[])


def test_build_http_provider_request():
    request = build_http_provider_request(
        provider_id="provider-1",
        method="GET",
        url="https://example.com",
    )

    assert isinstance(request, HttpProviderRequest)


def test_http_provider_response_to_dict():
    response = HttpProviderResponse(
        provider_id=" provider-1 ",
        status_code=200,
        payload={
            "ok": True,
        },
        headers={
            "Content-Type": "application/json",
        },
        elapsed_ms=12.5,
        metadata={
            "source": "test",
        },
    )

    assert response.success is True
    assert response.failed is False
    assert response.to_dict() == {
        "provider_id": "provider-1",
        "status_code": 200,
        "success": True,
        "failed": False,
        "payload": {
            "ok": True,
        },
        "headers": {
            "Content-Type": "application/json",
        },
        "elapsed_ms": 12.5,
        "metadata": {
            "source": "test",
        },
    }


def test_http_provider_response_rejects_invalid_values():
    with pytest.raises(ValueError):
        HttpProviderResponse(provider_id="", status_code=200, payload={})

    with pytest.raises(ValueError):
        HttpProviderResponse(provider_id="provider-1", status_code=99, payload={})

    with pytest.raises(ValueError):
        HttpProviderResponse(provider_id="provider-1", status_code=200, payload="bad")

    with pytest.raises(ValueError):
        HttpProviderResponse(provider_id="provider-1", status_code=200, payload={}, headers=[])

    with pytest.raises(ValueError):
        HttpProviderResponse(provider_id="provider-1", status_code=200, payload={}, elapsed_ms=-1)

    with pytest.raises(ValueError):
        HttpProviderResponse(provider_id="provider-1", status_code=200, payload={}, metadata=[])


def test_validate_http_provider_config():
    config = build_provider_config(
        provider_id="http-1",
        name="HTTP",
        provider_type="market_data",
        base_url="https://example.com",
        capabilities=["historical_ohlcv"],
    )

    assert validate_http_provider_config(config) == config

    with pytest.raises(ValueError):
        validate_http_provider_config("bad")

    with pytest.raises(ValueError):
        validate_http_provider_config(
            build_provider_config(
                provider_id="bad",
                name="Bad",
                provider_type="broker",
                base_url="https://example.com",
                capabilities=["historical_ohlcv"],
            ),
        )

    with pytest.raises(ValueError):
        validate_http_provider_config(
            build_provider_config(
                provider_id="bad",
                name="Bad",
                provider_type="market_data",
                base_url="bad",
                capabilities=["historical_ohlcv"],
            ),
        )

    with pytest.raises(ValueError):
        validate_http_provider_config(
            build_provider_config(
                provider_id="bad",
                name="Bad",
                provider_type="market_data",
                base_url="https://example.com",
                capabilities=["news_feed"],
            ),
        )


def test_build_http_market_data_provider():
    provider = build_provider()

    assert isinstance(provider, HttpMarketDataProvider)
    assert provider.provider_id == "http-1"
    assert provider.base_url == "https://example.com/api"
    assert provider.active is True


def test_http_market_data_provider_rejects_invalid_values():
    config = build_provider_config(
        provider_id="http-1",
        name="HTTP",
        provider_type="market_data",
        base_url="https://example.com",
        capabilities=["historical_ohlcv"],
    )

    with pytest.raises(ValueError):
        HttpMarketDataProvider(provider_config="bad")

    with pytest.raises(ValueError):
        HttpMarketDataProvider(provider_config=config, transport="bad")

    with pytest.raises(ValueError):
        HttpMarketDataProvider(provider_config=config, metadata=[])


def test_http_market_data_provider_request():
    provider = build_provider()
    request = build_http_provider_request(
        provider_id="http-1",
        method="GET",
        url="https://example.com/api/quote",
    )

    response = provider.request(request)

    assert response.success is True
    assert response.payload["quote"]["symbol"] == "XAUUSD"

    wrong_request = build_http_provider_request(
        provider_id="other",
        method="GET",
        url="https://example.com/api/quote",
    )

    with pytest.raises(ValueError):
        provider.request("bad")

    with pytest.raises(ValueError):
        provider.request(wrong_request)


def test_json_payload_to_ohlcv_rows():
    rows = json_payload_to_ohlcv_rows(
        payload={
            "data": [
                {
                    "time": "2026-01-01T00:00:00+00:00",
                    "o": 2000,
                    "h": 2020,
                    "l": 1990,
                    "c": 2010,
                    "v": 100,
                }
            ],
        },
        field_map={
            "timestamp": "time",
            "open": "o",
            "high": "h",
            "low": "l",
            "close": "c",
            "volume": "v",
        },
    )

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

    list_rows = json_payload_to_ohlcv_rows(
        payload=[
            {
                "timestamp": "2026-01-01",
                "open": 1,
                "high": 2,
                "low": 1,
                "close": 2,
            }
        ],
        records_key="",
    )

    assert list_rows[0]["volume"] == 0.0

    with pytest.raises(ValueError):
        json_payload_to_ohlcv_rows(payload={"data": {}})

    with pytest.raises(KeyError):
        json_payload_to_ohlcv_rows(payload={"data": [{}]})


def test_json_payload_to_market_quote():
    quote = json_payload_to_market_quote(
        provider_id="provider-1",
        payload={
            "quote": {
                "symbol": "XAUUSD",
                "bid": 2000,
                "ask": 2002,
                "last": 2001,
                "timestamp": "2026-01-01T00:00:00+00:00",
            },
        },
    )

    direct_quote = json_payload_to_market_quote(
        provider_id="provider-1",
        payload={
            "s": "XAUUSD",
            "b": 2000,
            "a": 2002,
        },
        quote_key="",
        field_map={
            "symbol": "s",
            "bid": "b",
            "ask": "a",
        },
    )

    assert isinstance(quote, MarketQuote)
    assert quote.mid == 2001.0
    assert direct_quote.mid == 2001.0

    with pytest.raises(ValueError):
        json_payload_to_market_quote(provider_id="", payload={})

    with pytest.raises(ValueError):
        json_payload_to_market_quote(provider_id="provider-1", payload=[])

    with pytest.raises(KeyError):
        json_payload_to_market_quote(provider_id="provider-1", payload={})


def test_json_payload_to_market_ticks():
    ticks = json_payload_to_market_ticks(
        provider_id="provider-1",
        payload={
            "ticks": [
                {
                    "symbol": "XAUUSD",
                    "price": 2001,
                    "volume": 10,
                    "price_type": "last",
                    "timestamp": "2026-01-01T00:00:01+00:00",
                }
            ],
        },
    )

    assert len(ticks) == 1
    assert isinstance(ticks[0], MarketTick)
    assert ticks[0].price == 2001

    with pytest.raises(ValueError):
        json_payload_to_market_ticks(provider_id="", payload={})

    with pytest.raises(ValueError):
        json_payload_to_market_ticks(provider_id="provider-1", payload={"ticks": {}})

    with pytest.raises(KeyError):
        json_payload_to_market_ticks(provider_id="provider-1", payload={"ticks": [{}]})


def test_fetch_http_historical_ohlcv_success():
    provider = build_provider()
    request = build_historical_ohlcv_request(
        provider_id="http-1",
        symbol="XAUUSD",
        timeframe="H1",
        limit=100,
    )

    result = provider.fetch_historical_ohlcv(request)

    assert result.success is True
    assert result.provider_id == "http-1"
    assert result.metadata["capability"] == "historical_ohlcv"
    assert result.data["batch"]["count"] == 2
    assert result.data["batch"]["latest_close"] == 2025.0


def test_fetch_http_historical_ohlcv_helper():
    provider = build_provider()
    request = build_historical_ohlcv_request(
        provider_id="http-1",
        symbol="XAUUSD",
        timeframe="H1",
    )

    result = fetch_http_historical_ohlcv(
        provider=provider,
        request=request,
    )

    assert result.success is True

    with pytest.raises(ValueError):
        fetch_http_historical_ohlcv(provider="bad", request=request)


def test_fetch_http_live_quote_success():
    provider = build_provider()
    request = build_live_quote_request(
        provider_id="http-1",
        symbol="XAUUSD",
    )

    result = provider.fetch_live_quote(request)

    assert result.success is True
    assert result.metadata["capability"] == "live_quotes"
    assert result.data["quote"]["symbol"] == "XAUUSD"
    assert result.data["quote"]["mid"] == 2001.0


def test_fetch_http_live_quote_helper():
    provider = build_provider()
    request = build_live_quote_request(
        provider_id="http-1",
        symbol="XAUUSD",
    )

    result = fetch_http_live_quote(
        provider=provider,
        request=request,
    )

    assert result.success is True

    with pytest.raises(ValueError):
        fetch_http_live_quote(provider="bad", request=request)


def test_fetch_http_market_ticks_success():
    provider = build_provider()
    request = build_tick_data_request(
        provider_id="http-1",
        symbol="XAUUSD",
        limit=1,
    )

    result = provider.fetch_ticks(request)

    assert result.success is True
    assert result.metadata["capability"] == "ticks"
    assert result.data["count"] == 1
    assert result.data["ticks"][0]["price"] == 2001.0


def test_fetch_http_market_ticks_helper():
    provider = build_provider()
    request = build_tick_data_request(
        provider_id="http-1",
        symbol="XAUUSD",
    )

    result = fetch_http_market_ticks(
        provider=provider,
        request=request,
    )

    assert result.success is True

    with pytest.raises(ValueError):
        fetch_http_market_ticks(provider="bad", request=request)


def test_http_fetch_failures():
    provider = build_provider()

    wrong_provider_request = build_historical_ohlcv_request(
        provider_id="other",
        symbol="XAUUSD",
        timeframe="H1",
    )
    wrong_provider_result = provider.fetch_historical_ohlcv(wrong_provider_request)

    failing_provider = build_provider(transport=failing_transport)
    failing_result = failing_provider.fetch_historical_ohlcv(
        build_historical_ohlcv_request(
            provider_id="http-1",
            symbol="XAUUSD",
            timeframe="H1",
        ),
    )

    inactive_provider = build_http_market_data_provider(
        provider_id="inactive",
        base_url="https://example.com",
        status=ProviderStatus.INACTIVE,
        transport=fake_transport,
    )
    inactive_result = inactive_provider.fetch_live_quote(
        build_live_quote_request(
            provider_id="inactive",
            symbol="XAUUSD",
        ),
    )

    no_capability_provider = build_http_market_data_provider(
        provider_config=build_provider_config(
            provider_id="no-live",
            name="No Live",
            provider_type="market_data",
            base_url="https://example.com",
            capabilities=["historical_ohlcv"],
        ),
        transport=fake_transport,
    )
    no_capability_result = no_capability_provider.fetch_live_quote(
        build_live_quote_request(
            provider_id="no-live",
            symbol="XAUUSD",
        ),
    )

    assert wrong_provider_result.success is False
    assert failing_result.success is False
    assert failing_result.metadata["status_code"] == 500
    assert inactive_result.success is False
    assert no_capability_result.success is False

    with pytest.raises(ValueError):
        provider.fetch_historical_ohlcv("bad")

    with pytest.raises(ValueError):
        provider.fetch_live_quote("bad")

    with pytest.raises(ValueError):
        provider.fetch_ticks("bad")


def test_http_provider_error_result():
    result = http_provider_error_result(
        provider_id="http-1",
        error="failed",
        request_type="historical_ohlcv",
    )

    assert result.success is False
    assert result.error == "failed"
    assert result.metadata["transport"] == "http"


def test_http_provider_exports_exist():
    import aqos.providers as providers

    expected_exports = [
        "HttpMarketDataProvider",
        "HttpProviderMethod",
        "HttpProviderRequest",
        "HttpProviderResponse",
        "build_http_market_data_provider",
        "build_http_provider_request",
        "build_http_provider_response",
        "default_http_transport",
        "fetch_http_historical_ohlcv",
        "fetch_http_live_quote",
        "fetch_http_market_ticks",
        "http_provider_error_result",
        "is_success_http_status",
        "join_http_url",
        "json_payload_to_market_quote",
        "json_payload_to_market_ticks",
        "json_payload_to_ohlcv_rows",
        "normalize_http_provider_method",
        "validate_http_headers",
        "validate_http_params",
        "validate_http_provider_config",
        "validate_http_status_code",
        "validate_http_url",
    ]

    for export_name in expected_exports:
        assert hasattr(providers, export_name), export_name