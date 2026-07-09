"""
Unit tests for AQOS Hacker News public JSON connector.
"""

import pytest

from aqos.news_providers import (
    HackerNewsQuery,
    HackerNewsSearchEndpoint,
    HackerNewsTag,
    HttpNewsProviderConfig,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorRuntimeConfig,
    NewsFeedProviderResult,
    NewsProviderResult,
    build_hackernews_connector_definition,
    build_hackernews_http_config,
    build_hackernews_query,
    build_hackernews_runtime_config,
    hackernews_query_to_query_params,
    hackernews_raw_row_to_normalized_news_row,
    load_hackernews_news_feed_result,
    load_hackernews_news_provider_result,
    normalize_hackernews_payload,
    normalize_hackernews_search_endpoint,
    normalize_hackernews_tag,
    validate_hackernews_string_list,
    validate_hackernews_tags,
)


def sample_hackernews_payload():
    return {
        "hits": [
            {
                "objectID": "1001",
                "created_at": "2026-07-09T12:00:00Z",
                "title": "Inflation and markets discussion",
                "url": "https://example.com/inflation-markets",
                "author": "alice",
                "points": 120,
                "num_comments": 33,
                "_tags": ["story"],
            },
            {
                "objectID": "1002",
                "created_at": "2026-07-09T13:00:00Z",
                "story_title": "Gold and rates",
                "story_url": "https://example.com/gold-rates",
                "author": "bob",
                "points": 90,
                "num_comments": 20,
                "_tags": ["story"],
            },
        ]
    }


def test_hackernews_enums_and_normalizers():
    assert HackerNewsSearchEndpoint.SEARCH.value == "search"
    assert HackerNewsSearchEndpoint.SEARCH_BY_DATE.value == "search_by_date"

    assert HackerNewsTag.STORY.value == "story"
    assert HackerNewsTag.COMMENT.value == "comment"
    assert HackerNewsTag.POLL.value == "poll"
    assert HackerNewsTag.JOB.value == "job"

    assert normalize_hackernews_search_endpoint(" SEARCH ") == HackerNewsSearchEndpoint.SEARCH
    assert normalize_hackernews_tag(" STORY ") == HackerNewsTag.STORY

    with pytest.raises(ValueError):
        normalize_hackernews_search_endpoint("bad")

    with pytest.raises(ValueError):
        normalize_hackernews_tag("bad")


def test_hackernews_query_to_dict_and_builder():
    query = HackerNewsQuery(
        query_terms=[" Inflation ", " Markets "],
        tags=[" story "],
        endpoint=" search_by_date ",
        page=2,
        hits_per_page=5,
        metadata={"source": "test"},
    )

    payload = query.to_dict()
    built = build_hackernews_query(query_terms=["gold"])

    assert query.query_expression == "Inflation Markets"
    assert query.tag_expression == "story"
    assert payload["query_terms"] == ["inflation", "markets"]
    assert payload["query_expression"] == "Inflation Markets"
    assert payload["tags"] == ["story"]
    assert payload["endpoint"] == "search_by_date"
    assert payload["page"] == 2
    assert payload["hits_per_page"] == 5
    assert isinstance(built, HackerNewsQuery)

    with pytest.raises(ValueError):
        HackerNewsQuery(query_terms="bad")

    with pytest.raises(ValueError):
        HackerNewsQuery(query_terms=[""])

    with pytest.raises(ValueError):
        HackerNewsQuery(tags="bad")

    with pytest.raises(ValueError):
        HackerNewsQuery(tags=["bad"])

    with pytest.raises(ValueError):
        HackerNewsQuery(endpoint="bad")

    with pytest.raises(ValueError):
        HackerNewsQuery(page=-1)

    with pytest.raises(ValueError):
        HackerNewsQuery(hits_per_page=0)

    with pytest.raises(ValueError):
        HackerNewsQuery(metadata=[])


def test_hackernews_query_to_query_params():
    query = build_hackernews_query(
        query_terms=["inflation", "markets"],
        tags=["story"],
        page=1,
        hits_per_page=3,
    )

    params = hackernews_query_to_query_params(query)

    assert params["query"] == "inflation markets"
    assert params["tags"] == "story"
    assert params["page"] == 1
    assert params["hitsPerPage"] == 3

    with pytest.raises(ValueError):
        hackernews_query_to_query_params("bad")


def test_hackernews_connector_definition():
    definition = build_hackernews_connector_definition(endpoint="search_by_date")
    payload = definition.to_dict()

    assert isinstance(definition, LiveNewsConnectorDefinition)
    assert payload["connector_id"] == "hacker_news"
    assert payload["name"] == "Hacker News Algolia"
    assert payload["category"] == "public_json"
    assert payload["auth_type"] == "none"
    assert payload["status"] == "ready"
    assert payload["endpoint"]["endpoint"] == "/api/v1/search_by_date"
    assert payload["endpoint"]["payload_key"] == "hits"
    assert payload["requires_api_key"] is False

    with pytest.raises(ValueError):
        build_hackernews_connector_definition(endpoint="bad")


def test_hackernews_runtime_and_http_config():
    query = build_hackernews_query(
        query_terms=["inflation"],
        tags=["story"],
        endpoint="search",
        hits_per_page=2,
    )
    runtime = build_hackernews_runtime_config(query=query)
    http_config = build_hackernews_http_config(query=query)

    assert isinstance(runtime, LiveNewsConnectorRuntimeConfig)
    assert isinstance(http_config, HttpNewsProviderConfig)
    assert http_config.provider_id == "hacker_news"
    assert http_config.base_url == "https://hn.algolia.com"
    assert http_config.endpoint == "/api/v1/search"
    assert http_config.payload_key == "hits"
    assert http_config.default_query_params["query"] == "inflation"
    assert http_config.default_query_params["tags"] == "story"
    assert http_config.default_query_params["hitsPerPage"] == 2

    with pytest.raises(ValueError):
        build_hackernews_runtime_config(query="bad")


def test_hackernews_raw_row_normalization():
    row = sample_hackernews_payload()["hits"][0]
    normalized = hackernews_raw_row_to_normalized_news_row(row)

    assert normalized["article_id"] == "1001"
    assert normalized["published_at"] == "2026-07-09T12:00:00Z"
    assert normalized["title"] == "Inflation and markets discussion"
    assert normalized["source"] == "news.ycombinator.com"
    assert normalized["source_type"] == "blog"
    assert normalized["url"] == "https://example.com/inflation-markets"
    assert normalized["event_type"] == "news"
    assert normalized["provider_id"] == "hacker_news"
    assert normalized["metadata"]["hn_author"] == "alice"
    assert normalized["metadata"]["hn_points"] == 120

    with pytest.raises(ValueError):
        hackernews_raw_row_to_normalized_news_row("bad")


def test_normalize_hackernews_payload():
    normalized = normalize_hackernews_payload(sample_hackernews_payload())

    assert "hits" in normalized
    assert len(normalized["hits"]) == 2
    assert normalized["hits"][0]["provider_id"] == "hacker_news"

    with pytest.raises(ValueError):
        normalize_hackernews_payload({"missing": []})


def test_load_hackernews_news_feed_and_provider_result_from_payload():
    query = build_hackernews_query(query_terms=["inflation"])
    feed_result = load_hackernews_news_feed_result(
        query=query,
        payload=sample_hackernews_payload(),
    )
    provider_result = load_hackernews_news_provider_result(
        query=query,
        payload=sample_hackernews_payload(),
    )

    assert isinstance(feed_result, NewsFeedProviderResult)
    assert feed_result.success is True
    assert feed_result.article_count == 2
    assert feed_result.articles[0].article_id == "1001"

    assert isinstance(provider_result, NewsProviderResult)
    assert provider_result.success is True
    assert provider_result.record_count == 2
    assert provider_result.records[0].event_id == "1001"
    assert provider_result.records[0].source == "news.ycombinator.com"


def test_load_hackernews_news_with_fetcher():
    query = build_hackernews_query(query_terms=["inflation"])
    feed_result = load_hackernews_news_feed_result(
        query=query,
        fetcher=lambda _request: sample_hackernews_payload(),
    )
    provider_result = load_hackernews_news_provider_result(
        query=query,
        fetcher=lambda _request: sample_hackernews_payload(),
    )

    assert feed_result.success is True
    assert feed_result.article_count == 2
    assert provider_result.success is True
    assert provider_result.record_count == 2


def test_hackernews_validators_and_exports_exist():
    assert validate_hackernews_string_list(["gold"]) == ["gold"]
    assert validate_hackernews_tags(["story"]) == ["story"]

    with pytest.raises(ValueError):
        validate_hackernews_string_list("bad", "Terms")

    with pytest.raises(ValueError):
        validate_hackernews_string_list([""], "Terms")

    with pytest.raises(ValueError):
        validate_hackernews_tags("bad")

    with pytest.raises(ValueError):
        validate_hackernews_tags(["bad"])

    import aqos.news_providers as news_providers

    expected_exports = [
        "HackerNewsQuery",
        "HackerNewsSearchEndpoint",
        "HackerNewsTag",
        "build_hackernews_connector_definition",
        "build_hackernews_http_config",
        "build_hackernews_query",
        "build_hackernews_runtime_config",
        "hackernews_query_to_query_params",
        "hackernews_raw_row_to_normalized_news_row",
        "load_hackernews_news_feed_result",
        "load_hackernews_news_provider_result",
        "normalize_hackernews_payload",
        "normalize_hackernews_search_endpoint",
        "normalize_hackernews_tag",
        "validate_hackernews_string_list",
        "validate_hackernews_tags",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name