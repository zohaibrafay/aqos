"""
Unit tests for AQOS Trading Economics macro calendar connector.
"""

import pytest

from aqos.news_providers import (
    EconomicCalendarProviderResult,
    HttpNewsProviderConfig,
    LiveNewsConnectorDefinition,
    LiveNewsConnectorRuntimeConfig,
    NewsProviderCredentials,
    NewsProviderResult,
    TradingEconomicsCalendarEndpoint,
    TradingEconomicsImportance,
    TradingEconomicsMacroQuery,
    build_trading_economics_connector_definition,
    build_trading_economics_http_config,
    build_trading_economics_macro_query,
    build_trading_economics_runtime_config,
    load_trading_economics_calendar_result,
    load_trading_economics_macro_provider_result,
    load_trading_economics_news_provider_result,
    normalize_trading_economics_calendar_endpoint,
    normalize_trading_economics_importance,
    normalize_trading_economics_payload,
    safe_float,
    trading_economics_importance_to_impact,
    trading_economics_provider_result_to_calendar_result,
    trading_economics_query_to_query_params,
    trading_economics_raw_row_to_normalized_macro_row,
    trading_economics_surprise_to_sentiment,
    validate_trading_economics_string_list,
)


def sample_trading_economics_payload():
    return [
        {
            "Id": "te-1",
            "Date": "2026-07-09T12:00:00Z",
            "Country": "United States",
            "Currency": "USD",
            "Event": "Inflation Rate YoY",
            "Category": "Inflation Rate",
            "Importance": "3",
            "Actual": "3.4%",
            "Forecast": "3.1%",
            "Previous": "3.0%",
            "Unit": "%",
            "Ticker": "USIRYY",
            "URL": "https://example.com/us-cpi",
        },
        {
            "Id": "te-2",
            "Date": "2026-07-09T13:00:00Z",
            "Country": "United States",
            "Currency": "USD",
            "Event": "Initial Jobless Claims",
            "Category": "Jobless Claims",
            "Importance": "2",
            "Actual": "210K",
            "Forecast": "220K",
            "Previous": "225K",
            "Unit": "K",
            "Ticker": "IJCUSA",
            "URL": "https://example.com/jobless-claims",
        },
    ]


def test_trading_economics_enums_and_normalizers():
    assert TradingEconomicsCalendarEndpoint.CALENDAR.value == "calendar"
    assert TradingEconomicsCalendarEndpoint.COUNTRY_CALENDAR.value == "country_calendar"
    assert TradingEconomicsCalendarEndpoint.INDICATOR_CALENDAR.value == "indicator_calendar"

    assert TradingEconomicsImportance.LOW.value == "low"
    assert TradingEconomicsImportance.MEDIUM.value == "medium"
    assert TradingEconomicsImportance.HIGH.value == "high"
    assert TradingEconomicsImportance.UNKNOWN.value == "unknown"

    assert (
        normalize_trading_economics_calendar_endpoint(" CALENDAR ")
        == TradingEconomicsCalendarEndpoint.CALENDAR
    )
    assert normalize_trading_economics_importance(" HIGH ") == TradingEconomicsImportance.HIGH

    with pytest.raises(ValueError):
        normalize_trading_economics_calendar_endpoint("bad")

    with pytest.raises(ValueError):
        normalize_trading_economics_importance("bad")


def test_trading_economics_macro_query_to_dict_and_builder():
    query = TradingEconomicsMacroQuery(
        endpoint=" country_calendar ",
        countries=[" United States ", " United Kingdom "],
        indicators=[" Inflation Rate ", " Interest Rate "],
        importance=" high ",
        from_date="2026-07-01",
        to_date="2026-07-09",
        limit=25,
        metadata={"source": "test"},
    )

    payload = query.to_dict()
    built = build_trading_economics_macro_query(countries=["United States"])

    assert payload["endpoint"] == "country_calendar"
    assert payload["countries"] == ["United States", "United Kingdom"]
    assert payload["country_expression"] == "United States,United Kingdom"
    assert payload["indicators"] == ["Inflation Rate", "Interest Rate"]
    assert payload["indicator_expression"] == "Inflation Rate,Interest Rate"
    assert payload["importance"] == "high"
    assert payload["from_date"] == "2026-07-01"
    assert payload["to_date"] == "2026-07-09"
    assert payload["limit"] == 25
    assert isinstance(built, TradingEconomicsMacroQuery)

    with pytest.raises(ValueError):
        TradingEconomicsMacroQuery(endpoint="bad")

    with pytest.raises(ValueError):
        TradingEconomicsMacroQuery(countries="bad")

    with pytest.raises(ValueError):
        TradingEconomicsMacroQuery(countries=[""])

    with pytest.raises(ValueError):
        TradingEconomicsMacroQuery(indicators="bad")

    with pytest.raises(ValueError):
        TradingEconomicsMacroQuery(importance="bad")

    with pytest.raises(ValueError):
        TradingEconomicsMacroQuery(limit=0)

    with pytest.raises(ValueError):
        TradingEconomicsMacroQuery(metadata=[])


def test_trading_economics_query_to_query_params():
    query = build_trading_economics_macro_query(
        countries=["United States"],
        indicators=["Inflation Rate"],
        importance="high",
        from_date="2026-07-01",
        to_date="2026-07-09",
        limit=10,
    )

    params = trading_economics_query_to_query_params(query)

    assert params["format"] == "json"
    assert params["country"] == "United States"
    assert params["indicator"] == "Inflation Rate"
    assert params["importance"] == "high"
    assert params["d1"] == "2026-07-01"
    assert params["d2"] == "2026-07-09"
    assert params["limit"] == 10

    with pytest.raises(ValueError):
        trading_economics_query_to_query_params("bad")


def test_trading_economics_connector_definition():
    definition = build_trading_economics_connector_definition()

    assert isinstance(definition, LiveNewsConnectorDefinition)
    assert definition.to_dict()["connector_id"] == "trading_economics"
    assert definition.to_dict()["name"] == "Trading Economics Calendar"
    assert definition.to_dict()["category"] == "macro_calendar"
    assert definition.to_dict()["endpoint"]["endpoint"] == "/calendar"
    assert definition.to_dict()["endpoint"]["payload_key"] == "data"
    assert definition.to_dict()["api_key_query_param"] == "c"
    assert definition.to_dict()["requires_api_key"] is True

    with pytest.raises(ValueError):
        build_trading_economics_connector_definition(endpoint="bad")


def test_trading_economics_runtime_and_http_config():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="client:secret",
    )
    query = build_trading_economics_macro_query(
        countries=["United States"],
        indicators=["Inflation Rate"],
        from_date="2026-07-01",
        to_date="2026-07-09",
    )
    runtime = build_trading_economics_runtime_config(
        query=query,
        credentials=credentials,
    )
    http_config = build_trading_economics_http_config(
        query=query,
        credentials=credentials,
    )

    assert isinstance(runtime, LiveNewsConnectorRuntimeConfig)
    assert isinstance(http_config, HttpNewsProviderConfig)
    assert http_config.provider_id == "trading_economics"
    assert http_config.base_url == "https://api.tradingeconomics.com"
    assert http_config.endpoint == "/calendar"
    assert http_config.payload_key == "data"
    assert http_config.api_key_query_param == "c"
    assert http_config.default_query_params["country"] == "United States"
    assert http_config.default_query_params["indicator"] == "Inflation Rate"

    with pytest.raises(ValueError):
        build_trading_economics_runtime_config(query="bad")


def test_trading_economics_mapping_helpers():
    assert safe_float("3.4%") == 3.4
    assert safe_float("1,250") == 1250.0
    assert safe_float("") is None
    assert safe_float(None) is None

    assert trading_economics_importance_to_impact("3") == "high"
    assert trading_economics_importance_to_impact("2") == "medium"
    assert trading_economics_importance_to_impact("1") == "low"
    assert trading_economics_importance_to_impact("bad") == "unknown"

    assert trading_economics_surprise_to_sentiment(actual="3.4", forecast="3.1") == "bullish"
    assert trading_economics_surprise_to_sentiment(actual="2.9", forecast="3.1") == "bearish"
    assert trading_economics_surprise_to_sentiment(actual="3.1", forecast="3.1") == "neutral"
    assert trading_economics_surprise_to_sentiment(actual="", forecast="3.1") == "unknown"


def test_trading_economics_raw_row_normalization():
    row = sample_trading_economics_payload()[0]
    normalized = trading_economics_raw_row_to_normalized_macro_row(row)

    assert normalized["event_id"] == "te-1"
    assert normalized["article_id"] == "te-1"
    assert normalized["timestamp"] == "2026-07-09T12:00:00Z"
    assert normalized["title"] == "Inflation Rate YoY"
    assert normalized["source"] == "Trading Economics"
    assert normalized["source_type"] == "economic_calendar"
    assert normalized["url"] == "https://example.com/us-cpi"
    assert normalized["country"] == "United States"
    assert normalized["currency"] == "USD"
    assert normalized["symbol"] == "USD"
    assert normalized["topics"] == ["macro"]
    assert normalized["event_type"] == "economic_calendar"
    assert normalized["impact"] == "high"
    assert normalized["sentiment"] == "bullish"
    assert normalized["provider_id"] == "trading_economics"
    assert normalized["metadata"]["actual"] == "3.4%"

    with pytest.raises(ValueError):
        trading_economics_raw_row_to_normalized_macro_row("bad")


def test_normalize_trading_economics_payload():
    normalized = normalize_trading_economics_payload(sample_trading_economics_payload())

    assert "data" in normalized
    assert len(normalized["data"]) == 2
    assert normalized["data"][0]["provider_id"] == "trading_economics"

    with pytest.raises(ValueError):
        normalize_trading_economics_payload({"missing": []})


def test_load_trading_economics_provider_results():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="client:secret",
    )
    query = build_trading_economics_macro_query(countries=["United States"])

    provider_result = load_trading_economics_news_provider_result(
        query=query,
        credentials=credentials,
        payload=sample_trading_economics_payload(),
    )
    fetcher_result = load_trading_economics_news_provider_result(
        query=query,
        credentials=credentials,
        fetcher=lambda _request: sample_trading_economics_payload(),
    )

    assert isinstance(provider_result, NewsProviderResult)
    assert provider_result.success is True
    assert provider_result.record_count == 2
    assert provider_result.records[0].event_id == "te-1"
    assert provider_result.records[0].source == "Trading Economics"

    assert fetcher_result.success is True
    assert fetcher_result.record_count == 2


def test_trading_economics_calendar_and_macro_results():
    credentials = NewsProviderCredentials(
        auth_type="api_key",
        api_key="client:secret",
    )
    query = build_trading_economics_macro_query(countries=["United States"])

    calendar_result = load_trading_economics_calendar_result(
        query=query,
        credentials=credentials,
        payload=sample_trading_economics_payload(),
    )
    macro_result = load_trading_economics_macro_provider_result(
        query=query,
        credentials=credentials,
        payload=sample_trading_economics_payload(),
    )

    assert isinstance(calendar_result, EconomicCalendarProviderResult)
    assert calendar_result.success is True
    assert calendar_result.event_count == 2

    assert isinstance(macro_result, NewsProviderResult)
    assert macro_result.success is True
    assert macro_result.record_count == 2
    assert macro_result.records[0].event_id == "te-1"

    provider_result = load_trading_economics_news_provider_result(
        query=query,
        credentials=credentials,
        payload=sample_trading_economics_payload(),
    )

    converted = trading_economics_provider_result_to_calendar_result(provider_result)

    assert converted.success is True
    assert converted.event_count == 2

    with pytest.raises(ValueError):
        trading_economics_provider_result_to_calendar_result("bad")


def test_trading_economics_validators_and_exports_exist():
    assert validate_trading_economics_string_list(["United States"]) == ["United States"]

    with pytest.raises(ValueError):
        validate_trading_economics_string_list("bad", "Countries")

    with pytest.raises(ValueError):
        validate_trading_economics_string_list([""], "Countries")

    import aqos.news_providers as news_providers

    expected_exports = [
        "TradingEconomicsCalendarEndpoint",
        "TradingEconomicsImportance",
        "TradingEconomicsMacroQuery",
        "build_trading_economics_connector_definition",
        "build_trading_economics_http_config",
        "build_trading_economics_macro_query",
        "build_trading_economics_runtime_config",
        "load_trading_economics_calendar_result",
        "load_trading_economics_macro_provider_result",
        "load_trading_economics_news_provider_result",
        "normalize_trading_economics_calendar_endpoint",
        "normalize_trading_economics_importance",
        "normalize_trading_economics_payload",
        "safe_float",
        "trading_economics_importance_to_impact",
        "trading_economics_provider_result_to_calendar_result",
        "trading_economics_query_to_query_params",
        "trading_economics_raw_row_to_normalized_macro_row",
        "trading_economics_surprise_to_sentiment",
        "validate_trading_economics_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name