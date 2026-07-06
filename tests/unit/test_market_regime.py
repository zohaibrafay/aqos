import pandas as pd

from aqos.strategy import MarketRegime


def test_market_regime():

    dataframe = pd.DataFrame(
        {
            "close": list(range(1, 101)),
        }
    )

    detector = MarketRegime()

    result = detector.generate(dataframe)

    assert "market_regime" in result.columns
    assert "trend_strength" in result.columns

    assert len(result) == 100