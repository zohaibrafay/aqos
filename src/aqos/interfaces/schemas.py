"""
Interface schemas.

Defines lightweight request and response schemas used by AQOS
application-facing interfaces such as API, CLI, dashboard, and agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class MarketDataRequest:
    """
    Request schema for market data access.
    """

    symbol: str
    timeframe: str
    limit: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.symbol, "Symbol")
        _validate_non_empty_string(self.timeframe, "Timeframe")

        if self.limit is not None:
            _validate_positive_integer(self.limit, "Limit")


@dataclass(slots=True, frozen=True)
class PredictionRequest:
    """
    Request schema for model prediction.
    """

    model_name: str
    features: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.model_name, "Model name")
        _validate_non_empty_list(self.features, "Features")


@dataclass(slots=True, frozen=True)
class PredictionResponse:
    """
    Response schema for model prediction.
    """

    model_name: str
    predictions: list[Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.model_name, "Model name")
        _validate_non_empty_list(self.predictions, "Predictions")


@dataclass(slots=True, frozen=True)
class StrategyRequest:
    """
    Request schema for strategy decision generation.
    """

    market_state: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_dict(self.market_state, "Market state")


@dataclass(slots=True, frozen=True)
class StrategyResponse:
    """
    Response schema for strategy decision generation.
    """

    signal: str
    should_enter: bool
    should_exit: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_signal(self.signal)
        _validate_boolean(self.should_enter, "Should enter")
        _validate_boolean(self.should_exit, "Should exit")


@dataclass(slots=True, frozen=True)
class RiskRequest:
    """
    Request schema for risk assessment.
    """

    trade_request: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_dict(self.trade_request, "Trade request")


@dataclass(slots=True, frozen=True)
class RiskResponse:
    """
    Response schema for risk assessment.
    """

    allowed: bool
    reason: str
    position_size: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_boolean(self.allowed, "Allowed")
        _validate_non_empty_string(self.reason, "Reason")

        if self.position_size is not None:
            _validate_positive_number(self.position_size, "Position size")


@dataclass(slots=True, frozen=True)
class BacktestRequest:
    """
    Request schema for backtest execution.
    """

    name: str
    profits: list[float]
    initial_balance: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.name, "Backtest name")
        _validate_non_empty_list(self.profits, "Profits")
        _validate_positive_number(self.initial_balance, "Initial balance")


@dataclass(slots=True, frozen=True)
class BacktestResponse:
    """
    Response schema for backtest execution.
    """

    name: str
    total_profit: float
    final_balance: float
    win_rate: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.name, "Backtest name")
        _validate_number(self.total_profit, "Total profit")
        _validate_positive_number(self.final_balance, "Final balance")
        _validate_ratio(self.win_rate, "Win rate")


@dataclass(slots=True, frozen=True)
class ExperimentRequest:
    """
    Request schema for experiment creation.
    """

    name: str
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.name, "Experiment name")


@dataclass(slots=True, frozen=True)
class ExperimentResponse:
    """
    Response schema for experiment status/result output.
    """

    name: str
    status: str
    results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_non_empty_string(self.name, "Experiment name")
        _validate_experiment_status(self.status)


@dataclass(slots=True, frozen=True)
class InterfaceEnvelope:
    """
    Generic interface response envelope.
    """

    success: bool
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_boolean(self.success, "Success")
        _validate_non_empty_string(self.message, "Message")


def _validate_non_empty_string(
    value: str,
    name: str,
) -> None:
    """
    Validate non-empty string.
    """

    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string.")

    if not value:
        raise ValueError(f"{name} cannot be empty.")


def _validate_non_empty_list(
    value: list,
    name: str,
) -> None:
    """
    Validate non-empty list.
    """

    if not isinstance(value, list):
        raise TypeError(f"{name} must be a list.")

    if not value:
        raise ValueError(f"{name} cannot be empty.")


def _validate_non_empty_dict(
    value: dict,
    name: str,
) -> None:
    """
    Validate non-empty dictionary.
    """

    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dictionary.")

    if not value:
        raise ValueError(f"{name} cannot be empty.")


def _validate_boolean(
    value: bool,
    name: str,
) -> None:
    """
    Validate boolean.
    """

    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean.")


def _validate_number(
    value: float,
    name: str,
) -> None:
    """
    Validate numeric value.
    """

    if not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric.")


def _validate_positive_number(
    value: float,
    name: str,
) -> None:
    """
    Validate positive numeric value.
    """

    _validate_number(value, name)

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _validate_positive_integer(
    value: int,
    name: str,
) -> None:
    """
    Validate positive integer.
    """

    if not isinstance(value, int):
        raise TypeError(f"{name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")


def _validate_ratio(
    value: float,
    name: str,
) -> None:
    """
    Validate ratio between 0 and 1.
    """

    _validate_number(value, name)

    if value < 0 or value > 1:
        raise ValueError(f"{name} must be between 0 and 1.")


def _validate_signal(
    signal: str,
) -> None:
    """
    Validate strategy signal.
    """

    if signal not in {"buy", "sell", "hold"}:
        raise ValueError("Signal must be buy, sell, or hold.")


def _validate_experiment_status(
    status: str,
) -> None:
    """
    Validate experiment status.
    """

    if status not in {"created", "running", "completed", "failed"}:
        raise ValueError(
            "Experiment status must be created, running, completed, or failed."
        )


__all__ = [
    "BacktestRequest",
    "BacktestResponse",
    "ExperimentRequest",
    "ExperimentResponse",
    "InterfaceEnvelope",
    "MarketDataRequest",
    "PredictionRequest",
    "PredictionResponse",
    "RiskRequest",
    "RiskResponse",
    "StrategyRequest",
    "StrategyResponse",
]