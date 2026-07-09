"""
Unit tests for AQOS market overview dashboard payloads.
"""

import pytest

from aqos.dashboard import (
    DashboardCard,
    DashboardPayload,
    DashboardStatus,
    DashboardWidget,
    MarketOverviewSnapshot,
    MarketPricePoint,
    MarketSessionStatus,
    MarketTrendDirection,
    build_market_overview_card,
    build_market_overview_payload,
    build_market_overview_snapshot,
    build_market_overview_widget,
    build_market_price_chart_widget,
    build_market_price_point,
    build_market_table_widget,
    calculate_market_change,
    infer_market_trend_direction,
    latest_market_price_from_points,
    market_rows_to_price_points,
    market_rows_to_snapshot,
    market_snapshot_to_chart_points,
    market_snapshot_to_metrics,
    normalize_market_session_status,
    normalize_market_symbol,
    normalize_market_trend_direction,
    previous_market_price_from_points,
    quote_payload_to_market_snapshot,
    validate_market_price_points,
    validate_market_rows,
    validate_market_snapshots,
)


def sample_rows():
    return [
        {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "open": 1990,
            "high": 2010,
            "low": 1980,
            "close": 2000,
            "volume": 100,
        },
        {
            "timestamp": "2026-01-02T00:00:00+00:00",
            "open": 2000,
            "high": 2025,
            "low": 1995,
            "close": 2020,
            "volume": 120,
        },
    ]


def sample_snapshot():
    return market_rows_to_snapshot(
        symbol="xauusd",
        rows=sample_rows(),
        timeframe="D1",
        provider_id="csv-local",
        session_status="open",
    )


def test_market_enum_values():
    assert MarketTrendDirection.UP.value == "up"
    assert MarketTrendDirection.DOWN.value == "down"
    assert MarketTrendDirection.SIDEWAYS.value == "sideways"
    assert MarketTrendDirection.UNKNOWN.value == "unknown"

    assert MarketSessionStatus.OPEN.value == "open"
    assert MarketSessionStatus.CLOSED.value == "closed"
    assert MarketSessionStatus.UNKNOWN.value == "unknown"


def test_market_normalizers():
    assert normalize_market_symbol(" xauusd ") == "XAUUSD"
    assert normalize_market_symbol("btc/usdt") == "BTC/USDT"
    assert normalize_market_symbol("eth-usdt") == "ETH-USDT"
    assert normalize_market_trend_direction(MarketTrendDirection.UP) == MarketTrendDirection.UP
    assert normalize_market_trend_direction(" DOWN ") == MarketTrendDirection.DOWN
    assert normalize_market_session_status(MarketSessionStatus.OPEN) == MarketSessionStatus.OPEN
    assert normalize_market_session_status(" CLOSED ") == MarketSessionStatus.CLOSED

    with pytest.raises(ValueError):
        normalize_market_symbol("bad symbol")

    with pytest.raises(ValueError):
        normalize_market_trend_direction("bad")

    with pytest.raises(ValueError):
        normalize_market_session_status("bad")


def test_market_price_point_to_dict():
    point = MarketPricePoint(
        timestamp=" 2026-01-01 ",
        open=1990,
        high=2010,
        low=1980,
        close=2000,
        volume=100,
        metadata={
            "source": "test",
        },
    )

    payload = point.to_dict()

    assert point.chart_value == 2000
    assert payload == {
        "timestamp": "2026-01-01",
        "open": 1990.0,
        "high": 2010.0,
        "low": 1980.0,
        "close": 2000.0,
        "volume": 100.0,
        "chart_value": 2000.0,
        "metadata": {
            "source": "test",
        },
    }


def test_market_price_point_rejects_invalid_values():
    with pytest.raises(ValueError):
        MarketPricePoint(timestamp="", close=2000)

    with pytest.raises(ValueError):
        MarketPricePoint(timestamp="2026-01-01", close=0)

    with pytest.raises(ValueError):
        MarketPricePoint(timestamp="2026-01-01", close=2000, open=-1)

    with pytest.raises(ValueError):
        MarketPricePoint(timestamp="2026-01-01", close=2000, metadata=[])


def test_build_market_price_point():
    point = build_market_price_point(
        timestamp="2026-01-01",
        close=2000,
    )

    assert isinstance(point, MarketPricePoint)
    assert point.close == 2000


def test_rows_to_price_points():
    points = market_rows_to_price_points(sample_rows())

    assert len(points) == 2
    assert points[0].close == 2000
    assert points[1].volume == 120

    with pytest.raises(ValueError):
        market_rows_to_price_points("bad")

    with pytest.raises(ValueError):
        market_rows_to_price_points(["bad"])

    with pytest.raises(KeyError):
        market_rows_to_price_points([{"timestamp": "2026-01-01"}])


def test_latest_previous_and_change_helpers():
    points = market_rows_to_price_points(sample_rows())

    assert latest_market_price_from_points(points) == 2020
    assert previous_market_price_from_points(points) == 2000
    assert latest_market_price_from_points([]) == 0.0
    assert previous_market_price_from_points([points[0]]) == 0.0

    change, change_pct = calculate_market_change(
        latest_price=2020,
        previous_price=2000,
    )

    assert change == 20.0
    assert change_pct == 1.0
    assert calculate_market_change(latest_price=0, previous_price=2000) == (0.0, 0.0)

    with pytest.raises(ValueError):
        latest_market_price_from_points(["bad"])

    with pytest.raises(ValueError):
        previous_market_price_from_points(["bad"])

    with pytest.raises(ValueError):
        calculate_market_change(latest_price=-1, previous_price=2000)


def test_infer_market_trend_direction():
    assert infer_market_trend_direction(change_pct=1.0) == MarketTrendDirection.UP
    assert infer_market_trend_direction(change_pct=-1.0) == MarketTrendDirection.DOWN
    assert infer_market_trend_direction(change_pct=0.01) == MarketTrendDirection.SIDEWAYS

    with pytest.raises(ValueError):
        infer_market_trend_direction(change_pct="bad")

    with pytest.raises(ValueError):
        infer_market_trend_direction(change_pct=1, threshold_pct=-1)


def test_market_snapshot_to_dict():
    snapshot = sample_snapshot()
    payload = snapshot.to_dict()

    assert snapshot.has_data is True
    assert snapshot.point_count == 2
    assert snapshot.positive_change is True
    assert snapshot.negative_change is False
    assert payload["symbol"] == "XAUUSD"
    assert payload["timeframe"] == "D1"
    assert payload["latest_price"] == 2020.0
    assert payload["previous_price"] == 2000.0
    assert payload["change"] == 20.0
    assert payload["change_pct"] == 1.0
    assert payload["trend"] == "up"
    assert payload["session_status"] == "open"
    assert payload["provider_id"] == "csv-local"


def test_market_snapshot_rejects_invalid_values():
    point = build_market_price_point(timestamp="2026-01-01", close=2000)

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="", price_points=[point])

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", timeframe="", price_points=[point])

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", price_points=["bad"])

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", latest_price=-1)

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", previous_price=-1)

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", change="bad")

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", change_pct="bad")

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", trend="bad")

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", session_status="bad")

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", provider_id=123)

    with pytest.raises(ValueError):
        MarketOverviewSnapshot(symbol="XAUUSD", metadata=[])


def test_build_market_overview_snapshot():
    points = market_rows_to_price_points(sample_rows())
    snapshot = build_market_overview_snapshot(
        symbol="xauusd",
        timeframe="H1",
        price_points=points,
        provider_id="provider-1",
    )

    assert isinstance(snapshot, MarketOverviewSnapshot)
    assert snapshot.symbol == "xauusd"
    assert snapshot.latest_price == 2020
    assert snapshot.previous_price == 2000
    assert snapshot.change_pct == 1.0
    assert snapshot.trend == MarketTrendDirection.UP
    assert snapshot.provider_id == "provider-1"


def test_quote_payload_to_market_snapshot():
    snapshot = quote_payload_to_market_snapshot(
        quote={
            "symbol": "xauusd",
            "price": 2020,
            "previous_close": 2000,
            "provider_id": "live-provider",
            "session_status": "open",
            "metadata": {
                "source": "quote",
            },
        },
    )

    assert snapshot.symbol == "XAUUSD"
    assert snapshot.latest_price == 2020
    assert snapshot.previous_price == 2000
    assert snapshot.change_pct == 1.0
    assert snapshot.provider_id == "live-provider"
    assert snapshot.metadata == {
        "source": "quote",
    }

    with pytest.raises(ValueError):
        quote_payload_to_market_snapshot(quote=[])

    with pytest.raises(KeyError):
        quote_payload_to_market_snapshot(quote={})


def test_validators():
    points = market_rows_to_price_points(sample_rows())
    snapshot = sample_snapshot()

    assert validate_market_rows(sample_rows()) == sample_rows()
    assert validate_market_price_points(points) == points
    assert validate_market_snapshots([snapshot]) == [snapshot]

    with pytest.raises(ValueError):
        validate_market_rows("bad")

    with pytest.raises(ValueError):
        validate_market_rows(["bad"])

    with pytest.raises(ValueError):
        validate_market_price_points("bad")

    with pytest.raises(ValueError):
        validate_market_price_points(["bad"])

    with pytest.raises(ValueError):
        validate_market_snapshots("bad")

    with pytest.raises(ValueError):
        validate_market_snapshots(["bad"])


def test_market_snapshot_to_metrics_and_chart_points():
    snapshot = sample_snapshot()
    metrics = market_snapshot_to_metrics(snapshot)
    points = market_snapshot_to_chart_points(snapshot)

    assert len(metrics) == 3
    assert metrics[0].name == "latest_price"
    assert metrics[0].value == 2020
    assert metrics[1].name == "change_pct"
    assert points[0]["x"] == "2026-01-01T00:00:00+00:00"
    assert points[1]["close"] == 2020

    with pytest.raises(ValueError):
        market_snapshot_to_metrics("bad")

    with pytest.raises(ValueError):
        market_snapshot_to_chart_points("bad")


def test_build_market_overview_widget():
    widget = build_market_overview_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "market-overview-xauusd"
    assert widget.widget_type.value == "market"
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 3
    assert widget.action_count == 1
    assert widget.data["symbol"] == "XAUUSD"

    empty_widget = build_market_overview_widget(
        build_market_overview_snapshot(symbol="EURUSD"),
    )

    assert empty_widget.status == DashboardStatus.EMPTY
    assert empty_widget.issue_count == 1

    with pytest.raises(ValueError):
        build_market_overview_widget("bad")


def test_build_market_price_chart_widget():
    widget = build_market_price_chart_widget(sample_snapshot())

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "market-chart-xauusd"
    assert widget.chart_type.value == "line"
    assert widget.series_count == 1
    assert widget.chart_series[0].point_count == 2

    empty_widget = build_market_price_chart_widget(
        build_market_overview_snapshot(symbol="EURUSD"),
    )

    assert empty_widget.status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_market_price_chart_widget("bad")


def test_build_market_table_widget():
    snapshot = sample_snapshot()
    widget = build_market_table_widget([snapshot])

    assert isinstance(widget, DashboardWidget)
    assert widget.widget_id == "market-overview-table"
    assert widget.row_count == 1
    assert widget.table_rows[0]["symbol"] == "XAUUSD"
    assert widget.table_rows[0]["trend"] == "up"

    empty_widget = build_market_table_widget([])

    assert empty_widget.status == DashboardStatus.EMPTY

    with pytest.raises(ValueError):
        build_market_table_widget(["bad"])


def test_build_market_overview_card():
    card = build_market_overview_card(sample_snapshot())

    assert isinstance(card, DashboardCard)
    assert card.card_id == "market-card-xauusd"
    assert card.primary_metric.name == "latest_price"
    assert card.widget_count == 2
    assert card.data["symbol"] == "XAUUSD"

    with pytest.raises(ValueError):
        build_market_overview_card("bad")


def test_build_market_overview_payload():
    snapshot = sample_snapshot()
    payload = build_market_overview_payload(
        snapshots=[snapshot],
    )

    assert isinstance(payload, DashboardPayload)
    assert payload.payload_id == "market-overview"
    assert payload.status == DashboardStatus.READY
    assert payload.component_count == 2
    assert payload.metric_count == 2
    assert payload.data["symbols"] == ["XAUUSD"]
    assert payload.metrics[0].name == "symbol_count"

    empty_payload = build_market_overview_payload(snapshots=[])

    assert empty_payload.status == DashboardStatus.EMPTY
    assert empty_payload.component_count == 1

    with pytest.raises(ValueError):
        build_market_overview_payload(snapshots=["bad"])


def test_dashboard_market_exports_exist():
    import aqos.dashboard as dashboard

    expected_exports = [
        "MarketOverviewSnapshot",
        "MarketPricePoint",
        "MarketSessionStatus",
        "MarketTrendDirection",
        "build_market_overview_card",
        "build_market_overview_payload",
        "build_market_overview_snapshot",
        "build_market_overview_widget",
        "build_market_price_chart_widget",
        "build_market_price_point",
        "build_market_table_widget",
        "calculate_market_change",
        "infer_market_trend_direction",
        "latest_market_price_from_points",
        "market_rows_to_price_points",
        "market_rows_to_snapshot",
        "market_snapshot_to_chart_points",
        "market_snapshot_to_metrics",
        "normalize_market_session_status",
        "normalize_market_symbol",
        "normalize_market_trend_direction",
        "previous_market_price_from_points",
        "quote_payload_to_market_snapshot",
        "validate_market_price_points",
        "validate_market_rows",
        "validate_market_snapshots",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name