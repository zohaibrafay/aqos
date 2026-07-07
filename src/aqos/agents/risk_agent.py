"""
Risk agent.

Provides agent-level workflows for trade risk assessment,
position sizing, approval checks, rejection reasons, and risk handoffs.
"""

from __future__ import annotations

from typing import Any

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)


class RiskAgent(AgentBase):
    """
    Agent responsible for risk workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "position-size",
        "assess-trade",
        "approve-trade",
        "reject-reason",
        "risk-handoff",
    }

    VALID_SIDES = {
        "buy",
        "sell",
    }

    def __init__(
        self,
        default_max_risk_percent: float = 0.02,
    ) -> None:
        self._validate_risk_percent(default_max_risk_percent)

        self._default_max_risk_percent = default_max_risk_percent

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "risk-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for trade risk assessment, position sizing, and approval checks."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a risk agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "position-size":
            return self.position_size(task)

        if task.action == "assess-trade":
            return self.assess_trade(task)

        if task.action == "approve-trade":
            return self.approve_trade(task)

        if task.action == "reject-reason":
            return self.reject_reason(task)

        if task.action == "risk-handoff":
            return self.risk_handoff(task)

        return self.failure(
            message=f"Unhandled risk agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return risk agent health.
        """

        return self.success(
            message="Risk agent is healthy.",
            data={
                "status": "ok",
                "supported_sides": sorted(self.VALID_SIDES),
                "default_max_risk_percent": self._default_max_risk_percent,
            },
            metadata=task.metadata,
        )

    def position_size(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Calculate position size.
        """

        trade_request = self._get_trade_request(task)
        sizing = self._calculate_position_size(trade_request)

        return self.success(
            message="Position size calculated.",
            data=sizing,
            metadata=task.metadata,
        )

    def assess_trade(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Assess whether a trade is allowed.
        """

        trade_request = self._get_trade_request(task)
        assessment = self._assess_trade_request(trade_request)

        return self.success(
            message="Trade risk assessed.",
            data=assessment,
            metadata=task.metadata,
        )

    def approve_trade(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return trade approval decision.
        """

        trade_request = self._get_trade_request(task)
        assessment = self._assess_trade_request(trade_request)

        return self.success(
            message="Trade approval checked.",
            data={
                "approved": assessment["allowed"],
                "reason": assessment["reason"],
                "position_size": assessment["position_size"],
            },
            metadata=task.metadata,
        )

    def reject_reason(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return risk rejection reason.
        """

        trade_request = self._get_trade_request(task)
        assessment = self._assess_trade_request(trade_request)

        reason = (
            "Trade is not rejected."
            if assessment["allowed"]
            else assessment["reason"]
        )

        return self.success(
            message="Risk rejection reason generated.",
            data={
                "allowed": assessment["allowed"],
                "reason": reason,
            },
            metadata=task.metadata,
        )

    def risk_handoff(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Build a risk handoff payload for execution agent.
        """

        trade_request = self._get_trade_request(task)
        assessment = self._assess_trade_request(trade_request)

        handoff = {
            "symbol": str(trade_request.get("symbol", "UNKNOWN")).upper(),
            "side": str(trade_request["side"]).lower(),
            "allowed": assessment["allowed"],
            "reason": assessment["reason"],
            "position_size": assessment["position_size"],
            "entry_price": float(trade_request["entry_price"]),
            "stop_loss_price": float(trade_request["stop_loss_price"]),
            "risk_amount": assessment["risk_amount"],
            "risk_percent": float(trade_request["risk_percent"]),
            "execution_ready": assessment["allowed"],
        }

        if "take_profit_price" in trade_request:
            handoff["take_profit_price"] = float(trade_request["take_profit_price"])

        return self.success(
            message="Risk handoff generated.",
            data=handoff,
            metadata=task.metadata,
        )

    def _get_trade_request(
        self,
        task: AgentTask,
    ) -> dict[str, Any]:
        """
        Get trade request from task payload.
        """

        trade_request = self.get_required_payload_value(
            payload=task.payload,
            key="trade_request",
        )

        if not isinstance(trade_request, dict):
            raise TypeError("Trade request must be a dictionary.")

        if not trade_request:
            raise ValueError("Trade request cannot be empty.")

        return trade_request

    def _assess_trade_request(
        self,
        trade_request: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Assess a trade request.
        """

        try:
            self._validate_trade_request(trade_request)
            sizing = self._calculate_position_size(trade_request)

            max_position_size = trade_request.get("max_position_size")

            if max_position_size is not None:
                self._validate_positive_number(
                    float(max_position_size),
                    "Max position size",
                )

                if sizing["position_size"] > float(max_position_size):
                    return {
                        **sizing,
                        "allowed": False,
                        "reason": "Position size exceeds maximum allowed size.",
                    }

            return {
                **sizing,
                "allowed": True,
                "reason": "Trade allowed.",
            }
        except ValueError as exc:
            return {
                "allowed": False,
                "reason": str(exc),
                "position_size": None,
                "risk_amount": None,
                "risk_per_unit": None,
            }

    def _calculate_position_size(
        self,
        trade_request: dict[str, Any],
    ) -> dict[str, float]:
        """
        Calculate risk-based position size.
        """

        self._validate_trade_request(trade_request)

        account_balance = float(trade_request["account_balance"])
        risk_percent = float(trade_request["risk_percent"])
        entry_price = float(trade_request["entry_price"])
        stop_loss_price = float(trade_request["stop_loss_price"])

        risk_amount = account_balance * risk_percent
        risk_per_unit = abs(entry_price - stop_loss_price)

        if risk_per_unit == 0:
            raise ValueError("Risk per unit cannot be zero.")

        position_size = risk_amount / risk_per_unit

        return {
            "account_balance": account_balance,
            "risk_percent": risk_percent,
            "risk_amount": risk_amount,
            "entry_price": entry_price,
            "stop_loss_price": stop_loss_price,
            "risk_per_unit": risk_per_unit,
            "position_size": position_size,
        }

    def _validate_trade_request(
        self,
        trade_request: dict[str, Any],
    ) -> None:
        """
        Validate trade request.
        """

        required_keys = [
            "side",
            "account_balance",
            "risk_percent",
            "entry_price",
            "stop_loss_price",
        ]

        for key in required_keys:
            if key not in trade_request:
                raise ValueError(f"Trade request is missing required key: {key}")

        side = str(trade_request["side"]).lower()
        account_balance = float(trade_request["account_balance"])
        risk_percent = float(trade_request["risk_percent"])
        entry_price = float(trade_request["entry_price"])
        stop_loss_price = float(trade_request["stop_loss_price"])

        self._validate_side(side)
        self._validate_positive_number(account_balance, "Account balance")
        self._validate_risk_percent(risk_percent)
        self._validate_positive_number(entry_price, "Entry price")
        self._validate_positive_number(stop_loss_price, "Stop loss price")

        max_risk_percent = float(
            trade_request.get(
                "max_risk_percent",
                self._default_max_risk_percent,
            )
        )

        self._validate_risk_percent(max_risk_percent)

        if risk_percent > max_risk_percent:
            raise ValueError("Risk percent exceeds maximum allowed risk percent.")

        if side == "buy" and stop_loss_price >= entry_price:
            raise ValueError("Buy trade stop loss must be below entry price.")

        if side == "sell" and stop_loss_price <= entry_price:
            raise ValueError("Sell trade stop loss must be above entry price.")

    def _validate_side(
        self,
        side: str,
    ) -> None:
        """
        Validate trade side.
        """

        if side not in self.VALID_SIDES:
            raise ValueError("Side must be buy or sell.")

    def _validate_risk_percent(
        self,
        risk_percent: float,
    ) -> None:
        """
        Validate risk percent.
        """

        if risk_percent <= 0 or risk_percent > 1:
            raise ValueError("Risk percent must be between 0 and 1.")

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
    "RiskAgent",
]