"""
AQOS product-facing signal API.

This module provides dependency-free product API primitives for creating,
listing, retrieving, approving, rejecting, and serializing trading signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.product_api.base import (
    ProductApiErrorCode,
    ProductApiRequestContext,
    ProductApiResponse,
    product_api_failure,
    product_api_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_percentage,
    validate_product_symbol,
    validate_product_timeframe,
    validate_string,
)
from aqos.product_api.contracts import (
    ProductApiListQuery,
    ProductApiListResult,
    ProductApiOperation,
    ProductApiOperationResult,
    ProductApiPagination,
    ProductApiRequestType,
    list_result_to_response,
    operation_result_to_response,
)


class ProductSignalDirection(str, Enum):
    """Supported product signal directions."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class ProductSignalStrength(str, Enum):
    """Supported product signal strengths."""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class ProductSignalStatus(str, Enum):
    """Supported product signal statuses."""

    GENERATED = "generated"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ProductSignalRequest:
    """Product signal generation request."""

    symbol: str
    timeframe: str
    entry_price: float = 0.0
    risk_profile: str = "balanced"
    include_explanation: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_product_symbol(self.symbol)
        validate_product_timeframe(self.timeframe)
        validate_signal_price(self.entry_price, "Entry price")
        validate_non_empty_string(self.risk_profile, "Risk profile")

        if not isinstance(self.include_explanation, bool):
            raise ValueError("Include explanation must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert signal request into dictionary."""
        return {
            "symbol": validate_product_symbol(self.symbol),
            "timeframe": validate_product_timeframe(self.timeframe),
            "entry_price": float(self.entry_price),
            "risk_profile": self.risk_profile.strip(),
            "include_explanation": self.include_explanation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductSignalPayload:
    """Product-facing signal payload."""

    signal_id: str
    symbol: str
    timeframe: str
    direction: ProductSignalDirection | str
    confidence: float
    strength: ProductSignalStrength | str
    status: ProductSignalStatus | str = ProductSignalStatus.GENERATED
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward_ratio: float = 0.0
    explanation: str = ""
    features: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.signal_id, "Signal ID")
        validate_product_symbol(self.symbol)
        validate_product_timeframe(self.timeframe)
        normalize_product_signal_direction(self.direction)
        validate_percentage(self.confidence, "Confidence")
        normalize_product_signal_strength(self.strength)
        normalize_product_signal_status(self.status)
        validate_signal_price(self.entry_price, "Entry price")
        validate_signal_price(self.stop_loss, "Stop loss")
        validate_signal_price(self.take_profit, "Take profit")
        validate_non_negative_float(self.risk_reward_ratio, "Risk/reward ratio")
        validate_string(self.explanation, "Explanation")
        validate_metadata(self.features, "Features")
        validate_metadata(self.metadata, "Metadata")
        validate_non_empty_string(self.created_at, "Created at")

    @property
    def actionable(self) -> bool:
        """Return whether signal is actionable."""
        return normalize_product_signal_direction(self.direction) in {
            ProductSignalDirection.BUY,
            ProductSignalDirection.SELL,
        }

    @property
    def approved(self) -> bool:
        """Return whether signal is approved."""
        return normalize_product_signal_status(self.status) == ProductSignalStatus.APPROVED

    def to_dict(self) -> dict[str, Any]:
        """Convert signal payload into dictionary."""
        return {
            "signal_id": self.signal_id.strip(),
            "symbol": validate_product_symbol(self.symbol),
            "timeframe": validate_product_timeframe(self.timeframe),
            "direction": normalize_product_signal_direction(self.direction).value,
            "confidence": float(self.confidence),
            "strength": normalize_product_signal_strength(self.strength).value,
            "status": normalize_product_signal_status(self.status).value,
            "entry_price": float(self.entry_price),
            "stop_loss": float(self.stop_loss),
            "take_profit": float(self.take_profit),
            "risk_reward_ratio": float(self.risk_reward_ratio),
            "actionable": self.actionable,
            "approved": self.approved,
            "explanation": self.explanation.strip(),
            "features": dict(self.features),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.strip(),
        }


@dataclass(frozen=True)
class ProductSignalSummary:
    """Compact product signal summary."""

    total: int = 0
    buy: int = 0
    sell: int = 0
    hold: int = 0
    average_confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_negative_integer(self.total, "Total")
        validate_non_negative_integer(self.buy, "Buy count")
        validate_non_negative_integer(self.sell, "Sell count")
        validate_non_negative_integer(self.hold, "Hold count")
        validate_percentage(self.average_confidence, "Average confidence")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert summary into dictionary."""
        return {
            "total": self.total,
            "buy": self.buy,
            "sell": self.sell,
            "hold": self.hold,
            "average_confidence": float(self.average_confidence),
            "metadata": dict(self.metadata),
        }


@dataclass
class ProductSignalStore:
    """In-memory product signal store."""

    signals: dict[str, ProductSignalPayload] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.signals, dict):
            raise ValueError("Signals must be a dictionary.")

        for signal_id, signal in self.signals.items():
            validate_non_empty_string(signal_id, "Signal ID")

            if not isinstance(signal, ProductSignalPayload):
                raise ValueError("Signals must contain ProductSignalPayload objects.")

    def add(self, signal: ProductSignalPayload) -> ProductSignalPayload:
        """Add signal to store."""
        if not isinstance(signal, ProductSignalPayload):
            raise ValueError("Signal must be a ProductSignalPayload.")

        self.signals[signal.signal_id.strip()] = signal
        return signal

    def get(self, signal_id: str) -> ProductSignalPayload | None:
        """Get signal by ID."""
        normalized_signal_id = validate_non_empty_string(signal_id, "Signal ID")
        return self.signals.get(normalized_signal_id)

    def list(self) -> list[ProductSignalPayload]:
        """List signals."""
        return list(self.signals.values())

    def remove(self, signal_id: str) -> ProductSignalPayload | None:
        """Remove signal by ID."""
        normalized_signal_id = validate_non_empty_string(signal_id, "Signal ID")
        return self.signals.pop(normalized_signal_id, None)

    def clear(self) -> None:
        """Clear signal store."""
        self.signals.clear()

    def count(self) -> int:
        """Return signal count."""
        return len(self.signals)


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_signal_price(value: float | int, field_name: str) -> float:
    """Validate signal price."""
    return validate_non_negative_float(value, field_name)


def normalize_product_signal_direction(
    direction: ProductSignalDirection | str,
) -> ProductSignalDirection:
    """Normalize signal direction."""
    if isinstance(direction, ProductSignalDirection):
        return direction

    normalized = validate_non_empty_string(direction, "Signal direction").lower()

    try:
        return ProductSignalDirection(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductSignalDirection)
        raise ValueError(
            f"Invalid signal direction '{direction}'. Valid directions: {valid}.",
        ) from exc


def normalize_product_signal_strength(
    strength: ProductSignalStrength | str,
) -> ProductSignalStrength:
    """Normalize signal strength."""
    if isinstance(strength, ProductSignalStrength):
        return strength

    normalized = validate_non_empty_string(strength, "Signal strength").lower()

    try:
        return ProductSignalStrength(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductSignalStrength)
        raise ValueError(
            f"Invalid signal strength '{strength}'. Valid strengths: {valid}.",
        ) from exc


def normalize_product_signal_status(
    status: ProductSignalStatus | str,
) -> ProductSignalStatus:
    """Normalize signal status."""
    if isinstance(status, ProductSignalStatus):
        return status

    normalized = validate_non_empty_string(status, "Signal status").lower()

    try:
        return ProductSignalStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductSignalStatus)
        raise ValueError(
            f"Invalid signal status '{status}'. Valid statuses: {valid}.",
        ) from exc


def resolve_signal_strength(confidence: float | int) -> ProductSignalStrength:
    """Resolve signal strength from confidence."""
    normalized_confidence = validate_percentage(confidence, "Confidence")

    if normalized_confidence >= 75:
        return ProductSignalStrength.STRONG

    if normalized_confidence >= 50:
        return ProductSignalStrength.MODERATE

    return ProductSignalStrength.WEAK


def calculate_signal_risk_reward_ratio(
    *,
    direction: ProductSignalDirection | str,
    entry_price: float | int,
    stop_loss: float | int,
    take_profit: float | int,
) -> float:
    """Calculate signal risk/reward ratio."""
    normalized_direction = normalize_product_signal_direction(direction)
    entry = validate_signal_price(entry_price, "Entry price")
    stop = validate_signal_price(stop_loss, "Stop loss")
    target = validate_signal_price(take_profit, "Take profit")

    if normalized_direction == ProductSignalDirection.HOLD:
        return 0.0

    if normalized_direction == ProductSignalDirection.BUY:
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target

    if risk <= 0 or reward <= 0:
        return 0.0

    return round(reward / risk, 4)


def build_product_signal_request(
    *,
    symbol: str,
    timeframe: str,
    entry_price: float = 0.0,
    risk_profile: str = "balanced",
    include_explanation: bool = True,
    metadata: dict[str, Any] | None = None,
) -> ProductSignalRequest:
    """Build product signal request."""
    return ProductSignalRequest(
        symbol=symbol,
        timeframe=timeframe,
        entry_price=entry_price,
        risk_profile=risk_profile,
        include_explanation=include_explanation,
        metadata=metadata or {},
    )


def build_product_signal_payload(
    *,
    signal_id: str,
    symbol: str,
    timeframe: str,
    direction: ProductSignalDirection | str,
    confidence: float,
    strength: ProductSignalStrength | str | None = None,
    status: ProductSignalStatus | str = ProductSignalStatus.GENERATED,
    entry_price: float = 0.0,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    risk_reward_ratio: float | None = None,
    explanation: str = "",
    features: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: str | None = None,
) -> ProductSignalPayload:
    """Build product signal payload."""
    resolved_strength = strength or resolve_signal_strength(confidence)
    resolved_risk_reward_ratio = (
        risk_reward_ratio
        if risk_reward_ratio is not None
        else calculate_signal_risk_reward_ratio(
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )
    )

    payload_kwargs: dict[str, Any] = {
        "signal_id": signal_id,
        "symbol": symbol,
        "timeframe": timeframe,
        "direction": direction,
        "confidence": confidence,
        "strength": resolved_strength,
        "status": status,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_reward_ratio": resolved_risk_reward_ratio,
        "explanation": explanation,
        "features": features or {},
        "metadata": metadata or {},
    }

    if created_at is not None:
        payload_kwargs["created_at"] = created_at

    return ProductSignalPayload(**payload_kwargs)


def build_product_signal_summary(
    *,
    signals: list[ProductSignalPayload],
    metadata: dict[str, Any] | None = None,
) -> ProductSignalSummary:
    """Build product signal summary."""
    validate_product_signal_payloads(signals)

    total = len(signals)
    buy = sum(
        1
        for signal in signals
        if normalize_product_signal_direction(signal.direction) == ProductSignalDirection.BUY
    )
    sell = sum(
        1
        for signal in signals
        if normalize_product_signal_direction(signal.direction) == ProductSignalDirection.SELL
    )
    hold = sum(
        1
        for signal in signals
        if normalize_product_signal_direction(signal.direction) == ProductSignalDirection.HOLD
    )

    average_confidence = (
        round(
            sum(float(signal.confidence) for signal in signals) / total,
            4,
        )
        if total
        else 0.0
    )

    return ProductSignalSummary(
        total=total,
        buy=buy,
        sell=sell,
        hold=hold,
        average_confidence=average_confidence,
        metadata=metadata or {},
    )


def build_product_signal_store(
    *,
    signals: dict[str, ProductSignalPayload] | None = None,
) -> ProductSignalStore:
    """Build product signal store."""
    return ProductSignalStore(
        signals=signals or {},
    )


def validate_product_signal_payloads(
    signals: list[ProductSignalPayload],
) -> list[ProductSignalPayload]:
    """Validate product signal payload list."""
    if not isinstance(signals, list):
        raise ValueError("Signals must be a list.")

    for signal in signals:
        if not isinstance(signal, ProductSignalPayload):
            raise ValueError("Signals must contain ProductSignalPayload objects.")

    return signals


def signal_payload_to_response(
    *,
    signal: ProductSignalPayload,
    context: ProductApiRequestContext | None = None,
    message: str = "Signal request completed.",
) -> ProductApiResponse:
    """Convert signal payload into product API response."""
    if not isinstance(signal, ProductSignalPayload):
        raise ValueError("Signal must be a ProductSignalPayload.")

    return product_api_success(
        data={
            "signal": signal.to_dict(),
        },
        message=message,
        context=context,
    )


def list_signals_response(
    *,
    signals: list[ProductSignalPayload],
    query: ProductApiListQuery | None = None,
    context: ProductApiRequestContext | None = None,
    message: str = "Signals listed successfully.",
) -> ProductApiResponse:
    """Build signal list response."""
    validate_product_signal_payloads(signals)

    pagination = query.pagination if query else ProductApiPagination()
    paged_signals = paginate_product_signals(
        signals=signals,
        pagination=pagination,
    )
    result = ProductApiListResult(
        items=[
            signal.to_dict()
            for signal in paged_signals
        ],
        pagination=pagination,
        total_items=len(signals),
        metadata={
            "summary": build_product_signal_summary(signals=signals).to_dict(),
        },
    )

    return list_result_to_response(
        result=result,
        context=context,
        message=message,
    )


def create_signal_operation_response(
    *,
    signal: ProductSignalPayload,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Build create signal operation response."""
    if not isinstance(signal, ProductSignalPayload):
        raise ValueError("Signal must be a ProductSignalPayload.")

    return operation_result_to_response(
        result=ProductApiOperationResult(
            operation=ProductApiOperation.CREATE,
            resource_type=ProductApiRequestType.SIGNAL,
            resource_id=signal.signal_id,
            accepted=True,
            result={
                "signal": signal.to_dict(),
            },
        ),
        context=context,
        message="Signal created successfully.",
    )


def update_signal_status(
    signal: ProductSignalPayload,
    *,
    status: ProductSignalStatus | str,
    metadata: dict[str, Any] | None = None,
) -> ProductSignalPayload:
    """Update signal status by returning a new payload."""
    if not isinstance(signal, ProductSignalPayload):
        raise ValueError("Signal must be a ProductSignalPayload.")

    return build_product_signal_payload(
        signal_id=signal.signal_id,
        symbol=signal.symbol,
        timeframe=signal.timeframe,
        direction=signal.direction,
        confidence=signal.confidence,
        strength=signal.strength,
        status=status,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        risk_reward_ratio=signal.risk_reward_ratio,
        explanation=signal.explanation,
        features=signal.features,
        metadata={
            **signal.metadata,
            **(metadata or {}),
        },
        created_at=signal.created_at,
    )


def approve_signal_response(
    *,
    signal: ProductSignalPayload,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Approve signal and return response."""
    approved_signal = update_signal_status(
        signal,
        status=ProductSignalStatus.APPROVED,
    )

    return signal_payload_to_response(
        signal=approved_signal,
        context=context,
        message="Signal approved successfully.",
    )


def reject_signal_response(
    *,
    signal: ProductSignalPayload,
    reason: str = "",
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Reject signal and return response."""
    validate_string(reason, "Reason")
    rejected_signal = update_signal_status(
        signal,
        status=ProductSignalStatus.REJECTED,
        metadata={
            "rejection_reason": reason.strip(),
        },
    )

    return signal_payload_to_response(
        signal=rejected_signal,
        context=context,
        message="Signal rejected successfully.",
    )


def get_signal_response(
    *,
    store: ProductSignalStore,
    signal_id: str,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Get signal from store and return response."""
    if not isinstance(store, ProductSignalStore):
        raise ValueError("Store must be a ProductSignalStore.")

    signal = store.get(signal_id)

    if signal is None:
        return product_api_failure(
            message="Signal not found.",
            code=ProductApiErrorCode.NOT_FOUND,
            details={
                "signal_id": signal_id.strip(),
            },
            context=context,
        )

    return signal_payload_to_response(
        signal=signal,
        context=context,
        message="Signal retrieved successfully.",
    )


def paginate_product_signals(
    *,
    signals: list[ProductSignalPayload],
    pagination: ProductApiPagination,
) -> list[ProductSignalPayload]:
    """Paginate product signals."""
    validate_product_signal_payloads(signals)

    if not isinstance(pagination, ProductApiPagination):
        raise ValueError("Pagination must be a ProductApiPagination.")

    return signals[pagination.offset : pagination.offset + pagination.page_size]


def filter_product_signals(
    *,
    signals: list[ProductSignalPayload],
    symbol: str | None = None,
    timeframe: str | None = None,
    direction: ProductSignalDirection | str | None = None,
    status: ProductSignalStatus | str | None = None,
) -> list[ProductSignalPayload]:
    """Filter product signals."""
    validate_product_signal_payloads(signals)

    filtered = list(signals)

    if symbol is not None:
        normalized_symbol = validate_product_symbol(symbol)
        filtered = [
            signal
            for signal in filtered
            if validate_product_symbol(signal.symbol) == normalized_symbol
        ]

    if timeframe is not None:
        normalized_timeframe = validate_product_timeframe(timeframe)
        filtered = [
            signal
            for signal in filtered
            if validate_product_timeframe(signal.timeframe) == normalized_timeframe
        ]

    if direction is not None:
        normalized_direction = normalize_product_signal_direction(direction)
        filtered = [
            signal
            for signal in filtered
            if normalize_product_signal_direction(signal.direction) == normalized_direction
        ]

    if status is not None:
        normalized_status = normalize_product_signal_status(status)
        filtered = [
            signal
            for signal in filtered
            if normalize_product_signal_status(signal.status) == normalized_status
        ]

    return filtered