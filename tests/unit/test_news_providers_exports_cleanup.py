"""
Unit tests for AQOS news providers package exports cleanup.
"""

import aqos.news_providers as news_providers


def test_news_providers_all_exports_are_sorted_and_unique():
    assert news_providers.__all__ == sorted(news_providers.__all__)
    assert len(news_providers.__all__) == len(set(news_providers.__all__))


def test_news_providers_all_exports_exist_on_package():
    for export_name in news_providers.__all__:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_core_exports_exist():
    expected_exports = [
        "NewsProviderType",
        "NewsProviderConfig",
        "NewsProviderResult",
        "NewsEventRecord",
        "build_news_provider_result",
        "news_provider_success",
        "news_provider_failure",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_economic_calendar_exports_exist():
    expected_exports = [
        "EconomicCalendarEvent",
        "EconomicCalendarQuery",
        "EconomicCalendarProviderResult",
        "build_economic_calendar_event",
        "economic_calendar_event_to_news_record",
        "economic_calendar_result_to_news_provider_result",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_news_feed_exports_exist():
    expected_exports = [
        "NewsFeedArticle",
        "NewsFeedQuery",
        "NewsFeedProviderResult",
        "build_news_feed_article",
        "news_feed_article_to_news_record",
        "news_feed_result_to_news_provider_result",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_sentiment_exports_exist():
    expected_exports = [
        "SentimentClassificationRequest",
        "SentimentClassificationResult",
        "SentimentProviderResult",
        "build_sentiment_classification_request",
        "classify_text_with_keyword_lexicon",
        "apply_sentiment_result_to_news_record",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_local_json_exports_exist():
    expected_exports = [
        "LocalJsonNewsProviderConfig",
        "build_local_json_news_provider_config",
        "load_local_json_news_feed_result",
        "load_local_json_news_provider_result",
        "read_local_json_payload",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_http_exports_exist():
    expected_exports = [
        "HttpNewsProviderConfig",
        "HttpNewsProviderRequest",
        "HttpNewsProviderResponse",
        "HttpNewsFetcher",
        "build_http_news_provider_config",
        "load_http_news_feed_result",
        "load_http_news_provider_result",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_normalization_exports_exist():
    expected_exports = [
        "MacroEventNormalizationConfig",
        "MacroEventNormalizationResult",
        "MacroEventNormalizationSummary",
        "news_event_record_to_historical_event_row",
        "normalize_news_provider_result_for_macro_pipeline",
        "rank_historical_event_rows_by_relevance",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name


def test_news_providers_integration_exports_exist():
    expected_exports = [
        "NewsIntegrationHubConfig",
        "NewsIntegrationSource",
        "NewsIntegrationResult",
        "NewsIntegrationSummary",
        "build_news_integration_hub_config",
        "resolve_news_integration_source",
        "run_news_integration_hub",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name