"""
AQOS historical OHLCV training dataset contracts.

This module defines historical candle rows, dataset summaries, import helpers,
validation helpers, and frontend/model-ready OHLCV dataset structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.training_data.base import (
    TrainingDataAssetType,
    TrainingDataConfig,
    TrainingDataHealth,
    TrainingDataStatus,
    TrainingDataTimeframe,
    build_training_data_config,
    build_training_data_health,
    normalize_training_data_asset_type,
    normalize_training_data_timeframe,
    normalize_training_symbol,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_non_negative_integer,
    validate_number,
    validate_string,
)


@dataclass(frozen=True)
class HistoricalOhlcvRow:
    """Historical OHLCV candle row."""

    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    symbol: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_non_negative_float(self.open, "Open")
        validate_non_negative_float(self.high, "High")
        validate_non_negative_float(self.low, "Low")
        validate_non_negative_float(self.close, "Close")
        validate_non_negative_float(self.volume, "Volume")
        validate_string(self.symbol, "Symbol")

        if self.symbol.strip():
            normalize_training_symbol(self.symbol)

        validate_metadata(self.metadata, "Metadata")

        if self.high < max(self.open, self.close, self.low):
            raise ValueError("High must be greater than or equal to open, close, and low.")

        if self.low > min(self.open, self.close, self.high):
            raise ValueError("Low must be less than or equal to open, close, and high.")

    @property
    def bullish(self) -> bool:
        """Return whether candle is bullish."""
        return self.close > self.open

    @property
    def bearish(self) -> bool:
        """Return whether candle is bearish."""
        return self.close < self.open

    @property
    def body_size(self) -> float:
        """Return candle body size."""
        return round(abs(float(self.close) - float(self.open)), 10)

    @property
    def range_size(self) -> float:
        """Return candle range size."""
        return round(float(self.high) - float(self.low), 10)

    @property
    def typical_price(self) -> float:
        """Return typical price."""
        return round((float(self.high) + float(self.low) + float(self.close)) / 3, 10)

    def to_dict(self) -> dict[str, Any]:
        """Convert OHLCV row to dictionary."""
        return {
            "timestamp": self.timestamp.strip(),
            "symbol": normalize_training_symbol(self.symbol) if self.symbol.strip() else "",
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "bullish": self.bullish,
            "bearish": self.bearish,
            "body_size": self.body_size,
            "range_size": self.range_size,
            "typical_price": self.typical_price,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HistoricalOhlcvDataset:
    """Historical OHLCV training dataset."""

    config: TrainingDataConfig
    rows: list[HistoricalOhlcvRow] = field(default_factory=list)
    source: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.config, TrainingDataConfig):
            raise ValueError("Config must be TrainingDataConfig.")

        validate_historical_ohlcv_rows(self.rows)
        validate_string(self.source, "Source")
        validate_metadata(self.metadata, "Metadata")

    @property
    def dataset_id(self) -> str:
        """Return dataset ID."""
        return self.config.dataset_id

    @property
    def symbol(self) -> str:
        """Return dataset symbol."""
        return normalize_training_symbol(self.config.symbol)

    @property
    def timeframe(self) -> TrainingDataTimeframe:
        """Return dataset timeframe."""
        return normalize_training_data_timeframe(self.config.timeframe)

    @property
    def row_count(self) -> int:
        """Return row count."""
        return len(self.rows)

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

    @property
    def close_prices(self) -> list[float]:
        """Return close prices."""
        return [float(row.close) for row in self.rows]

    @property
    def volumes(self) -> list[float]:
        """Return volumes."""
        return [float(row.volume) for row in self.rows]

    def health(self) -> TrainingDataHealth:
        """Build dataset health."""
        status = TrainingDataStatus.READY if self.rows else TrainingDataStatus.EMPTY

        return build_training_data_health(
            dataset_id=self.dataset_id,
            status=status,
            row_count=self.row_count,
            metadata={
                "symbol": self.symbol,
                "timeframe": self.timeframe.value,
                "source": self.source,
            },
        )

    def to_rows(self) -> list[dict[str, Any]]:
        """Convert rows to dictionaries."""
        return [row.to_dict() for row in self.rows]

    def to_dict(self) -> dict[str, Any]:
        """Convert dataset to dictionary."""
        return {
            "config": self.config.to_dict(),
            "dataset_id": self.dataset_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe.value,
            "source": self.source.strip(),
            "rows": self.to_rows(),
            "row_count": self.row_count,
            "empty": self.empty,
            "first_timestamp": self.first_timestamp,
            "last_timestamp": self.last_timestamp,
            "health": self.health().to_dict(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class HistoricalOhlcvSummary:
    """Historical OHLCV dataset summary."""

    dataset_id: str
    symbol: str
    timeframe: TrainingDataTimeframe | str
    row_count: int = 0
    first_timestamp: str = ""
    last_timestamp: str = ""
    min_close: float = 0.0
    max_close: float = 0.0
    average_close: float = 0.0
    total_volume: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dataset_id, "Dataset ID")
        normalize_training_symbol(self.symbol)
        normalize_training_data_timeframe(self.timeframe)
        validate_non_negative_integer(self.row_count, "Row count")
        validate_string(self.first_timestamp, "First timestamp")
        validate_string(self.last_timestamp, "Last timestamp")
        validate_non_negative_float(self.min_close, "Minimum close")
        validate_non_negative_float(self.max_close, "Maximum close")
        validate_non_negative_float(self.average_close, "Average close")
        validate_non_negative_float(self.total_volume, "Total volume")
        validate_metadata(self.metadata, "Metadata")

    @property
    def has_data(self) -> bool:
        """Return whether summary has data."""
        return self.row_count > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert summary to dictionary."""
        return {
            "dataset_id": self.dataset_id.strip(),
            "symbol": normalize_training_symbol(self.symbol),
            "timeframe": normalize_training_data_timeframe(self.timeframe).value,
            "row_count": self.row_count,
            "first_timestamp": self.first_timestamp.strip(),
            "last_timestamp": self.last_timestamp.strip(),
            "min_close": float(self.min_close),
            "max_close": float(self.max_close),
            "average_close": float(self.average_close),
            "total_volume": float(self.total_volume),
            "has_data": self.has_data,
            "metadata": dict(self.metadata),
        }


def validate_historical_ohlcv_rows(
    rows: list[HistoricalOhlcvRow],
) -> list[HistoricalOhlcvRow]:
    """Validate historical OHLCV rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        if not isinstance(row, HistoricalOhlcvRow):
            raise ValueError("Rows must contain HistoricalOhlcvRow objects.")

    return rows


def validate_raw_ohlcv_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate raw OHLCV rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        validate_metadata(row, "OHLCV row")

    return rows


def build_historical_ohlcv_row(
    *,
    timestamp: str,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float = 0.0,
    symbol: str = "",
    metadata: dict[str, Any] | None = None,
) -> HistoricalOhlcvRow:
    """Build historical OHLCV row."""
    return HistoricalOhlcvRow(
        timestamp=timestamp,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        symbol=symbol,
        metadata=metadata or {},
    )


def raw_row_to_historical_ohlcv_row(
    row: dict[str, Any],
    *,
    timestamp_key: str = "timestamp",
    open_key: str = "open",
    high_key: str = "high",
    low_key: str = "low",
    close_key: str = "close",
    volume_key: str = "volume",
    symbol: str = "",
) -> HistoricalOhlcvRow:
    """Convert raw row to historical OHLCV row."""
    validate_metadata(row, "OHLCV row")

    return build_historical_ohlcv_row(
        timestamp=str(row[timestamp_key]),
        open=float(row[open_key]),
        high=float(row[high_key]),
        low=float(row[low_key]),
        close=float(row[close_key]),
        volume=float(row.get(volume_key, 0.0) or 0.0),
        symbol=str(row.get("symbol", symbol)),
        metadata=dict(row.get("metadata", {})),
    )


def raw_rows_to_historical_ohlcv_rows(
    rows: list[dict[str, Any]],
    *,
    symbol: str = "",
    timestamp_key: str = "timestamp",
    open_key: str = "open",
    high_key: str = "high",
    low_key: str = "low",
    close_key: str = "close",
    volume_key: str = "volume",
) -> list[HistoricalOhlcvRow]:
    """Convert raw rows to historical OHLCV rows."""
    validate_raw_ohlcv_rows(rows)

    return [
        raw_row_to_historical_ohlcv_row(
            row,
            timestamp_key=timestamp_key,
            open_key=open_key,
            high_key=high_key,
            low_key=low_key,
            close_key=close_key,
            volume_key=volume_key,
            symbol=symbol,
        )
        for row in rows
    ]


def build_historical_ohlcv_dataset(
    *,
    dataset_id: str,
    symbol: str,
    rows: list[HistoricalOhlcvRow] | None = None,
    asset_type: TrainingDataAssetType | str = TrainingDataAssetType.UNKNOWN,
    timeframe: TrainingDataTimeframe | str = TrainingDataTimeframe.H1,
    start_date: str = "",
    end_date: str = "",
    timezone: str = "UTC",
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> HistoricalOhlcvDataset:
    """Build historical OHLCV dataset."""
    config = build_training_data_config(
        dataset_id=dataset_id,
        symbol=symbol,
        asset_type=asset_type,
        timeframe=timeframe,
        start_date=start_date,
        end_date=end_date,
        timezone=timezone,
    )

    return HistoricalOhlcvDataset(
        config=config,
        rows=rows or [],
        source=source,
        metadata=metadata or {},
    )


def raw_rows_to_historical_ohlcv_dataset(
    *,
    dataset_id: str,
    symbol: str,
    rows: list[dict[str, Any]],
    asset_type: TrainingDataAssetType | str = TrainingDataAssetType.UNKNOWN,
    timeframe: TrainingDataTimeframe | str = TrainingDataTimeframe.H1,
    source: str = "",
    metadata: dict[str, Any] | None = None,
) -> HistoricalOhlcvDataset:
    """Convert raw OHLCV rows to dataset."""
    historical_rows = raw_rows_to_historical_ohlcv_rows(
        rows,
        symbol=symbol,
    )

    return build_historical_ohlcv_dataset(
        dataset_id=dataset_id,
        symbol=symbol,
        rows=historical_rows,
        asset_type=asset_type,
        timeframe=timeframe,
        source=source,
        metadata=metadata or {},
    )


def summarize_historical_ohlcv_dataset(
    dataset: HistoricalOhlcvDataset,
) -> HistoricalOhlcvSummary:
    """Summarize historical OHLCV dataset."""
    if not isinstance(dataset, HistoricalOhlcvDataset):
        raise ValueError("Dataset must be HistoricalOhlcvDataset.")

    closes = dataset.close_prices
    volumes = dataset.volumes

    return HistoricalOhlcvSummary(
        dataset_id=dataset.dataset_id,
        symbol=dataset.symbol,
        timeframe=dataset.timeframe,
        row_count=dataset.row_count,
        first_timestamp=dataset.first_timestamp,
        last_timestamp=dataset.last_timestamp,
        min_close=min(closes) if closes else 0.0,
        max_close=max(closes) if closes else 0.0,
        average_close=round(sum(closes) / len(closes), 10) if closes else 0.0,
        total_volume=round(sum(volumes), 10) if volumes else 0.0,
        metadata={
            "source": dataset.source,
        },
    )


def slice_historical_ohlcv_dataset(
    dataset: HistoricalOhlcvDataset,
    *,
    start_index: int = 0,
    end_index: int | None = None,
) -> HistoricalOhlcvDataset:
    """Slice historical OHLCV dataset by index."""
    if not isinstance(dataset, HistoricalOhlcvDataset):
        raise ValueError("Dataset must be HistoricalOhlcvDataset.")

    validate_non_negative_integer(start_index, "Start index")

    if end_index is not None:
        validate_non_negative_integer(end_index, "End index")

        if end_index < start_index:
            raise ValueError("End index must be greater than or equal to start index.")

    sliced_rows = dataset.rows[start_index:end_index]

    return HistoricalOhlcvDataset(
        config=dataset.config,
        rows=sliced_rows,
        source=dataset.source,
        metadata={
            **dataset.metadata,
            "slice_start_index": start_index,
            "slice_end_index": end_index,
        },
    )


def ensure_ohlcv_dataset_not_empty(dataset: HistoricalOhlcvDataset) -> HistoricalOhlcvDataset:
    """Ensure OHLCV dataset is not empty."""
    if not isinstance(dataset, HistoricalOhlcvDataset):
        raise ValueError("Dataset must be HistoricalOhlcvDataset.")

    if dataset.empty:
        raise ValueError("Historical OHLCV dataset is empty.")

    return dataset


def ohlcv_dataset_to_feature_rows(
    dataset: HistoricalOhlcvDataset,
) -> list[dict[str, Any]]:
    """Convert OHLCV dataset rows into base feature rows."""
    ensure_ohlcv_dataset_not_empty(dataset)

    return [
        {
            "timestamp": row.timestamp,
            "symbol": dataset.symbol,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume,
            "body_size": row.body_size,
            "range_size": row.range_size,
            "typical_price": row.typical_price,
            "bullish": int(row.bullish),
            "bearish": int(row.bearish),
        }
        for row in dataset.rows
    ]