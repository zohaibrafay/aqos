from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestSignal,
    BacktestSignalAction,
)


BACKTEST_SIGNAL_ADAPTER_VERSION = "1.0"


class BacktestSignalAdapterType(str, Enum):
    CSV = "csv"
    RULE_BASED = "rule_based"
    ML_MODEL = "ml_model"
    CUSTOM = "custom"
    NOOP = "noop"


class BacktestSignalAdapterStatus(str, Enum):
    GENERATED = "generated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class BacktestSignalAdapterContext:
    bar: BacktestBar
    history: tuple[BacktestBar, ...] = ()
    index: int = 0
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("index cannot be negative.")

    @property
    def previous_bar(self) -> BacktestBar | None:
        if not self.history:
            return None

        return self.history[-1]

    @property
    def history_size(self) -> int:
        return len(self.history)

    def to_dict(self) -> dict[str, Any]:
        return {
            "bar": self.bar.to_dict(),
            "history_size": self.history_size,
            "index": self.index,
            "previous_bar": (
                self.previous_bar.to_dict() if self.previous_bar is not None else None
            ),
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class BacktestSignalAdapterResult:
    signal: BacktestSignal
    status: BacktestSignalAdapterStatus
    adapter_type: BacktestSignalAdapterType
    adapter_name: str
    reason: str | None = None
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("adapter_name cannot be empty.")

        if self.status == BacktestSignalAdapterStatus.FAILED and not self.reason:
            raise ValueError("reason is required when adapter status is failed.")

    @property
    def generated(self) -> bool:
        return self.status == BacktestSignalAdapterStatus.GENERATED

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal.to_dict(),
            "status": self.status.value,
            "adapter_type": self.adapter_type.value,
            "adapter_name": self.adapter_name,
            "reason": self.reason,
            "generated": self.generated,
            "metadata": self.metadata,
        }


@runtime_checkable
class BacktestSignalAdapter(Protocol):
    adapter_name: str
    adapter_type: BacktestSignalAdapterType

    def generate_signal(
        self,
        context: BacktestSignalAdapterContext,
    ) -> BacktestSignalAdapterResult:
        ...


@dataclass(frozen=True)
class NoOpBacktestSignalAdapter:
    adapter_name: str = "noop_backtest_signal_adapter"
    adapter_type: BacktestSignalAdapterType = BacktestSignalAdapterType.NOOP

    def generate_signal(
        self,
        context: BacktestSignalAdapterContext,
    ) -> BacktestSignalAdapterResult:
        signal = BacktestSignal(
            timestamp=context.bar.timestamp,
            symbol=context.bar.symbol,
            action=BacktestSignalAction.HOLD,
            source=self.adapter_name,
            metadata={
                "adapter_type": self.adapter_type.value,
                "reason": "No-op adapter always returns hold.",
            },
        )

        return BacktestSignalAdapterResult(
            signal=signal,
            status=BacktestSignalAdapterStatus.SKIPPED,
            adapter_type=self.adapter_type,
            adapter_name=self.adapter_name,
            reason="No-op adapter always returns hold.",
        )


def normalize_adapter_signal_action(value: Any) -> BacktestSignalAction:
    if value is None:
        return BacktestSignalAction.HOLD

    clean_value = str(value).strip().lower()

    if clean_value in {"", "none", "nan", "null"}:
        return BacktestSignalAction.HOLD

    aliases = {
        "buy": BacktestSignalAction.BUY,
        "long": BacktestSignalAction.BUY,
        "bullish": BacktestSignalAction.BUY,
        "sell": BacktestSignalAction.SELL,
        "short": BacktestSignalAction.SELL,
        "bearish": BacktestSignalAction.SELL,
        "hold": BacktestSignalAction.HOLD,
        "flat": BacktestSignalAction.HOLD,
        "neutral": BacktestSignalAction.HOLD,
        "exit": BacktestSignalAction.EXIT,
        "close": BacktestSignalAction.EXIT,
    }

    if clean_value not in aliases:
        raise ValueError(f"Unsupported backtest signal action: {value}")

    return aliases[clean_value]


def build_hold_signal_for_bar(
    bar: BacktestBar,
    source: str,
    reason: str | None = None,
) -> BacktestSignal:
    if not source.strip():
        raise ValueError("source cannot be empty.")

    metadata: dict[str, Any] = {}

    if reason is not None:
        metadata["reason"] = reason

    return BacktestSignal(
        timestamp=bar.timestamp,
        symbol=bar.symbol,
        action=BacktestSignalAction.HOLD,
        source=source,
        metadata=metadata,
    )


def build_adapter_result_from_signal(
    signal: BacktestSignal,
    adapter_name: str,
    adapter_type: BacktestSignalAdapterType,
    reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> BacktestSignalAdapterResult:
    status = (
        BacktestSignalAdapterStatus.SKIPPED
        if signal.action == BacktestSignalAction.HOLD
        else BacktestSignalAdapterStatus.GENERATED
    )

    return BacktestSignalAdapterResult(
        signal=signal,
        status=status,
        adapter_type=adapter_type,
        adapter_name=adapter_name,
        reason=reason,
        metadata=metadata or {},
    )


def build_failed_adapter_result(
    context: BacktestSignalAdapterContext,
    adapter_name: str,
    adapter_type: BacktestSignalAdapterType,
    reason: str,
    metadata: dict[str, Any] | None = None,
) -> BacktestSignalAdapterResult:
    if not reason.strip():
        raise ValueError("reason cannot be empty.")

    signal = build_hold_signal_for_bar(
        bar=context.bar,
        source=adapter_name,
        reason=reason,
    )

    return BacktestSignalAdapterResult(
        signal=signal,
        status=BacktestSignalAdapterStatus.FAILED,
        adapter_type=adapter_type,
        adapter_name=adapter_name,
        reason=reason,
        metadata=metadata or {},
    )


__all__ = [
    "BACKTEST_SIGNAL_ADAPTER_VERSION",
    "BacktestSignalAdapter",
    "BacktestSignalAdapterContext",
    "BacktestSignalAdapterResult",
    "BacktestSignalAdapterStatus",
    "BacktestSignalAdapterType",
    "NoOpBacktestSignalAdapter",
    "build_adapter_result_from_signal",
    "build_failed_adapter_result",
    "build_hold_signal_for_bar",
    "normalize_adapter_signal_action",
]