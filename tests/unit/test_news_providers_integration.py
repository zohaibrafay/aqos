"""
Unit tests for AQOS news integration hub.
"""

import pytest

from aqos.news_providers import (
    NewsIntegrationHubConfig,
    NewsIntegrationResult,
    NewsIntegrationSource,
    NewsIntegrationSourceKind,
    NewsIntegrationStatus,
    NewsIntegrationSummary,
    NewsProviderResult,
    build_http_news_provider_config,
    build_macro_config_for_news_integration,
    build_macro_event_normalization_config,
    build_news_event_record,
    build_news_feed_article,
    build_news_feed_provider_result,
    build_news_integration_hub_config,
    build_news_integration_result,
    build_news_integration_source,
    build_news_integration_summary,
    build_news_provider_result,
    build_sentiment_classification_result,
    deduplicate_news_event_records,
    infer_news_integration_status,
    merge_news_provider_results,
    news_event_record_key,
    normalize_news_integration_source_kind,
    normalize_news_integration_status,
    resolve_news_integration_source,
    run_news_integration_hub,
)


def sample_records():
    return [
        build_news_event_record(
            event_id="event-001",
            timestamp="2026-01-01T10:00:00+00:00",
            title="Gold falls after hot CPI",
            event_type="news",
            symbol="XAUUSD",
            impact="high",
            sentiment="bearish",
            source="Reuters",
            provider_id="news-feed",
            description="Gold dropped after inflation beat forecast.",
            country="US",
            currency="USD",
            relevance_score=0.95,
        ),
        build_news_event_record(
            event_id="event-002",
            timestamp="2026-01-02T12:00:00+00:00",
            title="Bitcoin rallies after ETF inflows",
            event_type="crypto",
            symbol="BTC/USDT",
            impact="medium",
            sentiment="bullish",
            source="CoinDesk",
            provider_id="news-feed",
            description="Bitcoin gained after ETF inflows.",
            country="US",
            currency="USD",
            relevance_score=0.9,
        ),
    ]


def sample_provider_result():
    return build_news_provider_result(
        success=True,
        records=sample_records(),
        message="OK",
        provider_id="news-feed",
    )


def sample_feed_result():
    article = build_news_feed_article(
        article_id="article-001",
        published_at="2026-01-03T10:00:00+00:00",
        title="ECB comments move euro",
        source="Bloomberg",
        source_type="news_api",
        description="Rates remained in focus.",
        country="DE",
        symbol="EUR/USD",
        topics=["forex", "central_banks"],
        event_type="central_bank",
        impact="medium",
        sentiment="mixed",
        relevance_score=0.8,
        provider_id="feed",
    )

    return build_news_feed_provider_result(
        success=True,
        articles=[article],
        provider_id="feed",
    )


def sample_http_payload():
    return {
        "articles": [
            {
                "id": "http-001",
                "published_at": "2026-01-04T09:00:00+00:00",
                "title": "Gold rebounds after dollar weakness",
                "source": "MarketWatch",
                "description": "Gold recovered as the dollar softened.",
                "country": "US",
                "symbol": "XAUUSD",
                "topics": ["commodities"],
                "event_type": "news",
                "impact": "medium",
                "sentiment": "bullish",
                "relevance_score": 0.85,
            }
        ]
    }


def test_news_integration_enums_and_normalizers():
    assert NewsIntegrationSourceKind.NEWS_PROVIDER_RESULT.value == "news_provider_result"
    assert NewsIntegrationSourceKind.NEWS_FEED_RESULT.value == "news_feed_result"
    assert NewsIntegrationSourceKind.ECONOMIC_CALENDAR_RESULT.value == "economic_calendar_result"
    assert NewsIntegrationSourceKind.LOCAL_JSON.value == "local_json"
    assert NewsIntegrationSourceKind.HTTP.value == "http"
    assert NewsIntegrationSourceKind.MANUAL_RECORDS.value == "manual_records"
    assert NewsIntegrationSourceKind.UNKNOWN.value == "unknown"

    assert NewsIntegrationStatus.READY.value == "ready"
    assert NewsIntegrationStatus.EMPTY.value == "empty"
    assert NewsIntegrationStatus.PARTIAL.value == "partial"
    assert NewsIntegrationStatus.ERROR.value == "error"

    assert normalize_news_integration_source_kind(" HTTP ") == NewsIntegrationSourceKind.HTTP
    assert normalize_news_integration_status(" READY ") == NewsIntegrationStatus.READY

    with pytest.raises(ValueError):
        normalize_news_integration_source_kind("bad")

    with pytest.raises(ValueError):
        normalize_news_integration_status("bad")


def test_news_integration_hub_config_to_dict_and_rejections():
    config = NewsIntegrationHubConfig(
        hub_id=" hub ",
        name=" Hub ",
        default_symbol=" xauusd ",
        normalize_macro_events=True,
        deduplicate_records=True,
        metadata={"source": "test"},
    )

    payload = config.to_dict()
    built = build_news_integration_hub_config(hub_id="hub")

    assert payload["hub_id"] == "hub"
    assert payload["name"] == "Hub"
    assert payload["default_symbol"] == "XAUUSD"
    assert isinstance(built, NewsIntegrationHubConfig)

    with pytest.raises(ValueError):
        NewsIntegrationHubConfig(hub_id="")

    with pytest.raises(ValueError):
        NewsIntegrationHubConfig(hub_id="hub", name="")

    with pytest.raises(ValueError):
        NewsIntegrationHubConfig(hub_id="hub", default_symbol=123)

    with pytest.raises(ValueError):
        NewsIntegrationHubConfig(hub_id="hub", normalize_macro_events="yes")

    with pytest.raises(ValueError):
        NewsIntegrationHubConfig(hub_id="hub", deduplicate_records="yes")

    with pytest.raises(ValueError):
        NewsIntegrationHubConfig(hub_id="hub", metadata=[])


def test_news_integration_source_to_dict_and_rejections():
    source = NewsIntegrationSource(
        source_id=" source ",
        source_kind=" news_provider_result ",
        provider_result=sample_provider_result(),
        metadata={"source": "test"},
    )
    payload = source.to_dict()
    built = build_news_integration_source(
        source_id="source",
        source_kind="manual_records",
        manual_records=sample_records(),
    )

    assert payload["source_id"] == "source"
    assert payload["source_kind"] == "news_provider_result"
    assert payload["has_provider_result"] is True
    assert isinstance(built, NewsIntegrationSource)

    with pytest.raises(ValueError):
        NewsIntegrationSource(source_id="", source_kind="manual_records")

    with pytest.raises(ValueError):
        NewsIntegrationSource(source_id="source", source_kind="bad")

    with pytest.raises(ValueError):
        NewsIntegrationSource(source_id="source", source_kind="news_provider_result", provider_result="bad")

    with pytest.raises(ValueError):
        NewsIntegrationSource(source_id="source", source_kind="manual_records", manual_records=["bad"])

    with pytest.raises(ValueError):
        NewsIntegrationSource(source_id="source", source_kind="manual_records", query="bad")

    with pytest.raises(ValueError):
        NewsIntegrationSource(source_id="source", source_kind="manual_records", payload="bad")

    with pytest.raises(ValueError):
        NewsIntegrationSource(source_id="source", source_kind="manual_records", metadata=[])


def test_news_integration_summary_and_result_to_dict():
    summary = NewsIntegrationSummary(
        hub_id=" hub ",
        status=" ready ",
        source_count=2,
        successful_source_count=2,
        failed_source_count=0,
        record_count=3,
        duplicate_count=1,
        macro_row_count=3,
        issue_count=0,
        metadata={"source": "test"},
    )
    provider_result = sample_provider_result()
    result = NewsIntegrationResult(
        success=True,
        provider_result=provider_result,
        summary=summary,
        source_results={"source": provider_result},
        metadata={"source": "test"},
    )

    summary_payload = summary.to_dict()
    result_payload = result.to_dict()

    assert summary.ready is True
    assert summary.empty is False
    assert summary_payload["status"] == "ready"
    assert result.failed is False
    assert result.issue_count == 0
    assert result_payload["success"] is True

    built_summary = build_news_integration_summary(hub_id="hub")
    built_result = build_news_integration_result(
        success=True,
        provider_result=provider_result,
    )

    assert isinstance(built_summary, NewsIntegrationSummary)
    assert isinstance(built_result, NewsIntegrationResult)

    with pytest.raises(ValueError):
        NewsIntegrationSummary(hub_id="")

    with pytest.raises(ValueError):
        NewsIntegrationSummary(hub_id="hub", status="bad")

    with pytest.raises(ValueError):
        NewsIntegrationSummary(hub_id="hub", source_count=-1)

    with pytest.raises(ValueError):
        NewsIntegrationSummary(hub_id="hub", metadata=[])

    with pytest.raises(ValueError):
        NewsIntegrationResult(success="yes", provider_result=provider_result)

    with pytest.raises(ValueError):
        NewsIntegrationResult(success=True, provider_result="bad")

    with pytest.raises(ValueError):
        NewsIntegrationResult(success=True, provider_result=provider_result, issues="bad")

    with pytest.raises(ValueError):
        NewsIntegrationResult(success=True, provider_result=provider_result, source_results={"x": "bad"})


def test_record_key_and_deduplicate():
    records = [sample_records()[0], sample_records()[0], sample_records()[1]]
    key = news_event_record_key(records[0])
    deduped, duplicate_count = deduplicate_news_event_records(records)

    assert "gold falls" in key
    assert len(deduped) == 2
    assert duplicate_count == 1

    with pytest.raises(ValueError):
        news_event_record_key("bad")

    with pytest.raises(ValueError):
        deduplicate_news_event_records(["bad"])


def test_merge_provider_results():
    result, duplicate_count = merge_news_provider_results(
        [
            build_news_provider_result(success=True, records=[sample_records()[0]]),
            build_news_provider_result(success=True, records=[sample_records()[0], sample_records()[1]]),
        ],
        provider_id="hub",
    )

    assert isinstance(result, NewsProviderResult)
    assert result.success is True
    assert result.record_count == 2
    assert duplicate_count == 1

    with pytest.raises(ValueError):
        merge_news_provider_results("bad")

    with pytest.raises(ValueError):
        merge_news_provider_results(["bad"])


def test_resolve_news_integration_source_provider_feed_manual_and_missing():
    provider_source = build_news_integration_source(
        source_id="provider",
        source_kind="news_provider_result",
        provider_result=sample_provider_result(),
    )
    feed_source = build_news_integration_source(
        source_id="feed",
        source_kind="news_feed_result",
        news_feed_result=sample_feed_result(),
    )
    manual_source = build_news_integration_source(
        source_id="manual",
        source_kind="manual_records",
        manual_records=sample_records(),
    )
    missing_source = build_news_integration_source(
        source_id="missing",
        source_kind="news_provider_result",
    )

    provider_result = resolve_news_integration_source(provider_source)
    feed_result = resolve_news_integration_source(feed_source)
    manual_result = resolve_news_integration_source(manual_source)
    missing_result = resolve_news_integration_source(missing_source)

    assert provider_result.record_count == 2
    assert feed_result.record_count == 1
    assert manual_result.record_count == 2
    assert missing_result.failed is True

    with pytest.raises(ValueError):
        resolve_news_integration_source("bad")


def test_resolve_http_source_with_payload():
    http_config = build_http_news_provider_config(
        provider_id="http",
        name="HTTP",
        base_url="https://example.com",
        payload_key="articles",
    )
    source = build_news_integration_source(
        source_id="http",
        source_kind="http",
        http_config=http_config,
        payload=sample_http_payload(),
    )

    result = resolve_news_integration_source(source)

    assert result.success is True
    assert result.record_count == 1
    assert result.records[0].event_id == "http-001"


def test_macro_config_and_status_inference():
    config = build_news_integration_hub_config(
        hub_id="hub",
        default_symbol="XAUUSD",
    )
    macro_config = build_macro_config_for_news_integration(config=config)

    assert macro_config.dataset_id == "hub-macro-events"
    assert macro_config.symbol == "XAUUSD"

    explicit = build_macro_event_normalization_config(dataset_id="explicit")
    assert build_macro_config_for_news_integration(config=config, macro_config=explicit) == explicit

    assert infer_news_integration_status(
        record_count=2,
        source_count=2,
        failed_source_count=0,
    ) == NewsIntegrationStatus.READY

    assert infer_news_integration_status(
        record_count=2,
        source_count=2,
        failed_source_count=1,
    ) == NewsIntegrationStatus.PARTIAL

    assert infer_news_integration_status(
        record_count=0,
        source_count=0,
        failed_source_count=0,
    ) == NewsIntegrationStatus.EMPTY

    assert infer_news_integration_status(
        record_count=0,
        source_count=2,
        failed_source_count=2,
    ) == NewsIntegrationStatus.ERROR

    with pytest.raises(ValueError):
        build_macro_config_for_news_integration(config="bad")

    with pytest.raises(ValueError):
        build_macro_config_for_news_integration(config=config, macro_config="bad")


def test_run_news_integration_hub():
    config = build_news_integration_hub_config(
        hub_id="hub",
        default_symbol="XAUUSD",
    )
    macro_config = build_macro_event_normalization_config(
        dataset_id="hub-macro",
        min_relevance_score=0.8,
    )
    sentiment_result = build_sentiment_classification_result(
        request_id="event-001-sentiment",
        sentiment="bearish",
        impact="high",
        confidence=0.99,
        confidence_level="high",
        bearish_score=0.99,
        model_type="rule_based",
    )
    sources = [
        build_news_integration_source(
            source_id="provider",
            source_kind="news_provider_result",
            provider_result=sample_provider_result(),
        ),
        build_news_integration_source(
            source_id="feed",
            source_kind="news_feed_result",
            news_feed_result=sample_feed_result(),
        ),
    ]

    result = run_news_integration_hub(
        config=config,
        sources=sources,
        macro_config=macro_config,
        sentiment_results=[sentiment_result],
    )

    assert isinstance(result, NewsIntegrationResult)
    assert result.success is True
    assert result.provider_result.record_count == 3
    assert result.macro_result.row_count == 3
    assert result.summary.status == NewsIntegrationStatus.READY
    assert result.summary.source_count == 2
    assert result.provider_result.records[0].relevance_score == 0.99

    with pytest.raises(ValueError):
        run_news_integration_hub(config="bad", sources=sources)

    with pytest.raises(ValueError):
        run_news_integration_hub(config=config, sources="bad")

    with pytest.raises(ValueError):
        run_news_integration_hub(config=config, sources=["bad"])


def test_news_providers_integration_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "NewsIntegrationHubConfig",
        "NewsIntegrationResult",
        "NewsIntegrationSource",
        "NewsIntegrationSourceKind",
        "NewsIntegrationStatus",
        "NewsIntegrationSummary",
        "build_macro_config_for_news_integration",
        "build_news_integration_hub_config",
        "build_news_integration_result",
        "build_news_integration_source",
        "build_news_integration_summary",
        "deduplicate_news_event_records",
        "infer_news_integration_status",
        "merge_news_provider_results",
        "news_event_record_key",
        "normalize_news_integration_source_kind",
        "normalize_news_integration_status",
        "resolve_news_integration_source",
        "run_news_integration_hub",
        "validate_news_event_records",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name