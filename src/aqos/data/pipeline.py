"""
AQOS Data Pipeline.
"""

from __future__ import annotations

import pandas as pd

from aqos.data.cleaner import DataCleaner
from aqos.data.loader import DataLoader
from aqos.data.validator import DataValidator


class DataPipeline:
    """
    End-to-end market data pipeline.
    """

    def __init__(self) -> None:
        self.loader = DataLoader()
        self.cleaner = DataCleaner()
        self.validator = DataValidator()

    def run(self, file_path: str) -> pd.DataFrame:
        """
        Execute the complete data pipeline.
        """

        dataframe = self.loader.load_csv(file_path)
        dataframe = self.cleaner.clean(dataframe)
        self.validator.validate(dataframe)

        return dataframe