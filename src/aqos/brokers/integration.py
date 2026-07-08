"""
AQOS broker execution integration helpers.

This module connects broker registries, paper brokers, exchange HTTP adapters,
account/position adapters, and AQOS-friendly execution payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.brokers.account import (
    BrokerAccountSnapshot,
    PositionAccountAdapter,
    build_position_account_adapter,
)
from aqos.brokers.base import (
    BrokerCapability,
    BrokerResult,
    broker_failure,
    broker_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_positive_float,
    validate_string,
)
from aqos.brokers.exchange_http import ExchangeHttpBrokerAdapter
from aqos.brokers.orders import (
    BrokerOrderRequest,
    BrokerTrade,
    OrderType,
    build_broker_order_request,
    validate_order_symbol,
)
from aqos.brokers.paper import (
    PaperBrokerAdapter,
    build_paper_broker_adapter,
)
from aqos.brokers.registry import (
    BrokerRegistry,
    BrokerRegistryEntry,
    build_broker_registry,
    register_paper_broker,
    resolve_paper_broker_adapter,
    resolve_position_account_adapter,
    validate_broker_registry,
)


EXECUTION_INTEGRATION_BROKER_ID = "broker-execution-integration"


@dataclass(frozen=True)
class BrokerExecutionPayload:
    """AQOS-friendly broker execution payload."""

    broker_id: str
    operation: str
    success: bool
    order: dict[str, Any] = field(default_factory=dict)
    trade: dict[str, Any] = field(default_factory=dict)
    account: dict[str, Any] = field(default_factory=dict)
    positions: list[dict[str, Any]] = field(default_factory=list)
    snapshot: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.broker_id, "Broker ID")
        validate_non_empty_string(self.operation, "Operation")

        if not isinstance(self.success, bool):
            raise ValueError("Success must be a boolean.")

        validate_metadata(self.order, "Order")
        validate_metadata(self.trade, "Trade")
        validate_metadata(self.account, "Account")
        validate_execution_positions(self.positions)
        validate_metadata(self.snapshot, "Snapshot")
        validate_string(self.error, "Error")
        validate_metadata(self.metadata, "Metadata")

    @property
    def failed(self) -> bool:
        """Return whether execution payload failed."""
        return not self.success

    @property
    def has_order(self) -> bool:
        """Return whether payload has order data."""
        return bool(self.order)

    @property
    def has_trade(self) -> bool:
        """Return whether payload has trade data."""
        return bool(self.trade)

    @property
    def has_account(self) -> bool:
        """Return whether payload has account data."""
        return bool(self.account)

    @property
    def position_count(self) -> int:
        """Return position count."""
        return len(self.positions)

    def to_dict(self) -> dict[str, Any]:
        """Convert payload into dictionary."""
        return {
            "broker_id": self.broker_id.strip(),
            "operation": self.operation.strip(),
            "success": self.success,
            "failed": self.failed,
            "order": dict(self.order),
            "trade": dict(self.trade),
            "account": dict(self.account),
            "positions": [dict(position) for position in self.positions],
            "snapshot": dict(self.snapshot),
            "error": self.error.strip(),
            "has_order": self.has_order,
            "has_trade": self.has_trade,
            "has_account": self.has_account,
            "position_count": self.position_count,
            "metadata": dict(self.metadata),
        }


@dataclass
class BrokerExecutionHub:
    """Broker execution integration hub."""

    registry: BrokerRegistry = field(default_factory=build_broker_registry)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_broker_registry(self.registry)
        validate_metadata(self.metadata, "Metadata")

    def resolve_execution_adapter(
        self,
        *,
        preferred_broker_id: str = "",
        capability: BrokerCapability | str = BrokerCapability.MARKET_ORDERS,
    ) -> PaperBrokerAdapter | ExchangeHttpBrokerAdapter | None:
        """Resolve supported execution adapter."""
        if preferred_broker_id:
            adapter = self.registry.get_adapter(preferred_broker_id)
        else:
            adapter = self.registry.resolve_adapter(
                capability=capability,
            )

        if adapter is None:
            return None

        if isinstance(adapter, PaperBrokerAdapter | ExchangeHttpBrokerAdapter):
            return adapter

        raise ValueError("Resolved adapter is not a supported execution adapter.")

    def submit_order(
        self,
        request: BrokerOrderRequest,
        *,
        market_price: float = 0.0,
    ) -> BrokerResult:
        """Submit order through registered broker adapter."""
        if not isinstance(request, BrokerOrderRequest):
            raise ValueError("Request must be a BrokerOrderRequest.")

        validate_non_negative_float(market_price, "Market price")

        adapter = self.resolve_execution_adapter(
            preferred_broker_id=request.broker_id,
            capability=BrokerCapability.MARKET_ORDERS,
        )

        if adapter is None:
            return execution_failure(
                error="Execution adapter is not registered.",
                operation="submit_order",
                metadata={
                    "broker_id": request.broker_id,
                },
            )

        if isinstance(adapter, PaperBrokerAdapter):
            return adapter.submit_order(
                request,
                market_price=market_price,
            )

        return adapter.submit_order(request)

    def submit_market_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: float,
        market_price: float,
        preferred_broker_id: str = "",
        client_order_id: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BrokerResult:
        """Submit market order through registered broker adapter."""
        validate_order_symbol(symbol)
        validate_positive_float(quantity, "Quantity")
        validate_positive_float(market_price, "Market price")
        validate_string(preferred_broker_id, "Preferred broker ID")
        validate_string(client_order_id, "Client order ID")
        validate_metadata(metadata or {}, "Metadata")

        adapter = self.resolve_execution_adapter(
            preferred_broker_id=preferred_broker_id,
            capability=BrokerCapability.MARKET_ORDERS,
        )

        if adapter is None:
            return execution_failure(
                error="Execution adapter is not registered.",
                operation="submit_market_order",
            )

        request = build_broker_order_request(
            broker_id=adapter.broker_id,
            symbol=symbol,
            side=side,
            order_type=OrderType.MARKET,
            quantity=quantity,
            client_order_id=client_order_id,
            metadata=metadata or {},
        )

        if isinstance(adapter, PaperBrokerAdapter):
            return adapter.submit_order(
                request,
                market_price=market_price,
            )

        return adapter.submit_order(request)


    
    def cancel_order(
        self,
        *,
        order_id: str,
        preferred_broker_id: str = "",
    ) -> BrokerResult:
        """Cancel order through registered broker adapter."""
        validate_non_empty_string(order_id, "Order ID")
        validate_string(preferred_broker_id, "Preferred broker ID")

        adapter = self.resolve_execution_adapter(
            preferred_broker_id=preferred_broker_id,
            capability=BrokerCapability.MARKET_ORDERS,
        )

        if adapter is None:
            return execution_failure(
                error="Execution adapter is not registered.",
                operation="cancel_order",
                metadata={
                    "order_id": order_id,
                },
            )

        if isinstance(adapter, PaperBrokerAdapter):
            return adapter.cancel_order(order_id)

        return adapter.cancel_order(order_id=order_id)

    def apply_trade_to_account(
        self,
        trade: BrokerTrade,
        *,
        preferred_broker_id: str = "",
    ) -> BrokerResult:
        """Apply trade to registered account adapter."""
        if not isinstance(trade, BrokerTrade):
            raise ValueError("Trade must be BrokerTrade.")

        account_adapter = resolve_position_account_adapter(
            self.registry,
            preferred_broker_id=preferred_broker_id or trade.broker_id,
        )

        if account_adapter is None:
            return execution_failure(
                error="Position account adapter is not registered.",
                operation="apply_trade_to_account",
                metadata={
                    "broker_id": trade.broker_id,
                    "trade_id": trade.trade_id,
                },
            )

        position = account_adapter.apply_trade(trade)
        snapshot = account_adapter.snapshot()

        return broker_success(
            broker_id=account_adapter.broker_id,
            data={
                "position": position.to_dict(),
                "snapshot": snapshot.to_dict(),
            },
            message="Trade applied to account adapter.",
            metadata={
                "operation": "apply_trade_to_account",
            },
        )

    def account_snapshot(
        self,
        *,
        preferred_broker_id: str = "",
    ) -> BrokerResult:
        """Return account snapshot from registered account adapter."""
        validate_string(preferred_broker_id, "Preferred broker ID")

        account_adapter = resolve_position_account_adapter(
            self.registry,
            preferred_broker_id=preferred_broker_id,
        )

        if account_adapter is None:
            return execution_failure(
                error="Position account adapter is not registered.",
                operation="account_snapshot",
            )

        return broker_success(
            broker_id=account_adapter.broker_id,
            data={
                "snapshot": account_adapter.snapshot().to_dict(),
            },
            message="Broker account snapshot generated.",
            metadata={
                "operation": "account_snapshot",
            },
        )

    def payload_from_result(
        self,
        result: BrokerResult,
        *,
        operation: str,
    ) -> BrokerExecutionPayload:
        """Convert broker result into execution payload."""
        return broker_result_to_execution_payload(
            result,
            operation=operation,
        )

    def summary(self) -> dict[str, Any]:
        """Return execution hub summary."""
        return {
            "broker_id": EXECUTION_INTEGRATION_BROKER_ID,
            "registry": self.registry.summary().to_dict(),
            "metadata": dict(self.metadata),
        }


def validate_execution_positions(
    positions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Validate execution position payloads."""
    if not isinstance(positions, list):
        raise ValueError("Positions must be a list.")

    for position in positions:
        validate_metadata(position, "Position")

    return positions


def validate_broker_execution_hub(
    hub: BrokerExecutionHub,
) -> BrokerExecutionHub:
    """Validate broker execution hub."""
    if not isinstance(hub, BrokerExecutionHub):
        raise ValueError("Hub must be a BrokerExecutionHub.")

    return hub


def build_broker_execution_payload(
    *,
    broker_id: str,
    operation: str,
    success: bool,
    order: dict[str, Any] | None = None,
    trade: dict[str, Any] | None = None,
    account: dict[str, Any] | None = None,
    positions: list[dict[str, Any]] | None = None,
    snapshot: dict[str, Any] | None = None,
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> BrokerExecutionPayload:
    """Build broker execution payload."""
    return BrokerExecutionPayload(
        broker_id=broker_id,
        operation=operation,
        success=success,
        order=order or {},
        trade=trade or {},
        account=account or {},
        positions=positions or [],
        snapshot=snapshot or {},
        error=error,
        metadata=metadata or {},
    )


def broker_result_order(result: BrokerResult) -> dict[str, Any] | None:
    """Extract order payload from broker result."""
    if not isinstance(result, BrokerResult):
        raise ValueError("Result must be BrokerResult.")

    if result.failed:
        return None

    order = result.data.get("order")

    if order is None:
        return None

    validate_metadata(order, "Order payload")
    return order


def broker_result_trade(result: BrokerResult) -> dict[str, Any] | None:
    """Extract trade payload from broker result."""
    if not isinstance(result, BrokerResult):
        raise ValueError("Result must be BrokerResult.")

    if result.failed:
        return None

    trade = result.data.get("trade")

    if trade is None:
        return None

    validate_metadata(trade, "Trade payload")
    return trade


def broker_result_snapshot(result: BrokerResult) -> dict[str, Any] | None:
    """Extract snapshot payload from broker result."""
    if not isinstance(result, BrokerResult):
        raise ValueError("Result must be BrokerResult.")

    if result.failed:
        return None

    snapshot = result.data.get("snapshot")

    if snapshot is None:
        return None

    validate_metadata(snapshot, "Snapshot payload")
    return snapshot


def broker_result_account(result: BrokerResult) -> dict[str, Any] | None:
    """Extract account payload from broker result."""
    if not isinstance(result, BrokerResult):
        raise ValueError("Result must be BrokerResult.")

    if result.failed:
        return None

    account = result.data.get("account")

    if account is None:
        snapshot = broker_result_snapshot(result)
        if snapshot is not None:
            account = snapshot.get("account")

    if account is None:
        return None

    validate_metadata(account, "Account payload")
    return account


def broker_result_positions(result: BrokerResult) -> list[dict[str, Any]] | None:
    """Extract positions payload from broker result."""
    if not isinstance(result, BrokerResult):
        raise ValueError("Result must be BrokerResult.")

    if result.failed:
        return None

    positions = result.data.get("positions")

    if positions is None:
        snapshot = broker_result_snapshot(result)
        if snapshot is not None:
            positions = snapshot.get("positions")

    if positions is None:
        return None

    validate_execution_positions(positions)
    return positions


def broker_result_to_execution_payload(
    result: BrokerResult,
    *,
    operation: str,
) -> BrokerExecutionPayload:
    """Convert broker result into execution payload."""
    if not isinstance(result, BrokerResult):
        raise ValueError("Result must be BrokerResult.")

    return build_broker_execution_payload(
        broker_id=result.broker_id,
        operation=operation,
        success=result.success,
        order=broker_result_order(result) or {},
        trade=broker_result_trade(result) or {},
        account=broker_result_account(result) or {},
        positions=broker_result_positions(result) or [],
        snapshot=broker_result_snapshot(result) or {},
        error=result.error,
        metadata={
            **result.metadata,
            "message": result.message,
        },
    )


def register_execution_adapters(
    *,
    registry: BrokerRegistry,
    broker_adapter: PaperBrokerAdapter | ExchangeHttpBrokerAdapter,
    account_adapter: PositionAccountAdapter | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerRegistryEntry:
    """Register execution adapter and optional account adapter."""
    validate_broker_registry(registry)

    if isinstance(broker_adapter, PaperBrokerAdapter):
        return register_paper_broker(
            registry=registry,
            adapter=broker_adapter,
            account_adapter=account_adapter,
            metadata=metadata or {},
        )

    if isinstance(broker_adapter, ExchangeHttpBrokerAdapter):
        return registry.register_adapter(
            config=broker_adapter.broker_config,
            adapter=broker_adapter,
            account_adapter=account_adapter,
            metadata=metadata or {},
        )

    raise ValueError("Broker adapter must be PaperBrokerAdapter or ExchangeHttpBrokerAdapter.")


def build_broker_execution_hub(
    *,
    registry: BrokerRegistry | None = None,
    metadata: dict[str, Any] | None = None,
) -> BrokerExecutionHub:
    """Build broker execution hub."""
    return BrokerExecutionHub(
        registry=registry or build_broker_registry(),
        metadata=metadata or {},
    )


def build_sample_broker_registry(
    *,
    broker_id: str = "paper-broker",
    cash_balance: float = 100_000.0,
) -> BrokerRegistry:
    """Build sample broker registry with paper broker and account adapter."""
    registry = build_broker_registry()
    paper_adapter = build_paper_broker_adapter(
        broker_id=broker_id,
        cash_balance=cash_balance,
    )
    account_adapter = build_position_account_adapter(
        broker_config=paper_adapter.broker_config,
        account_id=f"{broker_id}-account",
        cash_balance=cash_balance,
    )

    register_execution_adapters(
        registry=registry,
        broker_adapter=paper_adapter,
        account_adapter=account_adapter,
        metadata={
            "sample": True,
        },
    )

    return registry


def build_sample_broker_execution_hub(
    *,
    broker_id: str = "paper-broker",
    cash_balance: float = 100_000.0,
) -> BrokerExecutionHub:
    """Build sample broker execution hub."""
    return build_broker_execution_hub(
        registry=build_sample_broker_registry(
            broker_id=broker_id,
            cash_balance=cash_balance,
        ),
        metadata={
            "sample": True,
        },
    )


def submit_broker_order(
    *,
    hub: BrokerExecutionHub,
    request: BrokerOrderRequest,
    market_price: float = 0.0,
) -> BrokerResult:
    """Submit broker order through hub."""
    validate_broker_execution_hub(hub)
    return hub.submit_order(
        request,
        market_price=market_price,
    )


def submit_market_broker_order(
    *,
    hub: BrokerExecutionHub,
    symbol: str,
    side: str,
    quantity: float,
    market_price: float,
    preferred_broker_id: str = "",
    client_order_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Submit market broker order through hub."""
    validate_broker_execution_hub(hub)

    return hub.submit_market_order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        market_price=market_price,
        preferred_broker_id=preferred_broker_id,
        client_order_id=client_order_id,
        metadata=metadata or {},
    )


def cancel_broker_order_via_hub(
    *,
    hub: BrokerExecutionHub,
    order_id: str,
    preferred_broker_id: str = "",
) -> BrokerResult:
    """Cancel broker order through hub."""
    validate_broker_execution_hub(hub)

    return hub.cancel_order(
        order_id=order_id,
        preferred_broker_id=preferred_broker_id,
    )


def fetch_broker_account_snapshot(
    *,
    hub: BrokerExecutionHub,
    preferred_broker_id: str = "",
) -> BrokerResult:
    """Fetch broker account snapshot through hub."""
    validate_broker_execution_hub(hub)

    return hub.account_snapshot(
        preferred_broker_id=preferred_broker_id,
    )


def apply_trade_to_broker_account(
    *,
    hub: BrokerExecutionHub,
    trade: BrokerTrade,
    preferred_broker_id: str = "",
) -> BrokerResult:
    """Apply trade to broker account through hub."""
    validate_broker_execution_hub(hub)

    return hub.apply_trade_to_account(
        trade,
        preferred_broker_id=preferred_broker_id,
    )


def broker_account_snapshot_to_payload(
    snapshot: BrokerAccountSnapshot,
    *,
    operation: str = "account_snapshot",
) -> BrokerExecutionPayload:
    """Convert account snapshot into execution payload."""
    if not isinstance(snapshot, BrokerAccountSnapshot):
        raise ValueError("Snapshot must be BrokerAccountSnapshot.")

    payload = snapshot.to_dict()

    return build_broker_execution_payload(
        broker_id=snapshot.account.broker_id,
        operation=operation,
        success=True,
        account=payload["account"],
        positions=payload["positions"],
        snapshot=payload,
        metadata={
            "trade_count": snapshot.trade_count,
            "position_count": snapshot.position_count,
        },
    )


def execution_failure(
    *,
    error: str,
    operation: str,
    metadata: dict[str, Any] | None = None,
) -> BrokerResult:
    """Build execution integration failure result."""
    return broker_failure(
        broker_id=EXECUTION_INTEGRATION_BROKER_ID,
        error=error,
        message="Broker execution operation failed.",
        metadata={
            "operation": validate_non_empty_string(operation, "Operation"),
            **(metadata or {}),
        },
    )