"""
AQOS Health Check System.
"""

from __future__ import annotations

from pathlib import Path

from aqos.core.bootstrap import Bootstrap


class HealthCheck:
    """
    Performs health checks for the AQOS application.
    """

    REQUIRED_DIRECTORIES = (
        "logs",
        "datasets",
        "experiments",
        "models",
    )

    def __init__(self, bootstrap: Bootstrap) -> None:
        self.bootstrap = bootstrap

    def status(self) -> dict[str, bool]:
        """
        Return the health status of AQOS.
        """

        return {
            "bootstrap": self.bootstrap.is_initialized(),
            "configuration": self.bootstrap.get_configuration() is not None,
            "directories": self._directories_exist(),
            "healthy": self.is_healthy(),
        }

    def is_healthy(self) -> bool:
        """
        Return True if AQOS is healthy.
        """

        return (
            self.bootstrap.is_initialized()
            and self.bootstrap.get_configuration() is not None
            and self._directories_exist()
        )

    def _directories_exist(self) -> bool:
        """
        Verify that all required directories exist.
        """

        return all(
            Path(directory).exists()
            for directory in self.REQUIRED_DIRECTORIES
        )