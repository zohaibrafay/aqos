"""
Unit tests for AQOS dashboard widget and card contracts.
"""

import pytest

from aqos.dashboard import (
    DashboardActionType,
    DashboardCard,
    DashboardChartSeries,
    DashboardChartType,
    DashboardComponent,
    DashboardStatus,
    DashboardTableColumn,
    DashboardWidget,
    DashboardWidgetAction,
    DashboardWidgetSize,
    DashboardWidgetType,
    build_dashboard_card,
    build_dashboard_chart_series,
    build_dashboard_issue,
    build_dashboard_metric,
    build_dashboard_table_column,
    build_dashboard_widget,
    build_dashboard_widget_action,
    card_to_dashboard_component,
    normalize_dashboard_action_type,
    normalize_dashboard_chart_type,
    normalize_dashboard_widget_size,
    normalize_dashboard_widget_type,
    validate_chart_points,
    validate_dashboard_cards,
    validate_dashboard_chart_series,
    validate_dashboard_table_columns,
    validate_dashboard_widget_actions,
    validate_dashboard_widgets,
    validate_table_rows,
    widget_to_dashboard_component,
)


def build_metric():
    return build_dashboard_metric(
        name="win_rate",
        value=62.5,
        unit="%",
    )


def build_issue():
    return build_dashboard_issue(
        code="low_confidence",
        message="Low confidence signal.",
        severity="warning",
    )


def build_action():
    return build_dashboard_widget_action(
        action_id="refresh",
        label="Refresh",
        action_type="refresh",
    )


def build_widget():
    return build_dashboard_widget(
        widget_id="signal-widget",
        title="Signal Widget",
        widget_type="signal",
        metrics=[build_metric()],
    )


def test_widget_enum_values():
    assert DashboardWidgetType.KPI.value == "kpi"
    assert DashboardWidgetType.MARKET.value == "market"
    assert DashboardWidgetType.SIGNAL.value == "signal"
    assert DashboardWidgetType.STRATEGY.value == "strategy"
    assert DashboardWidgetType.PORTFOLIO.value == "portfolio"
    assert DashboardWidgetType.RISK.value == "risk"
    assert DashboardWidgetType.BROKER.value == "broker"
    assert DashboardWidgetType.PROVIDER.value == "provider"
    assert DashboardWidgetType.ALERT.value == "alert"
    assert DashboardWidgetType.CUSTOM.value == "custom"

    assert DashboardWidgetSize.SMALL.value == "small"
    assert DashboardWidgetSize.MEDIUM.value == "medium"
    assert DashboardWidgetSize.LARGE.value == "large"
    assert DashboardWidgetSize.FULL.value == "full"

    assert DashboardChartType.NONE.value == "none"
    assert DashboardChartType.LINE.value == "line"
    assert DashboardChartType.BAR.value == "bar"
    assert DashboardChartType.AREA.value == "area"
    assert DashboardChartType.PIE.value == "pie"
    assert DashboardChartType.CANDLESTICK.value == "candlestick"
    assert DashboardChartType.GAUGE.value == "gauge"
    assert DashboardChartType.SCATTER.value == "scatter"

    assert DashboardActionType.LINK.value == "link"
    assert DashboardActionType.REFRESH.value == "refresh"
    assert DashboardActionType.API.value == "api"
    assert DashboardActionType.MODAL.value == "modal"
    assert DashboardActionType.DOWNLOAD.value == "download"


def test_widget_normalizers_accept_enum_and_string():
    assert normalize_dashboard_widget_type(DashboardWidgetType.KPI) == DashboardWidgetType.KPI
    assert normalize_dashboard_widget_type(" SIGNAL ") == DashboardWidgetType.SIGNAL
    assert normalize_dashboard_widget_size(DashboardWidgetSize.SMALL) == DashboardWidgetSize.SMALL
    assert normalize_dashboard_widget_size(" FULL ") == DashboardWidgetSize.FULL
    assert normalize_dashboard_chart_type(DashboardChartType.LINE) == DashboardChartType.LINE
    assert normalize_dashboard_chart_type(" CANDLESTICK ") == DashboardChartType.CANDLESTICK
    assert normalize_dashboard_action_type(DashboardActionType.API) == DashboardActionType.API
    assert normalize_dashboard_action_type(" DOWNLOAD ") == DashboardActionType.DOWNLOAD


def test_widget_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_dashboard_widget_type("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_widget_size("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_chart_type("bad")

    with pytest.raises(ValueError):
        normalize_dashboard_action_type("bad")


def test_widget_action_to_dict():
    action = DashboardWidgetAction(
        action_id=" open ",
        label=" Open Details ",
        action_type=" LINK ",
        target=" /signals/1 ",
        payload={
            "signal_id": "signal-1",
        },
        disabled=True,
        metadata={
            "source": "test",
        },
    )

    assert action.enabled is False
    assert action.to_dict() == {
        "action_id": "open",
        "label": "Open Details",
        "action_type": "link",
        "target": "/signals/1",
        "payload": {
            "signal_id": "signal-1",
        },
        "disabled": True,
        "enabled": False,
        "metadata": {
            "source": "test",
        },
    }


def test_widget_action_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardWidgetAction(action_id="", label="Open", action_type="link")

    with pytest.raises(ValueError):
        DashboardWidgetAction(action_id="open", label="", action_type="link")

    with pytest.raises(ValueError):
        DashboardWidgetAction(action_id="open", label="Open", action_type="bad")

    with pytest.raises(ValueError):
        DashboardWidgetAction(action_id="open", label="Open", action_type="link", target=123)

    with pytest.raises(ValueError):
        DashboardWidgetAction(action_id="open", label="Open", action_type="link", payload=[])

    with pytest.raises(ValueError):
        DashboardWidgetAction(action_id="open", label="Open", action_type="link", disabled="yes")

    with pytest.raises(ValueError):
        DashboardWidgetAction(action_id="open", label="Open", action_type="link", metadata=[])


def test_table_column_to_dict():
    column = DashboardTableColumn(
        key=" symbol ",
        label=" Symbol ",
        data_type=" string ",
        sortable=False,
        visible=False,
        metadata={
            "width": 120,
        },
    )

    assert column.to_dict() == {
        "key": "symbol",
        "label": "Symbol",
        "data_type": "string",
        "sortable": False,
        "visible": False,
        "metadata": {
            "width": 120,
        },
    }


def test_table_column_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardTableColumn(key="", label="Symbol")

    with pytest.raises(ValueError):
        DashboardTableColumn(key="symbol", label="")

    with pytest.raises(ValueError):
        DashboardTableColumn(key="symbol", label="Symbol", data_type="")

    with pytest.raises(ValueError):
        DashboardTableColumn(key="symbol", label="Symbol", sortable="yes")

    with pytest.raises(ValueError):
        DashboardTableColumn(key="symbol", label="Symbol", visible="yes")

    with pytest.raises(ValueError):
        DashboardTableColumn(key="symbol", label="Symbol", metadata=[])


def test_chart_series_to_dict():
    series = DashboardChartSeries(
        name=" close ",
        points=[
            {
                "x": "2026-01-01",
                "y": 2000,
            },
            {
                "x": "2026-01-02",
                "y": 2010,
            },
        ],
        chart_type=" AREA ",
        metadata={
            "symbol": "XAUUSD",
        },
    )

    payload = series.to_dict()

    assert series.point_count == 2
    assert payload["name"] == "close"
    assert payload["chart_type"] == "area"
    assert payload["point_count"] == 2
    assert payload["metadata"] == {
        "symbol": "XAUUSD",
    }


def test_chart_series_rejects_invalid_values():
    with pytest.raises(ValueError):
        DashboardChartSeries(name="")

    with pytest.raises(ValueError):
        DashboardChartSeries(name="Close", points="bad")

    with pytest.raises(ValueError):
        DashboardChartSeries(name="Close", points=["bad"])

    with pytest.raises(ValueError):
        DashboardChartSeries(name="Close", chart_type="bad")

    with pytest.raises(ValueError):
        DashboardChartSeries(name="Close", metadata=[])


def test_dashboard_widget_to_dict():
    metric = build_metric()
    issue = build_issue()
    action = build_action()
    column = build_dashboard_table_column(
        key="symbol",
        label="Symbol",
    )
    series = build_dashboard_chart_series(
        name="Close",
        points=[
            {
                "x": "2026-01-01",
                "y": 2000,
            }
        ],
    )
    widget = DashboardWidget(
        widget_id=" market-widget ",
        title=" Market Widget ",
        widget_type=" MARKET ",
        status=" WARNING ",
        size=" LARGE ",
        chart_type=" LINE ",
        subtitle=" XAUUSD ",
        description=" Market chart ",
        data={
            "symbol": "XAUUSD",
        },
        metrics=[metric],
        issues=[issue],
        actions=[action],
        table_columns=[column],
        table_rows=[
            {
                "symbol": "XAUUSD",
            }
        ],
        chart_series=[series],
        metadata={
            "order": 1,
        },
    )

    payload = widget.to_dict()

    assert widget.healthy is False
    assert widget.metric_count == 1
    assert widget.issue_count == 1
    assert widget.action_count == 1
    assert widget.row_count == 1
    assert widget.series_count == 1
    assert payload["widget_id"] == "market-widget"
    assert payload["title"] == "Market Widget"
    assert payload["widget_type"] == "market"
    assert payload["status"] == "warning"
    assert payload["size"] == "large"
    assert payload["chart_type"] == "line"
    assert payload["subtitle"] == "XAUUSD"
    assert payload["description"] == "Market chart"


def test_build_dashboard_widget():
    widget = build_dashboard_widget(
        widget_id="kpi",
        title="KPI",
        widget_type="kpi",
        metrics=[build_metric()],
    )

    assert isinstance(widget, DashboardWidget)
    assert widget.status == DashboardStatus.READY
    assert widget.metric_count == 1


def test_dashboard_widget_rejects_invalid_values():
    metric = build_metric()
    issue = build_issue()
    action = build_action()
    column = build_dashboard_table_column(key="symbol", label="Symbol")
    series = build_dashboard_chart_series(name="Close")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="", title="Widget", widget_type="kpi")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="", widget_type="kpi")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", status="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", size="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", chart_type="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", subtitle=123)

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", description=123)

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", data=[])

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", metrics="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", metrics=["bad"])

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", issues="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", issues=["bad"])

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", actions="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", actions=["bad"])

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", table_columns="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", table_columns=["bad"])

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", table_rows="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", table_rows=["bad"])

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", chart_series="bad")

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", chart_series=["bad"])

    with pytest.raises(ValueError):
        DashboardWidget(widget_id="widget", title="Widget", widget_type="kpi", metadata=[])

    assert validate_dashboard_widget_actions([action]) == [action]
    assert validate_dashboard_table_columns([column]) == [column]
    assert validate_dashboard_chart_series([series]) == [series]
    assert validate_dashboard_widgets([build_widget()]) == [build_widget()]
    assert validate_dashboard_cards([]) == []
    assert validate_chart_points([{"x": 1}]) == [{"x": 1}]
    assert validate_table_rows([{"symbol": "XAUUSD"}]) == [{"symbol": "XAUUSD"}]


def test_dashboard_card_to_dict():
    metric = build_metric()
    issue = build_issue()
    action = build_action()
    widget = build_widget()

    card = DashboardCard(
        card_id=" signal-card ",
        title=" Signal Card ",
        status=" WARNING ",
        subtitle=" Latest signal ",
        primary_metric=metric,
        metrics=[metric],
        widgets=[widget],
        actions=[action],
        issues=[issue],
        data={
            "symbol": "XAUUSD",
        },
        metadata={
            "source": "test",
        },
    )

    payload = card.to_dict()

    assert card.healthy is False
    assert card.metric_count == 2
    assert card.widget_count == 1
    assert card.issue_count == 1
    assert payload["card_id"] == "signal-card"
    assert payload["title"] == "Signal Card"
    assert payload["status"] == "warning"
    assert payload["subtitle"] == "Latest signal"
    assert payload["primary_metric"]["name"] == "win_rate"


def test_build_dashboard_card():
    card = build_dashboard_card(
        card_id="portfolio",
        title="Portfolio",
        primary_metric=build_metric(),
        widgets=[build_widget()],
    )

    assert isinstance(card, DashboardCard)
    assert card.metric_count == 1
    assert card.widget_count == 1


def test_dashboard_card_rejects_invalid_values():
    metric = build_metric()
    issue = build_issue()
    action = build_action()
    widget = build_widget()

    with pytest.raises(ValueError):
        DashboardCard(card_id="", title="Card")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", status="bad")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", subtitle=123)

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", primary_metric="bad")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", metrics="bad")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", metrics=["bad"])

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", widgets="bad")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", widgets=["bad"])

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", actions="bad")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", actions=["bad"])

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", issues="bad")

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", issues=["bad"])

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", data=[])

    with pytest.raises(ValueError):
        DashboardCard(card_id="card", title="Card", metadata=[])

    assert validate_dashboard_cards(
        [
            DashboardCard(
                card_id="card",
                title="Card",
                primary_metric=metric,
                widgets=[widget],
                actions=[action],
                issues=[issue],
            )
        ]
    )[0].card_id == "card"


def test_widget_and_card_to_dashboard_component():
    widget = build_widget()
    card = build_dashboard_card(
        card_id="signal-card",
        title="Signal Card",
        primary_metric=build_metric(),
        widgets=[widget],
    )

    widget_component = widget_to_dashboard_component(widget)
    card_component = card_to_dashboard_component(card)

    assert isinstance(widget_component, DashboardComponent)
    assert widget_component.component_id == "signal-widget"
    assert widget_component.data["widget_type"] == "signal"
    assert widget_component.metadata["widget_type"] == "signal"

    assert isinstance(card_component, DashboardComponent)
    assert card_component.component_id == "signal-card"
    assert card_component.metric_count == 1
    assert card_component.data["card_id"] == "signal-card"

    with pytest.raises(ValueError):
        widget_to_dashboard_component("bad")

    with pytest.raises(ValueError):
        card_to_dashboard_component("bad")


def test_dashboard_widget_exports_exist():
    import aqos.dashboard as dashboard

    expected_exports = [
        "DashboardActionType",
        "DashboardCard",
        "DashboardChartSeries",
        "DashboardChartType",
        "DashboardTableColumn",
        "DashboardWidget",
        "DashboardWidgetAction",
        "DashboardWidgetSize",
        "DashboardWidgetType",
        "build_dashboard_card",
        "build_dashboard_chart_series",
        "build_dashboard_table_column",
        "build_dashboard_widget",
        "build_dashboard_widget_action",
        "card_to_dashboard_component",
        "normalize_dashboard_action_type",
        "normalize_dashboard_chart_type",
        "normalize_dashboard_widget_size",
        "normalize_dashboard_widget_type",
        "validate_chart_points",
        "validate_dashboard_cards",
        "validate_dashboard_chart_series",
        "validate_dashboard_table_columns",
        "validate_dashboard_widget_actions",
        "validate_dashboard_widgets",
        "validate_table_rows",
        "widget_to_dashboard_component",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name