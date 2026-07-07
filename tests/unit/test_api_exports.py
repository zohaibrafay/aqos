"""
Unit tests for AQOS API package exports.
"""

import aqos.api as api


EXPECTED_API_EXPORTS = {
    "API_SERVICE_NAME",
    "API_VERSION",
    "ApiError",
    "ApiResponse",
    "ApiStatus",
    "BacktestNameRequest",
    "BacktestWorkflowRequest",
    "ClosePositionRequest",
    "CompareBacktestsRequest",
    "CreateExperimentRequest",
    "EvaluationBacktestRequest",
    "ExecutionOrderRequest",
    "ExecutionTradeRequest",
    "ExperimentPlanRequest",
    "FillOrderRequest",
    "HealthCheck",
    "HealthStatus",
    "MarketRequest",
    "MarketStrategyWorkflowRequest",
    "MemoryIdRequest",
    "MemoryWorkflowRequest",
    "OrderIdRequest",
    "OrchestratorRouteRequest",
    "PatternMemoryRequest",
    "RecallMemoryRequest",
    "RememberMemoryRequest",
    "ResearchFindingRequest",
    "ResearchHypothesisRequest",
    "ResearchWorkflowRequest",
    "RiskExecutionWorkflowRequest",
    "RiskTradeRequest",
    "StrategyMarketStateRequest",
    "StrategyRiskWorkflowRequest",
    "TradeMemoryRequest",
    "TradeWorkflowRequest",
    "agent_health",
    "agents_health",
    "api_approve_trade",
    "api_assess_trade",
    "api_backtest_summary",
    "api_backtest_workflow",
    "api_calendar_context",
    "api_cancel_order",
    "api_close_position",
    "api_compare_backtests",
    "api_create_experiment",
    "api_entry_check",
    "api_error",
    "api_evaluation_report",
    "api_execute_trade",
    "api_execution_summary",
    "api_exit_check",
    "api_experiment_plan",
    "api_failure",
    "api_fill_order",
    "api_forget",
    "api_get_memory",
    "api_health",
    "api_market_snapshot",
    "api_market_state",
    "api_market_strategy_workflow",
    "api_memory_summary",
    "api_memory_workflow",
    "api_news_context",
    "api_order_status",
    "api_orchestrator_route",
    "api_pattern_memory",
    "api_performance_grade",
    "api_place_order",
    "api_position_size",
    "api_recall",
    "api_record_finding",
    "api_regime_summary",
    "api_reject_reason",
    "api_remember",
    "api_research_hypothesis",
    "api_research_summary",
    "api_research_workflow",
    "api_risk_execution_workflow",
    "api_risk_handoff",
    "api_run_backtest",
    "api_strategy_decision",
    "api_strategy_explanation",
    "api_strategy_handoff",
    "api_strategy_risk_workflow",
    "api_strategy_signal",
    "api_success",
    "api_trade_memory",
    "api_trade_workflow",
    "api_trend_summary",
    "build_api_metadata",
    "build_execution_trade_request",
    "build_market_request",
    "build_risk_trade_request",
    "build_strategy_market_state_request",
    "dependency_health",
    "evaluation_agent_operation",
    "exception_failure",
    "execution_agent_operation",
    "health_check",
    "market_agent_operation",
    "memory_agent_operation",
    "normalize_backtest_request",
    "normalize_execution_trade",
    "normalize_experiment_plan_request",
    "normalize_finding_request",
    "normalize_hypothesis_request",
    "normalize_market_state",
    "normalize_pattern_memory_request",
    "normalize_recall_request",
    "normalize_remember_request",
    "normalize_trade_memory_request",
    "normalize_trade_request",
    "not_found_failure",
    "orchestrator_operation",
    "research_agent_operation",
    "resolve_overall_health",
    "risk_agent_operation",
    "strategy_agent_operation",
    "system_health",
    "utc_timestamp",
    "validation_failure",
}


def test_api_all_exports_match_expected_public_boundary():
    assert set(api.__all__) == EXPECTED_API_EXPORTS


def test_api_all_exports_are_available_on_package():
    for export_name in api.__all__:
        assert hasattr(api, export_name), export_name


def test_api_all_exports_are_unique():
    assert len(api.__all__) == len(set(api.__all__))


def test_api_all_exports_are_sorted_for_maintenance():
    assert api.__all__ == sorted(api.__all__)


def test_api_response_exports_are_available():
    response = api.api_success(
        message="Export test passed.",
        data={
            "module": "api",
        },
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["status"] == "success"
    assert payload["message"] == "Export test passed."
    assert payload["data"] == {
        "module": "api",
    }


def test_api_request_object_exports_are_instantiable():
    assert api.MarketRequest().to_payload() == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
    }

    assert api.StrategyMarketStateRequest().to_payload()["market_state"][
        "symbol"
    ] == "XAUUSD"

    assert api.RiskTradeRequest().to_payload()["trade_request"]["side"] == "buy"

    assert api.ExecutionTradeRequest().to_payload()["trade"]["symbol"] == "XAUUSD"

    assert api.EvaluationBacktestRequest().to_payload()["name"] == (
        "api-backtest-run"
    )

    assert api.ResearchHypothesisRequest().to_payload()["symbol"] == "XAUUSD"

    assert api.RememberMemoryRequest(
        memory_id="memory-1",
        content="Memory content.",
    ).to_payload()["memory_type"] == "observation"

    assert api.TradeWorkflowRequest().to_payload()["symbol"] == "XAUUSD"


def test_api_operation_exports_are_callable():
    operation_names = [
        "api_health",
        "api_market_state",
        "api_strategy_signal",
        "api_risk_handoff",
        "api_execute_trade",
        "api_run_backtest",
        "api_research_hypothesis",
        "api_remember",
        "api_trade_workflow",
    ]

    for operation_name in operation_names:
        assert callable(getattr(api, operation_name)), operation_name


def test_api_agent_operation_exports_are_callable():
    operation_names = [
        "market_agent_operation",
        "strategy_agent_operation",
        "risk_agent_operation",
        "execution_agent_operation",
        "evaluation_agent_operation",
        "research_agent_operation",
        "memory_agent_operation",
        "orchestrator_operation",
    ]

    for operation_name in operation_names:
        assert callable(getattr(api, operation_name)), operation_name