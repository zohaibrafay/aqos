"""
AQOS Logging System

Centralized logging for the entire application.
"""

from __future__ import annotations

import logging
from pathlib import Path


class Logger:
    """
    Singleton logger factory for AQOS.
    """

    _logger: logging.Logger | None = None

    @classmethod
    def get_logger(cls) -> logging.Logger:

        if cls._logger is not None:
            return cls._logger

        log_directory = Path("logs")
        log_directory.mkdir(exist_ok=True)

        logger = logging.getLogger("AQOS")
        logger.setLevel(logging.INFO)

        if logger.handlers:
            return logger

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)

        file_handler = logging.FileHandler(
            log_directory / "aqos.log",
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        logger.propagate = False

        cls._logger = logger

        return logger