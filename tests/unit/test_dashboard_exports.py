"""
Unit tests for AQOS dashboard package exports.
"""

import aqos.dashboard as dashboard


def test_dashboard_all_exports_are_sorted_and_unique():
    assert dashboard.__all__ == sorted(dashboard.__all__)
    assert len(dashboard.__all__) == len(set(dashboard.__all__))


def test_dashboard_all_exports_exist():
    for export_name in dashboard.__all__:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_base_exports_exist():
    expected_exports = [
        "DashboardComponent",
        "DashboardComponentType",
        "DashboardIssue",
        "DashboardMetric",
        "DashboardPayload",
        "DashboardRefreshMode",
        "DashboardSeverity",
        "DashboardStatus",
        "DashboardTimeRange",
        "build_dashboard_component",
        "build_dashboard_issue",
        "build_dashboard_metric",
        "build_dashboard_payload",
        "build_dashboard_time_range",
        "dashboard_error_payload",
        "dashboard_success_payload",
        "normalize_dashboard_component_type",
        "normalize_dashboard_refresh_mode",
        "normalize_dashboard_severity",
        "normalize_dashboard_status",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_widget_exports_exist():
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
        "widget_to_dashboard_component",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_market_exports_exist():
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
        "market_rows_to_price_points",
        "market_rows_to_snapshot",
        "quote_payload_to_market_snapshot",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_signal_exports_exist():
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
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_portfolio_exports_exist():
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
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_status_exports_exist():
    expected_exports = [
        "BrokerProviderStatusSnapshot",
        "IntegrationHealthState",
        "IntegrationStatusItem",
        "IntegrationStatusKind",
        "broker_config_to_integration_item",
        "broker_registry_to_status_items",
        "build_broker_provider_status_card",
        "build_broker_provider_status_payload",
        "build_broker_provider_status_snapshot",
        "build_broker_provider_status_snapshot_from_registries",
        "build_broker_status_widget",
        "build_integration_status_item",
        "build_provider_status_widget",
        "build_status_summary_widget",
        "build_status_table_widget",
        "provider_config_to_integration_item",
        "provider_registry_to_status_items",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_hub_exports_exist():
    expected_exports = [
        "DashboardAggregationHub",
        "DashboardAggregationMode",
        "DashboardAggregationSnapshot",
        "DashboardSection",
        "DashboardSectionKind",
        "aggregate_dashboard_payloads",
        "build_aggregation_summary_metrics",
        "build_dashboard_aggregation_hub",
        "build_dashboard_aggregation_snapshot",
        "build_dashboard_section",
        "build_section_from_payload",
        "build_section_summary_components",
        "dashboard_aggregation_error_payload",
        "infer_aggregation_status",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name


def test_dashboard_serialization_exports_exist():
    expected_exports = [
        "DashboardApiEnvelope",
        "DashboardApiResponseStatus",
        "DashboardPagination",
        "DashboardSerializationFormat",
        "build_dashboard_api_envelope",
        "build_dashboard_pagination",
        "build_frontend_ready_dashboard_payload",
        "dashboard_component_to_dict",
        "dashboard_components_to_collection_envelope",
        "dashboard_envelope_to_json",
        "dashboard_error_api_envelope",
        "dashboard_issue_to_dict",
        "dashboard_metric_to_dict",
        "dashboard_metrics_to_collection_envelope",
        "dashboard_payload_to_api_envelope",
        "dashboard_payload_to_dict",
        "dashboard_payload_to_json",
        "dashboard_payloads_to_collection_envelope",
        "frontend_response_from_error",
        "frontend_response_from_payload",
        "sanitize_dashboard_value",
    ]

    for export_name in expected_exports:
        assert hasattr(dashboard, export_name), export_name