"""
Evaluation pipeline.

Coordinates metrics, backtesting, walk-forward validation,
paper trading, and report generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aqos.evaluation.backtest import Backtester, BacktestResult
from aqos.evaluation.metrics import EvaluationMetrics
from aqos.evaluation.paper_trading import PaperTradingEngine
from aqos.evaluation.report import EvaluationReport, ReportGenerator
from aqos.evaluation.walk_forward import (
    WalkForwardSplit,
    WalkForwardValidator,
)


@dataclass(slots=True)
class EvaluationPipeline:
    """
    Unified evaluation pipeline.
    """

    metrics: EvaluationMetrics
    backtester: Backtester
    report_generator: ReportGenerator
    walk_forward_validator: WalkForwardValidator | None = None
    paper_trading_engine: PaperTradingEngine | None = None

    def evaluate_classification(
        self,
        actual: list[Any],
        predicted: list[Any],
    ) -> dict[str, float]:
        """
        Evaluate classification predictions.
        """

        return {
            "accuracy": self.metrics.accuracy(
                actual=actual,
                predicted=predicted,
            )
        }

    def evaluate_regression(
        self,
        actual: list[float],
        predicted: list[float],
    ) -> dict[str, float]:
        """
        Evaluate regression predictions.
        """

        return {
            "mae": self.metrics.mean_absolute_error(
                actual=actual,
                predicted=predicted,
            ),
            "mse": self.metrics.mean_squared_error(
                actual=actual,
                predicted=predicted,
            ),
            "rmse": self.metrics.root_mean_squared_error(
                actual=actual,
                predicted=predicted,
            ),
        }

    def evaluate_trades(
        self,
        profits: list[float],
    ) -> dict[str, float]:
        """
        Evaluate trade profit/loss values.
        """

        return {
            "total_profit": self.metrics.total_profit(profits),
            "average_profit": self.metrics.average_profit(profits),
            "win_rate": self.metrics.win_rate(profits),
            "profit_factor": self.metrics.profit_factor(profits),
        }

    def run_backtest(
        self,
        profits: list[float],
        initial_balance: float,
    ) -> BacktestResult:
        """
        Run a backtest.
        """

        return self.backtester.run(
            profits=profits,
            initial_balance=initial_balance,
        )

    def generate_backtest_report(
        self,
        profits: list[float],
        initial_balance: float,
        title: str = "Backtest Report",
    ) -> EvaluationReport:
        """
        Run a backtest and generate an evaluation report.
        """

        result = self.run_backtest(
            profits=profits,
            initial_balance=initial_balance,
        )

        return self.report_generator.generate_backtest_report(
            result=result,
            title=title,
        )

    def generate_backtest_text_summary(
        self,
        profits: list[float],
        initial_balance: float,
        title: str = "Backtest Report",
    ) -> str:
        """
        Run a backtest and generate a text summary.
        """

        report = self.generate_backtest_report(
            profits=profits,
            initial_balance=initial_balance,
            title=title,
        )

        return self.report_generator.generate_text_summary(report)

    def walk_forward_split(
        self,
        data: list[Any],
    ) -> list[WalkForwardSplit]:
        """
        Run walk-forward validation split.
        """

        if self.walk_forward_validator is None:
            raise ValueError("Walk-forward validator is not configured.")

        return self.walk_forward_validator.split(data)

    def paper_trading(self) -> PaperTradingEngine:
        """
        Return configured paper-trading engine.
        """

        if self.paper_trading_engine is None:
            raise ValueError("Paper trading engine is not configured.")

        return self.paper_trading_engine


__all__ = ["EvaluationPipeline"]