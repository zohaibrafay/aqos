"""
Common Utilities adoption integration tests.

Validates that Sprint 013 common utilities can safely operate on
real AQOS subsystem outputs from services, agents, and orchestrated workflows.
"""

from aqos.agents import (
    AgentOrchestrator,
    DataAgent,
    EvaluationAgent,
    MarketAgent,
    RiskAgent,
    StrategyAgent,
)
from aqos.common import (
    DEFAULT_ACCOUNT_BALANCE,
    DEFAULT_RISK_PERCENT,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
    OHLCV_COLUMNS,
    build_compound_id,
    build_error_dict,
    build_timestamp_id,
    compact_dict,
    exception_to_dict,
    flatten_dict,
    from_json,
    max_drawdown,
    normalize_id,
    parse_datetime,
    profit_factor,
    safe_execute,
    serialize_dict,
    to_json,
    to_serializable,
    unflatten_dict,
    validate_account_balance,
    validate_ohlcv_record,
    validate_price,
    validate_risk_percent,
    validate_side,
    validate_signal,
    validate_symbol,
    validate_timeframe,
    win_rate,
)


def test_common_constants_match_integration_defaults(
    integration_symbol: str,
    integration_timeframe: str,
    integration_account_balance: float,
    integration_risk_percent: float,
):
    assert integration_symbol == DEFAULT_SYMBOL
    assert integration_timeframe == DEFAULT_TIMEFRAME
    assert integration_account_balance == DEFAULT_ACCOUNT_BALANCE
    assert integration_risk_percent == DEFAULT_RISK_PERCENT
    assert OHLCV_COLUMNS == (
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    )


def test_common_validators_accept_sample_ohlcv_records(sample_ohlcv_records):
    for record in sample_ohlcv_records:
        validated_record = validate_ohlcv_record(record)

        assert validated_record == record
        assert validate_symbol("xauusd") == "XAUUSD"
        assert validate_timeframe("h1") == "H1"


def test_common_validators_accept_market_agent_output(
    market_agent: MarketAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    result = market_agent.execute(
        action="market-state",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert result.success is True

    assert validate_symbol(result.data["symbol"]) == integration_symbol
    assert validate_timeframe(result.data["timeframe"]) == integration_timeframe
    assert validate_price(result.data["close"]) == 2025.0


def test_common_validators_accept_strategy_and_risk_outputs(
    market_agent: MarketAgent,
    strategy_agent: StrategyAgent,
    risk_agent: RiskAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    market_result = market_agent.execute(
        action="market-state",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    strategy_result = strategy_agent.execute(
        action="handoff",
        payload={
            "market_state": {
                **market_result.data,
                "entry_price": market_result.data["close"],
            },
        },
    )

    assert strategy_result.success is True

    assert validate_signal(strategy_result.data["signal"]) == "buy"
    assert validate_price(strategy_result.data["entry_price"]) == 2025.0
    assert validate_price(strategy_result.data["stop_loss_price"]) > 0

    risk_result = risk_agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": {
                "symbol": strategy_result.data["symbol"],
                "side": strategy_result.data["signal"],
                "account_balance": DEFAULT_ACCOUNT_BALANCE,
                "risk_percent": DEFAULT_RISK_PERCENT,
                "entry_price": strategy_result.data["entry_price"],
                "stop_loss_price": strategy_result.data["stop_loss_price"],
            },
        },
    )

    assert risk_result.success is True
    assert risk_result.data["allowed"] is True

    assert validate_side(risk_result.data["side"]) == "buy"
    assert validate_account_balance(DEFAULT_ACCOUNT_BALANCE) == 10_000.0
    assert validate_risk_percent(risk_result.data["risk_percent"]) == 0.01
    assert validate_price(risk_result.data["entry_price"]) == 2025.0


def test_common_id_helpers_can_build_workflow_ids(
    integration_symbol: str,
    integration_timeframe: str,
):
    compound_id = build_compound_id(
        integration_symbol,
        integration_timeframe,
        "trade workflow",
    )
    timestamp_id = build_timestamp_id(
        prefix="integration",
        timestamp=parse_datetime("2026-01-01T00:00:00Z"),
    )

    assert compound_id == "xauusd-h1-trade-workflow"
    assert timestamp_id == "integration-20260101000000"
    assert normalize_id("XAUUSD H1 Trade Workflow") == "xauusd-h1-trade-workflow"


def test_common_time_utils_parse_fixture_datetimes(sample_ohlcv_records):
    parsed = parse_datetime(sample_ohlcv_records[0]["timestamp"])

    assert parsed.year == 2026
    assert parsed.month == 1
    assert parsed.day == 1
    assert parsed.hour == 0


def test_common_serialization_handles_agent_results(
    market_agent: MarketAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    result = market_agent.execute(
        action="market-state",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    serialized = to_serializable(result.data)
    json_text = to_json(serialized)
    restored = from_json(json_text)

    assert restored["symbol"] == integration_symbol
    assert restored["timeframe"] == integration_timeframe
    assert restored["close"] == 2025.0


def test_common_serialization_flattens_orchestrator_result(
    agent_orchestrator: AgentOrchestrator,
    integration_symbol: str,
    integration_timeframe: str,
):
    result = agent_orchestrator.execute(
        action="market-strategy-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert result.success is True

    flattened = flatten_dict(result.data)

    assert flattened["market_state.symbol"] == integration_symbol
    assert flattened["market_state.timeframe"] == integration_timeframe
    assert flattened["strategy_handoff.signal"] == "buy"

    unflattened = unflatten_dict(flattened)

    assert unflattened["market_state"]["symbol"] == integration_symbol
    assert unflattened["strategy_handoff"]["signal"] == "buy"


def test_common_serialization_compacts_agent_payload():
    payload = {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "empty": "",
        "none": None,
        "metadata": {},
        "risk_percent": 0.01,
    }

    compacted = compact_dict(payload)

    assert compacted == {
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "risk_percent": 0.01,
    }


def test_common_math_helpers_accept_backtest_like_values():
    profits = [
        100.0,
        -50.0,
        25.0,
    ]
    equity_curve = [
        10_000.0,
        10_100.0,
        10_050.0,
        10_075.0,
    ]

    assert win_rate(profits) == 2 / 3
    assert profit_factor(profits) == 2.5
    assert max_drawdown(equity_curve) < 0


def test_common_math_helpers_accept_evaluation_agent_output(
    evaluation_agent: EvaluationAgent,
):
    result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "common-utils-backtest",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert result.success is True

    assert validate_price(result.data["initial_balance"]) == 10_000.0
    assert validate_price(result.data["final_balance"]) == 10_075.0
    assert result.data["total_profit"] == 75.0


def test_common_error_helpers_can_format_agent_failure(
    data_agent: DataAgent,
):
    result = data_agent.execute(
        action="availability",
        payload={
            "timeframe": "H1",
        },
    )

    assert result.success is False

    error = build_error_dict(
        code="agent_failure",
        message=result.message,
        category="agent",
        details={
            "agent": data_agent.name,
            "action": "availability",
        },
    )

    assert error["code"] == "AGENT_FAILURE"
    assert error["category"] == "agent"
    assert error["details"]["agent"] == "data-agent"


def test_common_exception_helpers_can_serialize_exceptions():
    error = exception_to_dict(ValueError("Invalid integration payload."))

    assert error["code"] == "VALUEERROR"
    assert error["message"] == "Invalid integration payload."
    assert error["details"]["exception_type"] == "ValueError"


def test_common_safe_execute_handles_expected_exception():
    result = safe_execute(
        lambda: 1 / 0,
        default="safe-default",
    )

    assert result == "safe-default"


def test_common_serialize_dict_handles_cross_subsystem_payload(
    agent_orchestrator: AgentOrchestrator,
    integration_symbol: str,
    integration_timeframe: str,
):
    result = agent_orchestrator.execute(
        action="trade-workflow",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert result.success is True

    serialized = serialize_dict(result.data)

    assert serialized["market_state"]["symbol"] == integration_symbol
    assert serialized["strategy_handoff"]["signal"] == "buy"
    assert serialized["risk_handoff"]["allowed"] is True
    assert serialized["execution"]["symbol"] == integration_symbol