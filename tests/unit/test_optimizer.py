"""
Unit tests for Optimizer.
"""

import pytest

from aqos.learning.optimizer import Optimizer


def test_default_optimizer():
    optimizer = Optimizer()

    config = optimizer.config()

    assert config["name"] == "adam"
    assert config["learning_rate"] == pytest.approx(0.001)


def test_custom_optimizer():
    optimizer = Optimizer(
        name="sgd",
        learning_rate=0.01,
    )

    config = optimizer.config()

    assert config["name"] == "sgd"
    assert config["learning_rate"] == pytest.approx(0.01)


def test_empty_name():
    optimizer = Optimizer(
        name="",
        learning_rate=0.001,
    )

    with pytest.raises(ValueError):
        optimizer.config()


def test_invalid_learning_rate():
    optimizer = Optimizer(
        learning_rate=0.0,
    )

    with pytest.raises(ValueError):
        optimizer.config()


def test_negative_learning_rate():
    optimizer = Optimizer(
        learning_rate=-0.01,
    )

    with pytest.raises(ValueError):
        optimizer.config()