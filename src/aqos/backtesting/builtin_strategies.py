from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aqos.backtesting.contracts import BacktestBar


BACKTEST_BUILTIN_STRATEGIES_VERSION = "1.0"


@dataclass(frozen=True)
class CloseMomentumStrategyConfig:
    lookback_bars: int = 1
    min_return_fraction: float = 0.001
    stop_loss_points: float = 10.0
    take_profit_points: float = 20.0
    confidence: float = 0.65

    def __post_init__(self) -> None:
        if self.lookback_bars < 1:
            raise ValueError("lookback_bars must be at least 1.")

        if self.min_return_fraction < 0:
            raise ValueError("min_return_fraction cannot be negative.")

        if self.stop_loss_points <= 0:
            raise ValueError("stop_loss_points must be positive.")

        if self.take_profit_points <= 0:
            raise ValueError("take_profit_points must be positive.")

        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1.")


@dataclass(frozen=True)
class CloseMomentumRuleStrategy:
    config: CloseMomentumStrategyConfig = CloseMomentumStrategyConfig()
    strategy_name: str = "close_momentum"

    def generate_signal(
        self,
        bar: BacktestBar,
        history: tuple[BacktestBar, ...],
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if len(history) < self.config.lookback_bars:
            return {
                "action": "hold",
                "source": self.strategy_name,
                "metadata": {
                    "reason": "Not enough history.",
                    "history_size": len(history),
                    "required_history": self.config.lookback_bars,
                },
            }

        reference_bar = history[-self.config.lookback_bars]
        return_fraction = (bar.close - reference_bar.close) / reference_bar.close

        if return_fraction >= self.config.min_return_fraction:
            return {
                "action": "buy",
                "confidence": self.config.confidence,
                "stop_loss": bar.close - self.config.stop_loss_points,
                "take_profit": bar.close + self.config.take_profit_points,
                "source": self.strategy_name,
                "metadata": {
                    "reason": "Close momentum bullish.",
                    "return_fraction": return_fraction,
                    "lookback_bars": self.config.lookback_bars,
                },
            }

        if return_fraction <= -self.config.min_return_fraction:
            return {
                "action": "sell",
                "confidence": self.config.confidence,
                "stop_loss": bar.close + self.config.stop_loss_points,
                "take_profit": bar.close - self.config.take_profit_points,
                "source": self.strategy_name,
                "metadata": {
                    "reason": "Close momentum bearish.",
                    "return_fraction": return_fraction,
                    "lookback_bars": self.config.lookback_bars,
                },
            }

        return {
            "action": "hold",
            "source": self.strategy_name,
            "metadata": {
                "reason": "Momentum threshold not reached.",
                "return_fraction": return_fraction,
                "lookback_bars": self.config.lookback_bars,
            },
        }


def normalize_builtin_rule_strategy_name(strategy_name: str) -> str:
    clean_name = strategy_name.strip().lower().replace("-", "_")

    aliases = {
        "close_momentum": "close_momentum",
        "momentum": "close_momentum",
        "close_direction": "close_momentum",
    }

    if clean_name not in aliases:
        raise ValueError(f"Unsupported built-in rule strategy: {strategy_name}")

    return aliases[clean_name]


def list_builtin_rule_strategy_names() -> tuple[str, ...]:
    return ("close_momentum",)


def build_builtin_rule_strategy(
    strategy_name: str,
    *,
    lookback_bars: int = 1,
    min_return_fraction: float = 0.001,
    stop_loss_points: float = 10.0,
    take_profit_points: float = 20.0,
    confidence: float = 0.65,
):
    normalized_name = normalize_builtin_rule_strategy_name(strategy_name)

    if normalized_name == "close_momentum":
        return CloseMomentumRuleStrategy(
            config=CloseMomentumStrategyConfig(
                lookback_bars=lookback_bars,
                min_return_fraction=min_return_fraction,
                stop_loss_points=stop_loss_points,
                take_profit_points=take_profit_points,
                confidence=confidence,
            )
        )

    raise ValueError(f"Unsupported built-in rule strategy: {strategy_name}")


__all__ = [
    "BACKTEST_BUILTIN_STRATEGIES_VERSION",
    "CloseMomentumRuleStrategy",
    "CloseMomentumStrategyConfig",
    "build_builtin_rule_strategy",
    "list_builtin_rule_strategy_names",
    "normalize_builtin_rule_strategy_name",
]