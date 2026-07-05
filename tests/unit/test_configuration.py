from aqos.core.configuration import ConfigurationManager


def test_configuration_loads():

    config = ConfigurationManager()

    config.load()

    assert config.validate() is True


def test_get_environment():

    config = ConfigurationManager()

    config.load()

    assert config.get("app.environment") is not None


def test_get_logging_level():

    config = ConfigurationManager()

    config.load()

    assert config.get("logging.level") is not None


def test_get_unknown_key():

    config = ConfigurationManager()

    config.load()

    assert config.get("abc.xyz") is None