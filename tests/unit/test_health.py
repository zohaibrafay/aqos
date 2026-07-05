"""
Unit tests for AQOS Health Check.
"""

from aqos.core import Bootstrap, HealthCheck


def test_health_check_is_created():

    bootstrap = Bootstrap()
    bootstrap.initialize()

    health = HealthCheck(bootstrap)

    assert health is not None

    bootstrap.shutdown()


def test_application_is_healthy():

    bootstrap = Bootstrap()
    bootstrap.initialize()

    health = HealthCheck(bootstrap)

    assert health.is_healthy() is True

    bootstrap.shutdown()


def test_health_status():

    bootstrap = Bootstrap()
    bootstrap.initialize()

    health = HealthCheck(bootstrap)

    status = health.status()

    assert isinstance(status, dict)
    assert status["bootstrap"] is True
    assert status["configuration"] is True
    assert status["directories"] is True
    assert status["healthy"] is True

    bootstrap.shutdown()


def test_application_shutdown():

    bootstrap = Bootstrap()
    bootstrap.initialize()

    health = HealthCheck(bootstrap)

    bootstrap.shutdown()

    assert health.is_healthy() is False