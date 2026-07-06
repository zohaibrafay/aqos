"""
Position sizing.

Calculates trade position size based on account balance, risk percent,
entry price, and stop-loss price.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PositionSizer:
    """
    Position sizing engine.
    """

    risk_percent: float = 0.01
    max_position_size: float | None = None

    def __post_init__(self) -> None:
        """
        Validate position sizing configuration.
        """

        if self.risk_percent <= 0:
            raise ValueError("Risk percent must be greater than zero.")

        if self.risk_percent > 1:
            raise ValueError("Risk percent cannot be greater than 1.")

        if (
            self.max_position_size is not None
            and self.max_position_size <= 0
        ):
            raise ValueError(
                "Max position size must be greater than zero."
            )

    def calculate(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        """
        Calculate position size.
        """

        if account_balance <= 0:
            raise ValueError("Account balance must be greater than zero.")

        if entry_price <= 0:
            raise ValueError("Entry price must be greater than zero.")

        if stop_loss_price <= 0:
            raise ValueError("Stop-loss price must be greater than zero.")

        risk_per_unit = abs(entry_price - stop_loss_price)

        if risk_per_unit == 0:
            raise ValueError(
                "Entry price and stop-loss price cannot be equal."
            )

        risk_amount = self.risk_amount(account_balance)
        position_size = risk_amount / risk_per_unit

        if self.max_position_size is not None:
            return min(position_size, self.max_position_size)

        return position_size

    def risk_amount(
        self,
        account_balance: float,
    ) -> float:
        """
        Calculate monetary risk amount.
        """

        if account_balance <= 0:
            raise ValueError("Account balance must be greater than zero.")

        return account_balance * self.risk_percent


__all__ = ["PositionSizer"]