import pandas as pd

from aqos.features import MarketStructureFeatures


def test_market_structure_features():

    dataframe = pd.DataFrame(
        {
            "high": [100, 105, 103, 108, 106],
            "low": [95, 97, 94, 99, 98],
        }
    )

    feature = MarketStructureFeatures()

    result = feature.transform(dataframe)

    assert "swing_high" in result.columns
    assert "swing_low" in result.columns
    assert "higher_high" in result.columns
    assert "lower_low" in result.columns
    assert "trend" in result.columns

    assert len(result) == 5