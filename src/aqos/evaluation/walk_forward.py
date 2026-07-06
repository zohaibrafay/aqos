"""
Walk-forward validation.

Provides a lightweight walk-forward splitter for time-series
evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class WalkForwardSplit:
    """
    Represents one walk-forward validation split.
    """

    train_start: int
    train_end: int
    test_start: int
    test_end: int
    train_data: list[Any]
    test_data: list[Any]


@dataclass(slots=True)
class WalkForwardValidator:
    """
    Walk-forward validation splitter.
    """

    train_size: int
    test_size: int
    step_size: int | None = None

    def __post_init__(self) -> None:
        """
        Validate walk-forward configuration.
        """

        if self.train_size <= 0:
            raise ValueError("Train size must be greater than zero.")

        if self.test_size <= 0:
            raise ValueError("Test size must be greater than zero.")

        if self.step_size is not None and self.step_size <= 0:
            raise ValueError("Step size must be greater than zero.")

    def split(
        self,
        data: list[Any],
    ) -> list[WalkForwardSplit]:
        """
        Create walk-forward validation splits.
        """

        if not data:
            raise ValueError("Data cannot be empty.")

        minimum_required = self.train_size + self.test_size

        if len(data) < minimum_required:
            raise ValueError(
                "Data length must be at least train_size + test_size."
            )

        step = self.step_size or self.test_size
        splits: list[WalkForwardSplit] = []

        start = 0

        while start + minimum_required <= len(data):
            train_start = start
            train_end = train_start + self.train_size
            test_start = train_end
            test_end = test_start + self.test_size

            splits.append(
                WalkForwardSplit(
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    train_data=list(data[train_start:train_end]),
                    test_data=list(data[test_start:test_end]),
                )
            )

            start += step

        return splits


__all__ = [
    "WalkForwardSplit",
    "WalkForwardValidator",
]