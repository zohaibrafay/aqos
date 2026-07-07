"""
Unit tests for AQOS CLI package exports.
"""

import inspect

import aqos.cli as cli


EXPECTED_CLI_EXPORTS = [
    "CliBacktestNameRequest",
    "CliBacktestWorkflowRequest",
    "CliClosePositionRequest",
    "CliCompareBacktestsRequest",
    "CliCreateExperimentRequest",
    "CliEvaluationBacktestRequest",
    "CliExecutionOrderRequest",
    "CliExecutionSummaryRequest",
    "CliExecutionTradeRequest",
    "CliExperimentPlanRequest",
    "CliFillOrderRequest",
    "CliHealthRequest",
    "CliMarketRequest",
    "CliMarketStrategyWorkflowRequest",
    "CliMemoryIdRequest",
    "CliMemorySummaryRequest",
    "CliMemoryWorkflowRequest",
    "CliOrchestratorRouteRequest",
    "CliOrderIdRequest",
    "CliOutput",
    "CliOutputFormat",
    "CliPatternMemoryRequest",
    "CliRecallMemoryRequest",
    "CliRememberMemoryRequest",
    "CliResearchFindingRequest",
    "CliResearchHypothesisRequest",
    "CliResearchSummaryRequest",
    "CliResearchWorkflowRequest",
    "CliRiskExecutionWorkflowRequest",
    "CliRiskRequest",
    "CliStrategyRequest",
    "CliStrategyRiskWorkflowRequest",
    "CliTradeMemoryRequest",
    "CliTradeWorkflowRequest",
    "build_cli_output",
    "build_evaluation_cli_output",
    "build_execution_cli_output",
    "build_health_cli_output",
    "build_market_cli_output",
    "build_memory_cli_output",
    "build_orchestrator_cli_output",
    "build_research_cli_output",
    "build_risk_cli_output",
    "build_strategy_cli_output",
    "cli_agent_health",
    "cli_agents_health",
    "cli_api_health",
    "cli_approve_trade",
    "cli_assess_trade",
    "cli_backtest_summary",
    "cli_backtest_workflow",
    "cli_calendar_context",
    "cli_cancel_order",
    "cli_close_position",
    "cli_compare_backtests",
    "cli_create_experiment",
    "cli_dependency_health",
    "cli_entry_check",
    "cli_evaluation_report",
    "cli_execute_trade",
    "cli_execution_summary",
    "cli_exit_check",
    "cli_experiment_plan",
    "cli_fill_order",
    "cli_forget",
    "cli_get_memory",
    "cli_market_snapshot",
    "cli_market_state",
    "cli_market_strategy_workflow",
    "cli_memory_summary",
    "cli_memory_workflow",
    "cli_news_context",
    "cli_orchestrator_route",
    "cli_order_status",
    "cli_pattern_memory",
    "cli_performance_grade",
    "cli_place_order",
    "cli_position_size",
    "cli_recall",
    "cli_record_finding",
    "cli_regime_summary",
    "cli_reject_reason",
    "cli_remember",
    "cli_research_hypothesis",
    "cli_research_summary",
    "cli_research_workflow",
    "cli_risk_execution_workflow",
    "cli_risk_handoff",
    "cli_run_backtest",
    "cli_strategy_decision",
    "cli_strategy_explanation",
    "cli_strategy_handoff",
    "cli_strategy_risk_workflow",
    "cli_strategy_signal",
    "cli_system_health",
    "cli_trade_memory",
    "cli_trade_workflow",
    "cli_trend_summary",
    "execute_evaluation_operation",
    "execute_execution_operation",
    "execute_health_operation",
    "execute_market_operation",
    "execute_memory_operation",
    "execute_orchestrator_operation",
    "execute_research_operation",
    "execute_risk_operation",
    "execute_strategy_operation",
    "format_api_response",
    "format_api_response_text",
    "format_cli_error",
    "format_json",
    "format_key_value_lines",
    "format_scalar",
    "format_text_data",
    "normalize_output_format",
    "run_risk_cli_operation",
    "run_strategy_cli_operation",
]


def test_cli_exports_are_complete():
    assert cli.__all__ == EXPECTED_CLI_EXPORTS


def test_cli_exports_are_unique():
    assert len(cli.__all__) == len(set(cli.__all__))


def test_cli_exports_are_sorted():
    assert cli.__all__ == sorted(cli.__all__)


def test_cli_exports_exist_on_package():
    for export_name in EXPECTED_CLI_EXPORTS:
        assert hasattr(cli, export_name), export_name


def test_cli_request_exports_are_classes():
    request_exports = [
        export_name
        for export_name in EXPECTED_CLI_EXPORTS
        if export_name.startswith("Cli")
    ]

    for export_name in request_exports:
        exported = getattr(cli, export_name)
        assert inspect.isclass(exported), export_name


def test_cli_function_exports_are_callables():
    function_exports = [
        export_name
        for export_name in EXPECTED_CLI_EXPORTS
        if not export_name.startswith("Cli")
    ]

    for export_name in function_exports:
        exported = getattr(cli, export_name)
        assert callable(exported), export_name


def test_cli_core_exports_import_directly():
    from aqos.cli import (  # noqa: PLC0415
        CliOutput,
        CliOutputFormat,
        cli_api_health,
        cli_market_state,
        cli_strategy_signal,
        cli_risk_handoff,
        cli_execute_trade,
        cli_run_backtest,
        cli_research_summary,
        cli_memory_summary,
        cli_trade_workflow,
    )

    assert CliOutput is cli.CliOutput
    assert CliOutputFormat is cli.CliOutputFormat
    assert cli_api_health is cli.cli_api_health
    assert cli_market_state is cli.cli_market_state
    assert cli_strategy_signal is cli.cli_strategy_signal
    assert cli_risk_handoff is cli.cli_risk_handoff
    assert cli_execute_trade is cli.cli_execute_trade
    assert cli_run_backtest is cli.cli_run_backtest
    assert cli_research_summary is cli.cli_research_summary
    assert cli_memory_summary is cli.cli_memory_summary
    assert cli_trade_workflow is cli.cli_trade_workflow