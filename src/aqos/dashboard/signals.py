"""
AQOS signal and strategy dashboard payloads.

This module prepares frontend-ready signal, strategy, confidence, and strategy
summary widgets/cards/payloads for dashboards and external clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.dashboard.base import (
    DashboardPayload,
    DashboardStatus,
    build_dashboard_component,
    build_dashboard_issue,
    build_dashboard_metric,
    build_dashboard_payload,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_number,
    validate_string,
)
from aqos.dashboard.market import normalize_market_symbol
from aqos.dashboard.widgets import (
    DashboardCard,
    DashboardChartType,
    DashboardWidget,
    DashboardWidgetSize,
    DashboardWidgetType,
    build_dashboard_card,
    build_dashboard_chart_series,
    build_dashboard_table_column,
    build_dashboard_widget,
    build_dashboard_widget_action,
    card_to_dashboard_component,
    widget_to_dashboard_component,
)


class SignalDirection(str, Enum):
    """Supported signal directions."""

    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    UNKNOWN = "unknown"


class SignalConfidenceLevel(str, Enum):
    """Supported signal confidence levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    UNKNOWN = "unknown"


class StrategyDashboardState(str, Enum):
    """Supported strategy dashboard states."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SignalDashboardItem:
    """Frontend-ready signal item."""

    signal_id: str
    symbol: str
    direction: SignalDirection | str
    confidence: float = 0.0
    strategy_name: str = ""
    timeframe: str = ""
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    risk_reward: float = 0.0
    generated_at: str = ""
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.signal_id, "Signal ID")
        normalize_market_symbol(self.symbol)
        normalize_signal_direction(self.direction)
        validate_confidence_score(self.confidence)
        validate_string(self.strategy_name, "Strategy name")
        validate_string(self.timeframe, "Timeframe")
        validate_non_negative_float(self.entry_price, "Entry price")
        validate_non_negative_float(self.stop_loss, "Stop loss")
        validate_non_negative_float(self.take_profit, "Take profit")
        validate_non_negative_float(self.risk_reward, "Risk reward")
        validate_string(self.generated_at, "Generated at")
        validate_string(self.reason, "Reason")
        validate_metadata(self.metadata, "Metadata")

    @property
    def confidence_level(self) -> SignalConfidenceLevel:
        """Return confidence level."""
        return infer_signal_confidence_level(self.confidence)

    @property
    def actionable(self) -> bool:
        """Return whether signal is actionable."""
        return normalize_signal_direction(self.direction) in {
            SignalDirection.BUY,
            SignalDirection.SELL,
        }

    @property
    def has_prices(self) -> bool:
        """Return whether signal has entry/SL/TP prices."""
        return self.entry_price > 0 and self.stop_loss > 0 and self.take_profit > 0

    def to_dict(self) -> dict[str, Any]:
        """Convert signal item into dictionary."""
        return {
            "signal_id": self.signal_id.strip(),
            "symbol": normalize_market_symbol(self.symbol),
            "direction": normalize_signal_direction(self.direction).value,
            "confidence": round(float(self.confidence), 6),
            "confidence_level": self.confidence_level.value,
            "strategy_name": self.strategy_name.strip(),
            "timeframe": self.timeframe.strip(),
            "entry_price": float(self.entry_price),
            "stop_loss": float(self.stop_loss),
            "take_profit": float(self.take_profit),
            "risk_reward": float(self.risk_reward),
            "generated_at": self.generated_at.strip(),
            "reason": self.reason.strip(),
            "actionable": self.actionable,
            "has_prices": self.has_prices,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class StrategyDashboardSnapshot:
    """Frontend-ready strategy dashboard snapshot."""

    strategy_id: str
    strategy_name: str
    state: StrategyDashboardState | str = StrategyDashboardState.UNKNOWN
    signals: list[SignalDashboardItem] = field(default_factory=list)
    win_rate: float = 0.0
    total_signals: int = 0
    active_signals: int = 0
    average_confidence: float = 0.0
    profit_factor: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.strategy_id, "Strategy ID")
        validate_non_empty_string(self.strategy_name, "Strategy name")
        normalize_strategy_dashboard_state(self.state)
        validate_signal_dashboard_items(self.signals)
        validate_percentage(self.win_rate, "Win rate")
        validate_non_negative_integer(self.total_signals, "Total signals")
        validate_non_negative_integer(self.active_signals, "Active signals")
        validate_percentage(self.average_confidence * 100, "Average confidence")
        validate_non_negative_float(self.profit_factor, "Profit factor")
        validate_number(self.sharpe_ratio, "Sharpe ratio")
        validate_non_negative_float(self.max_drawdown_pct, "Max drawdown percentage")
        validate_metadata(self.metadata, "Metadata")

    @property
    def signal_count(self) -> int:
        """Return signal count."""
        return len(self.signals)

    @property
    def latest_signal(self) -> SignalDashboardItem | None:
        """Return latest signal."""
        return self.signals[-1] if self.signals else None

    @property
    def healthy(self) -> bool:
        """Return whether strategy is healthy."""
        return normalize_strategy_dashboard_state(self.state) in {
            StrategyDashboardState.ACTIVE,
            StrategyDashboardState.TESTING,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert strategy snapshot into dictionary."""
        return {
            "strategy_id": self.strategy_id.strip(),
            "strategy_name": self.strategy_name.strip(),
            "state": normalize_strategy_dashboard_state(self.state).value,
            "healthy": self.healthy,
            "signals": [signal.to_dict() for signal in self.signals],
            "signal_count": self.signal_count,
            "win_rate": float(self.win_rate),
            "total_signals": self.total_signals,
            "active_signals": self.active_signals,
            "average_confidence": round(float(self.average_confidence), 6),
            "profit_factor": float(self.profit_factor),
            "sharpe_ratio": float(self.sharpe_ratio),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "latest_signal": self.latest_signal.to_dict() if self.latest_signal else None,
            "metadata": dict(self.metadata),
        }


def normalize_signal_direction(direction: SignalDirection | str) -> SignalDirection:
    """Normalize signal direction."""
    if isinstance(direction, SignalDirection):
        return direction

    normalized = validate_non_empty_string(direction, "Signal direction").lower()

    try:
        return SignalDirection(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SignalDirection)
        raise ValueError(
            f"Invalid signal direction '{direction}'. Valid directions: {valid}.",
        ) from exc


def normalize_signal_confidence_level(
    confidence_level: SignalConfidenceLevel | str,
) -> SignalConfidenceLevel:
    """Normalize signal confidence level."""
    if isinstance(confidence_level, SignalConfidenceLevel):
        return confidence_level

    normalized = validate_non_empty_string(confidence_level, "Signal confidence level").lower()

    try:
        return SignalConfidenceLevel(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in SignalConfidenceLevel)
        raise ValueError(
            f"Invalid signal confidence level '{confidence_level}'. Valid levels: {valid}.",
        ) from exc


def normalize_strategy_dashboard_state(
    state: StrategyDashboardState | str,
) -> StrategyDashboardState:
    """Normalize strategy dashboard state."""
    if isinstance(state, StrategyDashboardState):
        return state

    normalized = validate_non_empty_string(state, "Strategy state").lower()

    try:
        return StrategyDashboardState(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in StrategyDashboardState)
        raise ValueError(
            f"Invalid strategy state '{state}'. Valid states: {valid}.",
        ) from exc


def validate_confidence_score(confidence: float) -> float:
    """Validate confidence score from 0 to 1."""
    validate_number(confidence, "Confidence")

    if confidence < 0 or confidence > 1:
        raise ValueError("Confidence must be between 0 and 1.")

    return float(confidence)


def validate_percentage(value: float, field_name: str) -> float:
    """Validate percentage from 0 to 100."""
    validate_number(value, field_name)

    if value < 0 or value > 100:
        raise ValueError(f"{field_name} must be between 0 and 100.")

    return float(value)


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_signal_dashboard_items(
    signals: list[SignalDashboardItem],
) -> list[SignalDashboardItem]:
    """Validate signal dashboard items."""
    if not isinstance(signals, list):
        raise ValueError("Signals must be a list.")

    for signal in signals:
        if not isinstance(signal, SignalDashboardItem):
            raise ValueError("Signals must contain SignalDashboardItem objects.")

    return signals


def validate_strategy_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    """Validate raw strategy metrics dictionary."""
    validate_metadata(metrics, "Strategy metrics")
    return metrics


def infer_signal_confidence_level(confidence: float) -> SignalConfidenceLevel:
    """Infer confidence level from score."""
    validate_confidence_score(confidence)

    if confidence >= 0.75:
        return SignalConfidenceLevel.HIGH

    if confidence >= 0.45:
        return SignalConfidenceLevel.MEDIUM

    return SignalConfidenceLevel.LOW


def build_signal_dashboard_item(
    *,
    signal_id: str,
    symbol: str,
    direction: SignalDirection | str,
    confidence: float = 0.0,
    strategy_name: str = "",
    timeframe: str = "",
    entry_price: float = 0.0,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    risk_reward: float = 0.0,
    generated_at: str = "",
    reason: str = "",
    metadata: dict[str, Any] | None = None,
) -> SignalDashboardItem:
    """Build signal dashboard item."""
    return SignalDashboardItem(
        signal_id=signal_id,
        symbol=symbol,
        direction=direction,
        confidence=confidence,
        strategy_name=strategy_name,
        timeframe=timeframe,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        risk_reward=risk_reward,
        generated_at=generated_at,
        reason=reason,
        metadata=metadata or {},
    )


def signal_dict_to_dashboard_item(signal: dict[str, Any]) -> SignalDashboardItem:
    """Convert raw signal dictionary into dashboard item."""
    validate_metadata(signal, "Signal")

    return build_signal_dashboard_item(
        signal_id=str(signal.get("signal_id") or signal.get("id") or ""),
        symbol=str(signal["symbol"]),
        direction=str(signal.get("direction") or signal.get("side") or "unknown"),
        confidence=float(signal.get("confidence", 0.0) or 0.0),
        strategy_name=str(signal.get("strategy_name", "")),
        timeframe=str(signal.get("timeframe", "")),
        entry_price=float(signal.get("entry_price", signal.get("entry", 0.0)) or 0.0),
        stop_loss=float(signal.get("stop_loss", signal.get("sl", 0.0)) or 0.0),
        take_profit=float(signal.get("take_profit", signal.get("tp", 0.0)) or 0.0),
        risk_reward=float(signal.get("risk_reward", signal.get("rr", 0.0)) or 0.0),
        generated_at=str(signal.get("generated_at", "")),
        reason=str(signal.get("reason", "")),
        metadata=dict(signal.get("metadata", {})),
    )


def signal_dicts_to_dashboard_items(
    signals: list[dict[str, Any]],
) -> list[SignalDashboardItem]:
    """Convert raw signal dictionaries into dashboard items."""
    if not isinstance(signals, list):
        raise ValueError("Signals must be a list.")

    return [
        signal_dict_to_dashboard_item(signal)
        for signal in signals
    ]


def build_strategy_dashboard_snapshot(
    *,
    strategy_id: str,
    strategy_name: str,
    state: StrategyDashboardState | str = StrategyDashboardState.UNKNOWN,
    signals: list[SignalDashboardItem] | None = None,
    metrics: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> StrategyDashboardSnapshot:
    """Build strategy dashboard snapshot."""
    resolved_signals = signals or []
    resolved_metrics = validate_strategy_metrics(metrics or {})

    confidence_values = [
        signal.confidence
        for signal in resolved_signals
    ]

    return StrategyDashboardSnapshot(
        strategy_id=strategy_id,
        strategy_name=strategy_name,
        state=state,
        signals=resolved_signals,
        win_rate=float(resolved_metrics.get("win_rate", 0.0) or 0.0),
        total_signals=int(resolved_metrics.get("total_signals", len(resolved_signals)) or 0),
        active_signals=int(
            resolved_metrics.get(
                "active_signals",
                len([signal for signal in resolved_signals if signal.actionable]),
            )
            or 0,
        ),
        average_confidence=float(
            resolved_metrics.get(
                "average_confidence",
                round(sum(confidence_values) / len(confidence_values), 6)
                if confidence_values
                else 0.0,
            )
            or 0.0,
        ),
        profit_factor=float(resolved_metrics.get("profit_factor", 0.0) or 0.0),
        sharpe_ratio=float(resolved_metrics.get("sharpe_ratio", 0.0) or 0.0),
        max_drawdown_pct=float(resolved_metrics.get("max_drawdown_pct", 0.0) or 0.0),
        metadata=metadata or {},
    )


def signal_item_to_metrics(signal: SignalDashboardItem) -> list:
    """Convert signal into dashboard metrics."""
    if not isinstance(signal, SignalDashboardItem):
        raise ValueError("Signal must be SignalDashboardItem.")

    return [
        build_dashboard_metric(
            name="confidence",
            label="Confidence",
            value=round(signal.confidence * 100, 2),
            unit="%",
            status=DashboardStatus.READY if signal.actionable else DashboardStatus.WARNING,
            metadata={
                "confidence_level": signal.confidence_level.value,
            },
        ),
        build_dashboard_metric(
            name="risk_reward",
            label="Risk / Reward",
            value=round(signal.risk_reward, 4),
            status=DashboardStatus.READY if signal.risk_reward > 0 else DashboardStatus.EMPTY,
        ),
    ]


def build_latest_signal_widget(signal: SignalDashboardItem | None) -> DashboardWidget:
    """Build latest signal widget."""
    if signal is None:
        return build_dashboard_widget(
            widget_id="latest-signal-empty",
            title="Latest Signal",
            widget_type=DashboardWidgetType.SIGNAL,
            status=DashboardStatus.EMPTY,
            size=DashboardWidgetSize.MEDIUM,
            description="No latest signal is available.",
            issues=[
                build_dashboard_issue(
                    code="signal_empty",
                    message="No latest signal is available.",
                    severity="warning",
                    source="dashboard.signals",
                ),
            ],
        )

    if not isinstance(signal, SignalDashboardItem):
        raise ValueError("Signal must be SignalDashboardItem or None.")

    return build_dashboard_widget(
        widget_id=f"latest-signal-{signal.signal_id.strip()}",
        title="Latest Signal",
        widget_type=DashboardWidgetType.SIGNAL,
        status=DashboardStatus.READY if signal.actionable else DashboardStatus.WARNING,
        size=DashboardWidgetSize.MEDIUM,
        subtitle=f"{normalize_market_symbol(signal.symbol)} · {normalize_signal_direction(signal.direction).value}",
        description="Latest generated trading signal.",
        data=signal.to_dict(),
        metrics=signal_item_to_metrics(signal),
        actions=[
            build_dashboard_widget_action(
                action_id="open-signal",
                label="Open Signal",
                action_type="link",
                target=f"/signals/{signal.signal_id.strip()}",
            ),
        ],
        metadata={
            "symbol": normalize_market_symbol(signal.symbol),
            "direction": normalize_signal_direction(signal.direction).value,
        },
    )


def build_signal_confidence_widget(
    signals: list[SignalDashboardItem],
) -> DashboardWidget:
    """Build signal confidence widget."""
    validate_signal_dashboard_items(signals)

    if not signals:
        return build_dashboard_widget(
            widget_id="signal-confidence-empty",
            title="Signal Confidence",
            widget_type=DashboardWidgetType.SIGNAL,
            status=DashboardStatus.EMPTY,
            description="No signals available for confidence analysis.",
        )

    high_count = len([signal for signal in signals if signal.confidence_level == SignalConfidenceLevel.HIGH])
    medium_count = len([signal for signal in signals if signal.confidence_level == SignalConfidenceLevel.MEDIUM])
    low_count = len([signal for signal in signals if signal.confidence_level == SignalConfidenceLevel.LOW])
    average_confidence = round(sum(signal.confidence for signal in signals) / len(signals), 6)

    return build_dashboard_widget(
        widget_id="signal-confidence",
        title="Signal Confidence",
        widget_type=DashboardWidgetType.SIGNAL,
        status=DashboardStatus.READY,
        size=DashboardWidgetSize.MEDIUM,
        chart_type=DashboardChartType.PIE,
        metrics=[
            build_dashboard_metric(
                name="average_confidence",
                label="Average Confidence",
                value=round(average_confidence * 100, 2),
                unit="%",
            ),
            build_dashboard_metric(name="high_confidence", value=high_count),
            build_dashboard_metric(name="medium_confidence", value=medium_count),
            build_dashboard_metric(name="low_confidence", value=low_count),
        ],
        chart_series=[
            build_dashboard_chart_series(
                name="Confidence Levels",
                points=[
                    {"label": "High", "value": high_count},
                    {"label": "Medium", "value": medium_count},
                    {"label": "Low", "value": low_count},
                ],
                chart_type=DashboardChartType.PIE,
            ),
        ],
        metadata={
            "signal_count": len(signals),
        },
    )


def build_signal_table_widget(
    signals: list[SignalDashboardItem],
) -> DashboardWidget:
    """Build signal table widget."""
    validate_signal_dashboard_items(signals)

    columns = [
        build_dashboard_table_column(key="signal_id", label="Signal ID"),
        build_dashboard_table_column(key="symbol", label="Symbol"),
        build_dashboard_table_column(key="direction", label="Direction"),
        build_dashboard_table_column(key="confidence", label="Confidence", data_type="number"),
        build_dashboard_table_column(key="strategy_name", label="Strategy"),
        build_dashboard_table_column(key="timeframe", label="Timeframe"),
        build_dashboard_table_column(key="entry_price", label="Entry", data_type="number"),
        build_dashboard_table_column(key="stop_loss", label="Stop Loss", data_type="number"),
        build_dashboard_table_column(key="take_profit", label="Take Profit", data_type="number"),
        build_dashboard_table_column(key="risk_reward", label="R/R", data_type="number"),
    ]

    rows = [signal.to_dict() for signal in signals]

    return build_dashboard_widget(
        widget_id="signal-table",
        title="Signals",
        widget_type=DashboardWidgetType.SIGNAL,
        status=DashboardStatus.READY if rows else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.FULL,
        description="Generated trading signals.",
        table_columns=columns,
        table_rows=rows,
        metadata={
            "signal_count": len(rows),
        },
    )


def build_strategy_summary_widget(
    snapshot: StrategyDashboardSnapshot,
) -> DashboardWidget:
    """Build strategy summary widget."""
    if not isinstance(snapshot, StrategyDashboardSnapshot):
        raise ValueError("Snapshot must be StrategyDashboardSnapshot.")

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if normalize_strategy_dashboard_state(snapshot.state) == StrategyDashboardState.ERROR:
        status = DashboardStatus.ERROR

    return build_dashboard_widget(
        widget_id=f"strategy-summary-{snapshot.strategy_id.strip()}",
        title=f"{snapshot.strategy_name} Summary",
        widget_type=DashboardWidgetType.STRATEGY,
        status=status,
        size=DashboardWidgetSize.LARGE,
        description="Strategy performance and signal summary.",
        data=snapshot.to_dict(),
        metrics=[
            build_dashboard_metric(name="win_rate", label="Win Rate", value=snapshot.win_rate, unit="%"),
            build_dashboard_metric(name="total_signals", label="Total Signals", value=snapshot.total_signals),
            build_dashboard_metric(name="active_signals", label="Active Signals", value=snapshot.active_signals),
            build_dashboard_metric(
                name="average_confidence",
                label="Average Confidence",
                value=round(snapshot.average_confidence * 100, 2),
                unit="%",
            ),
            build_dashboard_metric(name="profit_factor", label="Profit Factor", value=snapshot.profit_factor),
            build_dashboard_metric(name="max_drawdown_pct", label="Max Drawdown", value=snapshot.max_drawdown_pct, unit="%"),
        ],
        metadata={
            "strategy_id": snapshot.strategy_id,
            "state": normalize_strategy_dashboard_state(snapshot.state).value,
        },
    )


def build_signal_strategy_card(
    snapshot: StrategyDashboardSnapshot,
) -> DashboardCard:
    """Build signal and strategy dashboard card."""
    if not isinstance(snapshot, StrategyDashboardSnapshot):
        raise ValueError("Snapshot must be StrategyDashboardSnapshot.")

    summary_widget = build_strategy_summary_widget(snapshot)
    latest_signal_widget = build_latest_signal_widget(snapshot.latest_signal)
    confidence_widget = build_signal_confidence_widget(snapshot.signals)
    table_widget = build_signal_table_widget(snapshot.signals)

    return build_dashboard_card(
        card_id=f"signal-strategy-card-{snapshot.strategy_id.strip()}",
        title=f"{snapshot.strategy_name} Signals",
        status=DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING,
        subtitle=normalize_strategy_dashboard_state(snapshot.state).value,
        primary_metric=build_dashboard_metric(
            name="win_rate",
            label="Win Rate",
            value=snapshot.win_rate,
            unit="%",
        ),
        metrics=[
            build_dashboard_metric(name="signal_count", label="Signals", value=snapshot.signal_count),
            build_dashboard_metric(
                name="average_confidence",
                label="Avg Confidence",
                value=round(snapshot.average_confidence * 100, 2),
                unit="%",
            ),
        ],
        widgets=[
            summary_widget,
            latest_signal_widget,
            confidence_widget,
            table_widget,
        ],
        data=snapshot.to_dict(),
        metadata={
            "strategy_id": snapshot.strategy_id,
        },
    )


def build_signal_strategy_payload(
    *,
    snapshots: list[StrategyDashboardSnapshot],
    payload_id: str = "signal-strategy-dashboard",
    title: str = "Signal & Strategy Dashboard",
) -> DashboardPayload:
    """Build signal and strategy dashboard payload."""
    validate_strategy_snapshots(snapshots)

    if not snapshots:
        return build_dashboard_payload(
            payload_id=payload_id,
            title=title,
            status=DashboardStatus.EMPTY,
            components=[
                build_dashboard_component(
                    component_id="signals-empty",
                    title="No Signals",
                    component_type="status",
                    status=DashboardStatus.EMPTY,
                    description="No strategy snapshots are available.",
                ),
            ],
        )

    cards = [build_signal_strategy_card(snapshot) for snapshot in snapshots]
    all_signals = [
        signal
        for snapshot in snapshots
        for signal in snapshot.signals
    ]

    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=DashboardStatus.READY,
        refresh_mode="auto",
        components=[
            card_to_dashboard_component(card)
            for card in cards
        ],
        metrics=[
            build_dashboard_metric(name="strategy_count", label="Strategies", value=len(snapshots)),
            build_dashboard_metric(name="signal_count", label="Signals", value=len(all_signals)),
            build_dashboard_metric(
                name="actionable_signals",
                label="Actionable Signals",
                value=len([signal for signal in all_signals if signal.actionable]),
            ),
        ],
        data={
            "strategies": [snapshot.to_dict() for snapshot in snapshots],
            "signals": [signal.to_dict() for signal in all_signals],
        },
        metadata={
            "source": "dashboard.signals",
        },
    )


def validate_strategy_snapshots(
    snapshots: list[StrategyDashboardSnapshot],
) -> list[StrategyDashboardSnapshot]:
    """Validate strategy snapshots."""
    if not isinstance(snapshots, list):
        raise ValueError("Snapshots must be a list.")

    for snapshot in snapshots:
        if not isinstance(snapshot, StrategyDashboardSnapshot):
            raise ValueError("Snapshots must contain StrategyDashboardSnapshot objects.")

    return snapshots