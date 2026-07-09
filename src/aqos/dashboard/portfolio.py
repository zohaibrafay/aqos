"""
AQOS portfolio and risk dashboard payloads.

This module prepares frontend-ready portfolio, position, PnL, exposure, and
risk widgets/cards/payloads for dashboards and external clients.
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
from aqos.dashboard.signals import (
    validate_non_negative_integer,
    validate_percentage,
)
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


class PortfolioPositionSide(str, Enum):
    """Supported portfolio position sides."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class PortfolioRiskLevel(str, Enum):
    """Supported portfolio risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PortfolioPositionItem:
    """Frontend-ready portfolio position item."""

    position_id: str
    symbol: str
    side: PortfolioPositionSide | str
    quantity: float = 0.0
    average_price: float = 0.0
    market_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    allocation_pct: float = 0.0
    opened_at: str = ""
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.position_id, "Position ID")
        normalize_market_symbol(self.symbol)
        normalize_portfolio_position_side(self.side)
        validate_non_negative_float(self.quantity, "Quantity")
        validate_non_negative_float(self.average_price, "Average price")
        validate_non_negative_float(self.market_price, "Market price")
        validate_number(self.market_value, "Market value")
        validate_number(self.unrealized_pnl, "Unrealized PnL")
        validate_number(self.realized_pnl, "Realized PnL")
        validate_percentage(self.allocation_pct, "Allocation percentage")
        validate_string(self.opened_at, "Opened at")
        validate_string(self.updated_at, "Updated at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def open(self) -> bool:
        """Return whether position is open."""
        return normalize_portfolio_position_side(self.side) != PortfolioPositionSide.FLAT and self.quantity > 0

    @property
    def total_pnl(self) -> float:
        """Return total PnL."""
        return round(float(self.unrealized_pnl) + float(self.realized_pnl), 6)

    @property
    def pnl_pct(self) -> float:
        """Return PnL percentage."""
        basis = self.quantity * self.average_price

        if basis <= 0:
            return 0.0

        return round((self.total_pnl / basis) * 100, 6)

    def to_dict(self) -> dict[str, Any]:
        """Convert portfolio position into dictionary."""
        return {
            "position_id": self.position_id.strip(),
            "symbol": normalize_market_symbol(self.symbol),
            "side": normalize_portfolio_position_side(self.side).value,
            "quantity": float(self.quantity),
            "average_price": float(self.average_price),
            "market_price": float(self.market_price),
            "market_value": float(self.market_value),
            "unrealized_pnl": float(self.unrealized_pnl),
            "realized_pnl": float(self.realized_pnl),
            "total_pnl": self.total_pnl,
            "pnl_pct": self.pnl_pct,
            "allocation_pct": float(self.allocation_pct),
            "opened_at": self.opened_at.strip(),
            "updated_at": self.updated_at.strip(),
            "open": self.open,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class PortfolioRiskSnapshot:
    """Frontend-ready portfolio risk snapshot."""

    portfolio_id: str
    account_id: str = ""
    currency: str = "USD"
    cash_balance: float = 0.0
    equity: float = 0.0
    buying_power: float = 0.0
    total_market_value: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    exposure_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    daily_var: float = 0.0
    risk_level: PortfolioRiskLevel | str = PortfolioRiskLevel.UNKNOWN
    positions: list[PortfolioPositionItem] = field(default_factory=list)
    pnl_history: list[dict[str, Any]] = field(default_factory=list)
    updated_at: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.portfolio_id, "Portfolio ID")
        validate_string(self.account_id, "Account ID")
        validate_non_empty_string(self.currency, "Currency")
        validate_non_negative_float(self.cash_balance, "Cash balance")
        validate_non_negative_float(self.equity, "Equity")
        validate_non_negative_float(self.buying_power, "Buying power")
        validate_non_negative_float(self.total_market_value, "Total market value")
        validate_number(self.realized_pnl, "Realized PnL")
        validate_number(self.unrealized_pnl, "Unrealized PnL")
        validate_percentage(self.exposure_pct, "Exposure percentage")
        validate_percentage(self.max_drawdown_pct, "Max drawdown percentage")
        validate_non_negative_float(self.daily_var, "Daily VaR")
        normalize_portfolio_risk_level(self.risk_level)
        validate_portfolio_positions(self.positions)
        validate_pnl_history(self.pnl_history)
        validate_string(self.updated_at, "Updated at")
        validate_metadata(self.metadata, "Metadata")

    @property
    def total_pnl(self) -> float:
        """Return total PnL."""
        return round(float(self.realized_pnl) + float(self.unrealized_pnl), 6)

    @property
    def position_count(self) -> int:
        """Return position count."""
        return len(self.positions)

    @property
    def open_position_count(self) -> int:
        """Return open position count."""
        return len([position for position in self.positions if position.open])

    @property
    def healthy(self) -> bool:
        """Return whether portfolio risk is healthy."""
        return normalize_portfolio_risk_level(self.risk_level) in {
            PortfolioRiskLevel.LOW,
            PortfolioRiskLevel.MEDIUM,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert portfolio risk snapshot into dictionary."""
        return {
            "portfolio_id": self.portfolio_id.strip(),
            "account_id": self.account_id.strip(),
            "currency": self.currency.strip().upper(),
            "cash_balance": float(self.cash_balance),
            "equity": float(self.equity),
            "buying_power": float(self.buying_power),
            "total_market_value": float(self.total_market_value),
            "realized_pnl": float(self.realized_pnl),
            "unrealized_pnl": float(self.unrealized_pnl),
            "total_pnl": self.total_pnl,
            "exposure_pct": float(self.exposure_pct),
            "max_drawdown_pct": float(self.max_drawdown_pct),
            "daily_var": float(self.daily_var),
            "risk_level": normalize_portfolio_risk_level(self.risk_level).value,
            "healthy": self.healthy,
            "positions": [position.to_dict() for position in self.positions],
            "position_count": self.position_count,
            "open_position_count": self.open_position_count,
            "pnl_history": [dict(point) for point in self.pnl_history],
            "updated_at": self.updated_at.strip(),
            "metadata": dict(self.metadata),
        }


def normalize_portfolio_position_side(
    side: PortfolioPositionSide | str,
) -> PortfolioPositionSide:
    """Normalize portfolio position side."""
    if isinstance(side, PortfolioPositionSide):
        return side

    normalized = validate_non_empty_string(side, "Position side").lower()

    try:
        return PortfolioPositionSide(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PortfolioPositionSide)
        raise ValueError(
            f"Invalid position side '{side}'. Valid sides: {valid}.",
        ) from exc


def normalize_portfolio_risk_level(
    risk_level: PortfolioRiskLevel | str,
) -> PortfolioRiskLevel:
    """Normalize portfolio risk level."""
    if isinstance(risk_level, PortfolioRiskLevel):
        return risk_level

    normalized = validate_non_empty_string(risk_level, "Risk level").lower()

    try:
        return PortfolioRiskLevel(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in PortfolioRiskLevel)
        raise ValueError(
            f"Invalid risk level '{risk_level}'. Valid levels: {valid}.",
        ) from exc


def validate_portfolio_positions(
    positions: list[PortfolioPositionItem],
) -> list[PortfolioPositionItem]:
    """Validate portfolio positions."""
    if not isinstance(positions, list):
        raise ValueError("Positions must be a list.")

    for position in positions:
        if not isinstance(position, PortfolioPositionItem):
            raise ValueError("Positions must contain PortfolioPositionItem objects.")

    return positions


def validate_portfolio_snapshots(
    snapshots: list[PortfolioRiskSnapshot],
) -> list[PortfolioRiskSnapshot]:
    """Validate portfolio snapshots."""
    if not isinstance(snapshots, list):
        raise ValueError("Snapshots must be a list.")

    for snapshot in snapshots:
        if not isinstance(snapshot, PortfolioRiskSnapshot):
            raise ValueError("Snapshots must contain PortfolioRiskSnapshot objects.")

    return snapshots


def validate_pnl_history(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate PnL history."""
    if not isinstance(history, list):
        raise ValueError("PnL history must be a list.")

    for point in history:
        validate_metadata(point, "PnL history point")

    return history


def infer_portfolio_risk_level(
    *,
    exposure_pct: float,
    max_drawdown_pct: float,
    daily_var: float = 0.0,
) -> PortfolioRiskLevel:
    """Infer portfolio risk level from exposure/drawdown/VaR."""
    validate_percentage(exposure_pct, "Exposure percentage")
    validate_percentage(max_drawdown_pct, "Max drawdown percentage")
    validate_non_negative_float(daily_var, "Daily VaR")

    if max_drawdown_pct >= 30 or exposure_pct >= 95:
        return PortfolioRiskLevel.CRITICAL

    if max_drawdown_pct >= 18 or exposure_pct >= 80 or daily_var >= 10:
        return PortfolioRiskLevel.HIGH

    if max_drawdown_pct >= 8 or exposure_pct >= 50 or daily_var >= 4:
        return PortfolioRiskLevel.MEDIUM

    return PortfolioRiskLevel.LOW


def build_portfolio_position_item(
    *,
    position_id: str,
    symbol: str,
    side: PortfolioPositionSide | str,
    quantity: float = 0.0,
    average_price: float = 0.0,
    market_price: float = 0.0,
    market_value: float | None = None,
    unrealized_pnl: float = 0.0,
    realized_pnl: float = 0.0,
    allocation_pct: float = 0.0,
    opened_at: str = "",
    updated_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> PortfolioPositionItem:
    """Build portfolio position item."""
    resolved_market_value = (
        round(float(quantity) * float(market_price), 6)
        if market_value is None
        else float(market_value)
    )

    return PortfolioPositionItem(
        position_id=position_id,
        symbol=symbol,
        side=side,
        quantity=quantity,
        average_price=average_price,
        market_price=market_price,
        market_value=resolved_market_value,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=realized_pnl,
        allocation_pct=allocation_pct,
        opened_at=opened_at,
        updated_at=updated_at,
        metadata=metadata or {},
    )


def position_dict_to_portfolio_item(position: dict[str, Any]) -> PortfolioPositionItem:
    """Convert raw position dictionary into portfolio item."""
    validate_metadata(position, "Position")

    return build_portfolio_position_item(
        position_id=str(position.get("position_id") or position.get("id") or ""),
        symbol=str(position["symbol"]),
        side=str(position.get("side", "flat")),
        quantity=float(position.get("quantity", 0.0) or 0.0),
        average_price=float(position.get("average_price", position.get("avg_price", 0.0)) or 0.0),
        market_price=float(position.get("market_price", position.get("price", 0.0)) or 0.0),
        market_value=float(position.get("market_value", 0.0) or 0.0)
        if "market_value" in position
        else None,
        unrealized_pnl=float(position.get("unrealized_pnl", 0.0) or 0.0),
        realized_pnl=float(position.get("realized_pnl", 0.0) or 0.0),
        allocation_pct=float(position.get("allocation_pct", 0.0) or 0.0),
        opened_at=str(position.get("opened_at", "")),
        updated_at=str(position.get("updated_at", "")),
        metadata=dict(position.get("metadata", {})),
    )


def position_dicts_to_portfolio_items(
    positions: list[dict[str, Any]],
) -> list[PortfolioPositionItem]:
    """Convert raw position dictionaries into portfolio items."""
    if not isinstance(positions, list):
        raise ValueError("Positions must be a list.")

    return [
        position_dict_to_portfolio_item(position)
        for position in positions
    ]


def build_portfolio_risk_snapshot(
    *,
    portfolio_id: str,
    account_id: str = "",
    currency: str = "USD",
    cash_balance: float = 0.0,
    equity: float = 0.0,
    buying_power: float = 0.0,
    total_market_value: float | None = None,
    realized_pnl: float = 0.0,
    unrealized_pnl: float = 0.0,
    exposure_pct: float | None = None,
    max_drawdown_pct: float = 0.0,
    daily_var: float = 0.0,
    risk_level: PortfolioRiskLevel | str | None = None,
    positions: list[PortfolioPositionItem] | None = None,
    pnl_history: list[dict[str, Any]] | None = None,
    updated_at: str = "",
    metadata: dict[str, Any] | None = None,
) -> PortfolioRiskSnapshot:
    """Build portfolio risk snapshot."""
    resolved_positions = positions or []
    resolved_total_market_value = (
        round(sum(abs(position.market_value) for position in resolved_positions), 6)
        if total_market_value is None
        else float(total_market_value)
    )
    resolved_exposure_pct = (
        round((resolved_total_market_value / equity) * 100, 6)
        if exposure_pct is None and equity > 0
        else float(exposure_pct or 0.0)
    )
    resolved_risk_level = risk_level or infer_portfolio_risk_level(
        exposure_pct=resolved_exposure_pct,
        max_drawdown_pct=max_drawdown_pct,
        daily_var=daily_var,
    )

    return PortfolioRiskSnapshot(
        portfolio_id=portfolio_id,
        account_id=account_id,
        currency=currency,
        cash_balance=cash_balance,
        equity=equity,
        buying_power=buying_power,
        total_market_value=resolved_total_market_value,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        exposure_pct=resolved_exposure_pct,
        max_drawdown_pct=max_drawdown_pct,
        daily_var=daily_var,
        risk_level=resolved_risk_level,
        positions=resolved_positions,
        pnl_history=pnl_history or [],
        updated_at=updated_at,
        metadata=metadata or {},
    )


def account_payload_to_portfolio_snapshot(
    *,
    account: dict[str, Any],
    positions: list[dict[str, Any]] | None = None,
    portfolio_id: str = "portfolio",
    pnl_history: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> PortfolioRiskSnapshot:
    """Convert account/positions payload into portfolio snapshot."""
    validate_metadata(account, "Account")

    portfolio_positions = position_dicts_to_portfolio_items(positions or [])

    return build_portfolio_risk_snapshot(
        portfolio_id=portfolio_id,
        account_id=str(account.get("account_id", "")),
        currency=str(account.get("currency", "USD")),
        cash_balance=float(account.get("cash_balance", 0.0) or 0.0),
        equity=float(account.get("equity", account.get("cash_balance", 0.0)) or 0.0),
        buying_power=float(account.get("buying_power", 0.0) or 0.0),
        realized_pnl=float(account.get("realized_pnl", 0.0) or 0.0),
        unrealized_pnl=float(account.get("unrealized_pnl", 0.0) or 0.0),
        positions=portfolio_positions,
        pnl_history=pnl_history or [],
        updated_at=str(account.get("updated_at", "")),
        metadata={
            **dict(account.get("metadata", {})),
            **(metadata or {}),
        },
    )


def portfolio_snapshot_to_metrics(
    snapshot: PortfolioRiskSnapshot,
) -> list:
    """Build portfolio summary metrics."""
    if not isinstance(snapshot, PortfolioRiskSnapshot):
        raise ValueError("Snapshot must be PortfolioRiskSnapshot.")

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if normalize_portfolio_risk_level(snapshot.risk_level) == PortfolioRiskLevel.CRITICAL:
        status = DashboardStatus.ERROR

    return [
        build_dashboard_metric(name="equity", label="Equity", value=round(snapshot.equity, 6), unit=snapshot.currency),
        build_dashboard_metric(name="cash_balance", label="Cash", value=round(snapshot.cash_balance, 6), unit=snapshot.currency),
        build_dashboard_metric(name="total_pnl", label="Total PnL", value=round(snapshot.total_pnl, 6), unit=snapshot.currency),
        build_dashboard_metric(name="exposure_pct", label="Exposure", value=round(snapshot.exposure_pct, 6), unit="%", status=status),
        build_dashboard_metric(name="max_drawdown_pct", label="Max Drawdown", value=round(snapshot.max_drawdown_pct, 6), unit="%", status=status),
        build_dashboard_metric(name="open_positions", label="Open Positions", value=snapshot.open_position_count),
    ]


def build_portfolio_summary_widget(
    snapshot: PortfolioRiskSnapshot,
) -> DashboardWidget:
    """Build portfolio summary widget."""
    if not isinstance(snapshot, PortfolioRiskSnapshot):
        raise ValueError("Snapshot must be PortfolioRiskSnapshot.")

    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if normalize_portfolio_risk_level(snapshot.risk_level) == PortfolioRiskLevel.CRITICAL:
        status = DashboardStatus.ERROR

    issues = []

    if not snapshot.healthy:
        issues.append(
            build_dashboard_issue(
                code="portfolio_risk_elevated",
                message="Portfolio risk level is elevated.",
                severity="warning" if status == DashboardStatus.WARNING else "error",
                source="dashboard.portfolio",
                metadata={
                    "risk_level": normalize_portfolio_risk_level(snapshot.risk_level).value,
                },
            ),
        )

    return build_dashboard_widget(
        widget_id=f"portfolio-summary-{snapshot.portfolio_id.strip()}",
        title="Portfolio Summary",
        widget_type=DashboardWidgetType.PORTFOLIO,
        status=status,
        size=DashboardWidgetSize.LARGE,
        description="Portfolio equity, cash, PnL, and exposure.",
        data=snapshot.to_dict(),
        metrics=portfolio_snapshot_to_metrics(snapshot),
        issues=issues,
        actions=[
            build_dashboard_widget_action(
                action_id="refresh-portfolio",
                label="Refresh",
                action_type="refresh",
                target="portfolio",
                payload={
                    "portfolio_id": snapshot.portfolio_id,
                },
            ),
        ],
        metadata={
            "risk_level": normalize_portfolio_risk_level(snapshot.risk_level).value,
        },
    )


def build_portfolio_positions_table_widget(
    snapshot: PortfolioRiskSnapshot,
) -> DashboardWidget:
    """Build portfolio positions table widget."""
    if not isinstance(snapshot, PortfolioRiskSnapshot):
        raise ValueError("Snapshot must be PortfolioRiskSnapshot.")

    columns = [
        build_dashboard_table_column(key="symbol", label="Symbol"),
        build_dashboard_table_column(key="side", label="Side"),
        build_dashboard_table_column(key="quantity", label="Quantity", data_type="number"),
        build_dashboard_table_column(key="average_price", label="Average Price", data_type="number"),
        build_dashboard_table_column(key="market_price", label="Market Price", data_type="number"),
        build_dashboard_table_column(key="market_value", label="Market Value", data_type="number"),
        build_dashboard_table_column(key="total_pnl", label="Total PnL", data_type="number"),
        build_dashboard_table_column(key="pnl_pct", label="PnL %", data_type="number"),
        build_dashboard_table_column(key="allocation_pct", label="Allocation %", data_type="number"),
    ]

    rows = [position.to_dict() for position in snapshot.positions]

    return build_dashboard_widget(
        widget_id=f"portfolio-positions-{snapshot.portfolio_id.strip()}",
        title="Positions",
        widget_type=DashboardWidgetType.PORTFOLIO,
        status=DashboardStatus.READY if rows else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.FULL,
        description="Open and historical portfolio positions.",
        table_columns=columns,
        table_rows=rows,
        metadata={
            "position_count": len(rows),
            "open_position_count": snapshot.open_position_count,
        },
    )


def build_portfolio_risk_widget(
    snapshot: PortfolioRiskSnapshot,
) -> DashboardWidget:
    """Build portfolio risk widget."""
    if not isinstance(snapshot, PortfolioRiskSnapshot):
        raise ValueError("Snapshot must be PortfolioRiskSnapshot.")

    risk_level = normalize_portfolio_risk_level(snapshot.risk_level)
    status = DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING

    if risk_level == PortfolioRiskLevel.CRITICAL:
        status = DashboardStatus.ERROR

    return build_dashboard_widget(
        widget_id=f"portfolio-risk-{snapshot.portfolio_id.strip()}",
        title="Risk Overview",
        widget_type=DashboardWidgetType.RISK,
        status=status,
        size=DashboardWidgetSize.MEDIUM,
        chart_type=DashboardChartType.GAUGE,
        description="Exposure, drawdown, and portfolio risk level.",
        data={
            "risk_level": risk_level.value,
            "exposure_pct": snapshot.exposure_pct,
            "max_drawdown_pct": snapshot.max_drawdown_pct,
            "daily_var": snapshot.daily_var,
        },
        metrics=[
            build_dashboard_metric(name="exposure_pct", label="Exposure", value=snapshot.exposure_pct, unit="%", status=status),
            build_dashboard_metric(name="max_drawdown_pct", label="Max Drawdown", value=snapshot.max_drawdown_pct, unit="%", status=status),
            build_dashboard_metric(name="daily_var", label="Daily VaR", value=snapshot.daily_var, unit=snapshot.currency, status=status),
        ],
        chart_series=[
            build_dashboard_chart_series(
                name="Risk Gauge",
                points=[
                    {"label": "Exposure", "value": snapshot.exposure_pct},
                    {"label": "Max Drawdown", "value": snapshot.max_drawdown_pct},
                ],
                chart_type=DashboardChartType.GAUGE,
            ),
        ],
        metadata={
            "risk_level": risk_level.value,
        },
    )


def build_portfolio_pnl_chart_widget(
    snapshot: PortfolioRiskSnapshot,
) -> DashboardWidget:
    """Build portfolio PnL chart widget."""
    if not isinstance(snapshot, PortfolioRiskSnapshot):
        raise ValueError("Snapshot must be PortfolioRiskSnapshot.")

    return build_dashboard_widget(
        widget_id=f"portfolio-pnl-{snapshot.portfolio_id.strip()}",
        title="PnL History",
        widget_type=DashboardWidgetType.PORTFOLIO,
        status=DashboardStatus.READY if snapshot.pnl_history else DashboardStatus.EMPTY,
        size=DashboardWidgetSize.FULL,
        chart_type=DashboardChartType.LINE,
        description="Portfolio PnL history.",
        chart_series=[
            build_dashboard_chart_series(
                name="PnL",
                points=[dict(point) for point in snapshot.pnl_history],
                chart_type=DashboardChartType.LINE,
            ),
        ],
        metadata={
            "point_count": len(snapshot.pnl_history),
        },
    )


def build_portfolio_risk_card(
    snapshot: PortfolioRiskSnapshot,
) -> DashboardCard:
    """Build portfolio/risk dashboard card."""
    if not isinstance(snapshot, PortfolioRiskSnapshot):
        raise ValueError("Snapshot must be PortfolioRiskSnapshot.")

    summary_widget = build_portfolio_summary_widget(snapshot)
    positions_widget = build_portfolio_positions_table_widget(snapshot)
    risk_widget = build_portfolio_risk_widget(snapshot)
    pnl_widget = build_portfolio_pnl_chart_widget(snapshot)

    return build_dashboard_card(
        card_id=f"portfolio-risk-card-{snapshot.portfolio_id.strip()}",
        title="Portfolio & Risk",
        status=DashboardStatus.READY if snapshot.healthy else DashboardStatus.WARNING,
        subtitle=normalize_portfolio_risk_level(snapshot.risk_level).value,
        primary_metric=build_dashboard_metric(
            name="equity",
            label="Equity",
            value=round(snapshot.equity, 6),
            unit=snapshot.currency,
        ),
        metrics=[
            build_dashboard_metric(name="total_pnl", label="Total PnL", value=snapshot.total_pnl, unit=snapshot.currency),
            build_dashboard_metric(name="exposure_pct", label="Exposure", value=snapshot.exposure_pct, unit="%"),
            build_dashboard_metric(name="position_count", label="Positions", value=snapshot.position_count),
        ],
        widgets=[
            summary_widget,
            risk_widget,
            positions_widget,
            pnl_widget,
        ],
        data=snapshot.to_dict(),
        metadata={
            "portfolio_id": snapshot.portfolio_id,
            "risk_level": normalize_portfolio_risk_level(snapshot.risk_level).value,
        },
    )


def build_portfolio_risk_payload(
    *,
    snapshots: list[PortfolioRiskSnapshot],
    payload_id: str = "portfolio-risk-dashboard",
    title: str = "Portfolio & Risk Dashboard",
) -> DashboardPayload:
    """Build portfolio and risk dashboard payload."""
    validate_portfolio_snapshots(snapshots)

    if not snapshots:
        return build_dashboard_payload(
            payload_id=payload_id,
            title=title,
            status=DashboardStatus.EMPTY,
            components=[
                build_dashboard_component(
                    component_id="portfolio-empty",
                    title="No Portfolio Data",
                    component_type="status",
                    status=DashboardStatus.EMPTY,
                    description="No portfolio snapshots are available.",
                ),
            ],
        )

    cards = [build_portfolio_risk_card(snapshot) for snapshot in snapshots]
    all_positions = [
        position
        for snapshot in snapshots
        for position in snapshot.positions
    ]

    return build_dashboard_payload(
        payload_id=payload_id,
        title=title,
        status=DashboardStatus.READY,
        refresh_mode="auto",
        components=[
            *[card_to_dashboard_component(card) for card in cards],
            *[
                widget_to_dashboard_component(build_portfolio_risk_widget(snapshot))
                for snapshot in snapshots
            ],
        ],
        metrics=[
            build_dashboard_metric(name="portfolio_count", label="Portfolios", value=len(snapshots)),
            build_dashboard_metric(name="position_count", label="Positions", value=len(all_positions)),
            build_dashboard_metric(
                name="total_equity",
                label="Total Equity",
                value=round(sum(snapshot.equity for snapshot in snapshots), 6),
            ),
            build_dashboard_metric(
                name="total_pnl",
                label="Total PnL",
                value=round(sum(snapshot.total_pnl for snapshot in snapshots), 6),
            ),
        ],
        data={
            "portfolios": [snapshot.to_dict() for snapshot in snapshots],
            "positions": [position.to_dict() for position in all_positions],
        },
        metadata={
            "source": "dashboard.portfolio",
        },
    )