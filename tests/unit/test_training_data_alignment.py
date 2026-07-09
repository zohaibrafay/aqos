"""
Unit tests for AQOS news-to-candle alignment engine.
"""

import pytest

from aqos.training_data import (
    AlignedEvent,
    CandleEventAlignmentDataset,
    CandleEventAlignmentRow,
    EventAlignmentConfig,
    EventAlignmentMode,
    aggregate_aligned_event_features,
    align_event_dataset_to_ohlcv_dataset,
    align_events_to_candle,
    aligned_row_to_training_features,
    alignment_dataset_to_training_rows,
    build_aligned_event,
    build_event_alignment_config,
    build_historical_event_row,
    build_historical_ohlcv_row,
    event_is_within_alignment_window,
    minutes_between_timestamps,
    normalize_event_alignment_mode,
    parse_alignment_timestamp,
    raw_rows_to_historical_event_dataset,
    raw_rows_to_historical_ohlcv_dataset,
    validate_aligned_events,
    validate_candle_event_alignment_rows,
)


def sample_ohlcv_dataset():
    return raw_rows_to_historical_ohlcv_dataset(
        dataset_id="xauusd-h1",
        symbol="XAUUSD",
        rows=[
            {
                "timestamp": "2020-01-01T10:00:00+00:00",
                "open": 1500,
                "high": 1510,
                "low": 1495,
                "close": 1505,
                "volume": 100,
            },
            {
                "timestamp": "2020-01-01T11:00:00+00:00",
                "open": 1505,
                "high": 1520,
                "low": 1500,
                "close": 1515,
                "volume": 150,
            },
            {
                "timestamp": "2020-01-01T12:00:00+00:00",
                "open": 1515,
                "high": 1518,
                "low": 1508,
                "close": 1510,
                "volume": 120,
            },
        ],
        asset_type="commodity",
        timeframe="1h",
        source="test",
    )


def sample_event_dataset():
    return raw_rows_to_historical_event_dataset(
        dataset_id="xauusd-events",
        symbol="XAUUSD",
        rows=[
            {
                "event_id": "event-001",
                "timestamp": "2020-01-01T09:30:00+00:00",
                "event_type": "economic_calendar",
                "title": "US CPI",
                "symbol": "XAUUSD",
                "impact": "high",
                "sentiment": "bearish",
                "surprise": 0.2,
                "relevance_score": 0.95,
            },
            {
                "event_id": "event-002",
                "timestamp": "2020-01-01T10:30:00+00:00",
                "event_type": "news",
                "title": "Gold risk flow",
                "symbol": "XAUUSD",
                "impact": "medium",
                "sentiment": "bullish",
                "relevance_score": 0.7,
            },
            {
                "event_id": "event-003",
                "timestamp": "2020-01-01T11:50:00+00:00",
                "event_type": "central_bank",
                "title": "Fed speech",
                "symbol": "XAUUSD",
                "impact": "critical",
                "sentiment": "mixed",
                "relevance_score": 0.9,
            },
        ],
        source="test",
    )


def test_event_alignment_mode_values_and_normalizer():
    assert EventAlignmentMode.BEFORE_OR_AT.value == "before_or_at"
    assert EventAlignmentMode.AFTER_OR_AT.value == "after_or_at"
    assert EventAlignmentMode.NEAREST.value == "nearest"
    assert EventAlignmentMode.WINDOW.value == "window"

    assert normalize_event_alignment_mode(EventAlignmentMode.WINDOW) == EventAlignmentMode.WINDOW
    assert normalize_event_alignment_mode(" BEFORE_OR_AT ".lower()) == EventAlignmentMode.BEFORE_OR_AT
    assert normalize_event_alignment_mode(" window ") == EventAlignmentMode.WINDOW

    with pytest.raises(ValueError):
        normalize_event_alignment_mode("bad")


def test_parse_alignment_timestamp_and_minutes_between():
    dt = parse_alignment_timestamp("2020-01-01T10:00:00+00:00")

    assert dt.year == 2020
    assert minutes_between_timestamps(
        "2020-01-01T10:00:00+00:00",
        "2020-01-01T10:30:00+00:00",
    ) == 30
    assert minutes_between_timestamps(
        "2020-01-01T10:00:00+00:00",
        "2020-01-01T09:30:00+00:00",
    ) == -30

    with pytest.raises(ValueError):
        parse_alignment_timestamp("")


def test_event_alignment_config_to_dict_and_impact_filter():
    config = EventAlignmentConfig(
        mode=" window ",
        lookback_minutes=120,
        lookahead_minutes=60,
        max_events_per_candle=3,
        include_low_impact=False,
        metadata={"source": "test"},
    )

    payload = config.to_dict()

    assert payload["mode"] == "window"
    assert payload["lookback_minutes"] == 120
    assert payload["lookahead_minutes"] == 60
    assert payload["max_events_per_candle"] == 3
    assert payload["include_low_impact"] is False
    assert config.impact_allowed("low") is False
    assert config.impact_allowed("medium") is True
    assert config.impact_allowed("high") is True


def test_event_alignment_config_builder_and_rejections():
    config = build_event_alignment_config(
        mode="nearest",
        lookback_minutes=60,
        lookahead_minutes=60,
    )

    assert isinstance(config, EventAlignmentConfig)
    assert config.mode == "nearest"

    with pytest.raises(ValueError):
        EventAlignmentConfig(mode="bad")

    with pytest.raises(ValueError):
        EventAlignmentConfig(lookback_minutes=-1)

    with pytest.raises(ValueError):
        EventAlignmentConfig(lookahead_minutes=-1)

    with pytest.raises(ValueError):
        EventAlignmentConfig(max_events_per_candle=0)

    with pytest.raises(ValueError):
        EventAlignmentConfig(include_low_impact="yes")

    with pytest.raises(ValueError):
        EventAlignmentConfig(metadata=[])


def test_event_is_within_alignment_window():
    before_config = build_event_alignment_config(
        mode="before_or_at",
        lookback_minutes=60,
    )
    after_config = build_event_alignment_config(
        mode="after_or_at",
        lookahead_minutes=60,
    )
    window_config = build_event_alignment_config(
        mode="window",
        lookback_minutes=60,
        lookahead_minutes=60,
    )

    assert event_is_within_alignment_window(
        candle_timestamp="2020-01-01T10:00:00+00:00",
        event_timestamp="2020-01-01T09:30:00+00:00",
        config=before_config,
    ) is True
    assert event_is_within_alignment_window(
        candle_timestamp="2020-01-01T10:00:00+00:00",
        event_timestamp="2020-01-01T10:30:00+00:00",
        config=before_config,
    ) is False
    assert event_is_within_alignment_window(
        candle_timestamp="2020-01-01T10:00:00+00:00",
        event_timestamp="2020-01-01T10:30:00+00:00",
        config=after_config,
    ) is True
    assert event_is_within_alignment_window(
        candle_timestamp="2020-01-01T10:00:00+00:00",
        event_timestamp="2020-01-01T10:30:00+00:00",
        config=window_config,
    ) is True

    with pytest.raises(ValueError):
        event_is_within_alignment_window(
            candle_timestamp="2020-01-01T10:00:00+00:00",
            event_timestamp="2020-01-01T10:30:00+00:00",
            config="bad",
        )


def test_aligned_event_to_dict():
    event = build_historical_event_row(
        event_id="event-001",
        timestamp="2020-01-01T09:30:00+00:00",
        event_type="news",
        title="Gold news",
        symbol="XAUUSD",
    )
    aligned = AlignedEvent(
        candle_timestamp="2020-01-01T10:00:00+00:00",
        event=event,
        minutes_from_candle=-30,
        alignment_mode="before_or_at",
        metadata={"source": "test"},
    )

    payload = aligned.to_dict()

    assert aligned.event_id == "event-001"
    assert aligned.event_timestamp == "2020-01-01T09:30:00+00:00"
    assert aligned.before_candle is True
    assert aligned.after_candle is False
    assert payload["event_id"] == "event-001"
    assert payload["minutes_from_candle"] == -30
    assert payload["before_candle"] is True
    assert payload["alignment_mode"] == "before_or_at"


def test_aligned_event_builder_and_rejections():
    event = sample_event_dataset().events[0]
    aligned = build_aligned_event(
        candle_timestamp="2020-01-01T10:00:00+00:00",
        event=event,
        alignment_mode="before_or_at",
    )

    assert isinstance(aligned, AlignedEvent)
    assert aligned.minutes_from_candle == -30

    with pytest.raises(ValueError):
        AlignedEvent(
            candle_timestamp="",
            event=event,
            minutes_from_candle=0,
            alignment_mode="before_or_at",
        )

    with pytest.raises(ValueError):
        AlignedEvent(
            candle_timestamp="2020-01-01T10:00:00+00:00",
            event="bad",
            minutes_from_candle=0,
            alignment_mode="before_or_at",
        )

    with pytest.raises(ValueError):
        AlignedEvent(
            candle_timestamp="2020-01-01T10:00:00+00:00",
            event=event,
            minutes_from_candle=0.5,
            alignment_mode="before_or_at",
        )

    with pytest.raises(ValueError):
        AlignedEvent(
            candle_timestamp="2020-01-01T10:00:00+00:00",
            event=event,
            minutes_from_candle=0,
            alignment_mode="bad",
        )


def test_align_events_to_candle_before_or_at():
    candle = sample_ohlcv_dataset().rows[0]
    events = sample_event_dataset().events
    config = build_event_alignment_config(
        mode="before_or_at",
        lookback_minutes=60,
        max_events_per_candle=5,
    )

    row = align_events_to_candle(
        candle=candle,
        events=events,
        config=config,
    )

    assert isinstance(row, CandleEventAlignmentRow)
    assert row.timestamp == "2020-01-01T10:00:00+00:00"
    assert row.event_count == 1
    assert row.has_events is True
    assert row.aligned_events[0].event_id == "event-001"
    assert row.aligned_events[0].minutes_from_candle == -30


def test_align_events_to_candle_window_and_limit():
    candle = sample_ohlcv_dataset().rows[0]
    events = sample_event_dataset().events
    config = build_event_alignment_config(
        mode="window",
        lookback_minutes=60,
        lookahead_minutes=60,
        max_events_per_candle=1,
    )

    row = align_events_to_candle(
        candle=candle,
        events=events,
        config=config,
    )

    assert row.event_count == 1
    assert row.aligned_events[0].event_id in {"event-001", "event-002"}


def test_align_events_to_candle_filters_impact():
    candle = sample_ohlcv_dataset().rows[0]
    events = sample_event_dataset().events
    config = build_event_alignment_config(
        mode="window",
        lookback_minutes=60,
        lookahead_minutes=60,
        include_medium_impact=False,
    )

    row = align_events_to_candle(
        candle=candle,
        events=events,
        config=config,
    )

    event_ids = [event.event_id for event in row.aligned_events]

    assert "event-001" in event_ids
    assert "event-002" not in event_ids


def test_align_events_to_candle_rejections():
    candle = sample_ohlcv_dataset().rows[0]
    events = sample_event_dataset().events

    with pytest.raises(ValueError):
        align_events_to_candle(candle="bad", events=events)

    with pytest.raises(ValueError):
        align_events_to_candle(candle=candle, events="bad")

    with pytest.raises(ValueError):
        align_events_to_candle(candle=candle, events=["bad"])

    with pytest.raises(ValueError):
        align_events_to_candle(candle=candle, events=events, config="bad")


def test_candle_event_alignment_row_to_dict():
    candle = sample_ohlcv_dataset().rows[0]
    event = sample_event_dataset().events[0]
    aligned = build_aligned_event(
        candle_timestamp=candle.timestamp,
        event=event,
        alignment_mode="before_or_at",
    )
    row = CandleEventAlignmentRow(
        candle=candle,
        aligned_events=[aligned],
    )

    payload = row.to_dict()

    assert row.timestamp == candle.timestamp
    assert row.event_count == 1
    assert row.has_events is True
    assert row.high_impact_event_count == 1
    assert payload["event_count"] == 1
    assert payload["high_impact_event_count"] == 1

    with pytest.raises(ValueError):
        CandleEventAlignmentRow(candle="bad")

    with pytest.raises(ValueError):
        CandleEventAlignmentRow(candle=candle, aligned_events="bad")

    assert validate_aligned_events([aligned]) == [aligned]


def test_align_event_dataset_to_ohlcv_dataset():
    ohlcv = sample_ohlcv_dataset()
    events = sample_event_dataset()
    config = build_event_alignment_config(
        mode="window",
        lookback_minutes=60,
        lookahead_minutes=60,
    )

    dataset = align_event_dataset_to_ohlcv_dataset(
        ohlcv_dataset=ohlcv,
        event_dataset=events,
        config=config,
        dataset_id="aligned",
    )

    assert isinstance(dataset, CandleEventAlignmentDataset)
    assert dataset.dataset_id == "aligned"
    assert dataset.symbol == "XAUUSD"
    assert dataset.row_count == 3
    assert dataset.event_count >= 3
    assert dataset.candles_with_events >= 2
    assert dataset.metadata["ohlcv_dataset_id"] == "xauusd-h1"
    assert dataset.metadata["event_dataset_id"] == "xauusd-events"

    with pytest.raises(ValueError):
        align_event_dataset_to_ohlcv_dataset(
            ohlcv_dataset="bad",
            event_dataset=events,
        )

    with pytest.raises(ValueError):
        align_event_dataset_to_ohlcv_dataset(
            ohlcv_dataset=ohlcv,
            event_dataset="bad",
        )

    with pytest.raises(ValueError):
        align_event_dataset_to_ohlcv_dataset(
            ohlcv_dataset=ohlcv,
            event_dataset=events,
            config="bad",
        )


def test_candle_event_alignment_dataset_to_dict_and_rejections():
    dataset = align_event_dataset_to_ohlcv_dataset(
        ohlcv_dataset=sample_ohlcv_dataset(),
        event_dataset=sample_event_dataset(),
        config=build_event_alignment_config(mode="window", lookback_minutes=60, lookahead_minutes=60),
    )

    payload = dataset.to_dict()

    assert payload["dataset_id"] == "xauusd-h1-aligned-events"
    assert payload["symbol"] == "XAUUSD"
    assert payload["row_count"] == 3
    assert payload["config"]["mode"] == "window"

    with pytest.raises(ValueError):
        CandleEventAlignmentDataset(dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        CandleEventAlignmentDataset(dataset_id="dataset", symbol="")

    with pytest.raises(ValueError):
        CandleEventAlignmentDataset(dataset_id="dataset", symbol="XAUUSD", rows=["bad"])

    with pytest.raises(ValueError):
        CandleEventAlignmentDataset(dataset_id="dataset", symbol="XAUUSD", config="bad")

    assert validate_candle_event_alignment_rows(dataset.rows) == dataset.rows


def test_aggregate_aligned_event_features():
    candle = sample_ohlcv_dataset().rows[0]
    events = sample_event_dataset().events[:2]
    aligned = [
        build_aligned_event(
            candle_timestamp=candle.timestamp,
            event=event,
            alignment_mode="window",
        )
        for event in events
    ]

    features = aggregate_aligned_event_features(aligned)

    assert features["aligned_event_count"] == 2
    assert features["aligned_high_impact_event_count"] == 1
    assert features["aligned_directional_event_count"] == 2
    assert features["aligned_event_impact_score_max"] == 0.75
    assert features["aligned_event_sentiment_score_sum"] == 0.0
    assert features["aligned_event_relevance_score_max"] == 0.95
    assert features["aligned_event_surprise_sum"] == 0.2
    assert features["aligned_event_ids"] == ["event-001", "event-002"]

    with pytest.raises(ValueError):
        aggregate_aligned_event_features(["bad"])


def test_aligned_row_to_training_features_and_dataset_rows():
    alignment_dataset = align_event_dataset_to_ohlcv_dataset(
        ohlcv_dataset=sample_ohlcv_dataset(),
        event_dataset=sample_event_dataset(),
        config=build_event_alignment_config(
            mode="window",
            lookback_minutes=60,
            lookahead_minutes=60,
        ),
    )

    first_row_features = aligned_row_to_training_features(alignment_dataset.rows[0])
    all_rows = alignment_dataset_to_training_rows(alignment_dataset)

    assert first_row_features["timestamp"] == "2020-01-01T10:00:00+00:00"
    assert first_row_features["open"] == 1500
    assert first_row_features["close"] == 1505
    assert "aligned_event_count" in first_row_features
    assert len(all_rows) == 3

    with pytest.raises(ValueError):
        aligned_row_to_training_features("bad")

    with pytest.raises(ValueError):
        alignment_dataset_to_training_rows("bad")


def test_training_data_alignment_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "AlignedEvent",
        "CandleEventAlignmentDataset",
        "CandleEventAlignmentRow",
        "EventAlignmentConfig",
        "EventAlignmentMode",
        "aggregate_aligned_event_features",
        "align_event_dataset_to_ohlcv_dataset",
        "align_events_to_candle",
        "aligned_row_to_training_features",
        "alignment_dataset_to_training_rows",
        "build_aligned_event",
        "build_event_alignment_config",
        "event_is_within_alignment_window",
        "minutes_between_timestamps",
        "normalize_event_alignment_mode",
        "parse_alignment_timestamp",
        "validate_aligned_events",
        "validate_candle_event_alignment_rows",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name