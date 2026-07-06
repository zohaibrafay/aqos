"""
Exit engine.

Determines whether an open position should be closed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ExitEngine:
    """
    Exit decision engine.
    """

    def should_exit(self, signal: str) -> bool:
        """
        Determine whether to exit an existing position.

        Parameters
        ----------
        signal : str
            Trading signal.

        Returns
        -------
        bool
            True if exit is recommended.
        """

        signal = signal.lower()

        return signal == "hold"


__all__ = ["ExitEngine"]