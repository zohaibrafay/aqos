"""
News service.

Provides a lightweight financial news service for storing,
retrieving, filtering, and scoring market news items.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class NewsItem:
    """
    Represents a financial news item.
    """

    news_id: str
    title: str
    source: str
    published_at: str
    symbols: list[str] = field(default_factory=list)
    sentiment: str = "neutral"
    impact_score: float = 0.0
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class NewsService:
    """
    Service layer for financial news items.
    """

    VALID_SENTIMENTS = {
        "positive",
        "negative",
        "neutral",
    }

    def __init__(self) -> None:
        self._items: dict[str, NewsItem] = {}

    def create_item(
        self,
        news_id: str,
        title: str,
        source: str,
        published_at: str,
        symbols: list[str] | None = None,
        sentiment: str = "neutral",
        impact_score: float = 0.0,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NewsItem:
        """
        Create a validated news item.
        """

        normalized_sentiment = sentiment.lower().strip()

        item = NewsItem(
            news_id=news_id,
            title=title,
            source=source,
            published_at=published_at,
            symbols=symbols or [],
            sentiment=normalized_sentiment,
            impact_score=impact_score,
            url=url,
            metadata=metadata or {},
        )

        self._validate_item(item)

        return item

    def add_item(
        self,
        item: NewsItem,
    ) -> NewsItem:
        """
        Add a news item.
        """

        self._validate_item(item)

        if item.news_id in self._items:
            raise ValueError("News item already exists.")

        self._items[item.news_id] = item

        return item

    def add(
        self,
        news_id: str,
        title: str,
        source: str,
        published_at: str,
        symbols: list[str] | None = None,
        sentiment: str = "neutral",
        impact_score: float = 0.0,
        url: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> NewsItem:
        """
        Create and add a news item.
        """

        item = self.create_item(
            news_id=news_id,
            title=title,
            source=source,
            published_at=published_at,
            symbols=symbols,
            sentiment=sentiment,
            impact_score=impact_score,
            url=url,
            metadata=metadata,
        )

        return self.add_item(item)

    def get(
        self,
        news_id: str,
    ) -> NewsItem | None:
        """
        Get a news item by ID.
        """

        self._validate_news_id(news_id)

        return self._items.get(news_id)

    def get_required(
        self,
        news_id: str,
    ) -> NewsItem:
        """
        Get a news item or raise if it does not exist.
        """

        item = self.get(news_id)

        if item is None:
            raise ValueError("News item does not exist.")

        return item

    def exists(
        self,
        news_id: str,
    ) -> bool:
        """
        Check whether a news item exists.
        """

        self._validate_news_id(news_id)

        return news_id in self._items

    def list(self) -> list[NewsItem]:
        """
        Return all news items sorted by published time.
        """

        return sorted(
            self._items.values(),
            key=lambda item: item.published_at,
        )

    def latest(
        self,
        limit: int | None = None,
    ) -> list[NewsItem]:
        """
        Return latest news items.
        """

        items = sorted(
            self._items.values(),
            key=lambda item: item.published_at,
            reverse=True,
        )

        if limit is None:
            return items

        self._validate_limit(limit)

        return items[:limit]

    def filter_by_symbol(
        self,
        symbol: str,
    ) -> list[NewsItem]:
        """
        Return news items related to a symbol.
        """

        self._validate_symbol(symbol)

        return [
            item
            for item in self.list()
            if symbol in item.symbols
        ]

    def filter_by_source(
        self,
        source: str,
    ) -> list[NewsItem]:
        """
        Return news items from a source.
        """

        self._validate_source(source)

        return [
            item
            for item in self.list()
            if item.source == source
        ]

    def filter_by_sentiment(
        self,
        sentiment: str,
    ) -> list[NewsItem]:
        """
        Return news items by sentiment.
        """

        normalized_sentiment = sentiment.lower().strip()
        self._validate_sentiment(normalized_sentiment)

        return [
            item
            for item in self.list()
            if item.sentiment == normalized_sentiment
        ]

    def high_impact(
        self,
        minimum_score: float = 0.7,
    ) -> list[NewsItem]:
        """
        Return high-impact news items.
        """

        self._validate_impact_score(minimum_score)

        return [
            item
            for item in self.list()
            if item.impact_score >= minimum_score
        ]

    def average_impact_score(
        self,
        symbol: str | None = None,
    ) -> float:
        """
        Return average impact score.
        """

        items = self.list()

        if symbol is not None:
            items = self.filter_by_symbol(symbol)

        if not items:
            return 0.0

        return sum(
            item.impact_score
            for item in items
        ) / len(items)

    def count(self) -> int:
        """
        Return number of news items.
        """

        return len(self._items)

    def remove(
        self,
        news_id: str,
    ) -> None:
        """
        Remove a news item.
        """

        self._validate_news_id(news_id)

        self._items.pop(news_id, None)

    def clear(self) -> None:
        """
        Clear all news items.
        """

        self._items.clear()

    def _validate_item(
        self,
        item: NewsItem,
    ) -> None:
        """
        Validate a news item.
        """

        self._validate_news_id(item.news_id)

        if not item.title:
            raise ValueError("News title cannot be empty.")

        self._validate_source(item.source)

        if not item.published_at:
            raise ValueError("Published time cannot be empty.")

        self._validate_sentiment(item.sentiment)
        self._validate_impact_score(item.impact_score)

        for symbol in item.symbols:
            self._validate_symbol(symbol)

    def _validate_news_id(
        self,
        news_id: str,
    ) -> None:
        """
        Validate news ID.
        """

        if not news_id:
            raise ValueError("News ID cannot be empty.")

    def _validate_source(
        self,
        source: str,
    ) -> None:
        """
        Validate news source.
        """

        if not source:
            raise ValueError("Source cannot be empty.")

    def _validate_symbol(
        self,
        symbol: str,
    ) -> None:
        """
        Validate symbol.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

    def _validate_sentiment(
        self,
        sentiment: str,
    ) -> None:
        """
        Validate sentiment.
        """

        if sentiment not in self.VALID_SENTIMENTS:
            raise ValueError("Sentiment must be positive, negative, or neutral.")

    def _validate_impact_score(
        self,
        impact_score: float,
    ) -> None:
        """
        Validate impact score.
        """

        if impact_score < 0 or impact_score > 1:
            raise ValueError("Impact score must be between 0.0 and 1.0.")

    def _validate_limit(
        self,
        limit: int,
    ) -> None:
        """
        Validate result limit.
        """

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")


__all__ = [
    "NewsItem",
    "NewsService",
]