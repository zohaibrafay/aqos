"""
Unit tests for AQOS Finnhub news connector.
"""

import pytest

from aqos.news_providers import (
    FinnhubNewsCategory,
    FinnhubNewsEndpoint,
    FinnhubNewsQuery,
    HttpNewsProviderConfig,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorRuntimeConfig,
    NewsProviderCredentials,
    NewsProviderResult,
    build_finnhub_connector_definition,
    build_finnhub_http_config,
    build_finnhub_news_query,
    build_finnhub_runtime_config,
    finnhub_category_to_topic,
    finnhub_query_to_query_params,
    finnhub_raw_row_to_normalized_news_row,
    load_finnhub_news_feed_result,
    load_finnhub_news_provider_result,
    normalize_finnhub_news_category,
    normalize_finnhub_news_endpoint,
    normalize_finnhub_payload,
)


def sample_finnhub_payload():
    return [
        {
            "category": "general",
            "datetime": "2026-07-09T12:00:00Z",
            "headline": "Gold rises after inflation data",
            "id": 101,
            "image": "https://example.com/gold.png",
            "related": "XAUUSD",
            "source": "Example Finance",
            "summary": "Gold moved higher after inflation cooled.",
            "url": "https://example.com/gold-inflation",
        },
        {
            "category": "general",
            "datetime": "2026-07-09T13:00:00Z",
            "headline": "Dollar weakens after Fed comments",
            "id": 102,
            "image": "https://example.com/usd.png",
            "related": "USD",
            "source": "Example Finance",
            "summary": "USD weakened after dovish Fed comments.",
            "url": "https://example.com/usd-fed",
        },
    ]


def test_finnhub_enums_and_normalizers():
    assert FinnhubNewsEndpoint.MARKET_NEWS.value == "market_news"
    assert FinnhubNewsEndpoint.COMPANY_NEWS.value == "company_news"

    assert FinnhubNewsCategory.GENERAL.value == "general"
    assert FinnhubNewsCategory.FOREX.value == "forex"
    assert FinnhubNewsCategory.CRYPTO.value == "crypto"
    assert FinnhubNewsCategory.MERGER.value == "merger"

    assert normalize_finnhub_news_endpoint(" MARKET_NEWS ") == FinnhubNewsEndpoint.MARKET_NEWS
    assert normalize_finnhub_news_category(" FOREX ") == FinnhubNewsCategory.FOREX

    with pytest.raises(ValueError):
        normalize_finnhub_news_endpoint("bad")

    with pytest.raises(ValueError):
        normalize_finnhub_news_category("bad")


def test_finnhub_news_query_to_dict_and_builder():
    query = FinnhubNewsQuery(
        endpoint=" company_news ",
        category=" forex ",
        symbol=" aapl ",
        from_date="2026-07-01",
        to_date="2026-07-09",
        min_id=10,
        max_records=5,
        metadata={"source": "test"},
    )

    payload = query.to_dict()
    built = build_finnhub_news_query(category="crypto")

    assert payload["endpoint"] == "company_news"
    assert payload["category"] == "forex"
    assert payload["symbol"] == "AAPL"
    assert payload["from_date"] == "2026-07-01"
    assert payload["to_date"] == "2026-07-09"
    assert payload["min_id"] == 10
    assert payload["max_records"] == 5
    assert isinstance(built, FinnhubNewsQuery)

    with pytest.raises(ValueError):
        FinnhubNewsQuery(endpoint="bad")

    with pytest.raises(ValueError):
        FinnhubNewsQuery(category="bad")

    with pytest.raises(ValueError):
        FinnhubNewsQuery(symbol=123)

    with pytest.raises(ValueError):
        FinnhubNewsQuery(min_id=-1)

    with pytest.raises(ValueError):
        FinnhubNewsQuery(max_records=0)

    with pytest.raises(ValueError):
        FinnhubNewsQuery(metadata=[])


def test_finnhub_query_to_query_params_market_news():
    query = build_finnhub_news_query(
        endpoint="market_news",
        category="forex",
        min_id=5,
    )

    params = finnhub_query_to_query_params(query)

    assert params["category"] == "forex"
    assert params["minId"] == 5

    with pytest.raises(ValueError):
        finnhub_query_to_query_params("bad")


def test_finnhub_query_to_query_params_company_news():
    query = build_finnhub_news_query(
        endpoint="company_news",
        symbol="AAPL",
        from_date="2026-07-01",
        to_date="2026-07-09",
    )

    params = finnhub_query_to_query_params(query)

    assert params["symbol"] == "AAPL"
    assert params["from"] == "2026-07-01"
    assert params["to"] == "2026-07-09"


def test_finnhub_connector_definition():
    market = build_finnhub_connector_definition(endpoint="market_news")
    company = build_finnhub_connector_definition(endpoint="company_news")

    assert isinstance(market, LiveNewsConnectorDefinition)
    assert isinstance(company, LiveNewsConnectorDefinition)

    assert market.to_dict()["connector_id"] == "finnhub"
    assert market.to_dict()["endpoint"]["endpoint"] == "/api/v1/news"
    assert market.to_dict()["api_key_query_param"] == "token"
    assert market.to_dict()["requires_api_key"] is True

    assert company.to_dict()["endpoint"]["endpoint"] == "/api/v1/company-news"

    with pytest.raises(ValueError):
        build_finnhub_connector_definition(endpoint="bad")


def test_finnhub_runtime_and_http_config():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    query = build_finnhub_news_query(
        endpoint="company_news",
        symbol="AAPL",
        from_date="2026-07-01",
        to_date="2026-07-09",
    )
    runtime = build_finnhub_runtime_config(
        query=query,
        credentials=credentials,
    )
    http_config = build_finnhub_http_config(
        query=query,
        credentials=credentials,
    )

    assert isinstance(runtime, LiveNewsConnectorRuntimeConfig)
    assert isinstance(http_config, HttpNewsProviderConfig)
    assert http_config.provider_id == "finnhub"
    assert http_config.base_url == "https://finnhub.io"
    assert http_config.endpoint == "/api/v1/company-news"
    assert http_config.payload_key == "data"
    assert http_config.api_key_query_param == "token"
    assert http_config.default_query_params["symbol"] == "AAPL"

    with pytest.raises(ValueError):
        build_finnhub_runtime_config(query="bad")


def test_finnhub_category_to_topic():
    assert finnhub_category_to_topic("general") == "macro"
    assert finnhub_category_to_topic("forex") == "forex"
    assert finnhub_category_to_topic("crypto") == "crypto"
    assert finnhub_category_to_topic("merger") == "equities"

    with pytest.raises(ValueError):
        finnhub_category_to_topic("bad")


def test_finnhub_raw_row_normalization():
    row = sample_finnhub_payload()[0]
    normalized = finnhub_raw_row_to_normalized_news_row(
        row,
        category="general",
    )

    assert normalized["article_id"] == "101"
    assert normalized["published_at"] == "2026-07-09T12:00:00Z"
    assert normalized["title"] == "Gold rises after inflation data"
    assert normalized["source"] == "Example Finance"
    assert normalized["source_type"] == "news_api"
    assert normalized["url"] == "https://example.com/gold-inflation"
    assert normalized["symbol"] == "XAUUSD"
    assert normalized["topics"] == ["macro"]
    assert normalized["event_type"] == "news"
    assert normalized["provider_id"] == "finnhub"
    assert normalized["metadata"]["image"] == "https://example.com/gold.png"

    with pytest.raises(ValueError):
        finnhub_raw_row_to_normalized_news_row("bad")


def test_normalize_finnhub_payload():
    normalized = normalize_finnhub_payload(sample_finnhub_payload())

    assert "data" in normalized
    assert len(normalized["data"]) == 2
    assert normalized["data"][0]["provider_id"] == "finnhub"

    with pytest.raises(ValueError):
        normalize_finnhub_payload({"missing": []})


def test_load_finnhub_feed_and_provider_result_from_payload_and_fetcher():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    query = build_finnhub_news_query(category="general")

    feed_result = load_finnhub_news_feed_result(
        query=query,
        credentials=credentials,
        payload=sample_finnhub_payload(),
    )
    provider_result = load_finnhub_news_provider_result(
        query=query,
        credentials=credentials,
        payload=sample_finnhub_payload(),
    )
    fetcher_result = load_finnhub_news_provider_result(
        query=query,
        credentials=credentials,
        fetcher=lambda _request: sample_finnhub_payload(),
    )

    assert feed_result.success is True
    assert feed_result.article_count == 2

    assert isinstance(provider_result, NewsProviderResult)
    assert provider_result.success is True
    assert provider_result.record_count == 2
    assert provider_result.records[0].event_id == "101"
    assert provider_result.records[0].source == "Example Finance"

    assert fetcher_result.success is True
    assert fetcher_result.record_count == 2


def test_finnhub_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "FinnhubNewsCategory",
        "FinnhubNewsEndpoint",
        "FinnhubNewsQuery",
        "build_finnhub_connector_definition",
        "build_finnhub_http_config",
        "build_finnhub_news_query",
        "build_finnhub_runtime_config",
        "finnhub_category_to_topic",
        "finnhub_query_to_query_params",
        "finnhub_raw_row_to_normalized_news_row",
        "load_finnhub_news_feed_result",
        "load_finnhub_news_provider_result",
        "normalize_finnhub_news_category",
        "normalize_finnhub_news_endpoint",
        "normalize_finnhub_payload",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name