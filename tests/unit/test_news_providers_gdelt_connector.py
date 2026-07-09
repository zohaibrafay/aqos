"""
Unit tests for AQOS GDELT live news connector.
"""

import pytest

from aqos.news_providers import (
    GdeltDocMode,
    GdeltNewsQuery,
    GdeltSortMode,
    HttpNewsProviderConfig,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorRuntimeConfig,
    NewsFeedProviderResult,
    NewsProviderResult,
    build_gdelt_connector_definition,
    build_gdelt_http_config,
    build_gdelt_news_query,
    build_gdelt_runtime_config,
    gdelt_query_to_query_params,
    gdelt_raw_row_to_normalized_news_row,
    load_gdelt_news_feed_result,
    load_gdelt_news_provider_result,
    normalize_gdelt_doc_mode,
    normalize_gdelt_payload,
    normalize_gdelt_sort_mode,
    validate_gdelt_string_list,
)


def sample_gdelt_payload():
    return {
        "articles": [
            {
                "url": "https://example.com/gold-cpi",
                "seendate": "20260709T120000Z",
                "title": "Gold falls after hot CPI",
                "domain": "example.com",
                "sourcecountry": "US",
                "language": "English",
            },
            {
                "url": "https://example.com/fed-gold",
                "seendate": "20260709T130000Z",
                "title": "Fed comments pressure gold",
                "domain": "example.com",
                "sourcecountry": "US",
                "language": "English",
            },
        ]
    }


def test_gdelt_enums_and_normalizers():
    assert GdeltDocMode.ARTLIST.value == "artlist"
    assert GdeltDocMode.TIMELINE_VOL.value == "timelinevol"
    assert GdeltDocMode.TIMELINE_VOL_RAW.value == "timelinevolraw"
    assert GdeltDocMode.TIMELINE_TONE.value == "timelinetone"

    assert GdeltSortMode.HYBRID_RELEVANCE.value == "hybridrel"
    assert GdeltSortMode.DATE_DESC.value == "datedesc"
    assert GdeltSortMode.DATE_ASC.value == "dateasc"

    assert normalize_gdelt_doc_mode(" ARTLIST ") == GdeltDocMode.ARTLIST
    assert normalize_gdelt_sort_mode(" HYBRIDREL ") == GdeltSortMode.HYBRID_RELEVANCE

    with pytest.raises(ValueError):
        normalize_gdelt_doc_mode("bad")

    with pytest.raises(ValueError):
        normalize_gdelt_sort_mode("bad")


def test_gdelt_news_query_to_dict_and_builder():
    query = GdeltNewsQuery(
        query_terms=[" Gold ", " Inflation "],
        exact_phrase="Federal Reserve",
        symbol=" xauusd ",
        source_country=" us ",
        source_language=" en ",
        domain=" Example.com ",
        theme="ECON_STOCKMARKET",
        timespan="1d",
        start_datetime="20260709000000",
        end_datetime="20260709235959",
        mode=" artlist ",
        sort=" hybridrel ",
        max_records=5,
        metadata={"source": "test"},
    )

    payload = query.to_dict()
    built = build_gdelt_news_query(query_terms=["gold"])

    assert query.query_expression == 'Gold OR Inflation "Federal Reserve" XAUUSD'
    assert payload["query_terms"] == ["gold", "inflation"]
    assert payload["source_country"] == "US"
    assert payload["source_language"] == "en"
    assert payload["domain"] == "example.com"
    assert payload["mode"] == "artlist"
    assert payload["sort"] == "hybridrel"
    assert payload["max_records"] == 5
    assert isinstance(built, GdeltNewsQuery)

    with pytest.raises(ValueError):
        GdeltNewsQuery(query_terms="bad")

    with pytest.raises(ValueError):
        GdeltNewsQuery(query_terms=[""])

    with pytest.raises(ValueError):
        GdeltNewsQuery(exact_phrase=123)

    with pytest.raises(ValueError):
        GdeltNewsQuery(mode="bad")

    with pytest.raises(ValueError):
        GdeltNewsQuery(sort="bad")

    with pytest.raises(ValueError):
        GdeltNewsQuery(max_records=0)

    with pytest.raises(ValueError):
        GdeltNewsQuery(metadata=[])


def test_gdelt_query_to_query_params():
    query = build_gdelt_news_query(
        query_terms=["gold", "inflation"],
        source_country="US",
        source_language="en",
        domain="example.com",
        theme="ECON",
        timespan="1d",
        max_records=3,
    )

    params = gdelt_query_to_query_params(query)

    assert params["query"] == "gold OR inflation"
    assert params["mode"] == "artlist"
    assert params["format"] == "json"
    assert params["maxrecords"] == 3
    assert params["sort"] == "hybridrel"
    assert params["sourcecountry"] == "US"
    assert params["sourcelang"] == "en"
    assert params["domain"] == "example.com"
    assert params["theme"] == "ECON"
    assert params["timespan"] == "1d"

    with pytest.raises(ValueError):
        gdelt_query_to_query_params("bad")


def test_gdelt_connector_definition():
    definition = build_gdelt_connector_definition()
    payload = definition.to_dict()

    assert isinstance(definition, LiveNewsConnectorDefinition)
    assert payload["connector_id"] == "gdelt"
    assert payload["name"] == "GDELT DOC 2.0"
    assert payload["category"] == "global_news"
    assert payload["auth_type"] == "none"
    assert payload["status"] == "ready"
    assert payload["endpoint"]["payload_key"] == "articles"
    assert payload["requires_api_key"] is False


def test_gdelt_runtime_and_http_config():
    query = build_gdelt_news_query(
        query_terms=["gold"],
        source_country="US",
        max_records=2,
    )
    runtime = build_gdelt_runtime_config(query=query)
    http_config = build_gdelt_http_config(query=query)

    assert isinstance(runtime, LiveNewsConnectorRuntimeConfig)
    assert isinstance(http_config, HttpNewsProviderConfig)
    assert http_config.provider_id == "gdelt"
    assert http_config.base_url == "https://api.gdeltproject.org"
    assert http_config.endpoint == "/api/v2/doc/doc"
    assert http_config.payload_key == "articles"
    assert http_config.default_query_params["query"] == "gold"
    assert http_config.default_query_params["sourcecountry"] == "US"
    assert http_config.default_query_params["maxrecords"] == 2

    with pytest.raises(ValueError):
        build_gdelt_runtime_config(query="bad")


def test_gdelt_raw_row_normalization():
    row = sample_gdelt_payload()["articles"][0]
    normalized = gdelt_raw_row_to_normalized_news_row(row)

    assert normalized["article_id"] == "https://example.com/gold-cpi"
    assert normalized["published_at"] == "20260709T120000Z"
    assert normalized["title"] == "Gold falls after hot CPI"
    assert normalized["source"] == "example.com"
    assert normalized["source_type"] == "news_api"
    assert normalized["url"] == "https://example.com/gold-cpi"
    assert normalized["country"] == "US"
    assert normalized["event_type"] == "news"
    assert normalized["provider_id"] == "gdelt"

    with pytest.raises(ValueError):
        gdelt_raw_row_to_normalized_news_row("bad")


def test_normalize_gdelt_payload():
    normalized = normalize_gdelt_payload(sample_gdelt_payload())

    assert "articles" in normalized
    assert len(normalized["articles"]) == 2
    assert normalized["articles"][0]["provider_id"] == "gdelt"

    with pytest.raises(ValueError):
        normalize_gdelt_payload({"missing": []})


def test_load_gdelt_news_feed_and_provider_result_from_payload():
    query = build_gdelt_news_query(query_terms=["gold"])
    feed_result = load_gdelt_news_feed_result(
        query=query,
        payload=sample_gdelt_payload(),
    )
    provider_result = load_gdelt_news_provider_result(
        query=query,
        payload=sample_gdelt_payload(),
    )

    assert isinstance(feed_result, NewsFeedProviderResult)
    assert feed_result.success is True
    assert feed_result.article_count == 2
    assert feed_result.articles[0].article_id == "https://example.com/gold-cpi"

    assert isinstance(provider_result, NewsProviderResult)
    assert provider_result.success is True
    assert provider_result.record_count == 2
    assert provider_result.records[0].event_id == "https://example.com/gold-cpi"
    assert provider_result.records[0].source == "example.com"


def test_load_gdelt_news_with_fetcher():
    query = build_gdelt_news_query(query_terms=["gold"])
    feed_result = load_gdelt_news_feed_result(
        query=query,
        fetcher=lambda _request: sample_gdelt_payload(),
    )
    provider_result = load_gdelt_news_provider_result(
        query=query,
        fetcher=lambda _request: sample_gdelt_payload(),
    )

    assert feed_result.success is True
    assert feed_result.article_count == 2
    assert provider_result.success is True
    assert provider_result.record_count == 2


def test_gdelt_validators_and_exports_exist():
    assert validate_gdelt_string_list(["gold"]) == ["gold"]

    with pytest.raises(ValueError):
        validate_gdelt_string_list("bad", "Terms")

    with pytest.raises(ValueError):
        validate_gdelt_string_list([""], "Terms")

    import aqos.news_providers as news_providers

    expected_exports = [
        "GdeltDocMode",
        "GdeltNewsQuery",
        "GdeltSortMode",
        "build_gdelt_connector_definition",
        "build_gdelt_http_config",
        "build_gdelt_news_query",
        "build_gdelt_runtime_config",
        "gdelt_query_to_query_params",
        "gdelt_raw_row_to_normalized_news_row",
        "load_gdelt_news_feed_result",
        "load_gdelt_news_provider_result",
        "normalize_gdelt_doc_mode",
        "normalize_gdelt_payload",
        "normalize_gdelt_sort_mode",
        "validate_gdelt_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name