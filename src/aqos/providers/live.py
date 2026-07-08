"""
AQOS live market data provider adapter.

This module provides an in-memory live quote and tick adapter contract that can
be used by websocket, polling HTTP, broker, exchange, or local test providers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.providers.base import (
    ProviderCapability,
    ProviderConfig,
    ProviderResult,
    ProviderStatus,
    ProviderType,
    build_provider_config,
    validate_metadata,
    validate_non_empty_string,
)
from aqos.providers.market_data import (
    LiveQuoteRequest,
    MarketDataPriceType,
    MarketQuote,
    MarketTick,
    TickDataRequest,
    build_live_quote_request,
    build_market_quote,
    build_market_tick,
    build_tick_data_request,
    market_data_error_result,
    market_quote_to_provider_result,
    market_ticks_to_provider_result,
    normalize_market_data_price_type,
    validate_market_data_limit,
    validate_market_symbol,
    validate_market_ticks,
)


@dataclass(frozen=True)
class LiveMarketDataSnapshot:
    """Live market data snapshot."""

    provider_id: str
    quotes: list[MarketQuote] = field(default_factory=list)
    ticks: list[MarketTick] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_quotes(self.quotes)
        validate_market_ticks(self.ticks)
        validate_metadata(self.metadata, "Metadata")

    @property
    def quote_count(self) -> int:
        """Return quote count."""
        return len(self.quotes)

    @property
    def tick_count(self) -> int:
        """Return tick count."""
        return len(self.ticks)

    @property
    def empty(self) -> bool:
        """Return whether snapshot is empty."""
        return self.quote_count == 0 and self.tick_count == 0

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "quote_count": self.quote_count,
            "tick_count": self.tick_count,
            "empty": self.empty,
            "quotes": [quote.to_dict() for quote in self.quotes],
            "ticks": [tick.to_dict() for tick in self.ticks],
            "metadata": dict(self.metadata),
        }


@dataclass
class LiveMarketDataAdapter:
    """In-memory live market data adapter."""

    provider_config: ProviderConfig
    quotes: dict[str, MarketQuote] = field(default_factory=dict)
    ticks: dict[str, list[MarketTick]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_live_provider_config(self.provider_config)
        validate_live_quotes_dict(self.quotes)
        validate_live_ticks_dict(self.ticks)
        validate_metadata(self.metadata, "Metadata")

    @property
    def provider_id(self) -> str:
        """Return adapter provider ID."""
        return self.provider_config.provider_id.strip()

    @property
    def active(self) -> bool:
        """Return whether live provider is active."""
        return self.provider_config.active

    def update_quote(self, quote: MarketQuote) -> MarketQuote:
        """Update latest quote."""
        if not isinstance(quote, MarketQuote):
            raise ValueError("Quote must be a MarketQuote.")

        if quote.provider_id.strip() != self.provider_id:
            raise ValueError("Quote provider ID must match adapter provider ID.")

        self.quotes[live_symbol_key(quote.symbol)] = quote
        return quote

    def update_quote_from_values(
        self,
        *,
        symbol: str,
        bid: float,
        ask: float,
        last: float = 0.0,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MarketQuote:
        """Update latest quote from values."""
        quote = build_market_quote(
            provider_id=self.provider_id,
            symbol=symbol,
            bid=bid,
            ask=ask,
            last=last,
            timestamp=timestamp,
            metadata=metadata or {},
        )

        return self.update_quote(quote)

    def add_tick(self, tick: MarketTick) -> MarketTick:
        """Add market tick."""
        if not isinstance(tick, MarketTick):
            raise ValueError("Tick must be a MarketTick.")

        if tick.provider_id.strip() != self.provider_id:
            raise ValueError("Tick provider ID must match adapter provider ID.")

        key = live_symbol_key(tick.symbol)
        self.ticks.setdefault(key, []).append(tick)
        return tick

    def add_tick_from_values(
        self,
        *,
        symbol: str,
        price: float,
        volume: float = 0.0,
        price_type: MarketDataPriceType | str = MarketDataPriceType.LAST,
        timestamp: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MarketTick:
        """Add market tick from values."""
        tick = build_market_tick(
            provider_id=self.provider_id,
            symbol=symbol,
            price=price,
            volume=volume,
            price_type=price_type,
            timestamp=timestamp,
            metadata=metadata or {},
        )

        return self.add_tick(tick)

    def get_quote(self, symbol: str) -> MarketQuote | None:
        """Get latest quote."""
        return self.quotes.get(live_symbol_key(symbol))

    def get_price(
        self,
        *,
        symbol: str,
        price_type: MarketDataPriceType | str = MarketDataPriceType.MID,
    ) -> float:
        """Get latest price by quote type."""
        quote = self.get_quote(symbol)

        if quote is None:
            return 0.0

        return quote.price(price_type)

    def get_ticks(self, *, symbol: str, limit: int = 100) -> list[MarketTick]:
        """Get latest ticks for symbol."""
        validate_market_data_limit(limit)
        key = live_symbol_key(symbol)
        return list(self.ticks.get(key, []))[-limit:]

    def fetch_quote(self, request: LiveQuoteRequest) -> ProviderResult:
        """Fetch latest quote."""
        if not isinstance(request, LiveQuoteRequest):
            raise ValueError("Request must be a LiveQuoteRequest.")

        if request.provider_id.strip() != self.provider_id:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Request provider ID does not match adapter provider ID.",
                request_type="live_quote",
                metadata={
                    "request_provider_id": request.provider_id.strip(),
                },
            )

        if not self.active:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Live quote provider is not active.",
                request_type="live_quote",
            )

        quote = self.get_quote(request.symbol)

        if quote is None:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Live quote not found.",
                request_type="live_quote",
                metadata={
                    "symbol": validate_market_symbol(request.symbol),
                },
            )

        return market_quote_to_provider_result(
            quote,
            message="Live quote fetched.",
        )

    def fetch_ticks(self, request: TickDataRequest) -> ProviderResult:
        """Fetch market ticks."""
        if not isinstance(request, TickDataRequest):
            raise ValueError("Request must be a TickDataRequest.")

        if request.provider_id.strip() != self.provider_id:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Request provider ID does not match adapter provider ID.",
                request_type="ticks",
                metadata={
                    "request_provider_id": request.provider_id.strip(),
                },
            )

        if not self.active:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Tick provider is not active.",
                request_type="ticks",
            )

        ticks = self.get_ticks(
            symbol=request.symbol,
            limit=request.limit,
        )

        if not ticks:
            return market_data_error_result(
                provider_id=self.provider_id,
                error="Market ticks not found.",
                request_type="ticks",
                metadata={
                    "symbol": validate_market_symbol(request.symbol),
                },
            )

        return market_ticks_to_provider_result(
            provider_id=self.provider_id,
            ticks=ticks,
            message="Market ticks fetched.",
        )

    def snapshot(self, symbols: list[str] | None = None) -> LiveMarketDataSnapshot:
        """Return live market data snapshot."""
        if symbols is None:
            quotes = list(self.quotes.values())
            ticks = [
                tick
                for symbol_ticks in self.ticks.values()
                for tick in symbol_ticks
            ]
        else:
            validate_symbol_list(symbols)
            keys = {live_symbol_key(symbol) for symbol in symbols}
            quotes = [
                quote
                for key, quote in self.quotes.items()
                if key in keys
            ]
            ticks = [
                tick
                for key, symbol_ticks in self.ticks.items()
                if key in keys
                for tick in symbol_ticks
            ]

        return build_live_market_data_snapshot(
            provider_id=self.provider_id,
            quotes=quotes,
            ticks=ticks,
            metadata={
                "symbols": symbols or self.list_symbols(),
            },
        )

    def list_symbols(self) -> list[str]:
        """List symbols with quote or tick data."""
        quote_symbols = set(self.quotes.keys())
        tick_symbols = set(self.ticks.keys())
        return sorted(quote_symbols | tick_symbols)

    def clear_quotes(self) -> None:
        """Clear quotes."""
        self.quotes.clear()

    def clear_ticks(self) -> None:
        """Clear ticks."""
        self.ticks.clear()

    def clear(self) -> None:
        """Clear quotes and ticks."""
        self.clear_quotes()
        self.clear_ticks()

    def quote_count(self) -> int:
        """Return quote count."""
        return len(self.quotes)

    def tick_count(self) -> int:
        """Return total tick count."""
        return sum(len(items) for items in self.ticks.values())


def validate_live_provider_config(config: ProviderConfig) -> ProviderConfig:
    """Validate live market data provider config."""
    if not isinstance(config, ProviderConfig):
        raise ValueError("Provider config must be ProviderConfig.")

    if (
        config.provider_type != ProviderType.MARKET_DATA
        and str(config.provider_type) != ProviderType.MARKET_DATA.value
    ):
        raise ValueError("Live adapter requires a market data provider config.")

    if not (
        config.supports(ProviderCapability.LIVE_QUOTES)
        or config.supports(ProviderCapability.TICKS)
    ):
        raise ValueError("Provider config must support live quotes or ticks.")

    return config


def validate_market_quotes(quotes: list[MarketQuote]) -> list[MarketQuote]:
    """Validate market quote list."""
    if not isinstance(quotes, list):
        raise ValueError("Quotes must be a list.")

    for quote in quotes:
        if not isinstance(quote, MarketQuote):
            raise ValueError("Quotes must contain MarketQuote objects.")

    return quotes


def validate_live_quotes_dict(quotes: dict[str, MarketQuote]) -> dict[str, MarketQuote]:
    """Validate live quote dictionary."""
    if not isinstance(quotes, dict):
        raise ValueError("Quotes must be a dictionary.")

    for key, quote in quotes.items():
        validate_non_empty_string(key, "Quote key")

        if not isinstance(quote, MarketQuote):
            raise ValueError("Quotes must contain MarketQuote objects.")

    return quotes


def validate_live_ticks_dict(ticks: dict[str, list[MarketTick]]) -> dict[str, list[MarketTick]]:
    """Validate live ticks dictionary."""
    if not isinstance(ticks, dict):
        raise ValueError("Ticks must be a dictionary.")

    for key, symbol_ticks in ticks.items():
        validate_non_empty_string(key, "Tick key")
        validate_market_ticks(symbol_ticks)

    return ticks


def validate_symbol_list(symbols: list[str]) -> list[str]:
    """Validate symbol list."""
    if not isinstance(symbols, list):
        raise ValueError("Symbols must be a list.")

    for symbol in symbols:
        validate_market_symbol(symbol)

    return symbols


def live_symbol_key(symbol: str) -> str:
    """Build live symbol key."""
    return validate_market_symbol(symbol)


def build_live_market_data_snapshot(
    *,
    provider_id: str,
    quotes: list[MarketQuote] | None = None,
    ticks: list[MarketTick] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveMarketDataSnapshot:
    """Build live market data snapshot."""
    return LiveMarketDataSnapshot(
        provider_id=provider_id,
        quotes=quotes or [],
        ticks=ticks or [],
        metadata=metadata or {},
    )


def build_live_market_data_adapter(
    *,
    provider_config: ProviderConfig | None = None,
    provider_id: str = "local-live",
    name: str = "Local Live Market Data Provider",
    quotes: dict[str, MarketQuote] | None = None,
    ticks: dict[str, list[MarketTick]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> LiveMarketDataAdapter:
    """Build live market data adapter."""
    resolved_config = provider_config or build_provider_config(
        provider_id=provider_id,
        name=name,
        provider_type=ProviderType.MARKET_DATA,
        capabilities=[
            ProviderCapability.LIVE_QUOTES,
            ProviderCapability.TICKS,
        ],
    )

    return LiveMarketDataAdapter(
        provider_config=resolved_config,
        quotes=quotes or {},
        ticks=ticks or {},
        metadata=metadata or {},
    )


def build_live_quote_request_for_adapter(
    *,
    adapter: LiveMarketDataAdapter,
    symbol: str,
    price_type: MarketDataPriceType | str = MarketDataPriceType.MID,
    metadata: dict[str, Any] | None = None,
) -> LiveQuoteRequest:
    """Build live quote request for adapter."""
    if not isinstance(adapter, LiveMarketDataAdapter):
        raise ValueError("Adapter must be a LiveMarketDataAdapter.")

    return build_live_quote_request(
        provider_id=adapter.provider_id,
        symbol=symbol,
        price_type=price_type,
        metadata=metadata or {},
    )


def build_tick_data_request_for_adapter(
    *,
    adapter: LiveMarketDataAdapter,
    symbol: str,
    limit: int = 100,
    metadata: dict[str, Any] | None = None,
) -> TickDataRequest:
    """Build tick data request for adapter."""
    if not isinstance(adapter, LiveMarketDataAdapter):
        raise ValueError("Adapter must be a LiveMarketDataAdapter.")

    return build_tick_data_request(
        provider_id=adapter.provider_id,
        symbol=symbol,
        limit=limit,
        metadata=metadata or {},
    )


def fetch_live_quote(
    *,
    adapter: LiveMarketDataAdapter,
    request: LiveQuoteRequest,
) -> ProviderResult:
    """Fetch live quote from adapter."""
    if not isinstance(adapter, LiveMarketDataAdapter):
        raise ValueError("Adapter must be a LiveMarketDataAdapter.")

    return adapter.fetch_quote(request)


def fetch_market_ticks(
    *,
    adapter: LiveMarketDataAdapter,
    request: TickDataRequest,
) -> ProviderResult:
    """Fetch market ticks from adapter."""
    if not isinstance(adapter, LiveMarketDataAdapter):
        raise ValueError("Adapter must be a LiveMarketDataAdapter.")

    return adapter.fetch_ticks(request)


def quote_payload_to_market_quote(
    *,
    provider_id: str,
    payload: dict[str, Any],
) -> MarketQuote:
    """Convert quote payload into market quote."""
    validate_metadata(payload, "Quote payload")

    return build_market_quote(
        provider_id=provider_id,
        symbol=str(payload["symbol"]),
        bid=float(payload["bid"]),
        ask=float(payload["ask"]),
        last=float(payload.get("last", 0.0)),
        timestamp=str(payload["timestamp"]) if "timestamp" in payload else None,
        metadata=dict(payload.get("metadata", {})),
    )


def tick_payload_to_market_tick(
    *,
    provider_id: str,
    payload: dict[str, Any],
) -> MarketTick:
    """Convert tick payload into market tick."""
    validate_metadata(payload, "Tick payload")

    return build_market_tick(
        provider_id=provider_id,
        symbol=str(payload["symbol"]),
        price=float(payload["price"]),
        volume=float(payload.get("volume", 0.0)),
        price_type=normalize_market_data_price_type(payload.get("price_type", "last")),
        timestamp=str(payload["timestamp"]) if "timestamp" in payload else None,
        metadata=dict(payload.get("metadata", {})),
    )


def create_sample_live_adapter(
    *,
    provider_id: str = "sample-live",
    symbol: str = "XAUUSD",
) -> LiveMarketDataAdapter:
    """Create sample live adapter for tests/examples."""
    adapter = build_live_market_data_adapter(provider_id=provider_id)
    adapter.update_quote_from_values(
        symbol=symbol,
        bid=2000,
        ask=2002,
        last=2001,
        timestamp="2026-01-01T00:00:00+00:00",
    )
    adapter.add_tick_from_values(
        symbol=symbol,
        price=2001,
        volume=10,
        timestamp="2026-01-01T00:00:01+00:00",
    )
    adapter.add_tick_from_values(
        symbol=symbol,
        price=2002,
        volume=12,
        timestamp="2026-01-01T00:00:02+00:00",
    )

    return adapter