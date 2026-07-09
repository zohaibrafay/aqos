"""
AQOS walk-forward split builder.

This module creates chronological train/validation/test and walk-forward
splits for AQOS ML training without leaking future market information.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.training_data.base import (
    TrainingDatasetSplit,
    normalize_training_dataset_split,
    normalize_training_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_positive_integer,
    validate_string,
)
from aqos.training_data.dataset_builder import TrainingFeatureDataset
from aqos.training_data.labels import LabeledTrainingDataset
from aqos.training_data.pattern_windows import PatternWindowDataset


class SplitStrategy(str, Enum):
    """Supported split strategies."""

    HOLDOUT = "holdout"
    WALK_FORWARD = "walk_forward"
    EXPANDING_WINDOW = "expanding_window"
    ROLLING_WINDOW = "rolling_window"


@dataclass(frozen=True)
class DatasetSplitConfig:
    """Dataset split configuration."""

    strategy: SplitStrategy | str = SplitStrategy.HOLDOUT
    train_ratio: float = 0.7
    validation_ratio: float = 0.15
    test_ratio: float = 0.15
    train_window_size: int = 0
    validation_window_size: int = 0
    test_window_size: int = 0
    step_size: int = 1
    min_train_size: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_split_strategy(self.strategy)
        validate_ratio(self.train_ratio, "Train ratio")
        validate_ratio(self.validation_ratio, "Validation ratio")
        validate_ratio(self.test_ratio, "Test ratio")
        validate_non_negative_integer(self.train_window_size, "Train window size")
        validate_non_negative_integer(self.validation_window_size, "Validation window size")
        validate_non_negative_integer(self.test_window_size, "Test window size")
        validate_positive_integer(self.step_size, "Step size")
        validate_positive_integer(self.min_train_size, "Minimum train size")
        validate_metadata(self.metadata, "Metadata")

        total_ratio = round(
            float(self.train_ratio) + float(self.validation_ratio) + float(self.test_ratio),
            10,
        )

        if total_ratio <= 0:
            raise ValueError("Split ratios must be greater than zero.")

        if normalize_split_strategy(self.strategy) == SplitStrategy.HOLDOUT and total_ratio > 1.0:
            raise ValueError("Holdout split ratios must not exceed 1.0.")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "strategy": normalize_split_strategy(self.strategy).value,
            "train_ratio": float(self.train_ratio),
            "validation_ratio": float(self.validation_ratio),
            "test_ratio": float(self.test_ratio),
            "train_window_size": self.train_window_size,
            "validation_window_size": self.validation_window_size,
            "test_window_size": self.test_window_size,
            "step_size": self.step_size,
            "min_train_size": self.min_train_size,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DatasetSplitRange:
    """Single split range."""

    split_id: str
    split: TrainingDatasetSplit | str
    start_index: int
    end_index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.split_id, "Split ID")
        normalize_training_dataset_split(self.split)
        validate_non_negative_integer(self.start_index, "Start index")
        validate_non_negative_integer(self.end_index, "End index")

        if self.end_index < self.start_index:
            raise ValueError("End index must be greater than or equal to start index.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def row_count(self) -> int:
        """Return row count."""
        return self.end_index - self.start_index

    @property
    def empty(self) -> bool:
        """Return whether range is empty."""
        return self.row_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert split range to dictionary."""
        return {
            "split_id": self.split_id.strip(),
            "split": normalize_training_dataset_split(self.split).value,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "row_count": self.row_count,
            "empty": self.empty,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class WalkForwardFold:
    """Walk-forward fold."""

    fold_id: str
    train_range: DatasetSplitRange
    validation_range: DatasetSplitRange | None = None
    test_range: DatasetSplitRange | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.fold_id, "Fold ID")

        if not isinstance(self.train_range, DatasetSplitRange):
            raise ValueError("Train range must be DatasetSplitRange.")

        if self.validation_range is not None and not isinstance(
            self.validation_range,
            DatasetSplitRange,
        ):
            raise ValueError("Validation range must be DatasetSplitRange.")

        if self.test_range is not None and not isinstance(self.test_range, DatasetSplitRange):
            raise ValueError("Test range must be DatasetSplitRange.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def range_count(self) -> int:
        """Return number of ranges."""
        return 1 + int(self.validation_range is not None) + int(self.test_range is not None)

    def to_dict(self) -> dict[str, Any]:
        """Convert fold to dictionary."""
        return {
            "fold_id": self.fold_id.strip(),
            "train_range": self.train_range.to_dict(),
            "validation_range": self.validation_range.to_dict()
            if self.validation_range is not None
            else None,
            "test_range": self.test_range.to_dict() if self.test_range is not None else None,
            "range_count": self.range_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DatasetSplitPlan:
    """Dataset split plan."""

    dataset_id: str
    symbol: str
    row_count: int
    strategy: SplitStrategy | str
    holdout_ranges: list[DatasetSplitRange] = field(default_factory=list)
    folds: list[WalkForwardFold] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        validate_non_negative_integer(self.row_count, "Row count")
        normalize_split_strategy(self.strategy)
        validate_dataset_split_ranges(self.holdout_ranges)
        validate_walk_forward_folds(self.folds)
        validate_metadata(self.metadata, "Metadata")

    @property
    def fold_count(self) -> int:
        """Return fold count."""
        return len(self.folds)

    @property
    def range_count(self) -> int:
        """Return range count."""
        return len(self.holdout_ranges) + sum(fold.range_count for fold in self.folds)

    @property
    def empty(self) -> bool:
        """Return whether split plan is empty."""
        return self.range_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert split plan to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "row_count": self.row_count,
            "strategy": normalize_split_strategy(self.strategy).value,
            "holdout_ranges": [item.to_dict() for item in self.holdout_ranges],
            "folds": [fold.to_dict() for fold in self.folds],
            "fold_count": self.fold_count,
            "range_count": self.range_count,
            "empty": self.empty,
            "metadata": dict(self.metadata),
        }


def validate_ratio(value: float, field_name: str) -> float:
    """Validate ratio."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    ratio = float(value)

    if ratio < 0 or ratio > 1:
        raise ValueError(f"{field_name} must be between 0 and 1.")

    return ratio


def normalize_split_strategy(strategy: SplitStrategy | str) -> SplitStrategy:
    """Normalize split strategy."""
    if isinstance(strategy, SplitStrategy):
        return strategy

    normalized = validate_non_empty_string(strategy, "Split strategy").lower()

    try:
        return SplitStrategy(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SplitStrategy)
        raise ValueError(
            f"Invalid split strategy '{strategy}'. Valid strategies: {valid}.",
        ) from exc


def validate_dataset_split_ranges(
    ranges: list[DatasetSplitRange],
) -> list[DatasetSplitRange]:
    """Validate split ranges."""
    if not isinstance(ranges, list):
        raise ValueError("Ranges must be a list.")

    for item in ranges:
        if not isinstance(item, DatasetSplitRange):
            raise ValueError("Ranges must contain DatasetSplitRange objects.")

    return ranges


def validate_walk_forward_folds(
    folds: list[WalkForwardFold],
) -> list[WalkForwardFold]:
    """Validate walk-forward folds."""
    if not isinstance(folds, list):
        raise ValueError("Folds must be a list.")

    for fold in folds:
        if not isinstance(fold, WalkForwardFold):
            raise ValueError("Folds must contain WalkForwardFold objects.")

    return folds


def build_dataset_split_config(
    *,
    strategy: SplitStrategy | str = SplitStrategy.HOLDOUT,
    train_ratio: float = 0.7,
    validation_ratio: float = 0.15,
    test_ratio: float = 0.15,
    train_window_size: int = 0,
    validation_window_size: int = 0,
    test_window_size: int = 0,
    step_size: int = 1,
    min_train_size: int = 1,
    metadata: dict[str, Any] | None = None,
) -> DatasetSplitConfig:
    """Build dataset split config."""
    return DatasetSplitConfig(
        strategy=strategy,
        train_ratio=train_ratio,
        validation_ratio=validation_ratio,
        test_ratio=test_ratio,
        train_window_size=train_window_size,
        validation_window_size=validation_window_size,
        test_window_size=test_window_size,
        step_size=step_size,
        min_train_size=min_train_size,
        metadata=metadata or {},
    )


def build_dataset_split_range(
    *,
    split_id: str,
    split: TrainingDatasetSplit | str,
    start_index: int,
    end_index: int,
    metadata: dict[str, Any] | None = None,
) -> DatasetSplitRange:
    """Build dataset split range."""
    return DatasetSplitRange(
        split_id=split_id,
        split=split,
        start_index=start_index,
        end_index=end_index,
        metadata=metadata or {},
    )


def calculate_holdout_split_ranges(
    *,
    dataset_id: str,
    row_count: int,
    config: DatasetSplitConfig,
) -> list[DatasetSplitRange]:
    """Calculate chronological holdout ranges."""
    validate_non_empty_string(dataset_id, "Dataset ID")
    validate_non_negative_integer(row_count, "Row count")

    if not isinstance(config, DatasetSplitConfig):
        raise ValueError("Config must be DatasetSplitConfig.")

    train_count = int(row_count * config.train_ratio)
    validation_count = int(row_count * config.validation_ratio)
    test_count = row_count - train_count - validation_count

    train_end = train_count
    validation_end = train_end + validation_count
    test_end = validation_end + test_count

    return [
        build_dataset_split_range(
            split_id=f"{dataset_id}-train",
            split=TrainingDatasetSplit.TRAIN,
            start_index=0,
            end_index=train_end,
        ),
        build_dataset_split_range(
            split_id=f"{dataset_id}-validation",
            split=TrainingDatasetSplit.VALIDATION,
            start_index=train_end,
            end_index=validation_end,
        ),
        build_dataset_split_range(
            split_id=f"{dataset_id}-test",
            split=TrainingDatasetSplit.TEST,
            start_index=validation_end,
            end_index=test_end,
        ),
    ]


def calculate_walk_forward_folds(
    *,
    dataset_id: str,
    row_count: int,
    config: DatasetSplitConfig,
) -> list[WalkForwardFold]:
    """Calculate walk-forward folds."""
    validate_non_empty_string(dataset_id, "Dataset ID")
    validate_non_negative_integer(row_count, "Row count")

    if not isinstance(config, DatasetSplitConfig):
        raise ValueError("Config must be DatasetSplitConfig.")

    train_size = config.train_window_size or max(config.min_train_size, int(row_count * 0.6))
    validation_size = config.validation_window_size or max(1, int(row_count * 0.2))
    test_size = config.test_window_size or max(1, int(row_count * 0.2))

    folds: list[WalkForwardFold] = []
    fold_index = 0

    start = 0

    while start + train_size + validation_size + test_size <= row_count:
        train_start = start
        train_end = train_start + train_size
        validation_start = train_end
        validation_end = validation_start + validation_size
        test_start = validation_end
        test_end = test_start + test_size

        folds.append(
            WalkForwardFold(
                fold_id=f"{dataset_id}-fold-{fold_index:06d}",
                train_range=build_dataset_split_range(
                    split_id=f"{dataset_id}-fold-{fold_index:06d}-train",
                    split=TrainingDatasetSplit.TRAIN,
                    start_index=train_start,
                    end_index=train_end,
                ),
                validation_range=build_dataset_split_range(
                    split_id=f"{dataset_id}-fold-{fold_index:06d}-validation",
                    split=TrainingDatasetSplit.VALIDATION,
                    start_index=validation_start,
                    end_index=validation_end,
                ),
                test_range=build_dataset_split_range(
                    split_id=f"{dataset_id}-fold-{fold_index:06d}-test",
                    split=TrainingDatasetSplit.TEST,
                    start_index=test_start,
                    end_index=test_end,
                ),
            )
        )

        fold_index += 1
        start += config.step_size

    return folds


def calculate_expanding_window_folds(
    *,
    dataset_id: str,
    row_count: int,
    config: DatasetSplitConfig,
) -> list[WalkForwardFold]:
    """Calculate expanding window folds."""
    validate_non_empty_string(dataset_id, "Dataset ID")
    validate_non_negative_integer(row_count, "Row count")

    if not isinstance(config, DatasetSplitConfig):
        raise ValueError("Config must be DatasetSplitConfig.")

    validation_size = config.validation_window_size or max(1, int(row_count * 0.15))
    test_size = config.test_window_size or max(1, int(row_count * 0.15))
    train_end = config.train_window_size or config.min_train_size

    folds: list[WalkForwardFold] = []
    fold_index = 0

    while train_end + validation_size + test_size <= row_count:
        validation_start = train_end
        validation_end = validation_start + validation_size
        test_start = validation_end
        test_end = test_start + test_size

        folds.append(
            WalkForwardFold(
                fold_id=f"{dataset_id}-fold-{fold_index:06d}",
                train_range=build_dataset_split_range(
                    split_id=f"{dataset_id}-fold-{fold_index:06d}-train",
                    split=TrainingDatasetSplit.TRAIN,
                    start_index=0,
                    end_index=train_end,
                ),
                validation_range=build_dataset_split_range(
                    split_id=f"{dataset_id}-fold-{fold_index:06d}-validation",
                    split=TrainingDatasetSplit.VALIDATION,
                    start_index=validation_start,
                    end_index=validation_end,
                ),
                test_range=build_dataset_split_range(
                    split_id=f"{dataset_id}-fold-{fold_index:06d}-test",
                    split=TrainingDatasetSplit.TEST,
                    start_index=test_start,
                    end_index=test_end,
                ),
            )
        )

        fold_index += 1
        train_end += config.step_size

    return folds


def build_dataset_split_plan(
    *,
    dataset_id: str,
    symbol: str,
    row_count: int,
    config: DatasetSplitConfig | None = None,
    metadata: dict[str, Any] | None = None,
) -> DatasetSplitPlan:
    """Build split plan."""
    config = config or DatasetSplitConfig()

    if not isinstance(config, DatasetSplitConfig):
        raise ValueError("Config must be DatasetSplitConfig.")

    strategy = normalize_split_strategy(config.strategy)

    holdout_ranges: list[DatasetSplitRange] = []
    folds: list[WalkForwardFold] = []

    if strategy == SplitStrategy.HOLDOUT:
        holdout_ranges = calculate_holdout_split_ranges(
            dataset_id=dataset_id,
            row_count=row_count,
            config=config,
        )

    if strategy == SplitStrategy.WALK_FORWARD or strategy == SplitStrategy.ROLLING_WINDOW:
        folds = calculate_walk_forward_folds(
            dataset_id=dataset_id,
            row_count=row_count,
            config=config,
        )

    if strategy == SplitStrategy.EXPANDING_WINDOW:
        folds = calculate_expanding_window_folds(
            dataset_id=dataset_id,
            row_count=row_count,
            config=config,
        )

    return DatasetSplitPlan(
        dataset_id=dataset_id,
        symbol=symbol,
        row_count=row_count,
        strategy=strategy,
        holdout_ranges=holdout_ranges,
        folds=folds,
        metadata=metadata or {},
    )


def build_split_plan_from_feature_dataset(
    dataset: TrainingFeatureDataset,
    *,
    config: DatasetSplitConfig | None = None,
) -> DatasetSplitPlan:
    """Build split plan from feature dataset."""
    if not isinstance(dataset, TrainingFeatureDataset):
        raise ValueError("Dataset must be TrainingFeatureDataset.")

    return build_dataset_split_plan(
        dataset_id=dataset.dataset_id,
        symbol=dataset.symbol,
        row_count=dataset.row_count,
        config=config or DatasetSplitConfig(),
    )


def build_split_plan_from_labeled_dataset(
    dataset: LabeledTrainingDataset,
    *,
    config: DatasetSplitConfig | None = None,
) -> DatasetSplitPlan:
    """Build split plan from labeled dataset."""
    if not isinstance(dataset, LabeledTrainingDataset):
        raise ValueError("Dataset must be LabeledTrainingDataset.")

    return build_dataset_split_plan(
        dataset_id=dataset.dataset_id,
        symbol=dataset.symbol,
        row_count=dataset.row_count,
        config=config or DatasetSplitConfig(),
    )


def build_split_plan_from_pattern_windows(
    dataset: PatternWindowDataset,
    *,
    config: DatasetSplitConfig | None = None,
) -> DatasetSplitPlan:
    """Build split plan from pattern window dataset."""
    if not isinstance(dataset, PatternWindowDataset):
        raise ValueError("Dataset must be PatternWindowDataset.")

    return build_dataset_split_plan(
        dataset_id=dataset.dataset_id,
        symbol=dataset.symbol,
        row_count=dataset.window_count,
        config=config or DatasetSplitConfig(),
    )


def apply_split_range_to_rows(
    rows: list[dict[str, Any]],
    split_range: DatasetSplitRange,
) -> list[dict[str, Any]]:
    """Apply split range to raw rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    if not isinstance(split_range, DatasetSplitRange):
        raise ValueError("Split range must be DatasetSplitRange.")

    return [dict(row) for row in rows[split_range.start_index : split_range.end_index]]


def split_rows_by_plan(
    rows: list[dict[str, Any]],
    plan: DatasetSplitPlan,
) -> dict[str, Any]:
    """Split raw rows by split plan."""
    if not isinstance(plan, DatasetSplitPlan):
        raise ValueError("Plan must be DatasetSplitPlan.")

    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    payload: dict[str, Any] = {
        "dataset_id": plan.dataset_id,
        "strategy": normalize_split_strategy(plan.strategy).value,
    }

    if plan.holdout_ranges:
        payload["holdout"] = {
            normalize_training_dataset_split(split_range.split).value: apply_split_range_to_rows(
                rows,
                split_range,
            )
            for split_range in plan.holdout_ranges
        }

    if plan.folds:
        payload["folds"] = [
            {
                "fold_id": fold.fold_id,
                "train": apply_split_range_to_rows(rows, fold.train_range),
                "validation": apply_split_range_to_rows(rows, fold.validation_range)
                if fold.validation_range is not None
                else [],
                "test": apply_split_range_to_rows(rows, fold.test_range)
                if fold.test_range is not None
                else [],
            }
            for fold in plan.folds
        ]

    return payload