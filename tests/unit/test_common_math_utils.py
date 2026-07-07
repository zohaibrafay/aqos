"""
Unit tests for common math utilities.
"""

import math

import pytest

from aqos.common import (
    clamp,
    cumulative_sum,
    max_drawdown,
    mean,
    median,
    normalize_min_max,
    percentage_change,
    percentage_return,
    profit_factor,
    rolling_mean,
    round_to_decimals,
    safe_divide,
    standard_deviation,
    validate_number,
    validate_numbers,
    variance,
    weighted_average,
    win_rate,
)


def test_validate_number():
    assert validate_number(10, "Value") == 10.0
    assert validate_number(10.5, "Value") == 10.5


def test_validate_number_rejects_bool():
    with pytest.raises(TypeError):
        validate_number(True, "Value")


def test_validate_number_rejects_invalid_type():
    with pytest.raises(TypeError):
        validate_number("10", "Value")


def test_validate_numbers():
    assert validate_numbers([1, 2, 3]) == [
        1.0,
        2.0,
        3.0,
    ]


def test_validate_numbers_rejects_string():
    with pytest.raises(TypeError):
        validate_numbers("123")


def test_validate_numbers_rejects_empty_iterable():
    with pytest.raises(ValueError):
        validate_numbers([])


def test_validate_numbers_rejects_invalid_item():
    with pytest.raises(TypeError):
        validate_numbers([1, "2"])


def test_safe_divide():
    assert safe_divide(10, 2) == 5.0


def test_safe_divide_by_zero_returns_default():
    assert safe_divide(10, 0) == 0.0
    assert safe_divide(10, 0, default=-1.0) == -1.0


def test_safe_divide_rejects_invalid_default():
    with pytest.raises(TypeError):
        safe_divide(10, 0, default="invalid")


def test_percentage_change():
    assert percentage_change(100, 110) == 0.1
    assert percentage_change(100, 90) == -0.1


def test_percentage_change_rejects_zero_old_value():
    with pytest.raises(ValueError):
        percentage_change(0, 100)


def test_percentage_return():
    assert percentage_return(100, 125) == 0.25


def test_clamp_inside_range():
    assert clamp(5, 0, 10) == 5.0


def test_clamp_below_range():
    assert clamp(-1, 0, 10) == 0.0


def test_clamp_above_range():
    assert clamp(11, 0, 10) == 10.0


def test_clamp_rejects_invalid_range():
    with pytest.raises(ValueError):
        clamp(5, 10, 0)


def test_round_to_decimals():
    assert round_to_decimals(1.2345, 2) == 1.23


def test_round_to_decimals_default():
    assert round_to_decimals(1.235) == 1.24


def test_round_to_decimals_rejects_invalid_decimals_type():
    with pytest.raises(TypeError):
        round_to_decimals(1.23, "2")


def test_round_to_decimals_rejects_negative_decimals():
    with pytest.raises(ValueError):
        round_to_decimals(1.23, -1)


def test_mean():
    assert mean([1, 2, 3]) == 2.0


def test_median_odd_values():
    assert median([1, 3, 2]) == 2.0


def test_median_even_values():
    assert median([1, 2, 3, 4]) == 2.5


def test_variance_population():
    assert variance([1, 2, 3]) == pytest.approx(0.6666666667)


def test_variance_sample():
    assert variance([1, 2, 3], sample=True) == 1.0


def test_variance_sample_requires_two_values():
    with pytest.raises(ValueError):
        variance([1], sample=True)


def test_standard_deviation_population():
    assert standard_deviation([1, 2, 3]) == pytest.approx(math.sqrt(2 / 3))


def test_standard_deviation_sample():
    assert standard_deviation([1, 2, 3], sample=True) == 1.0


def test_normalize_min_max():
    assert normalize_min_max([10, 20, 30]) == [
        0.0,
        0.5,
        1.0,
    ]


def test_normalize_min_max_same_values():
    assert normalize_min_max([10, 10, 10]) == [
        0.0,
        0.0,
        0.0,
    ]


def test_weighted_average():
    assert weighted_average(
        values=[10, 20, 30],
        weights=[1, 2, 1],
    ) == 20.0


def test_weighted_average_rejects_length_mismatch():
    with pytest.raises(ValueError):
        weighted_average(
            values=[10, 20],
            weights=[1],
        )


def test_weighted_average_rejects_zero_total_weight():
    with pytest.raises(ValueError):
        weighted_average(
            values=[10, 20],
            weights=[0, 0],
        )


def test_rolling_mean():
    assert rolling_mean(
        values=[1, 2, 3, 4],
        window=2,
    ) == [
        1.5,
        2.5,
        3.5,
    ]


def test_rolling_mean_rejects_invalid_window_type():
    with pytest.raises(TypeError):
        rolling_mean(
            values=[1, 2, 3],
            window=1.5,
        )


def test_rolling_mean_rejects_zero_window():
    with pytest.raises(ValueError):
        rolling_mean(
            values=[1, 2, 3],
            window=0,
        )


def test_rolling_mean_rejects_window_larger_than_values():
    with pytest.raises(ValueError):
        rolling_mean(
            values=[1, 2, 3],
            window=4,
        )


def test_cumulative_sum():
    assert cumulative_sum([1, -2, 3]) == [
        1.0,
        -1.0,
        2.0,
    ]


def test_max_drawdown():
    assert max_drawdown([100, 120, 90, 130]) == -0.25


def test_max_drawdown_without_drawdown():
    assert max_drawdown([100, 110, 120]) == 0.0


def test_profit_factor():
    assert profit_factor([100, -50, 25]) == 2.5


def test_profit_factor_without_loss():
    assert profit_factor([100, 25]) == float("inf")


def test_profit_factor_without_profit_or_loss():
    assert profit_factor([0, 0]) == 0.0


def test_win_rate():
    assert win_rate([100, -50, 25, 0]) == 0.5