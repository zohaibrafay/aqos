"""
Agent interface.

Provides an application-facing interface for AI-agent style access
to AQOS through standardized interface envelopes.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aqos.interfaces.api_interface import APIInterface
from aqos.interfaces.dashboard_interface import DashboardInterface
from aqos.interfaces.memory import MemoryInterface
from aqos.interfaces.schemas import (
    BacktestRequest,
    InterfaceEnvelope,
    RiskRequest,
    StrategyRequest,
)


class AgentInterface:
    """
    Agent-facing interface for AQOS.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "dashboard-overview",
        "market-summary",
        "strategy-decision",
        "risk-assessment",
        "backtest",
        "remember",
        "recall",
    }

    def __init__(
        self,
        api_interface: APIInterface | None = None,
        dashboard_interface: DashboardInterface | None = None,
        memory_interface: MemoryInterface | None = None,
    ) -> None:
        self._api_interface = api_interface or APIInterface()
        self._dashboard_interface = dashboard_interface or DashboardInterface()
        self._memory_interface = memory_interface

    def run_action(
        self,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> InterfaceEnvelope:
        """
        Run an agent action.
        """

        try:
            normalized_action = self._normalize_action(action)
            payload = payload or {}

            if normalized_action not in self.SUPPORTED_ACTIONS:
                return self._failure(
                    message=f"Unsupported agent action: {normalized_action}"
                )

            if normalized_action == "health":
                return self.health()

            if normalized_action == "dashboard-overview":
                return self.dashboard_overview()

            if normalized_action == "market-summary":
                return self.market_summary(payload)

            if normalized_action == "strategy-decision":
                return self.strategy_decision(payload)

            if normalized_action == "risk-assessment":
                return self.risk_assessment(payload)

            if normalized_action == "backtest":
                return self.backtest(payload)

            if normalized_action == "remember":
                return self.remember(payload)

            if normalized_action == "recall":
                return self.recall(payload)

            return self._failure(
                message=f"Unsupported agent action: {normalized_action}"
            )
        except (TypeError, ValueError) as exc:
            return self._failure(str(exc))

    def health(self) -> InterfaceEnvelope:
        """
        Return agent interface health status.
        """

        return self._success(
            message="Agent interface is healthy.",
            payload={
                "status": "ok",
            },
        )

    def dashboard_overview(self) -> InterfaceEnvelope:
        """
        Return dashboard overview for an agent.
        """

        return self._dashboard_interface.overview()

    def market_summary(
        self,
        payload: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Return market summary for an agent.
        """

        symbol = self._get_required_value(
            data=payload,
            key="symbol",
        )
        timeframe = self._get_required_value(
            data=payload,
            key="timeframe",
        )

        return self._dashboard_interface.market_data_summary(
            symbol=str(symbol),
            timeframe=str(timeframe),
        )

    def strategy_decision(
        self,
        payload: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Generate strategy decision for an agent.
        """

        market_state = self._get_required_value(
            data=payload,
            key="market_state",
        )

        metadata = payload.get("metadata", {})

        request = StrategyRequest(
            market_state=market_state,
            metadata=metadata,
        )

        return self._api_interface.generate_strategy_decision(request)

    def risk_assessment(
        self,
        payload: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run risk assessment for an agent.
        """

        trade_request = self._get_required_value(
            data=payload,
            key="trade_request",
        )

        metadata = payload.get("metadata", {})

        request = RiskRequest(
            trade_request=trade_request,
            metadata=metadata,
        )

        return self._api_interface.assess_risk(request)

    def backtest(
        self,
        payload: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run backtest for an agent.
        """

        request = BacktestRequest(
            name=str(
                self._get_required_value(
                    data=payload,
                    key="name",
                )
            ),
            profits=self._get_required_value(
                data=payload,
                key="profits",
            ),
            initial_balance=float(
                self._get_required_value(
                    data=payload,
                    key="initial_balance",
                )
            ),
            metadata=payload.get("metadata", {}),
        )

        return self._api_interface.run_backtest(request)

    def remember(
        self,
        payload: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Store memory for an agent.
        """

        if self._memory_interface is None:
            return self._failure("Memory interface is not configured.")

        memory_id = self._get_required_value(
            data=payload,
            key="memory_id",
        )
        content = self._get_required_value(
            data=payload,
            key="content",
        )

        metadata = payload.get("metadata", {})

        record = self._memory_interface.store(
            memory_id=str(memory_id),
            content=str(content),
            metadata=metadata,
        )

        return self._success(
            message="Memory stored.",
            payload=asdict(record),
            metadata=metadata,
        )

    def recall(
        self,
        payload: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Search memory for an agent.
        """

        if self._memory_interface is None:
            return self._failure("Memory interface is not configured.")

        query = self._get_required_value(
            data=payload,
            key="query",
        )

        limit = payload.get("limit")

        results = self._memory_interface.search(
            query=str(query),
            limit=limit,
        )

        return self._success(
            message="Memory recall completed.",
            payload={
                "query": query,
                "results": [
                    asdict(result)
                    for result in results
                ],
            },
        )

    def available_actions(self) -> list[str]:
        """
        Return supported agent actions.
        """

        return sorted(self.SUPPORTED_ACTIONS)

    def _normalize_action(
        self,
        action: str,
    ) -> str:
        """
        Normalize agent action.
        """

        if not isinstance(action, str):
            raise TypeError("Agent action must be a string.")

        if not action:
            raise ValueError("Agent action cannot be empty.")

        return action.lower().strip().replace("_", "-")

    def _get_required_value(
        self,
        data: dict[str, Any],
        key: str,
    ) -> Any:
        """
        Get required value from payload.
        """

        if not isinstance(data, dict):
            raise TypeError("Agent payload must be a dictionary.")

        if not key:
            raise ValueError("Payload key cannot be empty.")

        if key not in data:
            raise ValueError(f"Missing required payload key: {key}")

        return data[key]

    def _success(
        self,
        message: str,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InterfaceEnvelope:
        """
        Build success envelope.
        """

        return InterfaceEnvelope(
            success=True,
            message=message,
            payload=payload or {},
            metadata=metadata or {},
        )

    def _failure(
        self,
        message: str,
    ) -> InterfaceEnvelope:
        """
        Build failure envelope.
        """

        return InterfaceEnvelope(
            success=False,
            message=message,
            payload={},
            metadata={},
        )


__all__ = [
    "AgentInterface",
]