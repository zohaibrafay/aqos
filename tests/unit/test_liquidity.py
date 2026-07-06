import pandas as pd

from aqos.strategy import LiquidityDetector


def test_liquidity_detector():

    dataframe = pd.DataFrame(
        {
            "high": [101, 103, 105, 107, 109],
            "low": [99, 98, 100, 102, 103],
            "close": [100, 102, 104, 106, 108],
        }
    )

    detector = LiquidityDetector()

    result = detector.generate(dataframe)

    assert "buy_side_liquidity" in result.columns
    assert "sell_side_liquidity" in result.columns
    assert "near_buy_liquidity" in result.columns
    assert "near_sell_liquidity" in result.columns

    assert len(result) == 5