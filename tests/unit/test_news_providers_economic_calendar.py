"""
Unit tests for AQOS economic calendar provider contracts.
"""

import pytest

from aqos.news_providers import (
    EconomicCalendarEvent,
    EconomicCalendarEventCategory,
    EconomicCalendarImportance,
    EconomicCalendarProviderResult,
    EconomicCalendarQuery,
    NewsEventRecord,
    NewsProviderConfig,
    NewsProviderResult,
    build_economic_calendar_event,
    build_economic_calendar_provider_config,
    build_economic_calendar_provider_result,
    build_economic_calendar_query,
    economic_calendar_event_to_news_record,
    economic_calendar_events_to_news_records,
    economic_calendar_result_to_news_provider_result,
    filter_economic_calendar_events,
    infer_impact_from_importance,
    infer_sentiment_from_surprise,
    normalize_economic_calendar_category,
    normalize_economic_calendar_importance,
    validate_economic_calendar_categories,
    validate_economic_calendar_events,
    validate_number_like,
    validate_string_list,
)


def sample_events():
    return [
        build_economic_calendar_event(
            event_id="event-001",
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
            previous_value=3.1,
            source="test",
            provider_id="calendar",
            description="US inflation came above forecast.",
            relevance_score=0.95,
        ),
        build_economic_calendar_event(
            event_id="event-002",
            timestamp="2026-01-02T18:00:00+00:00",
            title="FOMC Minutes",
            country="US",
            currency="USD",
            category="central_bank",
            importance="critical",
            impact="critical",
            sentiment="mixed",
            source="test",
            provider_id="calendar",
            description="Fed minutes released.",
            relevance_score=0.9,
        ),
        build_economic_calendar_event(
            event_id="event-003",
            timestamp="2026-01-03T08:00:00+00:00",
            title="UK PMI",
            country="GB",
            currency="GBP",
            category="pmi",
            importance="medium",
            impact="medium",
            sentiment="bullish",
            actual_value=52.0,
            forecast_value=50.0,
            source="test",
            provider_id="calendar",
            description="UK PMI improved.",
            relevance_score=0.7,
        ),
    ]


def test_economic_calendar_enum_values():
    assert EconomicCalendarEventCategory.INFLATION.value == "inflation"
    assert EconomicCalendarEventCategory.EMPLOYMENT.value == "employment"
    assert EconomicCalendarEventCategory.INTEREST_RATE.value == "interest_rate"
    assert EconomicCalendarEventCategory.GDP.value == "gdp"
    assert EconomicCalendarEventCategory.PMI.value == "pmi"
    assert EconomicCalendarEventCategory.RETAIL_SALES.value == "retail_sales"
    assert EconomicCalendarEventCategory.CENTRAL_BANK.value == "central_bank"
    assert EconomicCalendarEventCategory.HOUSING.value == "housing"
    assert EconomicCalendarEventCategory.TRADE.value == "trade"
    assert EconomicCalendarEventCategory.ENERGY.value == "energy"
    assert EconomicCalendarEventCategory.UNKNOWN.value == "unknown"

    assert EconomicCalendarImportance.LOW.value == "low"
    assert EconomicCalendarImportance.MEDIUM.value == "medium"
    assert EconomicCalendarImportance.HIGH.value == "high"
    assert EconomicCalendarImportance.CRITICAL.value == "critical"
    assert EconomicCalendarImportance.UNKNOWN.value == "unknown"


def test_economic_calendar_normalizers():
    assert normalize_economic_calendar_category(EconomicCalendarEventCategory.INFLATION) == EconomicCalendarEventCategory.INFLATION
    assert normalize_economic_calendar_category(" PMI ") == EconomicCalendarEventCategory.PMI
    assert normalize_economic_calendar_importance(EconomicCalendarImportance.HIGH) == EconomicCalendarImportance.HIGH
    assert normalize_economic_calendar_importance(" CRITICAL ") == EconomicCalendarImportance.CRITICAL

    with pytest.raises(ValueError):
        normalize_economic_calendar_category("bad")

    with pytest.raises(ValueError):
        normalize_economic_calendar_importance("bad")


def test_economic_calendar_validators():
    assert validate_string_list([" US ", "GB"], "Countries") == [" US ", "GB"]
    assert validate_number_like(1.5, "Value") == 1.5
    assert validate_economic_calendar_categories(["inflation", EconomicCalendarEventCategory.PMI]) == [
        "inflation",
        EconomicCalendarEventCategory.PMI,
    ]

    with pytest.raises(ValueError):
        validate_string_list("bad", "Countries")

    with pytest.raises(ValueError):
        validate_string_list([""], "Countries")

    with pytest.raises(ValueError):
        validate_number_like("1", "Value")

    with pytest.raises(ValueError):
        validate_economic_calendar_categories("bad")

    with pytest.raises(ValueError):
        validate_economic_calendar_categories(["bad"])


def test_economic_calendar_query_to_dict():
    query = EconomicCalendarQuery(
        symbol=" xauusd ",
        countries=[" us "],
        currencies=[" usd "],
        categories=[" inflation "],
        min_importance=" high ",
        start_date="2020-01-01",
        end_date="2020-12-31",
        keywords=[" CPI "],
        metadata={"source": "test"},
    )

    payload = query.to_dict()

    assert query.bounded is True
    assert payload == {
        "symbol": "XAUUSD",
        "countries": ["US"],
        "currencies": ["USD"],
        "categories": ["inflation"],
        "min_importance": "high",
        "start_date": "2020-01-01",
        "end_date": "2020-12-31",
        "bounded": True,
        "keywords": ["cpi"],
        "metadata": {"source": "test"},
    }


def test_economic_calendar_query_builder_and_rejections():
    query = build_economic_calendar_query(
        symbol="XAUUSD",
        countries=["US"],
        currencies=["USD"],
        categories=["inflation"],
    )

    assert isinstance(query, EconomicCalendarQuery)

    with pytest.raises(ValueError):
        EconomicCalendarQuery(symbol=123)

    with pytest.raises(ValueError):
        EconomicCalendarQuery(symbol="bad symbol")

    with pytest.raises(ValueError):
        EconomicCalendarQuery(countries="bad")

    with pytest.raises(ValueError):
        EconomicCalendarQuery(currencies=[""])

    with pytest.raises(ValueError):
        EconomicCalendarQuery(categories=["bad"])

    with pytest.raises(ValueError):
        EconomicCalendarQuery(min_importance="bad")

    with pytest.raises(ValueError):
        EconomicCalendarQuery(start_date=123)

    with pytest.raises(ValueError):
        EconomicCalendarQuery(end_date=123)

    with pytest.raises(ValueError):
        EconomicCalendarQuery(keywords="bad")

    with pytest.raises(ValueError):
        EconomicCalendarQuery(metadata=[])


def test_economic_calendar_event_to_dict():
    event = EconomicCalendarEvent(
        event_id=" event-001 ",
        timestamp=" 2026-01-01T12:30:00+00:00 ",
        title=" US CPI ",
        country=" us ",
        currency=" usd ",
        category=" inflation ",
        importance=" high ",
        impact=" high ",
        sentiment=" bearish ",
        actual_value=3.4,
        forecast_value=3.2,
        previous_value=3.1,
        unit=" % ",
        source=" test ",
        provider_id=" calendar ",
        url=" https://example.com ",
        description=" Hot CPI ",
        relevance_score=0.95,
        raw_payload={"id": 1},
        metadata={"source": "test"},
    )

    payload = event.to_dict()

    assert event.has_actual_forecast is True
    assert event.calculated_surprise == 0.2
    assert event.high_importance is True
    assert payload["event_id"] == "event-001"
    assert payload["country"] == "US"
    assert payload["currency"] == "USD"
    assert payload["category"] == "inflation"
    assert payload["importance"] == "high"
    assert payload["impact"] == "high"
    assert payload["sentiment"] == "bearish"
    assert payload["surprise"] == 0.2
    assert payload["unit"] == "%"


def test_economic_calendar_event_builder_and_rejections():
    event = build_economic_calendar_event(
        event_id="event",
        timestamp="2026-01-01",
        title="CPI",
    )

    assert isinstance(event, EconomicCalendarEvent)

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="", timestamp="t", title="Title")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="", title="Title")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", country=123)

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", currency=123)

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", category="bad")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", importance="bad")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", impact="bad")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", sentiment="bad")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", actual_value="bad")

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", relevance_score=2)

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", raw_payload=[])

    with pytest.raises(ValueError):
        EconomicCalendarEvent(event_id="id", timestamp="t", title="Title", metadata=[])


def test_economic_calendar_provider_config():
    config = build_economic_calendar_provider_config(
        provider_id="calendar",
        name="Calendar Provider",
        base_url="https://example.com",
        status="active",
    )

    assert isinstance(config, NewsProviderConfig)
    assert config.provider_type.value == "economic_calendar"
    assert config.active is True
    assert config.has_capability("economic_calendar") is True
    assert config.has_capability("macro_events") is True


def test_economic_calendar_provider_result_to_dict():
    query = build_economic_calendar_query(countries=["US"])
    result = EconomicCalendarProviderResult(
        success=True,
        events=sample_events(),
        query=query,
        message=" OK ",
        provider_id=" calendar ",
        metadata={"source": "test"},
    )

    payload = result.to_dict()

    assert result.failed is False
    assert result.event_count == 3
    assert result.high_importance_count == 2
    assert payload["success"] is True
    assert payload["event_count"] == 3
    assert payload["high_importance_count"] == 2
    assert payload["query"]["countries"] == ["US"]


def test_economic_calendar_provider_result_builder_and_rejections():
    result = build_economic_calendar_provider_result(
        success=True,
        events=sample_events(),
        provider_id="calendar",
    )

    assert isinstance(result, EconomicCalendarProviderResult)

    with pytest.raises(ValueError):
        EconomicCalendarProviderResult(success="yes")

    with pytest.raises(ValueError):
        EconomicCalendarProviderResult(success=True, events="bad")

    with pytest.raises(ValueError):
        EconomicCalendarProviderResult(success=True, events=["bad"])

    with pytest.raises(ValueError):
        EconomicCalendarProviderResult(success=True, query="bad")

    with pytest.raises(ValueError):
        EconomicCalendarProviderResult(success=True, message=123)

    with pytest.raises(ValueError):
        EconomicCalendarProviderResult(success=True, provider_id=123)

    with pytest.raises(ValueError):
        EconomicCalendarProviderResult(success=True, metadata=[])

    assert validate_economic_calendar_events(sample_events()) == sample_events()


def test_infer_impact_and_sentiment():
    assert infer_impact_from_importance("low").value == "low"
    assert infer_impact_from_importance("medium").value == "medium"
    assert infer_impact_from_importance("high").value == "high"
    assert infer_impact_from_importance("critical").value == "critical"

    assert infer_sentiment_from_surprise(0.5).value == "bullish"
    assert infer_sentiment_from_surprise(-0.5).value == "bearish"
    assert infer_sentiment_from_surprise(0.0).value == "neutral"
    assert infer_sentiment_from_surprise(None).value == "unknown"
    assert infer_sentiment_from_surprise(0.5, positive_surprise_is_bullish=False).value == "bearish"


def test_economic_calendar_event_to_news_record():
    event = sample_events()[0]
    record = economic_calendar_event_to_news_record(
        event,
        symbol="XAUUSD",
    )

    assert isinstance(record, NewsEventRecord)
    assert record.event_id == "event-001"
    assert record.event_type.value == "economic_calendar"
    assert record.symbol == "XAUUSD"
    assert record.impact.value == "high"
    assert record.sentiment.value == "bearish"
    assert record.raw_payload["category"] == "inflation"
    assert record.metadata["importance"] == "high"

    with pytest.raises(ValueError):
        economic_calendar_event_to_news_record("bad")


def test_economic_calendar_events_to_news_records_and_provider_result():
    events = sample_events()
    records = economic_calendar_events_to_news_records(
        events,
        symbol="XAUUSD",
    )
    calendar_result = build_economic_calendar_provider_result(
        success=True,
        events=events,
        message="OK",
        provider_id="calendar",
    )
    news_result = economic_calendar_result_to_news_provider_result(
        calendar_result,
        symbol="XAUUSD",
    )

    assert len(records) == 3
    assert isinstance(news_result, NewsProviderResult)
    assert news_result.success is True
    assert news_result.record_count == 3
    assert news_result.records[0].symbol == "XAUUSD"

    with pytest.raises(ValueError):
        economic_calendar_events_to_news_records(["bad"])

    with pytest.raises(ValueError):
        economic_calendar_result_to_news_provider_result("bad")


def test_filter_economic_calendar_events():
    events = sample_events()
    query = build_economic_calendar_query(
        countries=["US"],
        currencies=["USD"],
        categories=["inflation"],
        min_importance="high",
        keywords=["cpi"],
    )

    filtered = filter_economic_calendar_events(
        events,
        query=query,
    )

    assert len(filtered) == 1
    assert filtered[0].event_id == "event-001"

    high_query = build_economic_calendar_query(
        min_importance="critical",
    )
    critical = filter_economic_calendar_events(
        events,
        query=high_query,
    )

    assert len(critical) == 1
    assert critical[0].event_id == "event-002"

    with pytest.raises(ValueError):
        filter_economic_calendar_events(["bad"], query=query)

    with pytest.raises(ValueError):
        filter_economic_calendar_events(events, query="bad")


def test_news_providers_economic_calendar_exports_exist():
    import aqos.news_providers as news_providers

    expected_exports = [
        "EconomicCalendarEvent",
        "EconomicCalendarEventCategory",
        "EconomicCalendarImportance",
        "EconomicCalendarProviderResult",
        "EconomicCalendarQuery",
        "build_economic_calendar_event",
        "build_economic_calendar_provider_config",
        "build_economic_calendar_provider_result",
        "build_economic_calendar_query",
        "economic_calendar_event_to_news_record",
        "economic_calendar_events_to_news_records",
        "economic_calendar_result_to_news_provider_result",
        "filter_economic_calendar_events",
        "infer_impact_from_importance",
        "infer_sentiment_from_surprise",
        "normalize_economic_calendar_category",
        "normalize_economic_calendar_importance",
        "validate_economic_calendar_categories",
        "validate_economic_calendar_events",
        "validate_number_like",
        "validate_string_list",
    ]

    for export_name in expected_exports:
        assert hasattr(news_providers, export_name), export_name