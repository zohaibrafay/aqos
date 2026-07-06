"""
Learning rate scheduler.

Provides a lightweight scheduler configuration that will later
support advanced learning-rate scheduling strategies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Scheduler:
    """
    Learning rate scheduler configuration.
    """

    name: str = "constant"
    step_size: int = 1
    gamma: float = 1.0

    def validate(self) -> None:
        """
        Validate scheduler configuration.
        """

        if not self.name:
            raise ValueError("Scheduler name cannot be empty.")

        if self.step_size <= 0:
            raise ValueError(
                "Step size must be greater than zero."
            )

        if self.gamma <= 0:
            raise ValueError(
                "Gamma must be greater than zero."
            )

    def config(self) -> dict:
        """
        Return scheduler configuration.

        Returns
        -------
        dict
            Scheduler configuration.
        """

        self.validate()

        return {
            "name": self.name,
            "step_size": self.step_size,
            "gamma": self.gamma,
        }


__all__ = ["Scheduler"]