"""
AQOS Data Catalog.
"""

from __future__ import annotations

from pathlib import Path


class DataCatalog:
    """
    Manages dataset registration and discovery.
    """

    def __init__(self) -> None:
        self._datasets: dict[str, Path] = {}

    def register(
        self,
        name: str,
        file_path: str | Path,
    ) -> None:
        """
        Register a dataset.
        """

        self._datasets[name] = Path(file_path)

    def get(
        self,
        name: str,
    ) -> Path:
        """
        Return dataset path.
        """

        if name not in self._datasets:
            raise KeyError(f"Dataset '{name}' not found.")

        return self._datasets[name]

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a dataset exists.
        """

        return name in self._datasets

    def list(self) -> list[str]:
        """
        List registered datasets.
        """

        return sorted(self._datasets.keys())