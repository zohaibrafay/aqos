"""
Unit tests for Loss.
"""

import pytest

from aqos.learning.loss import Loss


def test_default_loss():
    loss = Loss()

    config = loss.config()

    assert config["name"] == "mse"


def test_custom_loss():
    loss = Loss(name="cross_entropy")

    config = loss.config()

    assert config["name"] == "cross_entropy"


def test_empty_name():
    loss = Loss(name="")

    with pytest.raises(ValueError):
        loss.config()


def test_validate():
    loss = Loss(name="mae")

    # Should not raise
    loss.validate()


def test_config_returns_dict():
    loss = Loss()

    config = loss.config()

    assert isinstance(config, dict)