"""
Unit tests for AQOS HTTP news provider adapter.
"""

import json

import pytest

from aqos.news_providers import (
    HttpNewsProviderConfig,
    HttpNewsProviderRequest,
    HttpNewsProviderResponse,
    HttpNewsRequestMethod,
    HttpNewsResponseStatus,
    NewsEventRecord,
    NewsFeedArticle,
    NewsFeedProviderResult,
    NewsProviderConfig,
    NewsProviderCredentials,
    NewsProviderResult,
    build_http_auth_headers,
    build_http_auth_query_params,
    build_http_news_headers,
    build_http_news_provider_base_config,
    build_http_news_provider_config,
    build_http_news_provider_request,
    build_http_news_provider_response,
    build_http_news_query_params,
    build_http_news_url,
    build_news_feed_query,
    execute_http_news_request,
    extract_rows_from_http_news_payload,
    http_json_rows_to_news_event_records,
    http_json_rows_to_news_feed_articles,
    http_news_payload_to_feed_result,
    load_http_news_feed_result,
    load_http_news_provider_result,
    normalize_http_news_request_method,
    normalize_http_news_response_status,
    parse_http_news_response_payload,
    prepare_http_json_row,
    validate_http_payload,
    validate_http_string_mapping,
)


def sample_rows():
    return [
        {
            "id": "article-001",
            "published_at": "2026-01-01T10:00:00+00:00",
            "title": "Gold falls after hot CPI",
            "source": "Reuters",
            "url": "https://example.com/gold-cpi",
            "description": "Gold dropped as US inflation beat forecast.",
            "content": "The dollar surged after CPI.",
            "language": "en",
            "country": "US",
            "symbol": "XAUUSD",
            "topics": ["macro", "commodities"],
            "event_type": "news",
            "impact": "high",
            "sentiment": "bearish",
            "relevance_score": 0.95,
        },
        {
            "id": "article-002",
            "published_at": "2026-01-02T12:00:00+00:00",
            "title": "Bitcoin rallies after ETF inflows",
            "source": "CoinDesk",
            "description": "Crypto markets moved higher.",
            "language": "en",
            "country": "US",
            "symbol": "BTC/USDT",
            "topics": ["crypto"],
            "event_type": "crypto",
            "impact": "medium",
            "sentiment": "bullish",
            "relevance_score": 0.9,
        },
    ]


def sample_payload():
    return {
        "articles": sample_rows(),
    }


def sample_config():
    return build_http_news_provider_config(
        provider_id="http-news",
        name="HTTP News",
        base_url="https://example.com",
        endpoint="/api/news",
        credentials=NewsProviderCredentials(
            auth_type="api_key",
            api_key="secret",
        ),
        api_key_header="X-API-Key",
        default_headers={"Accept": "application/json"},
        default_query_params={"language": "en"},
        payload_key="articles",
    )


def test_http_enums_and_normalizers():
    assert HttpNewsRequestMethod.GET.value == "GET"
    assert HttpNewsRequestMethod.POST.value == "POST"

    assert HttpNewsResponseStatus.OK.value == "ok"
    assert HttpNewsResponseStatus.ERROR.value == "error"
    assert HttpNewsResponseStatus.TIMEOUT.value == "timeout"
    assert HttpNewsResponseStatus.INVALID_RESPONSE.value == "invalid_response"

    assert normalize_http_news_request_method(HttpNewsRequestMethod.GET) == HttpNewsRequestMethod.GET
    assert normalize_http_news_request_method(" post ") == HttpNewsRequestMethod.POST
    assert normalize_http_news_response_status(HttpNewsResponseStatus.OK) == HttpNewsResponseStatus.OK
    assert normalize_http_news_response_status(" ERROR ") == HttpNewsResponseStatus.ERROR

    with pytest.raises(ValueError):
        normalize_http_news_request_method("bad")

    with pytest.raises(ValueError):
        normalize_http_news_response_status("bad")


def test_http_validators():
    assert validate_http_string_mapping({"Accept": "application/json"}, "Headers") == {
        "Accept": "application/json",
    }
    assert validate_http_payload({"articles": []}) == {"articles": []}
    assert validate_http_payload([{"id": 1}]) == [{"id": 1}]

    with pytest.raises(ValueError):
        validate_http_string_mapping("bad", "Headers")

    with pytest.raises(ValueError):
        validate_http_string_mapping({"": "value"}, "Headers")

    with pytest.raises(ValueError):
        validate_http_string_mapping({"Accept": 123}, "Headers")

    with pytest.raises(ValueError):
        validate_http_payload("bad")

    with pytest.raises(ValueError):
        validate_http_payload(["bad"])


def test_http_provider_config_to_dict_and_builder():
    config = HttpNewsProviderConfig(
        provider_id=" provider ",
        name=" Provider ",
        base_url=" https://example.com ",
        endpoint=" /news ",
        credentials=NewsProviderCredentials(auth_type="bearer_token", bearer_token="token"),
        default_headers={"Accept": "application/json"},
        default_query_params={"limit": 10},
        timeout_seconds=20,
        payload_key="articles",
        symbol=" xauusd ",
        metadata={"source": "test"},
    )

    payload = config.to_dict()
    built = sample_config()

    assert config.has_endpoint is True
    assert config.url == "https://example.com/news"
    assert payload["provider_id"] == "provider"
    assert payload["name"] == "Provider"
    assert payload["symbol"] == "XAUUSD"
    assert payload["payload_key"] == "articles"
    assert isinstance(built, HttpNewsProviderConfig)

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="", name="Provider", base_url="https://example.com")

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="provider", name="", base_url="https://example.com")

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="provider", name="Provider", base_url="")

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="provider", name="Provider", base_url="https://example.com", credentials="bad")

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="provider", name="Provider", base_url="https://example.com", default_headers=[])

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="provider", name="Provider", base_url="https://example.com", timeout_seconds=0)

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="provider", name="Provider", base_url="https://example.com", symbol="bad symbol")

    with pytest.raises(ValueError):
        HttpNewsProviderConfig(provider_id="provider", name="Provider", base_url="https://example.com", metadata=[])


def test_http_provider_base_config():
    config = build_http_news_provider_base_config(
        provider_id="http",
        name="HTTP Provider",
        base_url="https://example.com",
        status="active",
    )

    assert isinstance(config, NewsProviderConfig)
    assert config.provider_type.value == "http"
    assert config.active is True
    assert config.has_capability("live_news") is True
    assert config.has_capability("sentiment") is True


def test_build_http_url_auth_headers_and_params():
    config = sample_config()

    assert build_http_news_url(base_url="https://example.com", endpoint="/news") == "https://example.com/news"
    assert build_http_news_url(base_url="https://example.com", endpoint="https://api.example.com/news") == "https://api.example.com/news"

    headers = build_http_news_headers(
        config,
        headers={"User-Agent": "AQOS"},
    )
    params = build_http_news_query_params(
        config,
        query_params={"q": "gold"},
    )

    assert headers["Accept"] == "application/json"
    assert headers["X-API-Key"] == "secret"
    assert headers["User-Agent"] == "AQOS"
    assert params == {"language": "en", "q": "gold"}

    query_credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    assert build_http_auth_query_params(query_credentials, api_key_query_param="token") == {
        "token": "secret",
    }

    bearer_headers = build_http_auth_headers(
        NewsProviderCredentials(
            auth_type="bearer_token",
            bearer_token="token",
        )
    )
    assert bearer_headers["Authorization"] == "Bearer token"

    basic_headers = build_http_auth_headers(
        NewsProviderCredentials(
            auth_type="basic",
            username="user",
            password="pass",
        )
    )
    assert basic_headers["Authorization"].startswith("Basic ")

    with pytest.raises(ValueError):
        build_http_news_headers("bad")

    with pytest.raises(ValueError):
        build_http_news_query_params("bad")

    with pytest.raises(ValueError):
        build_http_auth_headers("bad")

    with pytest.raises(ValueError):
        build_http_auth_query_params("bad")


def test_http_provider_request_to_dict_and_builder():
    request = build_http_news_provider_request(
        sample_config(),
        query_params={"q": "gold"},
        headers={"User-Agent": "AQOS"},
    )
    payload = request.to_dict()

    assert isinstance(request, HttpNewsProviderRequest)
    assert request.method == HttpNewsRequestMethod.GET
    assert request.url == "https://example.com/api/news"
    assert "q=gold" in request.resolved_url
    assert "language=en" in request.resolved_url
    assert payload["method"] == "GET"

    with pytest.raises(ValueError):
        HttpNewsProviderRequest(method="bad", url="https://example.com")

    with pytest.raises(ValueError):
        HttpNewsProviderRequest(method="GET", url="")

    with pytest.raises(ValueError):
        HttpNewsProviderRequest(method="GET", url="https://example.com", headers=[])

    with pytest.raises(ValueError):
        HttpNewsProviderRequest(method="GET", url="https://example.com", query_params=[])

    with pytest.raises(ValueError):
        HttpNewsProviderRequest(method="GET", url="https://example.com", timeout_seconds=0)

    with pytest.raises(ValueError):
        build_http_news_provider_request("bad")


def test_http_provider_response_and_payload_parser():
    response = HttpNewsProviderResponse(
        status=" ok ",
        status_code=200,
        payload=sample_payload(),
        raw_text="",
        headers={"Content-Type": "application/json"},
        message=" OK ",
        elapsed_ms=12.5,
        metadata={"source": "test"},
    )
    payload = response.to_dict()

    assert response.ok is True
    assert payload["status"] == "ok"
    assert payload["status_code"] == 200
    assert parse_http_news_response_payload(response) == sample_payload()

    raw_response = build_http_news_provider_response(
        status="ok",
        status_code=200,
        raw_text=json.dumps(sample_payload()),
    )
    assert parse_http_news_response_payload(raw_response) == sample_payload()

    with pytest.raises(ValueError):
        HttpNewsProviderResponse(status="bad")

    with pytest.raises(ValueError):
        HttpNewsProviderResponse(status="ok", status_code=-1)

    with pytest.raises(ValueError):
        HttpNewsProviderResponse(status="ok", payload="bad")

    with pytest.raises(ValueError):
        HttpNewsProviderResponse(status="ok", raw_text=123)

    with pytest.raises(ValueError):
        HttpNewsProviderResponse(status="ok", headers=[])

    with pytest.raises(ValueError):
        parse_http_news_response_payload("bad")

    with pytest.raises(ValueError):
        parse_http_news_response_payload(
            build_http_news_provider_response(status="ok", status_code=200)
        )

    with pytest.raises(ValueError):
        parse_http_news_response_payload(
            build_http_news_provider_response(status="ok", status_code=200, raw_text="{bad")
        )


def test_execute_http_news_request_with_fetcher():
    request = build_http_news_provider_request(sample_config())

    response = execute_http_news_request(
        request,
        fetcher=lambda _request: sample_payload(),
    )

    assert isinstance(response, HttpNewsProviderResponse)
    assert response.ok is True
    assert response.payload == sample_payload()

    raw_response = execute_http_news_request(
        request,
        fetcher=lambda _request: json.dumps(sample_payload()),
    )

    assert raw_response.raw_text

    direct_response = execute_http_news_request(
        request,
        fetcher=lambda _request: build_http_news_provider_response(
            status="ok",
            status_code=200,
            payload=sample_payload(),
        ),
    )

    assert direct_response.ok is True

    with pytest.raises(ValueError):
        execute_http_news_request("bad")

    with pytest.raises(ValueError):
        execute_http_news_request(request, fetcher=lambda _request: 123)


def test_prepare_rows_and_payload_converters():
    row = {
        "id": "article-001",
        "published_at": "2026-01-01",
        "title": "Gold news",
    }

    prepared = prepare_http_json_row(
        row,
        provider_id="http-news",
        default_symbol="XAUUSD",
    )

    assert prepared["provider_id"] == "http-news"
    assert prepared["symbol"] == "XAUUSD"
    assert prepared["source_type"] == "news_api"

    rows = extract_rows_from_http_news_payload(sample_payload(), key="articles")
    articles = http_json_rows_to_news_feed_articles(
        rows,
        provider_id="http-news",
    )
    records = http_json_rows_to_news_event_records(
        rows,
        provider_id="http-news",
    )

    assert len(rows) == 2
    assert len(articles) == 2
    assert len(records) == 2
    assert isinstance(articles[0], NewsFeedArticle)
    assert isinstance(records[0], NewsEventRecord)
    assert articles[0].provider_id == "http-news"
    assert records[0].provider_id == "http-news"

    with pytest.raises(ValueError):
        prepare_http_json_row("bad")

    with pytest.raises(ValueError):
        http_json_rows_to_news_feed_articles("bad")

    with pytest.raises(ValueError):
        http_json_rows_to_news_event_records("bad")


def test_http_payload_to_feed_and_provider_result():
    config = sample_config()
    feed_result = http_news_payload_to_feed_result(
        sample_payload(),
        config=config,
    )

    assert isinstance(feed_result, NewsFeedProviderResult)
    assert feed_result.success is True
    assert feed_result.article_count == 2

    filtered_feed = http_news_payload_to_feed_result(
        sample_payload(),
        config=config,
        query=build_news_feed_query(symbol="XAUUSD"),
    )

    assert filtered_feed.article_count == 1
    assert filtered_feed.articles[0].symbol == "XAUUSD"

    provider_result = load_http_news_provider_result(
        config,
        payload=sample_payload(),
    )

    assert isinstance(provider_result, NewsProviderResult)
    assert provider_result.success is True
    assert provider_result.record_count == 2
    assert provider_result.records[0].event_id == "article-001"

    with pytest.raises(ValueError):
        http_news_payload_to_feed_result(sample_payload(), config="bad")


def test_load_http_news_with_fetcher_and_failure():
    config = sample_config()

    feed_result = load_http_news_feed_result(
        config,
        fetcher=lambda _request: sample_payload(),
    )

    assert isinstance(feed_result, NewsFeedProviderResult)
    assert feed_result.success is True
    assert feed_result.article_count == 2

    provider_result = load_http_news_provider_result(
        config,
        fetcher=lambda _request: sample_payload(),
        query=build_news_feed_query(symbol="BTC/USDT"),
    )

    assert provider_result.success is True
    assert provider_result.record_count == 1
    assert provider_result.records[0].symbol == "BTC/USDT"

    failure = load_http_news_provider_result(
        config,
        payload={"missing": []},
    )

    assert failure.failed is True
    assert failure.issue_count == 1

    with pytest.raises(ValueError):
        load_http_news_feed_result("bad")

    with pytest.raises(ValueError):
        load_http_news_provider_result("bad")


def test_news_providers_http_provider_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "HttpNewsProviderConfig",
        "HttpNewsProviderRequest",
        "HttpNewsProviderResponse",
        "HttpNewsRequestMethod",
        "HttpNewsResponseStatus",
        "build_http_auth_headers",
        "build_http_auth_query_params",
        "build_http_news_headers",
        "build_http_news_provider_base_config",
        "build_http_news_provider_config",
        "build_http_news_provider_request",
        "build_http_news_provider_response",
        "build_http_news_query_params",
        "build_http_news_url",
        "execute_http_news_request",
        "extract_rows_from_http_news_payload",
        "http_json_rows_to_news_event_records",
        "http_json_rows_to_news_feed_articles",
        "http_news_payload_to_feed_result",
        "load_http_news_feed_result",
        "load_http_news_provider_result",
        "normalize_http_news_request_method",
        "normalize_http_news_response_status",
        "parse_http_news_response_payload",
        "prepare_http_json_row",
        "validate_http_payload",
        "validate_http_string_mapping",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name