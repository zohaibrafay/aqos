"""
Unit tests for services package exports.
"""

from aqos.services import (
    BacktestRun,
    BacktestService,
    BrokerOrder,
    BrokerPosition,
    BrokerService,
    DataService,
    DatasetSnapshot,
    EconomicCalendarEvent,
    EconomicCalendarService,
    ExperimentRun,
    ExperimentService,
    MarketCandle,
    MarketDataFeed,
    MarketDataService,
    ModelService,
    ModelSnapshot,
    NewsItem,
    NewsService,
    PredictionSnapshot,
    StorageRecord,
    StorageService,
    StrategyDecision,
    StrategyService,
)


def test_services_exports():
    assert BacktestRun is not None
    assert BacktestService is not None
    assert BrokerOrder is not None
    assert BrokerPosition is not None
    assert BrokerService is not None
    assert DataService is not None
    assert DatasetSnapshot is not None
    assert EconomicCalendarEvent is not None
    assert EconomicCalendarService is not None
    assert ExperimentRun is not None
    assert ExperimentService is not None
    assert MarketCandle is not None
    assert MarketDataFeed is not None
    assert MarketDataService is not None
    assert ModelService is not None
    assert ModelSnapshot is not None
    assert NewsItem is not None
    assert NewsService is not None
    assert PredictionSnapshot is not None
    assert StorageRecord is not None
    assert StorageService is not None
    assert StrategyDecision is not None
    assert StrategyService is not None


def test_service_instances_can_be_created():
    assert isinstance(BacktestService(), BacktestService)
    assert isinstance(BrokerService(), BrokerService)
    assert isinstance(DataService(), DataService)
    assert isinstance(EconomicCalendarService(), EconomicCalendarService)
    assert isinstance(ExperimentService(), ExperimentService)
    assert isinstance(MarketDataService(), MarketDataService)
    assert isinstance(ModelService(), ModelService)
    assert isinstance(NewsService(), NewsService)
    assert isinstance(StorageService(), StorageService)
    assert isinstance(StrategyService(), StrategyService)