"""
AQOS Data Storage.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class DataStorage:
    """
    Handles reading and writing market datasets.
    """

    def save_csv(
        self,
        dataframe: pd.DataFrame,
        file_path: str | Path,
    ) -> None:
        """
        Save a DataFrame to CSV.
        """

        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        dataframe.to_csv(path, index=False)

    def load_csv(
        self,
        file_path: str | Path,
    ) -> pd.DataFrame:
        """
        Load a DataFrame from CSV.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)

        dataframe = pd.read_csv(path)

        if "timestamp" in dataframe.columns:
            dataframe["timestamp"] = pd.to_datetime(
                dataframe["timestamp"]
            )

        return dataframe