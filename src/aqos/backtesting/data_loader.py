from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.backtesting.contracts import BacktestBar


@dataclass(frozen=True)
class BacktestDataLoadConfig:
    csv_path: Path
    symbol: str | None = None
    timeframe: str | None = None
    timestamp_column: str = "timestamp"
    symbol_column: str = "symbol"
    timeframe_column: str = "timeframe"
    open_column: str = "open"
    high_column: str = "high"
    low_column: str = "low"
    close_column: str = "close"
    volume_column: str = "volume"
    start_timestamp: str | None = None
    end_timestamp: str | None = None
    sort_ascending: bool = True
    drop_duplicate_timestamps: bool = True

    def __post_init__(self) -> None:
        if not str(self.csv_path).strip():
            raise ValueError("csv_path cannot be empty.")

        if self.symbol is not None and not self.symbol.strip():
            raise ValueError("symbol cannot be empty when provided.")

        if self.timeframe is not None and not self.timeframe.strip():
            raise ValueError("timeframe cannot be empty when provided.")

    def required_columns(self) -> tuple[str, ...]:
        return (
            self.timestamp_column,
            self.open_column,
            self.high_column,
            self.low_column,
            self.close_column,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "csv_path": self.csv_path.as_posix(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "timestamp_column": self.timestamp_column,
            "symbol_column": self.symbol_column,
            "timeframe_column": self.timeframe_column,
            "open_column": self.open_column,
            "high_column": self.high_column,
            "low_column": self.low_column,
            "close_column": self.close_column,
            "volume_column": self.volume_column,
            "start_timestamp": self.start_timestamp,
            "end_timestamp": self.end_timestamp,
            "sort_ascending": self.sort_ascending,
            "drop_duplicate_timestamps": self.drop_duplicate_timestamps,
        }


@dataclass(frozen=True)
class BacktestDataValidationIssue:
    column: str | None
    message: str
    row_index: int | None = None

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("Backtest data validation issue message cannot be empty.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "column": self.column,
            "message": self.message,
            "row_index": self.row_index,
        }


@dataclass(frozen=True)
class BacktestDataValidationReport:
    valid: bool
    rows: int
    columns: tuple[str, ...]
    issues: tuple[BacktestDataValidationIssue, ...] = ()

    def raise_if_invalid(self) -> None:
        if self.valid:
            return

        messages = [issue.message for issue in self.issues]
        raise ValueError("Backtest data validation failed: " + "; ".join(messages))

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "rows": self.rows,
            "columns": list(self.columns),
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass(frozen=True)
class BacktestDataLoadResult:
    bars: tuple[BacktestBar, ...]
    validation: BacktestDataValidationReport
    config: BacktestDataLoadConfig
    source_rows: int
    loaded_rows: int
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bars": [bar.to_dict() for bar in self.bars],
            "validation": self.validation.to_dict(),
            "config": self.config.to_dict(),
            "source_rows": self.source_rows,
            "loaded_rows": self.loaded_rows,
            "metadata": self.metadata,
        }


def read_backtest_csv_dataframe(csv_path: str | Path) -> pd.DataFrame:
    path = Path(csv_path)

    if not path.exists():
        raise FileNotFoundError(f"Backtest CSV does not exist: {path}")

    return pd.read_csv(path)


def validate_backtest_dataframe(
    dataframe: pd.DataFrame,
    config: BacktestDataLoadConfig,
) -> BacktestDataValidationReport:
    issues: list[BacktestDataValidationIssue] = []

    for column in config.required_columns():
        if column not in dataframe.columns:
            issues.append(
                BacktestDataValidationIssue(
                    column=column,
                    message=f"Required backtest data column is missing: {column}",
                )
            )

    if config.symbol is None and config.symbol_column not in dataframe.columns:
        issues.append(
            BacktestDataValidationIssue(
                column=config.symbol_column,
                message=(
                    "Symbol column is missing and no default symbol was provided."
                ),
            )
        )

    if config.timeframe is None and config.timeframe_column not in dataframe.columns:
        issues.append(
            BacktestDataValidationIssue(
                column=config.timeframe_column,
                message=(
                    "Timeframe column is missing and no default timeframe was provided."
                ),
            )
        )

    if issues:
        return BacktestDataValidationReport(
            valid=False,
            rows=len(dataframe),
            columns=tuple(str(column) for column in dataframe.columns),
            issues=tuple(issues),
        )

    numeric_columns = (
        config.open_column,
        config.high_column,
        config.low_column,
        config.close_column,
    )

    for column in numeric_columns:
        numeric_values = pd.to_numeric(dataframe[column], errors="coerce")

        invalid_indexes = numeric_values[numeric_values.isna()].index.tolist()

        for row_index in invalid_indexes[:10]:
            issues.append(
                BacktestDataValidationIssue(
                    column=column,
                    row_index=int(row_index),
                    message=f"Column contains non-numeric price value: {column}",
                )
            )

    if config.volume_column in dataframe.columns:
        volume_values = pd.to_numeric(dataframe[config.volume_column], errors="coerce")

        invalid_indexes = volume_values[volume_values.isna()].index.tolist()

        for row_index in invalid_indexes[:10]:
            issues.append(
                BacktestDataValidationIssue(
                    column=config.volume_column,
                    row_index=int(row_index),
                    message="Volume column contains non-numeric value.",
                )
            )

    return BacktestDataValidationReport(
        valid=not issues,
        rows=len(dataframe),
        columns=tuple(str(column) for column in dataframe.columns),
        issues=tuple(issues),
    )


def prepare_backtest_dataframe(
    dataframe: pd.DataFrame,
    config: BacktestDataLoadConfig,
) -> pd.DataFrame:
    prepared = dataframe.copy()

    if config.start_timestamp is not None:
        prepared = prepared[
            prepared[config.timestamp_column].astype(str) >= config.start_timestamp
        ]

    if config.end_timestamp is not None:
        prepared = prepared[
            prepared[config.timestamp_column].astype(str) <= config.end_timestamp
        ]

    if config.drop_duplicate_timestamps:
        prepared = prepared.drop_duplicates(
            subset=[config.timestamp_column],
            keep="first",
        )

    if config.sort_ascending:
        prepared = prepared.sort_values(config.timestamp_column, ascending=True)

    return prepared.reset_index(drop=True)


def dataframe_to_backtest_bars(
    dataframe: pd.DataFrame,
    config: BacktestDataLoadConfig,
) -> tuple[BacktestBar, ...]:
    bars: list[BacktestBar] = []

    for _, row in dataframe.iterrows():
        symbol = (
            config.symbol
            if config.symbol is not None
            else str(row[config.symbol_column])
        )
        timeframe = (
            config.timeframe
            if config.timeframe is not None
            else str(row[config.timeframe_column])
        )

        volume = (
            float(row[config.volume_column])
            if config.volume_column in dataframe.columns
            else 0.0
        )

        bars.append(
            BacktestBar(
                timestamp=str(row[config.timestamp_column]),
                symbol=symbol,
                timeframe=timeframe,
                open=float(row[config.open_column]),
                high=float(row[config.high_column]),
                low=float(row[config.low_column]),
                close=float(row[config.close_column]),
                volume=volume,
            )
        )

    return tuple(bars)


def load_backtest_bars_from_csv(
    config: BacktestDataLoadConfig,
) -> BacktestDataLoadResult:
    dataframe = read_backtest_csv_dataframe(config.csv_path)

    validation = validate_backtest_dataframe(dataframe, config)
    validation.raise_if_invalid()

    prepared = prepare_backtest_dataframe(dataframe, config)
    bars = dataframe_to_backtest_bars(prepared, config)

    return BacktestDataLoadResult(
        bars=bars,
        validation=validation,
        config=config,
        source_rows=len(dataframe),
        loaded_rows=len(bars),
        metadata={
            "first_timestamp": bars[0].timestamp if bars else None,
            "last_timestamp": bars[-1].timestamp if bars else None,
            "symbol": bars[0].symbol if bars else config.symbol,
            "timeframe": bars[0].timeframe if bars else config.timeframe,
        },
    )


__all__ = [
    "BacktestDataLoadConfig",
    "BacktestDataLoadResult",
    "BacktestDataValidationIssue",
    "BacktestDataValidationReport",
    "dataframe_to_backtest_bars",
    "load_backtest_bars_from_csv",
    "prepare_backtest_dataframe",
    "read_backtest_csv_dataframe",
    "validate_backtest_dataframe",
]