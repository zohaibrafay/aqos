import pandas as pd

from aqos.strategy import Strategy


class MockStrategy(Strategy):

    @property
    def name(self) -> str:
        return "MockStrategy"

    def generate(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()
        dataframe["signal"] = "HOLD"

        return dataframe


def test_strategy_name():

    strategy = MockStrategy()

    assert strategy.name == "MockStrategy"


def test_strategy_generate():

    dataframe = pd.DataFrame(
        {
            "close": [100, 101, 102],
        }
    )

    strategy = MockStrategy()

    result = strategy.generate(dataframe)

    assert "signal" in result.columns
    assert len(result) == 3