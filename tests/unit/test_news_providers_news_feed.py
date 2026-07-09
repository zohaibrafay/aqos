"""
Unit tests for AQOS news feed provider contracts.
"""

import pytest

from aqos.news_providers import (
    NewsEventRecord,
    NewsFeedArticle,
    NewsFeedProviderResult,
    NewsFeedQuery,
    NewsFeedSourceType,
    NewsFeedTopic,
    NewsProviderConfig,
    NewsProviderResult,
    build_news_feed_article,
    build_news_feed_provider_config,
    build_news_feed_provider_result,
    build_news_feed_query,
    filter_news_feed_articles,
    news_feed_article_to_news_record,
    news_feed_articles_to_news_records,
    news_feed_result_to_news_provider_result,
    normalize_news_feed_source_type,
    normalize_news_feed_topic,
    validate_news_feed_articles,
    validate_news_feed_topics,
)


def sample_articles():
    return [
        build_news_feed_article(
            article_id="article-001",
            published_at="2026-01-01T10:00:00+00:00",
            title="Gold falls after hot US CPI",
            source="Reuters",
            source_type="news_api",
            url="https://example.com/gold-cpi",
            author="Market Desk",
            description="Gold dropped as US inflation came above forecast.",
            content="The US dollar strengthened after the CPI release.",
            language="en",
            country="US",
            symbol="XAUUSD",
            topics=["macro", "commodities"],
            event_type="news",
            impact="high",
            sentiment="bearish",
            relevance_score=0.95,
            provider_id="news-feed",
        ),
        build_news_feed_article(
            article_id="article-002",
            published_at="2026-01-02T12:00:00+00:00",
            title="Bitcoin rallies after ETF inflows",
            source="CoinDesk",
            source_type="news_api",
            description="Crypto markets moved higher.",
            language="en",
            country="US",
            symbol="BTC/USDT",
            topics=["crypto"],
            event_type="crypto",
            impact="medium",
            sentiment="bullish",
            relevance_score=0.9,
            provider_id="news-feed",
        ),
        build_news_feed_article(
            article_id="article-003",
            published_at="2026-01-03T09:00:00+00:00",
            title="ECB comments move euro",
            source="Bloomberg",
            source_type="news_api",
            description="Rates remained in focus.",
            language="en",
            country="DE",
            symbol="EUR/USD",
            topics=["forex", "central_banks"],
            event_type="central_bank",
            impact="medium",
            sentiment="mixed",
            relevance_score=0.8,
            provider_id="news-feed",
        ),
    ]


def test_news_feed_enum_values():
    assert NewsFeedSourceType.NEWS_API.value == "news_api"
    assert NewsFeedSourceType.RSS.value == "rss"
    assert NewsFeedSourceType.SOCIAL.value == "social"
    assert NewsFeedSourceType.BLOG.value == "blog"
    assert NewsFeedSourceType.RESEARCH.value == "research"
    assert NewsFeedSourceType.PRESS_RELEASE.value == "press_release"
    assert NewsFeedSourceType.REGULATORY.value == "regulatory"
    assert NewsFeedSourceType.UNKNOWN.value == "unknown"

    assert NewsFeedTopic.MACRO.value == "macro"
    assert NewsFeedTopic.FOREX.value == "forex"
    assert NewsFeedTopic.CRYPTO.value == "crypto"
    assert NewsFeedTopic.COMMODITIES.value == "commodities"
    assert NewsFeedTopic.EQUITIES.value == "equities"
    assert NewsFeedTopic.RATES.value == "rates"
    assert NewsFeedTopic.CENTRAL_BANKS.value == "central_banks"
    assert NewsFeedTopic.GEOPOLITICS.value == "geopolitics"
    assert NewsFeedTopic.EARNINGS.value == "earnings"
    assert NewsFeedTopic.MARKET_STRUCTURE.value == "market_structure"
    assert NewsFeedTopic.UNKNOWN.value == "unknown"


def test_news_feed_normalizers():
    assert normalize_news_feed_source_type(NewsFeedSourceType.RSS) == NewsFeedSourceType.RSS
    assert normalize_news_feed_source_type(" NEWS_API ") == NewsFeedSourceType.NEWS_API
    assert normalize_news_feed_topic(NewsFeedTopic.MACRO) == NewsFeedTopic.MACRO
    assert normalize_news_feed_topic(" CRYPTO ") == NewsFeedTopic.CRYPTO

    with pytest.raises(ValueError):
        normalize_news_feed_source_type("bad")

    with pytest.raises(ValueError):
        normalize_news_feed_topic("bad")


def test_news_feed_topic_validator():
    assert validate_news_feed_topics(["macro", NewsFeedTopic.CRYPTO]) == [
        "macro",
        NewsFeedTopic.CRYPTO,
    ]

    with pytest.raises(ValueError):
        validate_news_feed_topics("bad")

    with pytest.raises(ValueError):
        validate_news_feed_topics(["bad"])


def test_news_feed_query_to_dict():
    query = NewsFeedQuery(
        symbol=" xauusd ",
        keywords=[" CPI ", " Gold "],
        topics=[" macro ", " commodities "],
        sources=[" Reuters "],
        languages=[" EN "],
        countries=[" us "],
        start_date="2026-01-01",
        end_date="2026-01-31",
        max_results=20,
        metadata={"source": "test"},
    )

    payload = query.to_dict()

    assert query.bounded is True
    assert payload == {
        "symbol": "XAUUSD",
        "keywords": ["cpi", "gold"],
        "topics": ["macro", "commodities"],
        "sources": ["reuters"],
        "languages": ["en"],
        "countries": ["US"],
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "bounded": True,
        "max_results": 20,
        "metadata": {"source": "test"},
    }


def test_news_feed_query_builder_and_rejections():
    query = build_news_feed_query(
        symbol="XAUUSD",
        keywords=["gold"],
        topics=["commodities"],
    )

    assert isinstance(query, NewsFeedQuery)

    with pytest.raises(ValueError):
        NewsFeedQuery(symbol=123)

    with pytest.raises(ValueError):
        NewsFeedQuery(symbol="bad symbol")

    with pytest.raises(ValueError):
        NewsFeedQuery(keywords="bad")

    with pytest.raises(ValueError):
        NewsFeedQuery(topics=["bad"])

    with pytest.raises(ValueError):
        NewsFeedQuery(sources=[""])

    with pytest.raises(ValueError):
        NewsFeedQuery(languages="bad")

    with pytest.raises(ValueError):
        NewsFeedQuery(countries="bad")

    with pytest.raises(ValueError):
        NewsFeedQuery(start_date=123)

    with pytest.raises(ValueError):
        NewsFeedQuery(end_date=123)

    with pytest.raises(ValueError):
        NewsFeedQuery(max_results=0)

    with pytest.raises(ValueError):
        NewsFeedQuery(metadata=[])


def test_news_feed_article_to_dict():
    article = NewsFeedArticle(
        article_id=" article-001 ",
        published_at=" 2026-01-01T10:00:00+00:00 ",
        title=" Gold CPI ",
        source=" Reuters ",
        source_type=" news_api ",
        url=" https://example.com ",
        author=" Desk ",
        description=" Hot CPI pressured gold. ",
        content=" Dollar moved higher. ",
        language=" EN ",
        country=" us ",
        symbol=" xauusd ",
        topics=[" macro ", " commodities "],
        event_type=" news ",
        impact=" high ",
        sentiment=" bearish ",
        relevance_score=0.95,
        provider_id=" provider ",
        raw_payload={"id": 1},
        metadata={"source": "test"},
    )

    payload = article.to_dict()

    assert article.text == "Gold CPI Hot CPI pressured gold. Dollar moved higher."
    assert article.has_content is True
    assert article.directional is True
    assert payload["article_id"] == "article-001"
    assert payload["published_at"] == "2026-01-01T10:00:00+00:00"
    assert payload["source"] == "Reuters"
    assert payload["source_type"] == "news_api"
    assert payload["language"] == "en"
    assert payload["country"] == "US"
    assert payload["symbol"] == "XAUUSD"
    assert payload["topics"] == ["macro", "commodities"]
    assert payload["event_type"] == "news"
    assert payload["impact"] == "high"
    assert payload["sentiment"] == "bearish"


def test_news_feed_article_builder_and_rejections():
    article = build_news_feed_article(
        article_id="article",
        published_at="2026-01-01",
        title="News",
    )

    assert isinstance(article, NewsFeedArticle)

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="", published_at="p", title="Title")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="", title="Title")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", source=123)

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", source_type="bad")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", url=123)

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", symbol="bad symbol")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", topics=["bad"])

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", event_type="bad")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", impact="bad")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", sentiment="bad")

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", relevance_score=2)

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", provider_id=123)

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", raw_payload=[])

    with pytest.raises(ValueError):
        NewsFeedArticle(article_id="id", published_at="p", title="Title", metadata=[])


def test_news_feed_provider_config():
    config = build_news_feed_provider_config(
        provider_id="news-feed",
        name="News Feed",
        base_url="https://example.com",
        status="active",
    )

    assert isinstance(config, NewsProviderConfig)
    assert config.provider_type.value == "news_feed"
    assert config.active is True
    assert config.has_capability("live_news") is True
    assert config.has_capability("sentiment") is True


def test_news_feed_provider_result_to_dict():
    query = build_news_feed_query(symbol="XAUUSD")
    result = NewsFeedProviderResult(
        success=True,
        articles=sample_articles(),
        query=query,
        message=" OK ",
        provider_id=" news-feed ",
        metadata={"source": "test"},
    )

    payload = result.to_dict()

    assert result.failed is False
    assert result.article_count == 3
    assert result.directional_count == 2
    assert payload["success"] is True
    assert payload["article_count"] == 3
    assert payload["directional_count"] == 2
    assert payload["query"]["symbol"] == "XAUUSD"


def test_news_feed_provider_result_builder_and_rejections():
    result = build_news_feed_provider_result(
        success=True,
        articles=sample_articles(),
        provider_id="news-feed",
    )

    assert isinstance(result, NewsFeedProviderResult)

    with pytest.raises(ValueError):
        NewsFeedProviderResult(success="yes")

    with pytest.raises(ValueError):
        NewsFeedProviderResult(success=True, articles="bad")

    with pytest.raises(ValueError):
        NewsFeedProviderResult(success=True, articles=["bad"])

    with pytest.raises(ValueError):
        NewsFeedProviderResult(success=True, query="bad")

    with pytest.raises(ValueError):
        NewsFeedProviderResult(success=True, message=123)

    with pytest.raises(ValueError):
        NewsFeedProviderResult(success=True, provider_id=123)

    with pytest.raises(ValueError):
        NewsFeedProviderResult(success=True, metadata=[])

    assert validate_news_feed_articles(sample_articles()) == sample_articles()


def test_news_feed_article_to_news_record():
    article = sample_articles()[0]
    record = news_feed_article_to_news_record(article)

    assert isinstance(record, NewsEventRecord)
    assert record.event_id == "article-001"
    assert record.event_type.value == "news"
    assert record.symbol == "XAUUSD"
    assert record.impact.value == "high"
    assert record.sentiment.value == "bearish"
    assert record.raw_payload["source_type"] == "news_api"
    assert record.metadata["topics"] == ["macro", "commodities"]

    with pytest.raises(ValueError):
        news_feed_article_to_news_record("bad")


def test_news_feed_articles_to_news_records_and_provider_result():
    articles = sample_articles()
    records = news_feed_articles_to_news_records(articles)
    feed_result = build_news_feed_provider_result(
        success=True,
        articles=articles,
        message="OK",
        provider_id="news-feed",
    )
    news_result = news_feed_result_to_news_provider_result(feed_result)

    assert len(records) == 3
    assert isinstance(news_result, NewsProviderResult)
    assert news_result.success is True
    assert news_result.record_count == 3
    assert news_result.records[0].symbol == "XAUUSD"

    with pytest.raises(ValueError):
        news_feed_articles_to_news_records(["bad"])

    with pytest.raises(ValueError):
        news_feed_result_to_news_provider_result("bad")


def test_filter_news_feed_articles():
    articles = sample_articles()
    query = build_news_feed_query(
        symbol="XAUUSD",
        keywords=["cpi"],
        topics=["commodities"],
        sources=["reuters"],
        languages=["en"],
        countries=["US"],
        max_results=10,
    )

    filtered = filter_news_feed_articles(
        articles,
        query=query,
    )

    assert len(filtered) == 1
    assert filtered[0].article_id == "article-001"

    limited = filter_news_feed_articles(
        articles,
        query=build_news_feed_query(max_results=2),
    )

    assert len(limited) == 2

    with pytest.raises(ValueError):
        filter_news_feed_articles(["bad"], query=query)

    with pytest.raises(ValueError):
        filter_news_feed_articles(articles, query="bad")


def test_news_providers_news_feed_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "NewsFeedArticle",
        "NewsFeedProviderResult",
        "NewsFeedQuery",
        "NewsFeedSourceType",
        "NewsFeedTopic",
        "build_news_feed_article",
        "build_news_feed_provider_config",
        "build_news_feed_provider_result",
        "build_news_feed_query",
        "filter_news_feed_articles",
        "news_feed_article_to_news_record",
        "news_feed_articles_to_news_records",
        "news_feed_result_to_news_provider_result",
        "normalize_news_feed_source_type",
        "normalize_news_feed_topic",
        "validate_news_feed_articles",
        "validate_news_feed_topics",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name