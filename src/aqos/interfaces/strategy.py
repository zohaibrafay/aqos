"""
Strategy interface.

Defines the contract that all AQOS strategy implementations must follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class StrategyInterfaceDecision:
    """
    Represents a generic strategy decision.
    """

    signal: str
    should_enter: bool
    should_exit: bool
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyInterface(ABC):
    """
    Interface for AQOS strategies.

    Any strategy implementation must be able to generate a signal
    and decide whether to enter or exit a trade.
    """

    VALID_SIGNALS = {
        "buy",
        "sell",
        "hold",
    }

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Return strategy name.
        """

    @abstractmethod
    def generate_signal(
        self,
        market_state: dict[str, Any],
    ) -> str:
        """
        Generate a buy, sell, or hold signal.
        """

    @abstractmethod
    def should_enter(
        self,
        signal: str,
        market_state: dict[str, Any] | None = None,
    ) -> bool:
        """
        Decide whether the strategy should enter a trade.
        """

    @abstractmethod
    def should_exit(
        self,
        signal: str,
        market_state: dict[str, Any] | None = None,
    ) -> bool:
        """
        Decide whether the strategy should exit a trade.
        """

    def decide(
        self,
        market_state: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> StrategyInterfaceDecision:
        """
        Build a complete strategy decision.
        """

        self.validate_market_state(market_state)

        signal = self.generate_signal(market_state)
        self.validate_signal(signal)

        return StrategyInterfaceDecision(
            signal=signal,
            should_enter=self.should_enter(
                signal=signal,
                market_state=market_state,
            ),
            should_exit=self.should_exit(
                signal=signal,
                market_state=market_state,
            ),
            metadata=metadata or {},
        )

    def validate_market_state(
        self,
        market_state: dict[str, Any],
    ) -> None:
        """
        Validate market state.
        """

        if not isinstance(market_state, dict):
            raise TypeError("Market state must be a dictionary.")

        if not market_state:
            raise ValueError("Market state cannot be empty.")

    def validate_signal(
        self,
        signal: str,
    ) -> None:
        """
        Validate strategy signal.
        """

        if signal not in self.VALID_SIGNALS:
            raise ValueError("Signal must be buy, sell, or hold.")

    def get_required_state_value(
        self,
        market_state: dict[str, Any],
        key: str,
    ) -> Any:
        """
        Get a required value from market state.
        """

        self.validate_market_state(market_state)

        if not key:
            raise ValueError("Market state key cannot be empty.")

        if key not in market_state:
            raise ValueError(f"Market state is missing required key: {key}")

        return market_state[key]


__all__ = [
    "StrategyInterface",
    "StrategyInterfaceDecision",
]