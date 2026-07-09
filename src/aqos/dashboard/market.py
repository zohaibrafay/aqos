"""
AQOS market overview dashboard payloads.

This module prepares frontend-ready market overview widgets, cards, charts,
tables, and dashboard payloads from OHLCV rows, quote payloads, and price data.
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
    validate_positive_float,
    validate_string,
)
from aqos.dashboard.widgets import (
    DashboardCard,
    DashboardChartType,
    DashboardTableColumn,
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


class MarketTrendDirection(str, Enum):
    """Supported market trend directions."""

    UP = "up"
    DOWN = "down"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class MarketSessionStatus(str, Enum):
    """Supported market session statuses."""

    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MarketPricePoint:
    """Market OHLCV/chart point."""

    timestamp: str
    close: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_positive_float(self.close, "Close")
        validate_non_negative_float(self.open, "Open")
        validate_non_negative_float(self.high, "High")
        validate_non_negative_float(self.low, "Low")
        validate_non_negative_float(self.volume, "Volume")
        validate_metadata(self.metadata, "Metadata")

    @property
    def chart_value(self) -> float:
        """Return chart value."""
        return float(self.close)

    def to_dict(self) -> dict[str, Any]:
        """Convert price point into dictionary."""
        return {
            "timestamp": self.timestamp.strip(),
            "open": float(self.open),
            "high": float(self.high),
            "low": float(self.low),
            "close": float(self.close),
            "volume": float(self.volume),
            "chart_value": self.chart_value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class MarketOverviewSnapshot:
    """Market overview snapshot."""

    symbol: str
    timeframe: str = "D1"
    price_points: list[MarketPricePoint] = field(default_factory=list)
    latest_price: float = 0.0
    previous_price: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    trend: MarketTrendDirection | str = MarketTrendDirection.UNKNOWN
    session_status: MarketSessionStatus | str = MarketSessionStatus.UNKNOWN
    provider_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalize_market_symbol(self.symbol)
        validate_non_empty_string(self.timeframe, "Timeframe")
        validate_market_price_points(self.price_points)
        validate_non_negative_float(self.latest_price, "Latest price")
        validate_non_negative_float(self.previous_price, "Previous price")
        validate_number(self.change, "Change")
        validate_number(self.change_pct, "Change percentage")
        normalize_market_trend_direction(self.trend)
        normalize_market_session_status(self.session_status)
        validate_string(self.provider_id, "Provider ID")
        validate_metadata(self.metadata, "Metadata")

    @property
    def has_data(self) -> bool:
        """Return whether snapshot has market data."""
        return bool(self.price_points) or self.latest_price > 0

    @property
    def point_count(self) -> int:
        """Return price point count."""
        return len(self.price_points)

    @property
    def positive_change(self) -> bool:
        """Return whether market change is positive."""
        return self.change > 0

    @property
    def negative_change(self) -> bool:
        """Return whether market change is negative."""
        return self.change < 0

    def to_dict(self) -> dict[str, Any]:
        """Convert snapshot into dictionary."""
        return {
            "symbol": normalize_market_symbol(self.symbol),
            "timeframe": self.timeframe.strip(),
            "price_points": [point.to_dict() for point in self.price_points],
            "latest_price": float(self.latest_price),
            "previous_price": float(self.previous_price),
            "change": float(self.change),
            "change_pct": float(self.change_pct),
            "trend": normalize_market_trend_direction(self.trend).value,
            "session_status": normalize_market_session_status(self.session_status).value,
            "provider_id": self.provider_id.strip(),
            "has_data": self.has_data,
            "point_count": self.point_count,
            "positive_change": self.positive_change,
            "negative_change": self.negative_change,
            "metadata": dict(self.metadata),
        }


def normalize_market_symbol(symbol: str) -> str:
    """Normalize market symbol."""
    normalized = validate_non_empty_string(symbol, "Symbol").upper()

    if not normalized.replace("/", "").replace("-", "").isalnum():
        raise ValueError("Symbol must be alphanumeric and may include '/' or '-'.")

    return normalized


def normalize_market_trend_direction(
    trend: MarketTrendDirection | str,
) -> MarketTrendDirection:
    """Normalize market trend direction."""
    if isinstance(trend, MarketTrendDirection):
        return trend

    normalized = validate_non_empty_string(trend, "Market trend").lower()

    try:
        return MarketTrendDirection(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MarketTrendDirection)
        raise ValueError(
            f"Invalid market trend '{trend}'. Valid trends: {valid}.",
        ) from exc


def normalize_market_session_status(
    session_status: MarketSessionStatus | str,
) -> MarketSessionStatus:
    """Normalize market session status."""
    if isinstance(session_status, MarketSessionStatus):
        return session_status

    normalized = validate_non_empty_string(session_status, "Market session status").lower()

    try:
        return MarketSessionStatus(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in MarketSessionStatus)
        raise ValueError(
            f"Invalid market session status '{session_status}'. Valid statuses: {valid}.",
        ) from exc


def validate_market_price_points(
    price_points: list[MarketPricePoint],
) -> list[MarketPricePoint]:
    """Validate market price points."""
    if not isinstance(price_points, list):
        raise ValueError("Price points must be a list.")

    for point in price_points:
        if not isinstance(point, MarketPricePoint):
            raise ValueError("Price points must contain MarketPricePoint objects.")

    return price_points


def validate_market_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate market rows."""
    if not isinstance(rows, list):
        raise ValueError("Rows must be a list.")

    for row in rows:
        validate_metadata(row, "Market row")

    return rows


def build_market_price_point(
    *,
    timestamp: str,
    close: float,
    open: float = 0.0,
    high: float = 0.0,
    low: float = 0.0,
    volume: float = 0.0,
    metadata: dict[str, Any] | None = None,
) -> MarketPricePoint:
    """Build market price point."""
    return MarketPricePoint(
        timestamp=timestamp,
        close=close,
        open=open,
        high=high,
        low=low,
        volume=volume,
        metadata=metadata or {},
    )


def market_rows_to_price_points(
    rows: list[dict[str, Any]],
    *,
    timestamp_key: str = "timestamp",
    open_key: str = "open",
    high_key: str = "high",
    low_key: str = "low",
    close_key: str = "close",
    volume_key: str = "volume",
) -> list[MarketPricePoint]:
    """Convert market rows into price points."""
    validate_market_rows(rows)
    price_points: list[MarketPricePoint] = []

    for row in rows:
        price_points.append(
            build_market_price_point(
                timestamp=str(row[timestamp_key]),
                open=float(row.get(open_key, 0.0) or 0.0),
                high=float(row.get(high_key, 0.0) or 0.0),
                low=float(row.get(low_key, 0.0) or 0.0),
                close=float(row[close_key]),
                volume=float(row.get(volume_key, 0.0) or 0.0),
                metadata=dict(row.get("metadata", {})),
            ),
        )

    return price_points


def latest_market_price_from_points(price_points: list[MarketPricePoint]) -> float:
    """Return latest price from points."""
    validate_market_price_points(price_points)

    if not price_points:
        return 0.0

    return float(price_points[-1].close)


def previous_market_price_from_points(price_points: list[MarketPricePoint]) -> float:
    """Return previous price from points."""
    validate_market_price_points(price_points)

    if len(price_points) < 2:
        return 0.0

    return float(price_points[-2].close)


def calculate_market_change(
    *,
    latest_price: float,
    previous_price: float,
) -> tuple[float, float]:
    """Calculate market change and percentage."""
    validate_non_negative_float(latest_price, "Latest price")
    validate_non_negative_float(previous_price, "Previous price")

    if latest_price <= 0 or previous_price <= 0:
        return 0.0, 0.0

    change = round(float(latest_price) - float(previous_price), 6)
    change_pct = round((change / float(previous_price)) * 100, 6)
    return change, change_pct


def infer_market_trend_direction(
    *,
    change_pct: float,
    threshold_pct: float = 0.05,
) -> MarketTrendDirection:
    """Infer market trend direction from change percentage."""
    validate_number(change_pct, "Change percentage")
    validate_non_negative_float(threshold_pct, "Threshold percentage")

    if change_pct > threshold_pct:
        return MarketTrendDirection.UP

    if change_pct < -threshold_pct:
        return MarketTrendDirection.DOWN

    return MarketTrendDirection.SIDEWAYS


def build_market_overview_snapshot(
    *,
    symbol: str,
    timeframe: str = "D1",
    price_points: list[MarketPricePoint] | None = None,
    latest_price: float | None = None,
    previous_price: float | None = None,
    trend: MarketTrendDirection | str | None = None,
    session_status: MarketSessionStatus | str = MarketSessionStatus.UNKNOWN,
    provider_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> MarketOverviewSnapshot:
    """Build market overview snapshot."""
    resolved_points = price_points or []
    resolved_latest = (
        latest_market_price_from_points(resolved_points)
        if latest_price is None
        else latest_price
    )
    resolved_previous = (
        previous_market_price_from_points(resolved_points)
        if previous_price is None
        else previous_price
    )
    change, change_pct = calculate_market_change(
        latest_price=resolved_latest,
        previous_price=resolved_previous,
    )
    resolved_trend = trend or infer_market_trend_direction(change_pct=change_pct)

    return MarketOverviewSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        price_points=resolved_points,
        latest_price=resolved_latest,
        previous_price=resolved_previous,
        change=change,
        change_pct=change_pct,
        trend=resolved_trend,
        session_status=session_status,
        provider_id=provider_id,
        metadata=metadata or {},
    )


def market_rows_to_snapshot(
    *,
    symbol: str,
    rows: list[dict[str, Any]],
    timeframe: str = "D1",
    provider_id: str = "",
    session_status: MarketSessionStatus | str = MarketSessionStatus.UNKNOWN,
    metadata: dict[str, Any] | None = None,
) -> MarketOverviewSnapshot:
    """Convert market rows into snapshot."""
    return build_market_overview_snapshot(
        symbol=symbol,
        timeframe=timeframe,
        price_points=market_rows_to_price_points(rows),
        provider_id=provider_id,
        session_status=session_status,
        metadata=metadata or {},
    )


def quote_payload_to_market_snapshot(
    *,
    quote: dict[str, Any],
    timeframe: str = "live",
    provider_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> MarketOverviewSnapshot:
    """Convert quote payload into market snapshot."""
    validate_metadata(quote, "Quote")
    symbol = normalize_market_symbol(str(quote["symbol"]))
    latest_price = float(
        quote.get("price")
        or quote.get("mid")
        or quote.get("last")
        or quote.get("ask")
        or quote.get("bid")
        or 0.0,
    )
    previous_price = float(
        quote.get("previous_price")
        or quote.get("previous_close")
        or quote.get("open")
        or 0.0,
    )

    return build_market_overview_snapshot(
        symbol=symbol,
        timeframe=timeframe,
        latest_price=latest_price,
        previous_price=previous_price,
        provider_id=provider_id or str(quote.get("provider_id", "")),
        session_status=str(quote.get("session_status", MarketSessionStatus.UNKNOWN.value)),
        metadata={
            **dict(quote.get("metadata", {})),
            **(metadata or {}),
        },
    )


def market_snapshot_to_metrics(
    snapshot: MarketOverviewSnapshot,
) -> list:
    """Build market overview metrics."""
    if not isinstance(snapshot, MarketOverviewSnapshot):
        raise ValueError("Snapshot must be MarketOverviewSnapshot.")

    return [
        build_dashboard_metric(
            name="latest_price",
            label="Latest Price",
            value=round(snapshot.latest_price, 6),
            previous_value=snapshot.previous_price if snapshot.previous_price > 0 else None,
            change=snapshot.change,
            change_pct=snapshot.change_pct,
            status=DashboardStatus.READY if snapshot.has_data else DashboardStatus.EMPTY,
            metadata={
                "symbol": normalize_market_symbol(snapshot.symbol),
                "timeframe": snapshot.timeframe,
            },
        ),
        build_dashboard_metric(
            name="change_pct",
            label="Change %",
            value=round(snapshot.change_pct, 6),
            unit="%",
            status=DashboardStatus.READY if snapshot.has_data else DashboardStatus.EMPTY,
            metadata={
                "trend": normalize_market_trend_direction(snapshot.trend).value,
            },
        ),
        build_dashboard_metric(
            name="point_count",
            label="Data Points",
            value=snapshot.point_count,
            status=DashboardStatus.READY if snapshot.point_count > 0 else DashboardStatus.EMPTY,
        ),
    ]


def market_snapshot_to_chart_points(
    snapshot: MarketOverviewSnapshot,
) -> list[dict[str, Any]]:
    """Convert snapshot price points to chart points."""
    if not isinstance(snapshot, MarketOverviewSnapshot):
        raise ValueError("Snapshot must be MarketOverviewSnapshot.")

    return [
        {
            "x": point.timestamp,
            "y": point.close,
            "open": point.open,
            "high": point.high,
            "low": point.low,
            "close": point.close,
            "volume": point.volume,
        }
        for point in snapshot.price_points
    ]


def build_market_overview_widget(
    snapshot: MarketOverviewSnapshot,
) -> DashboardWidget:
    """Build market overview KPI widget."""
    if not isinstance(snapshot, MarketOverviewSnapshot):
        raise ValueError("Snapshot must be MarketOverviewSnapshot.")

    status = DashboardStatus.READY if snapshot.has_data else DashboardStatus.EMPTY
    issues = []

    if not snapshot.has_data:
        issues.append(
            build_dashboard_issue(
                code="market_data_empty",
                message="No market data is available for this symbol.",
                severity="warning",
                source="dashboard.market",
            ),
        )

    return build_dashboard_widget(
        widget_id=f"market-overview-{normalize_market_symbol(snapshot.symbol).lower()}",
        title=f"{normalize_market_symbol(snapshot.symbol)} Overview",
        widget_type=DashboardWidgetType.MARKET,
        status=status,
        size=DashboardWidgetSize.MEDIUM,
        subtitle=snapshot.timeframe,
        description="Latest market price, change, and trend.",
        data=snapshot.to_dict(),
        metrics=market_snapshot_to_metrics(snapshot),
        issues=issues,
        actions=[
            build_dashboard_widget_action(
                action_id="refresh-market",
                label="Refresh",
                action_type="refresh",
                target="market",
                payload={
                    "symbol": normalize_market_symbol(snapshot.symbol),
                    "timeframe": snapshot.timeframe,
                },
            ),
        ],
        metadata={
            "provider_id": snapshot.provider_id,
            "trend": normalize_market_trend_direction(snapshot.trend).value,
        },
    )


def build_market_price_chart_widget(
    snapshot: MarketOverviewSnapshot,
) -> DashboardWidget:
    """Build market price chart widget."""
    if not isinstance(snapshot, MarketOverviewSnapshot):
        raise ValueError("Snapshot must be MarketOverviewSnapshot.")

    chart_points = market_snapshot_to_chart_points(snapshot)

    return build_dashboard_widget(
        widget_id=f"market-chart-{normalize_market_symbol(snapshot.symbol).lower()}",
        title=f"{normalize_market_symbol(snapshot.symbol)} Price Chart",
        widget_type=DashboardWidgetType.MARKET,
        status=DashboardStatus.READY if chart_points else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.FULL,
        chart_type=DashboardChartType.LINE,
        subtitle=snapshot.timeframe,
        description="Market price chart.",
        data={
            "symbol": normalize_market_symbol(snapshot.symbol),
            "timeframe": snapshot.timeframe,
        },
        chart_series=[
            build_dashboard_chart_series(
                name="Close",
                points=chart_points,
                chart_type=DashboardChartType.LINE,
                metadata={
                    "symbol": normalize_market_symbol(snapshot.symbol),
                },
            ),
        ],
        metadata={
            "point_count": len(chart_points),
        },
    )


def build_market_table_widget(
    snapshots: list[MarketOverviewSnapshot],
) -> DashboardWidget:
    """Build market overview table widget."""
    validate_market_snapshots(snapshots)

    columns: list[DashboardTableColumn] = [
        build_dashboard_table_column(key="symbol", label="Symbol"),
        build_dashboard_table_column(key="timeframe", label="Timeframe"),
        build_dashboard_table_column(key="latest_price", label="Latest Price", data_type="number"),
        build_dashboard_table_column(key="change", label="Change", data_type="number"),
        build_dashboard_table_column(key="change_pct", label="Change %", data_type="number"),
        build_dashboard_table_column(key="trend", label="Trend"),
        build_dashboard_table_column(key="session_status", label="Session"),
    ]
    rows = [
        {
            "symbol": normalize_market_symbol(snapshot.symbol),
            "timeframe": snapshot.timeframe,
            "latest_price": snapshot.latest_price,
            "change": snapshot.change,
            "change_pct": snapshot.change_pct,
            "trend": normalize_market_trend_direction(snapshot.trend).value,
            "session_status": normalize_market_session_status(snapshot.session_status).value,
        }
        for snapshot in snapshots
    ]

    return build_dashboard_widget(
        widget_id="market-overview-table",
        title="Market Overview Table",
        widget_type=DashboardWidgetType.MARKET,
        status=DashboardStatus.READY if rows else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.FULL,
        description="Multi-symbol market overview.",
        table_columns=columns,
        table_rows=rows,
        metadata={
            "symbol_count": len(rows),
        },
    )


def build_market_overview_card(
    snapshot: MarketOverviewSnapshot,
) -> DashboardCard:
    """Build market overview card."""
    if not isinstance(snapshot, MarketOverviewSnapshot):
        raise ValueError("Snapshot must be MarketOverviewSnapshot.")

    metrics = market_snapshot_to_metrics(snapshot)
    overview_widget = build_market_overview_widget(snapshot)
    chart_widget = build_market_price_chart_widget(snapshot)

    return build_dashboard_card(
        card_id=f"market-card-{normalize_market_symbol(snapshot.symbol).lower()}",
        title=f"{normalize_market_symbol(snapshot.symbol)} Market",
        status=DashboardStatus.READY if snapshot.has_data else DashboardStatus.EMPTY,
        subtitle=f"{snapshot.timeframe} · {normalize_market_trend_direction(snapshot.trend).value}",
        primary_metric=metrics[0],
        metrics=metrics[1:],
        widgets=[overview_widget, chart_widget],
        data=snapshot.to_dict(),
        metadata={
            "provider_id": snapshot.provider_id,
        },
    )


def build_market_overview_payload(
    *,
    snapshots: list[MarketOverviewSnapshot],
    payload_id: str = "market-overview",
    title: str = "Market Overview",
) -> DashboardPayload:
    """Build market overview dashboard payload."""
    validate_market_snapshots(snapshots)

    if not snapshots:
        return build_dashboard_payload(
            payload_id=payload_id,
            title=title,
            status=DashboardStatus.EMPTY,
            components=[
                build_dashboard_component(
                    component_id="market-empty",
                    title="No Market Data",
                    component_type="status",
                    status=DashboardStatus.EMPTY,
                    description="No market snapshots are available.",
                ),
            ],
        )

    cards = [build_market_overview_card(snapshot) for snapshot in snapshots]
    table_widget = build_market_table_widget(snapshots)

    latest_prices = [
        snapshot.latest_price
        for snapshot in snapshots
        if snapshot.latest_price > 0
    ]

    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=DashboardStatus.READY,
        refresh_mode="auto",
        components=[
            *[card_to_dashboard_component(card) for card in cards],
            widget_to_dashboard_component(table_widget),
        ],
        metrics=[
            build_dashboard_metric(
                name="symbol_count",
                label="Symbols",
                value=len(snapshots),
            ),
            build_dashboard_metric(
                name="average_latest_price",
                label="Average Latest Price",
                value=round(sum(latest_prices) / len(latest_prices), 6)
                if latest_prices
                else 0.0,
            ),
        ],
        data={
            "symbols": [normalize_market_symbol(snapshot.symbol) for snapshot in snapshots],
            "snapshots": [snapshot.to_dict() for snapshot in snapshots],
        },
        metadata={
            "source": "dashboard.market",
        },
    )


def validate_market_snapshots(
    snapshots: list[MarketOverviewSnapshot],
) -> list[MarketOverviewSnapshot]:
    """Validate market snapshots."""
    if not isinstance(snapshots, list):
        raise ValueError("Snapshots must be a list.")

    for snapshot in snapshots:
        if not isinstance(snapshot, MarketOverviewSnapshot):
            raise ValueError("Snapshots must contain MarketOverviewSnapshot objects.")

    return snapshots