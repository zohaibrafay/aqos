"""
Unit tests for TrendStructure.
"""

import pandas as pd
import pytest

from aqos.strategy.trend_structure import TrendStructure


def test_detect_uptrend():
    detector = TrendStructure()

    df = pd.DataFrame(
        {
            "high": [10, 11, 12, 13, 14],
            "low": [5, 6, 7, 8, 9],
        }
    )

    assert detector.detect(df) == "uptrend"


def test_detect_downtrend():
    detector = TrendStructure()

    df = pd.DataFrame(
        {
            "high": [14, 13, 12, 11, 10],
            "low": [9, 8, 7, 6, 5],
        }
    )

    assert detector.detect(df) == "downtrend"


def test_detect_sideways():
    detector = TrendStructure()

    df = pd.DataFrame(
        {
            "high": [10, 11, 10, 11, 10],
            "low": [5, 5, 6, 5, 6],
        }
    )

    assert detector.detect(df) == "sideways"


def test_empty_dataframe():
    detector = TrendStructure()

    with pytest.raises(ValueError):
        detector.detect(pd.DataFrame())


def test_missing_high_column():
    detector = TrendStructure()

    df = pd.DataFrame({"low": [1, 2, 3]})

    with pytest.raises(ValueError):
        detector.detect(df)


def test_missing_low_column():
    detector = TrendStructure()

    df = pd.DataFrame({"high": [1, 2, 3]})

    with pytest.raises(ValueError):
        detector.detect(df)


def test_missing_both_columns():
    detector = TrendStructure()

    df = pd.DataFrame({"close": [1, 2, 3]})

    with pytest.raises(ValueError):
        detector.detect(df)