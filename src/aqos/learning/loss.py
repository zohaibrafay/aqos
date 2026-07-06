"""
Loss function configuration.

Provides a lightweight loss configuration that will later support
advanced machine learning loss functions.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Loss:
    """
    Loss function configuration.
    """

    name: str = "mse"

    def validate(self) -> None:
        """
        Validate loss configuration.
        """

        if not self.name:
            raise ValueError("Loss name cannot be empty.")

    def config(self) -> dict:
        """
        Return loss configuration.

        Returns
        -------
        dict
            Loss configuration.
        """

        self.validate()

        return {
            "name": self.name,
        }


__all__ = ["Loss"]