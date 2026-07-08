"""
Unit tests for AQOS product API package exports.
"""

import inspect

import aqos.product_api as product_api


EXPECTED_PRODUCT_API_EXPORTS = sorted(
    [
        "ProductAnalyticsDashboard",
        "ProductAnalyticsMetric",
        "ProductAnalyticsMetricType",
        "ProductAnalyticsPeriod",
        "ProductAnalyticsPoint",
        "ProductAnalyticsSeries",
        "ProductAnalyticsStore",
        "ProductAnalyticsSummary",
        "ProductAnalyticsTrend",
        "ProductApiError",
        "ProductApiErrorCode",
        "ProductApiFilter",
        "ProductApiGateway",
        "ProductApiListQuery",
        "ProductApiListResult",
        "ProductApiMeta",
        "ProductApiOperation",
        "ProductApiOperationResult",
        "ProductApiPagination",
        "ProductApiRequest",
        "ProductApiRequestContext",
        "ProductApiRequestType",
        "ProductApiResponse",
        "ProductApiSort",
        "ProductApiStatus",
        "ProductApiStores",
        "ProductFilterOperator",
        "ProductPortfolioPosition",
        "ProductPortfolioSnapshot",
        "ProductPortfolioStore",
        "ProductPortfolioSummary",
        "ProductPositionSide",
        "ProductPositionStatus",
        "ProductResearchFinding",
        "ProductResearchFindingType",
        "ProductResearchPriority",
        "ProductResearchReport",
        "ProductResearchRequest",
        "ProductResearchStatus",
        "ProductResearchStore",
        "ProductResearchSummary",
        "ProductSignalDirection",
        "ProductSignalPayload",
        "ProductSignalRequest",
        "ProductSignalStatus",
        "ProductSignalStore",
        "ProductSignalStrength",
        "ProductSignalSummary",
        "ProductSortDirection",
        "analytics_dashboard_to_response",
        "analytics_metric_default_unit",
        "analytics_metric_to_response",
        "analytics_series_to_response",
        "approve_signal_response",
        "archive_research_finding",
        "build_product_analytics_dashboard",
        "build_product_analytics_metric",
        "build_product_analytics_point",
        "build_product_analytics_series",
        "build_product_analytics_store",
        "build_product_api_context",
        "build_product_api_error",
        "build_product_api_filter",
        "build_product_api_gateway",
        "build_product_api_list_query",
        "build_product_api_list_result",
        "build_product_api_meta",
        "build_product_api_operation_result",
        "build_product_api_pagination",
        "build_product_api_request",
        "build_product_api_response",
        "build_product_api_sort",
        "build_product_api_stores",
        "build_product_portfolio_position",
        "build_product_portfolio_snapshot",
        "build_product_portfolio_store",
        "build_product_portfolio_summary",
        "build_product_research_finding",
        "build_product_research_report",
        "build_product_research_request",
        "build_product_research_store",
        "build_product_signal_payload",
        "build_product_signal_request",
        "build_product_signal_store",
        "build_product_signal_summary",
        "calculate_signal_risk_reward_ratio",
        "close_portfolio_position",
        "create_analytics_operation_response",
        "create_portfolio_operation_response",
        "create_research_operation_response",
        "create_signal_operation_response",
        "empty_list_response",
        "filter_product_analytics_series",
        "filter_product_positions",
        "filter_product_research_findings",
        "filter_product_signals",
        "get_analytics_dashboard_response",
        "get_portfolio_response",
        "get_research_finding_response",
        "get_signal_response",
        "list_analytics_dashboards_response",
        "list_portfolios_response",
        "list_research_findings_response",
        "list_result_to_response",
        "list_signals_response",
        "normalize_product_analytics_metric_type",
        "normalize_product_analytics_period",
        "normalize_product_analytics_trend",
        "normalize_product_api_error_code",
        "normalize_product_api_operation",
        "normalize_product_api_request_type",
        "normalize_product_api_status",
        "normalize_product_filter_operator",
        "normalize_product_position_side",
        "normalize_product_position_status",
        "normalize_product_research_finding_type",
        "normalize_product_research_priority",
        "normalize_product_research_status",
        "normalize_product_signal_direction",
        "normalize_product_signal_status",
        "normalize_product_signal_strength",
        "normalize_product_sort_direction",
        "operation_result_to_response",
        "paginate_product_analytics_dashboards",
        "paginate_product_portfolios",
        "paginate_product_research_findings",
        "paginate_product_signals",
        "portfolio_snapshot_to_response",
        "product_api_error",
        "product_api_failure",
        "product_api_health_response",
        "product_api_success",
        "product_api_summary",
        "product_api_summary_response",
        "reject_signal_response",
        "research_finding_to_response",
        "research_report_to_response",
        "resolve_signal_strength",
        "route_product_api_request",
        "safe_product_api_call",
        "signal_payload_to_response",
        "summarize_product_analytics",
        "summarize_product_research_findings",
        "update_research_status",
        "update_signal_status",
        "validate_boolean",
        "validate_currency",
        "validate_field_name",
        "validate_list_items",
        "validate_metadata",
        "validate_metric_value",
        "validate_non_empty_string",
        "validate_non_negative_float",
        "validate_non_negative_integer",
        "validate_percentage",
        "validate_positive_float",
        "validate_positive_integer",
        "validate_product_analytics_dashboards",
        "validate_product_analytics_metrics",
        "validate_product_analytics_points",
        "validate_product_analytics_series_list",
        "validate_product_api_stores",
        "validate_product_filters",
        "validate_product_portfolio_positions",
        "validate_product_portfolio_snapshots",
        "validate_product_research_findings",
        "validate_product_signal_payloads",
        "validate_product_sorts",
        "validate_product_symbol",
        "validate_product_timeframe",
        "validate_research_tags",
        "validate_signal_price",
        "validate_string",
    ],
)


CLASS_EXPORTS = [
    "ProductAnalyticsDashboard",
    "ProductAnalyticsMetric",
    "ProductAnalyticsMetricType",
    "ProductAnalyticsPeriod",
    "ProductAnalyticsPoint",
    "ProductAnalyticsSeries",
    "ProductAnalyticsStore",
    "ProductAnalyticsSummary",
    "ProductAnalyticsTrend",
    "ProductApiError",
    "ProductApiErrorCode",
    "ProductApiFilter",
    "ProductApiGateway",
    "ProductApiListQuery",
    "ProductApiListResult",
    "ProductApiMeta",
    "ProductApiOperation",
    "ProductApiOperationResult",
    "ProductApiPagination",
    "ProductApiRequest",
    "ProductApiRequestContext",
    "ProductApiRequestType",
    "ProductApiResponse",
    "ProductApiSort",
    "ProductApiStatus",
    "ProductApiStores",
    "ProductFilterOperator",
    "ProductPortfolioPosition",
    "ProductPortfolioSnapshot",
    "ProductPortfolioStore",
    "ProductPortfolioSummary",
    "ProductPositionSide",
    "ProductPositionStatus",
    "ProductResearchFinding",
    "ProductResearchFindingType",
    "ProductResearchPriority",
    "ProductResearchReport",
    "ProductResearchRequest",
    "ProductResearchStatus",
    "ProductResearchStore",
    "ProductResearchSummary",
    "ProductSignalDirection",
    "ProductSignalPayload",
    "ProductSignalRequest",
    "ProductSignalStatus",
    "ProductSignalStore",
    "ProductSignalStrength",
    "ProductSignalSummary",
    "ProductSortDirection",
]


FUNCTION_EXPORTS = [
    export_name
    for export_name in EXPECTED_PRODUCT_API_EXPORTS
    if export_name not in CLASS_EXPORTS
]


def test_product_api_exports_are_complete():
    assert product_api.__all__ == EXPECTED_PRODUCT_API_EXPORTS


def test_product_api_exports_are_sorted():
    assert product_api.__all__ == sorted(product_api.__all__)


def test_product_api_exports_are_unique():
    assert len(product_api.__all__) == len(set(product_api.__all__))


def test_product_api_exports_exist_on_package():
    for export_name in EXPECTED_PRODUCT_API_EXPORTS:
        assert hasattr(product_api, export_name), export_name


def test_product_api_class_exports_are_classes():
    for export_name in CLASS_EXPORTS:
        assert inspect.isclass(getattr(product_api, export_name)), export_name


def test_product_api_function_exports_are_callables():
    for export_name in FUNCTION_EXPORTS:
        assert callable(getattr(product_api, export_name)), export_name


def test_product_api_core_exports_import_directly():
    from aqos.product_api import (  # noqa: PLC0415
        ProductAnalyticsDashboard,
        ProductApiGateway,
        ProductApiRequest,
        ProductApiResponse,
        ProductApiStores,
        ProductPortfolioSnapshot,
        ProductResearchFinding,
        ProductSignalPayload,
    )

    assert ProductAnalyticsDashboard.__name__ == "ProductAnalyticsDashboard"
    assert ProductApiGateway.__name__ == "ProductApiGateway"
    assert ProductApiRequest.__name__ == "ProductApiRequest"
    assert ProductApiResponse.__name__ == "ProductApiResponse"
    assert ProductApiStores.__name__ == "ProductApiStores"
    assert ProductPortfolioSnapshot.__name__ == "ProductPortfolioSnapshot"
    assert ProductResearchFinding.__name__ == "ProductResearchFinding"
    assert ProductSignalPayload.__name__ == "ProductSignalPayload"


def test_product_api_export_groups_exist():
    base_exports = {
        "ProductApiError",
        "ProductApiErrorCode",
        "ProductApiMeta",
        "ProductApiRequestContext",
        "ProductApiResponse",
        "ProductApiStatus",
    }
    contract_exports = {
        "ProductApiFilter",
        "ProductApiListQuery",
        "ProductApiOperation",
        "ProductApiPagination",
        "ProductApiRequest",
        "ProductApiRequestType",
    }
    signal_exports = {
        "ProductSignalDirection",
        "ProductSignalPayload",
        "ProductSignalStore",
        "ProductSignalSummary",
    }
    portfolio_exports = {
        "ProductPortfolioPosition",
        "ProductPortfolioSnapshot",
        "ProductPortfolioStore",
        "ProductPortfolioSummary",
    }
    research_exports = {
        "ProductResearchFinding",
        "ProductResearchReport",
        "ProductResearchStore",
        "ProductResearchSummary",
    }
    analytics_exports = {
        "ProductAnalyticsDashboard",
        "ProductAnalyticsMetric",
        "ProductAnalyticsSeries",
        "ProductAnalyticsStore",
    }
    integration_exports = {
        "ProductApiGateway",
        "ProductApiStores",
        "route_product_api_request",
        "product_api_health_response",
    }

    exports = set(product_api.__all__)

    assert base_exports.issubset(exports)
    assert contract_exports.issubset(exports)
    assert signal_exports.issubset(exports)
    assert portfolio_exports.issubset(exports)
    assert research_exports.issubset(exports)
    assert analytics_exports.issubset(exports)
    assert integration_exports.issubset(exports)