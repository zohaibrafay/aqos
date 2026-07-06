import pandas as pd

from aqos.strategy import SupportResistance


def test_support_resistance():

    dataframe = pd.DataFrame(
        {
            "high": [101, 103, 105, 107, 106],
            "low": [99, 100, 101, 102, 101],
            "close": [100, 102, 104, 106, 105],
        }
    )

    strategy = SupportResistance()

    result = strategy.generate(dataframe)

    assert "support" in result.columns
    assert "resistance" in result.columns
    assert "distance_to_support" in result.columns
    assert "distance_to_resistance" in result.columns

    assert len(result) == 5