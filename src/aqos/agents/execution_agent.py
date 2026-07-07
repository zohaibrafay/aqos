"""
Execution agent.

Provides agent-level workflows for simulated order execution,
order fills, cancellations, position closing, and execution summaries.
"""

from __future__ import annotations

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)
from aqos.services import BrokerService


class ExecutionAgent(AgentBase):
    """
    Agent responsible for simulated execution workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "execute-trade",
        "place-order",
        "fill-order",
        "cancel-order",
        "close-position",
        "order-status",
        "execution-summary",
    }

    VALID_SIDES = {
        "buy",
        "sell",
    }

    VALID_ORDER_TYPES = {
        "market",
        "limit",
        "stop",
    }

    def __init__(
        self,
        broker_service: BrokerService | None = None,
    ) -> None:
        self._broker_service = broker_service or BrokerService()

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "execution-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for simulated order execution, fills, cancellations, and positions."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run an execution agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "execute-trade":
            return self.execute_trade(task)

        if task.action == "place-order":
            return self.place_order(task)

        if task.action == "fill-order":
            return self.fill_order(task)

        if task.action == "cancel-order":
            return self.cancel_order(task)

        if task.action == "close-position":
            return self.close_position(task)

        if task.action == "order-status":
            return self.order_status(task)

        if task.action == "execution-summary":
            return self.execution_summary(task)

        return self.failure(
            message=f"Unhandled execution agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return execution agent health.
        """

        return self.success(
            message="Execution agent is healthy.",
            data={
                "status": "ok",
                "orders": self._broker_service.count_orders(),
                "positions": self._broker_service.count_positions(),
                "supported_sides": sorted(self.VALID_SIDES),
                "supported_order_types": sorted(self.VALID_ORDER_TYPES),
            },
            metadata=task.metadata,
        )

    def execute_trade(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Execute a risk-approved trade request.

        This action expects a risk handoff payload.
        """

        trade = self.get_required_payload_value(
            payload=task.payload,
            key="trade",
        )

        if not isinstance(trade, dict):
            raise TypeError("Trade must be a dictionary.")

        allowed = bool(trade.get("allowed", False))
        execution_ready = bool(trade.get("execution_ready", False))

        if not allowed or not execution_ready:
            return self.failure(
                message=str(trade.get("reason", "Trade is not execution ready.")),
                data={
                    "allowed": allowed,
                    "execution_ready": execution_ready,
                },
                metadata=task.metadata,
            )

        order_id = str(
            trade.get(
                "order_id",
                f"order-{self._broker_service.count_orders() + 1}",
            )
        )

        symbol = str(trade.get("symbol", "UNKNOWN"))
        side = str(trade.get("side", "")).lower()
        quantity = float(trade.get("position_size", 0))
        order_type = str(trade.get("order_type", "market")).lower()
        price = trade.get("entry_price")

        self._validate_order_values(
            side=side,
            quantity=quantity,
            order_type=order_type,
        )

        try:
            order = self._broker_service.place_order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
                metadata={
                    **trade.get("metadata", {}),
                    **task.metadata,
                },
            )

            return self.success(
                message="Trade execution order placed.",
                data=self._order_to_dict(order),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def place_order(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Place a simulated broker order.
        """

        order_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="order_id",
            )
        )
        symbol = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="symbol",
            )
        )
        side = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="side",
            )
        ).lower()
        quantity = float(
            self.get_required_payload_value(
                payload=task.payload,
                key="quantity",
            )
        )

        order_type = str(task.payload.get("order_type", "market")).lower()
        price = task.payload.get("price")
        metadata = {
            **task.payload.get("metadata", {}),
            **task.metadata,
        }

        self._validate_order_values(
            side=side,
            quantity=quantity,
            order_type=order_type,
        )

        try:
            order = self._broker_service.place_order(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type=order_type,
                price=price,
                metadata=metadata,
            )

            return self.success(
                message="Order placed.",
                data=self._order_to_dict(order),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def fill_order(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Fill an existing simulated order.
        """

        order_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="order_id",
            )
        )
        fill_price = float(
            self.get_required_payload_value(
                payload=task.payload,
                key="fill_price",
            )
        )

        self._validate_positive_number(fill_price, "Fill price")

        try:
            filled_order = self._broker_service.fill_order(
                order_id=order_id,
                fill_price=fill_price,
            )

            position_id = f"position-{filled_order.order_id}"
            position = self._broker_service.get_required_position(position_id)

            return self.success(
                message="Order filled.",
                data=self._position_to_dict(position),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )
    def cancel_order(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Cancel an existing simulated order.
        """

        order_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="order_id",
            )
        )

        try:
            order = self._broker_service.cancel_order(order_id)

            return self.success(
                message="Order cancelled.",
                data=self._order_to_dict(order),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def close_position(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Close an existing simulated position.
        """

        position_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="position_id",
            )
        )
        exit_price = float(
            self.get_required_payload_value(
                payload=task.payload,
                key="exit_price",
            )
        )

        self._validate_positive_number(exit_price, "Exit price")

        try:
            position = self._broker_service.close_position(
                position_id=position_id,
                exit_price=exit_price,
            )

            return self.success(
                message="Position closed.",
                data=self._position_to_dict(position),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def order_status(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return order status.
        """

        order_id = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="order_id",
            )
        )

        try:
            order = self._broker_service.get_required_order(order_id)

            return self.success(
                message="Order status retrieved.",
                data=self._order_to_dict(order),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def execution_summary(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return execution summary.
        """

        return self.success(
            message="Execution summary generated.",
            data={
                "orders": self._broker_service.count_orders(),
                "positions": self._broker_service.count_positions(),
                "open_orders": len(self._broker_service.open_orders()),
                "filled_orders": len(self._broker_service.filled_orders()),
                "cancelled_orders": len(self._broker_service.cancelled_orders()),
                "open_positions": len(self._broker_service.open_positions()),
                "closed_positions": len(self._broker_service.closed_positions()),
                "realized_profit": self._broker_service.realized_profit(),
            },
            metadata=task.metadata,
        )

    def _order_to_dict(
        self,
        order,
    ) -> dict:
        """
        Convert broker order to dictionary.
        """

        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side,
            "quantity": order.quantity,
            "order_type": order.order_type,
            "status": order.status,
            "price": order.price,
            "fill_price": order.fill_price,
            "metadata": order.metadata,
        }

    def _position_to_dict(
        self,
        position,
    ) -> dict:
        """
        Convert broker position to dictionary.
        """

        return {
            "position_id": position.position_id,
            "order_id": position.order_id,
            "symbol": position.symbol,
            "side": position.side,
            "quantity": position.quantity,
            "entry_price": position.entry_price,
            "status": position.status,
            "exit_price": position.exit_price,
            "profit": position.profit,
            "metadata": position.metadata,
        }

    def _validate_order_values(
        self,
        side: str,
        quantity: float,
        order_type: str,
    ) -> None:
        """
        Validate order values.
        """

        if side not in self.VALID_SIDES:
            raise ValueError("Side must be buy or sell.")

        self._validate_positive_number(quantity, "Quantity")

        if order_type not in self.VALID_ORDER_TYPES:
            raise ValueError("Order type must be market, limit, or stop.")

    def _validate_positive_number(
        self,
        value: float,
        name: str,
    ) -> None:
        """
        Validate positive number.
        """

        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")


__all__ = [
    "ExecutionAgent",
]