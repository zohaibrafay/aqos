"""
Integration tests for AQOS Core.
"""

from aqos.core import Bootstrap, HealthCheck


def test_core_integration():

    bootstrap = Bootstrap()
    bootstrap.initialize()

    assert bootstrap.is_initialized()

    config = bootstrap.get_configuration()

    assert config.get("app.environment") is not None

    health = HealthCheck(bootstrap)

    assert health.is_healthy()

    bootstrap.shutdown()

    assert bootstrap.is_initialized() is False