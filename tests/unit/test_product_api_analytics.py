"""
Unit tests for AQOS product analytics API.
"""

import pytest

from aqos.product_api import (
    ProductAnalyticsDashboard,
    ProductAnalyticsMetric,
    ProductAnalyticsMetricType,
    ProductAnalyticsPeriod,
    ProductAnalyticsPoint,
    ProductAnalyticsSeries,
    ProductAnalyticsStore,
    ProductAnalyticsSummary,
    ProductAnalyticsTrend,
    ProductApiListQuery,
    ProductApiPagination,
    ProductApiStatus,
    analytics_dashboard_to_response,
    analytics_metric_default_unit,
    analytics_metric_to_response,
    analytics_series_to_response,
    build_product_analytics_dashboard,
    build_product_analytics_metric,
    build_product_analytics_point,
    build_product_analytics_series,
    build_product_analytics_store,
    build_product_api_context,
    create_analytics_operation_response,
    filter_product_analytics_series,
    get_analytics_dashboard_response,
    list_analytics_dashboards_response,
    normalize_product_analytics_metric_type,
    normalize_product_analytics_period,
    normalize_product_analytics_trend,
    paginate_product_analytics_dashboards,
    summarize_product_analytics,
    validate_metric_value,
    validate_product_analytics_dashboards,
    validate_product_analytics_metrics,
    validate_product_analytics_points,
    validate_product_analytics_series_list,
)


def build_point(
    timestamp: str = "2026-01-01T00:00:00+00:00",
    value: float = 10.0,
) -> ProductAnalyticsPoint:
    return build_product_analytics_point(
        timestamp=timestamp,
        value=value,
        metadata={
            "source": "test",
        },
    )


def build_series(
    series_id: str = "series-1",
    metric_type: str = "return_percent",
    period: str = "daily",
) -> ProductAnalyticsSeries:
    return build_product_analytics_series(
        series_id=series_id,
        metric_type=metric_type,
        period=period,
        label="Return series",
        points=[
            build_point("2026-01-01T00:00:00+00:00", 10),
            build_point("2026-01-02T00:00:00+00:00", 15),
        ],
    )


def build_dashboard(dashboard_id: str = "dashboard-1") -> ProductAnalyticsDashboard:
    return build_product_analytics_dashboard(
        dashboard_id=dashboard_id,
        title="Trading Analytics",
        metrics=[
            build_product_analytics_metric(
                metric_id="metric-1",
                metric_type="return_percent",
                value=12.5,
                label="Return",
            ),
            build_product_analytics_metric(
                metric_id="metric-2",
                metric_type="win_rate",
                value=62.0,
                label="Win rate",
            ),
        ],
        series=[
            build_series("series-1", "return_percent"),
            build_product_analytics_series(
                series_id="series-2",
                metric_type="drawdown_percent",
                period="daily",
                label="Drawdown",
                points=[
                    build_point("2026-01-01T00:00:00+00:00", 8),
                    build_point("2026-01-02T00:00:00+00:00", 4),
                ],
            ),
        ],
        period="daily",
        generated_at="2026-01-01T01:00:00+00:00",
    )


def test_analytics_enum_values():
    assert ProductAnalyticsMetricType.RETURN_PERCENT.value == "return_percent"
    assert ProductAnalyticsMetricType.WIN_RATE.value == "win_rate"
    assert ProductAnalyticsMetricType.DRAWDOWN_PERCENT.value == "drawdown_percent"
    assert ProductAnalyticsMetricType.PROFIT_FACTOR.value == "profit_factor"
    assert ProductAnalyticsMetricType.SIGNAL_CONFIDENCE.value == "signal_confidence"
    assert ProductAnalyticsMetricType.PORTFOLIO_EXPOSURE.value == "portfolio_exposure"
    assert ProductAnalyticsMetricType.UNREALIZED_PNL.value == "unrealized_pnl"

    assert ProductAnalyticsPeriod.DAILY.value == "daily"
    assert ProductAnalyticsPeriod.WEEKLY.value == "weekly"
    assert ProductAnalyticsPeriod.MONTHLY.value == "monthly"
    assert ProductAnalyticsPeriod.QUARTERLY.value == "quarterly"
    assert ProductAnalyticsPeriod.YEARLY.value == "yearly"

    assert ProductAnalyticsTrend.UP.value == "up"
    assert ProductAnalyticsTrend.DOWN.value == "down"
    assert ProductAnalyticsTrend.FLAT.value == "flat"


def test_analytics_normalizers_accept_enum_and_string():
    assert normalize_product_analytics_metric_type(ProductAnalyticsMetricType.RETURN_PERCENT) == ProductAnalyticsMetricType.RETURN_PERCENT
    assert normalize_product_analytics_metric_type(" WIN_RATE ") == ProductAnalyticsMetricType.WIN_RATE
    assert normalize_product_analytics_period(ProductAnalyticsPeriod.DAILY) == ProductAnalyticsPeriod.DAILY
    assert normalize_product_analytics_period(" MONTHLY ") == ProductAnalyticsPeriod.MONTHLY
    assert normalize_product_analytics_trend(ProductAnalyticsTrend.UP) == ProductAnalyticsTrend.UP
    assert normalize_product_analytics_trend(" DOWN ") == ProductAnalyticsTrend.DOWN


def test_analytics_normalizers_reject_invalid_values():
    with pytest.raises(ValueError):
        normalize_product_analytics_metric_type("bad")

    with pytest.raises(ValueError):
        normalize_product_analytics_period("bad")

    with pytest.raises(ValueError):
        normalize_product_analytics_trend("bad")


def test_validate_metric_value():
    assert validate_metric_value(0, "Value") == 0.0
    assert validate_metric_value(-10, "Value") == -10.0
    assert validate_metric_value(12.5, "Value") == 12.5

    with pytest.raises(ValueError):
        validate_metric_value(True, "Value")

    with pytest.raises(ValueError):
        validate_metric_value("12", "Value")


def test_analytics_metric_default_unit():
    assert analytics_metric_default_unit("return_percent") == "%"
    assert analytics_metric_default_unit("win_rate") == "%"
    assert analytics_metric_default_unit("drawdown_percent") == "%"
    assert analytics_metric_default_unit("signal_confidence") == "%"
    assert analytics_metric_default_unit("portfolio_exposure") == "USD"
    assert analytics_metric_default_unit("unrealized_pnl") == "USD"
    assert analytics_metric_default_unit("profit_factor") == "ratio"


def test_product_analytics_metric_to_dict():
    metric = ProductAnalyticsMetric(
        metric_id=" metric-1 ",
        metric_type="RETURN_PERCENT",
        value=12.5,
        label=" Return ",
        unit=" % ",
        metadata={
            "source": "test",
        },
    )

    assert metric.to_dict() == {
        "metric_id": "metric-1",
        "metric_type": "return_percent",
        "value": 12.5,
        "label": "Return",
        "unit": "%",
        "metadata": {
            "source": "test",
        },
    }


def test_product_analytics_metric_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductAnalyticsMetric(metric_id="", metric_type="return_percent", value=1)

    with pytest.raises(ValueError):
        ProductAnalyticsMetric(metric_id="metric-1", metric_type="bad", value=1)

    with pytest.raises(ValueError):
        ProductAnalyticsMetric(metric_id="metric-1", metric_type="return_percent", value="1")

    with pytest.raises(ValueError):
        ProductAnalyticsMetric(metric_id="metric-1", metric_type="return_percent", value=1, metadata=[])


def test_build_product_analytics_metric():
    metric = build_product_analytics_metric(
        metric_id="metric-1",
        metric_type="return_percent",
        value=10,
    )

    assert isinstance(metric, ProductAnalyticsMetric)
    assert metric.unit == "%"


def test_product_analytics_point_to_dict():
    point = ProductAnalyticsPoint(
        timestamp=" 2026-01-01T00:00:00+00:00 ",
        value=12.5,
        metadata={
            "source": "test",
        },
    )

    assert point.to_dict() == {
        "timestamp": "2026-01-01T00:00:00+00:00",
        "value": 12.5,
        "metadata": {
            "source": "test",
        },
    }


def test_product_analytics_point_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductAnalyticsPoint(timestamp="", value=1)

    with pytest.raises(ValueError):
        ProductAnalyticsPoint(timestamp="2026-01-01", value="1")

    with pytest.raises(ValueError):
        ProductAnalyticsPoint(timestamp="2026-01-01", value=1, metadata=[])


def test_product_analytics_series_to_dict():
    series = build_series()

    payload = series.to_dict()

    assert payload["series_id"] == "series-1"
    assert payload["metric_type"] == "return_percent"
    assert payload["period"] == "daily"
    assert payload["latest_value"] == 15.0
    assert payload["average_value"] == 12.5
    assert payload["min_value"] == 10.0
    assert payload["max_value"] == 15.0
    assert payload["trend"] == "up"
    assert len(payload["points"]) == 2


def test_product_analytics_series_down_and_flat_trends():
    down = build_product_analytics_series(
        series_id="down",
        metric_type="return_percent",
        period="daily",
        points=[
            build_point("2026-01-01", 10),
            build_point("2026-01-02", 5),
        ],
    )
    flat = build_product_analytics_series(
        series_id="flat",
        metric_type="return_percent",
        period="daily",
        points=[
            build_point("2026-01-01", 10),
            build_point("2026-01-02", 10),
        ],
    )
    empty = build_product_analytics_series(
        series_id="empty",
        metric_type="return_percent",
        period="daily",
    )

    assert down.trend == ProductAnalyticsTrend.DOWN
    assert flat.trend == ProductAnalyticsTrend.FLAT
    assert empty.trend == ProductAnalyticsTrend.FLAT
    assert empty.latest_value == 0.0


def test_product_analytics_series_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductAnalyticsSeries(series_id="", metric_type="return_percent", period="daily")

    with pytest.raises(ValueError):
        ProductAnalyticsSeries(series_id="series-1", metric_type="bad", period="daily")

    with pytest.raises(ValueError):
        ProductAnalyticsSeries(series_id="series-1", metric_type="return_percent", period="bad")

    with pytest.raises(ValueError):
        ProductAnalyticsSeries(series_id="series-1", metric_type="return_percent", period="daily", points=["bad"])

    with pytest.raises(ValueError):
        ProductAnalyticsSeries(series_id="series-1", metric_type="return_percent", period="daily", metadata=[])


def test_validate_analytics_lists():
    metric = build_product_analytics_metric(metric_id="metric-1", metric_type="return_percent", value=10)
    point = build_point()
    series = build_series()
    dashboard = build_dashboard()

    assert validate_product_analytics_metrics([metric]) == [metric]
    assert validate_product_analytics_points([point]) == [point]
    assert validate_product_analytics_series_list([series]) == [series]
    assert validate_product_analytics_dashboards([dashboard]) == [dashboard]

    with pytest.raises(ValueError):
        validate_product_analytics_metrics("bad")

    with pytest.raises(ValueError):
        validate_product_analytics_metrics(["bad"])

    with pytest.raises(ValueError):
        validate_product_analytics_points("bad")

    with pytest.raises(ValueError):
        validate_product_analytics_points(["bad"])

    with pytest.raises(ValueError):
        validate_product_analytics_series_list("bad")

    with pytest.raises(ValueError):
        validate_product_analytics_series_list(["bad"])

    with pytest.raises(ValueError):
        validate_product_analytics_dashboards("bad")

    with pytest.raises(ValueError):
        validate_product_analytics_dashboards(["bad"])


def test_summarize_product_analytics():
    dashboard = build_dashboard()

    summary = summarize_product_analytics(
        metrics=dashboard.metrics,
        series=dashboard.series,
        metadata={
            "source": "test",
        },
    )

    assert isinstance(summary, ProductAnalyticsSummary)
    assert summary.to_dict() == {
        "total_metrics": 2,
        "total_series": 2,
        "up_trends": 1,
        "down_trends": 1,
        "flat_trends": 0,
        "average_latest_value": 9.5,
        "metadata": {
            "source": "test",
        },
    }


def test_product_analytics_summary_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductAnalyticsSummary(total_metrics=-1)

    with pytest.raises(ValueError):
        ProductAnalyticsSummary(average_latest_value="bad")

    with pytest.raises(ValueError):
        ProductAnalyticsSummary(metadata=[])


def test_product_analytics_dashboard_to_dict():
    dashboard = build_dashboard()

    payload = dashboard.to_dict()

    assert payload["dashboard_id"] == "dashboard-1"
    assert payload["title"] == "Trading Analytics"
    assert len(payload["metrics"]) == 2
    assert len(payload["series"]) == 2
    assert payload["period"] == "daily"
    assert payload["summary"]["total_metrics"] == 2
    assert payload["generated_at"] == "2026-01-01T01:00:00+00:00"


def test_product_analytics_dashboard_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductAnalyticsDashboard(dashboard_id="", title="Analytics")

    with pytest.raises(ValueError):
        ProductAnalyticsDashboard(dashboard_id="dashboard-1", title="")

    with pytest.raises(ValueError):
        ProductAnalyticsDashboard(dashboard_id="dashboard-1", title="Analytics", metrics=["bad"])

    with pytest.raises(ValueError):
        ProductAnalyticsDashboard(dashboard_id="dashboard-1", title="Analytics", series=["bad"])

    with pytest.raises(ValueError):
        ProductAnalyticsDashboard(dashboard_id="dashboard-1", title="Analytics", period="bad")

    with pytest.raises(ValueError):
        ProductAnalyticsDashboard(dashboard_id="dashboard-1", title="Analytics", metadata=[])

    with pytest.raises(ValueError):
        ProductAnalyticsDashboard(dashboard_id="dashboard-1", title="Analytics", generated_at="")


def test_analytics_store():
    dashboard = build_dashboard()
    store = build_product_analytics_store()

    assert isinstance(store, ProductAnalyticsStore)
    assert store.count() == 0

    store.add(dashboard)

    assert store.count() == 1
    assert store.get("dashboard-1") == dashboard
    assert store.list() == [dashboard]
    assert store.remove("dashboard-1") == dashboard
    assert store.count() == 0

    store.add(dashboard)
    store.clear()

    assert store.count() == 0


def test_analytics_store_rejects_invalid_values():
    with pytest.raises(ValueError):
        ProductAnalyticsStore(dashboards=[])

    with pytest.raises(ValueError):
        ProductAnalyticsStore(dashboards={"dashboard-1": "bad"})

    store = build_product_analytics_store()

    with pytest.raises(ValueError):
        store.add("bad")

    with pytest.raises(ValueError):
        store.get("")

    with pytest.raises(ValueError):
        store.remove("")


def test_analytics_metric_series_and_dashboard_responses():
    context = build_product_api_context(request_id="req-1")
    metric = build_product_analytics_metric(metric_id="metric-1", metric_type="return_percent", value=10)
    series = build_series()
    dashboard = build_dashboard()

    metric_response = analytics_metric_to_response(metric=metric, context=context)
    series_response = analytics_series_to_response(series=series, context=context)
    dashboard_response = analytics_dashboard_to_response(dashboard=dashboard, context=context)

    assert metric_response.status == ProductApiStatus.SUCCESS
    assert metric_response.data["metric"]["metric_id"] == "metric-1"
    assert metric_response.meta is not None

    assert series_response.status == ProductApiStatus.SUCCESS
    assert series_response.data["series"]["series_id"] == "series-1"

    assert dashboard_response.status == ProductApiStatus.SUCCESS
    assert dashboard_response.data["dashboard"]["dashboard_id"] == "dashboard-1"

    with pytest.raises(ValueError):
        analytics_metric_to_response(metric="bad")

    with pytest.raises(ValueError):
        analytics_series_to_response(series="bad")

    with pytest.raises(ValueError):
        analytics_dashboard_to_response(dashboard="bad")


def test_list_analytics_dashboards_response_and_pagination():
    context = build_product_api_context(request_id="req-1")
    dashboards = [
        build_dashboard("dashboard-1"),
        build_dashboard("dashboard-2"),
    ]
    query = ProductApiListQuery(
        pagination=ProductApiPagination(page=1, page_size=1),
    )

    response = list_analytics_dashboards_response(
        dashboards=dashboards,
        query=query,
        context=context,
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert len(response.data["items"]) == 1
    assert response.data["total_items"] == 2
    assert response.data["metadata"]["dashboard_ids"] == ["dashboard-1", "dashboard-2"]


def test_create_analytics_operation_response():
    response = create_analytics_operation_response(
        dashboard=build_dashboard(),
        context=build_product_api_context(request_id="req-1"),
    )

    assert response.status == ProductApiStatus.SUCCESS
    assert response.data["operation"] == "create"
    assert response.data["resource_type"] == "analytics"
    assert response.data["resource_id"] == "dashboard-1"

    with pytest.raises(ValueError):
        create_analytics_operation_response(dashboard="bad")


def test_get_analytics_dashboard_response():
    dashboard = build_dashboard()
    store = build_product_analytics_store()
    store.add(dashboard)

    found = get_analytics_dashboard_response(
        store=store,
        dashboard_id="dashboard-1",
    )

    missing = get_analytics_dashboard_response(
        store=store,
        dashboard_id="missing",
    )

    assert found.status == ProductApiStatus.SUCCESS
    assert found.data["dashboard"]["dashboard_id"] == "dashboard-1"
    assert missing.status == ProductApiStatus.FAILURE
    assert missing.error is not None
    assert missing.error.code == "not_found"

    with pytest.raises(ValueError):
        get_analytics_dashboard_response(
            store="bad",
            dashboard_id="dashboard-1",
        )


def test_paginate_dashboards_and_filter_series():
    dashboards = [
        build_dashboard("dashboard-1"),
        build_dashboard("dashboard-2"),
        build_dashboard("dashboard-3"),
    ]

    paged = paginate_product_analytics_dashboards(
        dashboards=dashboards,
        pagination=ProductApiPagination(page=2, page_size=1),
    )

    assert [dashboard.dashboard_id for dashboard in paged] == ["dashboard-2"]

    series = build_dashboard().series

    return_series = filter_product_analytics_series(
        series=series,
        metric_type="return_percent",
    )

    assert len(return_series) == 1
    assert return_series[0].series_id == "series-1"

    daily_series = filter_product_analytics_series(
        series=series,
        period="daily",
    )

    assert len(daily_series) == 2

    up_series = filter_product_analytics_series(
        series=series,
        trend="up",
    )

    assert len(up_series) == 1

    with pytest.raises(ValueError):
        paginate_product_analytics_dashboards(
            dashboards=dashboards,
            pagination="bad",
        )


def test_product_analytics_exports_exist():
    import aqos.product_api as product_api

    expected_exports = [
        "ProductAnalyticsDashboard",
        "ProductAnalyticsMetric",
        "ProductAnalyticsMetricType",
        "ProductAnalyticsPeriod",
        "ProductAnalyticsPoint",
        "ProductAnalyticsSeries",
        "ProductAnalyticsStore",
        "ProductAnalyticsSummary",
        "ProductAnalyticsTrend",
        "analytics_dashboard_to_response",
        "analytics_metric_default_unit",
        "analytics_metric_to_response",
        "analytics_series_to_response",
        "build_product_analytics_dashboard",
        "build_product_analytics_metric",
        "build_product_analytics_point",
        "build_product_analytics_series",
        "build_product_analytics_store",
        "create_analytics_operation_response",
        "filter_product_analytics_series",
        "get_analytics_dashboard_response",
        "list_analytics_dashboards_response",
        "normalize_product_analytics_metric_type",
        "normalize_product_analytics_period",
        "normalize_product_analytics_trend",
        "paginate_product_analytics_dashboards",
        "summarize_product_analytics",
        "validate_metric_value",
        "validate_product_analytics_dashboards",
        "validate_product_analytics_metrics",
        "validate_product_analytics_points",
        "validate_product_analytics_series_list",
    ]

    for export_name in expected_exports:
        assert hasattr(product_api, export_name), export_name