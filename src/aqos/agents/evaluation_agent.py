"""
Evaluation agent.

Provides agent-level workflows for backtest execution,
performance summaries, report generation, and backtest comparisons.
"""

from __future__ import annotations

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)
from aqos.services import BacktestService


class EvaluationAgent(AgentBase):
    """
    Agent responsible for evaluation and backtesting workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "run-backtest",
        "backtest-summary",
        "compare-backtests",
        "performance-grade",
        "evaluation-report",
    }

    def __init__(
        self,
        backtest_service: BacktestService | None = None,
    ) -> None:
        self._backtest_service = backtest_service or BacktestService()

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "evaluation-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for backtests, performance summaries, reports, and comparisons."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run an evaluation agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "run-backtest":
            return self.run_backtest(task)

        if task.action == "backtest-summary":
            return self.backtest_summary(task)

        if task.action == "compare-backtests":
            return self.compare_backtests(task)

        if task.action == "performance-grade":
            return self.performance_grade(task)

        if task.action == "evaluation-report":
            return self.evaluation_report(task)

        return self.failure(
            message=f"Unhandled evaluation agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return evaluation agent health.
        """

        return self.success(
            message="Evaluation agent is healthy.",
            data={
                "status": "ok",
                "backtest_runs": self._backtest_service.count(),
            },
            metadata=task.metadata,
        )

    def run_backtest(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a backtest.
        """

        name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="name",
            )
        )
        profits = self.get_required_payload_value(
            payload=task.payload,
            key="profits",
        )
        initial_balance = float(
            self.get_required_payload_value(
                payload=task.payload,
                key="initial_balance",
            )
        )

        metadata = {
            **task.payload.get("metadata", {}),
            **task.metadata,
        }

        if self._backtest_service.get(name) is not None:
            return self.failure(
                message="Backtest run already exists.",
                metadata=task.metadata,
            )

        try:
            run = self._backtest_service.run(
                name=name,
                profits=profits,
                initial_balance=initial_balance,
                metadata=metadata,
            )

            return self.success(
                message="Backtest executed.",
                data=self._backtest_run_to_dict(run),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )
    def backtest_summary(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return backtest summary.
        """

        name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="name",
            )
        )

        run = self._backtest_service.get(name)

        if run is None:
            return self.failure(
                message="Backtest run does not exist.",
                metadata=task.metadata,
            )

        return self.success(
            message="Backtest summary generated.",
            data=self._backtest_run_to_dict(run),
            metadata=task.metadata,
        )

    def compare_backtests(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Compare two backtest runs.
        """

        baseline_name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="baseline_name",
            )
        )
        candidate_name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="candidate_name",
            )
        )

        baseline = self._backtest_service.get(baseline_name)
        candidate = self._backtest_service.get(candidate_name)

        if baseline is None:
            return self.failure(
                message="Baseline backtest run does not exist.",
                metadata=task.metadata,
            )

        if candidate is None:
            return self.failure(
                message="Candidate backtest run does not exist.",
                metadata=task.metadata,
            )

        baseline_result = baseline.result
        candidate_result = candidate.result

        profit_delta = candidate_result.total_profit - baseline_result.total_profit
        return_delta = candidate_result.return_percent - baseline_result.return_percent
        win_rate_delta = candidate_result.win_rate - baseline_result.win_rate
        drawdown_delta = candidate_result.max_drawdown - baseline_result.max_drawdown

        improved = (
            profit_delta > 0
            and return_delta >= 0
            and drawdown_delta <= 0
        )

        return self.success(
            message="Backtests compared.",
            data={
                "baseline_name": baseline.name,
                "candidate_name": candidate.name,
                "baseline_total_profit": baseline_result.total_profit,
                "candidate_total_profit": candidate_result.total_profit,
                "profit_delta": profit_delta,
                "return_delta": return_delta,
                "win_rate_delta": win_rate_delta,
                "drawdown_delta": drawdown_delta,
                "improved": improved,
            },
            metadata=task.metadata,
        )

    def performance_grade(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Grade a backtest run.
        """

        name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="name",
            )
        )

        run = self._backtest_service.get(name)

        if run is None:
            return self.failure(
                message="Backtest run does not exist.",
                metadata=task.metadata,
            )

        grade = self._grade_result(run.result)

        return self.success(
            message="Performance grade generated.",
            data={
                "name": run.name,
                "grade": grade,
                "total_profit": run.result.total_profit,
                "return_percent": run.result.return_percent,
                "win_rate": run.result.win_rate,
                "max_drawdown": run.result.max_drawdown,
            },
            metadata=task.metadata,
        )

    def evaluation_report(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Generate a lightweight evaluation report.
        """

        name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="name",
            )
        )

        run = self._backtest_service.get(name)

        if run is None:
            return self.failure(
                message="Backtest run does not exist.",
                metadata=task.metadata,
            )

        grade = self._grade_result(run.result)

        report = {
            "name": run.name,
            "summary": (
                f"Backtest {run.name} finished with total profit "
                f"{run.result.total_profit} and final balance "
                f"{run.result.final_balance}."
            ),
            "grade": grade,
            "metrics": {
                "initial_balance": run.result.initial_balance,
                "final_balance": run.result.final_balance,
                "total_profit": run.result.total_profit,
                "return_percent": run.result.return_percent,
                "win_rate": run.result.win_rate,
                "max_drawdown": run.result.max_drawdown,
                "total_trades": len(run.result.trades),
            },
            "metadata": run.metadata,
        }

        return self.success(
            message="Evaluation report generated.",
            data=report,
            metadata=task.metadata,
        )

    def _backtest_run_to_dict(
        self,
        run,
    ) -> dict:
        """
        Convert backtest run to dictionary.
        """

        return {
            "name": run.name,
            "initial_balance": run.result.initial_balance,
            "final_balance": run.result.final_balance,
            "total_profit": run.result.total_profit,
            "return_percent": run.result.return_percent,
            "win_rate": run.result.win_rate,
            "max_drawdown": run.result.max_drawdown,
            "total_trades": len(run.result.trades),
            "metadata": run.metadata,
        }

    def _grade_result(
        self,
        result,
    ) -> str:
        """
        Grade backtest performance.
        """

        if (
            result.total_profit > 0
            and result.return_percent > 0
            and result.win_rate >= 0.6
            and result.max_drawdown <= 0
        ):
            return "A"

        if result.total_profit > 0 and result.return_percent > 0:
            return "B"

        if result.total_profit == 0:
            return "C"

        return "D"


__all__ = [
    "EvaluationAgent",
]