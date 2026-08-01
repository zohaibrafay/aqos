from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any, Callable, Protocol, runtime_checkable

from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestSignal,
    BacktestSignalAction,
)
from aqos.backtesting.signal_adapter import (
    BacktestSignalAdapterContext,
    BacktestSignalAdapterResult,
    BacktestSignalAdapterType,
    build_adapter_result_from_signal,
    build_failed_adapter_result,
    build_hold_signal_for_bar,
    normalize_adapter_signal_action,
)


BACKTEST_RULE_BASED_ADAPTER_VERSION = "1.0"


@runtime_checkable
class RuleBasedSignalStrategy(Protocol):
    strategy_name: str

    def generate_signal(
        self,
        bar: BacktestBar,
        history: tuple[BacktestBar, ...],
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        ...


RuleBasedStrategyCallable = Callable[
    [BacktestBar, tuple[BacktestBar, ...], dict[str, Any] | None],
    Any,
]


@dataclass(frozen=True)
class RuleBasedSignalAdapterConfig:
    adapter_name: str = "rule_based_signal_adapter"
    default_confidence: float | None = None
    fail_closed: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("adapter_name cannot be empty.")

        if self.default_confidence is not None and not 0.0 <= self.default_confidence <= 1.0:
            raise ValueError("default_confidence must be between 0 and 1.")


@dataclass(frozen=True)
class RuleBasedBacktestSignalAdapter:
    strategy: RuleBasedSignalStrategy | RuleBasedStrategyCallable
    config: RuleBasedSignalAdapterConfig = dataclass_field(
        default_factory=RuleBasedSignalAdapterConfig
    )
    adapter_type: BacktestSignalAdapterType = BacktestSignalAdapterType.RULE_BASED

    @property
    def adapter_name(self) -> str:
        return self.config.adapter_name

    def generate_signal(
        self,
        context: BacktestSignalAdapterContext,
    ) -> BacktestSignalAdapterResult:
        try:
            raw_signal = call_rule_based_strategy(
                strategy=self.strategy,
                context=context,
            )

            signal = convert_rule_based_output_to_backtest_signal(
                raw_signal=raw_signal,
                context=context,
                source=self.adapter_name,
                default_confidence=self.config.default_confidence,
            )

            return build_adapter_result_from_signal(
                signal=signal,
                adapter_name=self.adapter_name,
                adapter_type=self.adapter_type,
                metadata={
                    "strategy_type": type(self.strategy).__name__,
                    **self.config.metadata,
                },
            )
        except Exception as exc:
            if self.config.fail_closed:
                return build_failed_adapter_result(
                    context=context,
                    adapter_name=self.adapter_name,
                    adapter_type=self.adapter_type,
                    reason=str(exc),
                    metadata={
                        "strategy_type": type(self.strategy).__name__,
                        **self.config.metadata,
                    },
                )

            raise


def call_rule_based_strategy(
    strategy: RuleBasedSignalStrategy | RuleBasedStrategyCallable,
    context: BacktestSignalAdapterContext,
) -> Any:
    if hasattr(strategy, "generate_signal"):
        return strategy.generate_signal(
            bar=context.bar,
            history=context.history,
            metadata=context.metadata,
        )

    return strategy(
        context.bar,
        context.history,
        context.metadata,
    )


def optional_float_from_mapping(
    payload: dict[str, Any],
    key: str,
) -> float | None:
    if key not in payload:
        return None

    value = payload[key]

    if value is None:
        return None

    return float(value)


def convert_mapping_to_backtest_signal(
    payload: dict[str, Any],
    context: BacktestSignalAdapterContext,
    source: str,
    default_confidence: float | None = None,
) -> BacktestSignal:
    action_value = payload.get("action", payload.get("signal", "hold"))
    action = normalize_adapter_signal_action(action_value)

    confidence = optional_float_from_mapping(payload, "confidence")

    if confidence is None:
        confidence = default_confidence

    stop_loss = optional_float_from_mapping(payload, "stop_loss")
    take_profit = optional_float_from_mapping(payload, "take_profit")

    metadata = payload.get("metadata", {})

    if metadata is None:
        metadata = {}

    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dictionary when provided.")

    return BacktestSignal(
        timestamp=str(payload.get("timestamp", context.bar.timestamp)),
        symbol=str(payload.get("symbol", context.bar.symbol)),
        action=action,
        confidence=confidence,
        source=str(payload.get("source", source)),
        stop_loss=stop_loss,
        take_profit=take_profit,
        metadata=metadata,
    )


def convert_rule_based_output_to_backtest_signal(
    raw_signal: Any,
    context: BacktestSignalAdapterContext,
    source: str,
    default_confidence: float | None = None,
) -> BacktestSignal:
    if isinstance(raw_signal, BacktestSignal):
        return raw_signal

    if raw_signal is None:
        return build_hold_signal_for_bar(
            bar=context.bar,
            source=source,
            reason="Rule-based strategy returned no signal.",
        )

    if isinstance(raw_signal, dict):
        return convert_mapping_to_backtest_signal(
            payload=raw_signal,
            context=context,
            source=source,
            default_confidence=default_confidence,
        )

    action = normalize_adapter_signal_action(raw_signal)

    return BacktestSignal(
        timestamp=context.bar.timestamp,
        symbol=context.bar.symbol,
        action=action,
        confidence=default_confidence,
        source=source,
    )


__all__ = [
    "BACKTEST_RULE_BASED_ADAPTER_VERSION",
    "RuleBasedBacktestSignalAdapter",
    "RuleBasedSignalAdapterConfig",
    "RuleBasedSignalStrategy",
    "RuleBasedStrategyCallable",
    "call_rule_based_strategy",
    "convert_mapping_to_backtest_signal",
    "convert_rule_based_output_to_backtest_signal",
    "optional_float_from_mapping",
]