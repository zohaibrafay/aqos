"""
Unit tests for AQOS portfolio and risk dashboard payloads.
"""

import pytest

from aqos.dashboard import (
    DashboardCard,
    DashboardPayload,
    DashboardStatus,
    DashboardWidget,
    PortfolioPositionItem,
    PortfolioPositionSide,
    PortfolioRiskLevel,
    PortfolioRiskSnapshot,
    account_payload_to_portfolio_snapshot,
    build_portfolio_pnl_chart_widget,
    build_portfolio_position_item,
    build_portfolio_positions_table_widget,
    build_portfolio_risk_card,
    build_portfolio_risk_payload,
    build_portfolio_risk_snapshot,
    build_portfolio_risk_widget,
    build_portfolio_summary_widget,
    infer_portfolio_risk_level,
    normalize_portfolio_position_side,
    normalize_portfolio_risk_level,
    portfolio_snapshot_to_metrics,
    position_dict_to_portfolio_item,
    position_dicts_to_portfolio_items,
    validate_pnl_history,
    validate_portfolio_positions,
    validate_portfolio_snapshots,
)


def sample_position():
    return build_portfolio_position_item(
        position_id="position-1",
        symbol="xauusd",
        side="long",
        quantity=2,
        average_price=2000,
        market_price=2020,
        unrealized_pnl=40,
        realized_pnl=10,
        allocation_pct=25,
        opened_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-02T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )


def sample_snapshot():
    return build_portfolio_risk_snapshot(
        portfolio_id="portfolio-1",
        account_id="account-1",
        currency="USD",
        cash_balance=96000,
        equity=100000,
        buying_power=90000,
        realized_pnl=500,
        unrealized_pnl=250,
        max_drawdown_pct=6,
        daily_var=2,
        positions=[sample_position()],
        pnl_history=[
            {"x": "2026-01-01", "y": 500},
            {"x": "2026-01-02", "y": 750},
        ],
        updated_at="2026-01-02T00:00:00+00:00",
    )


def test_portfolio_enum_values():
    assert PortfolioPositionSide.LONG.value == "long"
    assert PortfolioPositionSide.SHORT.value == "short"
    assert PortfolioPositionSide.FLAT.value == "flat"

    assert PortfolioRiskLevel.LOW.value == "low"
    assert PortfolioRiskLevel.MEDIUM.value == "medium"
    assert PortfolioRiskLevel.HIGH.value == "high"
    assert PortfolioRiskLevel.CRITICAL.value == "critical"
    assert PortfolioRiskLevel.UNKNOWN.value == "unknown"


def test_portfolio_normalizers():
    assert normalize_portfolio_position_side(PortfolioPositionSide.LONG) == PortfolioPositionSide.LONG
    assert normalize_portfolio_position_side(" SHORT ") == PortfolioPositionSide.SHORT
    assert normalize_portfolio_risk_level(PortfolioRiskLevel.LOW) == PortfolioRiskLevel.LOW
    assert normalize_portfolio_risk_level(" CRITICAL ") == PortfolioRiskLevel.CRITICAL

    with pytest.raises(ValueError):
        normalize_portfolio_position_side("bad")

    with pytest.raises(ValueError):
        normalize_portfolio_risk_level("bad")


def test_infer_portfolio_risk_level():
    assert infer_portfolio_risk_level(exposure_pct=20, max_drawdown_pct=2) == PortfolioRiskLevel.LOW
    assert infer_portfolio_risk_level(exposure_pct=60, max_drawdown_pct=5) == PortfolioRiskLevel.MEDIUM
    assert infer_portfolio_risk_level(exposure_pct=85, max_drawdown_pct=10) == PortfolioRiskLevel.HIGH
    assert infer_portfolio_risk_level(exposure_pct=96, max_drawdown_pct=5) == PortfolioRiskLevel.CRITICAL
    assert infer_portfolio_risk_level(exposure_pct=20, max_drawdown_pct=30) == PortfolioRiskLevel.CRITICAL

    with pytest.raises(ValueError):
        infer_portfolio_risk_level(exposure_pct=-1, max_drawdown_pct=2)

    with pytest.raises(ValueError):
        infer_portfolio_risk_level(exposure_pct=20, max_drawdown_pct=-1)

    with pytest.raises(ValueError):
        infer_portfolio_risk_level(exposure_pct=20, max_drawdown_pct=2, daily_var=-1)


def test_portfolio_position_to_dict():
    position = sample_position()
    payload = position.to_dict()

    assert position.open is True
    assert position.total_pnl == 50.0
    assert position.pnl_pct == 1.25
    assert payload["position_id"] == "position-1"
    assert payload["symbol"] == "XAUUSD"
    assert payload["side"] == "long"
    assert payload["quantity"] == 2.0
    assert payload["market_value"] == 4040.0
    assert payload["total_pnl"] == 50.0
    assert payload["allocation_pct"] == 25.0


def test_portfolio_position_rejects_invalid_values():
    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="", symbol="XAUUSD", side="long")

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="bad symbol", side="long")

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="bad")

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="long", quantity=-1)

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="long", average_price=-1)

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="long", market_price=-1)

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="long", market_value="bad")

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="long", allocation_pct=101)

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="long", opened_at=123)

    with pytest.raises(ValueError):
        PortfolioPositionItem(position_id="position-1", symbol="XAUUSD", side="long", metadata=[])


def test_position_dict_converters():
    position = position_dict_to_portfolio_item(
        {
            "id": "position-1",
            "symbol": "xauusd",
            "side": "long",
            "quantity": 2,
            "avg_price": 2000,
            "price": 2020,
            "unrealized_pnl": 40,
            "allocation_pct": 25,
        }
    )
    positions = position_dicts_to_portfolio_items(
        [
            {
                "position_id": "position-2",
                "symbol": "EURUSD",
                "side": "short",
                "quantity": 1,
                "average_price": 1.1,
                "market_price": 1.08,
            }
        ]
    )

    assert position.position_id == "position-1"
    assert position.symbol == "xauusd"
    assert position.market_value == 4040.0
    assert len(positions) == 1
    assert positions[0].side == "short"

    with pytest.raises(ValueError):
        position_dict_to_portfolio_item([])

    with pytest.raises(ValueError):
        position_dicts_to_portfolio_items("bad")

    with pytest.raises(KeyError):
        position_dict_to_portfolio_item({"position_id": "bad"})


def test_portfolio_snapshot_to_dict():
    snapshot = sample_snapshot()
    payload = snapshot.to_dict()

    assert snapshot.total_pnl == 750.0
    assert snapshot.position_count == 1
    assert snapshot.open_position_count == 1
    assert snapshot.healthy is True
    assert payload["portfolio_id"] == "portfolio-1"
    assert payload["account_id"] == "account-1"
    assert payload["currency"] == "USD"
    assert payload["equity"] == 100000.0
    assert payload["total_market_value"] == 4040.0
    assert payload["exposure_pct"] == 4.04
    assert payload["risk_level"] == "low"
    assert payload["positions"][0]["symbol"] == "XAUUSD"


def test_portfolio_snapshot_rejects_invalid_values():
    position = sample_position()

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="")

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", account_id=123)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", currency="")

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", cash_balance=-1)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", equity=-1)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", buying_power=-1)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", total_market_value=-1)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", realized_pnl="bad")

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", exposure_pct=101)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", max_drawdown_pct=101)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", daily_var=-1)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", risk_level="bad")

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", positions=["bad"])

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", pnl_history=["bad"])

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", updated_at=123)

    with pytest.raises(ValueError):
        PortfolioRiskSnapshot(portfolio_id="portfolio-1", metadata=[])

    assert validate_portfolio_positions([position]) == [position]


def test_build_portfolio_risk_snapshot_defaults():
    snapshot = build_portfolio_risk_snapshot(
        portfolio_id="portfolio-1",
        equity=100000,
        positions=[sample_position()],
    )

    assert isinstance(snapshot, PortfolioRiskSnapshot)
    assert snapshot.total_market_value == 4040.0
    assert snapshot.exposure_pct == 4.04
    assert snapshot.risk_level == PortfolioRiskLevel.LOW


def test_account_payload_to_portfolio_snapshot():
    snapshot = account_payload_to_portfolio_snapshot(
        account={
            "account_id": "account-1",
            "currency": "USD",
            "cash_balance": 95000,
            "equity": 100000,
            "buying_power": 90000,
            "realized_pnl": 500,
            "unrealized_pnl": 250,
            "updated_at": "2026-01-01T00:00:00+00:00",
        },
        positions=[
            {
                "position_id": "position-1",
                "symbol": "XAUUSD",
                "side": "long",
                "quantity": 2,
                "average_price": 2000,
                "market_price": 2020,
                "allocation_pct": 25,
            }
        ],
        portfolio_id="portfolio-1",
    )

    assert snapshot.account_id == "account-1"
    assert snapshot.position_count == 1
    assert snapshot.total_market_value == 4040.0

    with pytest.raises(ValueError):
        account_payload_to_portfolio_snapshot(account=[])
        

def test_validate_helpers():
    position = sample_position()
    snapshot = sample_snapshot()

    assert validate_portfolio_positions([position]) == [position]
    assert validate_portfolio_snapshots([snapshot]) == [snapshot]
    assert validate_pnl_history([{"x": "2026-01-01", "y": 1}]) == [{"x": "2026-01-01", "y": 1}]

    with pytest.raises(ValueError):
        validate_portfolio_positions("bad")

    with pytest.raises(ValueError):
        validate_portfolio_positions(["bad"])

    with pytest.raises(ValueError):
        validate_portfolio_snapshots("bad")

    with pytest.raises(ValueError):
        validate_portfolio_snapshots(["bad"])

    with pytest.raises(ValueError):
        validate_pnl_history("bad")

    with pytest.raises(ValueError):
        validate_pnl_history(["bad"])


def test_portfolio_snapshot_to_metrics():
    metrics = portfolio_snapshot_to_metrics(sample_snapshot())

    assert len(metrics) == 6
    assert metrics[0].name == "equity"
    assert metrics[0].value == 100000
    assert metrics[2].name == "total_pnl"
    assert metrics[2].value == 750

    with pytest.raises(ValueError):
        portfolio_snapshot_to_metrics("bad")


def test_build_portfolio_summary_widget():
    widget = build_portfolio_summary_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "portfolio-summary-portfolio-1"
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 6
    assert widget.action_count == 1
    assert widget.data["portfolio_id"] == "portfolio-1"

    high_risk_widget = build_portfolio_summary_widget(
        build_portfolio_risk_snapshot(
            portfolio_id="portfolio-2",
            equity=100000,
            exposure_pct=96,
        )
    )

    assert high_risk_widget.status == DashboardStatus.ERROR
    assert high_risk_widget.issue_count == 1

    with pytest.raises(ValueError):
        build_portfolio_summary_widget("bad")


def test_build_portfolio_positions_table_widget():
    widget = build_portfolio_positions_table_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "portfolio-positions-portfolio-1"
    assert widget.status == DashboardStatus.READY
    assert widget.row_count == 1
    assert widget.table_rows[0]["symbol"] == "XAUUSD"

    empty_widget = build_portfolio_positions_table_widget(
        build_portfolio_risk_snapshot(portfolio_id="portfolio-empty")
    )

    assert empty_widget.status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_portfolio_positions_table_widget("bad")


def test_build_portfolio_risk_widget():
    widget = build_portfolio_risk_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "portfolio-risk-portfolio-1"
    assert widget.widget_type.value == "risk"
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 3
    assert widget.series_count == 1
    assert widget.data["risk_level"] == "low"

    critical_widget = build_portfolio_risk_widget(
        build_portfolio_risk_snapshot(
            portfolio_id="portfolio-critical",
            equity=100000,
            exposure_pct=96,
        )
    )

    assert critical_widget.status == DashboardStatus.ERROR

    with pytest.raises(ValueError):
        build_portfolio_risk_widget("bad")


def test_build_portfolio_pnl_chart_widget():
    widget = build_portfolio_pnl_chart_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "portfolio-pnl-portfolio-1"
    assert widget.status == DashboardStatus.READY
    assert widget.series_count == 1
    assert widget.chart_series[0].point_count == 2

    empty_widget = build_portfolio_pnl_chart_widget(
        build_portfolio_risk_snapshot(portfolio_id="portfolio-empty")
    )

    assert empty_widget.status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_portfolio_pnl_chart_widget("bad")


def test_build_portfolio_risk_card():
    card = build_portfolio_risk_card(sample_snapshot())

    assert isinstance(card, DashboardCard)
    assert card.card_id == "portfolio-risk-card-portfolio-1"
    assert card.status == DashboardStatus.READY
    assert card.primary_metric.name == "equity"
    assert card.widget_count == 4
    assert card.data["portfolio_id"] == "portfolio-1"

    with pytest.raises(ValueError):
        build_portfolio_risk_card("bad")


def test_build_portfolio_risk_payload():
    snapshot = sample_snapshot()
    payload = build_portfolio_risk_payload(
        snapshots=[snapshot],
    )

    assert isinstance(payload, DashboardPayload)
    assert payload.payload_id == "portfolio-risk-dashboard"
    assert payload.status == DashboardStatus.READY
    assert payload.component_count == 2
    assert payload.metric_count == 4
    assert payload.data["portfolios"][0]["portfolio_id"] == "portfolio-1"
    assert len(payload.data["positions"]) == 1

    empty_payload = build_portfolio_risk_payload(snapshots=[])

    assert empty_payload.status == DashboardStatus.EMPTY
    assert empty_payload.component_count == 1

    with pytest.raises(ValueError):
        build_portfolio_risk_payload(snapshots=["bad"])


def test_dashboard_portfolio_exports_exist():
    import aqos.dashboard as dashboard

    expected_exports = [
        "PortfolioPositionItem",
        "PortfolioPositionSide",
        "PortfolioRiskLevel",
        "PortfolioRiskSnapshot",
        "account_payload_to_portfolio_snapshot",
        "build_portfolio_pnl_chart_widget",
        "build_portfolio_position_item",
        "build_portfolio_positions_table_widget",
        "build_portfolio_risk_card",
        "build_portfolio_risk_payload",
        "build_portfolio_risk_snapshot",
        "build_portfolio_risk_widget",
        "build_portfolio_summary_widget",
        "infer_portfolio_risk_level",
        "normalize_portfolio_position_side",
        "normalize_portfolio_risk_level",
        "portfolio_snapshot_to_metrics",
        "position_dict_to_portfolio_item",
        "position_dicts_to_portfolio_items",
        "validate_pnl_history",
        "validate_portfolio_positions",
        "validate_portfolio_snapshots",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name