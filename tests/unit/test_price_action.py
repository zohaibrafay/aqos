import pandas as pd

from aqos.features import PriceActionFeatures


def test_price_action_features():

    dataframe = pd.DataFrame(
        {
            "open": [100, 102, 101],
            "high": [105, 107, 106],
            "low": [99, 101, 100],
            "close": [104, 103, 105],
        }
    )

    feature = PriceActionFeatures()

    result = feature.transform(dataframe)

    assert "higher_high" in result.columns
    assert "lower_low" in result.columns
    assert "higher_close" in result.columns
    assert "lower_close" in result.columns
    assert "price_range" in result.columns
    assert "gap" in result.columns

    assert len(result) == 3