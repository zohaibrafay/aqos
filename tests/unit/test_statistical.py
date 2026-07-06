import pandas as pd

from aqos.features import StatisticalFeatures


def test_statistical_features():

    dataframe = pd.DataFrame(
        {
            "high": list(range(101, 121)),
            "low": list(range(99, 119)),
            "close": list(range(100, 120)),
        }
    )

    feature = StatisticalFeatures()

    result = feature.transform(dataframe)

    assert "rolling_mean_10" in result.columns
    assert "rolling_std_10" in result.columns
    assert "rolling_min_10" in result.columns
    assert "rolling_max_10" in result.columns
    assert "z_score" in result.columns

    assert len(result) == 20