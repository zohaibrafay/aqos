"""
Unit tests for Scheduler.
"""

import pytest

from aqos.learning.scheduler import Scheduler


def test_default_scheduler():
    scheduler = Scheduler()

    config = scheduler.config()

    assert config["name"] == "constant"
    assert config["step_size"] == 1
    assert config["gamma"] == pytest.approx(1.0)


def test_custom_scheduler():
    scheduler = Scheduler(
        name="step",
        step_size=10,
        gamma=0.5,
    )

    config = scheduler.config()

    assert config["name"] == "step"
    assert config["step_size"] == 10
    assert config["gamma"] == pytest.approx(0.5)


def test_empty_name():
    scheduler = Scheduler(name="")

    with pytest.raises(ValueError):
        scheduler.config()


def test_invalid_step_size():
    scheduler = Scheduler(step_size=0)

    with pytest.raises(ValueError):
        scheduler.config()


def test_invalid_gamma():
    scheduler = Scheduler(gamma=0.0)

    with pytest.raises(ValueError):
        scheduler.config()


def test_negative_gamma():
    scheduler = Scheduler(gamma=-0.1)

    with pytest.raises(ValueError):
        scheduler.config()