"""
Unit tests for AQOS signal and strategy dashboard payloads.
"""

import pytest

from aqos.dashboard import (
    DashboardCard,
    DashboardPayload,
    DashboardStatus,
    DashboardWidget,
    SignalConfidenceLevel,
    SignalDashboardItem,
    SignalDirection,
    StrategyDashboardSnapshot,
    StrategyDashboardState,
    build_latest_signal_widget,
    build_signal_confidence_widget,
    build_signal_dashboard_item,
    build_signal_strategy_card,
    build_signal_strategy_payload,
    build_signal_table_widget,
    build_strategy_dashboard_snapshot,
    build_strategy_summary_widget,
    infer_signal_confidence_level,
    normalize_signal_confidence_level,
    normalize_signal_direction,
    normalize_strategy_dashboard_state,
    signal_dict_to_dashboard_item,
    signal_dicts_to_dashboard_items,
    signal_item_to_metrics,
    validate_confidence_score,
    validate_non_negative_integer,
    validate_percentage,
    validate_signal_dashboard_items,
    validate_strategy_metrics,
    validate_strategy_snapshots,
)


def sample_signal():
    return build_signal_dashboard_item(
        signal_id="signal-1",
        symbol="xauusd",
        direction="buy",
        confidence=0.82,
        strategy_name="Liquidity Sweep",
        timeframe="H1",
        entry_price=2000,
        stop_loss=1985,
        take_profit=2030,
        risk_reward=2.0,
        generated_at="2026-01-01T00:00:00+00:00",
        reason="Bullish liquidity sweep confirmed.",
        metadata={
            "source": "test",
        },
    )


def sample_snapshot():
    return build_strategy_dashboard_snapshot(
        strategy_id="strategy-1",
        strategy_name="Liquidity Sweep",
        state="active",
        signals=[
            sample_signal(),
            build_signal_dashboard_item(
                signal_id="signal-2",
                symbol="EURUSD",
                direction="hold",
                confidence=0.35,
                strategy_name="Liquidity Sweep",
                timeframe="H1",
            ),
        ],
        metrics={
            "win_rate": 62.5,
            "profit_factor": 1.8,
            "sharpe_ratio": 1.2,
            "max_drawdown_pct": 8.5,
        },
    )


def test_signal_enum_values():
    assert SignalDirection.BUY.value == "buy"
    assert SignalDirection.SELL.value == "sell"
    assert SignalDirection.HOLD.value == "hold"
    assert SignalDirection.UNKNOWN.value == "unknown"

    assert SignalConfidenceLevel.LOW.value == "low"
    assert SignalConfidenceLevel.MEDIUM.value == "medium"
    assert SignalConfidenceLevel.HIGH.value == "high"
    assert SignalConfidenceLevel.UNKNOWN.value == "unknown"

    assert StrategyDashboardState.ACTIVE.value == "active"
    assert StrategyDashboardState.INACTIVE.value == "inactive"
    assert StrategyDashboardState.TESTING.value == "testing"
    assert StrategyDashboardState.ERROR.value == "error"
    assert StrategyDashboardState.UNKNOWN.value == "unknown"


def test_signal_normalizers():
    assert normalize_signal_direction(SignalDirection.BUY) == SignalDirection.BUY
    assert normalize_signal_direction(" SELL ") == SignalDirection.SELL
    assert normalize_signal_confidence_level(SignalConfidenceLevel.HIGH) == SignalConfidenceLevel.HIGH
    assert normalize_signal_confidence_level(" MEDIUM ") == SignalConfidenceLevel.MEDIUM
    assert normalize_strategy_dashboard_state(StrategyDashboardState.ACTIVE) == StrategyDashboardState.ACTIVE
    assert normalize_strategy_dashboard_state(" TESTING ") == StrategyDashboardState.TESTING

    with pytest.raises(ValueError):
        normalize_signal_direction("bad")

    with pytest.raises(ValueError):
        normalize_signal_confidence_level("bad")

    with pytest.raises(ValueError):
        normalize_strategy_dashboard_state("bad")


def test_signal_validators():
    assert validate_confidence_score(0.5) == 0.5
    assert validate_percentage(50, "Win rate") == 50.0
    assert validate_non_negative_integer(0, "Count") == 0
    assert validate_strategy_metrics({"win_rate": 50}) == {"win_rate": 50}

    with pytest.raises(ValueError):
        validate_confidence_score(-0.1)

    with pytest.raises(ValueError):
        validate_confidence_score(1.1)

    with pytest.raises(ValueError):
        validate_confidence_score("bad")

    with pytest.raises(ValueError):
        validate_percentage(-1, "Win rate")

    with pytest.raises(ValueError):
        validate_percentage(101, "Win rate")

    with pytest.raises(ValueError):
        validate_non_negative_integer(-1, "Count")

    with pytest.raises(ValueError):
        validate_non_negative_integer(True, "Count")

    with pytest.raises(ValueError):
        validate_strategy_metrics([])


def test_infer_signal_confidence_level():
    assert infer_signal_confidence_level(0.8) == SignalConfidenceLevel.HIGH
    assert infer_signal_confidence_level(0.5) == SignalConfidenceLevel.MEDIUM
    assert infer_signal_confidence_level(0.2) == SignalConfidenceLevel.LOW


def test_signal_dashboard_item_to_dict():
    signal = sample_signal()
    payload = signal.to_dict()

    assert signal.confidence_level == SignalConfidenceLevel.HIGH
    assert signal.actionable is True
    assert signal.has_prices is True
    assert payload["signal_id"] == "signal-1"
    assert payload["symbol"] == "XAUUSD"
    assert payload["direction"] == "buy"
    assert payload["confidence"] == 0.82
    assert payload["confidence_level"] == "high"
    assert payload["strategy_name"] == "Liquidity Sweep"
    assert payload["risk_reward"] == 2.0


def test_signal_dashboard_item_rejects_invalid_values():
    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="", symbol="XAUUSD", direction="buy")

    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="signal-1", symbol="bad symbol", direction="buy")

    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="signal-1", symbol="XAUUSD", direction="bad")

    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="signal-1", symbol="XAUUSD", direction="buy", confidence=2)

    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="signal-1", symbol="XAUUSD", direction="buy", strategy_name=123)

    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="signal-1", symbol="XAUUSD", direction="buy", timeframe=123)

    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="signal-1", symbol="XAUUSD", direction="buy", entry_price=-1)

    with pytest.raises(ValueError):
        SignalDashboardItem(signal_id="signal-1", symbol="XAUUSD", direction="buy", metadata=[])


def test_signal_dict_converters():
    signal = signal_dict_to_dashboard_item(
        {
            "id": "signal-1",
            "symbol": "xauusd",
            "side": "sell",
            "confidence": 0.7,
            "entry": 2000,
            "sl": 2010,
            "tp": 1980,
            "rr": 2.0,
        }
    )
    signals = signal_dicts_to_dashboard_items(
        [
            {
                "signal_id": "signal-2",
                "symbol": "EURUSD",
                "direction": "buy",
            }
        ]
    )

    assert signal.signal_id == "signal-1"
    assert signal.direction == "sell"
    assert signal.entry_price == 2000
    assert len(signals) == 1
    assert signals[0].symbol == "EURUSD"

    with pytest.raises(ValueError):
        signal_dict_to_dashboard_item([])

    with pytest.raises(ValueError):
        signal_dicts_to_dashboard_items("bad")

    with pytest.raises(KeyError):
        signal_dict_to_dashboard_item({"signal_id": "bad"})


def test_strategy_dashboard_snapshot_to_dict():
    snapshot = sample_snapshot()
    payload = snapshot.to_dict()

    assert snapshot.signal_count == 2
    assert snapshot.latest_signal.signal_id == "signal-2"
    assert snapshot.healthy is True
    assert payload["strategy_id"] == "strategy-1"
    assert payload["strategy_name"] == "Liquidity Sweep"
    assert payload["state"] == "active"
    assert payload["win_rate"] == 62.5
    assert payload["total_signals"] == 2
    assert payload["active_signals"] == 1
    assert payload["average_confidence"] == 0.585
    assert payload["latest_signal"]["signal_id"] == "signal-2"


def test_strategy_snapshot_rejects_invalid_values():
    signal = sample_signal()

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="", strategy_name="Strategy")

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="")

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", state="bad")

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", signals=["bad"])

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", win_rate=101)

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", total_signals=-1)

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", average_confidence=2)

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", profit_factor=-1)

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", sharpe_ratio="bad")

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", max_drawdown_pct=-1)

    with pytest.raises(ValueError):
        StrategyDashboardSnapshot(strategy_id="strategy-1", strategy_name="Strategy", metadata=[])

    assert validate_signal_dashboard_items([signal]) == [signal]


def test_build_strategy_dashboard_snapshot_defaults():
    snapshot = build_strategy_dashboard_snapshot(
        strategy_id="strategy-1",
        strategy_name="Strategy",
        state="testing",
        signals=[sample_signal()],
    )

    assert snapshot.state == "testing"
    assert snapshot.total_signals == 1
    assert snapshot.active_signals == 1
    assert snapshot.average_confidence == 0.82


def test_signal_item_to_metrics():
    metrics = signal_item_to_metrics(sample_signal())

    assert len(metrics) == 2
    assert metrics[0].name == "confidence"
    assert metrics[0].value == 82.0
    assert metrics[1].name == "risk_reward"
    assert metrics[1].value == 2.0

    with pytest.raises(ValueError):
        signal_item_to_metrics("bad")


def test_build_latest_signal_widget():
    widget = build_latest_signal_widget(sample_signal())
    empty_widget = build_latest_signal_widget(None)

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "latest-signal-signal-1"
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 2
    assert widget.action_count == 1
    assert widget.data["symbol"] == "XAUUSD"

    assert empty_widget.status == DashboardStatus.EMPTY
    assert empty_widget.issue_count == 1

    with pytest.raises(ValueError):
        build_latest_signal_widget("bad")


def test_build_signal_confidence_widget():
    widget = build_signal_confidence_widget(sample_snapshot().signals)
    empty_widget = build_signal_confidence_widget([])

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "signal-confidence"
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 4
    assert widget.series_count == 1
    assert widget.metadata["signal_count"] == 2

    assert empty_widget.status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_signal_confidence_widget(["bad"])


def test_build_signal_table_widget():
    widget = build_signal_table_widget(sample_snapshot().signals)
    empty_widget = build_signal_table_widget([])

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "signal-table"
    assert widget.status == DashboardStatus.READY
    assert widget.row_count == 2
    assert widget.table_rows[0]["symbol"] == "XAUUSD"

    assert empty_widget.status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_signal_table_widget(["bad"])


def test_build_strategy_summary_widget():
    snapshot = sample_snapshot()
    widget = build_strategy_summary_widget(snapshot)

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "strategy-summary-strategy-1"
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 6
    assert widget.data["strategy_id"] == "strategy-1"

    error_widget = build_strategy_summary_widget(
        build_strategy_dashboard_snapshot(
            strategy_id="strategy-error",
            strategy_name="Strategy Error",
            state="error",
        )
    )

    assert error_widget.status == DashboardStatus.ERROR

    with pytest.raises(ValueError):
        build_strategy_summary_widget("bad")


def test_build_signal_strategy_card():
    card = build_signal_strategy_card(sample_snapshot())

    assert isinstance(card, DashboardCard)
    assert card.card_id == "signal-strategy-card-strategy-1"
    assert card.status == DashboardStatus.READY
    assert card.primary_metric.name == "win_rate"
    assert card.widget_count == 4
    assert card.data["strategy_id"] == "strategy-1"

    with pytest.raises(ValueError):
        build_signal_strategy_card("bad")


def test_build_signal_strategy_payload():
    snapshot = sample_snapshot()
    payload = build_signal_strategy_payload(
        snapshots=[snapshot],
    )

    assert isinstance(payload, DashboardPayload)
    assert payload.payload_id == "signal-strategy-dashboard"
    assert payload.status == DashboardStatus.READY
    assert payload.component_count == 1
    assert payload.metric_count == 3
    assert payload.data["strategies"][0]["strategy_id"] == "strategy-1"
    assert len(payload.data["signals"]) == 2

    empty_payload = build_signal_strategy_payload(snapshots=[])

    assert empty_payload.status == DashboardStatus.EMPTY
    assert empty_payload.component_count == 1

    with pytest.raises(ValueError):
        build_signal_strategy_payload(snapshots=["bad"])


def test_validate_strategy_snapshots():
    snapshot = sample_snapshot()

    assert validate_strategy_snapshots([snapshot]) == [snapshot]

    with pytest.raises(ValueError):
        validate_strategy_snapshots("bad")

    with pytest.raises(ValueError):
        validate_strategy_snapshots(["bad"])


def test_dashboard_signal_exports_exist():
    import aqos.dashboard as dashboard

    expected_exports = [
        "SignalConfidenceLevel",
        "SignalDashboardItem",
        "SignalDirection",
        "StrategyDashboardSnapshot",
        "StrategyDashboardState",
        "build_latest_signal_widget",
        "build_signal_confidence_widget",
        "build_signal_dashboard_item",
        "build_signal_strategy_card",
        "build_signal_strategy_payload",
        "build_signal_table_widget",
        "build_strategy_dashboard_snapshot",
        "build_strategy_summary_widget",
        "infer_signal_confidence_level",
        "normalize_signal_confidence_level",
        "normalize_signal_direction",
        "normalize_strategy_dashboard_state",
        "signal_dict_to_dashboard_item",
        "signal_dicts_to_dashboard_items",
        "signal_item_to_metrics",
        "validate_confidence_score",
        "validate_non_negative_integer",
        "validate_percentage",
        "validate_signal_dashboard_items",
        "validate_strategy_metrics",
        "validate_strategy_snapshots",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name