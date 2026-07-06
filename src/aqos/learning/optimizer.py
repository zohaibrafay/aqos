"""
Optimizer configuration.

Provides a lightweight optimizer configuration that will later be
extended with concrete implementations (e.g. Adam, SGD, RMSProp).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Optimizer:
    """
    Optimizer configuration.
    """

    name: str = "adam"
    learning_rate: float = 0.001

    def validate(self) -> None:
        """
        Validate optimizer configuration.
        """

        if not self.name:
            raise ValueError("Optimizer name cannot be empty.")

        if self.learning_rate <= 0:
            raise ValueError(
                "Learning rate must be greater than zero."
            )

    def config(self) -> dict:
        """
        Return optimizer configuration.

        Returns
        -------
        dict
            Optimizer configuration.
        """

        self.validate()

        return {
            "name": self.name,
            "learning_rate": self.learning_rate,
        }


__all__ = ["Optimizer"]