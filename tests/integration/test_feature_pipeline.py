import pandas as pd

from aqos.features import (
    CandlestickFeatures,
    FeaturePipeline,
    PriceActionFeatures,
    StatisticalFeatures,
    TechnicalIndicators,
)


def test_feature_pipeline():

    dataframe = pd.DataFrame(
        {
            "open": list(range(100, 120)),
            "high": list(range(101, 121)),
            "low": list(range(99, 119)),
            "close": list(range(100, 120)),
            "volume": [1000] * 20,
        }
    )

    pipeline = FeaturePipeline()

    pipeline.add(TechnicalIndicators())
    pipeline.add(CandlestickFeatures())
    pipeline.add(PriceActionFeatures())
    pipeline.add(StatisticalFeatures())

    result = pipeline.run(dataframe)

    assert "sma_10" in result.columns
    assert "body" in result.columns
    assert "price_range" in result.columns
    assert "rolling_mean_10" in result.columns

    assert len(result) == 20