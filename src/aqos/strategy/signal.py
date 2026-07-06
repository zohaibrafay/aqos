"""
Signal engine.

Combines strategy components into a final trading signal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class SignalEngine:
    """
    Generate final trading signals.
    """

    def generate(
        self,
        regime: str,
        trend: str,
    ) -> str:
        """
        Generate a trading signal.

        Parameters
        ----------
        regime : str
            Current market regime.
        trend : str
            Current market trend.

        Returns
        -------
        str
            One of:
            - "buy"
            - "sell"
            - "hold"
        """

        regime = regime.lower()
        trend = trend.lower()

        if regime == "bull" and trend == "uptrend":
            return "buy"

        if regime == "bear" and trend == "downtrend":
            return "sell"

        return "hold"


__all__ = ["SignalEngine"]