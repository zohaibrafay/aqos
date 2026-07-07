"""
Shared integration test fixtures for AQOS.

These fixtures provide deterministic in-memory services and agents
for Sprint 014 system integration tests.
"""

from __future__ import annotations

import pytest

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


@pytest.fixture()
def integration_symbol() -> str:
    """
    Return default integration symbol.
    """

    return DEFAULT_SYMBOL


@pytest.fixture()
def integration_timeframe() -> str:
    """
    Return default integration timeframe.
    """

    return DEFAULT_TIMEFRAME


@pytest.fixture()
def integration_account_balance() -> float:
    """
    Return default integration account balance.
    """

    return DEFAULT_ACCOUNT_BALANCE


@pytest.fixture()
def integration_risk_percent() -> float:
    """
    Return default integration risk percent.
    """

    return DEFAULT_RISK_PERCENT


@pytest.fixture()
def sample_ohlcv_records() -> list[dict[str, float | str]]:
    """
    Return deterministic sample OHLCV records.
    """

    return [
        {
            "timestamp": "2026-01-01T00:00:00Z",
            "open": 2000.0,
            "high": 2010.0,
            "low": 1995.0,
            "close": 2005.0,
            "volume": 1000.0,
        },
        {
            "timestamp": "2026-01-01T01:00:00Z",
            "open": 2005.0,
            "high": 2020.0,
            "low": 2000.0,
            "close": 2015.0,
            "volume": 1200.0,
        },
        {
            "timestamp": "2026-01-01T02:00:00Z",
            "open": 2015.0,
            "high": 2030.0,
            "low": 2010.0,
            "close": 2025.0,
            "volume": 1500.0,
        },
    ]


@pytest.fixture()
def data_service() -> DataService:
    """
    Return DataService instance.
    """

    return DataService()


@pytest.fixture()
def model_service() -> ModelService:
    """
    Return ModelService instance.
    """

    return ModelService()


@pytest.fixture()
def strategy_service() -> StrategyService:
    """
    Return StrategyService instance.
    """

    return StrategyService()


@pytest.fixture()
def market_data_service(
    integration_symbol: str,
    integration_timeframe: str,
    sample_ohlcv_records: list[dict[str, float | str]],
) -> MarketDataService:
    """
    Return populated MarketDataService instance.
    """

    service = MarketDataService()

    candles = [
        service.create_candle(
            timestamp=str(record["timestamp"]),
            open_price=float(record["open"]),
            high_price=float(record["high"]),
            low_price=float(record["low"]),
            close_price=float(record["close"]),
            volume=float(record["volume"]),
        )
        for record in sample_ohlcv_records
    ]

    service.register_feed(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
        candles=candles,
        source="integration-test",
    )

    return service


@pytest.fixture()
def news_service(
    integration_symbol: str,
) -> NewsService:
    """
    Return populated NewsService instance.
    """

    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold rises after weaker dollar",
        source="integration-test",
        published_at="2026-01-01T03:00:00Z",
        symbols=[
            integration_symbol,
        ],
        sentiment="positive",
        impact_score=0.8,
    )

    return service


@pytest.fixture()
def economic_calendar_service() -> EconomicCalendarService:
    """
    Return populated EconomicCalendarService instance.
    """

    service = EconomicCalendarService()

    service.add(
        event_id="event-1",
        title="US CPI",
        country="United States",
        currency="USD",
        event_time="2026-01-01T13:30:00Z",
        impact="high",
    )

    return service


@pytest.fixture()
def experiment_service() -> ExperimentService:
    """
    Return ExperimentService instance.
    """

    return ExperimentService()


@pytest.fixture()
def storage_service() -> StorageService:
    """
    Return StorageService instance.
    """

    return StorageService()


@pytest.fixture()
def broker_service() -> BrokerService:
    """
    Return BrokerService instance.
    """

    return BrokerService()


@pytest.fixture()
def backtest_service() -> BacktestService:
    """
    Return BacktestService instance.
    """

    return BacktestService()


@pytest.fixture()
def data_agent(
    market_data_service: MarketDataService,
) -> DataAgent:
    """
    Return DataAgent instance.
    """

    return DataAgent(
        market_data_service=market_data_service,
    )


@pytest.fixture()
def market_agent(
    market_data_service: MarketDataService,
    news_service: NewsService,
    economic_calendar_service: EconomicCalendarService,
) -> MarketAgent:
    """
    Return MarketAgent instance.
    """

    return MarketAgent(
        market_data_service=market_data_service,
        news_service=news_service,
        economic_calendar_service=economic_calendar_service,
    )


@pytest.fixture()
def research_agent(
    experiment_service: ExperimentService,
    storage_service: StorageService,
) -> ResearchAgent:
    """
    Return ResearchAgent instance.
    """

    return ResearchAgent(
        experiment_service=experiment_service,
        storage_service=storage_service,
    )


@pytest.fixture()
def strategy_agent() -> StrategyAgent:
    """
    Return StrategyAgent instance.
    """

    return StrategyAgent()


@pytest.fixture()
def risk_agent() -> RiskAgent:
    """
    Return RiskAgent instance.
    """

    return RiskAgent()


@pytest.fixture()
def execution_agent(
    broker_service: BrokerService,
) -> ExecutionAgent:
    """
    Return ExecutionAgent instance.
    """

    return ExecutionAgent(
        broker_service=broker_service,
    )


@pytest.fixture()
def evaluation_agent(
    backtest_service: BacktestService,
) -> EvaluationAgent:
    """
    Return EvaluationAgent instance.
    """

    return EvaluationAgent(
        backtest_service=backtest_service,
    )


@pytest.fixture()
def memory_agent() -> MemoryAgent:
    """
    Return MemoryAgent instance.
    """

    return MemoryAgent()


@pytest.fixture()
def agent_orchestrator(
    data_agent: DataAgent,
    market_agent: MarketAgent,
    research_agent: ResearchAgent,
    strategy_agent: StrategyAgent,
    risk_agent: RiskAgent,
    execution_agent: ExecutionAgent,
    evaluation_agent: EvaluationAgent,
    memory_agent: MemoryAgent,
) -> AgentOrchestrator:
    """
    Return AgentOrchestrator instance wired with shared agents.
    """

    return AgentOrchestrator(
        data_agent=data_agent,
        market_agent=market_agent,
        research_agent=research_agent,
        strategy_agent=strategy_agent,
        risk_agent=risk_agent,
        execution_agent=execution_agent,
        evaluation_agent=evaluation_agent,
        memory_agent=memory_agent,
    )