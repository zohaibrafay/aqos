"""
Unit tests for EvaluationMetrics.
"""

import pytest

from aqos.evaluation import EvaluationMetrics


def test_accuracy():
    metrics = EvaluationMetrics()

    result = metrics.accuracy(
        actual=["buy", "sell", "hold", "buy"],
        predicted=["buy", "sell", "buy", "buy"],
    )

    assert result == 0.75


def test_mean_absolute_error():
    metrics = EvaluationMetrics()

    result = metrics.mean_absolute_error(
        actual=[1.0, 2.0, 3.0],
        predicted=[1.0, 2.5, 2.0],
    )

    assert result == pytest.approx(0.5)


def test_mean_squared_error():
    metrics = EvaluationMetrics()

    result = metrics.mean_squared_error(
        actual=[1.0, 2.0, 3.0],
        predicted=[1.0, 2.5, 2.0],
    )

    assert result == pytest.approx(0.4166666667)


def test_root_mean_squared_error():
    metrics = EvaluationMetrics()

    result = metrics.root_mean_squared_error(
        actual=[1.0, 2.0, 3.0],
        predicted=[1.0, 2.5, 2.0],
    )

    assert result == pytest.approx(0.6454972244)


def test_win_rate():
    metrics = EvaluationMetrics()

    result = metrics.win_rate(
        profits=[100.0, -50.0, 25.0, 0.0],
    )

    assert result == 0.5


def test_average_profit():
    metrics = EvaluationMetrics()

    result = metrics.average_profit(
        profits=[100.0, -50.0, 25.0],
    )

    assert result == pytest.approx(25.0)


def test_total_profit():
    metrics = EvaluationMetrics()

    result = metrics.total_profit(
        profits=[100.0, -50.0, 25.0],
    )

    assert result == 75.0


def test_profit_factor():
    metrics = EvaluationMetrics()

    result = metrics.profit_factor(
        profits=[100.0, -50.0, 25.0],
    )

    assert result == 2.5


def test_profit_factor_without_losses():
    metrics = EvaluationMetrics()

    result = metrics.profit_factor(
        profits=[100.0, 50.0],
    )

    assert result == float("inf")


def test_empty_actual_values():
    metrics = EvaluationMetrics()

    with pytest.raises(ValueError):
        metrics.accuracy(
            actual=[],
            predicted=["buy"],
        )


def test_empty_predicted_values():
    metrics = EvaluationMetrics()

    with pytest.raises(ValueError):
        metrics.accuracy(
            actual=["buy"],
            predicted=[],
        )


def test_length_mismatch():
    metrics = EvaluationMetrics()

    with pytest.raises(ValueError):
        metrics.accuracy(
            actual=["buy", "sell"],
            predicted=["buy"],
        )


def test_empty_profits():
    metrics = EvaluationMetrics()

    with pytest.raises(ValueError):
        metrics.win_rate([])