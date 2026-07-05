"""
Unit tests for AQOS Bootstrap System.
"""

from pathlib import Path

from aqos.core import Bootstrap


def test_bootstrap_initialization():

    bootstrap = Bootstrap()

    bootstrap.initialize()

    assert bootstrap.is_initialized() is True

    bootstrap.shutdown()


def test_configuration_loaded():

    bootstrap = Bootstrap()

    bootstrap.initialize()

    config = bootstrap.get_configuration()

    assert config is not None
    assert config.get("app.environment") is not None

    bootstrap.shutdown()


def test_required_directories_exist():

    bootstrap = Bootstrap()

    bootstrap.initialize()

    directories = [
        "logs",
        "datasets",
        "experiments",
        "models",
    ]

    for directory in directories:
        assert Path(directory).exists()

    bootstrap.shutdown()


def test_shutdown():

    bootstrap = Bootstrap()

    bootstrap.initialize()

    bootstrap.shutdown()

    assert bootstrap.is_initialized() is False