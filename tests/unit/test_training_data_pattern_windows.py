"""
Unit tests for AQOS pattern window builder.
"""

import pytest

from aqos.training_data import (
    PatternWindowConfig,
    PatternWindowDataset,
    PatternWindowMode,
    PatternWindowRow,
    PatternWindowSummary,
    build_label_generation_config,
    build_labeled_training_dataset,
    build_pattern_window_config,
    build_pattern_window_row,
    build_pattern_windows_from_feature_dataset,
    build_pattern_windows_from_feature_rows,
    build_pattern_windows_from_labeled_dataset,
    build_training_data_config,
    build_training_feature_dataset,
    build_training_feature_row,
    calculate_pattern_window_ranges,
    feature_rows_to_pattern_rows,
    normalize_pattern_window_mode,
    pattern_window_dataset_to_label_rows,
    pattern_window_dataset_to_model_matrix,
    summarize_pattern_window_dataset,
    validate_pattern_window_rows,
    validate_raw_pattern_rows,
)


def sample_feature_rows():
    rows = []

    for index, close in enumerate([100, 101, 102, 101, 103, 104]):
        rows.append(
            build_training_feature_row(
                timestamp=f"2020-01-01T{10 + index:02d}:00:00+00:00",
                symbol="XAUUSD",
                features={
                    "open": close - 1,
                    "high": close + 1,
                    "low": close - 2,
                    "close": close,
                    "volume": 1000 + index,
                    "aligned_event_count": 1 if index == 1 else 0,
                    "aligned_high_impact_event_count": 1 if index == 1 else 0,
                },
            )
        )

    return rows


def sample_feature_dataset():
    return build_training_feature_dataset(
        config=build_training_data_config(
            dataset_id="xauusd-features",
            symbol="XAUUSD",
            asset_type="commodity",
            timeframe="1h",
        ),
        rows=sample_feature_rows(),
        source="test",
    )


def sample_labeled_dataset():
    return build_labeled_training_dataset(
        sample_feature_dataset(),
        config=build_label_generation_config(
            horizon=1,
            volatility_window=1,
        ),
    )


def test_pattern_window_mode_values_and_normalizer():
    assert PatternWindowMode.ROLLING.value == "rolling"
    assert PatternWindowMode.ANCHORED.value == "anchored"
    assert PatternWindowMode.EXPANDING.value == "expanding"

    assert normalize_pattern_window_mode(PatternWindowMode.ROLLING) == PatternWindowMode.ROLLING
    assert normalize_pattern_window_mode(" ANCHORED ") == PatternWindowMode.ANCHORED

    with pytest.raises(ValueError):
        normalize_pattern_window_mode("bad")


def test_pattern_window_config_to_dict():
    config = PatternWindowConfig(
        window_size=3,
        step_size=2,
        mode=" rolling ",
        include_labels=True,
        flatten_features=True,
        metadata={"source": "test"},
    )

    payload = config.to_dict()

    assert payload == {
        "window_size": 3,
        "step_size": 2,
        "mode": "rolling",
        "include_labels": True,
        "flatten_features": True,
        "metadata": {"source": "test"},
    }


def test_pattern_window_config_builder_and_rejections():
    config = build_pattern_window_config(
        window_size=4,
        step_size=2,
        mode="expanding",
    )

    assert isinstance(config, PatternWindowConfig)
    assert config.window_size == 4
    assert config.mode == "expanding"

    with pytest.raises(ValueError):
        PatternWindowConfig(window_size=0)

    with pytest.raises(ValueError):
        PatternWindowConfig(step_size=0)

    with pytest.raises(ValueError):
        PatternWindowConfig(mode="bad")

    with pytest.raises(ValueError):
        PatternWindowConfig(include_labels="yes")

    with pytest.raises(ValueError):
        PatternWindowConfig(flatten_features="yes")

    with pytest.raises(ValueError):
        PatternWindowConfig(metadata=[])


def test_pattern_window_row_to_dict_and_flatten():
    row = PatternWindowRow(
        window_id=" window-001 ",
        symbol=" xauusd ",
        start_timestamp=" 2020-01-01T10:00:00+00:00 ",
        end_timestamp=" 2020-01-01T12:00:00+00:00 ",
        rows=[
            {
                "timestamp": "2020-01-01T10:00:00+00:00",
                "symbol": "XAUUSD",
                "close": 100,
            },
            {
                "timestamp": "2020-01-01T11:00:00+00:00",
                "symbol": "XAUUSD",
                "close": 101,
            },
        ],
        label={
            "label_direction": "up",
        },
        metadata={"source": "test"},
    )

    payload = row.to_dict()
    flat = row.flatten()

    assert row.row_count == 2
    assert row.has_label is True
    assert payload["window_id"] == "window-001"
    assert payload["symbol"] == "XAUUSD"
    assert payload["row_count"] == 2
    assert payload["has_label"] is True
    assert flat["t0_close"] == 100
    assert flat["t1_close"] == 101
    assert flat["label_direction"] == "up"


def test_pattern_window_row_builder_and_rejections():
    row = build_pattern_window_row(
        window_id="window",
        symbol="XAUUSD",
        start_timestamp="2020-01-01",
        end_timestamp="2020-01-02",
        rows=[{"close": 100}],
    )

    assert isinstance(row, PatternWindowRow)

    with pytest.raises(ValueError):
        PatternWindowRow(window_id="", symbol="XAUUSD", start_timestamp="s", end_timestamp="e")

    with pytest.raises(ValueError):
        PatternWindowRow(window_id="w", symbol="bad symbol", start_timestamp="s", end_timestamp="e")

    with pytest.raises(ValueError):
        PatternWindowRow(window_id="w", symbol="XAUUSD", start_timestamp="", end_timestamp="e")

    with pytest.raises(ValueError):
        PatternWindowRow(window_id="w", symbol="XAUUSD", start_timestamp="s", end_timestamp="")

    with pytest.raises(ValueError):
        PatternWindowRow(window_id="w", symbol="XAUUSD", start_timestamp="s", end_timestamp="e", rows=["bad"])

    with pytest.raises(ValueError):
        PatternWindowRow(window_id="w", symbol="XAUUSD", start_timestamp="s", end_timestamp="e", label=[])

    with pytest.raises(ValueError):
        PatternWindowRow(window_id="w", symbol="XAUUSD", start_timestamp="s", end_timestamp="e", metadata=[])


def test_feature_rows_to_pattern_rows():
    pattern_rows = feature_rows_to_pattern_rows(sample_feature_rows())

    assert len(pattern_rows) == 6
    assert pattern_rows[0]["symbol"] == "XAUUSD"
    assert pattern_rows[0]["close"] == 100

    with pytest.raises(ValueError):
        feature_rows_to_pattern_rows("bad")

    with pytest.raises(ValueError):
        feature_rows_to_pattern_rows(["bad"])


def test_calculate_pattern_window_ranges():
    config = build_pattern_window_config(window_size=3, step_size=1, mode="rolling")
    anchored_config = build_pattern_window_config(window_size=3, step_size=2, mode="anchored")
    expanding_config = build_pattern_window_config(window_size=3, step_size=2, mode="expanding")

    assert calculate_pattern_window_ranges(row_count=6, config=config) == [
        (0, 3),
        (1, 4),
        (2, 5),
        (3, 6),
    ]
    assert calculate_pattern_window_ranges(row_count=6, config=anchored_config) == [
        (0, 3),
        (0, 5),
    ]
    assert calculate_pattern_window_ranges(row_count=6, config=expanding_config) == [
        (0, 3),
        (0, 5),
    ]
    assert calculate_pattern_window_ranges(row_count=2, config=config) == []

    with pytest.raises(ValueError):
        calculate_pattern_window_ranges(row_count=-1, config=config)

    with pytest.raises(ValueError):
        calculate_pattern_window_ranges(row_count=6, config="bad")


def test_build_pattern_windows_from_feature_rows():
    dataset = build_pattern_windows_from_feature_rows(
        dataset_id="patterns",
        symbol="XAUUSD",
        rows=sample_feature_rows(),
        config=build_pattern_window_config(window_size=3, step_size=1),
        source_dataset_id="features",
    )

    assert isinstance(dataset, PatternWindowDataset)
    assert dataset.dataset_id == "patterns"
    assert dataset.symbol == "XAUUSD"
    assert dataset.window_count == 4
    assert dataset.windows[0].window_id == "patterns-window-000000"
    assert dataset.windows[0].row_count == 3
    assert dataset.windows[0].start_timestamp == "2020-01-01T10:00:00+00:00"
    assert dataset.windows[0].end_timestamp == "2020-01-01T12:00:00+00:00"
    assert dataset.source_dataset_id == "features"

    with pytest.raises(ValueError):
        build_pattern_windows_from_feature_rows(
            dataset_id="patterns",
            symbol="XAUUSD",
            rows=sample_feature_rows(),
            config="bad",
        )


def test_build_pattern_windows_from_feature_dataset():
    dataset = build_pattern_windows_from_feature_dataset(
        sample_feature_dataset(),
        config=build_pattern_window_config(window_size=3, step_size=2),
    )

    assert isinstance(dataset, PatternWindowDataset)
    assert dataset.dataset_id == "xauusd-features-patterns"
    assert dataset.symbol == "XAUUSD"
    assert dataset.window_count == 2
    assert dataset.source_dataset_id == "xauusd-features"

    with pytest.raises(ValueError):
        build_pattern_windows_from_feature_dataset("bad")


def test_build_pattern_windows_from_labeled_dataset():
    labeled = sample_labeled_dataset()
    dataset = build_pattern_windows_from_labeled_dataset(
        labeled,
        config=build_pattern_window_config(
            window_size=3,
            step_size=1,
            include_labels=True,
        ),
    )

    assert isinstance(dataset, PatternWindowDataset)
    assert dataset.dataset_id == "xauusd-features-labeled-patterns"
    assert dataset.symbol == "XAUUSD"
    assert dataset.window_count == 4
    assert dataset.labeled_window_count == 4
    assert "label_direction" in dataset.windows[0].label
    assert "label_direction" not in dataset.windows[0].rows[-1]

    no_labels = build_pattern_windows_from_labeled_dataset(
        labeled,
        config=build_pattern_window_config(
            window_size=3,
            step_size=1,
            include_labels=False,
        ),
    )

    assert no_labels.labeled_window_count == 0

    with pytest.raises(ValueError):
        build_pattern_windows_from_labeled_dataset("bad")


def test_pattern_window_dataset_to_dict_and_rejections():
    dataset = build_pattern_windows_from_feature_dataset(
        sample_feature_dataset(),
        config=build_pattern_window_config(window_size=3, step_size=1),
    )
    payload = dataset.to_dict()

    assert dataset.window_count == 4
    assert dataset.empty is False
    assert dataset.first_timestamp == "2020-01-01T10:00:00+00:00"
    assert dataset.last_timestamp == "2020-01-01T15:00:00+00:00"
    assert payload["window_count"] == 4
    assert payload["config"]["window_size"] == 3

    with pytest.raises(ValueError):
        PatternWindowDataset(dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        PatternWindowDataset(dataset_id="dataset", symbol="bad symbol")

    with pytest.raises(ValueError):
        PatternWindowDataset(dataset_id="dataset", symbol="XAUUSD", windows=["bad"])

    with pytest.raises(ValueError):
        PatternWindowDataset(dataset_id="dataset", symbol="XAUUSD", config="bad")

    with pytest.raises(ValueError):
        PatternWindowDataset(dataset_id="dataset", symbol="XAUUSD", source_dataset_id=123)

    with pytest.raises(ValueError):
        PatternWindowDataset(dataset_id="dataset", symbol="XAUUSD", metadata=[])

    assert validate_pattern_window_rows(dataset.windows) == dataset.windows


def test_summarize_pattern_window_dataset():
    dataset = build_pattern_windows_from_labeled_dataset(
        sample_labeled_dataset(),
        config=build_pattern_window_config(window_size=3, step_size=1),
    )
    summary = summarize_pattern_window_dataset(dataset)
    payload = summary.to_dict()

    assert isinstance(summary, PatternWindowSummary)
    assert summary.dataset_id == "xauusd-features-labeled-patterns"
    assert summary.symbol == "XAUUSD"
    assert summary.window_count == 4
    assert summary.labeled_window_count == 4
    assert summary.labeled_ratio == 1.0
    assert summary.window_size == 3
    assert payload["has_windows"] is True

    with pytest.raises(ValueError):
        summarize_pattern_window_dataset("bad")


def test_pattern_window_summary_rejections():
    with pytest.raises(ValueError):
        PatternWindowSummary(dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        PatternWindowSummary(dataset_id="dataset", symbol="bad symbol")

    with pytest.raises(ValueError):
        PatternWindowSummary(dataset_id="dataset", symbol="XAUUSD", window_count=-1)

    with pytest.raises(ValueError):
        PatternWindowSummary(dataset_id="dataset", symbol="XAUUSD", labeled_window_count=-1)

    with pytest.raises(ValueError):
        PatternWindowSummary(dataset_id="dataset", symbol="XAUUSD", window_size=-1)

    with pytest.raises(ValueError):
        PatternWindowSummary(dataset_id="dataset", symbol="XAUUSD", metadata=[])


def test_pattern_window_dataset_to_model_matrix_and_labels():
    dataset = build_pattern_windows_from_labeled_dataset(
        sample_labeled_dataset(),
        config=build_pattern_window_config(window_size=3, step_size=1),
    )

    matrix = pattern_window_dataset_to_model_matrix(dataset)
    labels = pattern_window_dataset_to_label_rows(dataset)

    assert len(matrix) == 4
    assert len(matrix[0]) == 3
    assert len(labels) == 4
    assert labels[0]["window_id"] == dataset.windows[0].window_id
    assert "label_direction" in labels[0]

    with pytest.raises(ValueError):
        pattern_window_dataset_to_model_matrix("bad")

    with pytest.raises(ValueError):
        pattern_window_dataset_to_label_rows("bad")


def test_pattern_window_validators():
    assert validate_raw_pattern_rows([{"close": 100}]) == [{"close": 100}]

    with pytest.raises(ValueError):
        validate_raw_pattern_rows("bad")

    with pytest.raises(ValueError):
        validate_raw_pattern_rows(["bad"])


def test_training_data_pattern_window_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "PatternWindowConfig",
        "PatternWindowDataset",
        "PatternWindowMode",
        "PatternWindowRow",
        "PatternWindowSummary",
        "build_pattern_window_config",
        "build_pattern_window_row",
        "build_pattern_windows_from_feature_dataset",
        "build_pattern_windows_from_feature_rows",
        "build_pattern_windows_from_labeled_dataset",
        "calculate_pattern_window_ranges",
        "feature_rows_to_pattern_rows",
        "normalize_pattern_window_mode",
        "pattern_window_dataset_to_label_rows",
        "pattern_window_dataset_to_model_matrix",
        "summarize_pattern_window_dataset",
        "validate_pattern_window_rows",
        "validate_raw_pattern_rows",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name