"""
Unit tests for AgentOrchestrator.
"""

from aqos.agents import (
    AgentBase,
    AgentOrchestrator,
    DataAgent,
    EvaluationAgent,
    ExecutionAgent,
    MarketAgent,
    MemoryAgent,
    ResearchAgent,
    RiskAgent,
    StrategyAgent,
)
from aqos.services import (
    BacktestService,
    BrokerService,
    EconomicCalendarService,
    ExperimentService,
    MarketDataService,
    NewsService,
    StorageService,
)


def create_market_data_service() -> MarketDataService:
    service = MarketDataService()

    candle_1 = service.create_candle(
        timestamp="2026-01-01",
        open_price=2000.0,
        high_price=2010.0,
        low_price=1990.0,
        close_price=2005.0,
        volume=1000.0,
    )
    candle_2 = service.create_candle(
        timestamp="2026-01-02",
        open_price=2010.0,
        high_price=2020.0,
        low_price=2005.0,
        close_price=2015.0,
        volume=1500.0,
    )

    service.register_feed(
        symbol="XAUUSD",
        timeframe="H1",
        candles=[
            candle_1,
            candle_2,
        ],
        source="local",
    )

    return service


def create_news_service() -> NewsService:
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold rises after weak dollar",
        source="local",
        published_at="2026-01-01T10:00:00",
        symbols=[
            "XAUUSD",
        ],
        sentiment="positive",
        impact_score=0.8,
    )

    return service


def create_calendar_service() -> EconomicCalendarService:
    service = EconomicCalendarService()

    service.add(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00",
        impact="high",
    )

    return service


def create_orchestrator() -> AgentOrchestrator:
    market_data_service = create_market_data_service()
    news_service = create_news_service()
    calendar_service = create_calendar_service()

    return AgentOrchestrator(
        data_agent=DataAgent(
            market_data_service=market_data_service,
        ),
        market_agent=MarketAgent(
            market_data_service=market_data_service,
            news_service=news_service,
            economic_calendar_service=calendar_service,
        ),
        research_agent=ResearchAgent(
            experiment_service=ExperimentService(),
            storage_service=StorageService(),
        ),
        strategy_agent=StrategyAgent(),
        risk_agent=RiskAgent(),
        execution_agent=ExecutionAgent(
            broker_service=BrokerService(),
        ),
        evaluation_agent=EvaluationAgent(
            backtest_service=BacktestService(),
        ),
        memory_agent=MemoryAgent(),
    )


def test_orchestrator_is_agent_base_instance():
    orchestrator = AgentOrchestrator()

    assert isinstance(orchestrator, AgentBase)


def test_orchestrator_name():
    orchestrator = AgentOrchestrator()

    assert orchestrator.name == "agent-orchestrator"


def test_orchestrator_description():
    orchestrator = AgentOrchestrator()

    assert orchestrator.description == (
        "Agent orchestrator for routing and multi-agent AQOS workflows."
    )


def test_available_actions():
    orchestrator = AgentOrchestrator()

    assert orchestrator.available_actions() == [
        "backtest-workflow",
        "health",
        "market-strategy-workflow",
        "memory-workflow",
        "research-workflow",
        "risk-execution-workflow",
        "route",
        "strategy-risk-workflow",
        "trade-workflow",
    ]


def test_health():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="health",
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Agent orchestrator is healthy."
    assert result.data["status"] == "ok"
    assert result.data["agents"] == [
        "data",
        "evaluation",
        "execution",
        "market",
        "memory",
        "research",
        "risk",
        "strategy",
    ]
    assert result.data["agent_health"]["data"]["success"] is True
    assert result.data["agent_health"]["market"]["success"] is True
    assert result.metadata["request_id"] == "req-1"


def test_route_to_data_agent():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="route",
        payload={
            "agent": "data",
            "agent_action": "availability",
            "agent_payload": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
            },
        },
    )

    assert result.success is True
    assert result.message == "Agent route completed."
    assert result.data["agent"] == "data"
    assert result.data["result"]["success"] is True
    assert result.data["result"]["data"]["available"] is True


def test_route_unknown_agent():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="route",
        payload={
            "agent": "unknown",
            "agent_action": "health",
        },
    )

    assert result.success is False
    assert result.message == "Unknown agent: unknown"


def test_route_missing_agent_action():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="route",
        payload={
            "agent": "data",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: agent_action"


def test_market_strategy_workflow():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="market-strategy-workflow",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Market strategy workflow completed."
    assert result.data["market_state"]["symbol"] == "XAUUSD"
    assert result.data["market_state"]["regime"] == "bullish"
    assert result.data["strategy_handoff"]["signal"] == "buy"
    assert result.data["strategy_handoff"]["should_enter"] is True
    assert result.metadata["request_id"] == "req-1"


def test_market_strategy_workflow_missing_market_data():
    orchestrator = AgentOrchestrator()

    result = orchestrator.execute(
        action="market-strategy-workflow",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Market strategy workflow failed."
    assert result.data["failed_step"] == "market-state"


def test_strategy_risk_workflow():
    orchestrator = create_orchestrator()

    strategy_result = orchestrator.execute(
        action="market-strategy-workflow",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    result = orchestrator.execute(
        action="strategy-risk-workflow",
        payload={
            "strategy_handoff": strategy_result.data["strategy_handoff"],
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert result.success is True
    assert result.message == "Strategy risk workflow completed."
    assert result.data["trade_request"]["side"] == "buy"
    assert result.data["risk_handoff"]["allowed"] is True
    assert result.data["risk_handoff"]["execution_ready"] is True


def test_strategy_risk_workflow_hold_signal():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="strategy-risk-workflow",
        payload={
            "strategy_handoff": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "signal": "hold",
                "should_enter": False,
                "should_exit": False,
                "entry_price": 2015.0,
                "stop_loss_price": None,
                "take_profit_price": None,
            }
        },
    )

    assert result.success is False
    assert result.message == "Strategy signal is hold; no risk workflow required."


def test_risk_execution_workflow():
    orchestrator = create_orchestrator()

    risk_handoff = {
        "symbol": "XAUUSD",
        "side": "buy",
        "allowed": True,
        "reason": "Trade allowed.",
        "position_size": 10.0,
        "entry_price": 2015.0,
        "stop_loss_price": 2005.0,
        "risk_amount": 100.0,
        "risk_percent": 0.01,
        "execution_ready": True,
    }

    result = orchestrator.execute(
        action="risk-execution-workflow",
        payload={
            "risk_handoff": risk_handoff,
        },
    )

    assert result.success is True
    assert result.message == "Risk execution workflow completed."
    assert result.data["execution"]["symbol"] == "XAUUSD"
    assert result.data["execution"]["side"] == "buy"
    assert result.data["execution"]["quantity"] == 10.0


def test_risk_execution_workflow_rejected_trade():
    orchestrator = create_orchestrator()

    risk_handoff = {
        "symbol": "XAUUSD",
        "side": "buy",
        "allowed": False,
        "reason": "Risk rejected.",
        "position_size": None,
        "entry_price": 2015.0,
        "stop_loss_price": 2005.0,
        "risk_amount": None,
        "risk_percent": 0.01,
        "execution_ready": False,
    }

    result = orchestrator.execute(
        action="risk-execution-workflow",
        payload={
            "risk_handoff": risk_handoff,
        },
    )

    assert result.success is False
    assert result.message == "Risk execution workflow failed."
    assert result.data["failed_step"] == "execute-trade"


def test_trade_workflow():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="trade-workflow",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "account_balance": 10_000.0,
            "risk_percent": 0.01,
        },
    )

    assert result.success is True
    assert result.message == "Trade workflow completed."
    assert result.data["market_state"]["symbol"] == "XAUUSD"
    assert result.data["strategy_handoff"]["signal"] == "buy"
    assert result.data["risk_handoff"]["allowed"] is True
    assert result.data["execution"]["status"] == "open"


def test_research_workflow():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="research-workflow",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "signal_source": "news sentiment",
            "objective": "reduce false entries",
            "experiment_name": "news-sentiment-test",
        },
    )

    assert result.success is True
    assert result.message == "Research workflow completed."
    assert result.data["hypothesis"]["symbol"] == "XAUUSD"
    assert result.data["experiment_plan"]["name"] == "news-sentiment-test"
    assert result.data["experiment_plan"]["metric"] == "win_rate"


def test_research_workflow_missing_signal_source():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="research-workflow",
        payload={
            "symbol": "XAUUSD",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: signal_source"


def test_backtest_workflow():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="backtest-workflow",
        payload={
            "name": "run-1",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert result.success is True
    assert result.message == "Backtest workflow completed."
    assert result.data["backtest"]["name"] == "run-1"
    assert result.data["backtest"]["total_profit"] == 75.0
    assert result.data["report"]["name"] == "run-1"
    assert result.data["report"]["metrics"]["total_trades"] == 3


def test_backtest_workflow_duplicate_name_fails():
    orchestrator = create_orchestrator()

    payload = {
        "name": "run-1",
        "profits": [
            100.0,
        ],
        "initial_balance": 10_000.0,
    }

    orchestrator.execute(
        action="backtest-workflow",
        payload=payload,
    )
    result = orchestrator.execute(
        action="backtest-workflow",
        payload=payload,
    )

    assert result.success is False
    assert result.message == "Backtest workflow failed."
    assert result.data["failed_step"] == "run-backtest"


def test_memory_workflow_without_recall():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="memory-workflow",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout after CPI.",
            "memory_type": "research",
            "importance": 0.8,
        },
    )

    assert result.success is True
    assert result.message == "Memory workflow completed."
    assert result.data["remember"]["memory_id"] == "memory-1"
    assert result.data["recall"] is None


def test_memory_workflow_with_recall():
    orchestrator = create_orchestrator()

    result = orchestrator.execute(
        action="memory-workflow",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout after CPI.",
            "memory_type": "research",
            "importance": 0.8,
            "query": "XAUUSD bullish",
        },
    )

    assert result.success is True
    assert result.message == "Memory workflow completed."
    assert result.data["remember"]["memory_id"] == "memory-1"
    assert result.data["recall"]["count"] == 1
    assert result.data["recall"]["results"][0]["record"]["memory_id"] == "memory-1"


def test_unsupported_action():
    orchestrator = AgentOrchestrator()

    result = orchestrator.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"