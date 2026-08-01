from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from typing import Any

import pandas as pd

from aqos.backtesting.contracts import (
    BacktestBar,
    BacktestSignal,
    BacktestSignalAction,
)
from aqos.backtesting.signal_adapter import (
    BacktestSignalAdapterContext,
    BacktestSignalAdapterResult,
    BacktestSignalAdapterStatus,
    BacktestSignalAdapterType,
    build_adapter_result_from_signal,
    build_failed_adapter_result,
    build_hold_signal_for_bar,
    normalize_adapter_signal_action,
)
from aqos.model_training.baseline_signal_model import BaselineSignalModel
from aqos.model_training.ohlcv_feature_builder import (
    OHLCVFeatureBuilderConfig,
    build_ohlcv_ml_features,
)


BACKTEST_MODEL_SIGNAL_ADAPTER_VERSION = "1.0"


@dataclass(frozen=True)
class ModelSignalAdapterConfig:
    adapter_name: str = "model_backtest_signal_adapter"
    min_confidence: float = 0.0
    warmup_bars: int = 1
    stop_loss_points: float | None = None
    take_profit_points: float | None = None
    allow_short: bool = True
    include_probabilities: bool = True
    fail_closed: bool = True
    timestamp_column: str = "timestamp"
    model_identity: dict[str, Any] = dataclass_field(default_factory=dict)
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.adapter_name.strip():
            raise ValueError("adapter_name cannot be empty.")

        if not 0.0 <= self.min_confidence <= 1.0:
            raise ValueError("min_confidence must be between 0 and 1.")

        if self.warmup_bars < 0:
            raise ValueError("warmup_bars cannot be negative.")

        if self.stop_loss_points is not None and self.stop_loss_points <= 0:
            raise ValueError("stop_loss_points must be positive.")

        if self.take_profit_points is not None and self.take_profit_points <= 0:
            raise ValueError("take_profit_points must be positive.")

    def feature_builder_config(self) -> OHLCVFeatureBuilderConfig:
        return OHLCVFeatureBuilderConfig(timestamp_column=self.timestamp_column)

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_name": self.adapter_name,
            "min_confidence": self.min_confidence,
            "warmup_bars": self.warmup_bars,
            "stop_loss_points": self.stop_loss_points,
            "take_profit_points": self.take_profit_points,
            "allow_short": self.allow_short,
            "include_probabilities": self.include_probabilities,
            "fail_closed": self.fail_closed,
            "timestamp_column": self.timestamp_column,
            "model_identity": self.model_identity,
            "metadata": self.metadata,
        }


def bars_to_ohlcv_dataframe(
    bars: tuple[BacktestBar, ...],
    timestamp_column: str = "timestamp",
) -> pd.DataFrame:
    if not bars:
        raise ValueError("bars cannot be empty.")

    rows = [
        {
            timestamp_column: bar.timestamp,
            "symbol": bar.symbol,
            "timeframe": bar.timeframe,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": float(bar.volume),
        }
        for bar in bars
    ]

    return pd.DataFrame(rows)


def build_model_feature_frame(
    bars: tuple[BacktestBar, ...],
    config: ModelSignalAdapterConfig | None = None,
) -> pd.DataFrame:
    active_config = config or ModelSignalAdapterConfig()

    return build_ohlcv_ml_features(
        bars_to_ohlcv_dataframe(bars, active_config.timestamp_column),
        config=active_config.feature_builder_config(),
    )


def build_model_feature_row(
    context: BacktestSignalAdapterContext,
    config: ModelSignalAdapterConfig | None = None,
) -> pd.DataFrame:
    """
    Build the single feature row for the current bar.

    Only the current bar and bars that came before it are used, so the row can
    never contain forward-looking information.
    """

    bars = tuple(context.history) + (context.bar,)
    features = build_model_feature_frame(bars, config=config)

    return features.iloc[[-1]].reset_index(drop=True)


def select_model_features(
    features: pd.DataFrame,
    feature_columns: tuple[str, ...],
) -> pd.DataFrame:
    if not feature_columns:
        raise ValueError("feature_columns cannot be empty.")

    missing = [column for column in feature_columns if column not in features.columns]

    if missing:
        raise ValueError(f"Model feature columns are missing from bar features: {missing}")

    return features.loc[:, list(feature_columns)]


def extract_model_confidence(
    probabilities: pd.DataFrame | None,
    predicted_label: str,
) -> float | None:
    if probabilities is None or probabilities.empty:
        return None

    column = f"probability_{predicted_label}"

    if column not in probabilities.columns:
        return None

    value = float(probabilities.iloc[0][column])

    return min(max(value, 0.0), 1.0)


def build_model_probability_payload(
    probabilities: pd.DataFrame | None,
) -> dict[str, float]:
    if probabilities is None or probabilities.empty:
        return {}

    return {
        str(column): float(probabilities.iloc[0][column])
        for column in probabilities.columns
    }


def resolve_model_signal_action(
    predicted_label: str,
    allow_short: bool,
) -> BacktestSignalAction:
    action = normalize_adapter_signal_action(predicted_label)

    if action == BacktestSignalAction.SELL and not allow_short:
        return BacktestSignalAction.HOLD

    return action


def resolve_model_exit_prices(
    action: BacktestSignalAction,
    close: float,
    stop_loss_points: float | None,
    take_profit_points: float | None,
) -> tuple[float | None, float | None]:
    if action == BacktestSignalAction.BUY:
        stop_loss = close - stop_loss_points if stop_loss_points is not None else None
        take_profit = close + take_profit_points if take_profit_points is not None else None
    elif action == BacktestSignalAction.SELL:
        stop_loss = close + stop_loss_points if stop_loss_points is not None else None
        take_profit = close - take_profit_points if take_profit_points is not None else None
    else:
        return None, None

    if stop_loss is not None and stop_loss <= 0:
        stop_loss = None

    if take_profit is not None and take_profit <= 0:
        take_profit = None

    return stop_loss, take_profit


def build_model_signal_metadata(
    config: ModelSignalAdapterConfig,
    context: BacktestSignalAdapterContext,
    predicted_label: str,
    probabilities: dict[str, float],
    reason: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "adapter_type": BacktestSignalAdapterType.ML_MODEL.value,
        "predicted_label": predicted_label,
        "bar_index": context.index,
        "history_size": context.history_size,
        "warmup_bars": config.warmup_bars,
        "min_confidence": config.min_confidence,
        **config.model_identity,
        **config.metadata,
    }

    if probabilities:
        metadata["probabilities"] = probabilities

    if reason is not None:
        metadata["reason"] = reason

    return metadata


def build_model_backtest_signal(
    config: ModelSignalAdapterConfig,
    context: BacktestSignalAdapterContext,
    predicted_label: str,
    confidence: float | None,
    probabilities: dict[str, float],
    reason: str | None = None,
    action: BacktestSignalAction | None = None,
) -> BacktestSignal:
    resolved_action = action or resolve_model_signal_action(
        predicted_label,
        config.allow_short,
    )

    stop_loss, take_profit = resolve_model_exit_prices(
        action=resolved_action,
        close=context.bar.close,
        stop_loss_points=config.stop_loss_points,
        take_profit_points=config.take_profit_points,
    )

    return BacktestSignal(
        timestamp=context.bar.timestamp,
        symbol=context.bar.symbol,
        action=resolved_action,
        confidence=confidence,
        source=config.adapter_name,
        stop_loss=stop_loss,
        take_profit=take_profit,
        metadata=build_model_signal_metadata(
            config=config,
            context=context,
            predicted_label=predicted_label,
            probabilities=probabilities,
            reason=reason,
        ),
    )


@dataclass(frozen=True)
class ModelBacktestSignalAdapter:
    """
    Backtest signal adapter driven by a trained AQOS signal model.

    Promotion enforcement lives in ``aqos.backtesting.model_promotion_guard``;
    this adapter only executes the model it is handed.
    """

    model: BaselineSignalModel
    config: ModelSignalAdapterConfig = dataclass_field(
        default_factory=ModelSignalAdapterConfig
    )
    adapter_type: BacktestSignalAdapterType = BacktestSignalAdapterType.ML_MODEL

    @property
    def adapter_name(self) -> str:
        return self.config.adapter_name

    def generate_signal(
        self,
        context: BacktestSignalAdapterContext,
    ) -> BacktestSignalAdapterResult:
        try:
            return self._generate_signal(context)
        except Exception as exc:
            if self.config.fail_closed:
                return build_failed_adapter_result(
                    context=context,
                    adapter_name=self.adapter_name,
                    adapter_type=self.adapter_type,
                    reason=str(exc),
                    metadata={
                        "model_name": self.model.model_name,
                        **self.config.model_identity,
                    },
                )

            raise

    def _generate_signal(
        self,
        context: BacktestSignalAdapterContext,
    ) -> BacktestSignalAdapterResult:
        if context.history_size < self.config.warmup_bars:
            reason = "Insufficient history for model warmup."
            return BacktestSignalAdapterResult(
                signal=build_hold_signal_for_bar(
                    bar=context.bar,
                    source=self.adapter_name,
                    reason=reason,
                ),
                status=BacktestSignalAdapterStatus.SKIPPED,
                adapter_type=self.adapter_type,
                adapter_name=self.adapter_name,
                reason=reason,
                metadata={
                    "warmup_bars": self.config.warmup_bars,
                    "history_size": context.history_size,
                    **self.config.model_identity,
                },
            )

        features = build_model_feature_row(context, config=self.config)
        model_features = select_model_features(features, self.model.feature_columns)

        predictions = self.model.predict(model_features)
        predicted_label = str(predictions.iloc[0])

        probabilities_frame = (
            self.model.predict_proba(model_features)
            if self.config.include_probabilities
            else None
        )
        probabilities = build_model_probability_payload(probabilities_frame)
        confidence = extract_model_confidence(probabilities_frame, predicted_label)

        below_threshold = (
            confidence is not None and confidence < self.config.min_confidence
        )

        reason = (
            "Model confidence below configured threshold."
            if below_threshold
            else None
        )

        action = (
            BacktestSignalAction.HOLD
            if below_threshold
            else resolve_model_signal_action(predicted_label, self.config.allow_short)
        )

        signal = build_model_backtest_signal(
            config=self.config,
            context=context,
            predicted_label=predicted_label,
            confidence=confidence,
            probabilities=probabilities,
            reason=reason,
            action=action,
        )

        return build_adapter_result_from_signal(
            signal=signal,
            adapter_name=self.adapter_name,
            adapter_type=self.adapter_type,
            reason=reason,
            metadata={
                "model_name": self.model.model_name,
                "predicted_label": predicted_label,
                "confidence": confidence,
                **self.config.model_identity,
            },
        )


def load_model_backtest_signal_adapter(
    model_path: str | Path,
    config: ModelSignalAdapterConfig | None = None,
) -> ModelBacktestSignalAdapter:
    path = Path(model_path)

    if not path.exists():
        raise FileNotFoundError(f"Backtest model artifact does not exist: {path}")

    model = BaselineSignalModel.load(path)

    if not model.is_trained:
        raise ValueError(f"Backtest model artifact is not trained: {path}")

    return ModelBacktestSignalAdapter(
        model=model,
        config=config or ModelSignalAdapterConfig(),
    )


__all__ = [
    "BACKTEST_MODEL_SIGNAL_ADAPTER_VERSION",
    "ModelBacktestSignalAdapter",
    "ModelSignalAdapterConfig",
    "bars_to_ohlcv_dataframe",
    "build_model_backtest_signal",
    "build_model_feature_frame",
    "build_model_feature_row",
    "build_model_probability_payload",
    "build_model_signal_metadata",
    "extract_model_confidence",
    "load_model_backtest_signal_adapter",
    "resolve_model_exit_prices",
    "resolve_model_signal_action",
    "select_model_features",
]
