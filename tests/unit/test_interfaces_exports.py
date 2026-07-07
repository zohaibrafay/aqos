"""
Unit tests for interfaces package exports.
"""

from aqos.interfaces import (
    APIInterface,
    AgentInterface,
    BacktestRequest,
    BacktestResponse,
    CLIInterface,
    DashboardInterface,
    DataProviderInterface,
    ExperimentRequest,
    ExperimentResponse,
    InterfaceEnvelope,
    MarketDataRequest,
    MemoryInterface,
    MemoryInterfaceRecord,
    MemoryInterfaceSearchResult,
    ModelInterface,
    PredictionRequest,
    PredictionResponse,
    RiskInterface,
    RiskInterfaceDecision,
    RiskRequest,
    RiskResponse,
    StrategyInterface,
    StrategyInterfaceDecision,
    StrategyRequest,
    StrategyResponse,
)


def test_interfaces_exports():
    assert APIInterface is not None
    assert AgentInterface is not None
    assert BacktestRequest is not None
    assert BacktestResponse is not None
    assert CLIInterface is not None
    assert DashboardInterface is not None
    assert DataProviderInterface is not None
    assert ExperimentRequest is not None
    assert ExperimentResponse is not None
    assert InterfaceEnvelope is not None
    assert MarketDataRequest is not None
    assert MemoryInterface is not None
    assert MemoryInterfaceRecord is not None
    assert MemoryInterfaceSearchResult is not None
    assert ModelInterface is not None
    assert PredictionRequest is not None
    assert PredictionResponse is not None
    assert RiskInterface is not None
    assert RiskInterfaceDecision is not None
    assert RiskRequest is not None
    assert RiskResponse is not None
    assert StrategyInterface is not None
    assert StrategyInterfaceDecision is not None
    assert StrategyRequest is not None
    assert StrategyResponse is not None


def test_application_interface_instances_can_be_created():
    assert isinstance(APIInterface(), APIInterface)
    assert isinstance(AgentInterface(), AgentInterface)
    assert isinstance(CLIInterface(), CLIInterface)
    assert isinstance(DashboardInterface(), DashboardInterface)


def test_schema_instances_can_be_created():
    market_request = MarketDataRequest(
        symbol="XAUUSD",
        timeframe="H1",
    )

    prediction_request = PredictionRequest(
        model_name="model-1",
        features=[
            {
                "open": 2000.0,
                "close": 2005.0,
            }
        ],
    )

    prediction_response = PredictionResponse(
        model_name="model-1",
        predictions=[
            "buy",
        ],
    )

    strategy_request = StrategyRequest(
        market_state={
            "trend": "uptrend",
        }
    )

    strategy_response = StrategyResponse(
        signal="buy",
        should_enter=True,
        should_exit=False,
    )

    risk_request = RiskRequest(
        trade_request={
            "symbol": "XAUUSD",
            "side": "buy",
        }
    )

    risk_response = RiskResponse(
        allowed=True,
        reason="Trade allowed.",
        position_size=1.0,
    )

    backtest_request = BacktestRequest(
        name="run-1",
        profits=[
            100.0,
        ],
        initial_balance=10_000.0,
    )

    backtest_response = BacktestResponse(
        name="run-1",
        total_profit=100.0,
        final_balance=10_100.0,
        win_rate=1.0,
    )

    experiment_request = ExperimentRequest(
        name="experiment-1",
    )

    experiment_response = ExperimentResponse(
        name="experiment-1",
        status="created",
    )

    envelope = InterfaceEnvelope(
        success=True,
        message="ok",
    )

    assert market_request.symbol == "XAUUSD"
    assert prediction_request.model_name == "model-1"
    assert prediction_response.predictions == ["buy"]
    assert strategy_request.market_state["trend"] == "uptrend"
    assert strategy_response.signal == "buy"
    assert risk_request.trade_request["symbol"] == "XAUUSD"
    assert risk_response.allowed is True
    assert backtest_request.name == "run-1"
    assert backtest_response.total_profit == 100.0
    assert experiment_request.name == "experiment-1"
    assert experiment_response.status == "created"
    assert envelope.success is True


def test_memory_schema_instances_can_be_created():
    record = MemoryInterfaceRecord(
        memory_id="memory-1",
        content="XAUUSD bullish breakout",
    )

    result = MemoryInterfaceSearchResult(
        record=record,
        score=1.0,
    )

    assert record.memory_id == "memory-1"
    assert result.record.memory_id == "memory-1"
    assert result.score == 1.0


def test_interface_decision_instances_can_be_created():
    strategy_decision = StrategyInterfaceDecision(
        signal="buy",
        should_enter=True,
        should_exit=False,
    )

    risk_decision = RiskInterfaceDecision(
        allowed=True,
        reason="Trade allowed.",
        position_size=1.0,
    )

    assert strategy_decision.signal == "buy"
    assert risk_decision.allowed is True