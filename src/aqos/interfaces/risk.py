"""
Risk interface.

Defines the contract that all AQOS risk implementations must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class RiskInterfaceDecision:
    """
    Represents a generic risk decision.
    """

    allowed: bool
    reason: str
    position_size: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class RiskInterface(ABC):
    """
    Interface for AQOS risk systems.

    Any risk implementation must be able to validate a trade request,
    explain rejection reasons, and calculate position size.
    """

    VALID_SIDES = {
        "buy",
        "sell",
    }

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return risk system name.
        """

    @abstractmethod
    def validate_trade(
        self,
        trade_request: dict[str, Any],
    ) -> bool:
        """
        Validate whether a trade request is allowed.
        """

    @abstractmethod
    def rejection_reason(
        self,
        trade_request: dict[str, Any],
    ) -> str:
        """
        Return the reason a trade request is rejected.
        """

    @abstractmethod
    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        """
        Calculate position size for a trade.
        """

    def assess(
        self,
        trade_request: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> RiskInterfaceDecision:
        """
        Build a complete risk decision.
        """

        self.validate_trade_request(trade_request)

        allowed = self.validate_trade(trade_request)

        if not allowed:
            return RiskInterfaceDecision(
                allowed=False,
                reason=self.rejection_reason(trade_request),
                position_size=None,
                metadata=metadata or {},
            )

        position_size = self.calculate_position_size(
            account_balance=float(
                self.get_required_trade_value(
                    trade_request=trade_request,
                    key="account_balance",
                )
            ),
            risk_percent=float(
                self.get_required_trade_value(
                    trade_request=trade_request,
                    key="risk_percent",
                )
            ),
            entry_price=float(
                self.get_required_trade_value(
                    trade_request=trade_request,
                    key="entry_price",
                )
            ),
            stop_loss_price=float(
                self.get_required_trade_value(
                    trade_request=trade_request,
                    key="stop_loss_price",
                )
            ),
        )

        return RiskInterfaceDecision(
            allowed=True,
            reason="Trade allowed.",
            position_size=position_size,
            metadata=metadata or {},
        )

    def validate_trade_request(
        self,
        trade_request: dict[str, Any],
    ) -> None:
        """
        Validate trade request.
        """

        if not isinstance(trade_request, dict):
            raise TypeError("Trade request must be a dictionary.")

        if not trade_request:
            raise ValueError("Trade request cannot be empty.")

    def validate_side(
        self,
        side: str,
    ) -> None:
        """
        Validate trade side.
        """

        if side not in self.VALID_SIDES:
            raise ValueError("Side must be buy or sell.")

    def validate_account_balance(
        self,
        account_balance: float,
    ) -> None:
        """
        Validate account balance.
        """

        if account_balance <= 0:
            raise ValueError("Account balance must be greater than zero.")

    def validate_risk_percent(
        self,
        risk_percent: float,
    ) -> None:
        """
        Validate risk percent.

        The value should be expressed as a decimal.
        Example: 0.01 means 1%.
        """

        if risk_percent <= 0 or risk_percent > 1:
            raise ValueError("Risk percent must be between 0 and 1.")

    def validate_price(
        self,
        price: float,
    ) -> None:
        """
        Validate price.
        """

        if price <= 0:
            raise ValueError("Price must be greater than zero.")

    def validate_position_size(
        self,
        position_size: float,
    ) -> None:
        """
        Validate position size.
        """

        if position_size <= 0:
            raise ValueError("Position size must be greater than zero.")

    def get_required_trade_value(
        self,
        trade_request: dict[str, Any],
        key: str,
    ) -> Any:
        """
        Get a required value from a trade request.
        """

        self.validate_trade_request(trade_request)

        if not key:
            raise ValueError("Trade request key cannot be empty.")

        if key not in trade_request:
            raise ValueError(f"Trade request is missing required key: {key}")

        return trade_request[key]


__all__ = [
    "RiskInterface",
    "RiskInterfaceDecision",
]