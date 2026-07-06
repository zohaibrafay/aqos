"""
Integration tests for AQOS Feature Engineering.
"""

import pandas as pd

from aqos.features import (
    CandlestickFeatures,
    FeaturePipeline,
    MarketStructureFeatures,
    PriceActionFeatures,
    StatisticalFeatures,
    TechnicalIndicators,
)


def test_complete_feature_engineering_pipeline():

    dataframe = pd.DataFrame(
        {
            "open": list(range(100, 130)),
            "high": list(range(101, 131)),
            "low": list(range(99, 129)),
            "close": list(range(100, 130)),
            "volume": [1000] * 30,
        }
    )

    pipeline = FeaturePipeline()

    pipeline.add(TechnicalIndicators())
    pipeline.add(CandlestickFeatures())
    pipeline.add(PriceActionFeatures())
    pipeline.add(StatisticalFeatures())
    pipeline.add(MarketStructureFeatures())

    result = pipeline.run(dataframe)

    expected_columns = [
        "sma_10",
        "ema_10",
        "returns",
        "body",
        "body_size",
        "upper_wick",
        "lower_wick",
        "price_range",
        "rolling_mean_10",
        "rolling_std_10",
        "rolling_min_10",
        "rolling_max_10",
        "z_score",
        "swing_high",
        "swing_low",
        "trend",
    ]

    for column in expected_columns:
        assert column in result.columns

    assert len(result) == 30