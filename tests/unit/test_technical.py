import pandas as pd

from aqos.features import TechnicalIndicators


def test_technical_features():

    dataframe = pd.DataFrame(
        {
            "close": list(range(1, 21)),
        }
    )

    feature = TechnicalIndicators()

    result = feature.transform(dataframe)

    assert "sma_10" in result.columns
    assert "ema_10" in result.columns
    assert "returns" in result.columns
    assert "log_returns" in result.columns

    assert len(result) == 20