"""
AQOS dashboard widget and card contracts.

This module defines frontend-ready widget, card, action, table, and chart
contracts used by AQOS dashboards and external UI clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aqos.dashboard.base import (
    DashboardComponent,
    DashboardComponentType,
    DashboardIssue,
    DashboardMetric,
    DashboardStatus,
    build_dashboard_component,
    normalize_dashboard_status,
    validate_dashboard_issues,
    validate_dashboard_metrics,
    validate_metadata,
    validate_non_empty_string,
    validate_string,
)


class DashboardWidgetType(str, Enum):
    """Supported dashboard widget types."""

    KPI = "kpi"
    MARKET = "market"
    SIGNAL = "signal"
    STRATEGY = "strategy"
    PORTFOLIO = "portfolio"
    RISK = "risk"
    BROKER = "broker"
    PROVIDER = "provider"
    ALERT = "alert"
    CUSTOM = "custom"


class DashboardWidgetSize(str, Enum):
    """Supported dashboard widget sizes."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    FULL = "full"


class DashboardChartType(str, Enum):
    """Supported dashboard chart types."""

    NONE = "none"
    LINE = "line"
    BAR = "bar"
    AREA = "area"
    PIE = "pie"
    CANDLESTICK = "candlestick"
    GAUGE = "gauge"
    SCATTER = "scatter"


class DashboardActionType(str, Enum):
    """Supported dashboard action types."""

    LINK = "link"
    REFRESH = "refresh"
    API = "api"
    MODAL = "modal"
    DOWNLOAD = "download"


@dataclass(frozen=True)
class DashboardWidgetAction:
    """Dashboard widget action."""

    action_id: str
    label: str
    action_type: DashboardActionType | str
    target: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    disabled: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.action_id, "Action ID")
        validate_non_empty_string(self.label, "Action label")
        normalize_dashboard_action_type(self.action_type)
        validate_string(self.target, "Target")
        validate_metadata(self.payload, "Payload")

        if not isinstance(self.disabled, bool):
            raise ValueError("Disabled must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    @property
    def enabled(self) -> bool:
        """Return whether action is enabled."""
        return not self.disabled

    def to_dict(self) -> dict[str, Any]:
        """Convert action into dictionary."""
        return {
            "action_id": self.action_id.strip(),
            "label": self.label.strip(),
            "action_type": normalize_dashboard_action_type(self.action_type).value,
            "target": self.target.strip(),
            "payload": dict(self.payload),
            "disabled": self.disabled,
            "enabled": self.enabled,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardTableColumn:
    """Dashboard table column contract."""

    key: str
    label: str
    data_type: str = "string"
    sortable: bool = True
    visible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.key, "Column key")
        validate_non_empty_string(self.label, "Column label")
        validate_non_empty_string(self.data_type, "Column data type")

        if not isinstance(self.sortable, bool):
            raise ValueError("Sortable must be a boolean.")

        if not isinstance(self.visible, bool):
            raise ValueError("Visible must be a boolean.")

        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert table column into dictionary."""
        return {
            "key": self.key.strip(),
            "label": self.label.strip(),
            "data_type": self.data_type.strip(),
            "sortable": self.sortable,
            "visible": self.visible,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardChartSeries:
    """Dashboard chart series contract."""

    name: str
    points: list[dict[str, Any]] = field(default_factory=list)
    chart_type: DashboardChartType | str = DashboardChartType.LINE
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.name, "Series name")
        validate_chart_points(self.points)
        normalize_dashboard_chart_type(self.chart_type)
        validate_metadata(self.metadata, "Metadata")

    @property
    def point_count(self) -> int:
        """Return point count."""
        return len(self.points)

    def to_dict(self) -> dict[str, Any]:
        """Convert chart series into dictionary."""
        return {
            "name": self.name.strip(),
            "points": [dict(point) for point in self.points],
            "chart_type": normalize_dashboard_chart_type(self.chart_type).value,
            "point_count": self.point_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardWidget:
    """Dashboard widget contract."""

    widget_id: str
    title: str
    widget_type: DashboardWidgetType | str
    status: DashboardStatus | str = DashboardStatus.READY
    size: DashboardWidgetSize | str = DashboardWidgetSize.MEDIUM
    chart_type: DashboardChartType | str = DashboardChartType.NONE
    subtitle: str = ""
    description: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    metrics: list[DashboardMetric] = field(default_factory=list)
    issues: list[DashboardIssue] = field(default_factory=list)
    actions: list[DashboardWidgetAction] = field(default_factory=list)
    table_columns: list[DashboardTableColumn] = field(default_factory=list)
    table_rows: list[dict[str, Any]] = field(default_factory=list)
    chart_series: list[DashboardChartSeries] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.widget_id, "Widget ID")
        validate_non_empty_string(self.title, "Widget title")
        normalize_dashboard_widget_type(self.widget_type)
        normalize_dashboard_status(self.status)
        normalize_dashboard_widget_size(self.size)
        normalize_dashboard_chart_type(self.chart_type)
        validate_string(self.subtitle, "Subtitle")
        validate_string(self.description, "Description")
        validate_metadata(self.data, "Data")
        validate_dashboard_metrics(self.metrics)
        validate_dashboard_issues(self.issues)
        validate_dashboard_widget_actions(self.actions)
        validate_dashboard_table_columns(self.table_columns)
        validate_table_rows(self.table_rows)
        validate_dashboard_chart_series(self.chart_series)
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether widget is healthy."""
        return normalize_dashboard_status(self.status) == DashboardStatus.READY

    @property
    def metric_count(self) -> int:
        """Return metric count."""
        return len(self.metrics)

    @property
    def issue_count(self) -> int:
        """Return issue count."""
        return len(self.issues)

    @property
    def action_count(self) -> int:
        """Return action count."""
        return len(self.actions)

    @property
    def row_count(self) -> int:
        """Return table row count."""
        return len(self.table_rows)

    @property
    def series_count(self) -> int:
        """Return chart series count."""
        return len(self.chart_series)

    def to_dict(self) -> dict[str, Any]:
        """Convert widget into dictionary."""
        return {
            "widget_id": self.widget_id.strip(),
            "title": self.title.strip(),
            "widget_type": normalize_dashboard_widget_type(self.widget_type).value,
            "status": normalize_dashboard_status(self.status).value,
            "healthy": self.healthy,
            "size": normalize_dashboard_widget_size(self.size).value,
            "chart_type": normalize_dashboard_chart_type(self.chart_type).value,
            "subtitle": self.subtitle.strip(),
            "description": self.description.strip(),
            "data": dict(self.data),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "issues": [issue.to_dict() for issue in self.issues],
            "actions": [action.to_dict() for action in self.actions],
            "table_columns": [column.to_dict() for column in self.table_columns],
            "table_rows": [dict(row) for row in self.table_rows],
            "chart_series": [series.to_dict() for series in self.chart_series],
            "metric_count": self.metric_count,
            "issue_count": self.issue_count,
            "action_count": self.action_count,
            "row_count": self.row_count,
            "series_count": self.series_count,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DashboardCard:
    """Dashboard card contract."""

    card_id: str
    title: str
    status: DashboardStatus | str = DashboardStatus.READY
    subtitle: str = ""
    primary_metric: DashboardMetric | None = None
    metrics: list[DashboardMetric] = field(default_factory=list)
    widgets: list[DashboardWidget] = field(default_factory=list)
    actions: list[DashboardWidgetAction] = field(default_factory=list)
    issues: list[DashboardIssue] = field(default_factory=list)
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.card_id, "Card ID")
        validate_non_empty_string(self.title, "Card title")
        normalize_dashboard_status(self.status)
        validate_string(self.subtitle, "Subtitle")

        if self.primary_metric is not None and not isinstance(self.primary_metric, DashboardMetric):
            raise ValueError("Primary metric must be DashboardMetric.")

        validate_dashboard_metrics(self.metrics)
        validate_dashboard_widgets(self.widgets)
        validate_dashboard_widget_actions(self.actions)
        validate_dashboard_issues(self.issues)
        validate_metadata(self.data, "Data")
        validate_metadata(self.metadata, "Metadata")

    @property
    def healthy(self) -> bool:
        """Return whether card is healthy."""
        return normalize_dashboard_status(self.status) == DashboardStatus.READY

    @property
    def metric_count(self) -> int:
        """Return metric count."""
        return len(self.metrics) + (1 if self.primary_metric is not None else 0)

    @property
    def widget_count(self) -> int:
        """Return widget count."""
        return len(self.widgets)

    @property
    def issue_count(self) -> int:
        """Return issue count including nested widgets."""
        return len(self.issues) + sum(widget.issue_count for widget in self.widgets)

    def to_dict(self) -> dict[str, Any]:
        """Convert card into dictionary."""
        return {
            "card_id": self.card_id.strip(),
            "title": self.title.strip(),
            "status": normalize_dashboard_status(self.status).value,
            "healthy": self.healthy,
            "subtitle": self.subtitle.strip(),
            "primary_metric": self.primary_metric.to_dict() if self.primary_metric else None,
            "metrics": [metric.to_dict() for metric in self.metrics],
            "widgets": [widget.to_dict() for widget in self.widgets],
            "actions": [action.to_dict() for action in self.actions],
            "issues": [issue.to_dict() for issue in self.issues],
            "data": dict(self.data),
            "metric_count": self.metric_count,
            "widget_count": self.widget_count,
            "issue_count": self.issue_count,
            "metadata": dict(self.metadata),
        }


def normalize_dashboard_widget_type(
    widget_type: DashboardWidgetType | str,
) -> DashboardWidgetType:
    """Normalize dashboard widget type."""
    if isinstance(widget_type, DashboardWidgetType):
        return widget_type

    normalized = validate_non_empty_string(widget_type, "Dashboard widget type").lower()

    try:
        return DashboardWidgetType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardWidgetType)
        raise ValueError(
            f"Invalid dashboard widget type '{widget_type}'. Valid types: {valid}.",
        ) from exc


def normalize_dashboard_widget_size(
    size: DashboardWidgetSize | str,
) -> DashboardWidgetSize:
    """Normalize dashboard widget size."""
    if isinstance(size, DashboardWidgetSize):
        return size

    normalized = validate_non_empty_string(size, "Dashboard widget size").lower()

    try:
        return DashboardWidgetSize(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardWidgetSize)
        raise ValueError(
            f"Invalid dashboard widget size '{size}'. Valid sizes: {valid}.",
        ) from exc


def normalize_dashboard_chart_type(
    chart_type: DashboardChartType | str,
) -> DashboardChartType:
    """Normalize dashboard chart type."""
    if isinstance(chart_type, DashboardChartType):
        return chart_type

    normalized = validate_non_empty_string(chart_type, "Dashboard chart type").lower()

    try:
        return DashboardChartType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardChartType)
        raise ValueError(
            f"Invalid dashboard chart type '{chart_type}'. Valid chart types: {valid}.",
        ) from exc


def normalize_dashboard_action_type(
    action_type: DashboardActionType | str,
) -> DashboardActionType:
    """Normalize dashboard action type."""
    if isinstance(action_type, DashboardActionType):
        return action_type

    normalized = validate_non_empty_string(action_type, "Dashboard action type").lower()

    try:
        return DashboardActionType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in DashboardActionType)
        raise ValueError(
            f"Invalid dashboard action type '{action_type}'. Valid action types: {valid}.",
        ) from exc


def validate_chart_points(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate chart points."""
    if not isinstance(points, list):
        raise ValueError("Chart points must be a list.")

    for point in points:
        validate_metadata(point, "Chart point")

    return points


def validate_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate table rows."""
    if not isinstance(rows, list):
        raise ValueError("Table rows must be a list.")

    for row in rows:
        validate_metadata(row, "Table row")

    return rows


def validate_dashboard_widget_actions(
    actions: list[DashboardWidgetAction],
) -> list[DashboardWidgetAction]:
    """Validate dashboard widget actions."""
    if not isinstance(actions, list):
        raise ValueError("Actions must be a list.")

    for action in actions:
        if not isinstance(action, DashboardWidgetAction):
            raise ValueError("Actions must contain DashboardWidgetAction objects.")

    return actions


def validate_dashboard_table_columns(
    columns: list[DashboardTableColumn],
) -> list[DashboardTableColumn]:
    """Validate dashboard table columns."""
    if not isinstance(columns, list):
        raise ValueError("Table columns must be a list.")

    for column in columns:
        if not isinstance(column, DashboardTableColumn):
            raise ValueError("Table columns must contain DashboardTableColumn objects.")

    return columns


def validate_dashboard_chart_series(
    series: list[DashboardChartSeries],
) -> list[DashboardChartSeries]:
    """Validate dashboard chart series."""
    if not isinstance(series, list):
        raise ValueError("Chart series must be a list.")

    for item in series:
        if not isinstance(item, DashboardChartSeries):
            raise ValueError("Chart series must contain DashboardChartSeries objects.")

    return series


def validate_dashboard_widgets(
    widgets: list[DashboardWidget],
) -> list[DashboardWidget]:
    """Validate dashboard widgets."""
    if not isinstance(widgets, list):
        raise ValueError("Widgets must be a list.")

    for widget in widgets:
        if not isinstance(widget, DashboardWidget):
            raise ValueError("Widgets must contain DashboardWidget objects.")

    return widgets


def validate_dashboard_cards(cards: list[DashboardCard]) -> list[DashboardCard]:
    """Validate dashboard cards."""
    if not isinstance(cards, list):
        raise ValueError("Cards must be a list.")

    for card in cards:
        if not isinstance(card, DashboardCard):
            raise ValueError("Cards must contain DashboardCard objects.")

    return cards


def build_dashboard_widget_action(
    *,
    action_id: str,
    label: str,
    action_type: DashboardActionType | str,
    target: str = "",
    payload: dict[str, Any] | None = None,
    disabled: bool = False,
    metadata: dict[str, Any] | None = None,
) -> DashboardWidgetAction:
    """Build dashboard widget action."""
    return DashboardWidgetAction(
        action_id=action_id,
        label=label,
        action_type=action_type,
        target=target,
        payload=payload or {},
        disabled=disabled,
        metadata=metadata or {},
    )


def build_dashboard_table_column(
    *,
    key: str,
    label: str,
    data_type: str = "string",
    sortable: bool = True,
    visible: bool = True,
    metadata: dict[str, Any] | None = None,
) -> DashboardTableColumn:
    """Build dashboard table column."""
    return DashboardTableColumn(
        key=key,
        label=label,
        data_type=data_type,
        sortable=sortable,
        visible=visible,
        metadata=metadata or {},
    )


def build_dashboard_chart_series(
    *,
    name: str,
    points: list[dict[str, Any]] | None = None,
    chart_type: DashboardChartType | str = DashboardChartType.LINE,
    metadata: dict[str, Any] | None = None,
) -> DashboardChartSeries:
    """Build dashboard chart series."""
    return DashboardChartSeries(
        name=name,
        points=points or [],
        chart_type=chart_type,
        metadata=metadata or {},
    )


def build_dashboard_widget(
    *,
    widget_id: str,
    title: str,
    widget_type: DashboardWidgetType | str,
    status: DashboardStatus | str = DashboardStatus.READY,
    size: DashboardWidgetSize | str = DashboardWidgetSize.MEDIUM,
    chart_type: DashboardChartType | str = DashboardChartType.NONE,
    subtitle: str = "",
    description: str = "",
    data: dict[str, Any] | None = None,
    metrics: list[DashboardMetric] | None = None,
    issues: list[DashboardIssue] | None = None,
    actions: list[DashboardWidgetAction] | None = None,
    table_columns: list[DashboardTableColumn] | None = None,
    table_rows: list[dict[str, Any]] | None = None,
    chart_series: list[DashboardChartSeries] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardWidget:
    """Build dashboard widget."""
    return DashboardWidget(
        widget_id=widget_id,
        title=title,
        widget_type=widget_type,
        status=status,
        size=size,
        chart_type=chart_type,
        subtitle=subtitle,
        description=description,
        data=data or {},
        metrics=metrics or [],
        issues=issues or [],
        actions=actions or [],
        table_columns=table_columns or [],
        table_rows=table_rows or [],
        chart_series=chart_series or [],
        metadata=metadata or {},
    )


def build_dashboard_card(
    *,
    card_id: str,
    title: str,
    status: DashboardStatus | str = DashboardStatus.READY,
    subtitle: str = "",
    primary_metric: DashboardMetric | None = None,
    metrics: list[DashboardMetric] | None = None,
    widgets: list[DashboardWidget] | None = None,
    actions: list[DashboardWidgetAction] | None = None,
    issues: list[DashboardIssue] | None = None,
    data: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> DashboardCard:
    """Build dashboard card."""
    return DashboardCard(
        card_id=card_id,
        title=title,
        status=status,
        subtitle=subtitle,
        primary_metric=primary_metric,
        metrics=metrics or [],
        widgets=widgets or [],
        actions=actions or [],
        issues=issues or [],
        data=data or {},
        metadata=metadata or {},
    )


def widget_to_dashboard_component(widget: DashboardWidget) -> DashboardComponent:
    """Convert widget into base dashboard component."""
    if not isinstance(widget, DashboardWidget):
        raise ValueError("Widget must be DashboardWidget.")

    return build_dashboard_component(
        component_id=widget.widget_id,
        title=widget.title,
        component_type=DashboardComponentType.CARD,
        status=widget.status,
        description=widget.description,
        data=widget.to_dict(),
        metrics=widget.metrics,
        issues=widget.issues,
        metadata={
            **widget.metadata,
            "widget_type": normalize_dashboard_widget_type(widget.widget_type).value,
        },
    )


def card_to_dashboard_component(card: DashboardCard) -> DashboardComponent:
    """Convert card into base dashboard component."""
    if not isinstance(card, DashboardCard):
        raise ValueError("Card must be DashboardCard.")

    metrics = []
    if card.primary_metric is not None:
        metrics.append(card.primary_metric)
    metrics.extend(card.metrics)

    return build_dashboard_component(
        component_id=card.card_id,
        title=card.title,
        component_type=DashboardComponentType.CARD,
        status=card.status,
        description=card.subtitle,
        data=card.to_dict(),
        metrics=metrics,
        issues=card.issues,
        metadata=dict(card.metadata),
    )