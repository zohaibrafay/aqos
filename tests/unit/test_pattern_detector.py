import pandas as pd

from aqos.strategy import PatternDetector


def test_pattern_detector():

    dataframe = pd.DataFrame(
        {
            "open": [100, 99, 105],
            "high": [105, 106, 108],
            "low": [98, 97, 100],
            "close": [99, 105, 101],
        }
    )

    detector = PatternDetector()

    result = detector.generate(dataframe)

    expected = [
        "doji",
        "hammer",
        "shooting_star",
        "bullish_engulfing",
        "bearish_engulfing",
    ]

    for column in expected:
        assert column in result.columns

    assert len(result) == 3