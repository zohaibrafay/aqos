"""
Unit tests for AQOS Data Loader.
"""

from pathlib import Path

import pandas as pd
import pytest

from aqos.data import DataLoader


def test_load_csv(tmp_path: Path):

    csv_file = tmp_path / "data.csv"

    dataframe = pd.DataFrame(
        {
            "timestamp": ["2026-01-01 00:00:00"],
            "open": [1.0],
            "high": [2.0],
            "low": [0.5],
            "close": [1.5],
            "volume": [100],
        }
    )

    dataframe.to_csv(csv_file, index=False)

    loader = DataLoader()

    data = loader.load_csv(csv_file)

    assert len(data) == 1
    assert list(data.columns) == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]


def test_missing_file():

    loader = DataLoader()

    with pytest.raises(FileNotFoundError):
        loader.load_csv("missing.csv")


def test_missing_columns(tmp_path: Path):

    csv_file = tmp_path / "bad.csv"

    dataframe = pd.DataFrame(
        {
            "timestamp": ["2026-01-01"],
            "open": [1.0],
        }
    )

    dataframe.to_csv(csv_file, index=False)

    loader = DataLoader()

    with pytest.raises(ValueError):
        loader.load_csv(csv_file)