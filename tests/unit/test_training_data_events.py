"""
Unit tests for AQOS historical news/macro event contracts.
"""

import pytest

from aqos.training_data import (
    HistoricalEventDataset,
    HistoricalEventImpact,
    HistoricalEventRow,
    HistoricalEventSentiment,
    HistoricalEventSummary,
    HistoricalEventType,
    TrainingDataConfig,
    TrainingDataStatus,
    build_historical_event_dataset,
    build_historical_event_row,
    build_training_data_config,
    event_dataset_to_feature_rows,
    event_row_to_feature_dict,
    filter_historical_events_by_impact,
    filter_historical_events_by_sentiment,
    normalize_historical_event_impact,
    normalize_historical_event_sentiment,
    normalize_historical_event_type,
    raw_row_to_historical_event_row,
    raw_rows_to_historical_event_dataset,
    raw_rows_to_historical_event_rows,
    summarize_historical_event_dataset,
    validate_historical_event_rows,
    validate_raw_event_rows,
    validate_score,
)


def sample_raw_events():
    return [
        {
            "event_id": "event-001",
            "timestamp": "2020-01-01T12:30:00+00:00",
            "event_type": "economic_calendar",
            "title": "US CPI",
            "symbol": "XAUUSD",
            "impact": "high",
            "sentiment": "bearish",
            "source": "test",
            "description": "Higher than expected CPI.",
            "actual_value": 3.4,
            "forecast_value": 3.2,
            "previous_value": 3.1,
            "surprise": 0.2,
            "relevance_score": 0.95,
        },
        {
            "event_id": "event-002",
            "timestamp": "2020-01-02T18:00:00+00:00",
            "event_type": "central_bank",
            "title": "FOMC Minutes",
            "symbol": "XAUUSD",
            "impact": "critical",
            "sentiment": "mixed",
            "source": "test",
            "description": "Fed signals uncertainty.",
            "relevance_score": 0.85,
        },
        {
            "event_id": "event-003",
            "timestamp": "2020-01-03T08:00:00+00:00",
            "event_type": "news",
            "title": "Risk sentiment improves",
            "symbol": "XAUUSD",
            "impact": "medium",
            "sentiment": "bullish",
            "source": "test",
            "description": "Gold catches safe-haven flow.",
            "relevance_score": 0.75,
        },
    ]


def sample_events():
    return raw_rows_to_historical_event_rows(
        sample_raw_events(),
        symbol="XAUUSD",
    )


def sample_dataset():
    return raw_rows_to_historical_event_dataset(
        dataset_id="xauusd-events",
        symbol="XAUUSD",
        rows=sample_raw_events(),
        source="test",
    )


def test_historical_event_enum_values():
    assert HistoricalEventType.NEWS.value == "news"
    assert HistoricalEventType.ECONOMIC_CALENDAR.value == "economic_calendar"
    assert HistoricalEventType.CENTRAL_BANK.value == "central_bank"
    assert HistoricalEventType.GEOPOLITICAL.value == "geopolitical"
    assert HistoricalEventType.EARNINGS.value == "earnings"
    assert HistoricalEventType.CRYPTO.value == "crypto"
    assert HistoricalEventType.MARKET_STRUCTURE.value == "market_structure"
    assert HistoricalEventType.UNKNOWN.value == "unknown"

    assert HistoricalEventImpact.LOW.value == "low"
    assert HistoricalEventImpact.MEDIUM.value == "medium"
    assert HistoricalEventImpact.HIGH.value == "high"
    assert HistoricalEventImpact.CRITICAL.value == "critical"
    assert HistoricalEventImpact.UNKNOWN.value == "unknown"

    assert HistoricalEventSentiment.BULLISH.value == "bullish"
    assert HistoricalEventSentiment.BEARISH.value == "bearish"
    assert HistoricalEventSentiment.NEUTRAL.value == "neutral"
    assert HistoricalEventSentiment.MIXED.value == "mixed"
    assert HistoricalEventSentiment.UNKNOWN.value == "unknown"


def test_historical_event_normalizers():
    assert normalize_historical_event_type(HistoricalEventType.NEWS) == HistoricalEventType.NEWS
    assert normalize_historical_event_type(" CENTRAL_BANK ") == HistoricalEventType.CENTRAL_BANK
    assert normalize_historical_event_impact(HistoricalEventImpact.HIGH) == HistoricalEventImpact.HIGH
    assert normalize_historical_event_impact(" CRITICAL ") == HistoricalEventImpact.CRITICAL
    assert normalize_historical_event_sentiment(HistoricalEventSentiment.BULLISH) == HistoricalEventSentiment.BULLISH
    assert normalize_historical_event_sentiment(" BEARISH ") == HistoricalEventSentiment.BEARISH

    with pytest.raises(ValueError):
        normalize_historical_event_type("bad")

    with pytest.raises(ValueError):
        normalize_historical_event_impact("bad")

    with pytest.raises(ValueError):
        normalize_historical_event_sentiment("bad")


def test_validate_score():
    assert validate_score(0, "Score") == 0.0
    assert validate_score(0.5, "Score") == 0.5
    assert validate_score(1, "Score") == 1.0

    with pytest.raises(ValueError):
        validate_score(-0.1, "Score")

    with pytest.raises(ValueError):
        validate_score(1.1, "Score")

    with pytest.raises(ValueError):
        validate_score("1", "Score")


def test_historical_event_row_to_dict():
    event = HistoricalEventRow(
        event_id=" event-001 ",
        timestamp=" 2020-01-01T12:30:00+00:00 ",
        event_type=" economic_calendar ",
        title=" US CPI ",
        symbol=" xauusd ",
        impact=" high ",
        sentiment=" bearish ",
        source=" test ",
        description=" CPI came hot. ",
        actual_value=3.4,
        forecast_value=3.2,
        previous_value=3.1,
        surprise=0.2,
        relevance_score=0.95,
        metadata={"country": "US"},
    )

    payload = event.to_dict()

    assert event.has_numeric_values is True
    assert event.high_impact is True
    assert event.directional is True
    assert payload["event_id"] == "event-001"
    assert payload["timestamp"] == "2020-01-01T12:30:00+00:00"
    assert payload["event_type"] == "economic_calendar"
    assert payload["title"] == "US CPI"
    assert payload["symbol"] == "XAUUSD"
    assert payload["impact"] == "high"
    assert payload["sentiment"] == "bearish"
    assert payload["source"] == "test"
    assert payload["description"] == "CPI came hot."
    assert payload["actual_value"] == 3.4
    assert payload["forecast_value"] == 3.2
    assert payload["previous_value"] == 3.1
    assert payload["surprise"] == 0.2
    assert payload["relevance_score"] == 0.95
    assert payload["high_impact"] is True
    assert payload["directional"] is True


def test_historical_event_row_rejects_invalid_values():
    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="", timestamp="t", event_type="news", title="Title")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="", event_type="news", title="Title")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="bad", title="Title")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", symbol=123)

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", symbol="bad symbol")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", impact="bad")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", sentiment="bad")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", source=123)

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", description=123)

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", actual_value="bad")

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", relevance_score=2)

    with pytest.raises(ValueError):
        HistoricalEventRow(event_id="id", timestamp="t", event_type="news", title="Title", metadata=[])


def test_build_historical_event_row():
    event = build_historical_event_row(
        event_id="event",
        timestamp="2020-01-01",
        event_type="news",
        title="Gold news",
        symbol="XAUUSD",
        impact="medium",
        sentiment="bullish",
    )

    assert isinstance(event, HistoricalEventRow)
    assert event.symbol == "XAUUSD"
    assert event.directional is True


def test_raw_event_row_converters():
    event = raw_row_to_historical_event_row(
        {
            "event_id": "event",
            "timestamp": "2020-01-01",
            "event_type": "news",
            "title": "Gold news",
            "impact": "medium",
            "sentiment": "bullish",
            "relevance_score": "0.8",
        },
        symbol="XAUUSD",
    )
    events = raw_rows_to_historical_event_rows(sample_raw_events(), symbol="XAUUSD")

    assert isinstance(event, HistoricalEventRow)
    assert event.symbol == "XAUUSD"
    assert event.relevance_score == 0.8
    assert len(events) == 3
    assert events[0].event_id == "event-001"

    with pytest.raises(ValueError):
        raw_row_to_historical_event_row([])

    with pytest.raises(KeyError):
        raw_row_to_historical_event_row({"timestamp": "t"})

    with pytest.raises(ValueError):
        raw_rows_to_historical_event_rows("bad")

    with pytest.raises(ValueError):
        raw_rows_to_historical_event_rows(["bad"])


def test_historical_event_dataset_to_dict_and_health():
    dataset = sample_dataset()
    payload = dataset.to_dict()
    health = dataset.health()

    assert isinstance(dataset.config, TrainingDataConfig)
    assert dataset.dataset_id == "xauusd-events"
    assert dataset.symbol == "XAUUSD"
    assert dataset.event_count == 3
    assert dataset.empty is False
    assert dataset.high_impact_count == 2
    assert dataset.directional_count == 2
    assert dataset.first_timestamp == "2020-01-01T12:30:00+00:00"
    assert dataset.last_timestamp == "2020-01-03T08:00:00+00:00"
    assert health.status == TrainingDataStatus.READY
    assert health.event_count == 3
    assert payload["dataset_id"] == "xauusd-events"
    assert payload["event_count"] == 3
    assert payload["health"]["status"] == "ready"


def test_empty_historical_event_dataset_health():
    dataset = build_historical_event_dataset(
        dataset_id="empty-events",
        symbol="EURUSD",
    )

    assert dataset.empty is True
    assert dataset.health().status == TrainingDataStatus.EMPTY
    assert dataset.first_timestamp == ""
    assert dataset.last_timestamp == ""


def test_historical_event_dataset_rejects_invalid_values():
    config = build_training_data_config(
        dataset_id="dataset",
        symbol="XAUUSD",
    )
    event = sample_events()[0]

    with pytest.raises(ValueError):
        HistoricalEventDataset(config="bad")

    with pytest.raises(ValueError):
        HistoricalEventDataset(config=config, events="bad")

    with pytest.raises(ValueError):
        HistoricalEventDataset(config=config, events=["bad"])

    with pytest.raises(ValueError):
        HistoricalEventDataset(config=config, source=123)

    with pytest.raises(ValueError):
        HistoricalEventDataset(config=config, metadata=[])

    assert validate_historical_event_rows([event]) == [event]


def test_raw_rows_to_historical_event_dataset():
    dataset = raw_rows_to_historical_event_dataset(
        dataset_id="xauusd-events",
        symbol="XAUUSD",
        rows=sample_raw_events(),
        source="csv",
    )

    assert isinstance(dataset, HistoricalEventDataset)
    assert dataset.event_count == 3
    assert dataset.source == "csv"


def test_historical_event_summary():
    dataset = sample_dataset()
    summary = summarize_historical_event_dataset(dataset)
    payload = summary.to_dict()

    assert isinstance(summary, HistoricalEventSummary)
    assert summary.has_events is True
    assert summary.dataset_id == "xauusd-events"
    assert summary.symbol == "XAUUSD"
    assert summary.event_count == 3
    assert summary.high_impact_count == 2
    assert summary.directional_count == 2
    assert summary.bullish_count == 1
    assert summary.bearish_count == 1
    assert summary.neutral_count == 0
    assert payload["has_events"] is True

    with pytest.raises(ValueError):
        summarize_historical_event_dataset("bad")


def test_historical_event_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        HistoricalEventSummary(dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        HistoricalEventSummary(dataset_id="dataset", symbol="bad symbol")

    with pytest.raises(ValueError):
        HistoricalEventSummary(dataset_id="dataset", symbol="XAUUSD", event_count=-1)

    with pytest.raises(ValueError):
        HistoricalEventSummary(dataset_id="dataset", symbol="XAUUSD", high_impact_count=-1)

    with pytest.raises(ValueError):
        HistoricalEventSummary(dataset_id="dataset", symbol="XAUUSD", metadata=[])


def test_filter_historical_events_by_impact():
    dataset = sample_dataset()
    high = filter_historical_events_by_impact(dataset, impact="high")
    critical = filter_historical_events_by_impact(dataset, impact=HistoricalEventImpact.CRITICAL)

    assert isinstance(high, HistoricalEventDataset)
    assert high.event_count == 1
    assert high.events[0].event_id == "event-001"
    assert high.metadata["filtered_by_impact"] == "high"

    assert critical.event_count == 1
    assert critical.events[0].event_id == "event-002"

    with pytest.raises(ValueError):
        filter_historical_events_by_impact("bad", impact="high")

    with pytest.raises(ValueError):
        filter_historical_events_by_impact(dataset, impact="bad")


def test_filter_historical_events_by_sentiment():
    dataset = sample_dataset()
    bullish = filter_historical_events_by_sentiment(dataset, sentiment="bullish")
    mixed = filter_historical_events_by_sentiment(dataset, sentiment=HistoricalEventSentiment.MIXED)

    assert isinstance(bullish, HistoricalEventDataset)
    assert bullish.event_count == 1
    assert bullish.events[0].event_id == "event-003"
    assert bullish.metadata["filtered_by_sentiment"] == "bullish"

    assert mixed.event_count == 1
    assert mixed.events[0].event_id == "event-002"

    with pytest.raises(ValueError):
        filter_historical_events_by_sentiment("bad", sentiment="bullish")

    with pytest.raises(ValueError):
        filter_historical_events_by_sentiment(dataset, sentiment="bad")


def test_event_row_to_feature_dict():
    event = sample_events()[0]
    features = event_row_to_feature_dict(event)

    assert features["event_id"] == "event-001"
    assert features["event_type"] == "economic_calendar"
    assert features["event_impact"] == "high"
    assert features["event_sentiment"] == "bearish"
    assert features["event_impact_score"] == 0.75
    assert features["event_sentiment_score"] == -1.0
    assert features["event_relevance_score"] == 0.95
    assert features["event_has_numeric_values"] == 1
    assert features["event_high_impact"] == 1
    assert features["event_directional"] == 1
    assert features["event_surprise"] == 0.2

    with pytest.raises(ValueError):
        event_row_to_feature_dict("bad")


def test_event_dataset_to_feature_rows():
    features = event_dataset_to_feature_rows(sample_dataset())

    assert len(features) == 3
    assert features[0]["event_id"] == "event-001"
    assert features[1]["event_impact_score"] == 1.0
    assert features[2]["event_sentiment_score"] == 1.0

    with pytest.raises(ValueError):
        event_dataset_to_feature_rows("bad")


def test_raw_event_row_validators():
    rows = sample_raw_events()

    assert validate_raw_event_rows(rows) == rows

    with pytest.raises(ValueError):
        validate_raw_event_rows("bad")

    with pytest.raises(ValueError):
        validate_raw_event_rows(["bad"])


def test_training_data_event_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "HistoricalEventDataset",
        "HistoricalEventImpact",
        "HistoricalEventRow",
        "HistoricalEventSentiment",
        "HistoricalEventSummary",
        "HistoricalEventType",
        "build_historical_event_dataset",
        "build_historical_event_row",
        "event_dataset_to_feature_rows",
        "event_row_to_feature_dict",
        "filter_historical_events_by_impact",
        "filter_historical_events_by_sentiment",
        "normalize_historical_event_impact",
        "normalize_historical_event_sentiment",
        "normalize_historical_event_type",
        "raw_row_to_historical_event_row",
        "raw_rows_to_historical_event_dataset",
        "raw_rows_to_historical_event_rows",
        "summarize_historical_event_dataset",
        "validate_historical_event_rows",
        "validate_raw_event_rows",
        "validate_score",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name