"""
Evaluation reports.

Provides lightweight report generation for AQOS evaluation results.
"""

from __future__ import annotations

from dataclasses import dataclass

from aqos.evaluation.backtest import BacktestResult


@dataclass(slots=True, frozen=True)
class EvaluationReport:
    """
    Represents an evaluation report.
    """

    title: str
    summary: dict
    details: dict


@dataclass(slots=True)
class ReportGenerator:
    """
    Evaluation report generator.
    """

    def generate_backtest_report(
        self,
        result: BacktestResult,
        title: str = "Backtest Report",
    ) -> EvaluationReport:
        """
        Generate a report from a backtest result.
        """

        if not title:
            raise ValueError("Report title cannot be empty.")

        summary = {
            "initial_balance": result.initial_balance,
            "final_balance": result.final_balance,
            "total_profit": result.total_profit,
            "return_percent": result.return_percent,
            "win_rate": result.win_rate,
            "max_drawdown": result.max_drawdown,
            "total_trades": len(result.trades),
        }

        details = {
            "trades": [
                {
                    "index": trade.index,
                    "profit": trade.profit,
                    "balance": trade.balance,
                }
                for trade in result.trades
            ]
        }

        return EvaluationReport(
            title=title,
            summary=summary,
            details=details,
        )

    def generate_text_summary(
        self,
        report: EvaluationReport,
    ) -> str:
        """
        Generate a text summary from an evaluation report.
        """

        if not report.title:
            raise ValueError("Report title cannot be empty.")

        summary = report.summary

        return "\n".join(
            [
                report.title,
                f"Initial Balance: {summary['initial_balance']}",
                f"Final Balance: {summary['final_balance']}",
                f"Total Profit: {summary['total_profit']}",
                f"Return Percent: {summary['return_percent']}",
                f"Win Rate: {summary['win_rate']}",
                f"Max Drawdown: {summary['max_drawdown']}",
                f"Total Trades: {summary['total_trades']}",
            ]
        )


__all__ = [
    "EvaluationReport",
    "ReportGenerator",
]