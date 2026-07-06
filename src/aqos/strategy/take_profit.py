"""
Take-profit engine.

Provides basic take-profit calculation based on entry price
and a configurable percentage.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TakeProfitEngine:
    """
    Calculate take-profit prices.
    """

    percentage: float = 0.04

    def calculate(
        self,
        entry_price: float,
        side: str,
    ) -> float:
        """
        Calculate take-profit price.

        Parameters
        ----------
        entry_price : float
            Trade entry price.
        side : str
            Trade direction ("buy" or "sell").

        Returns
        -------
        float
            Take-profit price.
        """

        if entry_price <= 0:
            raise ValueError("Entry price must be greater than zero.")

        side = side.lower()

        if side == "buy":
            return entry_price * (1 + self.percentage)

        if side == "sell":
            return entry_price * (1 - self.percentage)

        raise ValueError("Side must be either 'buy' or 'sell'.")


__all__ = ["TakeProfitEngine"]