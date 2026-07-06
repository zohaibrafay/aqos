"""
Evaluation metrics.

Provides foundational metrics for model predictions and trading results.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(slots=True)
class EvaluationMetrics:
    """
    Evaluation metrics engine.
    """

    def accuracy(
        self,
        actual: list,
        predicted: list,
    ) -> float:
        """
        Calculate classification accuracy.
        """

        self._validate_equal_length(actual, predicted)

        correct = sum(
            1
            for actual_value, predicted_value in zip(actual, predicted)
            if actual_value == predicted_value
        )

        return correct / len(actual)

    def mean_absolute_error(
        self,
        actual: list[float],
        predicted: list[float],
    ) -> float:
        """
        Calculate mean absolute error.
        """

        self._validate_equal_length(actual, predicted)

        total_error = sum(
            abs(actual_value - predicted_value)
            for actual_value, predicted_value in zip(actual, predicted)
        )

        return total_error / len(actual)

    def mean_squared_error(
        self,
        actual: list[float],
        predicted: list[float],
    ) -> float:
        """
        Calculate mean squared error.
        """

        self._validate_equal_length(actual, predicted)

        total_error = sum(
            (actual_value - predicted_value) ** 2
            for actual_value, predicted_value in zip(actual, predicted)
        )

        return total_error / len(actual)

    def root_mean_squared_error(
        self,
        actual: list[float],
        predicted: list[float],
    ) -> float:
        """
        Calculate root mean squared error.
        """

        return sqrt(
            self.mean_squared_error(
                actual=actual,
                predicted=predicted,
            )
        )

    def win_rate(
        self,
        profits: list[float],
    ) -> float:
        """
        Calculate trading win rate.

        A winning trade is any trade with profit greater than zero.
        """

        self._validate_not_empty(profits, "Profits")

        wins = sum(
            1
            for profit in profits
            if profit > 0
        )

        return wins / len(profits)

    def average_profit(
        self,
        profits: list[float],
    ) -> float:
        """
        Calculate average profit.
        """

        self._validate_not_empty(profits, "Profits")

        return sum(profits) / len(profits)

    def total_profit(
        self,
        profits: list[float],
    ) -> float:
        """
        Calculate total profit.
        """

        self._validate_not_empty(profits, "Profits")

        return sum(profits)

    def profit_factor(
        self,
        profits: list[float],
    ) -> float:
        """
        Calculate profit factor.

        Profit factor = gross profit / gross loss.
        """

        self._validate_not_empty(profits, "Profits")

        gross_profit = sum(
            profit
            for profit in profits
            if profit > 0
        )

        gross_loss = abs(
            sum(
                profit
                for profit in profits
                if profit < 0
            )
        )

        if gross_loss == 0:
            return float("inf")

        return gross_profit / gross_loss

    def _validate_equal_length(
        self,
        actual: list,
        predicted: list,
    ) -> None:
        """
        Validate metric inputs.
        """

        self._validate_not_empty(actual, "Actual values")
        self._validate_not_empty(predicted, "Predicted values")

        if len(actual) != len(predicted):
            raise ValueError(
                "Actual and predicted values must have the same length."
            )

    def _validate_not_empty(
        self,
        values: list,
        name: str,
    ) -> None:
        """
        Validate non-empty list.
        """

        if not values:
            raise ValueError(f"{name} cannot be empty.")


__all__ = ["EvaluationMetrics"]