import pandas as pd

from aqos.features import Feature


class MockFeature(Feature):

    @property
    def name(self) -> str:
        return "MockFeature"

    def transform(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:

        dataframe = dataframe.copy()
        dataframe["mock_feature"] = 1

        return dataframe


def test_feature_name():

    feature = MockFeature()

    assert feature.name == "MockFeature"


def test_feature_transform():

    dataframe = pd.DataFrame(
        {
            "close": [1, 2, 3],
        }
    )

    feature = MockFeature()

    result = feature.transform(dataframe)

    assert "mock_feature" in result.columns
    assert len(result) == 3