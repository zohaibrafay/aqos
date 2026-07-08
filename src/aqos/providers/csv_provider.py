"""
AQOS local CSV market data provider.

This module provides dependency-free CSV helpers for loading local OHLCV data
into the historical market data adapter.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aqos.providers.base import (
    ProviderCapability,
    ProviderConfig,
    ProviderType,
    build_provider_config,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)
from aqos.providers.historical import (
    HistoricalOhlcvAdapter,
    build_historical_ohlcv_adapter,
    historical_batch_from_rows,
)
from aqos.providers.market_data import (
    MarketDataBatch,
    MarketDataQuality,
    MarketDataTimeframe,
    candles_to_ohlcv_rows,
    validate_market_symbol,
)


DEFAULT_CSV_TIMESTAMP_COLUMN = "timestamp"
DEFAULT_CSV_OPEN_COLUMN = "open"
DEFAULT_CSV_HIGH_COLUMN = "high"
DEFAULT_CSV_LOW_COLUMN = "low"
DEFAULT_CSV_CLOSE_COLUMN = "close"
DEFAULT_CSV_VOLUME_COLUMN = "volume"


@dataclass(frozen=True)
class CsvOhlcvColumnMap:
    """CSV OHLCV column mapping."""

    timestamp: str = DEFAULT_CSV_TIMESTAMP_COLUMN
    open: str = DEFAULT_CSV_OPEN_COLUMN
    high: str = DEFAULT_CSV_HIGH_COLUMN
    low: str = DEFAULT_CSV_LOW_COLUMN
    close: str = DEFAULT_CSV_CLOSE_COLUMN
    volume: str = DEFAULT_CSV_VOLUME_COLUMN

    def __post_init__(self) -> None:
        validate_non_empty_string(self.timestamp, "Timestamp column")
        validate_non_empty_string(self.open, "Open column")
        validate_non_empty_string(self.high, "High column")
        validate_non_empty_string(self.low, "Low column")
        validate_non_empty_string(self.close, "Close column")
        validate_non_empty_string(self.volume, "Volume column")

    @property
    def required_columns(self) -> list[str]:
        """Return required OHLC columns."""
        return [
            self.timestamp.strip(),
            self.open.strip(),
            self.high.strip(),
            self.low.strip(),
            self.close.strip(),
        ]

    @property
    def all_columns(self) -> list[str]:
        """Return all mapped columns."""
        return [
            self.timestamp.strip(),
            self.open.strip(),
            self.high.strip(),
            self.low.strip(),
            self.close.strip(),
            self.volume.strip(),
        ]

    def to_dict(self) -> dict[str, str]:
        """Convert column map into dictionary."""
        return {
            "timestamp": self.timestamp.strip(),
            "open": self.open.strip(),
            "high": self.high.strip(),
            "low": self.low.strip(),
            "close": self.close.strip(),
            "volume": self.volume.strip(),
        }


@dataclass(frozen=True)
class CsvOhlcvLoadRequest:
    """CSV OHLCV load request."""

    file_path: str
    symbol: str
    timeframe: MarketDataTimeframe | str
    provider_id: str = "csv-local"
    column_map: CsvOhlcvColumnMap = field(default_factory=CsvOhlcvColumnMap)
    quality: MarketDataQuality | str = MarketDataQuality.RAW
    delimiter: str = ","
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.file_path, "File path")
        validate_market_symbol(self.symbol)
        validate_non_empty_string(self.provider_id, "Provider ID")

        if not isinstance(self.column_map, CsvOhlcvColumnMap):
            raise ValueError("Column map must be a CsvOhlcvColumnMap.")

        validate_string(self.delimiter, "Delimiter")

        if len(self.delimiter) != 1:
            raise ValueError("Delimiter must be a single character.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert load request into dictionary."""
        return {
            "file_path": self.file_path.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "timeframe": str(self.timeframe).strip(),
            "provider_id": self.provider_id.strip(),
            "column_map": self.column_map.to_dict(),
            "quality": str(self.quality).strip(),
            "delimiter": self.delimiter,
            "metadata": dict(self.metadata),
        }


@dataclass
class LocalCsvOhlcvProvider:
    """Local CSV OHLCV provider."""

    provider_config: ProviderConfig = field(
        default_factory=lambda: build_provider_config(
            provider_id="csv-local",
            name="Local CSV OHLCV Provider",
            provider_type=ProviderType.MARKET_DATA,
            capabilities=[ProviderCapability.HISTORICAL_OHLCV],
        ),
    )
    adapter: HistoricalOhlcvAdapter | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.provider_config, ProviderConfig):
            raise ValueError("Provider config must be ProviderConfig.")

        if self.adapter is not None and not isinstance(self.adapter, HistoricalOhlcvAdapter):
            raise ValueError("Adapter must be a HistoricalOhlcvAdapter.")

        validate_metadata(self.metadata, "Metadata")

        if self.adapter is None:
            self.adapter = build_historical_ohlcv_adapter(
                provider_config=self.provider_config,
            )

    @property
    def provider_id(self) -> str:
        """Return provider ID."""
        return self.provider_config.provider_id.strip()

    def load(self, request: CsvOhlcvLoadRequest) -> MarketDataBatch:
        """Load CSV OHLCV data into adapter."""
        if not isinstance(request, CsvOhlcvLoadRequest):
            raise ValueError("Request must be a CsvOhlcvLoadRequest.")

        if request.provider_id.strip() != self.provider_id:
            raise ValueError("Request provider ID must match CSV provider ID.")

        rows = read_ohlcv_csv_rows(
            file_path=request.file_path,
            column_map=request.column_map,
            delimiter=request.delimiter,
        )

        batch = historical_batch_from_rows(
            provider_id=self.provider_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            rows=rows,
            quality=request.quality,
            metadata={
                **request.metadata,
                "source_file": str(Path(request.file_path)),
                "row_count": len(rows),
            },
        )

        assert self.adapter is not None
        self.adapter.add_batch(batch)
        return batch

    def load_file(
        self,
        *,
        file_path: str,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
        column_map: CsvOhlcvColumnMap | None = None,
        quality: MarketDataQuality | str = MarketDataQuality.RAW,
        delimiter: str = ",",
        metadata: dict[str, Any] | None = None,
    ) -> MarketDataBatch:
        """Load CSV file into adapter."""
        request = build_csv_ohlcv_load_request(
            file_path=file_path,
            symbol=symbol,
            timeframe=timeframe,
            provider_id=self.provider_id,
            column_map=column_map,
            quality=quality,
            delimiter=delimiter,
            metadata=metadata or {},
        )

        return self.load(request)

    def export_batch(
        self,
        *,
        batch: MarketDataBatch,
        file_path: str,
        delimiter: str = ",",
    ) -> Path:
        """Export OHLCV batch to CSV file."""
        return write_ohlcv_csv_rows(
            file_path=file_path,
            rows=candles_to_ohlcv_rows(batch.candles),
            delimiter=delimiter,
        )

    def get_adapter(self) -> HistoricalOhlcvAdapter:
        """Return historical adapter."""
        assert self.adapter is not None
        return self.adapter


def build_csv_ohlcv_column_map(
    *,
    timestamp: str = DEFAULT_CSV_TIMESTAMP_COLUMN,
    open: str = DEFAULT_CSV_OPEN_COLUMN,
    high: str = DEFAULT_CSV_HIGH_COLUMN,
    low: str = DEFAULT_CSV_LOW_COLUMN,
    close: str = DEFAULT_CSV_CLOSE_COLUMN,
    volume: str = DEFAULT_CSV_VOLUME_COLUMN,
) -> CsvOhlcvColumnMap:
    """Build CSV OHLCV column map."""
    return CsvOhlcvColumnMap(
        timestamp=timestamp,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
    )


def build_csv_ohlcv_load_request(
    *,
    file_path: str,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    provider_id: str = "csv-local",
    column_map: CsvOhlcvColumnMap | None = None,
    quality: MarketDataQuality | str = MarketDataQuality.RAW,
    delimiter: str = ",",
    metadata: dict[str, Any] | None = None,
) -> CsvOhlcvLoadRequest:
    """Build CSV OHLCV load request."""
    return CsvOhlcvLoadRequest(
        file_path=file_path,
        symbol=symbol,
        timeframe=timeframe,
        provider_id=provider_id,
        column_map=column_map or CsvOhlcvColumnMap(),
        quality=quality,
        delimiter=delimiter,
        metadata=metadata or {},
    )


def build_local_csv_ohlcv_provider(
    *,
    provider_config: ProviderConfig | None = None,
    provider_id: str = "csv-local",
    name: str = "Local CSV OHLCV Provider",
    adapter: HistoricalOhlcvAdapter | None = None,
    metadata: dict[str, Any] | None = None,
) -> LocalCsvOhlcvProvider:
    """Build local CSV OHLCV provider."""
    resolved_config = provider_config or build_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=ProviderType.MARKET_DATA,
        capabilities=[ProviderCapability.HISTORICAL_OHLCV],
    )

    return LocalCsvOhlcvProvider(
        provider_config=resolved_config,
        adapter=adapter,
        metadata=metadata or {},
    )


def validate_csv_file_path(file_path: str) -> Path:
    """Validate CSV file path exists."""
    normalized_file_path = validate_non_empty_string(file_path, "File path")
    path = Path(normalized_file_path)

    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    if not path.is_file():
        raise ValueError(f"CSV path is not a file: {path}")

    return path


def validate_csv_columns(
    *,
    fieldnames: list[str] | None,
    column_map: CsvOhlcvColumnMap,
) -> list[str]:
    """Validate required CSV columns."""
    if fieldnames is None:
        raise ValueError("CSV file must contain a header row.")

    if not isinstance(column_map, CsvOhlcvColumnMap):
        raise ValueError("Column map must be a CsvOhlcvColumnMap.")

    missing = [
        column
        for column in column_map.required_columns
        if column not in fieldnames
    ]

    if missing:
        raise ValueError(f"CSV file is missing required columns: {', '.join(missing)}.")

    return fieldnames


def normalize_csv_ohlcv_row(
    *,
    row: dict[str, Any],
    column_map: CsvOhlcvColumnMap,
) -> dict[str, Any]:
    """Normalize a CSV row into OHLCV row format."""
    validate_metadata(row, "CSV row")

    if not isinstance(column_map, CsvOhlcvColumnMap):
        raise ValueError("Column map must be a CsvOhlcvColumnMap.")

    return {
        "timestamp": str(row[column_map.timestamp]).strip(),
        "open": float(row[column_map.open]),
        "high": float(row[column_map.high]),
        "low": float(row[column_map.low]),
        "close": float(row[column_map.close]),
        "volume": float(row.get(column_map.volume, 0.0) or 0.0),
    }


def read_ohlcv_csv_rows(
    *,
    file_path: str,
    column_map: CsvOhlcvColumnMap | None = None,
    delimiter: str = ",",
) -> list[dict[str, Any]]:
    """Read OHLCV CSV rows."""
    path = validate_csv_file_path(file_path)
    resolved_column_map = column_map or CsvOhlcvColumnMap()

    if len(delimiter) != 1:
        raise ValueError("Delimiter must be a single character.")

    rows: list[dict[str, Any]] = []

    with path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file, delimiter=delimiter)
        validate_csv_columns(
            fieldnames=reader.fieldnames,
            column_map=resolved_column_map,
        )

        for row in reader:
            rows.append(
                normalize_csv_ohlcv_row(
                    row=row,
                    column_map=resolved_column_map,
                ),
            )

    return rows


def write_ohlcv_csv_rows(
    *,
    file_path: str,
    rows: list[dict[str, Any]],
    delimiter: str = ",",
) -> Path:
    """Write OHLCV rows to CSV file."""
    normalized_file_path = validate_non_empty_string(file_path, "File path")
    path = Path(normalized_file_path)

    if len(delimiter) != 1:
        raise ValueError("Delimiter must be a single character.")

    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        DEFAULT_CSV_TIMESTAMP_COLUMN,
        DEFAULT_CSV_OPEN_COLUMN,
        DEFAULT_CSV_HIGH_COLUMN,
        DEFAULT_CSV_LOW_COLUMN,
        DEFAULT_CSV_CLOSE_COLUMN,
        DEFAULT_CSV_VOLUME_COLUMN,
    ]

    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()

        for row in rows:
            validate_metadata(row, "OHLCV row")
            writer.writerow(
                {
                    DEFAULT_CSV_TIMESTAMP_COLUMN: row["timestamp"],
                    DEFAULT_CSV_OPEN_COLUMN: row["open"],
                    DEFAULT_CSV_HIGH_COLUMN: row["high"],
                    DEFAULT_CSV_LOW_COLUMN: row["low"],
                    DEFAULT_CSV_CLOSE_COLUMN: row["close"],
                    DEFAULT_CSV_VOLUME_COLUMN: row.get("volume", 0.0),
                },
            )

    return path


def load_csv_ohlcv_into_adapter(
    *,
    adapter: HistoricalOhlcvAdapter,
    file_path: str,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    column_map: CsvOhlcvColumnMap | None = None,
    quality: MarketDataQuality | str = MarketDataQuality.RAW,
    delimiter: str = ",",
    metadata: dict[str, Any] | None = None,
) -> MarketDataBatch:
    """Load CSV OHLCV data into an existing adapter."""
    if not isinstance(adapter, HistoricalOhlcvAdapter):
        raise ValueError("Adapter must be a HistoricalOhlcvAdapter.")

    provider = build_local_csv_ohlcv_provider(
        provider_config=adapter.provider_config,
        adapter=adapter,
    )

    return provider.load_file(
        file_path=file_path,
        symbol=symbol,
        timeframe=timeframe,
        column_map=column_map,
        quality=quality,
        delimiter=delimiter,
        metadata=metadata or {},
    )