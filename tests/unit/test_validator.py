"""
Unit tests for AQOS Data Validator.
"""

import pandas as pd
import pytest

from aqos.data import DataValidator


def create_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-01-01 00:00:00",
                    "2026-01-01 01:00:00",
                ]
            ),
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [1000, 1200],
        }
    )


def test_valid_dataframe():

    validator = DataValidator()

    dataframe = create_dataframe()

    validator.validate(dataframe)


def test_missing_values():

    validator = DataValidator()

    dataframe = create_dataframe()

    dataframe.loc[0, "close"] = None

    with pytest.raises(ValueError):
        validator.validate(dataframe)


def test_duplicate_timestamps():

    validator = DataValidator()

    dataframe = create_dataframe()

    dataframe.loc[1, "timestamp"] = dataframe.loc[0, "timestamp"]

    with pytest.raises(ValueError):
        validator.validate(dataframe)


def test_invalid_ohlc():

    validator = DataValidator()

    dataframe = create_dataframe()

    dataframe.loc[0, "high"] = 90.0

    with pytest.raises(ValueError):
        validator.validate(dataframe)