"""
AQOS product-facing analytics API.

This module provides dependency-free product API primitives for analytics
metrics, time series, dashboards, summaries, stores, and response helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from aqos.product_api.base import (
    ProductApiErrorCode,
    ProductApiRequestContext,
    ProductApiResponse,
    product_api_failure,
    product_api_success,
    validate_metadata,
    validate_non_empty_string,
    validate_non_negative_float,
    validate_percentage,
    validate_string,
)
from aqos.product_api.contracts import (
    ProductApiListQuery,
    ProductApiListResult,
    ProductApiOperation,
    ProductApiOperationResult,
    ProductApiPagination,
    ProductApiRequestType,
    list_result_to_response,
    operation_result_to_response,
)


class ProductAnalyticsMetricType(str, Enum):
    """Supported product analytics metric types."""

    RETURN_PERCENT = "return_percent"
    WIN_RATE = "win_rate"
    DRAWDOWN_PERCENT = "drawdown_percent"
    PROFIT_FACTOR = "profit_factor"
    SIGNAL_CONFIDENCE = "signal_confidence"
    PORTFOLIO_EXPOSURE = "portfolio_exposure"
    UNREALIZED_PNL = "unrealized_pnl"


class ProductAnalyticsPeriod(str, Enum):
    """Supported product analytics periods."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class ProductAnalyticsTrend(str, Enum):
    """Supported product analytics trend directions."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"


@dataclass(frozen=True)
class ProductAnalyticsMetric:
    """Product-facing analytics metric."""

    metric_id: str
    metric_type: ProductAnalyticsMetricType | str
    value: float
    label: str = ""
    unit: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.metric_id, "Metric ID")
        normalize_product_analytics_metric_type(self.metric_type)
        validate_metric_value(self.value, "Metric value")
        validate_string(self.label, "Label")
        validate_string(self.unit, "Unit")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert metric into dictionary."""
        return {
            "metric_id": self.metric_id.strip(),
            "metric_type": normalize_product_analytics_metric_type(self.metric_type).value,
            "value": float(self.value),
            "label": self.label.strip(),
            "unit": self.unit.strip(),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductAnalyticsPoint:
    """Product-facing analytics time series point."""

    timestamp: str
    value: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.timestamp, "Timestamp")
        validate_metric_value(self.value, "Point value")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert point into dictionary."""
        return {
            "timestamp": self.timestamp.strip(),
            "value": float(self.value),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductAnalyticsSeries:
    """Product-facing analytics series."""

    series_id: str
    metric_type: ProductAnalyticsMetricType | str
    period: ProductAnalyticsPeriod | str
    points: list[ProductAnalyticsPoint] = field(default_factory=list)
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_empty_string(self.series_id, "Series ID")
        normalize_product_analytics_metric_type(self.metric_type)
        normalize_product_analytics_period(self.period)
        validate_product_analytics_points(self.points)
        validate_string(self.label, "Label")
        validate_metadata(self.metadata, "Metadata")

    @property
    def latest_value(self) -> float:
        """Return latest series value."""
        return float(self.points[-1].value) if self.points else 0.0

    @property
    def average_value(self) -> float:
        """Return average series value."""
        if not self.points:
            return 0.0

        return round(sum(float(point.value) for point in self.points) / len(self.points), 4)

    @property
    def min_value(self) -> float:
        """Return minimum series value."""
        if not self.points:
            return 0.0

        return round(min(float(point.value) for point in self.points), 4)

    @property
    def max_value(self) -> float:
        """Return maximum series value."""
        if not self.points:
            return 0.0

        return round(max(float(point.value) for point in self.points), 4)

    @property
    def trend(self) -> ProductAnalyticsTrend:
        """Return series trend."""
        if len(self.points) < 2:
            return ProductAnalyticsTrend.FLAT

        first = float(self.points[0].value)
        latest = float(self.points[-1].value)

        if latest > first:
            return ProductAnalyticsTrend.UP

        if latest < first:
            return ProductAnalyticsTrend.DOWN

        return ProductAnalyticsTrend.FLAT

    def to_dict(self) -> dict[str, Any]:
        """Convert series into dictionary."""
        return {
            "series_id": self.series_id.strip(),
            "metric_type": normalize_product_analytics_metric_type(self.metric_type).value,
            "period": normalize_product_analytics_period(self.period).value,
            "label": self.label.strip(),
            "points": [point.to_dict() for point in self.points],
            "latest_value": self.latest_value,
            "average_value": self.average_value,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "trend": self.trend.value,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductAnalyticsSummary:
    """Compact product analytics summary."""

    total_metrics: int = 0
    total_series: int = 0
    up_trends: int = 0
    down_trends: int = 0
    flat_trends: int = 0
    average_latest_value: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        validate_non_negative_integer(self.total_metrics, "Total metrics")
        validate_non_negative_integer(self.total_series, "Total series")
        validate_non_negative_integer(self.up_trends, "Up trends")
        validate_non_negative_integer(self.down_trends, "Down trends")
        validate_non_negative_integer(self.flat_trends, "Flat trends")
        validate_metric_value(self.average_latest_value, "Average latest value")
        validate_metadata(self.metadata, "Metadata")

    def to_dict(self) -> dict[str, Any]:
        """Convert analytics summary into dictionary."""
        return {
            "total_metrics": self.total_metrics,
            "total_series": self.total_series,
            "up_trends": self.up_trends,
            "down_trends": self.down_trends,
            "flat_trends": self.flat_trends,
            "average_latest_value": float(self.average_latest_value),
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class ProductAnalyticsDashboard:
    """Product-facing analytics dashboard."""

    dashboard_id: str
    title: str
    metrics: list[ProductAnalyticsMetric] = field(default_factory=list)
    series: list[ProductAnalyticsSeries] = field(default_factory=list)
    period: ProductAnalyticsPeriod | str = ProductAnalyticsPeriod.DAILY
    metadata: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def __post_init__(self) -> None:
        validate_non_empty_string(self.dashboard_id, "Dashboard ID")
        validate_non_empty_string(self.title, "Title")
        validate_product_analytics_metrics(self.metrics)
        validate_product_analytics_series_list(self.series)
        normalize_product_analytics_period(self.period)
        validate_metadata(self.metadata, "Metadata")
        validate_non_empty_string(self.generated_at, "Generated at")

    def to_dict(self) -> dict[str, Any]:
        """Convert analytics dashboard into dictionary."""
        return {
            "dashboard_id": self.dashboard_id.strip(),
            "title": self.title.strip(),
            "metrics": [metric.to_dict() for metric in self.metrics],
            "series": [item.to_dict() for item in self.series],
            "period": normalize_product_analytics_period(self.period).value,
            "summary": summarize_product_analytics(
                metrics=self.metrics,
                series=self.series,
            ).to_dict(),
            "metadata": dict(self.metadata),
            "generated_at": self.generated_at.strip(),
        }


@dataclass
class ProductAnalyticsStore:
    """In-memory product analytics store."""

    dashboards: dict[str, ProductAnalyticsDashboard] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.dashboards, dict):
            raise ValueError("Dashboards must be a dictionary.")

        for dashboard_id, dashboard in self.dashboards.items():
            validate_non_empty_string(dashboard_id, "Dashboard ID")

            if not isinstance(dashboard, ProductAnalyticsDashboard):
                raise ValueError("Dashboards must contain ProductAnalyticsDashboard objects.")

    def add(self, dashboard: ProductAnalyticsDashboard) -> ProductAnalyticsDashboard:
        """Add dashboard to store."""
        if not isinstance(dashboard, ProductAnalyticsDashboard):
            raise ValueError("Dashboard must be a ProductAnalyticsDashboard.")

        self.dashboards[dashboard.dashboard_id.strip()] = dashboard
        return dashboard

    def get(self, dashboard_id: str) -> ProductAnalyticsDashboard | None:
        """Get dashboard by ID."""
        normalized_dashboard_id = validate_non_empty_string(dashboard_id, "Dashboard ID")
        return self.dashboards.get(normalized_dashboard_id)

    def list(self) -> list[ProductAnalyticsDashboard]:
        """List dashboards."""
        return list(self.dashboards.values())

    def remove(self, dashboard_id: str) -> ProductAnalyticsDashboard | None:
        """Remove dashboard by ID."""
        normalized_dashboard_id = validate_non_empty_string(dashboard_id, "Dashboard ID")
        return self.dashboards.pop(normalized_dashboard_id, None)

    def clear(self) -> None:
        """Clear analytics store."""
        self.dashboards.clear()

    def count(self) -> int:
        """Return dashboard count."""
        return len(self.dashboards)


def validate_non_negative_integer(value: int, field_name: str) -> int:
    """Validate non-negative integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")

    return value


def validate_metric_value(value: float | int, field_name: str) -> float:
    """Validate analytics metric value."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be a number.")

    return float(value)


def normalize_product_analytics_metric_type(
    metric_type: ProductAnalyticsMetricType | str,
) -> ProductAnalyticsMetricType:
    """Normalize analytics metric type."""
    if isinstance(metric_type, ProductAnalyticsMetricType):
        return metric_type

    normalized = validate_non_empty_string(metric_type, "Analytics metric type").lower()

    try:
        return ProductAnalyticsMetricType(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductAnalyticsMetricType)
        raise ValueError(
            f"Invalid analytics metric type '{metric_type}'. Valid metric types: {valid}.",
        ) from exc


def normalize_product_analytics_period(
    period: ProductAnalyticsPeriod | str,
) -> ProductAnalyticsPeriod:
    """Normalize analytics period."""
    if isinstance(period, ProductAnalyticsPeriod):
        return period

    normalized = validate_non_empty_string(period, "Analytics period").lower()

    try:
        return ProductAnalyticsPeriod(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductAnalyticsPeriod)
        raise ValueError(
            f"Invalid analytics period '{period}'. Valid periods: {valid}.",
        ) from exc


def normalize_product_analytics_trend(
    trend: ProductAnalyticsTrend | str,
) -> ProductAnalyticsTrend:
    """Normalize analytics trend."""
    if isinstance(trend, ProductAnalyticsTrend):
        return trend

    normalized = validate_non_empty_string(trend, "Analytics trend").lower()

    try:
        return ProductAnalyticsTrend(normalized)
    except ValueError as exc:
        valid = ", ".join(item.value for item in ProductAnalyticsTrend)
        raise ValueError(
            f"Invalid analytics trend '{trend}'. Valid trends: {valid}.",
        ) from exc


def analytics_metric_default_unit(metric_type: ProductAnalyticsMetricType | str) -> str:
    """Return default unit for analytics metric type."""
    normalized_metric_type = normalize_product_analytics_metric_type(metric_type)

    percentage_metrics = {
        ProductAnalyticsMetricType.RETURN_PERCENT,
        ProductAnalyticsMetricType.WIN_RATE,
        ProductAnalyticsMetricType.DRAWDOWN_PERCENT,
        ProductAnalyticsMetricType.SIGNAL_CONFIDENCE,
    }

    if normalized_metric_type in percentage_metrics:
        return "%"

    if normalized_metric_type in {
        ProductAnalyticsMetricType.PORTFOLIO_EXPOSURE,
        ProductAnalyticsMetricType.UNREALIZED_PNL,
    }:
        return "USD"

    return "ratio"


def build_product_analytics_metric(
    *,
    metric_id: str,
    metric_type: ProductAnalyticsMetricType | str,
    value: float,
    label: str = "",
    unit: str = "",
    metadata: dict[str, Any] | None = None,
) -> ProductAnalyticsMetric:
    """Build product analytics metric."""
    return ProductAnalyticsMetric(
        metric_id=metric_id,
        metric_type=metric_type,
        value=value,
        label=label,
        unit=unit or analytics_metric_default_unit(metric_type),
        metadata=metadata or {},
    )


def build_product_analytics_point(
    *,
    timestamp: str,
    value: float,
    metadata: dict[str, Any] | None = None,
) -> ProductAnalyticsPoint:
    """Build product analytics point."""
    return ProductAnalyticsPoint(
        timestamp=timestamp,
        value=value,
        metadata=metadata or {},
    )


def build_product_analytics_series(
    *,
    series_id: str,
    metric_type: ProductAnalyticsMetricType | str,
    period: ProductAnalyticsPeriod | str,
    points: list[ProductAnalyticsPoint] | None = None,
    label: str = "",
    metadata: dict[str, Any] | None = None,
) -> ProductAnalyticsSeries:
    """Build product analytics series."""
    return ProductAnalyticsSeries(
        series_id=series_id,
        metric_type=metric_type,
        period=period,
        points=points or [],
        label=label,
        metadata=metadata or {},
    )


def build_product_analytics_dashboard(
    *,
    dashboard_id: str,
    title: str,
    metrics: list[ProductAnalyticsMetric] | None = None,
    series: list[ProductAnalyticsSeries] | None = None,
    period: ProductAnalyticsPeriod | str = ProductAnalyticsPeriod.DAILY,
    metadata: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> ProductAnalyticsDashboard:
    """Build product analytics dashboard."""
    dashboard_kwargs: dict[str, Any] = {
        "dashboard_id": dashboard_id,
        "title": title,
        "metrics": metrics or [],
        "series": series or [],
        "period": period,
        "metadata": metadata or {},
    }

    if generated_at is not None:
        dashboard_kwargs["generated_at"] = generated_at

    return ProductAnalyticsDashboard(**dashboard_kwargs)


def build_product_analytics_store(
    *,
    dashboards: dict[str, ProductAnalyticsDashboard] | None = None,
) -> ProductAnalyticsStore:
    """Build product analytics store."""
    return ProductAnalyticsStore(
        dashboards=dashboards or {},
    )


def validate_product_analytics_metrics(
    metrics: list[ProductAnalyticsMetric],
) -> list[ProductAnalyticsMetric]:
    """Validate product analytics metrics."""
    if not isinstance(metrics, list):
        raise ValueError("Metrics must be a list.")

    for metric in metrics:
        if not isinstance(metric, ProductAnalyticsMetric):
            raise ValueError("Metrics must contain ProductAnalyticsMetric objects.")

    return metrics


def validate_product_analytics_points(
    points: list[ProductAnalyticsPoint],
) -> list[ProductAnalyticsPoint]:
    """Validate product analytics points."""
    if not isinstance(points, list):
        raise ValueError("Points must be a list.")

    for point in points:
        if not isinstance(point, ProductAnalyticsPoint):
            raise ValueError("Points must contain ProductAnalyticsPoint objects.")

    return points


def validate_product_analytics_series_list(
    series: list[ProductAnalyticsSeries],
) -> list[ProductAnalyticsSeries]:
    """Validate product analytics series list."""
    if not isinstance(series, list):
        raise ValueError("Series must be a list.")

    for item in series:
        if not isinstance(item, ProductAnalyticsSeries):
            raise ValueError("Series must contain ProductAnalyticsSeries objects.")

    return series


def summarize_product_analytics(
    *,
    metrics: list[ProductAnalyticsMetric],
    series: list[ProductAnalyticsSeries],
    metadata: dict[str, Any] | None = None,
) -> ProductAnalyticsSummary:
    """Summarize product analytics metrics and series."""
    validate_product_analytics_metrics(metrics)
    validate_product_analytics_series_list(series)

    up_trends = sum(1 for item in series if item.trend == ProductAnalyticsTrend.UP)
    down_trends = sum(1 for item in series if item.trend == ProductAnalyticsTrend.DOWN)
    flat_trends = sum(1 for item in series if item.trend == ProductAnalyticsTrend.FLAT)

    latest_values = [item.latest_value for item in series]
    average_latest_value = (
        round(sum(latest_values) / len(latest_values), 4)
        if latest_values
        else 0.0
    )

    return ProductAnalyticsSummary(
        total_metrics=len(metrics),
        total_series=len(series),
        up_trends=up_trends,
        down_trends=down_trends,
        flat_trends=flat_trends,
        average_latest_value=average_latest_value,
        metadata=metadata or {},
    )


def analytics_metric_to_response(
    *,
    metric: ProductAnalyticsMetric,
    context: ProductApiRequestContext | None = None,
    message: str = "Analytics metric request completed.",
) -> ProductApiResponse:
    """Convert analytics metric into product API response."""
    if not isinstance(metric, ProductAnalyticsMetric):
        raise ValueError("Metric must be a ProductAnalyticsMetric.")

    return product_api_success(
        data={
            "metric": metric.to_dict(),
        },
        message=message,
        context=context,
    )


def analytics_series_to_response(
    *,
    series: ProductAnalyticsSeries,
    context: ProductApiRequestContext | None = None,
    message: str = "Analytics series request completed.",
) -> ProductApiResponse:
    """Convert analytics series into product API response."""
    if not isinstance(series, ProductAnalyticsSeries):
        raise ValueError("Series must be a ProductAnalyticsSeries.")

    return product_api_success(
        data={
            "series": series.to_dict(),
        },
        message=message,
        context=context,
    )


def analytics_dashboard_to_response(
    *,
    dashboard: ProductAnalyticsDashboard,
    context: ProductApiRequestContext | None = None,
    message: str = "Analytics dashboard request completed.",
) -> ProductApiResponse:
    """Convert analytics dashboard into product API response."""
    if not isinstance(dashboard, ProductAnalyticsDashboard):
        raise ValueError("Dashboard must be a ProductAnalyticsDashboard.")

    return product_api_success(
        data={
            "dashboard": dashboard.to_dict(),
        },
        message=message,
        context=context,
    )


def list_analytics_dashboards_response(
    *,
    dashboards: list[ProductAnalyticsDashboard],
    query: ProductApiListQuery | None = None,
    context: ProductApiRequestContext | None = None,
    message: str = "Analytics dashboards listed successfully.",
) -> ProductApiResponse:
    """Build analytics dashboard list response."""
    validate_product_analytics_dashboards(dashboards)

    pagination = query.pagination if query else ProductApiPagination()
    paged_dashboards = paginate_product_analytics_dashboards(
        dashboards=dashboards,
        pagination=pagination,
    )
    result = ProductApiListResult(
        items=[dashboard.to_dict() for dashboard in paged_dashboards],
        pagination=pagination,
        total_items=len(dashboards),
        metadata={
            "dashboard_ids": [dashboard.dashboard_id.strip() for dashboard in dashboards],
        },
    )

    return list_result_to_response(
        result=result,
        context=context,
        message=message,
    )


def create_analytics_operation_response(
    *,
    dashboard: ProductAnalyticsDashboard,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Build create analytics dashboard operation response."""
    if not isinstance(dashboard, ProductAnalyticsDashboard):
        raise ValueError("Dashboard must be a ProductAnalyticsDashboard.")

    return operation_result_to_response(
        result=ProductApiOperationResult(
            operation=ProductApiOperation.CREATE,
            resource_type=ProductApiRequestType.ANALYTICS,
            resource_id=dashboard.dashboard_id,
            accepted=True,
            result={
                "dashboard": dashboard.to_dict(),
            },
        ),
        context=context,
        message="Analytics dashboard created successfully.",
    )


def get_analytics_dashboard_response(
    *,
    store: ProductAnalyticsStore,
    dashboard_id: str,
    context: ProductApiRequestContext | None = None,
) -> ProductApiResponse:
    """Get analytics dashboard from store and return response."""
    if not isinstance(store, ProductAnalyticsStore):
        raise ValueError("Store must be a ProductAnalyticsStore.")

    dashboard = store.get(dashboard_id)

    if dashboard is None:
        return product_api_failure(
            message="Analytics dashboard not found.",
            code=ProductApiErrorCode.NOT_FOUND,
            details={
                "dashboard_id": dashboard_id.strip(),
            },
            context=context,
        )

    return analytics_dashboard_to_response(
        dashboard=dashboard,
        context=context,
        message="Analytics dashboard retrieved successfully.",
    )


def paginate_product_analytics_dashboards(
    *,
    dashboards: list[ProductAnalyticsDashboard],
    pagination: ProductApiPagination,
) -> list[ProductAnalyticsDashboard]:
    """Paginate product analytics dashboards."""
    validate_product_analytics_dashboards(dashboards)

    if not isinstance(pagination, ProductApiPagination):
        raise ValueError("Pagination must be a ProductApiPagination.")

    return dashboards[pagination.offset : pagination.offset + pagination.page_size]


def filter_product_analytics_series(
    *,
    series: list[ProductAnalyticsSeries],
    metric_type: ProductAnalyticsMetricType | str | None = None,
    period: ProductAnalyticsPeriod | str | None = None,
    trend: ProductAnalyticsTrend | str | None = None,
) -> list[ProductAnalyticsSeries]:
    """Filter product analytics series."""
    validate_product_analytics_series_list(series)

    filtered = list(series)

    if metric_type is not None:
        normalized_metric_type = normalize_product_analytics_metric_type(metric_type)
        filtered = [
            item
            for item in filtered
            if normalize_product_analytics_metric_type(item.metric_type) == normalized_metric_type
        ]

    if period is not None:
        normalized_period = normalize_product_analytics_period(period)
        filtered = [
            item
            for item in filtered
            if normalize_product_analytics_period(item.period) == normalized_period
        ]

    if trend is not None:
        normalized_trend = normalize_product_analytics_trend(trend)
        filtered = [
            item
            for item in filtered
            if item.trend == normalized_trend
        ]

    return filtered


def validate_product_analytics_dashboards(
    dashboards: list[ProductAnalyticsDashboard],
) -> list[ProductAnalyticsDashboard]:
    """Validate product analytics dashboards."""
    if not isinstance(dashboards, list):
        raise ValueError("Dashboards must be a list.")

    for dashboard in dashboards:
        if not isinstance(dashboard, ProductAnalyticsDashboard):
            raise ValueError("Dashboards must contain ProductAnalyticsDashboard objects.")

    return dashboards