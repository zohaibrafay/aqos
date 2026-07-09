"""
Unit tests for AQOS NewsAPI / MarketAux style connector.
"""

import pytest

from aqos.news_providers import (
    ApiNewsConnectorKind,
    ApiNewsQuery,
    ApiNewsSortBy,
    HttpNewsProviderConfig,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorRuntimeConfig,
    NewsProviderCredentials,
    NewsProviderResult,
    api_news_query_to_query_params,
    api_news_raw_row_to_normalized_news_row,
    build_api_news_connector_definition,
    build_api_news_http_config,
    build_api_news_query,
    build_api_news_runtime_config,
    build_marketaux_connector_definition,
    build_newsapi_connector_definition,
    load_api_news_feed_result,
    load_api_news_provider_result,
    load_marketaux_news_provider_result,
    load_newsapi_news_provider_result,
    normalize_api_news_connector_kind,
    normalize_api_news_payload,
    normalize_api_news_sort_by,
    validate_api_news_string_list,
)


def sample_newsapi_payload():
    return {
        "articles": [
            {
                "source": {"id": "reuters", "name": "Reuters"},
                "author": "Jane",
                "title": "Gold rises as inflation cools",
                "description": "Gold moved higher after soft inflation data.",
                "url": "https://example.com/gold-inflation",
                "urlToImage": "https://example.com/img.png",
                "publishedAt": "2026-07-09T12:00:00Z",
                "content": "Gold moved higher after inflation cooled.",
            }
        ]
    }


def sample_marketaux_payload():
    return {
        "data": [
            {
                "uuid": "marketaux-1",
                "title": "Dollar falls after Fed speech",
                "description": "USD weakened after dovish Fed comments.",
                "snippet": "USD weakened after dovish Fed comments.",
                "url": "https://example.com/usd-fed",
                "image_url": "https://example.com/usd.png",
                "language": "en",
                "published_at": "2026-07-09T13:00:00Z",
                "source": "Example Finance",
                "entities": [{"symbol": "USD", "name": "US Dollar"}],
                "keywords": ["fed", "usd"],
                "score": 0.8,
            }
        ]
    }


def test_api_news_enums_and_normalizers():
    assert ApiNewsConnectorKind.NEWS_API.value == "news_api"
    assert ApiNewsConnectorKind.MARKETAUX.value == "marketaux"

    assert ApiNewsSortBy.RELEVANCY.value == "relevancy"
    assert ApiNewsSortBy.POPULARITY.value == "popularity"
    assert ApiNewsSortBy.PUBLISHED_AT.value == "publishedAt"

    assert normalize_api_news_connector_kind(" NEWS_API ") == ApiNewsConnectorKind.NEWS_API
    assert normalize_api_news_connector_kind(" MARKETAUX ") == ApiNewsConnectorKind.MARKETAUX
    assert normalize_api_news_sort_by("publishedAt") == ApiNewsSortBy.PUBLISHED_AT

    with pytest.raises(ValueError):
        normalize_api_news_connector_kind("bad")

    with pytest.raises(ValueError):
        normalize_api_news_sort_by("bad")


def test_api_news_query_to_dict_and_builder():
    query = ApiNewsQuery(
        query_terms=[" Gold ", " Inflation "],
        symbol=" xauusd ",
        country=" us ",
        language=" en ",
        category=" equity ",
        from_date="2026-07-01",
        to_date="2026-07-09",
        sort_by="publishedAt",
        page=2,
        page_size=5,
        metadata={"source": "test"},
    )

    payload = query.to_dict()
    built = build_api_news_query(query_terms=["gold"])

    assert query.query_expression == "Gold OR Inflation OR XAUUSD"
    assert payload["query_terms"] == ["gold", "inflation"]
    assert payload["symbol"] == "XAUUSD"
    assert payload["country"] == "us"
    assert payload["language"] == "en"
    assert payload["category"] == "equity"
    assert payload["from_date"] == "2026-07-01"
    assert payload["to_date"] == "2026-07-09"
    assert payload["sort_by"] == "publishedAt"
    assert payload["page"] == 2
    assert payload["page_size"] == 5
    assert isinstance(built, ApiNewsQuery)

    with pytest.raises(ValueError):
        ApiNewsQuery(query_terms="bad")

    with pytest.raises(ValueError):
        ApiNewsQuery(query_terms=[""])

    with pytest.raises(ValueError):
        ApiNewsQuery(sort_by="bad")

    with pytest.raises(ValueError):
        ApiNewsQuery(page=0)

    with pytest.raises(ValueError):
        ApiNewsQuery(page_size=0)

    with pytest.raises(ValueError):
        ApiNewsQuery(metadata=[])


def test_api_news_query_to_query_params_for_newsapi():
    query = build_api_news_query(
        query_terms=["gold", "inflation"],
        language="en",
        from_date="2026-07-01",
        to_date="2026-07-09",
        page=1,
        page_size=3,
    )

    params = api_news_query_to_query_params(
        query,
        connector_kind="news_api",
    )

    assert params["q"] == "gold OR inflation"
    assert params["language"] == "en"
    assert params["from"] == "2026-07-01"
    assert params["to"] == "2026-07-09"
    assert params["sortBy"] == "publishedAt"
    assert params["page"] == 1
    assert params["pageSize"] == 3

    with pytest.raises(ValueError):
        api_news_query_to_query_params("bad", connector_kind="news_api")


def test_api_news_query_to_query_params_for_marketaux():
    query = build_api_news_query(
        query_terms=["fed"],
        symbol="USD",
        country="us",
        category="equity",
        page=1,
        page_size=3,
    )

    params = api_news_query_to_query_params(
        query,
        connector_kind="marketaux",
    )

    assert params["search"] == "fed OR USD"
    assert params["language"] == "en"
    assert params["symbols"] == "USD"
    assert params["countries"] == "us"
    assert params["filter_entities"] == "true"
    assert params["entity_types"] == "equity"
    assert params["page"] == 1
    assert params["limit"] == 3


def test_newsapi_and_marketaux_connector_definitions():
    newsapi = build_newsapi_connector_definition()
    marketaux = build_marketaux_connector_definition()
    generic = build_api_news_connector_definition(connector_kind="news_api")

    assert isinstance(newsapi, LiveNewsConnectorDefinition)
    assert isinstance(marketaux, LiveNewsConnectorDefinition)
    assert isinstance(generic, LiveNewsConnectorDefinition)

    assert newsapi.to_dict()["connector_id"] == "news_api"
    assert newsapi.to_dict()["endpoint"]["payload_key"] == "articles"
    assert newsapi.to_dict()["api_key_query_param"] == "apiKey"
    assert newsapi.to_dict()["requires_api_key"] is True

    assert marketaux.to_dict()["connector_id"] == "marketaux"
    assert marketaux.to_dict()["endpoint"]["payload_key"] == "data"
    assert marketaux.to_dict()["api_key_query_param"] == "api_token"
    assert marketaux.to_dict()["requires_api_key"] is True

    with pytest.raises(ValueError):
        build_api_news_connector_definition(connector_kind="bad")


def test_api_news_runtime_and_http_config():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    query = build_api_news_query(
        query_terms=["gold"],
        page_size=2,
    )
    runtime = build_api_news_runtime_config(
        connector_kind="news_api",
        query=query,
        credentials=credentials,
    )
    http_config = build_api_news_http_config(
        connector_kind="news_api",
        query=query,
        credentials=credentials,
    )

    assert isinstance(runtime, LiveNewsConnectorRuntimeConfig)
    assert isinstance(http_config, HttpNewsProviderConfig)
    assert http_config.provider_id == "news_api"
    assert http_config.base_url == "https://newsapi.org"
    assert http_config.endpoint == "/v2/everything"
    assert http_config.payload_key == "articles"
    assert http_config.api_key_query_param == "apiKey"
    assert http_config.default_query_params["q"] == "gold"

    with pytest.raises(ValueError):
        build_api_news_runtime_config(
            connector_kind="news_api",
            query="bad",
        )


def test_api_news_raw_row_normalization_newsapi():
    row = sample_newsapi_payload()["articles"][0]
    normalized = api_news_raw_row_to_normalized_news_row(
        row,
        connector_kind="news_api",
    )

    assert normalized["article_id"] == "https://example.com/gold-inflation"
    assert normalized["published_at"] == "2026-07-09T12:00:00Z"
    assert normalized["title"] == "Gold rises as inflation cools"
    assert normalized["source"] == "Reuters"
    assert normalized["source_type"] == "news_api"
    assert normalized["url"] == "https://example.com/gold-inflation"
    assert normalized["event_type"] == "news"
    assert normalized["provider_id"] == "news_api"
    assert normalized["metadata"]["author"] == "Jane"

    with pytest.raises(ValueError):
        api_news_raw_row_to_normalized_news_row("bad", connector_kind="news_api")


def test_api_news_raw_row_normalization_marketaux():
    row = sample_marketaux_payload()["data"][0]
    normalized = api_news_raw_row_to_normalized_news_row(
        row,
        connector_kind="marketaux",
    )

    assert normalized["article_id"] == "marketaux-1"
    assert normalized["published_at"] == "2026-07-09T13:00:00Z"
    assert normalized["title"] == "Dollar falls after Fed speech"
    assert normalized["source"] == "Example Finance"
    assert normalized["source_type"] == "news_api"
    assert normalized["url"] == "https://example.com/usd-fed"
    assert normalized["symbol"] == "USD"
    assert normalized["event_type"] == "news"
    assert normalized["provider_id"] == "marketaux"
    assert normalized["metadata"]["image_url"] == "https://example.com/usd.png"


def test_normalize_api_news_payload():
    normalized_newsapi = normalize_api_news_payload(
        sample_newsapi_payload(),
        connector_kind="news_api",
    )
    normalized_marketaux = normalize_api_news_payload(
        sample_marketaux_payload(),
        connector_kind="marketaux",
    )

    assert "articles" in normalized_newsapi
    assert normalized_newsapi["articles"][0]["provider_id"] == "news_api"
    assert "data" in normalized_marketaux
    assert normalized_marketaux["data"][0]["provider_id"] == "marketaux"

    with pytest.raises(ValueError):
        normalize_api_news_payload({"missing": []}, connector_kind="news_api")


def test_load_api_news_provider_results_from_payload_and_fetcher():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    query = build_api_news_query(query_terms=["gold"])

    feed_result = load_api_news_feed_result(
        connector_kind="news_api",
        query=query,
        credentials=credentials,
        payload=sample_newsapi_payload(),
    )
    provider_result = load_api_news_provider_result(
        connector_kind="news_api",
        query=query,
        credentials=credentials,
        payload=sample_newsapi_payload(),
    )
    fetcher_result = load_api_news_provider_result(
        connector_kind="marketaux",
        query=query,
        credentials=credentials,
        fetcher=lambda _request: sample_marketaux_payload(),
    )

    assert feed_result.success is True
    assert feed_result.article_count == 1

    assert isinstance(provider_result, NewsProviderResult)
    assert provider_result.success is True
    assert provider_result.record_count == 1
    assert provider_result.records[0].event_id == "https://example.com/gold-inflation"

    assert fetcher_result.success is True
    assert fetcher_result.record_count == 1
    assert fetcher_result.records[0].event_id == "marketaux-1"


def test_newsapi_and_marketaux_shortcut_loaders():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    newsapi_result = load_newsapi_news_provider_result(
        credentials=credentials,
        payload=sample_newsapi_payload(),
    )
    marketaux_result = load_marketaux_news_provider_result(
        credentials=credentials,
        payload=sample_marketaux_payload(),
    )

    assert newsapi_result.success is True
    assert newsapi_result.record_count == 1
    assert newsapi_result.records[0].source == "Reuters"

    assert marketaux_result.success is True
    assert marketaux_result.record_count == 1
    assert marketaux_result.records[0].source == "Example Finance"


def test_api_news_validators_and_exports_exist():
    assert validate_api_news_string_list(["gold"]) == ["gold"]

    with pytest.raises(ValueError):
        validate_api_news_string_list("bad", "Terms")

    with pytest.raises(ValueError):
        validate_api_news_string_list([""], "Terms")

    import aqos.news_providers as news_providers

    expected_exports = [
        "ApiNewsConnectorKind",
        "ApiNewsQuery",
        "ApiNewsSortBy",
        "api_news_query_to_query_params",
        "api_news_raw_row_to_normalized_news_row",
        "build_api_news_connector_definition",
        "build_api_news_http_config",
        "build_api_news_query",
        "build_api_news_runtime_config",
        "build_marketaux_connector_definition",
        "build_newsapi_connector_definition",
        "load_api_news_feed_result",
        "load_api_news_provider_result",
        "load_marketaux_news_provider_result",
        "load_newsapi_news_provider_result",
        "normalize_api_news_connector_kind",
        "normalize_api_news_payload",
        "normalize_api_news_sort_by",
        "validate_api_news_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name