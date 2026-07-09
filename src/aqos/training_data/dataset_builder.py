"""
AQOS feature + event training dataset builder.

This module combines OHLCV candle features with aligned historical news/macro
event features to produce model-ready rows for AQOS ML training.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.training_data.alignment import (
    CandleEventAlignmentDataset,
    alignment_dataset_to_training_rows,
)
from aqos.training_data.base import (
    TrainingDataConfig,
    TrainingDataHealth,
    TrainingDataStatus,
    build_training_data_health,
    normalize_training_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_integer,
    validate_string,
)
from aqos.training_data.ohlcv import (
    HistoricalOhlcvDataset,
    ohlcv_dataset_to_feature_rows,
)


class TrainingFeatureSource(str, Enum):
    """Supported training feature sources."""

    OHLCV = "ohlcv"
    EVENTS = "events"
    ALIGNED = "aligned"
    TECHNICAL = "technical"
    CUSTOM = "custom"


@dataclass(frozen=True)
class TrainingFeatureColumn:
    """Training feature column contract."""

    name: str
    source: TrainingFeatureSource | str
    dtype: str = "float"
    description: str = ""
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Feature column name")
        normalize_training_feature_source(self.source)
        validate_non_empty_string(self.dtype, "Feature column dtype")
        validate_string(self.description, "Feature column description")

        if not isinstance(self.required, bool):
            raise ValueError("Required must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert feature column to dictionary."""
        return {
            "name": self.name.strip(),
            "source": normalize_training_feature_source(self.source).value,
            "dtype": self.dtype.strip(),
            "description": self.description.strip(),
            "required": self.required,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrainingFeatureRow:
    """Model-ready training feature row."""

    timestamp: str
    symbol: str
    features: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.timestamp, "Timestamp")
        normalize_training_symbol(self.symbol)
        validate_metadata(self.features, "Features")
        validate_metadata(self.metadata, "Metadata")

    @property
    def feature_count(self) -> int:
        """Return feature count."""
        return len(self.features)

    def to_dict(self) -> dict[str, Any]:
        """Convert feature row to dictionary."""
        return {
            "timestamp": self.timestamp.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "features": dict(self.features),
            "feature_count": self.feature_count,
            "metadata": dict(self.metadata),
        }

    def flatten(self) -> dict[str, Any]:
        """Flatten timestamp, symbol, and features into one dictionary."""
        return {
            "timestamp": self.timestamp.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            **dict(self.features),
        }


@dataclass(frozen=True)
class TrainingFeatureDataset:
    """Model-ready training feature dataset."""

    config: TrainingDataConfig
    rows: list[TrainingFeatureRow] = field(default_factory=list)
    columns: list[TrainingFeatureColumn] = field(default_factory=list)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.config, TrainingDataConfig):
            raise ValueError("Config must be TrainingDataConfig.")

        validate_training_feature_rows(self.rows)
        validate_training_feature_columns(self.columns)
        validate_string(self.source, "Source")
        validate_metadata(self.metadata, "Metadata")

        if not self.columns and self.rows:
            object.__setattr__(
                self,
                "columns",
                infer_feature_columns_from_rows(self.rows),
            )

    @property
    def dataset_id(self) -> str:
        """Return dataset ID."""
        return self.config.dataset_id

    @property
    def symbol(self) -> str:
        """Return symbol."""
        return normalize_training_symbol(self.config.symbol)

    @property
    def row_count(self) -> int:
        """Return row count."""
        return len(self.rows)

    @property
    def column_count(self) -> int:
        """Return column count."""
        return len(self.columns)

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

    def health(self) -> TrainingDataHealth:
        """Build feature dataset health."""
        status = TrainingDataStatus.READY if self.rows else TrainingDataStatus.EMPTY

        return build_training_data_health(
            dataset_id=self.dataset_id,
            status=status,
            row_count=self.row_count,
            feature_count=self.column_count,
            metadata={
                "symbol": self.symbol,
                "source": self.source,
            },
        )

    def to_rows(self) -> list[dict[str, Any]]:
        """Convert rows to dictionaries."""
        return [row.to_dict() for row in self.rows]

    def to_flat_rows(self) -> list[dict[str, Any]]:
        """Convert rows to flat dictionaries."""
        return [row.flatten() for row in self.rows]

    def to_dict(self) -> dict[str, Any]:
        """Convert feature dataset to dictionary."""
        return {
            "config": self.config.to_dict(),
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "rows": self.to_rows(),
            "flat_rows": self.to_flat_rows(),
            "columns": [column.to_dict() for column in self.columns],
            "row_count": self.row_count,
            "column_count": self.column_count,
            "empty": self.empty,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "source": self.source.strip(),
            "health": self.health().to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TrainingFeatureDatasetSummary:
    """Training feature dataset summary."""

    dataset_id: str
    symbol: str
    row_count: int = 0
    column_count: int = 0
    event_enriched_row_count: int = 0
    first_timestamp: str = ""
    last_timestamp: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        validate_non_negative_integer(self.row_count, "Row count")
        validate_non_negative_integer(self.column_count, "Column count")
        validate_non_negative_integer(
            self.event_enriched_row_count,
            "Event enriched row count",
        )
        validate_string(self.first_timestamp, "First timestamp")
        validate_string(self.last_timestamp, "Last timestamp")
        validate_metadata(self.metadata, "Metadata")

    @property
    def has_rows(self) -> bool:
        """Return whether summary has rows."""
        return self.row_count > 0

    @property
    def event_enriched_ratio(self) -> float:
        """Return event enriched row ratio."""
        if self.row_count == 0:
            return 0.0

        return round(self.event_enriched_row_count / self.row_count, 10)

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "event_enriched_row_count": self.event_enriched_row_count,
            "event_enriched_ratio": self.event_enriched_ratio,
            "first_timestamp": self.first_timestamp.strip(),
            "last_timestamp": self.last_timestamp.strip(),
            "has_rows": self.has_rows,
            "metadata": dict(self.metadata),
        }


def normalize_training_feature_source(
    source: TrainingFeatureSource | str,
) -> TrainingFeatureSource:
    """Normalize training feature source."""
    if isinstance(source, TrainingFeatureSource):
        return source

    normalized = validate_non_empty_string(source, "Training feature source").lower()

    try:
        return TrainingFeatureSource(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in TrainingFeatureSource)
        raise ValueError(
            f"Invalid training feature source '{source}'. Valid sources: {valid}.",
        ) from exc


def validate_training_feature_columns(
    columns: list[TrainingFeatureColumn],
) -> list[TrainingFeatureColumn]:
    """Validate feature columns."""
    if not isinstance(columns, list):
        raise ValueError("Columns must be a list.")

    for column in columns:
        if not isinstance(column, TrainingFeatureColumn):
            raise ValueError("Columns must contain TrainingFeatureColumn objects.")

    return columns


def validate_training_feature_rows(
    rows: list[TrainingFeatureRow],
) -> list[TrainingFeatureRow]:
    """Validate feature rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        if not isinstance(row, TrainingFeatureRow):
            raise ValueError("Rows must contain TrainingFeatureRow objects.")

    return rows


def build_training_feature_column(
    *,
    name: str,
    source: TrainingFeatureSource | str,
    dtype: str = "float",
    description: str = "",
    required: bool = True,
    metadata: dict[str, Any] | None = None,
) -> TrainingFeatureColumn:
    """Build training feature column."""
    return TrainingFeatureColumn(
        name=name,
        source=source,
        dtype=dtype,
        description=description,
        required=required,
        metadata=metadata or {},
    )


def build_training_feature_row(
    *,
    timestamp: str,
    symbol: str,
    features: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> TrainingFeatureRow:
    """Build training feature row."""
    return TrainingFeatureRow(
        timestamp=timestamp,
        symbol=symbol,
        features=features or {},
        metadata=metadata or {},
    )


def infer_feature_columns_from_rows(
    rows: list[TrainingFeatureRow],
    *,
    default_source: TrainingFeatureSource | str = TrainingFeatureSource.CUSTOM,
) -> list[TrainingFeatureColumn]:
    """Infer feature columns from feature rows."""
    validate_training_feature_rows(rows)

    seen: dict[str, TrainingFeatureColumn] = {}

    for row in rows:
        for name, value in row.features.items():
            if name in seen:
                continue

            seen[name] = build_training_feature_column(
                name=name,
                source=infer_feature_source_from_name(name, default_source=default_source),
                dtype=infer_feature_dtype(value),
            )

    return list(seen.values())


def infer_feature_dtype(value: Any) -> str:
    """Infer feature dtype."""
    if isinstance(value, bool):
        return "bool"

    if isinstance(value, int):
        return "int"

    if isinstance(value, float):
        return "float"

    if isinstance(value, list):
        return "list"

    if isinstance(value, dict):
        return "dict"

    return "string"


def infer_feature_source_from_name(
    name: str,
    *,
    default_source: TrainingFeatureSource | str = TrainingFeatureSource.CUSTOM,
) -> TrainingFeatureSource:
    """Infer feature source from feature name."""
    normalized_name = validate_non_empty_string(name, "Feature name").lower()

    if normalized_name.startswith(("open", "high", "low", "close", "volume", "body", "range", "typical")):
        return TrainingFeatureSource.OHLCV

    if normalized_name.startswith(("aligned_event", "event_")):
        return TrainingFeatureSource.EVENTS

    if normalized_name.startswith(("rsi", "macd", "ema", "sma", "atr", "adx")):
        return TrainingFeatureSource.TECHNICAL

    return normalize_training_feature_source(default_source)


def feature_dict_to_training_feature_row(
    row: dict[str, Any],
    *,
    symbol: str,
    timestamp_key: str = "timestamp",
) -> TrainingFeatureRow:
    """Convert raw feature dictionary to TrainingFeatureRow."""
    validate_metadata(row, "Feature row")

    timestamp = str(row[timestamp_key])
    feature_payload = dict(row)
    feature_payload.pop(timestamp_key, None)
    feature_payload.pop("symbol", None)

    return build_training_feature_row(
        timestamp=timestamp,
        symbol=str(row.get("symbol", symbol)),
        features=feature_payload,
    )


def feature_dicts_to_training_feature_rows(
    rows: list[dict[str, Any]],
    *,
    symbol: str,
    timestamp_key: str = "timestamp",
) -> list[TrainingFeatureRow]:
    """Convert raw feature dictionaries to TrainingFeatureRow objects."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    return [
        feature_dict_to_training_feature_row(
            row,
            symbol=symbol,
            timestamp_key=timestamp_key,
        )
        for row in rows
    ]


def build_training_feature_dataset(
    *,
    config: TrainingDataConfig,
    rows: list[TrainingFeatureRow] | None = None,
    columns: list[TrainingFeatureColumn] | None = None,
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> TrainingFeatureDataset:
    """Build training feature dataset."""
    resolved_rows = rows or []
    resolved_columns = columns or infer_feature_columns_from_rows(resolved_rows)

    return TrainingFeatureDataset(
        config=config,
        rows=resolved_rows,
        columns=resolved_columns,
        source=source,
        metadata=metadata or {},
    )


def build_feature_dataset_from_ohlcv(
    dataset: HistoricalOhlcvDataset,
) -> TrainingFeatureDataset:
    """Build feature dataset from OHLCV dataset."""
    if not isinstance(dataset, HistoricalOhlcvDataset):
        raise ValueError("Dataset must be HistoricalOhlcvDataset.")

    raw_rows = ohlcv_dataset_to_feature_rows(dataset)
    rows = feature_dicts_to_training_feature_rows(
        raw_rows,
        symbol=dataset.symbol,
    )

    return build_training_feature_dataset(
        config=dataset.config,
        rows=rows,
        source="ohlcv",
        metadata={
            "ohlcv_dataset_id": dataset.dataset_id,
        },
    )


def build_feature_dataset_from_alignment(
    dataset: CandleEventAlignmentDataset,
    *,
    config: TrainingDataConfig,
) -> TrainingFeatureDataset:
    """Build feature dataset from aligned candle/event dataset."""
    if not isinstance(dataset, CandleEventAlignmentDataset):
        raise ValueError("Dataset must be CandleEventAlignmentDataset.")

    if not isinstance(config, TrainingDataConfig):
        raise ValueError("Config must be TrainingDataConfig.")

    raw_rows = alignment_dataset_to_training_rows(dataset)
    rows = feature_dicts_to_training_feature_rows(
        raw_rows,
        symbol=dataset.symbol,
    )

    return build_training_feature_dataset(
        config=config,
        rows=rows,
        source="aligned",
        metadata={
            "alignment_dataset_id": dataset.dataset_id,
        },
    )


def summarize_training_feature_dataset(
    dataset: TrainingFeatureDataset,
) -> TrainingFeatureDatasetSummary:
    """Summarize training feature dataset."""
    if not isinstance(dataset, TrainingFeatureDataset):
        raise ValueError("Dataset must be TrainingFeatureDataset.")

    event_enriched_row_count = len(
        [
            row
            for row in dataset.rows
            if int(row.features.get("aligned_event_count", 0) or 0) > 0
        ]
    )

    return TrainingFeatureDatasetSummary(
        dataset_id=dataset.dataset_id,
        symbol=dataset.symbol,
        row_count=dataset.row_count,
        column_count=dataset.column_count,
        event_enriched_row_count=event_enriched_row_count,
        first_timestamp=dataset.first_timestamp,
        last_timestamp=dataset.last_timestamp,
        metadata={
            "source": dataset.source,
        },
    )


def merge_feature_rows(
    base_row: TrainingFeatureRow,
    extra_row: TrainingFeatureRow,
    *,
    prefix: str = "",
) -> TrainingFeatureRow:
    """Merge two feature rows with same timestamp/symbol."""
    if not isinstance(base_row, TrainingFeatureRow):
        raise ValueError("Base row must be TrainingFeatureRow.")

    if not isinstance(extra_row, TrainingFeatureRow):
        raise ValueError("Extra row must be TrainingFeatureRow.")

    if base_row.timestamp != extra_row.timestamp:
        raise ValueError("Rows must have same timestamp.")

    if normalize_training_symbol(base_row.symbol) != normalize_training_symbol(extra_row.symbol):
        raise ValueError("Rows must have same symbol.")

    prefix_value = prefix.strip()
    extra_features = {
        f"{prefix_value}{key}" if prefix_value else key: value
        for key, value in extra_row.features.items()
    }

    return TrainingFeatureRow(
        timestamp=base_row.timestamp,
        symbol=base_row.symbol,
        features={
            **base_row.features,
            **extra_features,
        },
        metadata={
            **base_row.metadata,
            "merged": True,
        },
    )


def filter_training_feature_dataset_columns(
    dataset: TrainingFeatureDataset,
    *,
    include_columns: list[str],
) -> TrainingFeatureDataset:
    """Filter feature dataset to selected feature columns."""
    if not isinstance(dataset, TrainingFeatureDataset):
        raise ValueError("Dataset must be TrainingFeatureDataset.")

    if not isinstance(include_columns, list) or not all(
        isinstance(item, str) and item.strip() for item in include_columns
    ):
        raise ValueError("Include columns must be a list of non-empty strings.")

    include_set = {item.strip() for item in include_columns}

    rows = [
        TrainingFeatureRow(
            timestamp=row.timestamp,
            symbol=row.symbol,
            features={
                key: value
                for key, value in row.features.items()
                if key in include_set
            },
            metadata=row.metadata,
        )
        for row in dataset.rows
    ]

    columns = [
        column
        for column in dataset.columns
        if column.name.strip() in include_set
    ]

    return TrainingFeatureDataset(
        config=dataset.config,
        rows=rows,
        columns=columns,
        source=dataset.source,
        metadata={
            **dataset.metadata,
            "filtered_columns": sorted(include_set),
        },
    )