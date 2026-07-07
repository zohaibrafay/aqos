"""
Backtest service.

Provides a service-level interface for running, storing,
retrieving, and reporting backtest results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.evaluation import (
    Backtester,
    BacktestResult,
    EvaluationReport,
    ReportGenerator,
)


@dataclass(slots=True, frozen=True)
class BacktestRun:
    """
    Represents a stored backtest run.
    """

    name: str
    result: BacktestResult
    metadata: dict[str, Any] = field(default_factory=dict)


class BacktestService:
    """
    Service layer for AQOS backtesting.
    """

    def __init__(self) -> None:
        self._backtester = Backtester()
        self._report_generator = ReportGenerator()
        self._runs: dict[str, BacktestRun] = {}

    def run(
        self,
        name: str,
        profits: list[float],
        initial_balance: float,
        metadata: dict[str, Any] | None = None,
    ) -> BacktestRun:
        """
        Run and store a backtest.
        """

        self._validate_name(name)

        result = self._backtester.run(
            profits=profits,
            initial_balance=initial_balance,
        )

        run = BacktestRun(
            name=name,
            result=result,
            metadata=metadata or {},
        )

        self._runs[name] = run

        return run

    def get(
        self,
        name: str,
    ) -> BacktestRun | None:
        """
        Get a stored backtest run.
        """

        self._validate_name(name)

        return self._runs.get(name)

    def get_result(
        self,
        name: str,
    ) -> BacktestResult:
        """
        Get a stored backtest result.
        """

        run = self.get(name)

        if run is None:
            raise ValueError("Backtest run does not exist.")

        return run.result

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Check whether a backtest run exists.
        """

        self._validate_name(name)

        return name in self._runs

    def list(self) -> list[BacktestRun]:
        """
        Return all stored backtest runs.
        """

        return list(self._runs.values())

    def list_names(self) -> list[str]:
        """
        Return stored backtest run names.
        """

        return sorted(self._runs.keys())

    def count(self) -> int:
        """
        Return the number of stored backtest runs.
        """

        return len(self._runs)

    def remove(
        self,
        name: str,
    ) -> None:
        """
        Remove a stored backtest run.
        """

        self._validate_name(name)

        self._runs.pop(name, None)

    def clear(self) -> None:
        """
        Clear all stored backtest runs.
        """

        self._runs.clear()

    def generate_report(
        self,
        name: str,
        title: str = "Backtest Report",
    ) -> EvaluationReport:
        """
        Generate a report for a stored backtest run.
        """

        result = self.get_result(name)

        return self._report_generator.generate_backtest_report(
            result=result,
            title=title,
        )

    def generate_text_summary(
        self,
        name: str,
        title: str = "Backtest Report",
    ) -> str:
        """
        Generate a text summary for a stored backtest run.
        """

        report = self.generate_report(
            name=name,
            title=title,
        )

        return self._report_generator.generate_text_summary(report)

    def best_run_by_profit(self) -> BacktestRun:
        """
        Return the run with the highest total profit.
        """

        if not self._runs:
            raise ValueError("No backtest runs are available.")

        return max(
            self._runs.values(),
            key=lambda run: run.result.total_profit,
        )

    def _validate_name(
        self,
        name: str,
    ) -> None:
        """
        Validate backtest run name.
        """

        if not name:
            raise ValueError("Backtest run name cannot be empty.")


__all__ = [
    "BacktestRun",
    "BacktestService",
]