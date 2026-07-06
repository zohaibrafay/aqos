"""
Unit tests for CrossValidation.
"""

import pytest

from aqos.learning.cross_validation import CrossValidation


def test_default_configuration():
    validation = CrossValidation()

    config = validation.config()

    assert config["folds"] == 5
    assert config["shuffle"] is False


def test_custom_configuration():
    validation = CrossValidation(
        folds=10,
        shuffle=True,
    )

    config = validation.config()

    assert config["folds"] == 10
    assert config["shuffle"] is True


def test_invalid_folds():
    validation = CrossValidation(folds=1)

    with pytest.raises(ValueError):
        validation.config()


def test_validate():
    validation = CrossValidation(folds=3)

    # Should not raise
    validation.validate()


def test_config_returns_dict():
    validation = CrossValidation()

    config = validation.config()

    assert isinstance(config, dict)