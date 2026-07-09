"""
AQOS training label generation engine.

This module creates supervised learning labels from historical feature rows:
future return, direction, TP/SL outcome, volatility, event impact, and risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.training_data.base import (
    TrainingLabelTarget,
    normalize_training_label_target,
    normalize_training_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_integer,
    validate_string,
)
from aqos.training_data.dataset_builder import (
    TrainingFeatureDataset,
    TrainingFeatureRow,
    build_training_feature_dataset,
)


class TrainingDirectionLabel(str, Enum):
    """Supported direction labels."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"


class TrainingRiskLabel(str, Enum):
    """Supported risk labels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class LabelGenerationConfig:
    """Label generation configuration."""

    horizon: int = 1
    direction_threshold: float = 0.0
    tp_pct: float = 0.01
    sl_pct: float = 0.005
    volatility_window: int = 3
    high_volatility_threshold: float = 0.02
    medium_volatility_threshold: float = 0.01
    label_targets: list[TrainingLabelTarget | str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_positive_integer(self.horizon, "Horizon")
        validate_non_negative_float(self.direction_threshold, "Direction threshold")
        validate_non_negative_float(self.tp_pct, "TP percentage")
        validate_non_negative_float(self.sl_pct, "SL percentage")
        validate_positive_integer(self.volatility_window, "Volatility window")
        validate_non_negative_float(self.high_volatility_threshold, "High volatility threshold")
        validate_non_negative_float(self.medium_volatility_threshold, "Medium volatility threshold")

        if not isinstance(self.label_targets, list):
            raise ValueError("Label targets must be a list.")

        for target in self.label_targets:
            normalize_training_label_target(target)

        validate_metadata(self.metadata, "Metadata")

    @property
    def resolved_label_targets(self) -> list[TrainingLabelTarget]:
        """Return resolved label targets."""
        if self.label_targets:
            return [normalize_training_label_target(target) for target in self.label_targets]

        return [
            TrainingLabelTarget.FUTURE_RETURN,
            TrainingLabelTarget.DIRECTION,
            TrainingLabelTarget.HIT_TP_BEFORE_SL,
            TrainingLabelTarget.VOLATILITY,
            TrainingLabelTarget.EVENT_IMPACT,
            TrainingLabelTarget.RISK_LEVEL,
        ]

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary."""
        return {
            "horizon": self.horizon,
            "direction_threshold": float(self.direction_threshold),
            "tp_pct": float(self.tp_pct),
            "sl_pct": float(self.sl_pct),
            "volatility_window": self.volatility_window,
            "high_volatility_threshold": float(self.high_volatility_threshold),
            "medium_volatility_threshold": float(self.medium_volatility_threshold),
            "label_targets": [target.value for target in self.resolved_label_targets],
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrainingLabelRow:
    """Generated label row."""

    timestamp: str
    symbol: str
    labels: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.timestamp, "Timestamp")
        normalize_training_symbol(self.symbol)
        validate_metadata(self.labels, "Labels")
        validate_metadata(self.metadata, "Metadata")

    @property
    def label_count(self) -> int:
        """Return label count."""
        return len(self.labels)

    def to_dict(self) -> dict[str, Any]:
        """Convert label row to dictionary."""
        return {
            "timestamp": self.timestamp.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "labels": dict(self.labels),
            "label_count": self.label_count,
            "metadata": dict(self.metadata),
        }

    def flatten(self) -> dict[str, Any]:
        """Flatten label row."""
        return {
            "timestamp": self.timestamp.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            **dict(self.labels),
        }


@dataclass(frozen=True)
class TrainingLabelDataset:
    """Generated label dataset."""

    dataset_id: str
    symbol: str
    rows: list[TrainingLabelRow] = field(default_factory=list)
    config: LabelGenerationConfig = field(default_factory=LabelGenerationConfig)
    source_dataset_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        validate_training_label_rows(self.rows)

        if not isinstance(self.config, LabelGenerationConfig):
            raise ValueError("Config must be LabelGenerationConfig.")

        validate_string(self.source_dataset_id, "Source dataset ID")
        validate_metadata(self.metadata, "Metadata")

    @property
    def row_count(self) -> int:
        """Return row count."""
        return len(self.rows)

    @property
    def label_count(self) -> int:
        """Return label count."""
        return len(self.rows[0].labels) if self.rows else 0

    @property
    def empty(self) -> bool:
        """Return whether dataset is empty."""
        return self.row_count == 0

    @property
    def first_timestamp(self) -> str:
        """Return first timestamp."""
        return self.rows[0].timestamp if self.rows else ""

    @property
    def last_timestamp(self) -> str:
        """Return last timestamp."""
        return self.rows[-1].timestamp if self.rows else ""

    def to_rows(self) -> list[dict[str, Any]]:
        """Convert rows to dictionaries."""
        return [row.to_dict() for row in self.rows]

    def to_flat_rows(self) -> list[dict[str, Any]]:
        """Convert rows to flat dictionaries."""
        return [row.flatten() for row in self.rows]

    def to_dict(self) -> dict[str, Any]:
        """Convert label dataset to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "rows": self.to_rows(),
            "flat_rows": self.to_flat_rows(),
            "row_count": self.row_count,
            "label_count": self.label_count,
            "empty": self.empty,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "source_dataset_id": self.source_dataset_id.strip(),
            "config": self.config.to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LabeledTrainingDataset:
    """Feature dataset joined with generated labels."""

    feature_dataset: TrainingFeatureDataset
    label_dataset: TrainingLabelDataset
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.feature_dataset, TrainingFeatureDataset):
            raise ValueError("Feature dataset must be TrainingFeatureDataset.")

        if not isinstance(self.label_dataset, TrainingLabelDataset):
            raise ValueError("Label dataset must be TrainingLabelDataset.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def dataset_id(self) -> str:
        """Return dataset ID."""
        return f"{self.feature_dataset.dataset_id}-labeled"

    @property
    def symbol(self) -> str:
        """Return symbol."""
        return self.feature_dataset.symbol

    @property
    def row_count(self) -> int:
        """Return joined row count."""
        return len(self.to_flat_rows())

    def to_flat_rows(self) -> list[dict[str, Any]]:
        """Join feature rows and label rows by timestamp."""
        labels_by_timestamp = {
            row.timestamp: row
            for row in self.label_dataset.rows
        }

        joined: list[dict[str, Any]] = []

        for feature_row in self.feature_dataset.rows:
            label_row = labels_by_timestamp.get(feature_row.timestamp)

            if label_row is None:
                continue

            joined.append(
                {
                    **feature_row.flatten(),
                    **label_row.labels,
                }
            )

        return joined

    def to_dict(self) -> dict[str, Any]:
        """Convert labeled dataset to dictionary."""
        rows = self.to_flat_rows()

        return {
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "rows": rows,
            "row_count": len(rows),
            "feature_dataset_id": self.feature_dataset.dataset_id,
            "label_dataset_id": self.label_dataset.dataset_id,
            "metadata": dict(self.metadata),
        }


def validate_training_label_rows(
    rows: list[TrainingLabelRow],
) -> list[TrainingLabelRow]:
    """Validate training label rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        if not isinstance(row, TrainingLabelRow):
            raise ValueError("Rows must contain TrainingLabelRow objects.")

    return rows


def build_label_generation_config(
    *,
    horizon: int = 1,
    direction_threshold: float = 0.0,
    tp_pct: float = 0.01,
    sl_pct: float = 0.005,
    volatility_window: int = 3,
    high_volatility_threshold: float = 0.02,
    medium_volatility_threshold: float = 0.01,
    label_targets: list[TrainingLabelTarget | str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LabelGenerationConfig:
    """Build label generation config."""
    return LabelGenerationConfig(
        horizon=horizon,
        direction_threshold=direction_threshold,
        tp_pct=tp_pct,
        sl_pct=sl_pct,
        volatility_window=volatility_window,
        high_volatility_threshold=high_volatility_threshold,
        medium_volatility_threshold=medium_volatility_threshold,
        label_targets=label_targets or [],
        metadata=metadata or {},
    )


def build_training_label_row(
    *,
    timestamp: str,
    symbol: str,
    labels: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingLabelRow:
    """Build training label row."""
    return TrainingLabelRow(
        timestamp=timestamp,
        symbol=symbol,
        labels=labels or {},
        metadata=metadata or {},
    )


def generate_future_return_label(
    rows: list[TrainingFeatureRow],
    *,
    index: int,
    horizon: int,
    close_key: str = "close",
) -> float | None:
    """Generate future return label."""
    validate_positive_integer(horizon, "Horizon")

    if index < 0 or index >= len(rows):
        raise ValueError("Index out of range.")

    future_index = index + horizon

    if future_index >= len(rows):
        return None

    current_close = float(rows[index].features[close_key])
    future_close = float(rows[future_index].features[close_key])

    if current_close == 0:
        return None

    return round((future_close - current_close) / current_close, 10)


def generate_direction_label(
    future_return: float | None,
    *,
    threshold: float = 0.0,
) -> str | None:
    """Generate direction label."""
    validate_non_negative_float(threshold, "Direction threshold")

    if future_return is None:
        return None

    if future_return > threshold:
        return TrainingDirectionLabel.UP.value

    if future_return < -threshold:
        return TrainingDirectionLabel.DOWN.value

    return TrainingDirectionLabel.FLAT.value


def generate_tp_sl_label(
    rows: list[TrainingFeatureRow],
    *,
    index: int,
    horizon: int,
    tp_pct: float,
    sl_pct: float,
    close_key: str = "close",
    high_key: str = "high",
    low_key: str = "low",
) -> int | None:
    """Generate TP-before-SL label.

    Returns:
        1 if TP is hit before SL.
        0 if SL is hit before TP.
        None if neither is hit or future window unavailable.
    """
    validate_positive_integer(horizon, "Horizon")
    validate_non_negative_float(tp_pct, "TP percentage")
    validate_non_negative_float(sl_pct, "SL percentage")

    if index < 0 or index >= len(rows):
        raise ValueError("Index out of range.")

    start_price = float(rows[index].features[close_key])
    tp_price = start_price * (1 + tp_pct)
    sl_price = start_price * (1 - sl_pct)

    future_rows = rows[index + 1 : index + horizon + 1]

    if len(future_rows) < horizon:
        return None

    for row in future_rows:
        high = float(row.features[high_key])
        low = float(row.features[low_key])

        if high >= tp_price:
            return 1

        if low <= sl_price:
            return 0

    return None


def generate_volatility_label(
    rows: list[TrainingFeatureRow],
    *,
    index: int,
    window: int,
    high_threshold: float,
    medium_threshold: float,
    close_key: str = "close",
    high_key: str = "high",
    low_key: str = "low",
) -> str | None:
    """Generate volatility label from future close returns and candle ranges."""
    validate_positive_integer(window, "Volatility window")
    validate_non_negative_float(high_threshold, "High volatility threshold")
    validate_non_negative_float(medium_threshold, "Medium volatility threshold")

    if index < 0 or index >= len(rows):
        raise ValueError("Index out of range.")

    future_rows = rows[index : index + window + 1]

    if len(future_rows) < window + 1:
        return None

    volatility_values: list[float] = []

    for current, future in zip(future_rows, future_rows[1:]):
        current_close = float(current.features[close_key])
        future_close = float(future.features[close_key])

        if current_close == 0:
            return None

        close_return = abs((future_close - current_close) / current_close)
        volatility_values.append(close_return)

        future_high = float(future.features[high_key])
        future_low = float(future.features[low_key])

        candle_range_volatility = abs((future_high - future_low) / current_close)
        volatility_values.append(candle_range_volatility)

    volatility = max(volatility_values) if volatility_values else 0.0

    if volatility >= high_threshold:
        return "high"

    if volatility >= medium_threshold:
        return "medium"

    return "low"


def generate_event_impact_label(row: TrainingFeatureRow) -> str:
    """Generate event impact label."""
    if not isinstance(row, TrainingFeatureRow):
        raise ValueError("Row must be TrainingFeatureRow.")

    high_count = int(row.features.get("aligned_high_impact_event_count", 0) or 0)
    event_count = int(row.features.get("aligned_event_count", 0) or 0)

    if high_count > 0:
        return "high"

    if event_count > 0:
        return "medium"

    return "low"


def generate_risk_label(row: TrainingFeatureRow, volatility_label: str | None) -> str | None:
    """Generate risk label."""
    if not isinstance(row, TrainingFeatureRow):
        raise ValueError("Row must be TrainingFeatureRow.")

    if volatility_label is None:
        return None

    high_events = int(row.features.get("aligned_high_impact_event_count", 0) or 0)

    if volatility_label == "high" or high_events > 0:
        return TrainingRiskLabel.HIGH.value

    if volatility_label == "medium" or int(row.features.get("aligned_event_count", 0) or 0) > 0:
        return TrainingRiskLabel.MEDIUM.value

    return TrainingRiskLabel.LOW.value


def generate_label_row_for_feature_row(
    rows: list[TrainingFeatureRow],
    *,
    index: int,
    config: LabelGenerationConfig,
) -> TrainingLabelRow | None:
    """Generate labels for one feature row."""
    validate_training_feature_rows_for_labels(rows)

    if not isinstance(config, LabelGenerationConfig):
        raise ValueError("Config must be LabelGenerationConfig.")

    row = rows[index]
    labels: dict[str, Any] = {}

    future_return = generate_future_return_label(
        rows,
        index=index,
        horizon=config.horizon,
    )
    volatility_label = generate_volatility_label(
        rows,
        index=index,
        window=config.volatility_window,
        high_threshold=config.high_volatility_threshold,
        medium_threshold=config.medium_volatility_threshold,
    )

    for target in config.resolved_label_targets:
        if target == TrainingLabelTarget.FUTURE_RETURN:
            labels["label_future_return"] = future_return

        if target == TrainingLabelTarget.DIRECTION:
            labels["label_direction"] = generate_direction_label(
                future_return,
                threshold=config.direction_threshold,
            )

        if target == TrainingLabelTarget.HIT_TP_BEFORE_SL:
            labels["label_hit_tp_before_sl"] = generate_tp_sl_label(
                rows,
                index=index,
                horizon=config.horizon,
                tp_pct=config.tp_pct,
                sl_pct=config.sl_pct,
            )

        if target == TrainingLabelTarget.VOLATILITY:
            labels["label_volatility"] = volatility_label

        if target == TrainingLabelTarget.EVENT_IMPACT:
            labels["label_event_impact"] = generate_event_impact_label(row)

        if target == TrainingLabelTarget.RISK_LEVEL:
            labels["label_risk_level"] = generate_risk_label(row, volatility_label)

    if all(value is None for value in labels.values()):
        return None

    return build_training_label_row(
        timestamp=row.timestamp,
        symbol=row.symbol,
        labels=labels,
        metadata={
            "source_index": index,
        },
    )


def generate_label_dataset(
    dataset: TrainingFeatureDataset,
    *,
    config: LabelGenerationConfig | None = None,
    dataset_id: str = "",
) -> TrainingLabelDataset:
    """Generate label dataset from feature dataset."""
    if not isinstance(dataset, TrainingFeatureDataset):
        raise ValueError("Dataset must be TrainingFeatureDataset.")

    config = config or LabelGenerationConfig()
    if not isinstance(config, LabelGenerationConfig):
        raise ValueError("Config must be LabelGenerationConfig.")

    validate_training_feature_rows_for_labels(dataset.rows)

    label_rows: list[TrainingLabelRow] = []

    for index in range(dataset.row_count):
        label_row = generate_label_row_for_feature_row(
            dataset.rows,
            index=index,
            config=config,
        )

        if label_row is not None:
            label_rows.append(label_row)

    return TrainingLabelDataset(
        dataset_id=dataset_id or f"{dataset.dataset_id}-labels",
        symbol=dataset.symbol,
        rows=label_rows,
        config=config,
        source_dataset_id=dataset.dataset_id,
        metadata={
            "feature_dataset_id": dataset.dataset_id,
        },
    )


def join_features_and_labels(
    feature_dataset: TrainingFeatureDataset,
    label_dataset: TrainingLabelDataset,
) -> LabeledTrainingDataset:
    """Join feature dataset and label dataset."""
    return LabeledTrainingDataset(
        feature_dataset=feature_dataset,
        label_dataset=label_dataset,
    )


def build_labeled_training_dataset(
    dataset: TrainingFeatureDataset,
    *,
    config: LabelGenerationConfig | None = None,
    label_dataset_id: str = "",
) -> LabeledTrainingDataset:
    """Build labeled training dataset from feature dataset."""
    label_dataset = generate_label_dataset(
        dataset,
        config=config or LabelGenerationConfig(),
        dataset_id=label_dataset_id,
    )

    return join_features_and_labels(
        feature_dataset=dataset,
        label_dataset=label_dataset,
    )


def validate_training_feature_rows_for_labels(
    rows: list[TrainingFeatureRow],
) -> list[TrainingFeatureRow]:
    """Validate feature rows are label-ready."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        if not isinstance(row, TrainingFeatureRow):
            raise ValueError("Rows must contain TrainingFeatureRow objects.")

        for required_key in ["close", "high", "low"]:
            if required_key not in row.features:
                raise ValueError(f"Feature row is missing required key '{required_key}'.")

    return rows