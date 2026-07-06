"""
Base model interface.

Defines the common interface for all prediction models used in AQOS.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class BaseModel(ABC):
    """
    Abstract base class for all AQOS models.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return the model name.
        """
        raise NotImplementedError

    @abstractmethod
    def fit(
        self,
        features: pd.DataFrame,
        target: pd.Series,
    ) -> None:
        """
        Train the model.
        """
        raise NotImplementedError

    @abstractmethod
    def predict(
        self,
        features: pd.DataFrame,
    ) -> pd.Series:
        """
        Generate predictions.
        """
        raise NotImplementedError

    @abstractmethod
    def save(
        self,
        path: str,
    ) -> None:
        """
        Save the model.
        """
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def load(
        cls,
        path: str,
    ) -> "BaseModel":
        """
        Load a saved model.
        """
        raise NotImplementedError


__all__ = ["BaseModel"]