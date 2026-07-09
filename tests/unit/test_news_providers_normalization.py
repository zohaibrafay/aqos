"""
Unit tests for AQOS macro event normalization pipeline.
"""

import pytest

from aqos.news_providers import (
    MacroEventNormalizationConfig,
    MacroEventNormalizationResult,
    MacroEventNormalizationStatus,
    MacroEventNormalizationSummary,
    MacroEventSourceKind,
    apply_sentiment_results_to_news_records,
    build_economic_calendar_event,
    build_economic_calendar_provider_result,
    build_macro_event_normalization_config,
    build_macro_event_normalization_result,
    build_macro_event_normalization_summary,
    build_news_event_record,
    build_news_feed_article,
    build_news_feed_provider_result,
    build_news_provider_result,
    build_sentiment_classification_result,
    deduplicate_historical_event_rows,
    economic_calendar_result_to_historical_event_rows,
    filter_historical_event_rows_for_macro_pipeline,
    historical_event_row_key,
    historical_event_row_matches_config,
    news_event_record_to_historical_event_row,
    news_event_records_to_historical_event_rows,
    news_feed_result_to_historical_event_rows,
    news_provider_result_to_historical_event_rows,
    normalize_economic_calendar_result_for_macro_pipeline,
    normalize_historical_event_rows_for_macro_pipeline,
    normalize_macro_event_normalization_status,
    normalize_macro_event_source_kind,
    normalize_news_feed_result_for_macro_pipeline,
    normalize_news_provider_result_for_macro_pipeline,
    rank_historical_event_rows_by_relevance,
    summarize_normalized_macro_event_rows,
    validate_historical_event_impact_filters,
    validate_historical_event_sentiment_filters,
    validate_historical_event_type_filters,
)


def sample_news_records():
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
            description="Gold dropped as inflation beat forecast.",
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
        build_news_event_record(
            event_id="event-003",
            timestamp="2026-01-03T09:00:00+00:00",
            title="ECB comments move euro",
            event_type="central_bank",
            symbol="EUR/USD",
            impact="medium",
            sentiment="mixed",
            source="Bloomberg",
            provider_id="news-feed",
            description="Rates remained in focus.",
            country="DE",
            currency="EUR",
            relevance_score=0.7,
        ),
    ]


def sample_news_provider_result():
    return build_news_provider_result(
        success=True,
        records=sample_news_records(),
        message="OK",
        provider_id="news-feed",
    )


def sample_news_feed_result():
    articles = [
        build_news_feed_article(
            article_id="article-001",
            published_at="2026-01-01T10:00:00+00:00",
            title="Gold falls after hot CPI",
            source="Reuters",
            source_type="news_api",
            description="Gold dropped as US inflation beat forecast.",
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
            country="US",
            symbol="BTC/USDT",
            topics=["crypto"],
            event_type="crypto",
            impact="medium",
            sentiment="bullish",
            relevance_score=0.9,
            provider_id="news-feed",
        ),
    ]

    return build_news_feed_provider_result(
        success=True,
        articles=articles,
        provider_id="news-feed",
    )


def sample_economic_calendar_result():
    events = [
        build_economic_calendar_event(
            event_id="calendar-001",
            timestamp="2026-01-01T12:30:00+00:00",
            title="US CPI",
            country="US",
            currency="USD",
            category="inflation",
            importance="high",
            impact="high",
            sentiment="bearish",
            actual_value=3.4,
            forecast_value=3.2,
            source="calendar",
            provider_id="calendar",
            description="US inflation came above forecast.",
            relevance_score=0.95,
        )
    ]

    return build_economic_calendar_provider_result(
        success=True,
        events=events,
        provider_id="calendar",
    )


def test_macro_event_enums_and_normalizers():
    assert MacroEventNormalizationStatus.READY.value == "ready"
    assert MacroEventNormalizationStatus.EMPTY.value == "empty"
    assert MacroEventNormalizationStatus.WARNING.value == "warning"
    assert MacroEventNormalizationStatus.ERROR.value == "error"

    assert MacroEventSourceKind.NEWS_PROVIDER.value == "news_provider"
    assert MacroEventSourceKind.NEWS_FEED.value == "news_feed"
    assert MacroEventSourceKind.ECONOMIC_CALENDAR.value == "economic_calendar"
    assert MacroEventSourceKind.SENTIMENT.value == "sentiment"
    assert MacroEventSourceKind.MANUAL.value == "manual"
    assert MacroEventSourceKind.UNKNOWN.value == "unknown"

    assert normalize_macro_event_normalization_status(" READY ") == MacroEventNormalizationStatus.READY
    assert normalize_macro_event_source_kind(" NEWS_FEED ") == MacroEventSourceKind.NEWS_FEED

    with pytest.raises(ValueError):
        normalize_macro_event_normalization_status("bad")

    with pytest.raises(ValueError):
        normalize_macro_event_source_kind("bad")


def test_macro_event_filter_validators():
    assert validate_historical_event_type_filters(["news", "crypto"]) == ["news", "crypto"]
    assert validate_historical_event_impact_filters(["high", "medium"]) == ["high", "medium"]
    assert validate_historical_event_sentiment_filters(["bullish", "bearish"]) == ["bullish", "bearish"]

    with pytest.raises(ValueError):
        validate_historical_event_type_filters("bad")

    with pytest.raises(ValueError):
        validate_historical_event_type_filters(["bad"])

    with pytest.raises(ValueError):
        validate_historical_event_impact_filters("bad")

    with pytest.raises(ValueError):
        validate_historical_event_impact_filters(["bad"])

    with pytest.raises(ValueError):
        validate_historical_event_sentiment_filters("bad")

    with pytest.raises(ValueError):
        validate_historical_event_sentiment_filters(["bad"])


def test_macro_event_normalization_config_to_dict_and_rejections():
    config = MacroEventNormalizationConfig(
        dataset_id=" dataset ",
        symbol=" xauusd ",
        allowed_event_types=[" news "],
        allowed_impacts=[" high "],
        allowed_sentiments=[" bearish "],
        allowed_countries=[" us "],
        allowed_currencies=[" usd "],
        min_relevance_score=0.5,
        metadata={"source": "test"},
    )

    payload = config.to_dict()

    assert config.has_filters is True
    assert payload["dataset_id"] == "dataset"
    assert payload["symbol"] == "XAUUSD"
    assert payload["allowed_event_types"] == ["news"]
    assert payload["allowed_impacts"] == ["high"]
    assert payload["allowed_sentiments"] == ["bearish"]
    assert payload["allowed_countries"] == ["US"]
    assert payload["allowed_currencies"] == ["USD"]

    built = build_macro_event_normalization_config(
        dataset_id="dataset",
        symbol="XAUUSD",
    )
    assert isinstance(built, MacroEventNormalizationConfig)

    with pytest.raises(ValueError):
        MacroEventNormalizationConfig(dataset_id="")

    with pytest.raises(ValueError):
        MacroEventNormalizationConfig(dataset_id="dataset", symbol="bad symbol")

    with pytest.raises(ValueError):
        MacroEventNormalizationConfig(dataset_id="dataset", allowed_event_types="bad")

    with pytest.raises(ValueError):
        MacroEventNormalizationConfig(dataset_id="dataset", min_relevance_score=2)

    with pytest.raises(ValueError):
        MacroEventNormalizationConfig(dataset_id="dataset", deduplicate="yes")

    with pytest.raises(ValueError):
        MacroEventNormalizationConfig(dataset_id="dataset", include_unknown_symbol="yes")

    with pytest.raises(ValueError):
        MacroEventNormalizationConfig(dataset_id="dataset", metadata=[])


def test_macro_event_summary_and_result_to_dict():
    summary = MacroEventNormalizationSummary(
        dataset_id=" dataset ",
        status=" ready ",
        input_count=3,
        output_count=2,
        duplicate_count=1,
        dropped_count=0,
        high_impact_count=1,
        directional_count=2,
        metadata={"source": "test"},
    )
    result = MacroEventNormalizationResult(
        success=True,
        rows=[],
        summary=summary,
        message=" OK ",
        issues=[" warning "],
        metadata={"source": "test"},
    )

    summary_payload = summary.to_dict()
    result_payload = result.to_dict()

    assert summary.ready is True
    assert summary.empty is False
    assert summary_payload["status"] == "ready"
    assert result.failed is False
    assert result.issue_count == 1
    assert result_payload["message"] == "OK"

    built_summary = build_macro_event_normalization_summary(dataset_id="dataset")
    built_result = build_macro_event_normalization_result(success=True)

    assert isinstance(built_summary, MacroEventNormalizationSummary)
    assert isinstance(built_result, MacroEventNormalizationResult)

    with pytest.raises(ValueError):
        MacroEventNormalizationSummary(dataset_id="", status="ready")

    with pytest.raises(ValueError):
        MacroEventNormalizationSummary(dataset_id="dataset", status="bad")

    with pytest.raises(ValueError):
        MacroEventNormalizationSummary(dataset_id="dataset", input_count=-1)

    with pytest.raises(ValueError):
        MacroEventNormalizationSummary(dataset_id="dataset", metadata=[])

    with pytest.raises(ValueError):
        MacroEventNormalizationResult(success="yes")

    with pytest.raises(ValueError):
        MacroEventNormalizationResult(success=True, rows=["bad"])

    with pytest.raises(ValueError):
        MacroEventNormalizationResult(success=True, summary="bad")

    with pytest.raises(ValueError):
        MacroEventNormalizationResult(success=True, issues="bad")

    with pytest.raises(ValueError):
        MacroEventNormalizationResult(success=True, metadata=[])


def test_news_record_to_historical_event_row():
    record = sample_news_records()[0]
    row = news_event_record_to_historical_event_row(record)
    payload = row.to_dict()

    assert payload["event_id"] == "event-001"
    assert payload["event_type"] == "news"
    assert payload["symbol"] == "XAUUSD"
    assert payload["impact"] == "high"
    assert payload["sentiment"] == "bearish"
    assert payload["country"] == "US"
    assert payload["currency"] == "USD"
    assert row.high_impact is True
    assert row.directional is True

    with pytest.raises(ValueError):
        news_event_record_to_historical_event_row("bad")


def test_result_converters_to_historical_rows():
    provider_rows = news_provider_result_to_historical_event_rows(
        sample_news_provider_result(),
    )
    feed_rows = news_feed_result_to_historical_event_rows(
        sample_news_feed_result(),
    )
    calendar_rows = economic_calendar_result_to_historical_event_rows(
        sample_economic_calendar_result(),
        symbol="XAUUSD",
    )
    record_rows = news_event_records_to_historical_event_rows(
        sample_news_records(),
    )

    assert len(provider_rows) == 3
    assert len(feed_rows) == 2
    assert len(calendar_rows) == 1
    assert len(record_rows) == 3
    assert calendar_rows[0].to_dict()["event_type"] == "economic_calendar"

    with pytest.raises(ValueError):
        news_provider_result_to_historical_event_rows("bad")

    with pytest.raises(ValueError):
        news_feed_result_to_historical_event_rows("bad")

    with pytest.raises(ValueError):
        economic_calendar_result_to_historical_event_rows("bad")

    with pytest.raises(ValueError):
        news_event_records_to_historical_event_rows("bad")

    with pytest.raises(ValueError):
        news_event_records_to_historical_event_rows(["bad"])


def test_deduplicate_and_key():
    rows = news_provider_result_to_historical_event_rows(
        build_news_provider_result(
            success=True,
            records=[sample_news_records()[0], sample_news_records()[0]],
        )
    )

    key = historical_event_row_key(rows[0])
    deduped, duplicate_count = deduplicate_historical_event_rows(rows)

    assert "gold falls" in key
    assert len(deduped) == 1
    assert duplicate_count == 1

    with pytest.raises(ValueError):
        historical_event_row_key("bad")

    with pytest.raises(ValueError):
        deduplicate_historical_event_rows(["bad"])


def test_filter_rows_for_macro_pipeline():
    rows = news_provider_result_to_historical_event_rows(sample_news_provider_result())
    config = build_macro_event_normalization_config(
        dataset_id="xauusd-events",
        symbol="XAUUSD",
        allowed_impacts=["high"],
        allowed_sentiments=["bearish"],
        allowed_countries=["US"],
        allowed_currencies=["USD"],
        min_relevance_score=0.9,
    )

    filtered = filter_historical_event_rows_for_macro_pipeline(
        rows,
        config=config,
    )

    assert len(filtered) == 1
    assert filtered[0].to_dict()["event_id"] == "event-001"
    assert historical_event_row_matches_config(filtered[0], config) is True

    with pytest.raises(ValueError):
        filter_historical_event_rows_for_macro_pipeline(["bad"], config=config)

    with pytest.raises(ValueError):
        filter_historical_event_rows_for_macro_pipeline(rows, config="bad")

    with pytest.raises(ValueError):
        historical_event_row_matches_config("bad", config)

    with pytest.raises(ValueError):
        historical_event_row_matches_config(rows[0], "bad")


def test_normalize_historical_rows_for_macro_pipeline():
    rows = news_provider_result_to_historical_event_rows(
        build_news_provider_result(
            success=True,
            records=[
                sample_news_records()[0],
                sample_news_records()[0],
                sample_news_records()[1],
            ],
        )
    )
    config = build_macro_event_normalization_config(
        dataset_id="macro-events",
        min_relevance_score=0.8,
    )

    result = normalize_historical_event_rows_for_macro_pipeline(
        rows,
        config=config,
    )

    assert isinstance(result, MacroEventNormalizationResult)
    assert result.success is True
    assert result.row_count == 2
    assert result.summary.input_count == 3
    assert result.summary.output_count == 2
    assert result.summary.duplicate_count == 1
    assert result.summary.ready is True

    with pytest.raises(ValueError):
        normalize_historical_event_rows_for_macro_pipeline(["bad"], config=config)

    with pytest.raises(ValueError):
        normalize_historical_event_rows_for_macro_pipeline(rows, config="bad")


def test_normalize_provider_feed_and_calendar_results():
    config = build_macro_event_normalization_config(
        dataset_id="macro-events",
        min_relevance_score=0.8,
    )

    provider_result = normalize_news_provider_result_for_macro_pipeline(
        sample_news_provider_result(),
        config=config,
    )
    feed_result = normalize_news_feed_result_for_macro_pipeline(
        sample_news_feed_result(),
        config=config,
    )
    calendar_result = normalize_economic_calendar_result_for_macro_pipeline(
        sample_economic_calendar_result(),
        config=config,
        symbol="XAUUSD",
    )

    assert provider_result.row_count == 2
    assert feed_result.row_count == 2
    assert calendar_result.row_count == 1
    assert calendar_result.rows[0].to_dict()["symbol"] == "XAUUSD"


def test_apply_sentiment_results_to_news_records():
    records = sample_news_records()
    sentiment_result = build_sentiment_classification_result(
        request_id="event-001-sentiment",
        sentiment="bearish",
        impact="high",
        confidence=0.99,
        confidence_level="high",
        bearish_score=0.99,
        model_type="rule_based",
    )

    enriched = apply_sentiment_results_to_news_records(
        records,
        [sentiment_result],
    )

    assert len(enriched) == 3
    assert enriched[0].sentiment.value == "bearish"
    assert enriched[0].impact.value == "high"
    assert enriched[0].relevance_score == 0.99
    assert enriched[1].event_id == "event-002"

    with pytest.raises(ValueError):
        apply_sentiment_results_to_news_records("bad", [sentiment_result])

    with pytest.raises(ValueError):
        apply_sentiment_results_to_news_records(records, "bad")

    with pytest.raises(ValueError):
        apply_sentiment_results_to_news_records(records, ["bad"])

    with pytest.raises(ValueError):
        apply_sentiment_results_to_news_records(["bad"], [sentiment_result])


def test_summarize_and_rank_normalized_macro_rows():
    rows = news_provider_result_to_historical_event_rows(sample_news_provider_result())

    summary = summarize_normalized_macro_event_rows(
        dataset_id="macro-events",
        input_count=3,
        output_rows=rows,
    )
    ranked = rank_historical_event_rows_by_relevance(rows)

    assert summary.output_count == 3
    assert summary.high_impact_count == 1
    assert summary.directional_count == 2
    assert ranked[0].to_dict()["event_id"] == "event-001"
    assert ranked[-1].to_dict()["event_id"] == "event-003"

    with pytest.raises(ValueError):
        summarize_normalized_macro_event_rows(
            dataset_id="macro-events",
            input_count=3,
            output_rows=["bad"],
        )

    with pytest.raises(ValueError):
        rank_historical_event_rows_by_relevance(["bad"])


def test_news_providers_normalization_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "MacroEventNormalizationConfig",
        "MacroEventNormalizationResult",
        "MacroEventNormalizationStatus",
        "MacroEventNormalizationSummary",
        "MacroEventSourceKind",
        "apply_sentiment_results_to_news_records",
        "build_macro_event_normalization_config",
        "build_macro_event_normalization_result",
        "build_macro_event_normalization_summary",
        "deduplicate_historical_event_rows",
        "economic_calendar_result_to_historical_event_rows",
        "filter_historical_event_rows_for_macro_pipeline",
        "historical_event_row_key",
        "historical_event_row_matches_config",
        "news_event_record_to_historical_event_row",
        "news_event_records_to_historical_event_rows",
        "news_feed_result_to_historical_event_rows",
        "news_provider_result_to_historical_event_rows",
        "normalize_economic_calendar_result_for_macro_pipeline",
        "normalize_historical_event_rows_for_macro_pipeline",
        "normalize_macro_event_normalization_status",
        "normalize_macro_event_source_kind",
        "normalize_news_feed_result_for_macro_pipeline",
        "normalize_news_provider_result_for_macro_pipeline",
        "rank_historical_event_rows_by_relevance",
        "summarize_normalized_macro_event_rows",
        "validate_historical_event_impact_filters",
        "validate_historical_event_sentiment_filters",
        "validate_historical_event_type_filters",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name