"""
Data service.

Provides a service-level interface for registering, retrieving,
validating, and managing AQOS market datasets.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True, frozen=True)
class DatasetSnapshot:
    """
    Represents a registered dataset.
    """

    name: str
    symbol: str
    timeframe: str
    data: pd.DataFrame


class DataService:
    """
    Service layer for market datasets.
    """

    REQUIRED_COLUMNS = {
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    }

    def __init__(self) -> None:
        self._datasets: dict[str, DatasetSnapshot] = {}

    def register(
        self,
        name: str,
        symbol: str,
        timeframe: str,
        data: pd.DataFrame,
    ) -> DatasetSnapshot:
        """
        Register a market dataset.
        """

        self._validate_name(name)
        self._validate_symbol(symbol)
        self._validate_timeframe(timeframe)
        self._validate_data(data)

        cleaned_data = data.copy()
        cleaned_data = cleaned_data.sort_values("timestamp")
        cleaned_data = cleaned_data.reset_index(drop=True)

        snapshot = DatasetSnapshot(
            name=name,
            symbol=symbol,
            timeframe=timeframe,
            data=cleaned_data,
        )

        self._datasets[name] = snapshot

        return snapshot

    def get(
        self,
        name: str,
    ) -> DatasetSnapshot | None:
        """
        Get a dataset by name.
        """

        self._validate_name(name)

        return self._datasets.get(name)

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a dataset exists.
        """

        self._validate_name(name)

        return name in self._datasets

    def list(self) -> list[DatasetSnapshot]:
        """
        Return all registered datasets.
        """

        return list(self._datasets.values())

    def list_names(self) -> list[str]:
        """
        Return registered dataset names.
        """

        return sorted(self._datasets.keys())

    def list_symbols(self) -> list[str]:
        """
        Return registered symbols.
        """

        symbols = {
            snapshot.symbol
            for snapshot in self._datasets.values()
        }

        return sorted(symbols)

    def list_timeframes(
        self,
        symbol: str | None = None,
    ) -> list[str]:
        """
        Return registered timeframes.
        """

        if symbol is not None:
            self._validate_symbol(symbol)

        timeframes = {
            snapshot.timeframe
            for snapshot in self._datasets.values()
            if symbol is None or snapshot.symbol == symbol
        }

        return sorted(timeframes)

    def count(self) -> int:
        """
        Return the number of registered datasets.
        """

        return len(self._datasets)

    def remove(
        self,
        name: str,
    ) -> None:
        """
        Remove a registered dataset.
        """

        self._validate_name(name)

        self._datasets.pop(name, None)

    def clear(self) -> None:
        """
        Clear all registered datasets.
        """

        self._datasets.clear()

    def latest_row(
        self,
        name: str,
    ) -> pd.Series:
        """
        Return the latest row from a dataset.
        """

        snapshot = self.get(name)

        if snapshot is None:
            raise ValueError("Dataset does not exist.")

        return snapshot.data.iloc[-1]

    def close_prices(
        self,
        name: str,
    ) -> list[float]:
        """
        Return close prices from a dataset.
        """

        snapshot = self.get(name)

        if snapshot is None:
            raise ValueError("Dataset does not exist.")

        return [
            float(value)
            for value in snapshot.data["close"].tolist()
        ]

    def _validate_name(
        self,
        name: str,
    ) -> None:
        """
        Validate dataset name.
        """

        if not name:
            raise ValueError("Dataset name cannot be empty.")

    def _validate_symbol(
        self,
        symbol: str,
    ) -> None:
        """
        Validate symbol.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

    def _validate_timeframe(
        self,
        timeframe: str,
    ) -> None:
        """
        Validate timeframe.
        """

        if not timeframe:
            raise ValueError("Timeframe cannot be empty.")

    def _validate_data(
        self,
        data: pd.DataFrame,
    ) -> None:
        """
        Validate market data.
        """

        if data.empty:
            raise ValueError("Dataset cannot be empty.")

        missing_columns = self.REQUIRED_COLUMNS.difference(data.columns)

        if missing_columns:
            raise ValueError(
                "Dataset is missing required columns: "
                f"{sorted(missing_columns)}"
            )


__all__ = [
    "DataService",
    "DatasetSnapshot",
]