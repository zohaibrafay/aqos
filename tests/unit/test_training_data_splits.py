"""
Unit tests for AQOS walk-forward split builder.
"""

import pytest

from aqos.training_data import (
    DatasetSplitConfig,
    DatasetSplitPlan,
    DatasetSplitRange,
    SplitStrategy,
    WalkForwardFold,
    apply_split_range_to_rows,
    build_dataset_split_config,
    build_dataset_split_plan,
    build_dataset_split_range,
    build_label_generation_config,
    build_labeled_training_dataset,
    build_pattern_window_config,
    build_pattern_windows_from_feature_dataset,
    build_split_plan_from_feature_dataset,
    build_split_plan_from_labeled_dataset,
    build_split_plan_from_pattern_windows,
    build_training_data_config,
    build_training_feature_dataset,
    build_training_feature_row,
    calculate_expanding_window_folds,
    calculate_holdout_split_ranges,
    calculate_walk_forward_folds,
    normalize_split_strategy,
    split_rows_by_plan,
    validate_dataset_split_ranges,
    validate_ratio,
    validate_walk_forward_folds,
)


def sample_feature_rows():
    rows = []

    for index in range(10):
        close = 100 + index
        rows.append(
            build_training_feature_row(
                timestamp=f"2020-01-01T{index:02d}:00:00+00:00",
                symbol="XAUUSD",
                features={
                    "open": close - 1,
                    "high": close + 1,
                    "low": close - 2,
                    "close": close,
                    "volume": 1000 + index,
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


def sample_pattern_dataset():
    return build_pattern_windows_from_feature_dataset(
        sample_feature_dataset(),
        config=build_pattern_window_config(
            window_size=3,
            step_size=1,
        ),
    )


def sample_raw_rows():
    return sample_feature_dataset().to_flat_rows()


def test_split_strategy_values_and_normalizer():
    assert SplitStrategy.HOLDOUT.value == "holdout"
    assert SplitStrategy.WALK_FORWARD.value == "walk_forward"
    assert SplitStrategy.EXPANDING_WINDOW.value == "expanding_window"
    assert SplitStrategy.ROLLING_WINDOW.value == "rolling_window"

    assert normalize_split_strategy(SplitStrategy.HOLDOUT) == SplitStrategy.HOLDOUT
    assert normalize_split_strategy(" WALK_FORWARD ") == SplitStrategy.WALK_FORWARD

    with pytest.raises(ValueError):
        normalize_split_strategy("bad")


def test_validate_ratio():
    assert validate_ratio(0, "Ratio") == 0.0
    assert validate_ratio(0.5, "Ratio") == 0.5
    assert validate_ratio(1, "Ratio") == 1.0

    with pytest.raises(ValueError):
        validate_ratio(-0.1, "Ratio")

    with pytest.raises(ValueError):
        validate_ratio(1.1, "Ratio")

    with pytest.raises(ValueError):
        validate_ratio("1", "Ratio")


def test_dataset_split_config_to_dict():
    config = DatasetSplitConfig(
        strategy=" holdout ",
        train_ratio=0.6,
        validation_ratio=0.2,
        test_ratio=0.2,
        train_window_size=10,
        validation_window_size=2,
        test_window_size=2,
        step_size=2,
        min_train_size=5,
        metadata={"source": "test"},
    )

    payload = config.to_dict()

    assert payload == {
        "strategy": "holdout",
        "train_ratio": 0.6,
        "validation_ratio": 0.2,
        "test_ratio": 0.2,
        "train_window_size": 10,
        "validation_window_size": 2,
        "test_window_size": 2,
        "step_size": 2,
        "min_train_size": 5,
        "metadata": {"source": "test"},
    }


def test_dataset_split_config_builder_and_rejections():
    config = build_dataset_split_config(
        strategy="walk_forward",
        train_window_size=5,
        validation_window_size=2,
        test_window_size=1,
    )

    assert isinstance(config, DatasetSplitConfig)
    assert config.strategy == "walk_forward"

    with pytest.raises(ValueError):
        DatasetSplitConfig(strategy="bad")

    with pytest.raises(ValueError):
        DatasetSplitConfig(train_ratio=1.1)

    with pytest.raises(ValueError):
        DatasetSplitConfig(validation_ratio=-0.1)

    with pytest.raises(ValueError):
        DatasetSplitConfig(train_window_size=-1)

    with pytest.raises(ValueError):
        DatasetSplitConfig(step_size=0)

    with pytest.raises(ValueError):
        DatasetSplitConfig(min_train_size=0)

    with pytest.raises(ValueError):
        DatasetSplitConfig(metadata=[])

    with pytest.raises(ValueError):
        DatasetSplitConfig(train_ratio=0.8, validation_ratio=0.3, test_ratio=0.1)


def test_dataset_split_range_to_dict():
    split_range = DatasetSplitRange(
        split_id=" train ",
        split=" train ",
        start_index=0,
        end_index=7,
        metadata={"source": "test"},
    )

    payload = split_range.to_dict()

    assert split_range.row_count == 7
    assert split_range.empty is False
    assert payload["split_id"] == "train"
    assert payload["split"] == "train"
    assert payload["start_index"] == 0
    assert payload["end_index"] == 7
    assert payload["row_count"] == 7


def test_dataset_split_range_builder_and_rejections():
    split_range = build_dataset_split_range(
        split_id="test",
        split="test",
        start_index=7,
        end_index=10,
    )

    assert isinstance(split_range, DatasetSplitRange)

    with pytest.raises(ValueError):
        DatasetSplitRange(split_id="", split="train", start_index=0, end_index=1)

    with pytest.raises(ValueError):
        DatasetSplitRange(split_id="x", split="bad", start_index=0, end_index=1)

    with pytest.raises(ValueError):
        DatasetSplitRange(split_id="x", split="train", start_index=-1, end_index=1)

    with pytest.raises(ValueError):
        DatasetSplitRange(split_id="x", split="train", start_index=2, end_index=1)

    with pytest.raises(ValueError):
        DatasetSplitRange(split_id="x", split="train", start_index=0, end_index=1, metadata=[])


def test_walk_forward_fold_to_dict_and_rejections():
    train_range = build_dataset_split_range(
        split_id="train",
        split="train",
        start_index=0,
        end_index=5,
    )
    validation_range = build_dataset_split_range(
        split_id="validation",
        split="validation",
        start_index=5,
        end_index=7,
    )
    test_range = build_dataset_split_range(
        split_id="test",
        split="test",
        start_index=7,
        end_index=10,
    )

    fold = WalkForwardFold(
        fold_id=" fold-001 ",
        train_range=train_range,
        validation_range=validation_range,
        test_range=test_range,
        metadata={"source": "test"},
    )

    payload = fold.to_dict()

    assert fold.range_count == 3
    assert payload["fold_id"] == "fold-001"
    assert payload["train_range"]["row_count"] == 5
    assert payload["validation_range"]["row_count"] == 2
    assert payload["test_range"]["row_count"] == 3

    with pytest.raises(ValueError):
        WalkForwardFold(fold_id="", train_range=train_range)

    with pytest.raises(ValueError):
        WalkForwardFold(fold_id="fold", train_range="bad")

    with pytest.raises(ValueError):
        WalkForwardFold(fold_id="fold", train_range=train_range, validation_range="bad")

    with pytest.raises(ValueError):
        WalkForwardFold(fold_id="fold", train_range=train_range, test_range="bad")

    with pytest.raises(ValueError):
        WalkForwardFold(fold_id="fold", train_range=train_range, metadata=[])


def test_calculate_holdout_split_ranges():
    ranges = calculate_holdout_split_ranges(
        dataset_id="dataset",
        row_count=10,
        config=build_dataset_split_config(
            train_ratio=0.6,
            validation_ratio=0.2,
            test_ratio=0.2,
        ),
    )

    assert len(ranges) == 3
    assert ranges[0].split_id == "dataset-train"
    assert ranges[0].start_index == 0
    assert ranges[0].end_index == 6
    assert ranges[1].start_index == 6
    assert ranges[1].end_index == 8
    assert ranges[2].start_index == 8
    assert ranges[2].end_index == 10

    with pytest.raises(ValueError):
        calculate_holdout_split_ranges(dataset_id="", row_count=10, config=build_dataset_split_config())

    with pytest.raises(ValueError):
        calculate_holdout_split_ranges(dataset_id="dataset", row_count=-1, config=build_dataset_split_config())

    with pytest.raises(ValueError):
        calculate_holdout_split_ranges(dataset_id="dataset", row_count=10, config="bad")


def test_calculate_walk_forward_folds():
    folds = calculate_walk_forward_folds(
        dataset_id="dataset",
        row_count=10,
        config=build_dataset_split_config(
            strategy="walk_forward",
            train_window_size=5,
            validation_window_size=2,
            test_window_size=1,
            step_size=1,
        ),
    )

    assert len(folds) == 3
    assert folds[0].train_range.start_index == 0
    assert folds[0].train_range.end_index == 5
    assert folds[0].validation_range.start_index == 5
    assert folds[0].validation_range.end_index == 7
    assert folds[0].test_range.start_index == 7
    assert folds[0].test_range.end_index == 8
    assert folds[1].train_range.start_index == 1

    with pytest.raises(ValueError):
        calculate_walk_forward_folds(dataset_id="", row_count=10, config=build_dataset_split_config())

    with pytest.raises(ValueError):
        calculate_walk_forward_folds(dataset_id="dataset", row_count=-1, config=build_dataset_split_config())

    with pytest.raises(ValueError):
        calculate_walk_forward_folds(dataset_id="dataset", row_count=10, config="bad")


def test_calculate_expanding_window_folds():
    folds = calculate_expanding_window_folds(
        dataset_id="dataset",
        row_count=10,
        config=build_dataset_split_config(
            strategy="expanding_window",
            train_window_size=4,
            validation_window_size=2,
            test_window_size=1,
            step_size=2,
        ),
    )

    assert len(folds) == 2
    assert folds[0].train_range.start_index == 0
    assert folds[0].train_range.end_index == 4
    assert folds[0].validation_range.start_index == 4
    assert folds[0].test_range.start_index == 6
    assert folds[1].train_range.start_index == 0
    assert folds[1].train_range.end_index == 6

    with pytest.raises(ValueError):
        calculate_expanding_window_folds(dataset_id="", row_count=10, config=build_dataset_split_config())

    with pytest.raises(ValueError):
        calculate_expanding_window_folds(dataset_id="dataset", row_count=-1, config=build_dataset_split_config())

    with pytest.raises(ValueError):
        calculate_expanding_window_folds(dataset_id="dataset", row_count=10, config="bad")


def test_build_dataset_split_plan_holdout():
    plan = build_dataset_split_plan(
        dataset_id="dataset",
        symbol="XAUUSD",
        row_count=10,
        config=build_dataset_split_config(
            strategy="holdout",
            train_ratio=0.6,
            validation_ratio=0.2,
            test_ratio=0.2,
        ),
    )

    payload = plan.to_dict()

    assert isinstance(plan, DatasetSplitPlan)
    assert plan.dataset_id == "dataset"
    assert plan.symbol == "XAUUSD"
    assert plan.row_count == 10
    assert plan.strategy == SplitStrategy.HOLDOUT
    assert len(plan.holdout_ranges) == 3
    assert plan.fold_count == 0
    assert plan.range_count == 3
    assert plan.empty is False
    assert payload["strategy"] == "holdout"


def test_build_dataset_split_plan_walk_forward_and_expanding():
    walk_forward = build_dataset_split_plan(
        dataset_id="dataset",
        symbol="XAUUSD",
        row_count=10,
        config=build_dataset_split_config(
            strategy="walk_forward",
            train_window_size=5,
            validation_window_size=2,
            test_window_size=1,
        ),
    )
    expanding = build_dataset_split_plan(
        dataset_id="dataset",
        symbol="XAUUSD",
        row_count=10,
        config=build_dataset_split_config(
            strategy="expanding_window",
            train_window_size=4,
            validation_window_size=2,
            test_window_size=1,
        ),
    )

    assert walk_forward.fold_count == 3
    assert expanding.fold_count >= 1


def test_dataset_split_plan_rejections_and_validators():
    split_range = build_dataset_split_range(
        split_id="train",
        split="train",
        start_index=0,
        end_index=5,
    )
    fold = WalkForwardFold(
        fold_id="fold",
        train_range=split_range,
    )

    with pytest.raises(ValueError):
        DatasetSplitPlan(dataset_id="", symbol="XAUUSD", row_count=10, strategy="holdout")

    with pytest.raises(ValueError):
        DatasetSplitPlan(dataset_id="dataset", symbol="bad symbol", row_count=10, strategy="holdout")

    with pytest.raises(ValueError):
        DatasetSplitPlan(dataset_id="dataset", symbol="XAUUSD", row_count=-1, strategy="holdout")

    with pytest.raises(ValueError):
        DatasetSplitPlan(dataset_id="dataset", symbol="XAUUSD", row_count=10, strategy="bad")

    with pytest.raises(ValueError):
        DatasetSplitPlan(dataset_id="dataset", symbol="XAUUSD", row_count=10, strategy="holdout", holdout_ranges=["bad"])

    with pytest.raises(ValueError):
        DatasetSplitPlan(dataset_id="dataset", symbol="XAUUSD", row_count=10, strategy="holdout", folds=["bad"])

    with pytest.raises(ValueError):
        DatasetSplitPlan(dataset_id="dataset", symbol="XAUUSD", row_count=10, strategy="holdout", metadata=[])

    assert validate_dataset_split_ranges([split_range]) == [split_range]
    assert validate_walk_forward_folds([fold]) == [fold]


def test_build_split_plan_from_datasets():
    feature_dataset = sample_feature_dataset()
    labeled_dataset = sample_labeled_dataset()
    pattern_dataset = sample_pattern_dataset()

    feature_plan = build_split_plan_from_feature_dataset(feature_dataset)
    labeled_plan = build_split_plan_from_labeled_dataset(labeled_dataset)
    pattern_plan = build_split_plan_from_pattern_windows(pattern_dataset)

    assert feature_plan.dataset_id == "xauusd-features"
    assert feature_plan.row_count == feature_dataset.row_count

    assert labeled_plan.dataset_id == "xauusd-features-labeled"
    assert labeled_plan.row_count == labeled_dataset.row_count

    assert pattern_plan.dataset_id == "xauusd-features-patterns"
    assert pattern_plan.row_count == pattern_dataset.window_count

    with pytest.raises(ValueError):
        build_split_plan_from_feature_dataset("bad")

    with pytest.raises(ValueError):
        build_split_plan_from_labeled_dataset("bad")

    with pytest.raises(ValueError):
        build_split_plan_from_pattern_windows("bad")


def test_apply_split_range_to_rows_and_split_rows_by_plan_holdout():
    rows = sample_raw_rows()
    split_range = build_dataset_split_range(
        split_id="first-five",
        split="train",
        start_index=0,
        end_index=5,
    )
    plan = build_dataset_split_plan(
        dataset_id="dataset",
        symbol="XAUUSD",
        row_count=len(rows),
        config=build_dataset_split_config(
            strategy="holdout",
            train_ratio=0.6,
            validation_ratio=0.2,
            test_ratio=0.2,
        ),
    )

    sliced = apply_split_range_to_rows(rows, split_range)
    payload = split_rows_by_plan(rows, plan)

    assert len(sliced) == 5
    assert len(payload["holdout"]["train"]) == 6
    assert len(payload["holdout"]["validation"]) == 2
    assert len(payload["holdout"]["test"]) == 2

    with pytest.raises(ValueError):
        apply_split_range_to_rows("bad", split_range)

    with pytest.raises(ValueError):
        apply_split_range_to_rows(rows, "bad")

    with pytest.raises(ValueError):
        split_rows_by_plan(rows, "bad")

    with pytest.raises(ValueError):
        split_rows_by_plan("bad", plan)


def test_split_rows_by_plan_walk_forward():
    rows = sample_raw_rows()
    plan = build_dataset_split_plan(
        dataset_id="dataset",
        symbol="XAUUSD",
        row_count=len(rows),
        config=build_dataset_split_config(
            strategy="walk_forward",
            train_window_size=5,
            validation_window_size=2,
            test_window_size=1,
        ),
    )

    payload = split_rows_by_plan(rows, plan)

    assert payload["strategy"] == "walk_forward"
    assert len(payload["folds"]) == 3
    assert len(payload["folds"][0]["train"]) == 5
    assert len(payload["folds"][0]["validation"]) == 2
    assert len(payload["folds"][0]["test"]) == 1


def test_training_data_splits_exports_exist():
    import aqos.training_data as training_data

    expected_exports = [
        "DatasetSplitConfig",
        "DatasetSplitPlan",
        "DatasetSplitRange",
        "SplitStrategy",
        "WalkForwardFold",
        "apply_split_range_to_rows",
        "build_dataset_split_config",
        "build_dataset_split_plan",
        "build_dataset_split_range",
        "build_split_plan_from_feature_dataset",
        "build_split_plan_from_labeled_dataset",
        "build_split_plan_from_pattern_windows",
        "calculate_expanding_window_folds",
        "calculate_holdout_split_ranges",
        "calculate_walk_forward_folds",
        "normalize_split_strategy",
        "split_rows_by_plan",
        "validate_dataset_split_ranges",
        "validate_ratio",
        "validate_walk_forward_folds",
    ]

    for export_name in expected_exports:
        assert hasattr(training_data, export_name), export_name