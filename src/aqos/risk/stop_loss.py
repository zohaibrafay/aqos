"""
Risk stop loss.

Provides account-level stop-loss calculations and trigger checks.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class StopLossRecord:
    """
    Represents a stop-loss calculation.
    """

    side: str
    entry_price: float
    stop_loss_price: float
    risk_per_unit: float


@dataclass(slots=True)
class StopLossManager:
    """
    Risk stop-loss manager.
    """

    max_loss_percent: float = 0.02

    def __post_init__(self) -> None:
        """
        Validate stop-loss configuration.
        """

        if self.max_loss_percent <= 0:
            raise ValueError(
                "Max loss percent must be greater than zero."
            )

        if self.max_loss_percent > 1:
            raise ValueError(
                "Max loss percent cannot be greater than 1."
            )

    def calculate(
        self,
        entry_price: float,
        side: str,
    ) -> float:
        """
        Calculate stop-loss price from max loss percent.
        """

        self._validate_price("Entry price", entry_price)
        self._validate_side(side)

        if side == "buy":
            return entry_price * (1 - self.max_loss_percent)

        return entry_price * (1 + self.max_loss_percent)

    def calculate_from_amount(
        self,
        entry_price: float,
        risk_per_unit: float,
        side: str,
    ) -> float:
        """
        Calculate stop-loss price from monetary risk per unit.
        """

        self._validate_price("Entry price", entry_price)
        self._validate_price("Risk per unit", risk_per_unit)
        self._validate_side(side)

        if side == "buy":
            stop_loss_price = entry_price - risk_per_unit
        else:
            stop_loss_price = entry_price + risk_per_unit

        if stop_loss_price <= 0:
            raise ValueError(
                "Calculated stop-loss price must be greater than zero."
            )

        return stop_loss_price

    def is_triggered(
        self,
        current_price: float,
        stop_loss_price: float,
        side: str,
    ) -> bool:
        """
        Check whether stop loss has been triggered.
        """

        self._validate_price("Current price", current_price)
        self._validate_price("Stop-loss price", stop_loss_price)
        self._validate_side(side)

        if side == "buy":
            return current_price <= stop_loss_price

        return current_price >= stop_loss_price

    def create_record(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str,
    ) -> StopLossRecord:
        """
        Create a stop-loss record.
        """

        self._validate_price("Entry price", entry_price)
        self._validate_price("Stop-loss price", stop_loss_price)
        self._validate_side(side)

        risk_per_unit = abs(entry_price - stop_loss_price)

        if risk_per_unit == 0:
            raise ValueError(
                "Entry price and stop-loss price cannot be equal."
            )

        return StopLossRecord(
            side=side,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            risk_per_unit=risk_per_unit,
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
    "StopLossManager",
    "StopLossRecord",
]