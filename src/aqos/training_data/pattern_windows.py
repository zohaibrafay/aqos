"""
AQOS pattern window builder.

This module builds rolling market-state windows from feature/labeled datasets
so AQOS models can learn hidden recurring patterns instead of only relying on
classical chart patterns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.training_data.base import (
    normalize_training_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_positive_integer,
    validate_string,
)
from aqos.training_data.dataset_builder import (
    TrainingFeatureDataset,
    TrainingFeatureRow,
)
from aqos.training_data.labels import LabeledTrainingDataset


class PatternWindowMode(str, Enum):
    """Supported pattern window modes."""

    ROLLING = "rolling"
    ANCHORED = "anchored"
    EXPANDING = "expanding"


@dataclass(frozen=True)
class PatternWindowConfig:
    """Pattern window generation configuration."""

    window_size: int = 32
    step_size: int = 1
    mode: PatternWindowMode | str = PatternWindowMode.ROLLING
    include_labels: bool = True
    flatten_features: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_positive_integer(self.window_size, "Window size")
        validate_positive_integer(self.step_size, "Step size")
        normalize_pattern_window_mode(self.mode)

        if not isinstance(self.include_labels, bool):
            raise ValueError("Include labels must be a boolean.")

        if not isinstance(self.flatten_features, bool):
            raise ValueError("Flatten features must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "window_size": self.window_size,
            "step_size": self.step_size,
            "mode": normalize_pattern_window_mode(self.mode).value,
            "include_labels": self.include_labels,
            "flatten_features": self.flatten_features,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PatternWindowRow:
    """Single pattern window row."""

    window_id: str
    symbol: str
    start_timestamp: str
    end_timestamp: str
    rows: list[dict[str, Any]] = field(default_factory=list)
    label: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.window_id, "Window ID")
        normalize_training_symbol(self.symbol)
        validate_non_empty_string(self.start_timestamp, "Start timestamp")
        validate_non_empty_string(self.end_timestamp, "End timestamp")
        validate_raw_pattern_rows(self.rows)
        validate_metadata(self.label, "Label")
        validate_metadata(self.metadata, "Metadata")

    @property
    def row_count(self) -> int:
        """Return number of rows inside window."""
        return len(self.rows)

    @property
    def has_label(self) -> bool:
        """Return whether window has label."""
        return bool(self.label)

    def to_dict(self) -> dict[str, Any]:
        """Convert pattern window row to dictionary."""
        return {
            "window_id": self.window_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "start_timestamp": self.start_timestamp.strip(),
            "end_timestamp": self.end_timestamp.strip(),
            "rows": [dict(row) for row in self.rows],
            "row_count": self.row_count,
            "label": dict(self.label),
            "has_label": self.has_label,
            "metadata": dict(self.metadata),
        }

    def flatten(self) -> dict[str, Any]:
        """Flatten window into one dictionary."""
        flattened: dict[str, Any] = {
            "window_id": self.window_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "start_timestamp": self.start_timestamp.strip(),
            "end_timestamp": self.end_timestamp.strip(),
        }

        for row_index, row in enumerate(self.rows):
            for key, value in row.items():
                if key in {"timestamp", "symbol"}:
                    continue

                flattened[f"t{row_index}_{key}"] = value

        for key, value in self.label.items():
            flattened[key] = value

        return flattened


@dataclass(frozen=True)
class PatternWindowDataset:
    """Pattern window dataset."""

    dataset_id: str
    symbol: str
    windows: list[PatternWindowRow] = field(default_factory=list)
    config: PatternWindowConfig = field(default_factory=PatternWindowConfig)
    source_dataset_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        validate_pattern_window_rows(self.windows)

        if not isinstance(self.config, PatternWindowConfig):
            raise ValueError("Config must be PatternWindowConfig.")

        validate_string(self.source_dataset_id, "Source dataset ID")
        validate_metadata(self.metadata, "Metadata")

    @property
    def window_count(self) -> int:
        """Return window count."""
        return len(self.windows)

    @property
    def empty(self) -> bool:
        """Return whether dataset is empty."""
        return self.window_count == 0

    @property
    def labeled_window_count(self) -> int:
        """Return labeled window count."""
        return len([window for window in self.windows if window.has_label])

    @property
    def first_timestamp(self) -> str:
        """Return first timestamp."""
        return self.windows[0].start_timestamp if self.windows else ""

    @property
    def last_timestamp(self) -> str:
        """Return last timestamp."""
        return self.windows[-1].end_timestamp if self.windows else ""

    def to_windows(self) -> list[dict[str, Any]]:
        """Convert windows to dictionaries."""
        return [window.to_dict() for window in self.windows]

    def to_flat_windows(self) -> list[dict[str, Any]]:
        """Convert windows to flat dictionaries."""
        return [window.flatten() for window in self.windows]

    def to_dict(self) -> dict[str, Any]:
        """Convert pattern window dataset to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "windows": self.to_windows(),
            "flat_windows": self.to_flat_windows(),
            "window_count": self.window_count,
            "empty": self.empty,
            "labeled_window_count": self.labeled_window_count,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "source_dataset_id": self.source_dataset_id.strip(),
            "config": self.config.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PatternWindowSummary:
    """Pattern window dataset summary."""

    dataset_id: str
    symbol: str
    window_count: int = 0
    labeled_window_count: int = 0
    window_size: int = 0
    step_size: int = 0
    first_timestamp: str = ""
    last_timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        validate_non_negative_integer(self.window_count, "Window count")
        validate_non_negative_integer(self.labeled_window_count, "Labeled window count")
        validate_non_negative_integer(self.window_size, "Window size")
        validate_non_negative_integer(self.step_size, "Step size")
        validate_string(self.first_timestamp, "First timestamp")
        validate_string(self.last_timestamp, "Last timestamp")
        validate_metadata(self.metadata, "Metadata")

    @property
    def has_windows(self) -> bool:
        """Return whether summary has windows."""
        return self.window_count > 0

    @property
    def labeled_ratio(self) -> float:
        """Return labeled window ratio."""
        if self.window_count == 0:
            return 0.0

        return round(self.labeled_window_count / self.window_count, 10)

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "window_count": self.window_count,
            "labeled_window_count": self.labeled_window_count,
            "labeled_ratio": self.labeled_ratio,
            "window_size": self.window_size,
            "step_size": self.step_size,
            "first_timestamp": self.first_timestamp.strip(),
            "last_timestamp": self.last_timestamp.strip(),
            "has_windows": self.has_windows,
            "metadata": dict(self.metadata),
        }


def normalize_pattern_window_mode(mode: PatternWindowMode | str) -> PatternWindowMode:
    """Normalize pattern window mode."""
    if isinstance(mode, PatternWindowMode):
        return mode

    normalized = validate_non_empty_string(mode, "Pattern window mode").lower()

    try:
        return PatternWindowMode(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PatternWindowMode)
        raise ValueError(
            f"Invalid pattern window mode '{mode}'. Valid modes: {valid}.",
        ) from exc


def validate_raw_pattern_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate raw pattern rows."""
    if not isinstance(rows, list):
        raise ValueError("Pattern rows must be a list.")

    for row in rows:
        validate_metadata(row, "Pattern row")

    return rows


def validate_pattern_window_rows(
    windows: list[PatternWindowRow],
) -> list[PatternWindowRow]:
    """Validate pattern windows."""
    if not isinstance(windows, list):
        raise ValueError("Windows must be a list.")

    for window in windows:
        if not isinstance(window, PatternWindowRow):
            raise ValueError("Windows must contain PatternWindowRow objects.")

    return windows


def build_pattern_window_config(
    *,
    window_size: int = 32,
    step_size: int = 1,
    mode: PatternWindowMode | str = PatternWindowMode.ROLLING,
    include_labels: bool = True,
    flatten_features: bool = False,
    metadata: dict[str, Any] | None = None,
) -> PatternWindowConfig:
    """Build pattern window config."""
    return PatternWindowConfig(
        window_size=window_size,
        step_size=step_size,
        mode=mode,
        include_labels=include_labels,
        flatten_features=flatten_features,
        metadata=metadata or {},
    )


def build_pattern_window_row(
    *,
    window_id: str,
    symbol: str,
    start_timestamp: str,
    end_timestamp: str,
    rows: list[dict[str, Any]] | None = None,
    label: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> PatternWindowRow:
    """Build pattern window row."""
    return PatternWindowRow(
        window_id=window_id,
        symbol=symbol,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        rows=rows or [],
        label=label or {},
        metadata=metadata or {},
    )


def feature_rows_to_pattern_rows(
    rows: list[TrainingFeatureRow],
) -> list[dict[str, Any]]:
    """Convert feature rows into raw pattern rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    pattern_rows: list[dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, TrainingFeatureRow):
            raise ValueError("Rows must contain TrainingFeatureRow objects.")

        pattern_rows.append(row.flatten())

    return pattern_rows


def calculate_pattern_window_ranges(
    *,
    row_count: int,
    config: PatternWindowConfig,
) -> list[tuple[int, int]]:
    """Calculate pattern window index ranges."""
    validate_non_negative_integer(row_count, "Row count")

    if not isinstance(config, PatternWindowConfig):
        raise ValueError("Config must be PatternWindowConfig.")

    if row_count < config.window_size:
        return []

    mode = normalize_pattern_window_mode(config.mode)

    ranges: list[tuple[int, int]] = []

    if mode == PatternWindowMode.ROLLING:
        start = 0
        while start + config.window_size <= row_count:
            ranges.append((start, start + config.window_size))
            start += config.step_size

    if mode == PatternWindowMode.ANCHORED:
        end = config.window_size
        while end <= row_count:
            ranges.append((0, end))
            end += config.step_size

    if mode == PatternWindowMode.EXPANDING:
        start = 0
        end = config.window_size
        while end <= row_count:
            ranges.append((start, end))
            end += config.step_size

    return ranges


def build_pattern_windows_from_feature_rows(
    *,
    dataset_id: str,
    symbol: str,
    rows: list[TrainingFeatureRow],
    config: PatternWindowConfig | None = None,
    source_dataset_id: str = "",
) -> PatternWindowDataset:
    """Build pattern windows from feature rows."""
    config = config or PatternWindowConfig()

    if not isinstance(config, PatternWindowConfig):
        raise ValueError("Config must be PatternWindowConfig.")

    pattern_rows = feature_rows_to_pattern_rows(rows)
    ranges = calculate_pattern_window_ranges(
        row_count=len(pattern_rows),
        config=config,
    )

    windows: list[PatternWindowRow] = []

    for window_index, (start, end) in enumerate(ranges):
        window_rows = pattern_rows[start:end]
        start_timestamp = str(window_rows[0]["timestamp"])
        end_timestamp = str(window_rows[-1]["timestamp"])

        windows.append(
            build_pattern_window_row(
                window_id=f"{dataset_id}-window-{window_index:06d}",
                symbol=symbol,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                rows=window_rows,
                metadata={
                    "start_index": start,
                    "end_index": end,
                },
            )
        )

    return PatternWindowDataset(
        dataset_id=dataset_id,
        symbol=symbol,
        windows=windows,
        config=config,
        source_dataset_id=source_dataset_id,
        metadata={
            "source_row_count": len(pattern_rows),
        },
    )


def build_pattern_windows_from_feature_dataset(
    dataset: TrainingFeatureDataset,
    *,
    config: PatternWindowConfig | None = None,
    dataset_id: str = "",
) -> PatternWindowDataset:
    """Build pattern windows from feature dataset."""
    if not isinstance(dataset, TrainingFeatureDataset):
        raise ValueError("Dataset must be TrainingFeatureDataset.")

    return build_pattern_windows_from_feature_rows(
        dataset_id=dataset_id or f"{dataset.dataset_id}-patterns",
        symbol=dataset.symbol,
        rows=dataset.rows,
        config=config or PatternWindowConfig(),
        source_dataset_id=dataset.dataset_id,
    )


def build_pattern_windows_from_labeled_dataset(
    dataset: LabeledTrainingDataset,
    *,
    config: PatternWindowConfig | None = None,
    dataset_id: str = "",
) -> PatternWindowDataset:
    """Build pattern windows from labeled training dataset."""
    if not isinstance(dataset, LabeledTrainingDataset):
        raise ValueError("Dataset must be LabeledTrainingDataset.")

    config = config or PatternWindowConfig()
    if not isinstance(config, PatternWindowConfig):
        raise ValueError("Config must be PatternWindowConfig.")

    flat_rows = dataset.to_flat_rows()
    ranges = calculate_pattern_window_ranges(
        row_count=len(flat_rows),
        config=config,
    )

    windows: list[PatternWindowRow] = []
    resolved_dataset_id = dataset_id or f"{dataset.dataset_id}-patterns"

    for window_index, (start, end) in enumerate(ranges):
        window_rows = flat_rows[start:end]
        start_timestamp = str(window_rows[0]["timestamp"])
        end_timestamp = str(window_rows[-1]["timestamp"])

        label: dict[str, Any] = {}
        if config.include_labels:
            label = {
                key: value
                for key, value in window_rows[-1].items()
                if key.startswith("label_")
            }

        feature_window_rows = [
            {
                key: value
                for key, value in row.items()
                if not key.startswith("label_")
            }
            for row in window_rows
        ]

        windows.append(
            build_pattern_window_row(
                window_id=f"{resolved_dataset_id}-window-{window_index:06d}",
                symbol=dataset.symbol,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
                rows=feature_window_rows,
                label=label,
                metadata={
                    "start_index": start,
                    "end_index": end,
                },
            )
        )

    return PatternWindowDataset(
        dataset_id=resolved_dataset_id,
        symbol=dataset.symbol,
        windows=windows,
        config=config,
        source_dataset_id=dataset.dataset_id,
        metadata={
            "source_row_count": len(flat_rows),
            "label_source": dataset.label_dataset.dataset_id,
        },
    )


def summarize_pattern_window_dataset(
    dataset: PatternWindowDataset,
) -> PatternWindowSummary:
    """Summarize pattern window dataset."""
    if not isinstance(dataset, PatternWindowDataset):
        raise ValueError("Dataset must be PatternWindowDataset.")

    return PatternWindowSummary(
        dataset_id=dataset.dataset_id,
        symbol=dataset.symbol,
        window_count=dataset.window_count,
        labeled_window_count=dataset.labeled_window_count,
        window_size=dataset.config.window_size,
        step_size=dataset.config.step_size,
        first_timestamp=dataset.first_timestamp,
        last_timestamp=dataset.last_timestamp,
        metadata={
            "source_dataset_id": dataset.source_dataset_id,
            "mode": normalize_pattern_window_mode(dataset.config.mode).value,
        },
    )


def pattern_window_dataset_to_model_matrix(
    dataset: PatternWindowDataset,
) -> list[list[dict[str, Any]]]:
    """Convert pattern windows into model matrix rows."""
    if not isinstance(dataset, PatternWindowDataset):
        raise ValueError("Dataset must be PatternWindowDataset.")

    return [[dict(row) for row in window.rows] for window in dataset.windows]


def pattern_window_dataset_to_label_rows(
    dataset: PatternWindowDataset,
) -> list[dict[str, Any]]:
    """Convert pattern window labels into rows."""
    if not isinstance(dataset, PatternWindowDataset):
        raise ValueError("Dataset must be PatternWindowDataset.")

    return [
        {
            "window_id": window.window_id,
            **dict(window.label),
        }
        for window in dataset.windows
        if window.has_label
    ]