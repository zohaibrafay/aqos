"""
AQOS provider integration helpers.

This module connects provider adapters, provider registry, and AQOS-friendly
market data payloads without forcing a hard dependency on service internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.providers.base import (
    ProviderResult,
    provider_failure,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)
from aqos.providers.historical import (
    HistoricalOhlcvAdapter,
    build_historical_batch_request,
    create_sample_historical_adapter,
    fetch_historical_ohlcv,
)
from aqos.providers.live import (
    LiveMarketDataAdapter,
    build_live_quote_request_for_adapter,
    build_tick_data_request_for_adapter,
    create_sample_live_adapter,
    fetch_live_quote,
    fetch_market_ticks,
)
from aqos.providers.market_data import (
    MarketDataBatch,
    MarketDataPriceType,
    MarketDataTimeframe,
    MarketQuote,
    MarketTick,
    candles_to_ohlcv_rows,
    validate_market_data_limit,
    validate_market_symbol,
)
from aqos.providers.registry import (
    ProviderRegistry,
    ProviderRegistryEntry,
    build_provider_registry,
    resolve_historical_adapter,
    resolve_live_adapter,
    validate_provider_registry,
)


INTEGRATION_PROVIDER_ID = "provider-integration"


@dataclass(frozen=True)
class AqosMarketDataPayload:
    """AQOS-friendly market data payload."""

    provider_id: str
    symbol: str
    timeframe: str = ""
    rows: list[dict[str, Any]] = field(default_factory=list)
    quote: dict[str, Any] = field(default_factory=dict)
    ticks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        validate_string(self.timeframe, "Timeframe")
        validate_aqos_market_data_rows(self.rows)
        validate_metadata(self.quote, "Quote")
        validate_aqos_market_data_ticks(self.ticks)
        validate_metadata(self.metadata, "Metadata")

    @property
    def row_count(self) -> int:
        """Return row count."""
        return len(self.rows)

    @property
    def tick_count(self) -> int:
        """Return tick count."""
        return len(self.ticks)

    @property
    def has_quote(self) -> bool:
        """Return whether payload has quote data."""
        return bool(self.quote)

    @property
    def latest_close(self) -> float:
        """Return latest close from rows."""
        if not self.rows:
            return 0.0

        return float(self.rows[-1].get("close", 0.0))

    def to_dict(self) -> dict[str, Any]:
        """Convert payload into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "timeframe": self.timeframe.strip(),
            "rows": [dict(row) for row in self.rows],
            "quote": dict(self.quote),
            "ticks": [dict(tick) for tick in self.ticks],
            "row_count": self.row_count,
            "tick_count": self.tick_count,
            "has_quote": self.has_quote,
            "latest_close": self.latest_close,
            "metadata": dict(self.metadata),
        }


@dataclass
class ProviderIntegrationHub:
    """Provider integration hub."""

    registry: ProviderRegistry = field(default_factory=build_provider_registry)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_provider_registry(self.registry)
        validate_metadata(self.metadata, "Metadata")

    def fetch_historical(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
        start: str = "",
        end: str = "",
        limit: int = 500,
    ) -> ProviderResult:
        """Fetch historical market data through registered adapter."""
        adapter = resolve_historical_adapter(self.registry)

        if adapter is None:
            return integration_failure(
                error="Historical adapter is not registered.",
                operation="fetch_historical",
            )

        request = build_historical_batch_request(
            adapter=adapter,
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )

        return fetch_historical_ohlcv(
            adapter=adapter,
            request=request,
        )

    def fetch_quote(
        self,
        *,
        symbol: str,
        price_type: MarketDataPriceType | str = MarketDataPriceType.MID,
    ) -> ProviderResult:
        """Fetch live quote through registered adapter."""
        adapter = resolve_live_adapter(self.registry)

        if adapter is None:
            return integration_failure(
                error="Live adapter is not registered.",
                operation="fetch_quote",
            )

        request = build_live_quote_request_for_adapter(
            adapter=adapter,
            symbol=symbol,
            price_type=price_type,
        )

        return fetch_live_quote(
            adapter=adapter,
            request=request,
        )

    def fetch_ticks(
        self,
        *,
        symbol: str,
        limit: int = 100,
    ) -> ProviderResult:
        """Fetch live ticks through registered adapter."""
        adapter = resolve_live_adapter(self.registry)

        if adapter is None:
            return integration_failure(
                error="Live adapter is not registered.",
                operation="fetch_ticks",
            )

        request = build_tick_data_request_for_adapter(
            adapter=adapter,
            symbol=symbol,
            limit=limit,
        )

        return fetch_market_ticks(
            adapter=adapter,
            request=request,
        )

    def historical_payload(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
        start: str = "",
        end: str = "",
        limit: int = 500,
    ) -> AqosMarketDataPayload | None:
        """Fetch historical data and convert it into AQOS payload."""
        result = self.fetch_historical(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
            limit=limit,
        )

        if result.failed:
            return None

        batch = provider_result_batch(result)

        if batch is None:
            return None

        return build_aqos_market_data_payload(
            provider_id=str(batch["provider_id"]),
            symbol=str(batch["symbol"]),
            timeframe=str(batch["timeframe"]),
            rows=[
                {
                    "timestamp": candle["timestamp"],
                    "open": candle["open"],
                    "high": candle["high"],
                    "low": candle["low"],
                    "close": candle["close"],
                    "volume": candle.get("volume", 0.0),
                }
                for candle in batch.get("candles", [])
            ],
            metadata={
                "source": "historical_provider",
                "result_provider_id": result.provider_id,
            },
        )

    def combined_payload(
        self,
        *,
        symbol: str,
        timeframe: MarketDataTimeframe | str,
        historical_limit: int = 500,
        tick_limit: int = 100,
    ) -> AqosMarketDataPayload | None:
        """Build combined historical, quote, and tick payload."""
        historical_payload = self.historical_payload(
            symbol=symbol,
            timeframe=timeframe,
            limit=historical_limit,
        )

        if historical_payload is None:
            return None

        quote_result = self.fetch_quote(symbol=symbol)
        ticks_result = self.fetch_ticks(symbol=symbol, limit=tick_limit)

        quote = provider_result_quote(quote_result) or {}
        ticks = provider_result_ticks(ticks_result) or []

        return build_aqos_market_data_payload(
            provider_id=historical_payload.provider_id,
            symbol=historical_payload.symbol,
            timeframe=historical_payload.timeframe,
            rows=historical_payload.rows,
            quote=quote,
            ticks=ticks,
            metadata={
                **historical_payload.metadata,
                "source": "combined_provider_payload",
            },
        )

    def summary(self) -> dict[str, Any]:
        """Return integration hub summary."""
        return {
            "provider_id": INTEGRATION_PROVIDER_ID,
            "registry": self.registry.summary().to_dict(),
            "metadata": dict(self.metadata),
        }


def validate_aqos_market_data_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate AQOS market data rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        validate_metadata(row, "Market data row")

    return rows


def validate_aqos_market_data_ticks(ticks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate AQOS market data ticks."""
    if not isinstance(ticks, list):
        raise ValueError("Ticks must be a list.")

    for tick in ticks:
        validate_metadata(tick, "Market data tick")

    return ticks


def validate_provider_integration_hub(
    hub: ProviderIntegrationHub,
) -> ProviderIntegrationHub:
    """Validate provider integration hub."""
    if not isinstance(hub, ProviderIntegrationHub):
        raise ValueError("Hub must be a ProviderIntegrationHub.")

    return hub


def build_aqos_market_data_payload(
    *,
    provider_id: str,
    symbol: str,
    timeframe: str = "",
    rows: list[dict[str, Any]] | None = None,
    quote: dict[str, Any] | None = None,
    ticks: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AqosMarketDataPayload:
    """Build AQOS market data payload."""
    return AqosMarketDataPayload(
        provider_id=provider_id,
        symbol=symbol,
        timeframe=timeframe,
        rows=rows or [],
        quote=quote or {},
        ticks=ticks or [],
        metadata=metadata or {},
    )


def market_data_batch_to_service_payload(
    *,
    batch: MarketDataBatch,
    quote: MarketQuote | None = None,
    ticks: list[MarketTick] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AqosMarketDataPayload:
    """Convert market data batch into AQOS service payload."""
    if not isinstance(batch, MarketDataBatch):
        raise ValueError("Batch must be a MarketDataBatch.")

    resolved_ticks = ticks or []

    for tick in resolved_ticks:
        if not isinstance(tick, MarketTick):
            raise ValueError("Ticks must contain MarketTick objects.")

    if quote is not None and not isinstance(quote, MarketQuote):
        raise ValueError("Quote must be a MarketQuote.")

    return build_aqos_market_data_payload(
        provider_id=batch.provider_id,
        symbol=batch.symbol,
        timeframe=str(batch.timeframe),
        rows=candles_to_ohlcv_rows(batch.candles),
        quote=quote.to_dict() if quote is not None else {},
        ticks=[tick.to_dict() for tick in resolved_ticks],
        metadata=metadata or {},
    )


def provider_result_batch(result: ProviderResult) -> dict[str, Any] | None:
    """Extract batch payload from provider result."""
    if not isinstance(result, ProviderResult):
        raise ValueError("Result must be a ProviderResult.")

    if result.failed:
        return None

    batch = result.data.get("batch")

    if batch is None:
        return None

    validate_metadata(batch, "Batch payload")
    return batch


def provider_result_quote(result: ProviderResult) -> dict[str, Any] | None:
    """Extract quote payload from provider result."""
    if not isinstance(result, ProviderResult):
        raise ValueError("Result must be a ProviderResult.")

    if result.failed:
        return None

    quote = result.data.get("quote")

    if quote is None:
        return None

    validate_metadata(quote, "Quote payload")
    return quote


def provider_result_ticks(result: ProviderResult) -> list[dict[str, Any]] | None:
    """Extract ticks payload from provider result."""
    if not isinstance(result, ProviderResult):
        raise ValueError("Result must be a ProviderResult.")

    if result.failed:
        return None

    ticks = result.data.get("ticks")

    if ticks is None:
        return None

    validate_aqos_market_data_ticks(ticks)
    return ticks


def register_historical_adapter(
    *,
    registry: ProviderRegistry,
    adapter: HistoricalOhlcvAdapter,
    metadata: dict[str, Any] | None = None,
) -> ProviderRegistryEntry:
    """Register historical adapter."""
    validate_provider_registry(registry)

    if not isinstance(adapter, HistoricalOhlcvAdapter):
        raise ValueError("Adapter must be a HistoricalOhlcvAdapter.")

    return registry.register_adapter(
        config=adapter.provider_config,
        adapter=adapter,
        metadata=metadata or {},
    )


def register_live_adapter(
    *,
    registry: ProviderRegistry,
    adapter: LiveMarketDataAdapter,
    metadata: dict[str, Any] | None = None,
) -> ProviderRegistryEntry:
    """Register live adapter."""
    validate_provider_registry(registry)

    if not isinstance(adapter, LiveMarketDataAdapter):
        raise ValueError("Adapter must be a LiveMarketDataAdapter.")

    return registry.register_adapter(
        config=adapter.provider_config,
        adapter=adapter,
        metadata=metadata or {},
    )


def build_provider_integration_hub(
    *,
    registry: ProviderRegistry | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProviderIntegrationHub:
    """Build provider integration hub."""
    return ProviderIntegrationHub(
        registry=registry or build_provider_registry(),
        metadata=metadata or {},
    )


def build_sample_provider_registry(
    *,
    symbol: str = "XAUUSD",
    timeframe: MarketDataTimeframe | str = MarketDataTimeframe.H1,
) -> ProviderRegistry:
    """Build registry with sample historical and live adapters."""
    registry = build_provider_registry()

    historical_adapter = create_sample_historical_adapter(
        provider_id="sample-historical",
        symbol=symbol,
        timeframe=timeframe,
    )
    live_adapter = create_sample_live_adapter(
        provider_id="sample-live",
        symbol=symbol,
    )

    register_historical_adapter(
        registry=registry,
        adapter=historical_adapter,
    )
    register_live_adapter(
        registry=registry,
        adapter=live_adapter,
    )

    return registry


def build_sample_provider_integration_hub(
    *,
    symbol: str = "XAUUSD",
    timeframe: MarketDataTimeframe | str = MarketDataTimeframe.H1,
) -> ProviderIntegrationHub:
    """Build sample provider integration hub."""
    return build_provider_integration_hub(
        registry=build_sample_provider_registry(
            symbol=symbol,
            timeframe=timeframe,
        ),
        metadata={
            "sample": True,
        },
    )


def fetch_historical_market_data(
    *,
    hub: ProviderIntegrationHub,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    start: str = "",
    end: str = "",
    limit: int = 500,
) -> ProviderResult:
    """Fetch historical market data through hub."""
    validate_provider_integration_hub(hub)
    validate_market_data_limit(limit)

    return hub.fetch_historical(
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
    )


def fetch_live_market_quote(
    *,
    hub: ProviderIntegrationHub,
    symbol: str,
    price_type: MarketDataPriceType | str = MarketDataPriceType.MID,
) -> ProviderResult:
    """Fetch live market quote through hub."""
    validate_provider_integration_hub(hub)

    return hub.fetch_quote(
        symbol=symbol,
        price_type=price_type,
    )


def fetch_live_market_ticks(
    *,
    hub: ProviderIntegrationHub,
    symbol: str,
    limit: int = 100,
) -> ProviderResult:
    """Fetch live market ticks through hub."""
    validate_provider_integration_hub(hub)
    validate_market_data_limit(limit)

    return hub.fetch_ticks(
        symbol=symbol,
        limit=limit,
    )


def integration_failure(
    *,
    error: str,
    operation: str,
) -> ProviderResult:
    """Build integration failure result."""
    return provider_failure(
        provider_id=INTEGRATION_PROVIDER_ID,
        error=error,
        message="Provider integration operation failed.",
        metadata={
            "operation": validate_non_empty_string(operation, "Operation"),
        },
    )