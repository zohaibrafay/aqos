"""
Unit tests for AQOS local JSON news provider.
"""

import json

import pytest

from aqos.news_providers import (
    LocalJsonNewsProviderConfig,
    NewsEventRecord,
    NewsFeedArticle,
    NewsFeedProviderResult,
    NewsProviderConfig,
    NewsProviderResult,
    build_local_json_news_provider_base_config,
    build_local_json_news_provider_config,
    build_news_feed_query,
    extract_rows_from_local_json_payload,
    load_local_json_news_feed_result,
    load_local_json_news_provider_result,
    local_json_rows_to_news_event_records,
    local_json_rows_to_news_feed_articles,
    raw_json_row_to_news_event_record,
    raw_json_row_to_news_feed_article,
    read_local_json_payload,
)


def sample_rows():
    return [
        {
            "id": "article-001",
            "published_at": "2026-01-01T10:00:00+00:00",
            "title": "Gold falls after hot CPI",
            "source": "Reuters",
            "source_type": "news_api",
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
            "source_type": "news_api",
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


def write_json(tmp_path, payload, filename="news.json"):
    path = tmp_path / filename
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


def test_local_json_config_to_dict_and_builder():
    config = LocalJsonNewsProviderConfig(
        provider_id=" local ",
        name=" Local Provider ",
        file_path=" news.json ",
        symbol=" xauusd ",
        metadata={"source": "test"},
    )

    payload = config.to_dict()
    built = build_local_json_news_provider_config(
        provider_id="local",
        file_path="news.json",
    )

    assert config.has_file_path is True
    assert payload["provider_id"] == "local"
    assert payload["name"] == "Local Provider"
    assert payload["file_path"] == "news.json"
    assert payload["symbol"] == "XAUUSD"
    assert isinstance(built, LocalJsonNewsProviderConfig)

    with pytest.raises(ValueError):
        LocalJsonNewsProviderConfig(provider_id="")

    with pytest.raises(ValueError):
        LocalJsonNewsProviderConfig(provider_id="local", name="")

    with pytest.raises(ValueError):
        LocalJsonNewsProviderConfig(provider_id="local", file_path=123)

    with pytest.raises(ValueError):
        LocalJsonNewsProviderConfig(provider_id="local", symbol=123)

    with pytest.raises(ValueError):
        LocalJsonNewsProviderConfig(provider_id="local", symbol="bad symbol")

    with pytest.raises(ValueError):
        LocalJsonNewsProviderConfig(provider_id="local", metadata=[])


def test_local_json_base_config():
    config = build_local_json_news_provider_base_config(
        provider_id="local",
        name="Local Provider",
        status="active",
    )

    assert isinstance(config, NewsProviderConfig)
    assert config.provider_type.value == "local_json"
    assert config.active is True
    assert config.has_capability("historical_news") is True
    assert config.has_capability("keyword_filtering") is True


def test_read_local_json_payload(tmp_path):
    list_path = write_json(tmp_path, sample_rows(), "news-list.json")
    dict_path = write_json(tmp_path, {"articles": sample_rows()}, "news-dict.json")

    list_payload = read_local_json_payload(list_path)
    dict_payload = read_local_json_payload(dict_path)

    assert isinstance(list_payload, list)
    assert isinstance(dict_payload, dict)

    with pytest.raises(ValueError):
        read_local_json_payload("")

    with pytest.raises(ValueError):
        read_local_json_payload(str(tmp_path / "missing.json"))

    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(ValueError):
        read_local_json_payload(str(directory))

    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{bad", encoding="utf-8")

    with pytest.raises(ValueError):
        read_local_json_payload(str(bad_path))

    invalid_type_path = tmp_path / "invalid.json"
    invalid_type_path.write_text('"hello"', encoding="utf-8")

    with pytest.raises(ValueError):
        read_local_json_payload(str(invalid_type_path))


def test_extract_rows_from_local_json_payload():
    rows = sample_rows()

    assert extract_rows_from_local_json_payload(rows) == rows
    assert extract_rows_from_local_json_payload({"articles": rows}) == rows
    assert extract_rows_from_local_json_payload({"records": rows}) == rows
    assert extract_rows_from_local_json_payload({"custom": rows}, key="custom") == rows

    with pytest.raises(ValueError):
        extract_rows_from_local_json_payload("bad")

    with pytest.raises(ValueError):
        extract_rows_from_local_json_payload({"custom": "bad"}, key="custom")

    with pytest.raises(ValueError):
        extract_rows_from_local_json_payload({"custom": rows}, key="missing")

    with pytest.raises(ValueError):
        extract_rows_from_local_json_payload({"unknown": rows})


def test_raw_json_row_converters():
    row = sample_rows()[0]

    article = raw_json_row_to_news_feed_article(
        row,
        provider_id="local",
    )
    record = raw_json_row_to_news_event_record(
        row,
        provider_id="local",
    )

    assert isinstance(article, NewsFeedArticle)
    assert article.article_id == "article-001"
    assert article.symbol == "XAUUSD"
    assert article.provider_id == "local"

    assert isinstance(record, NewsEventRecord)
    assert record.event_id == "article-001"
    assert record.symbol == "XAUUSD"
    assert record.provider_id == "local"

    with pytest.raises(ValueError):
        raw_json_row_to_news_feed_article("bad")

    with pytest.raises(ValueError):
        raw_json_row_to_news_event_record("bad")


def test_local_json_rows_to_articles_and_records():
    rows = sample_rows()

    articles = local_json_rows_to_news_feed_articles(
        rows,
        provider_id="local",
    )
    records = local_json_rows_to_news_event_records(
        rows,
        provider_id="local",
    )

    assert len(articles) == 2
    assert len(records) == 2
    assert articles[0].article_id == "article-001"
    assert records[0].event_id == "article-001"

    with pytest.raises(ValueError):
        local_json_rows_to_news_feed_articles("bad")

    with pytest.raises(ValueError):
        local_json_rows_to_news_event_records("bad")


def test_load_local_json_news_feed_result(tmp_path):
    path = write_json(tmp_path, {"articles": sample_rows()})
    config = build_local_json_news_provider_config(
        provider_id="local",
        file_path=path,
    )

    result = load_local_json_news_feed_result(config)

    assert isinstance(result, NewsFeedProviderResult)
    assert result.success is True
    assert result.article_count == 2
    assert result.provider_id == "local"

    filtered = load_local_json_news_feed_result(
        config,
        query=build_news_feed_query(symbol="XAUUSD"),
    )

    assert filtered.article_count == 1
    assert filtered.articles[0].symbol == "XAUUSD"

    with pytest.raises(ValueError):
        load_local_json_news_feed_result("bad")


def test_load_local_json_news_provider_result(tmp_path):
    path = write_json(tmp_path, {"articles": sample_rows()})
    config = build_local_json_news_provider_config(
        provider_id="local",
        file_path=path,
    )

    result = load_local_json_news_provider_result(config)

    assert isinstance(result, NewsProviderResult)
    assert result.success is True
    assert result.record_count == 2
    assert result.records[0].event_id == "article-001"

    filtered = load_local_json_news_provider_result(
        config,
        query=build_news_feed_query(symbol="BTC/USDT"),
    )

    assert filtered.success is True
    assert filtered.record_count == 1
    assert filtered.records[0].symbol == "BTC/USDT"

    bad_config = build_local_json_news_provider_config(
        provider_id="local",
        file_path=str(tmp_path / "missing.json"),
    )
    failure = load_local_json_news_provider_result(bad_config)

    assert failure.failed is True
    assert failure.issue_count == 1

    with pytest.raises(ValueError):
        load_local_json_news_provider_result("bad")


def test_news_providers_local_json_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "LocalJsonNewsProviderConfig",
        "build_local_json_news_provider_base_config",
        "build_local_json_news_provider_config",
        "extract_rows_from_local_json_payload",
        "load_local_json_news_feed_result",
        "load_local_json_news_provider_result",
        "local_json_rows_to_news_event_records",
        "local_json_rows_to_news_feed_articles",
        "raw_json_row_to_news_event_record",
        "raw_json_row_to_news_feed_article",
        "read_local_json_payload",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name