"""
AQOS historical OHLCV provider adapter.

This module provides an in-memory historical OHLCV adapter contract that can be
used by CSV, HTTP, database, or real provider integrations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.providers.base import (
    ProviderCapability,
    ProviderConfig,
    ProviderResult,
    ProviderType,
    build_provider_config,
    provider_failure,
    validate_metadata,
    validate_non_empty_string,
    validate_positive_integer,
)
from aqos.providers.market_data import (
    HistoricalOhlcvRequest,
    MarketDataBatch,
    MarketDataQuality,
    MarketDataTimeframe,
    OhlcvCandle,
    build_historical_ohlcv_request,
    build_market_data_batch,
    build_ohlcv_candle,
    candles_to_ohlcv_rows,
    market_data_batch_to_provider_result,
    market_data_error_result,
    normalize_market_data_quality,
    normalize_market_data_timeframe,
    ohlcv_rows_to_candles,
    validate_market_symbol,
    validate_ohlcv_candles,
)


@dataclass(frozen=True)
class HistoricalDataCoverage:
    """Historical OHLCV data coverage summary."""

    provider_id: str
    symbol: str
    timeframe: MarketDataTimeframe | str
    start: str = ""
    end: str = ""
    count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        normalize_market_data_timeframe(self.timeframe)
        validate_string_value(self.start, "Start")
        validate_string_value(self.end, "End")
        validate_non_negative_integer(self.count, "Count")
        validate_metadata(self.metadata, "Metadata")

    @property
    def empty(self) -> bool:
        """Return whether coverage is empty."""
        return self.count == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert coverage into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "timeframe": normalize_market_data_timeframe(self.timeframe).value,
            "start": self.start.strip(),
            "end": self.end.strip(),
            "count": self.count,
            "empty": self.empty,
            "metadata": dict(self.metadata),
        }


@dataclass
class HistoricalOhlcvAdapter:
    """In-memory historical OHLCV adapter."""

    provider_config: ProviderConfig
    batches: dict[str, MarketDataBatch] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_historical_provider_config(self.provider_config)
        validate_historical_batches(self.batches)
        validate_metadata(self.metadata, "Metadata")

    @property
    def provider_id(self) -> str:
        """Return adapter provider ID."""
        return self.provider_config.provider_id.strip()

    @property
    def active(self) -> bool:
        """Return whether adapter provider is active."""
        return self.provider_config.active

    def add_batch(self, batch: MarketDataBatch) -> MarketDataBatch:
        """Add historical batch."""
        if not isinstance(batch, MarketDataBatch):
            raise ValueError("Batch must be a MarketDataBatch.")

        if batch.provider_id.strip() != self.provider_id:
            raise ValueError("Batch provider ID must match adapter provider ID.")

        self.batches[historical_batch_key(batch.symbol, batch.timeframe)] = batch
        return batch

    def add_candles(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
        candles: list[OhlcvCandle],
        quality: MarketDataQuality | str = MarketDataQuality.RAW,
        metadata: dict[str, Any] | None = None,
    ) -> MarketDataBatch:
        """Add candles as a historical batch."""
        validate_ohlcv_candles(candles)

        batch = build_market_data_batch(
            provider_id=self.provider_id,
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            quality=quality,
            metadata=metadata or {},
        )

        return self.add_batch(batch)

    def add_rows(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
        rows: list[dict[str, Any]],
        quality: MarketDataQuality | str = MarketDataQuality.RAW,
        metadata: dict[str, Any] | None = None,
    ) -> MarketDataBatch:
        """Add OHLCV rows as a historical batch."""
        batch = historical_batch_from_rows(
            provider_id=self.provider_id,
            symbol=symbol,
            timeframe=timeframe,
            rows=rows,
            quality=quality,
            metadata=metadata or {},
        )

        return self.add_batch(batch)

    def get_batch(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
    ) -> MarketDataBatch | None:
        """Get historical batch."""
        return self.batches.get(historical_batch_key(symbol, timeframe))

    def has_data(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
    ) -> bool:
        """Return whether adapter has data for symbol/timeframe."""
        batch = self.get_batch(symbol=symbol, timeframe=timeframe)
        return batch is not None and not batch.empty

    def fetch(self, request: HistoricalOhlcvRequest) -> ProviderResult:
        """Fetch historical OHLCV data."""
        if not isinstance(request, HistoricalOhlcvRequest):
            raise ValueError("Request must be a HistoricalOhlcvRequest.")

        if request.provider_id.strip() != self.provider_id:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Request provider ID does not match adapter provider ID.",
                request_type="historical_ohlcv",
                metadata={
                    "request_provider_id": request.provider_id.strip(),
                },
            )

        if not self.active:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Historical OHLCV provider is not active.",
                request_type="historical_ohlcv",
            )

        batch = self.get_batch(
            symbol=request.symbol,
            timeframe=request.timeframe,
        )

        if batch is None:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Historical OHLCV data not found.",
                request_type="historical_ohlcv",
                metadata={
                    "symbol": validate_market_symbol(request.symbol),
                    "timeframe": normalize_market_data_timeframe(request.timeframe).value,
                },
            )

        filtered_candles = filter_historical_candles(
            candles=batch.candles,
            start=request.start,
            end=request.end,
            limit=request.limit,
        )

        result_batch = build_market_data_batch(
            provider_id=self.provider_id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            candles=filtered_candles,
            quality=batch.quality,
            metadata={
                **batch.metadata,
                "request": request.to_dict(),
            },
        )

        return market_data_batch_to_provider_result(result_batch)

    def latest_candle(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
    ) -> OhlcvCandle | None:
        """Return latest candle for symbol/timeframe."""
        batch = self.get_batch(symbol=symbol, timeframe=timeframe)

        if batch is None or batch.empty:
            return None

        return batch.candles[-1]

    def close_prices(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
    ) -> list[float]:
        """Return close prices for symbol/timeframe."""
        batch = self.get_batch(symbol=symbol, timeframe=timeframe)

        if batch is None:
            return []

        return batch.close_prices()

    def list_batches(self) -> list[MarketDataBatch]:
        """List all historical batches."""
        return list(self.batches.values())

    def list_symbols(self) -> list[str]:
        """List available symbols."""
        return sorted(
            {
                validate_market_symbol(batch.symbol)
                for batch in self.batches.values()
            },
        )

    def list_timeframes(self, symbol: str | None = None) -> list[str]:
        """List available timeframes."""
        batches = self.batches.values()

        if symbol is not None:
            normalized_symbol = validate_market_symbol(symbol)
            batches = [
                batch
                for batch in batches
                if validate_market_symbol(batch.symbol) == normalized_symbol
            ]

        return sorted(
            {
                normalize_market_data_timeframe(batch.timeframe).value
                for batch in batches
            },
        )

    def coverage(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
    ) -> HistoricalDataCoverage:
        """Return historical data coverage."""
        batch = self.get_batch(symbol=symbol, timeframe=timeframe)

        if batch is None:
            return build_historical_data_coverage(
                provider_id=self.provider_id,
                symbol=symbol,
                timeframe=timeframe,
            )

        return build_historical_data_coverage(
            provider_id=self.provider_id,
            symbol=batch.symbol,
            timeframe=batch.timeframe,
            start=batch.first_timestamp,
            end=batch.latest_timestamp,
            count=batch.count,
            metadata=batch.metadata,
        )

    def clear(self) -> None:
        """Clear all historical batches."""
        self.batches.clear()

    def count(self) -> int:
        """Return batch count."""
        return len(self.batches)


def validate_string_value(value: str, field_name: str) -> str:
    """Validate string value."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    return value


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_historical_provider_config(config: ProviderConfig) -> ProviderConfig:
    """Validate historical OHLCV provider config."""
    if not isinstance(config, ProviderConfig):
        raise ValueError("Provider config must be ProviderConfig.")

    if config.provider_type != ProviderType.MARKET_DATA and str(config.provider_type) != ProviderType.MARKET_DATA.value:
        raise ValueError("Historical adapter requires a market data provider config.")

    if not config.supports(ProviderCapability.HISTORICAL_OHLCV):
        raise ValueError("Provider config must support historical OHLCV.")

    return config


def validate_historical_batches(
    batches: dict[str, MarketDataBatch],
) -> dict[str, MarketDataBatch]:
    """Validate historical batch dictionary."""
    if not isinstance(batches, dict):
        raise ValueError("Batches must be a dictionary.")

    for key, batch in batches.items():
        validate_non_empty_string(key, "Batch key")

        if not isinstance(batch, MarketDataBatch):
            raise ValueError("Batches must contain MarketDataBatch objects.")

    return batches


def historical_batch_key(
    symbol: str,
    timeframe: MarketDataTimeframe | str,
) -> str:
    """Build historical batch key."""
    return f"{validate_market_symbol(symbol)}::{normalize_market_data_timeframe(timeframe).value}"


def build_historical_data_coverage(
    *,
    provider_id: str,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    start: str = "",
    end: str = "",
    count: int = 0,
    metadata: dict[str, Any] | None = None,
) -> HistoricalDataCoverage:
    """Build historical data coverage."""
    return HistoricalDataCoverage(
        provider_id=provider_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        count=count,
        metadata=metadata or {},
    )


def build_historical_ohlcv_adapter(
    *,
    provider_config: ProviderConfig | None = None,
    provider_id: str = "local-historical",
    name: str = "Local Historical OHLCV Provider",
    batches: dict[str, MarketDataBatch] | None = None,
    metadata: dict[str, Any] | None = None,
) -> HistoricalOhlcvAdapter:
    """Build historical OHLCV adapter."""
    resolved_config = provider_config or build_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=ProviderType.MARKET_DATA,
        capabilities=[ProviderCapability.HISTORICAL_OHLCV],
    )

    return HistoricalOhlcvAdapter(
        provider_config=resolved_config,
        batches=batches or {},
        metadata=metadata or {},
    )


def build_historical_batch_request(
    *,
    adapter: HistoricalOhlcvAdapter,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    start: str = "",
    end: str = "",
    limit: int = 500,
    metadata: dict[str, Any] | None = None,
) -> HistoricalOhlcvRequest:
    """Build historical request for adapter."""
    if not isinstance(adapter, HistoricalOhlcvAdapter):
        raise ValueError("Adapter must be a HistoricalOhlcvAdapter.")

    return build_historical_ohlcv_request(
        provider_id=adapter.provider_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
        metadata=metadata or {},
    )


def historical_batch_from_rows(
    *,
    provider_id: str,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    rows: list[dict[str, Any]],
    quality: MarketDataQuality | str = MarketDataQuality.RAW,
    metadata: dict[str, Any] | None = None,
) -> MarketDataBatch:
    """Build historical market data batch from rows."""
    candles = ohlcv_rows_to_candles(
        rows=rows,
        symbol=symbol,
        timeframe=timeframe,
        quality=quality,
    )

    return build_market_data_batch(
        provider_id=provider_id,
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        quality=quality,
        metadata=metadata or {},
    )


def historical_batch_to_rows(batch: MarketDataBatch) -> list[dict[str, Any]]:
    """Convert historical batch into rows."""
    if not isinstance(batch, MarketDataBatch):
        raise ValueError("Batch must be a MarketDataBatch.")

    return candles_to_ohlcv_rows(batch.candles)


def filter_historical_candles(
    *,
    candles: list[OhlcvCandle],
    start: str = "",
    end: str = "",
    limit: int = 500,
) -> list[OhlcvCandle]:
    """Filter historical candles by timestamp range and limit."""
    validate_ohlcv_candles(candles)
    validate_string_value(start, "Start")
    validate_string_value(end, "End")
    validate_positive_integer(limit, "Limit")

    filtered = list(candles)

    if start.strip():
        filtered = [
            candle
            for candle in filtered
            if candle.timestamp.strip() >= start.strip()
        ]

    if end.strip():
        filtered = [
            candle
            for candle in filtered
            if candle.timestamp.strip() <= end.strip()
        ]

    return filtered[:limit]


def fetch_historical_ohlcv(
    *,
    adapter: HistoricalOhlcvAdapter,
    request: HistoricalOhlcvRequest,
) -> ProviderResult:
    """Fetch historical OHLCV data from adapter."""
    if not isinstance(adapter, HistoricalOhlcvAdapter):
        raise ValueError("Adapter must be a HistoricalOhlcvAdapter.")

    return adapter.fetch(request)


def create_sample_historical_adapter(
    *,
    provider_id: str = "sample-historical",
    symbol: str = "XAUUSD",
    timeframe: MarketDataTimeframe | str = MarketDataTimeframe.H1,
) -> HistoricalOhlcvAdapter:
    """Create sample historical adapter for tests/examples."""
    adapter = build_historical_ohlcv_adapter(provider_id=provider_id)
    candles = [
        build_ohlcv_candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp="2026-01-01T00:00:00+00:00",
            open=2000,
            high=2010,
            low=1990,
            close=2005,
            volume=100,
            quality=MarketDataQuality.VALIDATED,
        ),
        build_ohlcv_candle(
            symbol=symbol,
            timeframe=timeframe,
            timestamp="2026-01-01T01:00:00+00:00",
            open=2005,
            high=2020,
            low=2000,
            close=2015,
            volume=120,
            quality=MarketDataQuality.VALIDATED,
        ),
    ]
    adapter.add_candles(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        quality=MarketDataQuality.VALIDATED,
    )

    return adapter