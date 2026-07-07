"""
Agent orchestrator.

Coordinates AQOS agents and provides multi-step workflows across
data, market, research, strategy, risk, execution, evaluation, and memory agents.
"""

from __future__ import annotations

from typing import Any

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)
from aqos.agents.data_agent import DataAgent
from aqos.agents.evaluation_agent import EvaluationAgent
from aqos.agents.execution_agent import ExecutionAgent
from aqos.agents.market_agent import MarketAgent
from aqos.agents.memory_agent import MemoryAgent
from aqos.agents.research_agent import ResearchAgent
from aqos.agents.risk_agent import RiskAgent
from aqos.agents.strategy_agent import StrategyAgent


class AgentOrchestrator(AgentBase):
    """
    Coordinates all AQOS agents.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "route",
        "market-strategy-workflow",
        "strategy-risk-workflow",
        "risk-execution-workflow",
        "trade-workflow",
        "research-workflow",
        "backtest-workflow",
        "memory-workflow",
    }

    def __init__(
        self,
        data_agent: DataAgent | None = None,
        market_agent: MarketAgent | None = None,
        research_agent: ResearchAgent | None = None,
        strategy_agent: StrategyAgent | None = None,
        risk_agent: RiskAgent | None = None,
        execution_agent: ExecutionAgent | None = None,
        evaluation_agent: EvaluationAgent | None = None,
        memory_agent: MemoryAgent | None = None,
    ) -> None:
        self._data_agent = data_agent or DataAgent()
        self._market_agent = market_agent or MarketAgent()
        self._research_agent = research_agent or ResearchAgent()
        self._strategy_agent = strategy_agent or StrategyAgent()
        self._risk_agent = risk_agent or RiskAgent()
        self._execution_agent = execution_agent or ExecutionAgent()
        self._evaluation_agent = evaluation_agent or EvaluationAgent()
        self._memory_agent = memory_agent or MemoryAgent()

        self._agents: dict[str, AgentBase] = {
            "data": self._data_agent,
            "market": self._market_agent,
            "research": self._research_agent,
            "strategy": self._strategy_agent,
            "risk": self._risk_agent,
            "execution": self._execution_agent,
            "evaluation": self._evaluation_agent,
            "memory": self._memory_agent,
        }

    @property
    def name(self) -> str:
        """
        Return orchestrator name.
        """

        return "agent-orchestrator"

    @property
    def description(self) -> str:
        """
        Return orchestrator description.
        """

        return "Agent orchestrator for routing and multi-agent AQOS workflows."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run orchestrator task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "route":
            return self.route(task)

        if task.action == "market-strategy-workflow":
            return self.market_strategy_workflow(task)

        if task.action == "strategy-risk-workflow":
            return self.strategy_risk_workflow(task)

        if task.action == "risk-execution-workflow":
            return self.risk_execution_workflow(task)

        if task.action == "trade-workflow":
            return self.trade_workflow(task)

        if task.action == "research-workflow":
            return self.research_workflow(task)

        if task.action == "backtest-workflow":
            return self.backtest_workflow(task)

        if task.action == "memory-workflow":
            return self.memory_workflow(task)

        return self.failure(
            message=f"Unhandled orchestrator action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return orchestrator health.
        """

        agent_health = {}

        for agent_key, agent in self._agents.items():
            result = agent.execute("health")

            agent_health[agent_key] = {
                "success": result.success,
                "message": result.message,
                "data": result.data,
            }

        return self.success(
            message="Agent orchestrator is healthy.",
            data={
                "status": "ok",
                "agents": sorted(self._agents.keys()),
                "agent_health": agent_health,
            },
            metadata=task.metadata,
        )

    def route(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Route a single action to a specific agent.
        """

        agent_name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="agent",
            )
        ).lower()
        action = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="agent_action",
            )
        )

        payload = task.payload.get("agent_payload", {})
        metadata = {
            **task.payload.get("metadata", {}),
            **task.metadata,
        }

        agent = self._get_agent(agent_name)

        result = agent.execute(
            action=action,
            payload=payload,
            metadata=metadata,
        )

        return self.success(
            message="Agent route completed.",
            data={
                "agent": agent_name,
                "agent_action": action,
                "result": self._agent_result_to_dict(result),
            },
            metadata=task.metadata,
        )

    def market_strategy_workflow(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Build market state and generate strategy handoff.
        """

        symbol, timeframe = self._get_symbol_timeframe(task)

        market_result = self._market_agent.execute(
            action="market-state",
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
            },
            metadata=task.metadata,
        )

        if not market_result.success:
            return self._workflow_failure(
                message="Market strategy workflow failed.",
                failed_step="market-state",
                result=market_result,
                metadata=task.metadata,
            )

        market_state = {
            **market_result.data,
            "entry_price": market_result.data["close"],
        }

        strategy_result = self._strategy_agent.execute(
            action="handoff",
            payload={
                "market_state": market_state,
            },
            metadata=task.metadata,
        )

        if not strategy_result.success:
            return self._workflow_failure(
                message="Market strategy workflow failed.",
                failed_step="strategy-handoff",
                result=strategy_result,
                metadata=task.metadata,
            )

        return self.success(
            message="Market strategy workflow completed.",
            data={
                "market_state": market_result.data,
                "strategy_handoff": strategy_result.data,
            },
            metadata=task.metadata,
        )

    def strategy_risk_workflow(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Convert strategy handoff into risk handoff.
        """

        strategy_handoff = self.get_required_payload_value(
            payload=task.payload,
            key="strategy_handoff",
        )

        if not isinstance(strategy_handoff, dict):
            raise TypeError("Strategy handoff must be a dictionary.")

        if strategy_handoff.get("signal") == "hold":
            return self.failure(
                message="Strategy signal is hold; no risk workflow required.",
                data={
                    "strategy_handoff": strategy_handoff,
                },
                metadata=task.metadata,
            )

        trade_request = self._build_trade_request(
            strategy_handoff=strategy_handoff,
            task_payload=task.payload,
        )

        risk_result = self._risk_agent.execute(
            action="risk-handoff",
            payload={
                "trade_request": trade_request,
            },
            metadata=task.metadata,
        )

        if not risk_result.success:
            return self._workflow_failure(
                message="Strategy risk workflow failed.",
                failed_step="risk-handoff",
                result=risk_result,
                metadata=task.metadata,
            )

        return self.success(
            message="Strategy risk workflow completed.",
            data={
                "strategy_handoff": strategy_handoff,
                "trade_request": trade_request,
                "risk_handoff": risk_result.data,
            },
            metadata=task.metadata,
        )

    def risk_execution_workflow(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Execute a risk-approved trade.
        """

        risk_handoff = self.get_required_payload_value(
            payload=task.payload,
            key="risk_handoff",
        )

        if not isinstance(risk_handoff, dict):
            raise TypeError("Risk handoff must be a dictionary.")

        execution_result = self._execution_agent.execute(
            action="execute-trade",
            payload={
                "trade": risk_handoff,
            },
            metadata=task.metadata,
        )

        if not execution_result.success:
            return self._workflow_failure(
                message="Risk execution workflow failed.",
                failed_step="execute-trade",
                result=execution_result,
                metadata=task.metadata,
            )

        return self.success(
            message="Risk execution workflow completed.",
            data={
                "risk_handoff": risk_handoff,
                "execution": execution_result.data,
            },
            metadata=task.metadata,
        )

    def trade_workflow(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a market → strategy → risk → execution workflow.
        """

        market_strategy_result = self.market_strategy_workflow(task)

        if not market_strategy_result.success:
            return market_strategy_result

        strategy_risk_result = self.strategy_risk_workflow(
            AgentTask(
                action="strategy-risk-workflow",
                payload={
                    "strategy_handoff": market_strategy_result.data["strategy_handoff"],
                    "account_balance": task.payload.get("account_balance", 10_000.0),
                    "risk_percent": task.payload.get("risk_percent", 0.01),
                    "max_risk_percent": task.payload.get("max_risk_percent", 0.02),
                    "max_position_size": task.payload.get("max_position_size"),
                },
                metadata=task.metadata,
            )
        )

        if not strategy_risk_result.success:
            return strategy_risk_result

        risk_execution_result = self.risk_execution_workflow(
            AgentTask(
                action="risk-execution-workflow",
                payload={
                    "risk_handoff": strategy_risk_result.data["risk_handoff"],
                },
                metadata=task.metadata,
            )
        )

        if not risk_execution_result.success:
            return risk_execution_result

        return self.success(
            message="Trade workflow completed.",
            data={
                "market_state": market_strategy_result.data["market_state"],
                "strategy_handoff": market_strategy_result.data["strategy_handoff"],
                "trade_request": strategy_risk_result.data["trade_request"],
                "risk_handoff": strategy_risk_result.data["risk_handoff"],
                "execution": risk_execution_result.data["execution"],
            },
            metadata=task.metadata,
        )

    def research_workflow(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a research hypothesis and experiment planning workflow.
        """

        symbol = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="symbol",
            )
        )
        signal_source = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="signal_source",
            )
        )

        timeframe = str(task.payload.get("timeframe", "H1"))
        objective = str(task.payload.get("objective", "improve signal quality"))
        experiment_name = str(
            task.payload.get(
                "experiment_name",
                f"{symbol.lower()}-{signal_source.replace(' ', '-')}-experiment",
            )
        )

        hypothesis_result = self._research_agent.execute(
            action="hypothesis",
            payload={
                "symbol": symbol,
                "timeframe": timeframe,
                "signal_source": signal_source,
                "objective": objective,
            },
            metadata=task.metadata,
        )

        if not hypothesis_result.success:
            return self._workflow_failure(
                message="Research workflow failed.",
                failed_step="hypothesis",
                result=hypothesis_result,
                metadata=task.metadata,
            )

        plan_result = self._research_agent.execute(
            action="experiment-plan",
            payload={
                "name": experiment_name,
                "symbol": symbol,
                "timeframe": timeframe,
                "hypothesis": hypothesis_result.data["hypothesis"],
                "metric": task.payload.get("metric", "win_rate"),
            },
            metadata=task.metadata,
        )

        if not plan_result.success:
            return self._workflow_failure(
                message="Research workflow failed.",
                failed_step="experiment-plan",
                result=plan_result,
                metadata=task.metadata,
            )

        return self.success(
            message="Research workflow completed.",
            data={
                "hypothesis": hypothesis_result.data,
                "experiment_plan": plan_result.data,
            },
            metadata=task.metadata,
        )

    def backtest_workflow(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run backtest and generate evaluation report.
        """

        name = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="name",
            )
        )

        run_result = self._evaluation_agent.execute(
            action="run-backtest",
            payload={
                "name": name,
                "profits": self.get_required_payload_value(
                    payload=task.payload,
                    key="profits",
                ),
                "initial_balance": self.get_required_payload_value(
                    payload=task.payload,
                    key="initial_balance",
                ),
                "metadata": task.payload.get("metadata", {}),
            },
            metadata=task.metadata,
        )

        if not run_result.success:
            return self._workflow_failure(
                message="Backtest workflow failed.",
                failed_step="run-backtest",
                result=run_result,
                metadata=task.metadata,
            )

        report_result = self._evaluation_agent.execute(
            action="evaluation-report",
            payload={
                "name": name,
            },
            metadata=task.metadata,
        )

        if not report_result.success:
            return self._workflow_failure(
                message="Backtest workflow failed.",
                failed_step="evaluation-report",
                result=report_result,
                metadata=task.metadata,
            )

        return self.success(
            message="Backtest workflow completed.",
            data={
                "backtest": run_result.data,
                "report": report_result.data,
            },
            metadata=task.metadata,
        )

    def memory_workflow(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Store and optionally recall a memory.
        """

        remember_result = self._memory_agent.execute(
            action="remember",
            payload={
                "memory_id": self.get_required_payload_value(
                    payload=task.payload,
                    key="memory_id",
                ),
                "content": self.get_required_payload_value(
                    payload=task.payload,
                    key="content",
                ),
                "memory_type": task.payload.get("memory_type", "observation"),
                "importance": task.payload.get("importance", 0.5),
                "metadata": task.payload.get("metadata", {}),
            },
            metadata=task.metadata,
        )

        if not remember_result.success:
            return self._workflow_failure(
                message="Memory workflow failed.",
                failed_step="remember",
                result=remember_result,
                metadata=task.metadata,
            )

        query = task.payload.get("query")

        if query is None:
            return self.success(
                message="Memory workflow completed.",
                data={
                    "remember": remember_result.data,
                    "recall": None,
                },
                metadata=task.metadata,
            )

        recall_result = self._memory_agent.execute(
            action="recall",
            payload={
                "query": query,
                "limit": task.payload.get("limit"),
                "memory_type": task.payload.get("memory_type"),
            },
            metadata=task.metadata,
        )

        if not recall_result.success:
            return self._workflow_failure(
                message="Memory workflow failed.",
                failed_step="recall",
                result=recall_result,
                metadata=task.metadata,
            )

        return self.success(
            message="Memory workflow completed.",
            data={
                "remember": remember_result.data,
                "recall": recall_result.data,
            },
            metadata=task.metadata,
        )

    def _build_trade_request(
        self,
        strategy_handoff: dict[str, Any],
        task_payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build risk trade request from strategy handoff.
        """

        trade_request = {
            "symbol": strategy_handoff.get("symbol", "UNKNOWN"),
            "side": strategy_handoff["signal"],
            "account_balance": task_payload.get("account_balance", 10_000.0),
            "risk_percent": task_payload.get("risk_percent", 0.01),
            "entry_price": strategy_handoff["entry_price"],
            "stop_loss_price": strategy_handoff["stop_loss_price"],
        }

        if strategy_handoff.get("take_profit_price") is not None:
            trade_request["take_profit_price"] = strategy_handoff[
                "take_profit_price"
            ]

        if task_payload.get("max_risk_percent") is not None:
            trade_request["max_risk_percent"] = task_payload["max_risk_percent"]

        if task_payload.get("max_position_size") is not None:
            trade_request["max_position_size"] = task_payload["max_position_size"]

        return trade_request

    def _get_agent(
        self,
        agent_name: str,
    ) -> AgentBase:
        """
        Get agent by name.
        """

        if agent_name not in self._agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        return self._agents[agent_name]

    def _get_symbol_timeframe(
        self,
        task: AgentTask,
    ) -> tuple[str, str]:
        """
        Get symbol and timeframe from payload.
        """

        symbol = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="symbol",
            )
        )
        timeframe = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="timeframe",
            )
        )

        return symbol, timeframe

    def _agent_result_to_dict(
        self,
        result: AgentResult,
    ) -> dict[str, Any]:
        """
        Convert AgentResult to dictionary.
        """

        return {
            "success": result.success,
            "message": result.message,
            "data": result.data,
            "metadata": result.metadata,
        }

    def _workflow_failure(
        self,
        message: str,
        failed_step: str,
        result: AgentResult,
        metadata: dict[str, Any],
    ) -> AgentResult:
        """
        Build workflow failure result.
        """

        return self.failure(
            message=message,
            data={
                "failed_step": failed_step,
                "result": self._agent_result_to_dict(result),
            },
            metadata=metadata,
        )


__all__ = [
    "AgentOrchestrator",
]