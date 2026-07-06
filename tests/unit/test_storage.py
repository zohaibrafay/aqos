"""
Unit tests for AQOS Data Storage.
"""

from pathlib import Path

import pandas as pd
import pytest

from aqos.data import DataStorage


def test_save_and_load_csv(tmp_path: Path):

    storage = DataStorage()

    dataframe = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-01-01 00:00:00"]
            ),
            "open": [100],
            "high": [101],
            "low": [99],
            "close": [100.5],
            "volume": [1000],
        }
    )

    file_path = tmp_path / "market.csv"

    storage.save_csv(dataframe, file_path)

    loaded = storage.load_csv(file_path)

    assert len(loaded) == 1
    assert list(loaded.columns) == list(dataframe.columns)


def test_load_missing_file():

    storage = DataStorage()

    with pytest.raises(FileNotFoundError):
        storage.load_csv("missing.csv")