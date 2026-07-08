"""
AQOS market data provider contracts.

This module contains provider-facing contracts for historical OHLCV candles,
live quotes, ticks, market data requests, and market data batches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.providers.base import (
    ProviderCapability,
    ProviderResult,
    build_provider_result,
    provider_failure,
    provider_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_positive_integer,
    validate_string,
)


class MarketDataTimeframe(str, Enum):
    """Supported market data timeframes."""

    M1 = "M1"
    M5 = "M5"
    M15 = "M15"
    M30 = "M30"
    H1 = "H1"
    H4 = "H4"
    D1 = "D1"
    W1 = "W1"


class MarketDataPriceType(str, Enum):
    """Supported market data price types."""

    BID = "bid"
    ASK = "ask"
    MID = "mid"
    LAST = "last"


class MarketDataQuality(str, Enum):
    """Supported market data quality levels."""

    RAW = "raw"
    VALIDATED = "validated"
    ADJUSTED = "adjusted"
    SYNTHETIC = "synthetic"


class MarketDataRequestType(str, Enum):
    """Supported market data request types."""

    HISTORICAL_OHLCV = "historical_ohlcv"
    LIVE_QUOTE = "live_quote"
    TICKS = "ticks"


@dataclass(frozen=True)
class HistoricalOhlcvRequest:
    """Historical OHLCV request."""

    provider_id: str
    symbol: str
    timeframe: MarketDataTimeframe | str
    start: str = ""
    end: str = ""
    limit: int = 500
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        normalize_market_data_timeframe(self.timeframe)
        validate_string(self.start, "Start")
        validate_string(self.end, "End")
        validate_market_data_limit(self.limit)
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert request into dictionary."""
        return {
            "request_type": MarketDataRequestType.HISTORICAL_OHLCV.value,
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "timeframe": normalize_market_data_timeframe(self.timeframe).value,
            "start": self.start.strip(),
            "end": self.end.strip(),
            "limit": self.limit,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class LiveQuoteRequest:
    """Live quote request."""

    provider_id: str
    symbol: str
    price_type: MarketDataPriceType | str = MarketDataPriceType.MID
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        normalize_market_data_price_type(self.price_type)
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert request into dictionary."""
        return {
            "request_type": MarketDataRequestType.LIVE_QUOTE.value,
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "price_type": normalize_market_data_price_type(self.price_type).value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class TickDataRequest:
    """Tick data request."""

    provider_id: str
    symbol: str
    limit: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        validate_market_data_limit(self.limit)
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert request into dictionary."""
        return {
            "request_type": MarketDataRequestType.TICKS.value,
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "limit": self.limit,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class OhlcvCandle:
    """OHLCV market data candle."""

    symbol: str
    timeframe: MarketDataTimeframe | str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0
    quality: MarketDataQuality | str = MarketDataQuality.RAW
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_market_symbol(self.symbol)
        normalize_market_data_timeframe(self.timeframe)
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_positive_float(self.open, "Open")
        validate_positive_float(self.high, "High")
        validate_positive_float(self.low, "Low")
        validate_positive_float(self.close, "Close")
        validate_non_negative_float(self.volume, "Volume")
        normalize_market_data_quality(self.quality)
        validate_metadata(self.metadata, "Metadata")

        if float(self.high) < max(float(self.open), float(self.close), float(self.low)):
            raise ValueError("High must be greater than or equal to open, low, and close.")

        if float(self.low) > min(float(self.open), float(self.high), float(self.close)):
            raise ValueError("Low must be less than or equal to open, high, and close.")

    @property
    def typical_price(self) -> float:
        """Return candle typical price."""
        return round((float(self.high) + float(self.low) + float(self.close)) / 3, 6)

    @property
    def range(self) -> float:
        """Return candle range."""
        return round(float(self.high) - float(self.low), 6)

    @property
    def bullish(self) -> bool:
        """Return whether candle is bullish."""
        return float(self.close) > float(self.open)

    @property
    def bearish(self) -> bool:
        """Return whether candle is bearish."""
        return float(self.close) < float(self.open)

    def to_dict(self) -> dict[str, Any]:
        """Convert candle into dictionary."""
        return {
            "symbol": validate_market_symbol(self.symbol),
            "timeframe": normalize_market_data_timeframe(self.timeframe).value,
            "timestamp": self.timestamp.strip(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "quality": normalize_market_data_quality(self.quality).value,
            "typical_price": self.typical_price,
            "range": self.range,
            "bullish": self.bullish,
            "bearish": self.bearish,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MarketQuote:
    """Live market quote."""

    provider_id: str
    symbol: str
    bid: float
    ask: float
    last: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    quality: MarketDataQuality | str = MarketDataQuality.RAW
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        validate_positive_float(self.bid, "Bid")
        validate_positive_float(self.ask, "Ask")
        validate_non_negative_float(self.last, "Last")
        validate_non_empty_string(self.timestamp, "Timestamp")
        normalize_market_data_quality(self.quality)
        validate_metadata(self.metadata, "Metadata")

        if float(self.ask) < float(self.bid):
            raise ValueError("Ask must be greater than or equal to bid.")

    @property
    def spread(self) -> float:
        """Return quote spread."""
        return round(float(self.ask) - float(self.bid), 6)

    @property
    def mid(self) -> float:
        """Return quote midpoint."""
        return round((float(self.bid) + float(self.ask)) / 2, 6)

    @property
    def effective_last(self) -> float:
        """Return last price, falling back to mid."""
        return float(self.last) if self.last > 0 else self.mid

    def price(self, price_type: MarketDataPriceType | str = MarketDataPriceType.MID) -> float:
        """Return quote price by type."""
        normalized = normalize_market_data_price_type(price_type)

        if normalized == MarketDataPriceType.BID:
            return float(self.bid)

        if normalized == MarketDataPriceType.ASK:
            return float(self.ask)

        if normalized == MarketDataPriceType.LAST:
            return self.effective_last

        return self.mid

    def to_dict(self) -> dict[str, Any]:
        """Convert quote into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "bid": float(self.bid),
            "ask": float(self.ask),
            "last": float(self.last),
            "effective_last": self.effective_last,
            "mid": self.mid,
            "spread": self.spread,
            "timestamp": self.timestamp.strip(),
            "quality": normalize_market_data_quality(self.quality).value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MarketTick:
    """Market tick data point."""

    provider_id: str
    symbol: str
    price: float
    volume: float = 0.0
    price_type: MarketDataPriceType | str = MarketDataPriceType.LAST
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        validate_positive_float(self.price, "Price")
        validate_non_negative_float(self.volume, "Volume")
        normalize_market_data_price_type(self.price_type)
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert tick into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "price": float(self.price),
            "volume": float(self.volume),
            "price_type": normalize_market_data_price_type(self.price_type).value,
            "timestamp": self.timestamp.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MarketDataBatch:
    """Historical market data batch."""

    provider_id: str
    symbol: str
    timeframe: MarketDataTimeframe | str
    candles: list[OhlcvCandle] = field(default_factory=list)
    quality: MarketDataQuality | str = MarketDataQuality.RAW
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.provider_id, "Provider ID")
        validate_market_symbol(self.symbol)
        normalize_market_data_timeframe(self.timeframe)
        validate_ohlcv_candles(self.candles)
        normalize_market_data_quality(self.quality)
        validate_metadata(self.metadata, "Metadata")

        normalized_symbol = validate_market_symbol(self.symbol)
        normalized_timeframe = normalize_market_data_timeframe(self.timeframe)

        for candle in self.candles:
            if validate_market_symbol(candle.symbol) != normalized_symbol:
                raise ValueError("All candles must match batch symbol.")

            if normalize_market_data_timeframe(candle.timeframe) != normalized_timeframe:
                raise ValueError("All candles must match batch timeframe.")

    @property
    def count(self) -> int:
        """Return candle count."""
        return len(self.candles)

    @property
    def empty(self) -> bool:
        """Return whether batch is empty."""
        return self.count == 0

    @property
    def latest_close(self) -> float:
        """Return latest close."""
        return float(self.candles[-1].close) if self.candles else 0.0

    @property
    def first_timestamp(self) -> str:
        """Return first timestamp."""
        return self.candles[0].timestamp if self.candles else ""

    @property
    def latest_timestamp(self) -> str:
        """Return latest timestamp."""
        return self.candles[-1].timestamp if self.candles else ""

    def close_prices(self) -> list[float]:
        """Return close prices."""
        return [float(candle.close) for candle in self.candles]

    def to_rows(self) -> list[dict[str, Any]]:
        """Convert candles into row dictionaries."""
        return [candle.to_dict() for candle in self.candles]

    def to_dict(self) -> dict[str, Any]:
        """Convert batch into dictionary."""
        return {
            "provider_id": self.provider_id.strip(),
            "symbol": validate_market_symbol(self.symbol),
            "timeframe": normalize_market_data_timeframe(self.timeframe).value,
            "count": self.count,
            "empty": self.empty,
            "first_timestamp": self.first_timestamp,
            "latest_timestamp": self.latest_timestamp,
            "latest_close": self.latest_close,
            "quality": normalize_market_data_quality(self.quality).value,
            "candles": self.to_rows(),
            "metadata": dict(self.metadata),
        }


def validate_market_symbol(symbol: str) -> str:
    """Validate market data symbol."""
    normalized = validate_non_empty_string(symbol, "Symbol").upper()

    if not normalized.replace("/", "").replace("-", "").isalnum():
        raise ValueError("Symbol must be alphanumeric and may include '/' or '-'.")

    return normalized


def validate_market_data_limit(limit: int) -> int:
    """Validate market data limit."""
    validate_positive_integer(limit, "Limit")

    if limit > 100_000:
        raise ValueError("Limit cannot exceed 100000.")

    return limit


def normalize_market_data_timeframe(
    timeframe: MarketDataTimeframe | str,
) -> MarketDataTimeframe:
    """Normalize market data timeframe."""
    if isinstance(timeframe, MarketDataTimeframe):
        return timeframe

    normalized = validate_non_empty_string(timeframe, "Timeframe").upper()

    try:
        return MarketDataTimeframe(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MarketDataTimeframe)
        raise ValueError(
            f"Invalid market data timeframe '{timeframe}'. Valid timeframes: {valid}.",
        ) from exc


def normalize_market_data_price_type(
    price_type: MarketDataPriceType | str,
) -> MarketDataPriceType:
    """Normalize market data price type."""
    if isinstance(price_type, MarketDataPriceType):
        return price_type

    normalized = validate_non_empty_string(price_type, "Price type").lower()

    try:
        return MarketDataPriceType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MarketDataPriceType)
        raise ValueError(
            f"Invalid market data price type '{price_type}'. Valid price types: {valid}.",
        ) from exc


def normalize_market_data_quality(
    quality: MarketDataQuality | str,
) -> MarketDataQuality:
    """Normalize market data quality."""
    if isinstance(quality, MarketDataQuality):
        return quality

    normalized = validate_non_empty_string(quality, "Market data quality").lower()

    try:
        return MarketDataQuality(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MarketDataQuality)
        raise ValueError(
            f"Invalid market data quality '{quality}'. Valid qualities: {valid}.",
        ) from exc


def normalize_market_data_request_type(
    request_type: MarketDataRequestType | str,
) -> MarketDataRequestType:
    """Normalize market data request type."""
    if isinstance(request_type, MarketDataRequestType):
        return request_type

    normalized = validate_non_empty_string(request_type, "Market data request type").lower()

    try:
        return MarketDataRequestType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MarketDataRequestType)
        raise ValueError(
            f"Invalid market data request type '{request_type}'. Valid request types: {valid}.",
        ) from exc


def validate_ohlcv_candles(candles: list[OhlcvCandle]) -> list[OhlcvCandle]:
    """Validate OHLCV candle list."""
    if not isinstance(candles, list):
        raise ValueError("Candles must be a list.")

    for candle in candles:
        if not isinstance(candle, OhlcvCandle):
            raise ValueError("Candles must contain OhlcvCandle objects.")

    return candles


def validate_market_ticks(ticks: list[MarketTick]) -> list[MarketTick]:
    """Validate market tick list."""
    if not isinstance(ticks, list):
        raise ValueError("Ticks must be a list.")

    for tick in ticks:
        if not isinstance(tick, MarketTick):
            raise ValueError("Ticks must contain MarketTick objects.")

    return ticks


def build_historical_ohlcv_request(
    *,
    provider_id: str,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    start: str = "",
    end: str = "",
    limit: int = 500,
    metadata: dict[str, Any] | None = None,
) -> HistoricalOhlcvRequest:
    """Build historical OHLCV request."""
    return HistoricalOhlcvRequest(
        provider_id=provider_id,
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
        limit=limit,
        metadata=metadata or {},
    )


def build_live_quote_request(
    *,
    provider_id: str,
    symbol: str,
    price_type: MarketDataPriceType | str = MarketDataPriceType.MID,
    metadata: dict[str, Any] | None = None,
) -> LiveQuoteRequest:
    """Build live quote request."""
    return LiveQuoteRequest(
        provider_id=provider_id,
        symbol=symbol,
        price_type=price_type,
        metadata=metadata or {},
    )


def build_tick_data_request(
    *,
    provider_id: str,
    symbol: str,
    limit: int = 100,
    metadata: dict[str, Any] | None = None,
) -> TickDataRequest:
    """Build tick data request."""
    return TickDataRequest(
        provider_id=provider_id,
        symbol=symbol,
        limit=limit,
        metadata=metadata or {},
    )


def build_ohlcv_candle(
    *,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    timestamp: str,
    open: float,
    high: float,
    low: float,
    close: float,
    volume: float = 0.0,
    quality: MarketDataQuality | str = MarketDataQuality.RAW,
    metadata: dict[str, Any] | None = None,
) -> OhlcvCandle:
    """Build OHLCV candle."""
    return OhlcvCandle(
        symbol=symbol,
        timeframe=timeframe,
        timestamp=timestamp,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        quality=quality,
        metadata=metadata or {},
    )


def build_market_quote(
    *,
    provider_id: str,
    symbol: str,
    bid: float,
    ask: float,
    last: float = 0.0,
    timestamp: str | None = None,
    quality: MarketDataQuality | str = MarketDataQuality.RAW,
    metadata: dict[str, Any] | None = None,
) -> MarketQuote:
    """Build market quote."""
    quote_kwargs: dict[str, Any] = {
        "provider_id": provider_id,
        "symbol": symbol,
        "bid": bid,
        "ask": ask,
        "last": last,
        "quality": quality,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        quote_kwargs["timestamp"] = timestamp

    return MarketQuote(**quote_kwargs)


def build_market_tick(
    *,
    provider_id: str,
    symbol: str,
    price: float,
    volume: float = 0.0,
    price_type: MarketDataPriceType | str = MarketDataPriceType.LAST,
    timestamp: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> MarketTick:
    """Build market tick."""
    tick_kwargs: dict[str, Any] = {
        "provider_id": provider_id,
        "symbol": symbol,
        "price": price,
        "volume": volume,
        "price_type": price_type,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        tick_kwargs["timestamp"] = timestamp

    return MarketTick(**tick_kwargs)


def build_market_data_batch(
    *,
    provider_id: str,
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    candles: list[OhlcvCandle] | None = None,
    quality: MarketDataQuality | str = MarketDataQuality.RAW,
    metadata: dict[str, Any] | None = None,
) -> MarketDataBatch:
    """Build market data batch."""
    return MarketDataBatch(
        provider_id=provider_id,
        symbol=symbol,
        timeframe=timeframe,
        candles=candles or [],
        quality=quality,
        metadata=metadata or {},
    )


def market_data_batch_to_provider_result(
    batch: MarketDataBatch,
    *,
    message: str = "Historical market data fetched.",
) -> ProviderResult:
    """Convert market data batch into provider result."""
    if not isinstance(batch, MarketDataBatch):
        raise ValueError("Batch must be a MarketDataBatch.")

    return provider_success(
        provider_id=batch.provider_id,
        data={
            "batch": batch.to_dict(),
        },
        message=message,
        metadata={
            "capability": ProviderCapability.HISTORICAL_OHLCV.value,
        },
    )


def market_quote_to_provider_result(
    quote: MarketQuote,
    *,
    message: str = "Live quote fetched.",
) -> ProviderResult:
    """Convert market quote into provider result."""
    if not isinstance(quote, MarketQuote):
        raise ValueError("Quote must be a MarketQuote.")

    return provider_success(
        provider_id=quote.provider_id,
        data={
            "quote": quote.to_dict(),
        },
        message=message,
        metadata={
            "capability": ProviderCapability.LIVE_QUOTES.value,
        },
    )


def market_ticks_to_provider_result(
    *,
    provider_id: str,
    ticks: list[MarketTick],
    message: str = "Market ticks fetched.",
) -> ProviderResult:
    """Convert market ticks into provider result."""
    validate_non_empty_string(provider_id, "Provider ID")
    validate_market_ticks(ticks)

    return provider_success(
        provider_id=provider_id,
        data={
            "ticks": [tick.to_dict() for tick in ticks],
            "count": len(ticks),
        },
        message=message,
        metadata={
            "capability": ProviderCapability.TICKS.value,
        },
    )


def market_data_error_result(
    *,
    provider_id: str,
    error: str,
    request_type: MarketDataRequestType | str,
    metadata: dict[str, Any] | None = None,
) -> ProviderResult:
    """Build market data provider error result."""
    return provider_failure(
        provider_id=provider_id,
        error=error,
        message="Market data provider operation failed.",
        metadata={
            "request_type": normalize_market_data_request_type(request_type).value,
            **(metadata or {}),
        },
    )


def candles_to_ohlcv_rows(candles: list[OhlcvCandle]) -> list[dict[str, Any]]:
    """Convert candles into normalized OHLCV rows."""
    validate_ohlcv_candles(candles)

    return [
        {
            "timestamp": candle.timestamp.strip(),
            "open": float(candle.open),
            "high": float(candle.high),
            "low": float(candle.low),
            "close": float(candle.close),
            "volume": float(candle.volume),
        }
        for candle in candles
    ]


def ohlcv_rows_to_candles(
    *,
    rows: list[dict[str, Any]],
    symbol: str,
    timeframe: MarketDataTimeframe | str,
    quality: MarketDataQuality | str = MarketDataQuality.RAW,
) -> list[OhlcvCandle]:
    """Convert normalized OHLCV rows into candles."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    candles: list[OhlcvCandle] = []

    for row in rows:
        validate_metadata(row, "OHLCV row")
        candles.append(
            build_ohlcv_candle(
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(row["timestamp"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0)),
                quality=quality,
            ),
        )

    return candles