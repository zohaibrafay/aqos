"""
Unit tests for AQOS feature + event training dataset builder.
"""

import pytest

from aqos.training_data import (
    TrainingDataConfig,
    TrainingFeatureColumn,
    TrainingFeatureDataset,
    TrainingFeatureDatasetSummary,
    TrainingFeatureRow,
    TrainingFeatureSource,
    align_event_dataset_to_ohlcv_dataset,
    build_event_alignment_config,
    build_feature_dataset_from_alignment,
    build_feature_dataset_from_ohlcv,
    build_training_data_config,
    build_training_feature_column,
    build_training_feature_dataset,
    build_training_feature_row,
    feature_dict_to_training_feature_row,
    feature_dicts_to_training_feature_rows,
    filter_training_feature_dataset_columns,
    infer_feature_columns_from_rows,
    infer_feature_dtype,
    infer_feature_source_from_name,
    merge_feature_rows,
    normalize_training_feature_source,
    raw_rows_to_historical_event_dataset,
    raw_rows_to_historical_ohlcv_dataset,
    summarize_training_feature_dataset,
    validate_training_feature_columns,
    validate_training_feature_rows,
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
        ],
        source="test",
    )


def sample_alignment_dataset():
    return align_event_dataset_to_ohlcv_dataset(
        ohlcv_dataset=sample_ohlcv_dataset(),
        event_dataset=sample_event_dataset(),
        config=build_event_alignment_config(
            mode="window",
            lookback_minutes=60,
            lookahead_minutes=60,
        ),
    )


def sample_config():
    return build_training_data_config(
        dataset_id="xauusd-features",
        symbol="XAUUSD",
        asset_type="commodity",
        timeframe="1h",
    )


def test_training_feature_source_values_and_normalizer():
    assert TrainingFeatureSource.OHLCV.value == "ohlcv"
    assert TrainingFeatureSource.EVENTS.value == "events"
    assert TrainingFeatureSource.ALIGNED.value == "aligned"
    assert TrainingFeatureSource.TECHNICAL.value == "technical"
    assert TrainingFeatureSource.CUSTOM.value == "custom"

    assert normalize_training_feature_source(TrainingFeatureSource.OHLCV) == TrainingFeatureSource.OHLCV
    assert normalize_training_feature_source(" EVENTS ") == TrainingFeatureSource.EVENTS

    with pytest.raises(ValueError):
        normalize_training_feature_source("bad")


def test_training_feature_column_to_dict():
    column = TrainingFeatureColumn(
        name=" close ",
        source=" ohlcv ",
        dtype=" float ",
        description=" Close price ",
        required=True,
        metadata={"unit": "price"},
    )

    payload = column.to_dict()

    assert payload == {
        "name": "close",
        "source": "ohlcv",
        "dtype": "float",
        "description": "Close price",
        "required": True,
        "metadata": {"unit": "price"},
    }


def test_training_feature_column_builder_and_rejections():
    column = build_training_feature_column(
        name="rsi_14",
        source="technical",
        dtype="float",
    )

    assert isinstance(column, TrainingFeatureColumn)

    with pytest.raises(ValueError):
        TrainingFeatureColumn(name="", source="ohlcv")

    with pytest.raises(ValueError):
        TrainingFeatureColumn(name="close", source="bad")

    with pytest.raises(ValueError):
        TrainingFeatureColumn(name="close", source="ohlcv", dtype="")

    with pytest.raises(ValueError):
        TrainingFeatureColumn(name="close", source="ohlcv", description=123)

    with pytest.raises(ValueError):
        TrainingFeatureColumn(name="close", source="ohlcv", required="yes")

    with pytest.raises(ValueError):
        TrainingFeatureColumn(name="close", source="ohlcv", metadata=[])


def test_training_feature_row_to_dict_and_flatten():
    row = TrainingFeatureRow(
        timestamp=" 2020-01-01T10:00:00+00:00 ",
        symbol=" xauusd ",
        features={
            "close": 1505,
            "aligned_event_count": 1,
        },
        metadata={"source": "test"},
    )

    payload = row.to_dict()
    flat = row.flatten()

    assert row.feature_count == 2
    assert payload["timestamp"] == "2020-01-01T10:00:00+00:00"
    assert payload["symbol"] == "XAUUSD"
    assert payload["feature_count"] == 2
    assert flat["timestamp"] == "2020-01-01T10:00:00+00:00"
    assert flat["symbol"] == "XAUUSD"
    assert flat["close"] == 1505


def test_training_feature_row_builder_and_rejections():
    row = build_training_feature_row(
        timestamp="2020-01-01",
        symbol="XAUUSD",
        features={"close": 1505},
    )

    assert isinstance(row, TrainingFeatureRow)

    with pytest.raises(ValueError):
        TrainingFeatureRow(timestamp="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TrainingFeatureRow(timestamp="t", symbol="bad symbol")

    with pytest.raises(ValueError):
        TrainingFeatureRow(timestamp="t", symbol="XAUUSD", features=[])

    with pytest.raises(ValueError):
        TrainingFeatureRow(timestamp="t", symbol="XAUUSD", metadata=[])


def test_infer_feature_dtype_and_source():
    assert infer_feature_dtype(True) == "bool"
    assert infer_feature_dtype(1) == "int"
    assert infer_feature_dtype(1.5) == "float"
    assert infer_feature_dtype([]) == "list"
    assert infer_feature_dtype({}) == "dict"
    assert infer_feature_dtype("x") == "string"

    assert infer_feature_source_from_name("close") == TrainingFeatureSource.OHLCV
    assert infer_feature_source_from_name("aligned_event_count") == TrainingFeatureSource.EVENTS
    assert infer_feature_source_from_name("event_impact_score") == TrainingFeatureSource.EVENTS
    assert infer_feature_source_from_name("rsi_14") == TrainingFeatureSource.TECHNICAL
    assert infer_feature_source_from_name("custom_x") == TrainingFeatureSource.CUSTOM

    with pytest.raises(ValueError):
        infer_feature_source_from_name("")


def test_feature_dict_converters():
    row = feature_dict_to_training_feature_row(
        {
            "timestamp": "2020-01-01",
            "symbol": "XAUUSD",
            "close": 1505,
            "volume": 100,
        },
        symbol="XAUUSD",
    )
    rows = feature_dicts_to_training_feature_rows(
        [
            {
                "timestamp": "2020-01-01",
                "close": 1505,
            },
            {
                "timestamp": "2020-01-02",
                "close": 1510,
            },
        ],
        symbol="XAUUSD",
    )

    assert isinstance(row, TrainingFeatureRow)
    assert row.timestamp == "2020-01-01"
    assert row.symbol == "XAUUSD"
    assert row.features == {"close": 1505, "volume": 100}
    assert len(rows) == 2

    with pytest.raises(ValueError):
        feature_dict_to_training_feature_row([], symbol="XAUUSD")

    with pytest.raises(KeyError):
        feature_dict_to_training_feature_row({"close": 1505}, symbol="XAUUSD")

    with pytest.raises(ValueError):
        feature_dicts_to_training_feature_rows("bad", symbol="XAUUSD")


def test_infer_feature_columns_from_rows():
    rows = [
        build_training_feature_row(
            timestamp="2020-01-01",
            symbol="XAUUSD",
            features={
                "close": 1505.0,
                "aligned_event_count": 1,
                "rsi_14": 55.0,
                "custom_note": "ok",
            },
        )
    ]

    columns = infer_feature_columns_from_rows(rows)

    names = [column.name for column in columns]
    sources = {column.name: column.source for column in columns}

    assert names == ["close", "aligned_event_count", "rsi_14", "custom_note"]
    assert sources["close"] == TrainingFeatureSource.OHLCV
    assert sources["aligned_event_count"] == TrainingFeatureSource.EVENTS
    assert sources["rsi_14"] == TrainingFeatureSource.TECHNICAL
    assert sources["custom_note"] == TrainingFeatureSource.CUSTOM

    with pytest.raises(ValueError):
        infer_feature_columns_from_rows(["bad"])


def test_training_feature_dataset_to_dict_and_health():
    rows = [
        build_training_feature_row(
            timestamp="2020-01-01",
            symbol="XAUUSD",
            features={"close": 1505, "volume": 100},
        )
    ]
    dataset = TrainingFeatureDataset(
        config=sample_config(),
        rows=rows,
        source="test",
    )

    payload = dataset.to_dict()
    health = dataset.health()

    assert dataset.dataset_id == "xauusd-features"
    assert dataset.symbol == "XAUUSD"
    assert dataset.row_count == 1
    assert dataset.column_count == 2
    assert dataset.empty is False
    assert dataset.first_timestamp == "2020-01-01"
    assert health.status.value == "ready"
    assert health.row_count == 1
    assert health.feature_count == 2
    assert payload["row_count"] == 1
    assert payload["flat_rows"][0]["close"] == 1505


def test_training_feature_dataset_builder_and_rejections():
    row = build_training_feature_row(
        timestamp="2020-01-01",
        symbol="XAUUSD",
        features={"close": 1505},
    )
    column = build_training_feature_column(
        name="close",
        source="ohlcv",
    )
    dataset = build_training_feature_dataset(
        config=sample_config(),
        rows=[row],
        columns=[column],
        source="manual",
    )

    assert isinstance(dataset, TrainingFeatureDataset)
    assert dataset.column_count == 1

    with pytest.raises(ValueError):
        TrainingFeatureDataset(config="bad")

    with pytest.raises(ValueError):
        TrainingFeatureDataset(config=sample_config(), rows=["bad"])

    with pytest.raises(ValueError):
        TrainingFeatureDataset(config=sample_config(), columns=["bad"])

    with pytest.raises(ValueError):
        TrainingFeatureDataset(config=sample_config(), source=123)

    with pytest.raises(ValueError):
        TrainingFeatureDataset(config=sample_config(), metadata=[])

    assert validate_training_feature_rows([row]) == [row]
    assert validate_training_feature_columns([column]) == [column]


def test_empty_training_feature_dataset_health():
    dataset = build_training_feature_dataset(
        config=sample_config(),
    )

    assert dataset.empty is True
    assert dataset.health().status == TrainingDataStatus.EMPTY if False else dataset.health().status.value == "empty"


def test_build_feature_dataset_from_ohlcv():
    dataset = build_feature_dataset_from_ohlcv(sample_ohlcv_dataset())

    assert isinstance(dataset, TrainingFeatureDataset)
    assert dataset.row_count == 2
    assert dataset.source == "ohlcv"
    assert dataset.metadata["ohlcv_dataset_id"] == "xauusd-h1"
    assert "close" in dataset.rows[0].features
    assert "body_size" in dataset.rows[0].features

    with pytest.raises(ValueError):
        build_feature_dataset_from_ohlcv("bad")


def test_build_feature_dataset_from_alignment():
    alignment = sample_alignment_dataset()
    dataset = build_feature_dataset_from_alignment(
        alignment,
        config=sample_config(),
    )

    assert isinstance(dataset, TrainingFeatureDataset)
    assert dataset.row_count == 2
    assert dataset.source == "aligned"
    assert dataset.metadata["alignment_dataset_id"] == "xauusd-h1-aligned-events"
    assert "aligned_event_count" in dataset.rows[0].features
    assert dataset.rows[0].features["aligned_event_count"] >= 1

    with pytest.raises(ValueError):
        build_feature_dataset_from_alignment("bad", config=sample_config())

    with pytest.raises(ValueError):
        build_feature_dataset_from_alignment(alignment, config="bad")


def test_summarize_training_feature_dataset():
    dataset = build_feature_dataset_from_alignment(
        sample_alignment_dataset(),
        config=sample_config(),
    )
    summary = summarize_training_feature_dataset(dataset)
    payload = summary.to_dict()

    assert isinstance(summary, TrainingFeatureDatasetSummary)
    assert summary.dataset_id == "xauusd-features"
    assert summary.symbol == "XAUUSD"
    assert summary.row_count == 2
    assert summary.column_count == dataset.column_count
    assert summary.event_enriched_row_count >= 1
    assert summary.event_enriched_ratio > 0
    assert payload["has_rows"] is True

    with pytest.raises(ValueError):
        summarize_training_feature_dataset("bad")


def test_training_feature_dataset_summary_rejections():
    with pytest.raises(ValueError):
        TrainingFeatureDatasetSummary(dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TrainingFeatureDatasetSummary(dataset_id="dataset", symbol="bad symbol")

    with pytest.raises(ValueError):
        TrainingFeatureDatasetSummary(dataset_id="dataset", symbol="XAUUSD", row_count=-1)

    with pytest.raises(ValueError):
        TrainingFeatureDatasetSummary(dataset_id="dataset", symbol="XAUUSD", column_count=-1)

    with pytest.raises(ValueError):
        TrainingFeatureDatasetSummary(dataset_id="dataset", symbol="XAUUSD", event_enriched_row_count=-1)

    with pytest.raises(ValueError):
        TrainingFeatureDatasetSummary(dataset_id="dataset", symbol="XAUUSD", metadata=[])


def test_merge_feature_rows():
    base = build_training_feature_row(
        timestamp="2020-01-01",
        symbol="XAUUSD",
        features={"close": 1505},
    )
    extra = build_training_feature_row(
        timestamp="2020-01-01",
        symbol="xauusd",
        features={"sentiment": -1},
    )

    merged = merge_feature_rows(base, extra, prefix="event_")

    assert merged.features == {
        "close": 1505,
        "event_sentiment": -1,
    }
    assert merged.metadata["merged"] is True

    with pytest.raises(ValueError):
        merge_feature_rows("bad", extra)

    with pytest.raises(ValueError):
        merge_feature_rows(base, "bad")

    with pytest.raises(ValueError):
        merge_feature_rows(
            base,
            build_training_feature_row(
                timestamp="2020-01-02",
                symbol="XAUUSD",
                features={},
            ),
        )

    with pytest.raises(ValueError):
        merge_feature_rows(
            base,
            build_training_feature_row(
                timestamp="2020-01-01",
                symbol="EURUSD",
                features={},
            ),
        )


def test_filter_training_feature_dataset_columns():
    dataset = build_feature_dataset_from_alignment(
        sample_alignment_dataset(),
        config=sample_config(),
    )
    filtered = filter_training_feature_dataset_columns(
        dataset,
        include_columns=["close", "aligned_event_count"],
    )

    assert isinstance(filtered, TrainingFeatureDataset)
    assert filtered.row_count == dataset.row_count
    assert filtered.metadata["filtered_columns"] == ["aligned_event_count", "close"]
    assert set(filtered.rows[0].features.keys()).issubset({"close", "aligned_event_count"})
    assert set(column.name for column in filtered.columns).issubset({"close", "aligned_event_count"})

    with pytest.raises(ValueError):
        filter_training_feature_dataset_columns("bad", include_columns=["close"])

    with pytest.raises(ValueError):
        filter_training_feature_dataset_columns(dataset, include_columns="close")

    with pytest.raises(ValueError):
        filter_training_feature_dataset_columns(dataset, include_columns=[""])


def test_training_data_dataset_builder_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "TrainingFeatureColumn",
        "TrainingFeatureDataset",
        "TrainingFeatureDatasetSummary",
        "TrainingFeatureRow",
        "TrainingFeatureSource",
        "build_feature_dataset_from_alignment",
        "build_feature_dataset_from_ohlcv",
        "build_training_feature_column",
        "build_training_feature_dataset",
        "build_training_feature_row",
        "feature_dict_to_training_feature_row",
        "feature_dicts_to_training_feature_rows",
        "filter_training_feature_dataset_columns",
        "infer_feature_columns_from_rows",
        "infer_feature_dtype",
        "infer_feature_source_from_name",
        "merge_feature_rows",
        "normalize_training_feature_source",
        "summarize_training_feature_dataset",
        "validate_training_feature_columns",
        "validate_training_feature_rows",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name