from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any, Mapping

from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestSignal,
    BacktestSignalAction,
)
from aqos.backtesting.signal_adapter import (
    build_hold_signal_for_bar,
    normalize_adapter_signal_action,
)


BACKTEST_STRATEGY_OUTPUT_MAPPER_VERSION = "1.0"


class StrategyOutputField(str, Enum):
    ACTION = "action"
    CONFIDENCE = "confidence"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIMESTAMP = "timestamp"
    SYMBOL = "symbol"
    SOURCE = "source"
    METADATA = "metadata"


@dataclass(frozen=True)
class StrategyOutputMappingConfig:
    action_fields: tuple[str, ...] = (
        "action",
        "signal",
        "signal_action",
        "side",
        "direction",
        "recommendation",
        "trade_action",
    )
    confidence_fields: tuple[str, ...] = (
        "confidence",
        "probability",
        "score",
        "signal_confidence",
    )
    stop_loss_fields: tuple[str, ...] = (
        "stop_loss",
        "sl",
        "stop_loss_price",
    )
    take_profit_fields: tuple[str, ...] = (
        "take_profit",
        "tp",
        "take_profit_price",
    )
    timestamp_fields: tuple[str, ...] = (
        "timestamp",
        "time",
        "created_at",
        "signal_time",
    )
    symbol_fields: tuple[str, ...] = (
        "symbol",
        "pair",
        "instrument",
    )
    source_fields: tuple[str, ...] = (
        "source",
        "strategy",
        "strategy_name",
        "name",
    )
    metadata_fields: tuple[str, ...] = (
        "metadata",
        "meta",
        "context",
    )
    default_source: str = "strategy_output_mapper"
    default_confidence: float | None = None

    def __post_init__(self) -> None:
        if not self.default_source.strip():
            raise ValueError("default_source cannot be empty.")

        if self.default_confidence is not None and not 0.0 <= self.default_confidence <= 1.0:
            raise ValueError("default_confidence must be between 0 and 1.")


@dataclass(frozen=True)
class StrategyOutputMappingResult:
    signal: BacktestSignal
    source_type: str
    mapped_fields: dict[str, str] = dataclass_field(default_factory=dict)
    raw_summary: dict[str, Any] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal": self.signal.to_dict(),
            "source_type": self.source_type,
            "mapped_fields": self.mapped_fields,
            "raw_summary": self.raw_summary,
        }


def get_mapping_value(
    payload: Mapping[str, Any],
    keys: tuple[str, ...],
) -> tuple[Any, str | None]:
    for key in keys:
        if key in payload:
            return payload[key], key

    return None, None


def get_object_value(
    output: Any,
    keys: tuple[str, ...],
) -> tuple[Any, str | None]:
    for key in keys:
        if hasattr(output, key):
            return getattr(output, key), key

    return None, None


def optional_float(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, str) and not value.strip():
        return None

    return float(value)


def normalize_strategy_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}

    if isinstance(value, dict):
        return value

    raise ValueError("strategy output metadata must be a dictionary.")


def build_strategy_signal_from_values(
    *,
    bar: BacktestBar,
    action: Any,
    confidence: Any = None,
    stop_loss: Any = None,
    take_profit: Any = None,
    timestamp: Any = None,
    symbol: Any = None,
    source: Any = None,
    metadata: Any = None,
    config: StrategyOutputMappingConfig,
) -> BacktestSignal:
    resolved_confidence = optional_float(confidence)

    if resolved_confidence is None:
        resolved_confidence = config.default_confidence

    return BacktestSignal(
        timestamp=str(timestamp if timestamp is not None else bar.timestamp),
        symbol=str(symbol if symbol is not None else bar.symbol),
        action=normalize_adapter_signal_action(action),
        confidence=resolved_confidence,
        source=str(source if source is not None else config.default_source),
        stop_loss=optional_float(stop_loss),
        take_profit=optional_float(take_profit),
        metadata=normalize_strategy_metadata(metadata),
    )


def map_mapping_strategy_output_to_signal(
    payload: Mapping[str, Any],
    bar: BacktestBar,
    config: StrategyOutputMappingConfig,
) -> StrategyOutputMappingResult:
    mapped_fields: dict[str, str] = {}

    action, action_key = get_mapping_value(payload, config.action_fields)
    confidence, confidence_key = get_mapping_value(payload, config.confidence_fields)
    stop_loss, stop_loss_key = get_mapping_value(payload, config.stop_loss_fields)
    take_profit, take_profit_key = get_mapping_value(payload, config.take_profit_fields)
    timestamp, timestamp_key = get_mapping_value(payload, config.timestamp_fields)
    symbol, symbol_key = get_mapping_value(payload, config.symbol_fields)
    source, source_key = get_mapping_value(payload, config.source_fields)
    metadata, metadata_key = get_mapping_value(payload, config.metadata_fields)

    for output_field, key in (
        (StrategyOutputField.ACTION, action_key),
        (StrategyOutputField.CONFIDENCE, confidence_key),
        (StrategyOutputField.STOP_LOSS, stop_loss_key),
        (StrategyOutputField.TAKE_PROFIT, take_profit_key),
        (StrategyOutputField.TIMESTAMP, timestamp_key),
        (StrategyOutputField.SYMBOL, symbol_key),
        (StrategyOutputField.SOURCE, source_key),
        (StrategyOutputField.METADATA, metadata_key),
    ):
        if key is not None:
            mapped_fields[output_field.value] = key

    signal = build_strategy_signal_from_values(
        bar=bar,
        action=action,
        confidence=confidence,
        stop_loss=stop_loss,
        take_profit=take_profit,
        timestamp=timestamp,
        symbol=symbol,
        source=source,
        metadata=metadata,
        config=config,
    )

    return StrategyOutputMappingResult(
        signal=signal,
        source_type="mapping",
        mapped_fields=mapped_fields,
        raw_summary={"keys": sorted(str(key) for key in payload.keys())},
    )


def map_object_strategy_output_to_signal(
    output: Any,
    bar: BacktestBar,
    config: StrategyOutputMappingConfig,
) -> StrategyOutputMappingResult:
    mapped_fields: dict[str, str] = {}

    action, action_key = get_object_value(output, config.action_fields)
    confidence, confidence_key = get_object_value(output, config.confidence_fields)
    stop_loss, stop_loss_key = get_object_value(output, config.stop_loss_fields)
    take_profit, take_profit_key = get_object_value(output, config.take_profit_fields)
    timestamp, timestamp_key = get_object_value(output, config.timestamp_fields)
    symbol, symbol_key = get_object_value(output, config.symbol_fields)
    source, source_key = get_object_value(output, config.source_fields)
    metadata, metadata_key = get_object_value(output, config.metadata_fields)

    for output_field, key in (
        (StrategyOutputField.ACTION, action_key),
        (StrategyOutputField.CONFIDENCE, confidence_key),
        (StrategyOutputField.STOP_LOSS, stop_loss_key),
        (StrategyOutputField.TAKE_PROFIT, take_profit_key),
        (StrategyOutputField.TIMESTAMP, timestamp_key),
        (StrategyOutputField.SYMBOL, symbol_key),
        (StrategyOutputField.SOURCE, source_key),
        (StrategyOutputField.METADATA, metadata_key),
    ):
        if key is not None:
            mapped_fields[output_field.value] = key

    signal = build_strategy_signal_from_values(
        bar=bar,
        action=action,
        confidence=confidence,
        stop_loss=stop_loss,
        take_profit=take_profit,
        timestamp=timestamp,
        symbol=symbol,
        source=source,
        metadata=metadata,
        config=config,
    )

    return StrategyOutputMappingResult(
        signal=signal,
        source_type="object",
        mapped_fields=mapped_fields,
        raw_summary={"class_name": type(output).__name__},
    )


def map_strategy_output_to_backtest_signal(
    output: Any,
    bar: BacktestBar,
    config: StrategyOutputMappingConfig | None = None,
) -> StrategyOutputMappingResult:
    mapping_config = config or StrategyOutputMappingConfig()

    if isinstance(output, BacktestSignal):
        return StrategyOutputMappingResult(
            signal=output,
            source_type="backtest_signal",
            mapped_fields={},
            raw_summary={"class_name": type(output).__name__},
        )

    if output is None:
        return StrategyOutputMappingResult(
            signal=build_hold_signal_for_bar(
                bar=bar,
                source=mapping_config.default_source,
                reason="Strategy output was None.",
            ),
            source_type="none",
            mapped_fields={},
            raw_summary={},
        )

    if isinstance(output, Mapping):
        return map_mapping_strategy_output_to_signal(
            payload=output,
            bar=bar,
            config=mapping_config,
        )

    if isinstance(output, str):
        signal = build_strategy_signal_from_values(
            bar=bar,
            action=output,
            config=mapping_config,
        )

        return StrategyOutputMappingResult(
            signal=signal,
            source_type="string",
            mapped_fields={"action": "string_value"},
            raw_summary={"value": output},
        )

    return map_object_strategy_output_to_signal(
        output=output,
        bar=bar,
        config=mapping_config,
    )


__all__ = [
    "BACKTEST_STRATEGY_OUTPUT_MAPPER_VERSION",
    "StrategyOutputField",
    "StrategyOutputMappingConfig",
    "StrategyOutputMappingResult",
    "build_strategy_signal_from_values",
    "get_mapping_value",
    "get_object_value",
    "map_mapping_strategy_output_to_signal",
    "map_object_strategy_output_to_signal",
    "map_strategy_output_to_backtest_signal",
    "normalize_strategy_metadata",
    "optional_float",
]