"""
Entry engine.

Determines whether market conditions satisfy entry requirements.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EntryEngine:
    """
    Entry decision engine.
    """

    def should_enter(self, signal: str) -> bool:
        """
        Determine whether to enter a trade.

        Parameters
        ----------
        signal : str
            Trading signal.

        Returns
        -------
        bool
            True if entry is allowed.
        """

        signal = signal.lower()

        return signal in {"buy", "sell"}


__all__ = ["EntryEngine"]