"""
AQOS news feed provider contracts.

This module defines provider-agnostic news feed article records, query
filters, source normalization, and conversion into AQOS news event records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsEventRecord,
    NewsProviderCapability,
    NewsProviderConfig,
    NewsProviderResult,
    NewsProviderType,
    build_news_event_record,
    build_news_provider_config,
    build_news_provider_result,
    normalize_news_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_score,
    validate_string,
)
from aqos.training_data.events import (
    HistoricalEventImpact,
    HistoricalEventSentiment,
    HistoricalEventType,
    normalize_historical_event_impact,
    normalize_historical_event_sentiment,
    normalize_historical_event_type,
)


class NewsFeedSourceType(str, Enum):
    """Supported news feed source types."""

    NEWS_API = "news_api"
    RSS = "rss"
    SOCIAL = "social"
    BLOG = "blog"
    RESEARCH = "research"
    PRESS_RELEASE = "press_release"
    REGULATORY = "regulatory"
    UNKNOWN = "unknown"


class NewsFeedTopic(str, Enum):
    """Supported news feed topics."""

    MACRO = "macro"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITIES = "commodities"
    EQUITIES = "equities"
    RATES = "rates"
    CENTRAL_BANKS = "central_banks"
    GEOPOLITICS = "geopolitics"
    EARNINGS = "earnings"
    MARKET_STRUCTURE = "market_structure"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class NewsFeedQuery:
    """News feed query."""

    symbol: str = ""
    keywords: list[str] = field(default_factory=list)
    topics: list[NewsFeedTopic | str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    countries: list[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    max_results: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_string_list(self.keywords, "Keywords")
        validate_news_feed_topics(self.topics)
        validate_string_list(self.sources, "Sources")
        validate_string_list(self.languages, "Languages")
        validate_string_list(self.countries, "Countries")
        validate_string(self.start_date, "Start date")
        validate_string(self.end_date, "End date")
        validate_positive_integer(self.max_results, "Max results")
        validate_metadata(self.metadata, "Metadata")

    @property
    def bounded(self) -> bool:
        """Return whether query has start and end date."""
        return bool(self.start_date.strip()) and bool(self.end_date.strip())

    def to_dict(self) -> dict[str, Any]:
        """Convert query to dictionary."""
        return {
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "keywords": [item.strip().lower() for item in self.keywords],
            "topics": [normalize_news_feed_topic(item).value for item in self.topics],
            "sources": [item.strip().lower() for item in self.sources],
            "languages": [item.strip().lower() for item in self.languages],
            "countries": [item.strip().upper() for item in self.countries],
            "start_date": self.start_date.strip(),
            "end_date": self.end_date.strip(),
            "bounded": self.bounded,
            "max_results": self.max_results,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsFeedArticle:
    """Normalized news feed article."""

    article_id: str
    published_at: str
    title: str
    source: str = ""
    source_type: NewsFeedSourceType | str = NewsFeedSourceType.UNKNOWN
    url: str = ""
    author: str = ""
    description: str = ""
    content: str = ""
    language: str = ""
    country: str = ""
    symbol: str = ""
    topics: list[NewsFeedTopic | str] = field(default_factory=list)
    event_type: HistoricalEventType | str = HistoricalEventType.NEWS
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN
    relevance_score: float = 0.0
    provider_id: str = ""
    raw_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.article_id, "Article ID")
        validate_non_empty_string(self.published_at, "Published at")
        validate_non_empty_string(self.title, "Title")
        validate_string(self.source, "Source")
        normalize_news_feed_source_type(self.source_type)
        validate_string(self.url, "URL")
        validate_string(self.author, "Author")
        validate_string(self.description, "Description")
        validate_string(self.content, "Content")
        validate_string(self.language, "Language")
        validate_string(self.country, "Country")
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_news_feed_topics(self.topics)
        normalize_historical_event_type(self.event_type)
        normalize_historical_event_impact(self.impact)
        normalize_historical_event_sentiment(self.sentiment)
        validate_score(self.relevance_score, "Relevance score")
        validate_string(self.provider_id, "Provider ID")
        validate_metadata(self.raw_payload, "Raw payload")
        validate_metadata(self.metadata, "Metadata")

    @property
    def text(self) -> str:
        """Return combined article text."""
        return " ".join(
            part.strip()
            for part in [self.title, self.description, self.content]
            if part.strip()
        )

    @property
    def has_content(self) -> bool:
        """Return whether article has content."""
        return bool(self.content.strip())

    @property
    def directional(self) -> bool:
        """Return whether article sentiment is directional."""
        return normalize_historical_event_sentiment(self.sentiment) in {
            HistoricalEventSentiment.BULLISH,
            HistoricalEventSentiment.BEARISH,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert article to dictionary."""
        return {
            "article_id": self.article_id.strip(),
            "published_at": self.published_at.strip(),
            "title": self.title.strip(),
            "source": self.source.strip(),
            "source_type": normalize_news_feed_source_type(self.source_type).value,
            "url": self.url.strip(),
            "author": self.author.strip(),
            "description": self.description.strip(),
            "content": self.content.strip(),
            "text": self.text,
            "has_content": self.has_content,
            "language": self.language.strip().lower(),
            "country": self.country.strip().upper(),
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "topics": [normalize_news_feed_topic(topic).value for topic in self.topics],
            "event_type": normalize_historical_event_type(self.event_type).value,
            "impact": normalize_historical_event_impact(self.impact).value,
            "sentiment": normalize_historical_event_sentiment(self.sentiment).value,
            "directional": self.directional,
            "relevance_score": float(self.relevance_score),
            "provider_id": self.provider_id.strip(),
            "raw_payload": dict(self.raw_payload),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class NewsFeedProviderResult:
    """News feed provider result."""

    success: bool
    articles: list[NewsFeedArticle] = field(default_factory=list)
    query: NewsFeedQuery | None = None
    message: str = ""
    provider_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_news_feed_articles(self.articles)

        if self.query is not None and not isinstance(self.query, NewsFeedQuery):
            raise ValueError("Query must be NewsFeedQuery.")

        validate_string(self.message, "Message")
        validate_string(self.provider_id, "Provider ID")
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether result failed."""
        return not self.success

    @property
    def article_count(self) -> int:
        """Return article count."""
        return len(self.articles)

    @property
    def directional_count(self) -> int:
        """Return directional article count."""
        return len([article for article in self.articles if article.directional])

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "failed": self.failed,
            "articles": [article.to_dict() for article in self.articles],
            "article_count": self.article_count,
            "directional_count": self.directional_count,
            "query": self.query.to_dict() if self.query is not None else None,
            "message": self.message.strip(),
            "provider_id": self.provider_id.strip(),
            "metadata": dict(self.metadata),
        }


def validate_positive_integer(value: int, field_name: str) -> int:
    """Validate positive integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer.")

    return value


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def normalize_news_feed_source_type(
    value: NewsFeedSourceType | str,
) -> NewsFeedSourceType:
    """Normalize news feed source type."""
    if isinstance(value, NewsFeedSourceType):
        return value

    normalized = validate_non_empty_string(value, "News feed source type").lower()

    try:
        return NewsFeedSourceType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsFeedSourceType)
        raise ValueError(
            f"Invalid news feed source type '{value}'. Valid source types: {valid}.",
        ) from exc


def normalize_news_feed_topic(value: NewsFeedTopic | str) -> NewsFeedTopic:
    """Normalize news feed topic."""
    if isinstance(value, NewsFeedTopic):
        return value

    normalized = validate_non_empty_string(value, "News feed topic").lower()

    try:
        return NewsFeedTopic(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in NewsFeedTopic)
        raise ValueError(
            f"Invalid news feed topic '{value}'. Valid topics: {valid}.",
        ) from exc


def validate_news_feed_topics(
    topics: list[NewsFeedTopic | str],
) -> list[NewsFeedTopic | str]:
    """Validate news feed topics."""
    if not isinstance(topics, list):
        raise ValueError("Topics must be a list.")

    for topic in topics:
        normalize_news_feed_topic(topic)

    return topics


def validate_news_feed_articles(
    articles: list[NewsFeedArticle],
) -> list[NewsFeedArticle]:
    """Validate news feed articles."""
    if not isinstance(articles, list):
        raise ValueError("Articles must be a list.")

    for article in articles:
        if not isinstance(article, NewsFeedArticle):
            raise ValueError("Articles must contain NewsFeedArticle objects.")

    return articles


def build_news_feed_query(
    *,
    symbol: str = "",
    keywords: list[str] | None = None,
    topics: list[NewsFeedTopic | str] | None = None,
    sources: list[str] | None = None,
    languages: list[str] | None = None,
    countries: list[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    max_results: int = 100,
    metadata: dict[str, Any] | None = None,
) -> NewsFeedQuery:
    """Build news feed query."""
    return NewsFeedQuery(
        symbol=symbol,
        keywords=keywords or [],
        topics=topics or [],
        sources=sources or [],
        languages=languages or [],
        countries=countries or [],
        start_date=start_date,
        end_date=end_date,
        max_results=max_results,
        metadata=metadata or {},
    )


def build_news_feed_article(
    *,
    article_id: str,
    published_at: str,
    title: str,
    source: str = "",
    source_type: NewsFeedSourceType | str = NewsFeedSourceType.UNKNOWN,
    url: str = "",
    author: str = "",
    description: str = "",
    content: str = "",
    language: str = "",
    country: str = "",
    symbol: str = "",
    topics: list[NewsFeedTopic | str] | None = None,
    event_type: HistoricalEventType | str = HistoricalEventType.NEWS,
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN,
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN,
    relevance_score: float = 0.0,
    provider_id: str = "",
    raw_payload: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> NewsFeedArticle:
    """Build news feed article."""
    return NewsFeedArticle(
        article_id=article_id,
        published_at=published_at,
        title=title,
        source=source,
        source_type=source_type,
        url=url,
        author=author,
        description=description,
        content=content,
        language=language,
        country=country,
        symbol=symbol,
        topics=topics or [],
        event_type=event_type,
        impact=impact,
        sentiment=sentiment,
        relevance_score=relevance_score,
        provider_id=provider_id,
        raw_payload=raw_payload or {},
        metadata=metadata or {},
    )


def build_news_feed_provider_config(
    *,
    provider_id: str,
    name: str,
    provider_type: NewsProviderType | str = NewsProviderType.NEWS_FEED,
    base_url: str = "",
    status: str = "inactive",
    metadata: dict[str, Any] | None = None,
) -> NewsProviderConfig:
    """Build news feed provider config."""
    return build_news_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        status=status,
        capabilities=[
            NewsProviderCapability.HISTORICAL_NEWS,
            NewsProviderCapability.LIVE_NEWS,
            NewsProviderCapability.KEYWORD_FILTERING,
            NewsProviderCapability.SYMBOL_MAPPING,
            NewsProviderCapability.SENTIMENT,
            NewsProviderCapability.IMPACT_CLASSIFICATION,
        ],
        metadata=metadata or {},
    )


def build_news_feed_provider_result(
    *,
    success: bool,
    articles: list[NewsFeedArticle] | None = None,
    query: NewsFeedQuery | None = None,
    message: str = "",
    provider_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> NewsFeedProviderResult:
    """Build news feed provider result."""
    return NewsFeedProviderResult(
        success=success,
        articles=articles or [],
        query=query,
        message=message,
        provider_id=provider_id,
        metadata=metadata or {},
    )


def news_feed_article_to_news_record(article: NewsFeedArticle) -> NewsEventRecord:
    """Convert news feed article to generic news event record."""
    if not isinstance(article, NewsFeedArticle):
        raise ValueError("Article must be NewsFeedArticle.")

    return build_news_event_record(
        event_id=article.article_id,
        timestamp=article.published_at,
        title=article.title,
        event_type=normalize_historical_event_type(article.event_type),
        symbol=article.symbol,
        impact=normalize_historical_event_impact(article.impact),
        sentiment=normalize_historical_event_sentiment(article.sentiment),
        source=article.source,
        provider_id=article.provider_id,
        url=article.url,
        description=article.description or article.content,
        country=article.country,
        relevance_score=article.relevance_score,
        raw_payload=article.to_dict(),
        metadata={
            "source_type": normalize_news_feed_source_type(article.source_type).value,
            "topics": [normalize_news_feed_topic(topic).value for topic in article.topics],
            "author": article.author,
            "language": article.language,
        },
    )


def news_feed_articles_to_news_records(
    articles: list[NewsFeedArticle],
) -> list[NewsEventRecord]:
    """Convert news feed articles to news records."""
    validate_news_feed_articles(articles)

    return [news_feed_article_to_news_record(article) for article in articles]


def news_feed_result_to_news_provider_result(
    result: NewsFeedProviderResult,
) -> NewsProviderResult:
    """Convert news feed result to generic news provider result."""
    if not isinstance(result, NewsFeedProviderResult):
        raise ValueError("Result must be NewsFeedProviderResult.")

    return build_news_provider_result(
        success=result.success,
        records=news_feed_articles_to_news_records(result.articles),
        message=result.message,
        provider_id=result.provider_id,
        metadata={
            **result.metadata,
            "source_result_type": "news_feed",
            "article_count": result.article_count,
        },
    )


def filter_news_feed_articles(
    articles: list[NewsFeedArticle],
    *,
    query: NewsFeedQuery,
) -> list[NewsFeedArticle]:
    """Filter news feed articles using query."""
    validate_news_feed_articles(articles)

    if not isinstance(query, NewsFeedQuery):
        raise ValueError("Query must be NewsFeedQuery.")

    query_payload = query.to_dict()
    symbol = query_payload["symbol"]
    keywords = set(query_payload["keywords"])
    topics = set(query_payload["topics"])
    sources = set(query_payload["sources"])
    languages = set(query_payload["languages"])
    countries = set(query_payload["countries"])

    filtered: list[NewsFeedArticle] = []

    for article in articles:
        article_payload = article.to_dict()

        if symbol and article_payload["symbol"] != symbol:
            continue

        if topics and not topics.intersection(set(article_payload["topics"])):
            continue

        if sources and article_payload["source"].lower() not in sources:
            continue

        if languages and article_payload["language"] not in languages:
            continue

        if countries and article_payload["country"] not in countries:
            continue

        if keywords:
            article_text = article_payload["text"].lower()

            if not any(keyword in article_text for keyword in keywords):
                continue

        filtered.append(article)

        if len(filtered) >= query.max_results:
            break

    return filtered