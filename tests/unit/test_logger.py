import logging

from aqos.core.logger import Logger


def test_logger_instance():

    logger = Logger.get_logger()

    assert isinstance(logger, logging.Logger)


def test_singleton_logger():

    logger1 = Logger.get_logger()
    logger2 = Logger.get_logger()

    assert logger1 is logger2


def test_logger_name():

    logger = Logger.get_logger()

    assert logger.name == "AQOS"