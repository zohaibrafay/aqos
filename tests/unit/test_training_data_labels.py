"""
Unit tests for AQOS training label generation engine.
"""

import pytest

from aqos.training_data import (
    LabelGenerationConfig,
    LabeledTrainingDataset,
    TrainingDirectionLabel,
    TrainingFeatureDataset,
    TrainingLabelDataset,
    TrainingLabelRow,
    TrainingRiskLabel,
    build_label_generation_config,
    build_labeled_training_dataset,
    build_training_data_config,
    build_training_feature_dataset,
    build_training_feature_row,
    build_training_label_row,
    generate_direction_label,
    generate_event_impact_label,
    generate_future_return_label,
    generate_label_dataset,
    generate_label_row_for_feature_row,
    generate_risk_label,
    generate_tp_sl_label,
    generate_volatility_label,
    join_features_and_labels,
    validate_training_feature_rows_for_labels,
    validate_training_label_rows,
)


def sample_feature_rows():
    return [
        build_training_feature_row(
            timestamp="2020-01-01T10:00:00+00:00",
            symbol="XAUUSD",
            features={
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 100,
                "volume": 1000,
                "aligned_event_count": 1,
                "aligned_high_impact_event_count": 1,
            },
        ),
        build_training_feature_row(
            timestamp="2020-01-01T11:00:00+00:00",
            symbol="XAUUSD",
            features={
                "open": 100,
                "high": 104,
                "low": 100,
                "close": 102,
                "volume": 1100,
                "aligned_event_count": 0,
                "aligned_high_impact_event_count": 0,
            },
        ),
        build_training_feature_row(
            timestamp="2020-01-01T12:00:00+00:00",
            symbol="XAUUSD",
            features={
                "open": 102,
                "high": 103,
                "low": 98,
                "close": 99,
                "volume": 1200,
                "aligned_event_count": 0,
                "aligned_high_impact_event_count": 0,
            },
        ),
        build_training_feature_row(
            timestamp="2020-01-01T13:00:00+00:00",
            symbol="XAUUSD",
            features={
                "open": 99,
                "high": 100,
                "low": 97,
                "close": 98,
                "volume": 1300,
                "aligned_event_count": 0,
                "aligned_high_impact_event_count": 0,
            },
        ),
    ]


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


def test_label_enums():
    assert TrainingDirectionLabel.UP.value == "up"
    assert TrainingDirectionLabel.DOWN.value == "down"
    assert TrainingDirectionLabel.FLAT.value == "flat"

    assert TrainingRiskLabel.LOW.value == "low"
    assert TrainingRiskLabel.MEDIUM.value == "medium"
    assert TrainingRiskLabel.HIGH.value == "high"


def test_label_generation_config_to_dict():
    config = LabelGenerationConfig(
        horizon=2,
        direction_threshold=0.01,
        tp_pct=0.02,
        sl_pct=0.01,
        volatility_window=2,
        high_volatility_threshold=0.03,
        medium_volatility_threshold=0.01,
        label_targets=["future_return", "direction"],
        metadata={"source": "test"},
    )

    payload = config.to_dict()

    assert payload["horizon"] == 2
    assert payload["direction_threshold"] == 0.01
    assert payload["tp_pct"] == 0.02
    assert payload["sl_pct"] == 0.01
    assert payload["volatility_window"] == 2
    assert payload["label_targets"] == ["future_return", "direction"]
    assert payload["metadata"] == {"source": "test"}


def test_label_generation_config_builder_and_rejections():
    config = build_label_generation_config(
        horizon=1,
        label_targets=["direction"],
    )

    assert isinstance(config, LabelGenerationConfig)
    assert config.resolved_label_targets[0].value == "direction"

    with pytest.raises(ValueError):
        LabelGenerationConfig(horizon=0)

    with pytest.raises(ValueError):
        LabelGenerationConfig(direction_threshold=-1)

    with pytest.raises(ValueError):
        LabelGenerationConfig(tp_pct=-1)

    with pytest.raises(ValueError):
        LabelGenerationConfig(sl_pct=-1)

    with pytest.raises(ValueError):
        LabelGenerationConfig(volatility_window=0)

    with pytest.raises(ValueError):
        LabelGenerationConfig(label_targets="bad")

    with pytest.raises(ValueError):
        LabelGenerationConfig(label_targets=["bad"])

    with pytest.raises(ValueError):
        LabelGenerationConfig(metadata=[])


def test_training_label_row_to_dict_and_flatten():
    row = TrainingLabelRow(
        timestamp=" 2020-01-01 ",
        symbol=" xauusd ",
        labels={
            "label_direction": "up",
        },
        metadata={"source": "test"},
    )

    payload = row.to_dict()
    flat = row.flatten()

    assert row.label_count == 1
    assert payload["timestamp"] == "2020-01-01"
    assert payload["symbol"] == "XAUUSD"
    assert payload["label_count"] == 1
    assert flat["label_direction"] == "up"


def test_training_label_row_builder_and_rejections():
    row = build_training_label_row(
        timestamp="2020-01-01",
        symbol="XAUUSD",
        labels={"label_direction": "up"},
    )

    assert isinstance(row, TrainingLabelRow)

    with pytest.raises(ValueError):
        TrainingLabelRow(timestamp="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TrainingLabelRow(timestamp="t", symbol="bad symbol")

    with pytest.raises(ValueError):
        TrainingLabelRow(timestamp="t", symbol="XAUUSD", labels=[])

    with pytest.raises(ValueError):
        TrainingLabelRow(timestamp="t", symbol="XAUUSD", metadata=[])


def test_future_return_and_direction_labels():
    rows = sample_feature_rows()

    assert generate_future_return_label(rows, index=0, horizon=1) == 0.02
    assert generate_future_return_label(rows, index=1, horizon=1) == -0.0294117647
    assert generate_future_return_label(rows, index=3, horizon=1) is None

    assert generate_direction_label(0.02, threshold=0.01) == "up"
    assert generate_direction_label(-0.02, threshold=0.01) == "down"
    assert generate_direction_label(0.005, threshold=0.01) == "flat"
    assert generate_direction_label(None) is None

    with pytest.raises(ValueError):
        generate_future_return_label(rows, index=-1, horizon=1)


def test_tp_sl_label():
    rows = sample_feature_rows()

    assert generate_tp_sl_label(
        rows,
        index=0,
        horizon=1,
        tp_pct=0.02,
        sl_pct=0.01,
    ) == 1
    assert generate_tp_sl_label(
        rows,
        index=1,
        horizon=1,
        tp_pct=0.02,
        sl_pct=0.01,
    ) == 0
    assert generate_tp_sl_label(
        rows,
        index=3,
        horizon=1,
        tp_pct=0.02,
        sl_pct=0.01,
    ) is None

    with pytest.raises(ValueError):
        generate_tp_sl_label(rows, index=-1, horizon=1, tp_pct=0.02, sl_pct=0.01)


def test_volatility_event_impact_and_risk_labels():
    rows = sample_feature_rows()

    assert generate_volatility_label(
        rows,
        index=0,
        window=2,
        high_threshold=0.03,
        medium_threshold=0.01,
    ) == "high"
    assert generate_event_impact_label(rows[0]) == "high"
    assert generate_event_impact_label(rows[1]) == "low"
    assert generate_risk_label(rows[0], "low") == "high"
    assert generate_risk_label(rows[1], "medium") == "medium"
    assert generate_risk_label(rows[1], "low") == "low"
    assert generate_risk_label(rows[1], None) is None

    with pytest.raises(ValueError):
        generate_event_impact_label("bad")

    with pytest.raises(ValueError):
        generate_risk_label("bad", "low")


def test_generate_label_row_for_feature_row():
    rows = sample_feature_rows()
    config = build_label_generation_config(
        horizon=1,
        volatility_window=1,
    )

    label_row = generate_label_row_for_feature_row(
        rows,
        index=0,
        config=config,
    )

    assert isinstance(label_row, TrainingLabelRow)
    assert label_row.timestamp == rows[0].timestamp
    assert label_row.labels["label_future_return"] == 0.02
    assert label_row.labels["label_direction"] == "up"
    assert label_row.labels["label_hit_tp_before_sl"] == 1
    assert label_row.labels["label_event_impact"] == "high"
    assert label_row.labels["label_risk_level"] == "high"

    with pytest.raises(ValueError):
        generate_label_row_for_feature_row(rows, index=0, config="bad")


def test_training_label_dataset_to_dict_and_rejections():
    rows = [
        build_training_label_row(
            timestamp="2020-01-01",
            symbol="XAUUSD",
            labels={"label_direction": "up"},
        )
    ]
    config = build_label_generation_config()
    dataset = TrainingLabelDataset(
        dataset_id="labels",
        symbol="XAUUSD",
        rows=rows,
        config=config,
        source_dataset_id="features",
    )

    payload = dataset.to_dict()

    assert dataset.dataset_id == "labels"
    assert dataset.symbol == "XAUUSD"
    assert dataset.row_count == 1
    assert dataset.label_count == 1
    assert dataset.empty is False
    assert payload["source_dataset_id"] == "features"

    with pytest.raises(ValueError):
        TrainingLabelDataset(dataset_id="", symbol="XAUUSD")

    with pytest.raises(ValueError):
        TrainingLabelDataset(dataset_id="labels", symbol="bad symbol")

    with pytest.raises(ValueError):
        TrainingLabelDataset(dataset_id="labels", symbol="XAUUSD", rows=["bad"])

    with pytest.raises(ValueError):
        TrainingLabelDataset(dataset_id="labels", symbol="XAUUSD", config="bad")

    with pytest.raises(ValueError):
        TrainingLabelDataset(dataset_id="labels", symbol="XAUUSD", source_dataset_id=123)

    with pytest.raises(ValueError):
        TrainingLabelDataset(dataset_id="labels", symbol="XAUUSD", metadata=[])

    assert validate_training_label_rows(rows) == rows


def test_generate_label_dataset():
    feature_dataset = sample_feature_dataset()
    config = build_label_generation_config(
        horizon=1,
        volatility_window=1,
    )
    label_dataset = generate_label_dataset(
        feature_dataset,
        config=config,
    )

    assert isinstance(label_dataset, TrainingLabelDataset)
    assert label_dataset.dataset_id == "xauusd-features-labels"
    assert label_dataset.symbol == "XAUUSD"
    assert label_dataset.source_dataset_id == "xauusd-features"
    assert label_dataset.row_count == 4
    assert label_dataset.rows[0].labels["label_direction"] == "up"

    with pytest.raises(ValueError):
        generate_label_dataset("bad")

    with pytest.raises(ValueError):
        generate_label_dataset(feature_dataset, config="bad")


def test_labeled_training_dataset_join():
    feature_dataset = sample_feature_dataset()
    label_dataset = generate_label_dataset(
        feature_dataset,
        config=build_label_generation_config(
            horizon=1,
            volatility_window=1,
        ),
    )

    labeled = join_features_and_labels(feature_dataset, label_dataset)
    built = build_labeled_training_dataset(
        feature_dataset,
        config=build_label_generation_config(
            horizon=1,
            volatility_window=1,
        ),
    )

    assert isinstance(labeled, LabeledTrainingDataset)
    assert labeled.dataset_id == "xauusd-features-labeled"
    assert labeled.symbol == "XAUUSD"
    assert labeled.row_count == 4
    assert "close" in labeled.to_flat_rows()[0]
    assert "label_direction" in labeled.to_flat_rows()[0]

    assert isinstance(built, LabeledTrainingDataset)

    with pytest.raises(ValueError):
        LabeledTrainingDataset(feature_dataset="bad", label_dataset=label_dataset)

    with pytest.raises(ValueError):
        LabeledTrainingDataset(feature_dataset=feature_dataset, label_dataset="bad")

    with pytest.raises(ValueError):
        LabeledTrainingDataset(feature_dataset=feature_dataset, label_dataset=label_dataset, metadata=[])


def test_validate_training_feature_rows_for_labels():
    rows = sample_feature_rows()

    assert validate_training_feature_rows_for_labels(rows) == rows

    with pytest.raises(ValueError):
        validate_training_feature_rows_for_labels("bad")

    with pytest.raises(ValueError):
        validate_training_feature_rows_for_labels(["bad"])

    with pytest.raises(ValueError):
        validate_training_feature_rows_for_labels(
            [
                build_training_feature_row(
                    timestamp="2020-01-01",
                    symbol="XAUUSD",
                    features={"close": 100},
                )
            ]
        )


def test_training_data_label_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "LabelGenerationConfig",
        "LabeledTrainingDataset",
        "TrainingDirectionLabel",
        "TrainingLabelDataset",
        "TrainingLabelRow",
        "TrainingRiskLabel",
        "build_label_generation_config",
        "build_labeled_training_dataset",
        "build_training_label_row",
        "generate_direction_label",
        "generate_event_impact_label",
        "generate_future_return_label",
        "generate_label_dataset",
        "generate_label_row_for_feature_row",
        "generate_risk_label",
        "generate_tp_sl_label",
        "generate_volatility_label",
        "join_features_and_labels",
        "validate_training_feature_rows_for_labels",
        "validate_training_label_rows",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name