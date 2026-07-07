"""
Strategy agent.

Provides agent-level workflows for strategy signals, decisions,
signal explanations, entry checks, exit checks, and strategy handoff payloads.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)
from aqos.services import StrategyService


class StrategyAgent(AgentBase):
    """
    Agent responsible for strategy workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "signal",
        "decision",
        "explain-signal",
        "entry-check",
        "exit-check",
        "handoff",
    }

    VALID_SIGNALS = {
        "buy",
        "sell",
        "hold",
    }

    def __init__(
        self,
        strategy_service: StrategyService | None = None,
    ) -> None:
        self._strategy_service = strategy_service or StrategyService()

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "strategy-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for strategy signals, decisions, explanations, and handoffs."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a strategy agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "signal":
            return self.signal(task)

        if task.action == "decision":
            return self.decision(task)

        if task.action == "explain-signal":
            return self.explain_signal(task)

        if task.action == "entry-check":
            return self.entry_check(task)

        if task.action == "exit-check":
            return self.exit_check(task)

        if task.action == "handoff":
            return self.handoff(task)

        return self.failure(
            message=f"Unhandled strategy agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return strategy agent health.
        """

        return self.success(
            message="Strategy agent is healthy.",
            data={
                "status": "ok",
                "supported_signals": sorted(self.VALID_SIGNALS),
            },
            metadata=task.metadata,
        )

    def signal(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Generate a strategy signal.
        """

        market_state = self._get_market_state(task)

        try:
            decision = self._build_strategy_decision(
                market_state=market_state,
                metadata=task.metadata,
            )

            return self.success(
                message="Strategy signal generated.",
                data={
                    "signal": decision.signal,
                    "regime": str(market_state["regime"]),
                    "trend": str(market_state["trend"]),
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def decision(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Generate a full strategy decision.
        """

        market_state = self._get_market_state(task)

        try:
            decision = self._build_strategy_decision(
                market_state=market_state,
                metadata=task.metadata,
            )

            return self.success(
                message="Strategy decision generated.",
                data=asdict(decision),
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def explain_signal(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Explain a strategy signal.
        """

        signal = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="signal",
            )
        ).lower()

        self._validate_signal(signal)

        explanation = self._signal_explanation(signal)

        return self.success(
            message="Strategy signal explained.",
            data={
                "signal": signal,
                "explanation": explanation,
                "bias": self._signal_bias(signal),
            },
            metadata=task.metadata,
        )

    def entry_check(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Check whether strategy should enter.
        """

        signal = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="signal",
            )
        ).lower()

        self._validate_signal(signal)

        should_enter = signal in {"buy", "sell"}

        return self.success(
            message="Strategy entry check completed.",
            data={
                "signal": signal,
                "should_enter": should_enter,
                "reason": self._entry_reason(signal, should_enter),
            },
            metadata=task.metadata,
        )

    def exit_check(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Check whether strategy should exit.
        """

        signal = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="signal",
            )
        ).lower()

        current_position = str(task.payload.get("current_position", "none")).lower()

        self._validate_signal(signal)

        should_exit = self._should_exit_position(
            signal=signal,
            current_position=current_position,
        )

        return self.success(
            message="Strategy exit check completed.",
            data={
                "signal": signal,
                "current_position": current_position,
                "should_exit": should_exit,
                "reason": self._exit_reason(
                    signal=signal,
                    current_position=current_position,
                    should_exit=should_exit,
                ),
            },
            metadata=task.metadata,
        )

    def handoff(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Build a strategy handoff payload for downstream risk/execution agents.
        """

        market_state = self._get_market_state(task)

        try:
            decision = self._build_strategy_decision(
                market_state=market_state,
                metadata=task.metadata,
            )

            handoff_payload = {
                "symbol": str(market_state.get("symbol", "UNKNOWN")).upper(),
                "timeframe": str(market_state.get("timeframe", "UNKNOWN")).upper(),
                "signal": decision.signal,
                "should_enter": decision.should_enter,
                "should_exit": decision.should_exit,
                "entry_price": market_state.get("entry_price"),
                "stop_loss_price": decision.stop_loss_price,
                "take_profit_price": decision.take_profit_price,
                "strategy_metadata": decision.metadata,
            }

            return self.success(
                message="Strategy handoff generated.",
                data=handoff_payload,
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def _get_market_state(
        self,
        task: AgentTask,
    ) -> dict[str, Any]:
        """
        Get market state from task payload.
        """

        market_state = self.get_required_payload_value(
            payload=task.payload,
            key="market_state",
        )

        if not isinstance(market_state, dict):
            raise TypeError("Market state must be a dictionary.")

        if not market_state:
            raise ValueError("Market state cannot be empty.")

        if "regime" not in market_state:
            raise ValueError("Market state is missing required key: regime")

        if "trend" not in market_state:
            raise ValueError("Market state is missing required key: trend")

        return market_state

    def _build_strategy_decision(
        self,
        market_state: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ):
        """
        Build strategy decision through StrategyService.
        """

        return self._strategy_service.decide(
            regime=str(market_state["regime"]),
            trend=str(market_state["trend"]),
            entry_price=market_state.get("entry_price"),
            metadata=metadata or {},
        )

    def _validate_signal(
        self,
        signal: str,
    ) -> None:
        """
        Validate strategy signal.
        """

        if signal not in self.VALID_SIGNALS:
            raise ValueError("Signal must be buy, sell, or hold.")

    def _signal_explanation(
        self,
        signal: str,
    ) -> str:
        """
        Return human-readable signal explanation.
        """

        if signal == "buy":
            return "Buy signal indicates bullish strategy bias."

        if signal == "sell":
            return "Sell signal indicates bearish strategy bias."

        return "Hold signal indicates no active entry bias."

    def _signal_bias(
        self,
        signal: str,
    ) -> str:
        """
        Return signal bias.
        """

        if signal == "buy":
            return "bullish"

        if signal == "sell":
            return "bearish"

        return "neutral"

    def _entry_reason(
        self,
        signal: str,
        should_enter: bool,
    ) -> str:
        """
        Return entry reason.
        """

        if should_enter:
            return f"{signal} signal allows a new strategy entry."

        return "Hold signal does not allow a new strategy entry."

    def _should_exit_position(
        self,
        signal: str,
        current_position: str,
    ) -> bool:
        """
        Decide whether current position should exit.
        """

        if current_position == "long" and signal == "sell":
            return True

        if current_position == "short" and signal == "buy":
            return True

        if current_position in {"long", "short"} and signal == "hold":
            return True

        return False

    def _exit_reason(
        self,
        signal: str,
        current_position: str,
        should_exit: bool,
    ) -> str:
        """
        Return exit reason.
        """

        if should_exit:
            return (
                f"{current_position} position should exit because signal is {signal}."
            )

        return "No strategy exit required."


__all__ = [
    "StrategyAgent",
]