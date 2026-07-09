"""
Unit tests for AQOS CryptoPanic crypto news connector.
"""

import pytest

from aqos.news_providers import (
    CryptoPanicFilter,
    CryptoPanicNewsQuery,
    CryptoPanicPostKind,
    HttpNewsProviderConfig,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorRuntimeConfig,
    NewsProviderCredentials,
    NewsProviderResult,
    build_cryptopanic_connector_definition,
    build_cryptopanic_http_config,
    build_cryptopanic_news_query,
    build_cryptopanic_runtime_config,
    cryptopanic_query_to_query_params,
    cryptopanic_raw_row_to_normalized_news_row,
    cryptopanic_votes_to_impact,
    cryptopanic_votes_to_sentiment,
    extract_cryptopanic_currency_symbol,
    extract_cryptopanic_source_name,
    load_cryptopanic_news_feed_result,
    load_cryptopanic_news_provider_result,
    normalize_cryptopanic_filter,
    normalize_cryptopanic_payload,
    normalize_cryptopanic_post_kind,
    safe_int,
    validate_cryptopanic_string_list,
)


def sample_cryptopanic_payload():
    return {
        "results": [
            {
                "id": 1001,
                "kind": "news",
                "domain": "example.com",
                "source": {"title": "Example Crypto", "domain": "example.com"},
                "title": "Bitcoin rallies after ETF inflow data",
                "published_at": "2026-07-09T12:00:00Z",
                "slug": "bitcoin-rallies-etf-inflow",
                "url": "https://example.com/btc-etf",
                "currencies": [{"code": "BTC", "title": "Bitcoin"}],
                "votes": {
                    "positive": 20,
                    "negative": 4,
                    "important": 5,
                    "comments": 10,
                },
            },
            {
                "id": 1002,
                "kind": "news",
                "domain": "example.com",
                "source": {"title": "Example Crypto", "domain": "example.com"},
                "title": "Ethereum weakens after security concern",
                "published_at": "2026-07-09T13:00:00Z",
                "slug": "ethereum-security-concern",
                "url": "https://example.com/eth-security",
                "currencies": [{"code": "ETH", "title": "Ethereum"}],
                "votes": {
                    "positive": 2,
                    "negative": 8,
                    "important": 1,
                    "comments": 3,
                },
            },
        ]
    }


def test_cryptopanic_enums_and_normalizers():
    assert CryptoPanicPostKind.NEWS.value == "news"
    assert CryptoPanicPostKind.MEDIA.value == "media"
    assert CryptoPanicPostKind.ALL.value == "all"

    assert CryptoPanicFilter.RISING.value == "rising"
    assert CryptoPanicFilter.HOT.value == "hot"
    assert CryptoPanicFilter.IMPORTANT.value == "important"
    assert CryptoPanicFilter.BULLISH.value == "bullish"
    assert CryptoPanicFilter.BEARISH.value == "bearish"
    assert CryptoPanicFilter.LOL.value == "lol"
    assert CryptoPanicFilter.NONE.value == "none"

    assert normalize_cryptopanic_post_kind(" NEWS ") == CryptoPanicPostKind.NEWS
    assert normalize_cryptopanic_filter(" BULLISH ") == CryptoPanicFilter.BULLISH

    with pytest.raises(ValueError):
        normalize_cryptopanic_post_kind("bad")

    with pytest.raises(ValueError):
        normalize_cryptopanic_filter("bad")


def test_cryptopanic_news_query_to_dict_and_builder():
    query = CryptoPanicNewsQuery(
        currencies=[" btc ", " eth "],
        regions=[" en ", " de "],
        kind=" news ",
        filter=" bullish ",
        public=True,
        page=2,
        metadata={"source": "test"},
    )

    payload = query.to_dict()
    built = build_cryptopanic_news_query(currencies=["BTC"])

    assert payload["currencies"] == ["BTC", "ETH"]
    assert payload["currency_expression"] == "BTC,ETH"
    assert payload["regions"] == ["en", "de"]
    assert payload["region_expression"] == "en,de"
    assert payload["kind"] == "news"
    assert payload["filter"] == "bullish"
    assert payload["public"] is True
    assert payload["page"] == 2
    assert isinstance(built, CryptoPanicNewsQuery)

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(currencies="bad")

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(currencies=[""])

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(regions="bad")

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(kind="bad")

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(filter="bad")

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(public="bad")

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(page=0)

    with pytest.raises(ValueError):
        CryptoPanicNewsQuery(metadata=[])


def test_cryptopanic_query_to_query_params():
    query = build_cryptopanic_news_query(
        currencies=["BTC", "ETH"],
        regions=["en"],
        kind="news",
        filter="hot",
        public=True,
        page=3,
    )

    params = cryptopanic_query_to_query_params(query)

    assert params["public"] == "true"
    assert params["kind"] == "news"
    assert params["currencies"] == "BTC,ETH"
    assert params["regions"] == "en"
    assert params["filter"] == "hot"
    assert params["page"] == 3

    query_without_filter = build_cryptopanic_news_query(currencies=["BTC"])
    params_without_filter = cryptopanic_query_to_query_params(query_without_filter)

    assert "filter" not in params_without_filter

    with pytest.raises(ValueError):
        cryptopanic_query_to_query_params("bad")


def test_cryptopanic_connector_definition():
    definition = build_cryptopanic_connector_definition()

    assert isinstance(definition, LiveNewsConnectorDefinition)
    assert definition.to_dict()["connector_id"] == "cryptopanic"
    assert definition.to_dict()["name"] == "CryptoPanic"
    assert definition.to_dict()["category"] == "crypto_news"
    assert definition.to_dict()["endpoint"]["endpoint"] == "/api/v1/posts/"
    assert definition.to_dict()["endpoint"]["payload_key"] == "results"
    assert definition.to_dict()["api_key_query_param"] == "auth_token"
    assert definition.to_dict()["requires_api_key"] is True


def test_cryptopanic_runtime_and_http_config():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    query = build_cryptopanic_news_query(
        currencies=["BTC"],
        regions=["en"],
        filter="important",
    )
    runtime = build_cryptopanic_runtime_config(
        query=query,
        credentials=credentials,
    )
    http_config = build_cryptopanic_http_config(
        query=query,
        credentials=credentials,
    )

    assert isinstance(runtime, LiveNewsConnectorRuntimeConfig)
    assert isinstance(http_config, HttpNewsProviderConfig)
    assert http_config.provider_id == "cryptopanic"
    assert http_config.base_url == "https://cryptopanic.com"
    assert http_config.endpoint == "/api/v1/posts/"
    assert http_config.payload_key == "results"
    assert http_config.api_key_query_param == "auth_token"
    assert http_config.default_query_params["currencies"] == "BTC"
    assert http_config.default_query_params["regions"] == "en"
    assert http_config.default_query_params["filter"] == "important"

    with pytest.raises(ValueError):
        build_cryptopanic_runtime_config(query="bad")


def test_cryptopanic_mapping_helpers():
    bullish_votes = {"positive": 10, "negative": 2, "important": 2, "comments": 5}
    bearish_votes = {"positive": 1, "negative": 6, "important": 0, "comments": 1}
    neutral_votes = {"positive": 3, "negative": 3}
    empty_votes = {}

    assert safe_int("1,200") == 1200
    assert safe_int("4.0") == 4
    assert safe_int("") == 0
    assert safe_int(None) == 0

    assert cryptopanic_votes_to_sentiment(bullish_votes) == "bullish"
    assert cryptopanic_votes_to_sentiment(bearish_votes) == "bearish"
    assert cryptopanic_votes_to_sentiment(neutral_votes) == "neutral"
    assert cryptopanic_votes_to_sentiment(empty_votes) == "unknown"

    assert cryptopanic_votes_to_impact(bullish_votes) == "high"
    assert cryptopanic_votes_to_impact(bearish_votes) == "medium"
    assert cryptopanic_votes_to_impact({"positive": 1}) == "low"
    assert cryptopanic_votes_to_impact(empty_votes) == "unknown"

    with pytest.raises(ValueError):
        cryptopanic_votes_to_sentiment("bad")

    with pytest.raises(ValueError):
        cryptopanic_votes_to_impact("bad")


def test_cryptopanic_source_and_currency_extractors():
    row = sample_cryptopanic_payload()["results"][0]

    assert extract_cryptopanic_currency_symbol(row) == "BTC"
    assert extract_cryptopanic_source_name(row) == "Example Crypto"

    assert extract_cryptopanic_currency_symbol({"currencies": ["SOL"]}) == "SOL"
    assert extract_cryptopanic_currency_symbol({"symbol": "DOGE"}) == "DOGE"

    assert extract_cryptopanic_source_name({"source": "Manual Source"}) == "Manual Source"
    assert extract_cryptopanic_source_name({}) == "CryptoPanic"


def test_cryptopanic_raw_row_normalization():
    row = sample_cryptopanic_payload()["results"][0]
    normalized = cryptopanic_raw_row_to_normalized_news_row(row)

    assert normalized["article_id"] == "1001"
    assert normalized["published_at"] == "2026-07-09T12:00:00Z"
    assert normalized["title"] == "Bitcoin rallies after ETF inflow data"
    assert normalized["source"] == "Example Crypto"
    assert normalized["source_type"] == "news_api"
    assert normalized["url"] == "https://example.com/btc-etf"
    assert normalized["symbol"] == "BTC"
    assert normalized["topics"] == ["crypto"]
    assert normalized["event_type"] == "news"
    assert normalized["impact"] == "high"
    assert normalized["sentiment"] == "bullish"
    assert normalized["provider_id"] == "cryptopanic"
    assert normalized["metadata"]["votes"]["positive"] == 20

    with pytest.raises(ValueError):
        cryptopanic_raw_row_to_normalized_news_row("bad")


def test_normalize_cryptopanic_payload():
    normalized = normalize_cryptopanic_payload(sample_cryptopanic_payload())

    assert "results" in normalized
    assert len(normalized["results"]) == 2
    assert normalized["results"][0]["provider_id"] == "cryptopanic"

    with pytest.raises(ValueError):
        normalize_cryptopanic_payload({"missing": []})


def test_load_cryptopanic_feed_and_provider_result_from_payload_and_fetcher():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="secret",
    )
    query = build_cryptopanic_news_query(currencies=["BTC"])

    feed_result = load_cryptopanic_news_feed_result(
        query=query,
        credentials=credentials,
        payload=sample_cryptopanic_payload(),
    )
    provider_result = load_cryptopanic_news_provider_result(
        query=query,
        credentials=credentials,
        payload=sample_cryptopanic_payload(),
    )
    fetcher_result = load_cryptopanic_news_provider_result(
        query=query,
        credentials=credentials,
        fetcher=lambda _request: sample_cryptopanic_payload(),
    )

    assert feed_result.success is True
    assert feed_result.article_count == 2

    assert isinstance(provider_result, NewsProviderResult)
    assert provider_result.success is True
    assert provider_result.record_count == 2
    assert provider_result.records[0].event_id == "1001"
    assert provider_result.records[0].source == "Example Crypto"

    assert fetcher_result.success is True
    assert fetcher_result.record_count == 2


def test_cryptopanic_validators_and_exports_exist():
    assert validate_cryptopanic_string_list(["BTC"]) == ["BTC"]

    with pytest.raises(ValueError):
        validate_cryptopanic_string_list("bad", "Currencies")

    with pytest.raises(ValueError):
        validate_cryptopanic_string_list([""], "Currencies")

    import aqos.news_providers as news_providers

    expected_exports = [
        "CryptoPanicFilter",
        "CryptoPanicNewsQuery",
        "CryptoPanicPostKind",
        "build_cryptopanic_connector_definition",
        "build_cryptopanic_http_config",
        "build_cryptopanic_news_query",
        "build_cryptopanic_runtime_config",
        "cryptopanic_query_to_query_params",
        "cryptopanic_raw_row_to_normalized_news_row",
        "cryptopanic_votes_to_impact",
        "cryptopanic_votes_to_sentiment",
        "extract_cryptopanic_currency_symbol",
        "extract_cryptopanic_source_name",
        "load_cryptopanic_news_feed_result",
        "load_cryptopanic_news_provider_result",
        "normalize_cryptopanic_filter",
        "normalize_cryptopanic_payload",
        "normalize_cryptopanic_post_kind",
        "safe_int",
        "validate_cryptopanic_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name