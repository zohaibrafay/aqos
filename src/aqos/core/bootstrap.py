"""
AQOS Bootstrap System

Responsible for initializing the AQOS application and preparing the
runtime environment.
"""

from __future__ import annotations

from pathlib import Path

from aqos.core.configuration import ConfigurationManager
from aqos.core.logger import Logger


class Bootstrap:
    """
    Bootstrap manager responsible for preparing AQOS before execution.
    """

    REQUIRED_DIRECTORIES = (
        "logs",
        "datasets",
        "experiments",
        "models",
    )

    def __init__(self) -> None:
        self.logger = None
        self.configuration = None
        self.initialized = False

    def initialize(self) -> None:
        """
        Initialize the AQOS application.
        """

        # Initialize logger
        self.logger = Logger.get_logger()
        self.logger.info("Initializing AQOS...")

        # Load configuration
        self.configuration = ConfigurationManager()
        self.configuration.load()
        self.configuration.validate()

        self.logger.info("Configuration loaded successfully.")

        # Create required directories
        self._create_directories()

        self.initialized = True

        self.logger.info("Bootstrap completed successfully.")

    def shutdown(self) -> None:
        """
        Shutdown AQOS gracefully.
        """

        if self.logger:
            self.logger.info("Shutting down AQOS...")

        self.initialized = False

    def is_initialized(self) -> bool:
        """
        Return bootstrap status.
        """

        return self.initialized

    def get_configuration(self) -> ConfigurationManager:
        """
        Return the loaded configuration manager.
        """

        if self.configuration is None:
            raise RuntimeError(
                "Bootstrap has not been initialized."
            )

        return self.configuration

    def _create_directories(self) -> None:
        """
        Create application directories if they do not exist.
        """

        for directory in self.REQUIRED_DIRECTORIES:
            path = Path(directory)
            path.mkdir(parents=True, exist_ok=True)

            if self.logger:
                self.logger.info(
                    "Verified directory: %s",
                    path.resolve(),
                )