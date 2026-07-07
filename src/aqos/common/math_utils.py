"""
Common math utilities.

Defines reusable numeric helpers for AQOS modules.
"""

from __future__ import annotations

from math import sqrt
from statistics import median as statistics_median
from typing import Iterable


def validate_number(
    value: int | float,
    name: str = "Value",
) -> float:
    """
    Validate numeric value and return it as float.
    """

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric.")

    return float(value)


def validate_numbers(
    values: Iterable[int | float],
    name: str = "Values",
) -> list[float]:
    """
    Validate an iterable of numeric values.
    """

    if isinstance(values, str) or not isinstance(values, Iterable):
        raise TypeError(f"{name} must be an iterable of numeric values.")

    numbers = [
        validate_number(value, name)
        for value in values
    ]

    if not numbers:
        raise ValueError(f"{name} cannot be empty.")

    return numbers


def safe_divide(
    numerator: int | float,
    denominator: int | float,
    default: float = 0.0,
) -> float:
    """
    Divide safely.

    Returns default when denominator is zero.
    """

    numerator_value = validate_number(numerator, "Numerator")
    denominator_value = validate_number(denominator, "Denominator")
    default_value = validate_number(default, "Default")

    if denominator_value == 0:
        return default_value

    return numerator_value / denominator_value


def percentage_change(
    old_value: int | float,
    new_value: int | float,
) -> float:
    """
    Calculate percentage change from old value to new value.
    """

    old = validate_number(old_value, "Old value")
    new = validate_number(new_value, "New value")

    if old == 0:
        raise ValueError("Old value cannot be zero.")

    return (new - old) / old


def percentage_return(
    entry_price: int | float,
    exit_price: int | float,
) -> float:
    """
    Calculate return percentage between entry and exit price.
    """

    return percentage_change(
        old_value=entry_price,
        new_value=exit_price,
    )


def clamp(
    value: int | float,
    minimum: int | float,
    maximum: int | float,
) -> float:
    """
    Clamp value between minimum and maximum.
    """

    number = validate_number(value, "Value")
    min_value = validate_number(minimum, "Minimum")
    max_value = validate_number(maximum, "Maximum")

    if min_value > max_value:
        raise ValueError("Minimum cannot be greater than maximum.")

    return max(
        min_value,
        min(number, max_value),
    )


def round_to_decimals(
    value: int | float,
    decimals: int = 2,
) -> float:
    """
    Round value to decimal places.
    """

    number = validate_number(value, "Value")

    if not isinstance(decimals, int):
        raise TypeError("Decimals must be an integer.")

    if decimals < 0:
        raise ValueError("Decimals cannot be negative.")

    return round(number, decimals)


def mean(
    values: Iterable[int | float],
) -> float:
    """
    Calculate arithmetic mean.
    """

    numbers = validate_numbers(values)

    return sum(numbers) / len(numbers)


def median(
    values: Iterable[int | float],
) -> float:
    """
    Calculate median.
    """

    numbers = validate_numbers(values)

    return float(statistics_median(numbers))


def variance(
    values: Iterable[int | float],
    sample: bool = False,
) -> float:
    """
    Calculate variance.

    Uses population variance by default.
    Uses sample variance when sample=True.
    """

    numbers = validate_numbers(values)

    if sample and len(numbers) < 2:
        raise ValueError("Sample variance requires at least two values.")

    average = mean(numbers)
    denominator = len(numbers) - 1 if sample else len(numbers)

    return sum(
        (number - average) ** 2
        for number in numbers
    ) / denominator


def standard_deviation(
    values: Iterable[int | float],
    sample: bool = False,
) -> float:
    """
    Calculate standard deviation.
    """

    return sqrt(
        variance(
            values=values,
            sample=sample,
        )
    )


def normalize_min_max(
    values: Iterable[int | float],
) -> list[float]:
    """
    Normalize values using min-max normalization.
    """

    numbers = validate_numbers(values)

    minimum = min(numbers)
    maximum = max(numbers)

    if minimum == maximum:
        return [
            0.0
            for _ in numbers
        ]

    return [
        (number - minimum) / (maximum - minimum)
        for number in numbers
    ]


def weighted_average(
    values: Iterable[int | float],
    weights: Iterable[int | float],
) -> float:
    """
    Calculate weighted average.
    """

    numbers = validate_numbers(values, "Values")
    weight_values = validate_numbers(weights, "Weights")

    if len(numbers) != len(weight_values):
        raise ValueError("Values and weights must have the same length.")

    total_weight = sum(weight_values)

    if total_weight == 0:
        raise ValueError("Total weight cannot be zero.")

    return sum(
        number * weight
        for number, weight in zip(numbers, weight_values, strict=True)
    ) / total_weight


def rolling_mean(
    values: Iterable[int | float],
    window: int,
) -> list[float]:
    """
    Calculate rolling mean.
    """

    numbers = validate_numbers(values)

    if not isinstance(window, int):
        raise TypeError("Window must be an integer.")

    if window <= 0:
        raise ValueError("Window must be greater than zero.")

    if window > len(numbers):
        raise ValueError("Window cannot be greater than number of values.")

    results = []

    for index in range(window - 1, len(numbers)):
        window_values = numbers[index - window + 1 : index + 1]
        results.append(mean(window_values))

    return results


def cumulative_sum(
    values: Iterable[int | float],
) -> list[float]:
    """
    Calculate cumulative sum.
    """

    numbers = validate_numbers(values)

    total = 0.0
    results = []

    for number in numbers:
        total += number
        results.append(total)

    return results


def max_drawdown(
    equity_curve: Iterable[int | float],
) -> float:
    """
    Calculate maximum drawdown as a negative percentage.

    Example:
        [100, 120, 90] -> -0.25
    """

    values = validate_numbers(equity_curve, "Equity curve")

    peak = values[0]
    worst_drawdown = 0.0

    for value in values:
        peak = max(peak, value)

        if peak == 0:
            continue

        drawdown = (value - peak) / peak
        worst_drawdown = min(worst_drawdown, drawdown)

    return worst_drawdown


def profit_factor(
    profits: Iterable[int | float],
) -> float:
    """
    Calculate profit factor.

    Profit factor = gross profit / absolute gross loss.
    """

    values = validate_numbers(profits, "Profits")

    gross_profit = sum(
        value
        for value in values
        if value > 0
    )
    gross_loss = abs(
        sum(
            value
            for value in values
            if value < 0
        )
    )

    if gross_loss == 0:
        return float("inf") if gross_profit > 0 else 0.0

    return gross_profit / gross_loss


def win_rate(
    profits: Iterable[int | float],
) -> float:
    """
    Calculate win rate from profit values.
    """

    values = validate_numbers(profits, "Profits")

    wins = len(
        [
            value
            for value in values
            if value > 0
        ]
    )

    return wins / len(values)


__all__ = [
    "clamp",
    "cumulative_sum",
    "max_drawdown",
    "mean",
    "median",
    "normalize_min_max",
    "percentage_change",
    "percentage_return",
    "profit_factor",
    "rolling_mean",
    "round_to_decimals",
    "safe_divide",
    "standard_deviation",
    "validate_number",
    "validate_numbers",
    "variance",
    "weighted_average",
    "win_rate",
]