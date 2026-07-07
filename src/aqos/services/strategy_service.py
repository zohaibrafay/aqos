"""
Strategy service.

Provides a service-level interface for generating strategy signals,
entry/exit decisions, and strategy-level stop-loss/take-profit plans.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aqos.strategy import (
    EntryEngine,
    ExitEngine,
    SignalEngine,
    StopLossEngine,
    TakeProfitEngine,
)


@dataclass(slots=True, frozen=True)
class StrategyDecision:
    """
    Represents a complete strategy decision.
    """

    signal: str
    should_enter: bool
    should_exit: bool
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class StrategyService:
    """
    Service layer for AQOS strategy operations.
    """

    def __init__(self) -> None:
        self._signal_engine = SignalEngine()
        self._entry_engine = EntryEngine()
        self._exit_engine = ExitEngine()
        self._stop_loss_engine = StopLossEngine()
        self._take_profit_engine = TakeProfitEngine()

    def generate_signal(
        self,
        regime: str,
        trend: str,
    ) -> str:
        """
        Generate a strategy signal.
        """

        self._validate_text("Regime", regime)
        self._validate_text("Trend", trend)

        signal = self._signal_engine.generate(
            regime=regime,
            trend=trend,
        )

        if signal != "hold":
            return signal

        normalized_regime = regime.lower().strip()
        normalized_trend = trend.lower().strip()

        bullish_regimes = {
            "bullish",
            "bull",
            "uptrend",
            "trending_up",
        }

        bullish_trends = {
            "bullish",
            "up",
            "uptrend",
            "trending_up",
        }

        bearish_regimes = {
            "bearish",
            "bear",
            "downtrend",
            "trending_down",
        }

        bearish_trends = {
            "bearish",
            "down",
            "downtrend",
            "trending_down",
        }

        if (
            normalized_regime in bullish_regimes
            and normalized_trend in bullish_trends
        ):
            return "buy"

        if (
            normalized_regime in bearish_regimes
            and normalized_trend in bearish_trends
        ):
            return "sell"

        return "hold"

    def should_enter(
        self,
        signal: str,
    ) -> bool:
        """
        Check whether strategy should enter.
        """

        self._validate_signal(signal)

        return self._entry_engine.should_enter(signal)

    def should_exit(
        self,
        signal: str,
    ) -> bool:
        """
        Check whether strategy should exit.
        """

        self._validate_signal(signal)

        return self._exit_engine.should_exit(signal)

    def calculate_stop_loss(
        self,
        entry_price: float,
        side: str,
    ) -> float:
        """
        Calculate strategy-level stop-loss price.
        """

        self._validate_price(entry_price)
        self._validate_side(side)

        return self._stop_loss_engine.calculate(
            entry_price=entry_price,
            side=side,
        )

    def calculate_take_profit(
        self,
        entry_price: float,
        side: str,
    ) -> float:
        """
        Calculate strategy-level take-profit price.
        """

        self._validate_price(entry_price)
        self._validate_side(side)

        return self._take_profit_engine.calculate(
            entry_price=entry_price,
            side=side,
        )

    def decide(
        self,
        regime: str,
        trend: str,
        entry_price: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StrategyDecision:
        """
        Build a complete strategy decision.
        """

        signal = self.generate_signal(
            regime=regime,
            trend=trend,
        )

        should_enter = self.should_enter(signal)
        should_exit = self.should_exit(signal)

        stop_loss_price = None
        take_profit_price = None

        if should_enter and entry_price is not None:
            self._validate_price(entry_price)

            stop_loss_price = self.calculate_stop_loss(
                entry_price=entry_price,
                side=signal,
            )

            take_profit_price = self.calculate_take_profit(
                entry_price=entry_price,
                side=signal,
            )

        return StrategyDecision(
            signal=signal,
            should_enter=should_enter,
            should_exit=should_exit,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            metadata=metadata or {},
        )

    def _validate_text(
        self,
        name: str,
        value: str,
    ) -> None:
        """
        Validate text input.
        """

        if not value:
            raise ValueError(f"{name} cannot be empty.")

    def _validate_signal(
        self,
        signal: str,
    ) -> None:
        """
        Validate strategy signal.
        """

        if signal not in {"buy", "sell", "hold"}:
            raise ValueError("Signal must be buy, sell, or hold.")

    def _validate_side(
        self,
        side: str,
    ) -> None:
        """
        Validate trade side.
        """

        if side not in {"buy", "sell"}:
            raise ValueError("Side must be either 'buy' or 'sell'.")

    def _validate_price(
        self,
        price: float,
    ) -> None:
        """
        Validate price input.
        """

        if price <= 0:
            raise ValueError("Price must be greater than zero.")


__all__ = [
    "StrategyDecision",
    "StrategyService",
]