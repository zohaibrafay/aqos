"""
AQOS CSV Data Loader.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


class DataLoader:
    """
    Loads OHLCV market data from CSV files.
    """

    REQUIRED_COLUMNS = (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )

    def load_csv(self, file_path: str | Path) -> pd.DataFrame:
        """
        Load market data from a CSV file.
        """

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(path)

        dataframe = pd.read_csv(path)

        missing = [
            column
            for column in self.REQUIRED_COLUMNS
            if column not in dataframe.columns
        ]

        if missing:
            raise ValueError(
                f"Missing required columns: {missing}"
            )

        dataframe["timestamp"] = pd.to_datetime(
            dataframe["timestamp"]
        )

        dataframe.sort_values(
            "timestamp",
            inplace=True,
        )

        dataframe.reset_index(
            drop=True,
            inplace=True,
        )

        return dataframe