"""
Unit tests for AQOS Data Cleaner.
"""

import pandas as pd

from aqos.data import DataCleaner


def test_clean_dataframe():

    dataframe = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 01:00:00",
                    "2026-01-01 00:00:00",
                    "2026-01-01 00:00:00",
                ]
            ),
            "open": [101, 100, 100],
            "high": [103, 102, 102],
            "low": [100, 99, 99],
            "close": [102, 101, 101],
            "volume": [1200, 1000, 1000],
        }
    )

    cleaner = DataCleaner()

    cleaned = cleaner.clean(dataframe)

    assert len(cleaned) == 2
    assert cleaned["timestamp"].is_monotonic_increasing