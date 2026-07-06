"""
AQOS Feature Pipeline.
"""

from __future__ import annotations

import pandas as pd

from aqos.features.base import Feature


class FeaturePipeline:
    """
    Sequential feature engineering pipeline.
    """

    def __init__(self) -> None:
        self._features: list[Feature] = []

    def add(self, feature: Feature) -> None:
        """
        Register a feature transformer.
        """
        self._features.append(feature)

    def run(
        self,
        dataframe: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        Execute all registered feature transformers.
        """

        result = dataframe.copy()

        for feature in self._features:
            result = feature.transform(result)

        return result