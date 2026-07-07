"""
Unit tests for DashboardInterface.
"""

from aqos.interfaces import DashboardInterface
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
        metadata={
            "provider": "test",
        },
    )

    return service


def create_backtest_service() -> BacktestService:
    service = BacktestService()

    service.run(
        name="run-1",
        profits=[
            100.0,
            -50.0,
            25.0,
        ],
        initial_balance=10_000.0,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    return service


def create_experiment_service() -> ExperimentService:
    service = ExperimentService()

    service.create(
        name="experiment-1",
        description="Baseline experiment",
        metadata={
            "symbol": "XAUUSD",
        },
    )
    service.add_result(
        name="experiment-1",
        key="total_profit",
        value=75.0,
    )
    service.complete("experiment-1")

    return service


def create_broker_service() -> BrokerService:
    service = BrokerService()

    service.place_order(
        order_id="order-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1.0,
    )
    service.fill_order(
        order_id="order-1",
        fill_price=2000.0,
    )
    service.close_position(
        position_id="position-order-1",
        exit_price=2010.0,
    )

    return service


def create_news_service() -> NewsService:
    service = NewsService()

    service.add(
        news_id="news-1",
        title="Gold rises",
        source="local",
        published_at="2026-01-01T10:00:00",
        symbols=[
            "XAUUSD",
        ],
        sentiment="positive",
        impact_score=0.8,
    )
    service.add(
        news_id="news-2",
        title="Euro weakens",
        source="local",
        published_at="2026-01-01T11:00:00",
        symbols=[
            "EURUSD",
        ],
        sentiment="negative",
        impact_score=0.4,
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
    service.add(
        event_id="event-2",
        title="EU CPI",
        country="Eurozone",
        currency="EUR",
        event_time="2026-01-01T10:00:00",
        impact="medium",
    )

    return service


def create_storage_service() -> StorageService:
    service = StorageService()

    service.save(
        key="run-1",
        value={
            "profit": 75.0,
        },
        namespace="experiments",
    )
    service.save(
        key="model-1",
        value={
            "accuracy": 0.8,
        },
        namespace="models",
    )

    return service


def create_dashboard() -> DashboardInterface:
    return DashboardInterface(
        market_data_service=create_market_data_service(),
        backtest_service=create_backtest_service(),
        experiment_service=create_experiment_service(),
        broker_service=create_broker_service(),
        news_service=create_news_service(),
        economic_calendar_service=create_calendar_service(),
        storage_service=create_storage_service(),
    )


def test_health():
    dashboard = DashboardInterface()

    response = dashboard.health()

    assert response.success is True
    assert response.message == "Dashboard interface is healthy."
    assert response.payload["status"] == "ok"


def test_overview():
    dashboard = create_dashboard()

    response = dashboard.overview()

    assert response.success is True
    assert response.message == "Dashboard overview retrieved."
    assert response.payload["market_data_feeds"] == 1
    assert response.payload["backtest_runs"] == 1
    assert response.payload["experiments"] == 1
    assert response.payload["orders"] == 1
    assert response.payload["positions"] == 1
    assert response.payload["news_items"] == 2
    assert response.payload["economic_events"] == 2
    assert response.payload["storage_records"] == 2


def test_market_data_summary():
    dashboard = create_dashboard()

    response = dashboard.market_data_summary(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert response.success is True
    assert response.message == "Market data summary retrieved."
    assert response.payload["symbol"] == "XAUUSD"
    assert response.payload["timeframe"] == "H1"
    assert response.payload["candles"] == 2
    assert response.payload["latest_timestamp"] == "2026-01-02"
    assert response.payload["latest_close"] == 2015.0
    assert response.payload["metadata"]["provider"] == "test"


def test_market_data_summary_missing_feed():
    dashboard = DashboardInterface()

    response = dashboard.market_data_summary(
        symbol="XAUUSD",
        timeframe="H1",
    )

    assert response.success is False
    assert response.message == "Market data feed does not exist."


def test_backtest_summary():
    dashboard = create_dashboard()

    response = dashboard.backtest_summary("run-1")

    assert response.success is True
    assert response.message == "Backtest summary retrieved."
    assert response.payload["name"] == "run-1"
    assert response.payload["total_profit"] == 75.0
    assert response.payload["final_balance"] == 10_075.0
    assert response.payload["total_trades"] == 3
    assert response.payload["metadata"]["symbol"] == "XAUUSD"


def test_backtest_summary_missing_run():
    dashboard = DashboardInterface()

    response = dashboard.backtest_summary("missing")

    assert response.success is False
    assert response.message == "Backtest run does not exist."


def test_experiment_summary():
    dashboard = create_dashboard()

    response = dashboard.experiment_summary("experiment-1")

    assert response.success is True
    assert response.message == "Experiment summary retrieved."
    assert response.payload["name"] == "experiment-1"
    assert response.payload["status"] == "completed"
    assert response.payload["results"]["total_profit"] == 75.0
    assert response.payload["metadata"]["symbol"] == "XAUUSD"


def test_experiment_summary_missing_experiment():
    dashboard = DashboardInterface()

    response = dashboard.experiment_summary("missing")

    assert response.success is False
    assert response.message == "Experiment does not exist."


def test_broker_summary():
    dashboard = create_dashboard()

    response = dashboard.broker_summary()

    assert response.success is True
    assert response.message == "Broker summary retrieved."
    assert response.payload["orders"] == 1
    assert response.payload["positions"] == 1
    assert response.payload["open_orders"] == 0
    assert response.payload["filled_orders"] == 1
    assert response.payload["closed_positions"] == 1
    assert response.payload["realized_profit"] == 10.0


def test_news_summary():
    dashboard = create_dashboard()

    response = dashboard.news_summary()

    assert response.success is True
    assert response.message == "News summary retrieved."
    assert response.payload["items"] == 2
    assert response.payload["high_impact_items"] == 1
    assert response.payload["average_impact_score"] == 0.6000000000000001


def test_news_summary_by_symbol():
    dashboard = create_dashboard()

    response = dashboard.news_summary("XAUUSD")

    assert response.success is True
    assert response.payload["symbol"] == "XAUUSD"
    assert response.payload["items"] == 1
    assert response.payload["high_impact_items"] == 1
    assert response.payload["average_impact_score"] == 0.8


def test_economic_calendar_summary():
    dashboard = create_dashboard()

    response = dashboard.economic_calendar_summary()

    assert response.success is True
    assert response.message == "Economic calendar summary retrieved."
    assert response.payload["events"] == 2
    assert response.payload["high_impact_events"] == 1


def test_economic_calendar_summary_by_currency():
    dashboard = create_dashboard()

    response = dashboard.economic_calendar_summary("usd")

    assert response.success is True
    assert response.payload["currency"] == "USD"
    assert response.payload["events"] == 1
    assert response.payload["high_impact_events"] == 1


def test_storage_summary():
    dashboard = create_dashboard()

    response = dashboard.storage_summary()

    assert response.success is True
    assert response.message == "Storage summary retrieved."
    assert response.payload["records"] == 2
    assert response.payload["namespaces"] == [
        "experiments",
        "models",
    ]