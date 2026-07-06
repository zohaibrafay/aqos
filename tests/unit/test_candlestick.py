import pandas as pd

from aqos.features import CandlestickFeatures


def test_candlestick_features():

    dataframe = pd.DataFrame(
        {
            "open": [100, 101],
            "high": [105, 106],
            "low": [99, 100],
            "close": [104, 100],
        }
    )

    feature = CandlestickFeatures()

    result = feature.transform(dataframe)

    assert "body" in result.columns
    assert "body_size" in result.columns
    assert "upper_wick" in result.columns
    assert "lower_wick" in result.columns
    assert "bullish" in result.columns
    assert "bearish" in result.columns

    assert len(result) == 2