"""
Integration test scaffold.

Validates that Sprint 014 shared integration fixtures are wired correctly.
"""

from aqos.agents import (
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
from aqos.common import (
    DEFAULT_ACCOUNT_BALANCE,
    DEFAULT_RISK_PERCENT,
    DEFAULT_SYMBOL,
    DEFAULT_TIMEFRAME,
)
from aqos.services import (
    BacktestService,
    BrokerService,
    DataService,
    EconomicCalendarService,
    ExperimentService,
    MarketDataService,
    ModelService,
    NewsService,
    StorageService,
    StrategyService,
)


def test_integration_default_values(
    integration_symbol: str,
    integration_timeframe: str,
    integration_account_balance: float,
    integration_risk_percent: float,
):
    assert integration_symbol == DEFAULT_SYMBOL
    assert integration_timeframe == DEFAULT_TIMEFRAME
    assert integration_account_balance == DEFAULT_ACCOUNT_BALANCE
    assert integration_risk_percent == DEFAULT_RISK_PERCENT


def test_sample_ohlcv_records(sample_ohlcv_records):
    assert len(sample_ohlcv_records) == 3
    assert sample_ohlcv_records[0]["timestamp"] == "2026-01-01T00:00:00Z"
    assert sample_ohlcv_records[-1]["close"] == 2025.0


def test_service_fixtures_are_available(
    data_service: DataService,
    model_service: ModelService,
    strategy_service: StrategyService,
    market_data_service: MarketDataService,
    news_service: NewsService,
    economic_calendar_service: EconomicCalendarService,
    experiment_service: ExperimentService,
    storage_service: StorageService,
    broker_service: BrokerService,
    backtest_service: BacktestService,
):
    assert isinstance(data_service, DataService)
    assert isinstance(model_service, ModelService)
    assert isinstance(strategy_service, StrategyService)
    assert isinstance(market_data_service, MarketDataService)
    assert isinstance(news_service, NewsService)
    assert isinstance(economic_calendar_service, EconomicCalendarService)
    assert isinstance(experiment_service, ExperimentService)
    assert isinstance(storage_service, StorageService)
    assert isinstance(broker_service, BrokerService)
    assert isinstance(backtest_service, BacktestService)


def test_market_data_service_fixture_is_populated(
    market_data_service: MarketDataService,
    integration_symbol: str,
    integration_timeframe: str,
):
    assert market_data_service.exists(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    ) is True
    assert market_data_service.count() == 1
    assert len(
        market_data_service.get_candles(
            symbol=integration_symbol,
            timeframe=integration_timeframe,
        )
    ) == 3
    assert market_data_service.close_prices(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    ) == [
        2005.0,
        2015.0,
        2025.0,
    ]


def test_news_service_fixture_is_populated(
    news_service: NewsService,
    integration_symbol: str,
):
    items = news_service.filter_by_symbol(integration_symbol)

    assert len(items) == 1
    assert items[0].news_id == "news-1"
    assert items[0].sentiment == "positive"


def test_economic_calendar_service_fixture_is_populated(
    economic_calendar_service: EconomicCalendarService,
):
    events = economic_calendar_service.filter_by_currency("USD")

    assert len(events) == 1
    assert events[0].event_id == "event-1"
    assert events[0].impact == "high"


def test_agent_fixtures_are_available(
    data_agent: DataAgent,
    market_agent: MarketAgent,
    research_agent: ResearchAgent,
    strategy_agent: StrategyAgent,
    risk_agent: RiskAgent,
    execution_agent: ExecutionAgent,
    evaluation_agent: EvaluationAgent,
    memory_agent: MemoryAgent,
    agent_orchestrator: AgentOrchestrator,
):
    assert isinstance(data_agent, DataAgent)
    assert isinstance(market_agent, MarketAgent)
    assert isinstance(research_agent, ResearchAgent)
    assert isinstance(strategy_agent, StrategyAgent)
    assert isinstance(risk_agent, RiskAgent)
    assert isinstance(execution_agent, ExecutionAgent)
    assert isinstance(evaluation_agent, EvaluationAgent)
    assert isinstance(memory_agent, MemoryAgent)
    assert isinstance(agent_orchestrator, AgentOrchestrator)


def test_agent_health_fixtures(
    data_agent: DataAgent,
    market_agent: MarketAgent,
    research_agent: ResearchAgent,
    strategy_agent: StrategyAgent,
    risk_agent: RiskAgent,
    execution_agent: ExecutionAgent,
    evaluation_agent: EvaluationAgent,
    memory_agent: MemoryAgent,
):
    agents = [
        data_agent,
        market_agent,
        research_agent,
        strategy_agent,
        risk_agent,
        execution_agent,
        evaluation_agent,
        memory_agent,
    ]

    for agent in agents:
        result = agent.execute("health")

        assert result.success is True
        assert "healthy" in result.message.lower()


def test_orchestrator_health_fixture(
    agent_orchestrator: AgentOrchestrator,
):
    result = agent_orchestrator.execute("health")

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


def test_orchestrator_can_route_to_data_agent(
    agent_orchestrator: AgentOrchestrator,
    integration_symbol: str,
    integration_timeframe: str,
):
    result = agent_orchestrator.execute(
        action="route",
        payload={
            "agent": "data",
            "agent_action": "availability",
            "agent_payload": {
                "symbol": integration_symbol,
                "timeframe": integration_timeframe,
            },
        },
    )

    assert result.success is True
    assert result.data["agent"] == "data"
    assert result.data["result"]["success"] is True
    assert result.data["result"]["data"]["available"] is True