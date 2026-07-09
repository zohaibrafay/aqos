"""
AQOS sentiment classification contracts.

This module defines sentiment requests, classification results, scoring helpers,
and conversion utilities for news and macro records.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.news_providers.base import (
    NewsEventRecord,
    NewsProviderCapability,
    NewsProviderConfig,
    NewsProviderType,
    build_news_provider_config,
    normalize_news_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_score,
    validate_string,
)
from aqos.news_providers.news_feed import NewsFeedArticle
from aqos.training_data.events import (
    HistoricalEventImpact,
    HistoricalEventSentiment,
    normalize_historical_event_impact,
    normalize_historical_event_sentiment,
)


class SentimentModelType(str, Enum):
    """Supported sentiment model types."""

    RULE_BASED = "rule_based"
    LLM = "llm"
    TRANSFORMER = "transformer"
    PROVIDER_API = "provider_api"
    HYBRID = "hybrid"
    UNKNOWN = "unknown"


class SentimentConfidenceLevel(str, Enum):
    """Supported sentiment confidence levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SentimentKeywordLexicon:
    """Keyword lexicon for simple sentiment classification."""

    bullish_keywords: list[str] = field(default_factory=list)
    bearish_keywords: list[str] = field(default_factory=list)
    neutral_keywords: list[str] = field(default_factory=list)
    high_impact_keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_string_list(self.bullish_keywords, "Bullish keywords")
        validate_string_list(self.bearish_keywords, "Bearish keywords")
        validate_string_list(self.neutral_keywords, "Neutral keywords")
        validate_string_list(self.high_impact_keywords, "High impact keywords")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert lexicon to dictionary."""
        return {
            "bullish_keywords": [item.strip().lower() for item in self.bullish_keywords],
            "bearish_keywords": [item.strip().lower() for item in self.bearish_keywords],
            "neutral_keywords": [item.strip().lower() for item in self.neutral_keywords],
            "high_impact_keywords": [item.strip().lower() for item in self.high_impact_keywords],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SentimentClassificationRequest:
    """Sentiment classification request."""

    request_id: str
    text: str
    symbol: str = ""
    source: str = ""
    provider_id: str = ""
    model_type: SentimentModelType | str = SentimentModelType.RULE_BASED
    context: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.request_id, "Request ID")
        validate_non_empty_string(self.text, "Text")
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_news_symbol(self.symbol)

        validate_string(self.source, "Source")
        validate_string(self.provider_id, "Provider ID")
        normalize_sentiment_model_type(self.model_type)
        validate_metadata(self.context, "Context")
        validate_metadata(self.metadata, "Metadata")

    @property
    def word_count(self) -> int:
        """Return word count."""
        return len([word for word in self.text.split() if word.strip()])

    def to_dict(self) -> dict[str, Any]:
        """Convert request to dictionary."""
        return {
            "request_id": self.request_id.strip(),
            "text": self.text.strip(),
            "symbol": normalize_news_symbol(self.symbol) if self.symbol.strip() else "",
            "source": self.source.strip(),
            "provider_id": self.provider_id.strip(),
            "model_type": normalize_sentiment_model_type(self.model_type).value,
            "word_count": self.word_count,
            "context": dict(self.context),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SentimentClassificationResult:
    """Sentiment classification result."""

    request_id: str
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN
    confidence: float = 0.0
    confidence_level: SentimentConfidenceLevel | str = SentimentConfidenceLevel.UNKNOWN
    bullish_score: float = 0.0
    bearish_score: float = 0.0
    neutral_score: float = 0.0
    summary: str = ""
    rationale: str = ""
    model_type: SentimentModelType | str = SentimentModelType.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.request_id, "Request ID")
        normalize_historical_event_sentiment(self.sentiment)
        normalize_historical_event_impact(self.impact)
        validate_score(self.confidence, "Confidence")
        normalize_sentiment_confidence_level(self.confidence_level)
        validate_score(self.bullish_score, "Bullish score")
        validate_score(self.bearish_score, "Bearish score")
        validate_score(self.neutral_score, "Neutral score")
        validate_string(self.summary, "Summary")
        validate_string(self.rationale, "Rationale")
        normalize_sentiment_model_type(self.model_type)
        validate_metadata(self.metadata, "Metadata")

    @property
    def directional(self) -> bool:
        """Return whether sentiment is directional."""
        return normalize_historical_event_sentiment(self.sentiment) in {
            HistoricalEventSentiment.BULLISH,
            HistoricalEventSentiment.BEARISH,
        }

    @property
    def high_confidence(self) -> bool:
        """Return whether result is high confidence."""
        return normalize_sentiment_confidence_level(self.confidence_level) == SentimentConfidenceLevel.HIGH

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "request_id": self.request_id.strip(),
            "sentiment": normalize_historical_event_sentiment(self.sentiment).value,
            "impact": normalize_historical_event_impact(self.impact).value,
            "confidence": float(self.confidence),
            "confidence_level": normalize_sentiment_confidence_level(self.confidence_level).value,
            "bullish_score": float(self.bullish_score),
            "bearish_score": float(self.bearish_score),
            "neutral_score": float(self.neutral_score),
            "summary": self.summary.strip(),
            "rationale": self.rationale.strip(),
            "model_type": normalize_sentiment_model_type(self.model_type).value,
            "directional": self.directional,
            "high_confidence": self.high_confidence,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SentimentProviderResult:
    """Sentiment provider result."""

    success: bool
    results: list[SentimentClassificationResult] = field(default_factory=list)
    message: str = ""
    provider_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_sentiment_classification_results(self.results)
        validate_string(self.message, "Message")
        validate_string(self.provider_id, "Provider ID")
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether result failed."""
        return not self.success

    @property
    def result_count(self) -> int:
        """Return result count."""
        return len(self.results)

    @property
    def directional_count(self) -> int:
        """Return directional result count."""
        return len([result for result in self.results if result.directional])

    @property
    def high_confidence_count(self) -> int:
        """Return high-confidence result count."""
        return len([result for result in self.results if result.high_confidence])

    def to_dict(self) -> dict[str, Any]:
        """Convert provider result to dictionary."""
        return {
            "success": self.success,
            "failed": self.failed,
            "results": [result.to_dict() for result in self.results],
            "result_count": self.result_count,
            "directional_count": self.directional_count,
            "high_confidence_count": self.high_confidence_count,
            "message": self.message.strip(),
            "provider_id": self.provider_id.strip(),
            "metadata": dict(self.metadata),
        }


def normalize_sentiment_model_type(value: SentimentModelType | str) -> SentimentModelType:
    """Normalize sentiment model type."""
    if isinstance(value, SentimentModelType):
        return value

    normalized = validate_non_empty_string(value, "Sentiment model type").lower()

    try:
        return SentimentModelType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SentimentModelType)
        raise ValueError(
            f"Invalid sentiment model type '{value}'. Valid model types: {valid}.",
        ) from exc


def normalize_sentiment_confidence_level(
    value: SentimentConfidenceLevel | str,
) -> SentimentConfidenceLevel:
    """Normalize sentiment confidence level."""
    if isinstance(value, SentimentConfidenceLevel):
        return value

    normalized = validate_non_empty_string(value, "Sentiment confidence level").lower()

    try:
        return SentimentConfidenceLevel(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SentimentConfidenceLevel)
        raise ValueError(
            f"Invalid sentiment confidence level '{value}'. Valid levels: {valid}.",
        ) from exc


def validate_string_list(values: list[str], field_name: str) -> list[str]:
    """Validate list of strings."""
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")

    for value in values:
        validate_non_empty_string(value, field_name)

    return values


def validate_sentiment_classification_requests(
    requests: list[SentimentClassificationRequest],
) -> list[SentimentClassificationRequest]:
    """Validate sentiment requests."""
    if not isinstance(requests, list):
        raise ValueError("Requests must be a list.")

    for request in requests:
        if not isinstance(request, SentimentClassificationRequest):
            raise ValueError("Requests must contain SentimentClassificationRequest objects.")

    return requests


def validate_sentiment_classification_results(
    results: list[SentimentClassificationResult],
) -> list[SentimentClassificationResult]:
    """Validate sentiment results."""
    if not isinstance(results, list):
        raise ValueError("Results must be a list.")

    for result in results:
        if not isinstance(result, SentimentClassificationResult):
            raise ValueError("Results must contain SentimentClassificationResult objects.")

    return results


def build_sentiment_keyword_lexicon(
    *,
    bullish_keywords: list[str] | None = None,
    bearish_keywords: list[str] | None = None,
    neutral_keywords: list[str] | None = None,
    high_impact_keywords: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> SentimentKeywordLexicon:
    """Build sentiment keyword lexicon."""
    return SentimentKeywordLexicon(
        bullish_keywords=bullish_keywords or [
            "rally",
            "surge",
            "gain",
            "bullish",
            "beat",
            "strong",
            "growth",
            "inflow",
        ],
        bearish_keywords=bearish_keywords or [
            "fall",
            "drop",
            "decline",
            "bearish",
            "miss",
            "weak",
            "risk-off",
            "selloff",
        ],
        neutral_keywords=neutral_keywords or [
            "unchanged",
            "flat",
            "mixed",
            "stable",
        ],
        high_impact_keywords=high_impact_keywords or [
            "cpi",
            "fomc",
            "rate decision",
            "nonfarm",
            "nfp",
            "war",
            "crisis",
        ],
        metadata=metadata or {},
    )


def build_sentiment_classification_request(
    *,
    request_id: str,
    text: str,
    symbol: str = "",
    source: str = "",
    provider_id: str = "",
    model_type: SentimentModelType | str = SentimentModelType.RULE_BASED,
    context: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> SentimentClassificationRequest:
    """Build sentiment classification request."""
    return SentimentClassificationRequest(
        request_id=request_id,
        text=text,
        symbol=symbol,
        source=source,
        provider_id=provider_id,
        model_type=model_type,
        context=context or {},
        metadata=metadata or {},
    )


def build_sentiment_classification_result(
    *,
    request_id: str,
    sentiment: HistoricalEventSentiment | str = HistoricalEventSentiment.UNKNOWN,
    impact: HistoricalEventImpact | str = HistoricalEventImpact.UNKNOWN,
    confidence: float = 0.0,
    confidence_level: SentimentConfidenceLevel | str = SentimentConfidenceLevel.UNKNOWN,
    bullish_score: float = 0.0,
    bearish_score: float = 0.0,
    neutral_score: float = 0.0,
    summary: str = "",
    rationale: str = "",
    model_type: SentimentModelType | str = SentimentModelType.UNKNOWN,
    metadata: dict[str, Any] | None = None,
) -> SentimentClassificationResult:
    """Build sentiment classification result."""
    return SentimentClassificationResult(
        request_id=request_id,
        sentiment=sentiment,
        impact=impact,
        confidence=confidence,
        confidence_level=confidence_level,
        bullish_score=bullish_score,
        bearish_score=bearish_score,
        neutral_score=neutral_score,
        summary=summary,
        rationale=rationale,
        model_type=model_type,
        metadata=metadata or {},
    )


def build_sentiment_provider_config(
    *,
    provider_id: str,
    name: str,
    provider_type: NewsProviderType | str = NewsProviderType.SENTIMENT,
    base_url: str = "",
    status: str = "inactive",
    metadata: dict[str, Any] | None = None,
) -> NewsProviderConfig:
    """Build sentiment provider config."""
    return build_news_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        status=status,
        capabilities=[
            NewsProviderCapability.SENTIMENT,
            NewsProviderCapability.IMPACT_CLASSIFICATION,
            NewsProviderCapability.SYMBOL_MAPPING,
        ],
        metadata=metadata or {},
    )


def build_sentiment_provider_result(
    *,
    success: bool,
    results: list[SentimentClassificationResult] | None = None,
    message: str = "",
    provider_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> SentimentProviderResult:
    """Build sentiment provider result."""
    return SentimentProviderResult(
        success=success,
        results=results or [],
        message=message,
        provider_id=provider_id,
        metadata=metadata or {},
    )


def confidence_level_from_score(score: float) -> SentimentConfidenceLevel:
    """Infer confidence level from score."""
    validate_score(score, "Confidence score")

    if score >= 0.75:
        return SentimentConfidenceLevel.HIGH

    if score >= 0.45:
        return SentimentConfidenceLevel.MEDIUM

    return SentimentConfidenceLevel.LOW


def dominant_sentiment_from_scores(
    *,
    bullish_score: float,
    bearish_score: float,
    neutral_score: float,
    margin: float = 0.05,
) -> HistoricalEventSentiment:
    """Infer dominant sentiment from score distribution."""
    validate_score(bullish_score, "Bullish score")
    validate_score(bearish_score, "Bearish score")
    validate_score(neutral_score, "Neutral score")
    validate_score(margin, "Margin")

    scores = {
        HistoricalEventSentiment.BULLISH: bullish_score,
        HistoricalEventSentiment.BEARISH: bearish_score,
        HistoricalEventSentiment.NEUTRAL: neutral_score,
    }
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)

    if ordered[0][1] - ordered[1][1] < margin:
        return HistoricalEventSentiment.MIXED

    return ordered[0][0]


def classify_text_with_keyword_lexicon(
    request: SentimentClassificationRequest,
    *,
    lexicon: SentimentKeywordLexicon | None = None,
) -> SentimentClassificationResult:
    """Classify text with simple keyword lexicon."""
    if not isinstance(request, SentimentClassificationRequest):
        raise ValueError("Request must be SentimentClassificationRequest.")

    lexicon = lexicon or build_sentiment_keyword_lexicon()

    if not isinstance(lexicon, SentimentKeywordLexicon):
        raise ValueError("Lexicon must be SentimentKeywordLexicon.")

    payload = lexicon.to_dict()
    text = request.text.lower()

    bullish_hits = count_keyword_hits(text, payload["bullish_keywords"])
    bearish_hits = count_keyword_hits(text, payload["bearish_keywords"])
    neutral_hits = count_keyword_hits(text, payload["neutral_keywords"])
    high_impact_hits = count_keyword_hits(text, payload["high_impact_keywords"])

    total_hits = bullish_hits + bearish_hits + neutral_hits

    if total_hits == 0:
        bullish_score = 0.0
        bearish_score = 0.0
        neutral_score = 1.0
    else:
        bullish_score = round(bullish_hits / total_hits, 10)
        bearish_score = round(bearish_hits / total_hits, 10)
        neutral_score = round(neutral_hits / total_hits, 10)

    sentiment = dominant_sentiment_from_scores(
        bullish_score=bullish_score,
        bearish_score=bearish_score,
        neutral_score=neutral_score,
    )
    confidence = max(bullish_score, bearish_score, neutral_score)
    confidence_level = confidence_level_from_score(confidence)
    impact = HistoricalEventImpact.HIGH if high_impact_hits > 0 else HistoricalEventImpact.UNKNOWN

    return build_sentiment_classification_result(
        request_id=request.request_id,
        sentiment=sentiment,
        impact=impact,
        confidence=confidence,
        confidence_level=confidence_level,
        bullish_score=bullish_score,
        bearish_score=bearish_score,
        neutral_score=neutral_score,
        summary=f"Keyword sentiment classified as {sentiment.value}.",
        rationale=(
            f"bullish_hits={bullish_hits}; bearish_hits={bearish_hits}; "
            f"neutral_hits={neutral_hits}; high_impact_hits={high_impact_hits}"
        ),
        model_type=SentimentModelType.RULE_BASED,
        metadata={
            "symbol": request.symbol,
            "source": request.source,
        },
    )


def count_keyword_hits(text: str, keywords: list[str]) -> int:
    """Count keyword hits in text."""
    validate_non_empty_string(text, "Text")
    validate_string_list(keywords, "Keywords")

    normalized_text = text.lower()

    return sum(1 for keyword in keywords if keyword.strip().lower() in normalized_text)


def news_event_record_to_sentiment_request(
    record: NewsEventRecord,
    *,
    request_id: str = "",
) -> SentimentClassificationRequest:
    """Convert news event record to sentiment request."""
    if not isinstance(record, NewsEventRecord):
        raise ValueError("Record must be NewsEventRecord.")

    resolved_request_id = request_id or f"{record.event_id}-sentiment"

    text = " ".join(
        part.strip()
        for part in [record.title, record.description]
        if part.strip()
    )

    return build_sentiment_classification_request(
        request_id=resolved_request_id,
        text=text,
        symbol=record.symbol,
        source=record.source,
        provider_id=record.provider_id,
        context=record.to_dict(),
    )


def news_feed_article_to_sentiment_request(
    article: NewsFeedArticle,
    *,
    request_id: str = "",
) -> SentimentClassificationRequest:
    """Convert news feed article to sentiment request."""
    if not isinstance(article, NewsFeedArticle):
        raise ValueError("Article must be NewsFeedArticle.")

    return build_sentiment_classification_request(
        request_id=request_id or f"{article.article_id}-sentiment",
        text=article.text,
        symbol=article.symbol,
        source=article.source,
        provider_id=article.provider_id,
        context=article.to_dict(),
    )


def apply_sentiment_result_to_news_record(
    record: NewsEventRecord,
    result: SentimentClassificationResult,
) -> NewsEventRecord:
    """Apply sentiment result to news event record."""
    if not isinstance(record, NewsEventRecord):
        raise ValueError("Record must be NewsEventRecord.")

    if not isinstance(result, SentimentClassificationResult):
        raise ValueError("Result must be SentimentClassificationResult.")

    return NewsEventRecord(
        event_id=record.event_id,
        timestamp=record.timestamp,
        title=record.title,
        event_type=record.event_type,
        symbol=record.symbol,
        impact=normalize_historical_event_impact(result.impact),
        sentiment=normalize_historical_event_sentiment(result.sentiment),
        source=record.source,
        provider_id=record.provider_id,
        url=record.url,
        description=record.description,
        country=record.country,
        currency=record.currency,
        relevance_score=max(record.relevance_score, result.confidence),
        raw_payload=record.raw_payload,
        metadata={
            **record.metadata,
            "sentiment_confidence": result.confidence,
            "sentiment_confidence_level": normalize_sentiment_confidence_level(
                result.confidence_level,
            ).value,
            "sentiment_model_type": normalize_sentiment_model_type(result.model_type).value,
            "sentiment_summary": result.summary,
        },
    )