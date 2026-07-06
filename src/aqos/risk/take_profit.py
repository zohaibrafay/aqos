"""
Risk take profit.

Provides risk-adjusted take-profit calculations and trigger checks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class TakeProfitRecord:
    """
    Represents a take-profit calculation.
    """

    side: str
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    reward_per_unit: float
    reward_risk_ratio: float


@dataclass(slots=True)
class TakeProfitManager:
    """
    Risk take-profit manager.
    """

    reward_risk_ratio: float = 2.0

    def __post_init__(self) -> None:
        """
        Validate take-profit configuration.
        """

        if self.reward_risk_ratio <= 0:
            raise ValueError(
                "Reward-risk ratio must be greater than zero."
            )

    def calculate(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str,
    ) -> float:
        """
        Calculate take-profit price from entry, stop loss, and ratio.
        """

        self._validate_price("Entry price", entry_price)
        self._validate_price("Stop-loss price", stop_loss_price)
        self._validate_side(side)

        risk_per_unit = abs(entry_price - stop_loss_price)

        if risk_per_unit == 0:
            raise ValueError(
                "Entry price and stop-loss price cannot be equal."
            )

        reward_per_unit = risk_per_unit * self.reward_risk_ratio

        if side == "buy":
            return entry_price + reward_per_unit

        take_profit_price = entry_price - reward_per_unit

        if take_profit_price <= 0:
            raise ValueError(
                "Calculated take-profit price must be greater than zero."
            )

        return take_profit_price

    def is_hit(
        self,
        current_price: float,
        take_profit_price: float,
        side: str,
    ) -> bool:
        """
        Check whether take profit has been hit.
        """

        self._validate_price("Current price", current_price)
        self._validate_price("Take-profit price", take_profit_price)
        self._validate_side(side)

        if side == "buy":
            return current_price >= take_profit_price

        return current_price <= take_profit_price

    def create_record(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str,
    ) -> TakeProfitRecord:
        """
        Create a take-profit record.
        """

        take_profit_price = self.calculate(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            side=side,
        )

        reward_per_unit = abs(take_profit_price - entry_price)

        return TakeProfitRecord(
            side=side,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            reward_per_unit=reward_per_unit,
            reward_risk_ratio=self.reward_risk_ratio,
        )

    def _validate_side(
        self,
        side: str,
    ) -> None:
        """
        Validate trade side.
        """

        if side not in {"buy", "sell"}:
            raise ValueError("Side must be either 'buy' or 'sell'.")

    def _validate_price(
        self,
        name: str,
        value: float,
    ) -> None:
        """
        Validate positive price.
        """

        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")


__all__ = [
    "TakeProfitManager",
    "TakeProfitRecord",
]