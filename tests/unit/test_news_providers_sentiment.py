"""
Unit tests for AQOS sentiment classification contracts.
"""

import pytest

from aqos.news_providers import (
    NewsEventRecord,
    NewsFeedArticle,
    NewsProviderConfig,
    SentimentClassificationRequest,
    SentimentClassificationResult,
    SentimentConfidenceLevel,
    SentimentKeywordLexicon,
    SentimentModelType,
    SentimentProviderResult,
    apply_sentiment_result_to_news_record,
    build_news_event_record,
    build_news_feed_article,
    build_sentiment_classification_request,
    build_sentiment_classification_result,
    build_sentiment_keyword_lexicon,
    build_sentiment_provider_config,
    build_sentiment_provider_result,
    classify_text_with_keyword_lexicon,
    confidence_level_from_score,
    count_keyword_hits,
    dominant_sentiment_from_scores,
    news_event_record_to_sentiment_request,
    news_feed_article_to_sentiment_request,
    normalize_sentiment_confidence_level,
    normalize_sentiment_model_type,
    validate_sentiment_classification_requests,
    validate_sentiment_classification_results,
)


def sample_news_record():
    return build_news_event_record(
        event_id="event-001",
        timestamp="2026-01-01T10:00:00+00:00",
        title="Gold falls after hot CPI",
        event_type="news",
        symbol="XAUUSD",
        impact="high",
        sentiment="unknown",
        source="Reuters",
        provider_id="news-feed",
        description="Gold dropped as US inflation beat forecast.",
        relevance_score=0.8,
    )


def sample_article():
    return build_news_feed_article(
        article_id="article-001",
        published_at="2026-01-01T10:00:00+00:00",
        title="Bitcoin rallies after ETF inflows",
        source="CoinDesk",
        source_type="news_api",
        description="Crypto markets surged after strong inflows.",
        content="Bitcoin gained as risk sentiment improved.",
        language="en",
        country="US",
        symbol="BTC/USDT",
        topics=["crypto"],
        event_type="crypto",
        impact="medium",
        sentiment="unknown",
        relevance_score=0.9,
        provider_id="news-feed",
    )


def test_sentiment_enum_values():
    assert SentimentModelType.RULE_BASED.value == "rule_based"
    assert SentimentModelType.LLM.value == "llm"
    assert SentimentModelType.TRANSFORMER.value == "transformer"
    assert SentimentModelType.PROVIDER_API.value == "provider_api"
    assert SentimentModelType.HYBRID.value == "hybrid"
    assert SentimentModelType.UNKNOWN.value == "unknown"

    assert SentimentConfidenceLevel.LOW.value == "low"
    assert SentimentConfidenceLevel.MEDIUM.value == "medium"
    assert SentimentConfidenceLevel.HIGH.value == "high"
    assert SentimentConfidenceLevel.UNKNOWN.value == "unknown"


def test_sentiment_normalizers():
    assert normalize_sentiment_model_type(SentimentModelType.LLM) == SentimentModelType.LLM
    assert normalize_sentiment_model_type(" RULE_BASED ") == SentimentModelType.RULE_BASED
    assert normalize_sentiment_confidence_level(SentimentConfidenceLevel.HIGH) == SentimentConfidenceLevel.HIGH
    assert normalize_sentiment_confidence_level(" MEDIUM ") == SentimentConfidenceLevel.MEDIUM

    with pytest.raises(ValueError):
        normalize_sentiment_model_type("bad")

    with pytest.raises(ValueError):
        normalize_sentiment_confidence_level("bad")


def test_sentiment_keyword_lexicon_to_dict_and_builder():
    lexicon = SentimentKeywordLexicon(
        bullish_keywords=[" Rally "],
        bearish_keywords=[" Drop "],
        neutral_keywords=[" Mixed "],
        high_impact_keywords=[" CPI "],
        metadata={"source": "test"},
    )

    payload = lexicon.to_dict()
    default_lexicon = build_sentiment_keyword_lexicon()

    assert payload == {
        "bullish_keywords": ["rally"],
        "bearish_keywords": ["drop"],
        "neutral_keywords": ["mixed"],
        "high_impact_keywords": ["cpi"],
        "metadata": {"source": "test"},
    }
    assert "rally" in default_lexicon.to_dict()["bullish_keywords"]
    assert "fall" in default_lexicon.to_dict()["bearish_keywords"]

    with pytest.raises(ValueError):
        SentimentKeywordLexicon(bullish_keywords="bad")

    with pytest.raises(ValueError):
        SentimentKeywordLexicon(bearish_keywords=[""])

    with pytest.raises(ValueError):
        SentimentKeywordLexicon(metadata=[])


def test_sentiment_classification_request_to_dict():
    request = SentimentClassificationRequest(
        request_id=" request-001 ",
        text=" Gold falls after hot CPI ",
        symbol=" xauusd ",
        source=" Reuters ",
        provider_id=" provider ",
        model_type=" rule_based ",
        context={"event_id": "event-001"},
        metadata={"source": "test"},
    )

    payload = request.to_dict()

    assert request.word_count == 5
    assert payload["request_id"] == "request-001"
    assert payload["text"] == "Gold falls after hot CPI"
    assert payload["symbol"] == "XAUUSD"
    assert payload["source"] == "Reuters"
    assert payload["provider_id"] == "provider"
    assert payload["model_type"] == "rule_based"
    assert payload["word_count"] == 5


def test_sentiment_classification_request_builder_and_rejections():
    request = build_sentiment_classification_request(
        request_id="request",
        text="Market rallies.",
        symbol="XAUUSD",
    )

    assert isinstance(request, SentimentClassificationRequest)

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="", text="Text")

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="")

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="Text", symbol=123)

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="Text", symbol="bad symbol")

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="Text", source=123)

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="Text", provider_id=123)

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="Text", model_type="bad")

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="Text", context=[])

    with pytest.raises(ValueError):
        SentimentClassificationRequest(request_id="id", text="Text", metadata=[])


def test_sentiment_classification_result_to_dict():
    result = SentimentClassificationResult(
        request_id=" request ",
        sentiment=" bullish ",
        impact=" high ",
        confidence=0.9,
        confidence_level=" high ",
        bullish_score=0.9,
        bearish_score=0.05,
        neutral_score=0.05,
        summary=" Bullish result ",
        rationale=" Strong keywords ",
        model_type=" rule_based ",
        metadata={"source": "test"},
    )

    payload = result.to_dict()

    assert result.directional is True
    assert result.high_confidence is True
    assert payload["request_id"] == "request"
    assert payload["sentiment"] == "bullish"
    assert payload["impact"] == "high"
    assert payload["confidence"] == 0.9
    assert payload["confidence_level"] == "high"
    assert payload["model_type"] == "rule_based"


def test_sentiment_classification_result_builder_and_rejections():
    result = build_sentiment_classification_result(
        request_id="request",
        sentiment="bearish",
        confidence=0.8,
        confidence_level="high",
        bearish_score=0.8,
    )

    assert isinstance(result, SentimentClassificationResult)

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="")

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", sentiment="bad")

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", impact="bad")

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", confidence=2)

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", confidence_level="bad")

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", bullish_score=-1)

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", summary=123)

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", model_type="bad")

    with pytest.raises(ValueError):
        SentimentClassificationResult(request_id="request", metadata=[])


def test_sentiment_provider_config():
    config = build_sentiment_provider_config(
        provider_id="sentiment",
        name="Sentiment Provider",
        base_url="https://example.com",
        status="active",
    )

    assert isinstance(config, NewsProviderConfig)
    assert config.provider_type.value == "sentiment"
    assert config.active is True
    assert config.has_capability("sentiment") is True


def test_sentiment_provider_result_to_dict_and_rejections():
    result_item = build_sentiment_classification_result(
        request_id="request",
        sentiment="bullish",
        confidence=0.9,
        confidence_level="high",
        bullish_score=0.9,
    )
    result = SentimentProviderResult(
        success=True,
        results=[result_item],
        message=" OK ",
        provider_id=" sentiment ",
        metadata={"source": "test"},
    )

    payload = result.to_dict()

    assert result.failed is False
    assert result.result_count == 1
    assert result.directional_count == 1
    assert result.high_confidence_count == 1
    assert payload["success"] is True
    assert payload["result_count"] == 1

    built = build_sentiment_provider_result(
        success=True,
        results=[result_item],
    )
    assert isinstance(built, SentimentProviderResult)

    with pytest.raises(ValueError):
        SentimentProviderResult(success="yes")

    with pytest.raises(ValueError):
        SentimentProviderResult(success=True, results="bad")

    with pytest.raises(ValueError):
        SentimentProviderResult(success=True, results=["bad"])

    with pytest.raises(ValueError):
        SentimentProviderResult(success=True, message=123)

    with pytest.raises(ValueError):
        SentimentProviderResult(success=True, provider_id=123)

    with pytest.raises(ValueError):
        SentimentProviderResult(success=True, metadata=[])

    assert validate_sentiment_classification_results([result_item]) == [result_item]


def test_confidence_and_dominant_sentiment_helpers():
    assert confidence_level_from_score(0.8) == SentimentConfidenceLevel.HIGH
    assert confidence_level_from_score(0.5) == SentimentConfidenceLevel.MEDIUM
    assert confidence_level_from_score(0.2) == SentimentConfidenceLevel.LOW

    assert dominant_sentiment_from_scores(
        bullish_score=0.8,
        bearish_score=0.1,
        neutral_score=0.1,
    ).value == "bullish"

    assert dominant_sentiment_from_scores(
        bullish_score=0.2,
        bearish_score=0.7,
        neutral_score=0.1,
    ).value == "bearish"

    assert dominant_sentiment_from_scores(
        bullish_score=0.48,
        bearish_score=0.45,
        neutral_score=0.07,
    ).value == "mixed"

    with pytest.raises(ValueError):
        confidence_level_from_score(2)

    with pytest.raises(ValueError):
        dominant_sentiment_from_scores(
            bullish_score=2,
            bearish_score=0,
            neutral_score=0,
        )


def test_count_keyword_hits_and_keyword_classification():
    assert count_keyword_hits("Gold rally after CPI rally", ["rally", "cpi"]) == 2

    request = build_sentiment_classification_request(
        request_id="request",
        text="Gold falls after hot CPI and dollar surge.",
        symbol="XAUUSD",
        source="Reuters",
    )
    result = classify_text_with_keyword_lexicon(request)

    assert result.sentiment.value == "mixed"
    assert result.impact.value == "high"
    assert result.confidence_level.value in {"medium", "high"}
    assert result.model_type.value == "rule_based"

    bullish_request = build_sentiment_classification_request(
        request_id="bullish",
        text="Bitcoin rallies after strong ETF inflow.",
        symbol="BTC/USDT",
    )
    bullish = classify_text_with_keyword_lexicon(bullish_request)

    assert bullish.sentiment.value == "bullish"

    with pytest.raises(ValueError):
        count_keyword_hits("", ["rally"])

    with pytest.raises(ValueError):
        count_keyword_hits("text", [""])

    with pytest.raises(ValueError):
        classify_text_with_keyword_lexicon("bad")

    with pytest.raises(ValueError):
        classify_text_with_keyword_lexicon(request, lexicon="bad")


def test_news_record_to_sentiment_request():
    record = sample_news_record()
    request = news_event_record_to_sentiment_request(record)

    assert isinstance(request, SentimentClassificationRequest)
    assert request.request_id == "event-001-sentiment"
    assert request.symbol == "XAUUSD"
    assert "Gold falls" in request.text
    assert request.context["event_id"] == "event-001"

    with pytest.raises(ValueError):
        news_event_record_to_sentiment_request("bad")


def test_news_feed_article_to_sentiment_request():
    article = sample_article()
    request = news_feed_article_to_sentiment_request(article)

    assert isinstance(request, SentimentClassificationRequest)
    assert request.request_id == "article-001-sentiment"
    assert request.symbol == "BTC/USDT"
    assert "Bitcoin rallies" in request.text
    assert request.context["article_id"] == "article-001"

    with pytest.raises(ValueError):
        news_feed_article_to_sentiment_request("bad")


def test_apply_sentiment_result_to_news_record():
    record = sample_news_record()
    result = build_sentiment_classification_result(
        request_id="request",
        sentiment="bearish",
        impact="high",
        confidence=0.95,
        confidence_level="high",
        bearish_score=0.95,
        summary="Bearish CPI shock.",
        model_type="rule_based",
    )

    enriched = apply_sentiment_result_to_news_record(record, result)

    assert isinstance(enriched, NewsEventRecord)
    assert enriched.event_id == record.event_id
    assert enriched.sentiment.value == "bearish"
    assert enriched.impact.value == "high"
    assert enriched.relevance_score == 0.95
    assert enriched.metadata["sentiment_confidence"] == 0.95
    assert enriched.metadata["sentiment_model_type"] == "rule_based"

    with pytest.raises(ValueError):
        apply_sentiment_result_to_news_record("bad", result)

    with pytest.raises(ValueError):
        apply_sentiment_result_to_news_record(record, "bad")


def test_sentiment_validators_and_exports_exist():
    request = build_sentiment_classification_request(
        request_id="request",
        text="Text",
    )
    result = build_sentiment_classification_result(
        request_id="request",
    )

    assert validate_sentiment_classification_requests([request]) == [request]
    assert validate_sentiment_classification_results([result]) == [result]

    with pytest.raises(ValueError):
        validate_sentiment_classification_requests("bad")

    with pytest.raises(ValueError):
        validate_sentiment_classification_requests(["bad"])

    with pytest.raises(ValueError):
        validate_sentiment_classification_results("bad")

    with pytest.raises(ValueError):
        validate_sentiment_classification_results(["bad"])

    import aqos.news_providers as news_providers

    expected_exports = [
        "SentimentClassificationRequest",
        "SentimentClassificationResult",
        "SentimentConfidenceLevel",
        "SentimentKeywordLexicon",
        "SentimentModelType",
        "SentimentProviderResult",
        "apply_sentiment_result_to_news_record",
        "build_sentiment_classification_request",
        "build_sentiment_classification_result",
        "build_sentiment_keyword_lexicon",
        "build_sentiment_provider_config",
        "build_sentiment_provider_result",
        "classify_text_with_keyword_lexicon",
        "confidence_level_from_score",
        "count_keyword_hits",
        "dominant_sentiment_from_scores",
        "news_event_record_to_sentiment_request",
        "news_feed_article_to_sentiment_request",
        "normalize_sentiment_confidence_level",
        "normalize_sentiment_model_type",
        "validate_sentiment_classification_requests",
        "validate_sentiment_classification_results",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name