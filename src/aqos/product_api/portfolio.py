"""
AQOS product-facing portfolio API.

This module provides dependency-free product API primitives for portfolio
positions, snapshots, summaries, store operations, and response helpers.
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
    validate_product_symbol,
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


class ProductPositionSide(str, Enum):
    """Supported product portfolio position sides."""

    BUY = "buy"
    SELL = "sell"


class ProductPositionStatus(str, Enum):
    """Supported product portfolio position statuses."""

    OPEN = "open"
    CLOSED = "closed"


@dataclass(frozen=True)
class ProductPortfolioPosition:
    """Product-facing portfolio position."""

    position_id: str
    symbol: str
    side: ProductPositionSide | str
    quantity: float
    entry_price: float
    current_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    status: ProductPositionStatus | str = ProductPositionStatus.OPEN
    opened_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    closed_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.position_id, "Position ID")
        validate_product_symbol(self.symbol)
        normalize_product_position_side(self.side)
        validate_positive_float(self.quantity, "Quantity")
        validate_positive_float(self.entry_price, "Entry price")
        validate_non_negative_float(self.current_price, "Current price")
        validate_non_negative_float(self.stop_loss, "Stop loss")
        validate_non_negative_float(self.take_profit, "Take profit")
        normalize_product_position_status(self.status)
        validate_non_empty_string(self.opened_at, "Opened at")
        validate_string(self.closed_at, "Closed at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def market_price(self) -> float:
        """Return current market price, falling back to entry price."""
        return float(self.current_price) if self.current_price > 0 else float(self.entry_price)

    @property
    def notional_value(self) -> float:
        """Return notional position value."""
        return round(float(self.quantity) * self.market_price, 4)

    @property
    def unrealized_pnl(self) -> float:
        """Return unrealized PnL."""
        if normalize_product_position_side(self.side) == ProductPositionSide.BUY:
            return round((self.market_price - float(self.entry_price)) * float(self.quantity), 4)

        return round((float(self.entry_price) - self.market_price) * float(self.quantity), 4)

    @property
    def open(self) -> bool:
        """Return whether position is open."""
        return normalize_product_position_status(self.status) == ProductPositionStatus.OPEN

    @property
    def closed(self) -> bool:
        """Return whether position is closed."""
        return normalize_product_position_status(self.status) == ProductPositionStatus.CLOSED

    def to_dict(self) -> dict[str, Any]:
        """Convert portfolio position into dictionary."""
        return {
            "position_id": self.position_id.strip(),
            "symbol": validate_product_symbol(self.symbol),
            "side": normalize_product_position_side(self.side).value,
            "quantity": float(self.quantity),
            "entry_price": float(self.entry_price),
            "current_price": float(self.current_price),
            "market_price": self.market_price,
            "stop_loss": float(self.stop_loss),
            "take_profit": float(self.take_profit),
            "status": normalize_product_position_status(self.status).value,
            "open": self.open,
            "closed": self.closed,
            "notional_value": self.notional_value,
            "unrealized_pnl": self.unrealized_pnl,
            "opened_at": self.opened_at.strip(),
            "closed_at": self.closed_at.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductPortfolioSnapshot:
    """Product-facing portfolio snapshot."""

    account_id: str
    balance: float
    equity: float
    positions: list[ProductPortfolioPosition] = field(default_factory=list)
    currency: str = "USD"
    margin_used: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.account_id, "Account ID")
        validate_non_negative_float(self.balance, "Balance")
        validate_non_negative_float(self.equity, "Equity")
        validate_product_portfolio_positions(self.positions)
        validate_currency(self.currency)
        validate_non_negative_float(self.margin_used, "Margin used")
        validate_metadata(self.metadata, "Metadata")
        validate_non_empty_string(self.timestamp, "Timestamp")

    @property
    def open_positions(self) -> list[ProductPortfolioPosition]:
        """Return open positions."""
        return [
            position
            for position in self.positions
            if position.open
        ]

    @property
    def closed_positions(self) -> list[ProductPortfolioPosition]:
        """Return closed positions."""
        return [
            position
            for position in self.positions
            if position.closed
        ]

    @property
    def total_exposure(self) -> float:
        """Return total open exposure."""
        return round(
            sum(position.notional_value for position in self.open_positions),
            4,
        )

    @property
    def unrealized_pnl(self) -> float:
        """Return total unrealized PnL."""
        return round(
            sum(position.unrealized_pnl for position in self.open_positions),
            4,
        )

    @property
    def free_margin(self) -> float:
        """Return free margin."""
        return round(float(self.equity) - float(self.margin_used), 4)

    def to_dict(self) -> dict[str, Any]:
        """Convert portfolio snapshot into dictionary."""
        return {
            "account_id": self.account_id.strip(),
            "balance": float(self.balance),
            "equity": float(self.equity),
            "currency": validate_currency(self.currency),
            "margin_used": float(self.margin_used),
            "free_margin": self.free_margin,
            "total_exposure": self.total_exposure,
            "unrealized_pnl": self.unrealized_pnl,
            "positions": [
                position.to_dict()
                for position in self.positions
            ],
            "open_positions": len(self.open_positions),
            "closed_positions": len(self.closed_positions),
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp.strip(),
        }


@dataclass(frozen=True)
class ProductPortfolioSummary:
    """Compact product portfolio summary."""

    total_positions: int = 0
    open_positions: int = 0
    closed_positions: int = 0
    buy_positions: int = 0
    sell_positions: int = 0
    total_exposure: float = 0.0
    unrealized_pnl: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_negative_integer(self.total_positions, "Total positions")
        validate_non_negative_integer(self.open_positions, "Open positions")
        validate_non_negative_integer(self.closed_positions, "Closed positions")
        validate_non_negative_integer(self.buy_positions, "Buy positions")
        validate_non_negative_integer(self.sell_positions, "Sell positions")
        validate_non_negative_float(self.total_exposure, "Total exposure")
        validate_metadata(self.metadata, "Metadata")

        if not isinstance(self.unrealized_pnl, int | float) or isinstance(self.unrealized_pnl, bool):
            raise ValueError("Unrealized PnL must be a number.")

    def to_dict(self) -> dict[str, Any]:
        """Convert portfolio summary into dictionary."""
        return {
            "total_positions": self.total_positions,
            "open_positions": self.open_positions,
            "closed_positions": self.closed_positions,
            "buy_positions": self.buy_positions,
            "sell_positions": self.sell_positions,
            "total_exposure": float(self.total_exposure),
            "unrealized_pnl": float(self.unrealized_pnl),
            "metadata": dict(self.metadata),
        }


@dataclass
class ProductPortfolioStore:
    """In-memory product portfolio store."""

    snapshots: dict[str, ProductPortfolioSnapshot] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.snapshots, dict):
            raise ValueError("Snapshots must be a dictionary.")

        for account_id, snapshot in self.snapshots.items():
            validate_non_empty_string(account_id, "Account ID")

            if not isinstance(snapshot, ProductPortfolioSnapshot):
                raise ValueError("Snapshots must contain ProductPortfolioSnapshot objects.")

    def add(self, snapshot: ProductPortfolioSnapshot) -> ProductPortfolioSnapshot:
        """Add snapshot to store."""
        if not isinstance(snapshot, ProductPortfolioSnapshot):
            raise ValueError("Snapshot must be a ProductPortfolioSnapshot.")

        self.snapshots[snapshot.account_id.strip()] = snapshot
        return snapshot

    def get(self, account_id: str) -> ProductPortfolioSnapshot | None:
        """Get snapshot by account ID."""
        normalized_account_id = validate_non_empty_string(account_id, "Account ID")
        return self.snapshots.get(normalized_account_id)

    def list(self) -> list[ProductPortfolioSnapshot]:
        """List snapshots."""
        return list(self.snapshots.values())

    def remove(self, account_id: str) -> ProductPortfolioSnapshot | None:
        """Remove snapshot by account ID."""
        normalized_account_id = validate_non_empty_string(account_id, "Account ID")
        return self.snapshots.pop(normalized_account_id, None)

    def clear(self) -> None:
        """Clear portfolio store."""
        self.snapshots.clear()

    def count(self) -> int:
        """Return snapshot count."""
        return len(self.snapshots)


def validate_positive_float(value: float | int, field_name: str) -> float:
    """Validate positive number."""
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ValueError(f"{field_name} must be a positive number.")

    return float(value)


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_currency(currency: str) -> str:
    """Validate currency code."""
    normalized = validate_non_empty_string(currency, "Currency").upper()

    if len(normalized) != 3 or not normalized.isalpha():
        raise ValueError("Currency must be a 3-letter code.")

    return normalized


def normalize_product_position_side(
    side: ProductPositionSide | str,
) -> ProductPositionSide:
    """Normalize product position side."""
    if isinstance(side, ProductPositionSide):
        return side

    normalized = validate_non_empty_string(side, "Position side").lower()

    try:
        return ProductPositionSide(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductPositionSide)
        raise ValueError(
            f"Invalid position side '{side}'. Valid sides: {valid}.",
        ) from exc


def normalize_product_position_status(
    status: ProductPositionStatus | str,
) -> ProductPositionStatus:
    """Normalize product position status."""
    if isinstance(status, ProductPositionStatus):
        return status

    normalized = validate_non_empty_string(status, "Position status").lower()

    try:
        return ProductPositionStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductPositionStatus)
        raise ValueError(
            f"Invalid position status '{status}'. Valid statuses: {valid}.",
        ) from exc


def validate_product_portfolio_positions(
    positions: list[ProductPortfolioPosition],
) -> list[ProductPortfolioPosition]:
    """Validate product portfolio positions."""
    if not isinstance(positions, list):
        raise ValueError("Positions must be a list.")

    for position in positions:
        if not isinstance(position, ProductPortfolioPosition):
            raise ValueError("Positions must contain ProductPortfolioPosition objects.")

    return positions


def build_product_portfolio_position(
    *,
    position_id: str,
    symbol: str,
    side: ProductPositionSide | str,
    quantity: float,
    entry_price: float,
    current_price: float = 0.0,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    status: ProductPositionStatus | str = ProductPositionStatus.OPEN,
    opened_at: str | None = None,
    closed_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> ProductPortfolioPosition:
    """Build product portfolio position."""
    position_kwargs: dict[str, Any] = {
        "position_id": position_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "entry_price": entry_price,
        "current_price": current_price,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "status": status,
        "closed_at": closed_at,
        "metadata": metadata or {},
    }

    if opened_at is not None:
        position_kwargs["opened_at"] = opened_at

    return ProductPortfolioPosition(**position_kwargs)


def build_product_portfolio_snapshot(
    *,
    account_id: str,
    balance: float,
    equity: float,
    positions: list[ProductPortfolioPosition] | None = None,
    currency: str = "USD",
    margin_used: float = 0.0,
    metadata: dict[str, Any] | None = None,
    timestamp: str | None = None,
) -> ProductPortfolioSnapshot:
    """Build product portfolio snapshot."""
    snapshot_kwargs: dict[str, Any] = {
        "account_id": account_id,
        "balance": balance,
        "equity": equity,
        "positions": positions or [],
        "currency": currency,
        "margin_used": margin_used,
        "metadata": metadata or {},
    }

    if timestamp is not None:
        snapshot_kwargs["timestamp"] = timestamp

    return ProductPortfolioSnapshot(**snapshot_kwargs)


def build_product_portfolio_summary(
    *,
    snapshot: ProductPortfolioSnapshot,
    metadata: dict[str, Any] | None = None,
) -> ProductPortfolioSummary:
    """Build product portfolio summary."""
    if not isinstance(snapshot, ProductPortfolioSnapshot):
        raise ValueError("Snapshot must be a ProductPortfolioSnapshot.")

    open_positions = snapshot.open_positions
    closed_positions = snapshot.closed_positions

    buy_positions = sum(
        1
        for position in open_positions
        if normalize_product_position_side(position.side) == ProductPositionSide.BUY
    )
    sell_positions = sum(
        1
        for position in open_positions
        if normalize_product_position_side(position.side) == ProductPositionSide.SELL
    )

    return ProductPortfolioSummary(
        total_positions=len(snapshot.positions),
        open_positions=len(open_positions),
        closed_positions=len(closed_positions),
        buy_positions=buy_positions,
        sell_positions=sell_positions,
        total_exposure=snapshot.total_exposure,
        unrealized_pnl=snapshot.unrealized_pnl,
        metadata=metadata or {},
    )


def build_product_portfolio_store(
    *,
    snapshots: dict[str, ProductPortfolioSnapshot] | None = None,
) -> ProductPortfolioStore:
    """Build product portfolio store."""
    return ProductPortfolioStore(
        snapshots=snapshots or {},
    )


def portfolio_snapshot_to_response(
    *,
    snapshot: ProductPortfolioSnapshot,
    context: ProductApiRequestContext | None = None,
    message: str = "Portfolio request completed.",
) -> ProductApiResponse:
    """Convert portfolio snapshot into product API response."""
    if not isinstance(snapshot, ProductPortfolioSnapshot):
        raise ValueError("Snapshot must be a ProductPortfolioSnapshot.")

    return product_api_success(
        data={
            "portfolio": snapshot.to_dict(),
            "summary": build_product_portfolio_summary(snapshot=snapshot).to_dict(),
        },
        message=message,
        context=context,
    )


def list_portfolios_response(
    *,
    snapshots: list[ProductPortfolioSnapshot],
    query: ProductApiListQuery | None = None,
    context: ProductApiRequestContext | None = None,
    message: str = "Portfolios listed successfully.",
) -> ProductApiResponse:
    """Build portfolio list response."""
    validate_product_portfolio_snapshots(snapshots)

    pagination = query.pagination if query else ProductApiPagination()
    paged_snapshots = paginate_product_portfolios(
        snapshots=snapshots,
        pagination=pagination,
    )
    result = ProductApiListResult(
        items=[
            snapshot.to_dict()
            for snapshot in paged_snapshots
        ],
        pagination=pagination,
        total_items=len(snapshots),
        metadata={
            "accounts": [
                snapshot.account_id.strip()
                for snapshot in snapshots
            ],
        },
    )

    return list_result_to_response(
        result=result,
        context=context,
        message=message,
    )


def create_portfolio_operation_response(
    *,
    snapshot: ProductPortfolioSnapshot,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Build create portfolio operation response."""
    if not isinstance(snapshot, ProductPortfolioSnapshot):
        raise ValueError("Snapshot must be a ProductPortfolioSnapshot.")

    return operation_result_to_response(
        result=ProductApiOperationResult(
            operation=ProductApiOperation.CREATE,
            resource_type=ProductApiRequestType.PORTFOLIO,
            resource_id=snapshot.account_id,
            accepted=True,
            result={
                "portfolio": snapshot.to_dict(),
            },
        ),
        context=context,
        message="Portfolio created successfully.",
    )


def get_portfolio_response(
    *,
    store: ProductPortfolioStore,
    account_id: str,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Get portfolio from store and return response."""
    if not isinstance(store, ProductPortfolioStore):
        raise ValueError("Store must be a ProductPortfolioStore.")

    snapshot = store.get(account_id)

    if snapshot is None:
        return product_api_failure(
            message="Portfolio not found.",
            code=ProductApiErrorCode.NOT_FOUND,
            details={
                "account_id": account_id.strip(),
            },
            context=context,
        )

    return portfolio_snapshot_to_response(
        snapshot=snapshot,
        context=context,
        message="Portfolio retrieved successfully.",
    )


def close_portfolio_position(
    position: ProductPortfolioPosition,
    *,
    closed_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProductPortfolioPosition:
    """Close portfolio position by returning a new payload."""
    if not isinstance(position, ProductPortfolioPosition):
        raise ValueError("Position must be a ProductPortfolioPosition.")

    return build_product_portfolio_position(
        position_id=position.position_id,
        symbol=position.symbol,
        side=position.side,
        quantity=position.quantity,
        entry_price=position.entry_price,
        current_price=position.current_price,
        stop_loss=position.stop_loss,
        take_profit=position.take_profit,
        status=ProductPositionStatus.CLOSED,
        opened_at=position.opened_at,
        closed_at=closed_at or datetime.now(UTC).isoformat(),
        metadata={
            **position.metadata,
            **(metadata or {}),
        },
    )


def paginate_product_portfolios(
    *,
    snapshots: list[ProductPortfolioSnapshot],
    pagination: ProductApiPagination,
) -> list[ProductPortfolioSnapshot]:
    """Paginate product portfolios."""
    validate_product_portfolio_snapshots(snapshots)

    if not isinstance(pagination, ProductApiPagination):
        raise ValueError("Pagination must be a ProductApiPagination.")

    return snapshots[pagination.offset : pagination.offset + pagination.page_size]


def filter_product_positions(
    *,
    positions: list[ProductPortfolioPosition],
    symbol: str | None = None,
    side: ProductPositionSide | str | None = None,
    status: ProductPositionStatus | str | None = None,
) -> list[ProductPortfolioPosition]:
    """Filter product positions."""
    validate_product_portfolio_positions(positions)

    filtered = list(positions)

    if symbol is not None:
        normalized_symbol = validate_product_symbol(symbol)
        filtered = [
            position
            for position in filtered
            if validate_product_symbol(position.symbol) == normalized_symbol
        ]

    if side is not None:
        normalized_side = normalize_product_position_side(side)
        filtered = [
            position
            for position in filtered
            if normalize_product_position_side(position.side) == normalized_side
        ]

    if status is not None:
        normalized_status = normalize_product_position_status(status)
        filtered = [
            position
            for position in filtered
            if normalize_product_position_status(position.status) == normalized_status
        ]

    return filtered


def validate_product_portfolio_snapshots(
    snapshots: list[ProductPortfolioSnapshot],
) -> list[ProductPortfolioSnapshot]:
    """Validate product portfolio snapshots."""
    if not isinstance(snapshots, list):
        raise ValueError("Snapshots must be a list.")

    for snapshot in snapshots:
        if not isinstance(snapshot, ProductPortfolioSnapshot):
            raise ValueError("Snapshots must contain ProductPortfolioSnapshot objects.")

    return snapshots