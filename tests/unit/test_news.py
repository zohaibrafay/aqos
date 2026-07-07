"""
Unit tests for NewsService.
"""

import pytest

from aqos.services import NewsItem, NewsService


def test_create_news_item():
    service = NewsService()

    item = service.create_item(
        news_id="news-1",
        title="Gold rises after weak dollar data",
        source="local",
        published_at="2026-01-01T10:00:00",
        symbols=["XAUUSD"],
        sentiment="positive",
        impact_score=0.8,
        url="https://example.com/news-1",
        metadata={"category": "macro"},
    )

    assert isinstance(item, NewsItem)
    assert item.news_id == "news-1"
    assert item.title == "Gold rises after weak dollar data"
    assert item.source == "local"
    assert item.symbols == ["XAUUSD"]
    assert item.sentiment == "positive"
    assert item.impact_score == 0.8
    assert item.metadata["category"] == "macro"


def test_add_news_item():
    service = NewsService()

    item = service.create_item(
        news_id="news-1",
        title="Gold rises",
        source="local",
        published_at="2026-01-01T10:00:00",
        symbols=["XAUUSD"],
        sentiment="positive",
        impact_score=0.8,
    )

    added = service.add_item(item)

    assert added.news_id == "news-1"
    assert service.count() == 1


def test_add_news_item_directly():
    service = NewsService()

    item = service.add(
        news_id="news-1",
        title="Gold rises",
        source="local",
        published_at="2026-01-01T10:00:00",
        symbols=["XAUUSD"],
        sentiment="positive",
        impact_score=0.8,
    )

    assert item.news_id == "news-1"
    assert service.count() == 1


def test_add_duplicate_news_item():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold rises",
        source="local",
        published_at="2026-01-01T10:00:00",
    )

    with pytest.raises(ValueError):
        service.add(
            news_id="news-1",
            title="Gold rises again",
            source="local",
            published_at="2026-01-01T11:00:00",
        )


def test_get_news_item():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold rises",
        source="local",
        published_at="2026-01-01T10:00:00",
    )

    item = service.get("news-1")

    assert item is not None
    assert item.news_id == "news-1"


def test_get_missing_news_item():
    service = NewsService()

    item = service.get("missing")

    assert item is None


def test_get_required_missing_news_item():
    service = NewsService()

    with pytest.raises(ValueError):
        service.get_required("missing")


def test_exists_true():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold rises",
        source="local",
        published_at="2026-01-01T10:00:00",
    )

    assert service.exists("news-1") is True


def test_exists_false():
    service = NewsService()

    assert service.exists("news-1") is False


def test_list_news_items_sorted_by_published_time():
    service = NewsService()

    service.add(
        news_id="news-2",
        title="Second news",
        source="local",
        published_at="2026-01-02T10:00:00",
    )
    service.add(
        news_id="news-1",
        title="First news",
        source="local",
        published_at="2026-01-01T10:00:00",
    )

    items = service.list()

    assert items[0].news_id == "news-1"
    assert items[1].news_id == "news-2"


def test_latest_news_items():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="First news",
        source="local",
        published_at="2026-01-01T10:00:00",
    )
    service.add(
        news_id="news-2",
        title="Second news",
        source="local",
        published_at="2026-01-02T10:00:00",
    )

    items = service.latest()

    assert items[0].news_id == "news-2"
    assert items[1].news_id == "news-1"


def test_latest_news_items_with_limit():
    service = NewsService()

    service.add("news-1", "First news", "local", "2026-01-01T10:00:00")
    service.add("news-2", "Second news", "local", "2026-01-02T10:00:00")

    items = service.latest(limit=1)

    assert len(items) == 1
    assert items[0].news_id == "news-2"


def test_filter_by_symbol():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold news",
        source="local",
        published_at="2026-01-01T10:00:00",
        symbols=["XAUUSD"],
    )
    service.add(
        news_id="news-2",
        title="Euro news",
        source="local",
        published_at="2026-01-01T11:00:00",
        symbols=["EURUSD"],
    )

    items = service.filter_by_symbol("XAUUSD")

    assert len(items) == 1
    assert items[0].news_id == "news-1"


def test_filter_by_source():
    service = NewsService()

    service.add("news-1", "Gold news", "local", "2026-01-01T10:00:00")
    service.add("news-2", "Gold news", "external", "2026-01-01T11:00:00")

    items = service.filter_by_source("external")

    assert len(items) == 1
    assert items[0].news_id == "news-2"


def test_filter_by_sentiment():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Positive news",
        source="local",
        published_at="2026-01-01T10:00:00",
        sentiment="positive",
    )
    service.add(
        news_id="news-2",
        title="Negative news",
        source="local",
        published_at="2026-01-01T11:00:00",
        sentiment="negative",
    )

    items = service.filter_by_sentiment("positive")

    assert len(items) == 1
    assert items[0].news_id == "news-1"


def test_high_impact_news():
    service = NewsService()

    service.add(
        news_id="news-low",
        title="Low impact",
        source="local",
        published_at="2026-01-01T10:00:00",
        impact_score=0.3,
    )
    service.add(
        news_id="news-high",
        title="High impact",
        source="local",
        published_at="2026-01-01T11:00:00",
        impact_score=0.9,
    )

    items = service.high_impact(minimum_score=0.7)

    assert len(items) == 1
    assert items[0].news_id == "news-high"


def test_average_impact_score():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="News 1",
        source="local",
        published_at="2026-01-01T10:00:00",
        impact_score=0.5,
    )
    service.add(
        news_id="news-2",
        title="News 2",
        source="local",
        published_at="2026-01-01T11:00:00",
        impact_score=1.0,
    )

    assert service.average_impact_score() == 0.75


def test_average_impact_score_by_symbol():
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold news",
        source="local",
        published_at="2026-01-01T10:00:00",
        symbols=["XAUUSD"],
        impact_score=0.8,
    )
    service.add(
        news_id="news-2",
        title="Euro news",
        source="local",
        published_at="2026-01-01T11:00:00",
        symbols=["EURUSD"],
        impact_score=0.2,
    )

    assert service.average_impact_score("XAUUSD") == 0.8


def test_average_impact_score_without_items():
    service = NewsService()

    assert service.average_impact_score() == 0.0


def test_remove_news_item():
    service = NewsService()

    service.add("news-1", "Gold news", "local", "2026-01-01T10:00:00")

    service.remove("news-1")

    assert service.exists("news-1") is False
    assert service.count() == 0


def test_clear_news_items():
    service = NewsService()

    service.add("news-1", "Gold news", "local", "2026-01-01T10:00:00")
    service.add("news-2", "Euro news", "local", "2026-01-01T11:00:00")

    service.clear()

    assert service.count() == 0


def test_empty_news_id():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add("", "Gold news", "local", "2026-01-01T10:00:00")


def test_empty_title():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add("news-1", "", "local", "2026-01-01T10:00:00")


def test_empty_source():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add("news-1", "Gold news", "", "2026-01-01T10:00:00")


def test_empty_published_at():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add("news-1", "Gold news", "local", "")


def test_empty_symbol():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add(
            news_id="news-1",
            title="Gold news",
            source="local",
            published_at="2026-01-01T10:00:00",
            symbols=[""],
        )


def test_invalid_sentiment():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add(
            news_id="news-1",
            title="Gold news",
            source="local",
            published_at="2026-01-01T10:00:00",
            sentiment="bullish",
        )


def test_invalid_impact_score_low():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add(
            news_id="news-1",
            title="Gold news",
            source="local",
            published_at="2026-01-01T10:00:00",
            impact_score=-0.1,
        )


def test_invalid_impact_score_high():
    service = NewsService()

    with pytest.raises(ValueError):
        service.add(
            news_id="news-1",
            title="Gold news",
            source="local",
            published_at="2026-01-01T10:00:00",
            impact_score=1.1,
        )


def test_invalid_limit():
    service = NewsService()

    service.add("news-1", "Gold news", "local", "2026-01-01T10:00:00")

    with pytest.raises(ValueError):
        service.latest(limit=0)