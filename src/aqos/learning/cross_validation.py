"""
Cross validation.

Provides a lightweight cross-validation configuration that will later
support K-Fold, Time Series Split, Walk-Forward Validation,
and other validation strategies.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class CrossValidation:
    """
    Cross-validation configuration.
    """

    folds: int = 5
    shuffle: bool = False

    def validate(self) -> None:
        """
        Validate cross-validation configuration.
        """

        if self.folds < 2:
            raise ValueError(
                "Number of folds must be at least 2."
            )

    def config(self) -> dict:
        """
        Return cross-validation configuration.

        Returns
        -------
        dict
            Cross-validation configuration.
        """

        self.validate()

        return {
            "folds": self.folds,
            "shuffle": self.shuffle,
        }


__all__ = ["CrossValidation"]