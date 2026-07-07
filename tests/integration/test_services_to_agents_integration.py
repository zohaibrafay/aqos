"""
Services → Agents integration tests.

Validates that agents correctly use shared AQOS service instances.
"""

from aqos.agents import (
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


def test_market_data_service_is_visible_through_data_agent(
    market_data_service: MarketDataService,
    data_agent: DataAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    assert market_data_service.exists(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    ) is True

    result = data_agent.execute(
        action="availability",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert result.success is True
    assert result.data["symbol"] == integration_symbol
    assert result.data["timeframe"] == integration_timeframe
    assert result.data["available"] is True


def test_market_data_service_close_prices_are_visible_through_data_agent(
    market_data_service: MarketDataService,
    data_agent: DataAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    service_prices = market_data_service.close_prices(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    )

    result = data_agent.execute(
        action="close-prices",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert result.success is True

    agent_prices = result.data.get("close_prices", result.data.get("prices"))

    assert agent_prices == service_prices
    assert agent_prices == [
        2005.0,
        2015.0,
        2025.0,
    ]


def test_market_data_service_latest_candle_is_visible_through_data_agent(
    market_data_service: MarketDataService,
    data_agent: DataAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    latest_candle = market_data_service.latest_candle(
        symbol=integration_symbol,
        timeframe=integration_timeframe,
    )

    result = data_agent.execute(
        action="latest-candle",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert result.success is True

    candle = result.data.get("candle", result.data)

    assert candle["close"] == latest_candle.close
    assert candle["volume"] == latest_candle.volume


def test_market_services_are_visible_through_market_agent(
    market_agent: MarketAgent,
    integration_symbol: str,
    integration_timeframe: str,
):
    market_state_result = market_agent.execute(
        action="market-state",
        payload={
            "symbol": integration_symbol,
            "timeframe": integration_timeframe,
        },
    )

    assert market_state_result.success is True
    assert market_state_result.data["symbol"] == integration_symbol
    assert market_state_result.data["timeframe"] == integration_timeframe
    assert market_state_result.data["close"] == 2025.0
    assert market_state_result.data["trend"] == "uptrend"
    assert market_state_result.data["regime"] == "bullish"


def test_news_service_is_visible_through_market_agent(
    news_service: NewsService,
    market_agent: MarketAgent,
    integration_symbol: str,
):
    service_items = news_service.filter_by_symbol(integration_symbol)

    result = market_agent.execute(
        action="news-context",
        payload={
            "symbol": integration_symbol,
        },
    )

    assert result.success is True
    assert len(service_items) == 1
    assert result.data["symbol"] == integration_symbol
    assert result.data["items"] == len(service_items)


def test_economic_calendar_service_is_visible_through_market_agent(
    economic_calendar_service: EconomicCalendarService,
    market_agent: MarketAgent,
):
    service_events = economic_calendar_service.filter_by_currency("USD")

    result = market_agent.execute(
        action="calendar-context",
        payload={
            "currency": "USD",
        },
    )

    assert result.success is True
    assert len(service_events) == 1
    assert result.data["currency"] == "USD"
    assert result.data["events"] == len(service_events)


def test_experiment_service_is_visible_through_research_agent(
    experiment_service: ExperimentService,
    research_agent: ResearchAgent,
):
    result = research_agent.execute(
        action="create-experiment",
        payload={
            "name": "integration-experiment",
            "description": "Integration experiment created through ResearchAgent.",
            "metadata": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
            },
        },
    )

    assert result.success is True
    assert experiment_service.get("integration-experiment") is not None
    assert experiment_service.get("integration-experiment").name == (
        "integration-experiment"
    )


def test_storage_service_is_visible_through_research_agent(
    storage_service: StorageService,
    research_agent: ResearchAgent,
):
    result = research_agent.execute(
        action="record-finding",
        payload={
            "finding_id": "finding-1",
            "title": "Bullish news finding",
            "finding": "Bullish news improves signal quality.",
            "conclusion": "Bullish news context can improve signal quality.",
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
    )

    assert result.success is True

    stored_record = storage_service.get(
        key="finding-1",
        namespace="research",
    )

    assert stored_record is not None
    assert stored_record.value["finding_id"] == "finding-1"
    assert stored_record.value["title"] == "Bullish news finding"
    assert stored_record.value["conclusion"] == ("Bullish news context can improve signal quality.")


def test_strategy_agent_uses_strategy_service_for_decision(
    strategy_agent: StrategyAgent,
):
    result = strategy_agent.execute(
        action="handoff",
        payload={
            "market_state": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2025.0,
            },
        },
    )

    assert result.success is True
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["signal"] == "buy"
    assert result.data["should_enter"] is True
    assert result.data["entry_price"] == 2025.0


def test_risk_agent_generates_execution_ready_handoff(
    risk_agent: RiskAgent,
):
    result = risk_agent.execute(
        action="risk-handoff",
        payload={
            "trade_request": {
                "symbol": "XAUUSD",
                "side": "buy",
                "account_balance": 10_000.0,
                "risk_percent": 0.01,
                "entry_price": 2025.0,
                "stop_loss_price": 2015.0,
            },
        },
    )

    assert result.success is True
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["side"] == "buy"
    assert result.data["allowed"] is True
    assert result.data["execution_ready"] is True
    assert result.data["position_size"] == 10.0


def test_broker_service_is_visible_through_execution_agent(
    broker_service: BrokerService,
    execution_agent: ExecutionAgent,
):
    result = execution_agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 10.0,
            "order_type": "market",
            "price": 2025.0,
        },
    )

    assert result.success is True

    stored_order = broker_service.get_order("order-1")

    assert stored_order is not None
    assert stored_order.symbol == "XAUUSD"
    assert stored_order.side == "buy"
    assert stored_order.quantity == 10.0


def test_broker_service_position_is_created_through_execution_agent_fill(
    broker_service: BrokerService,
    execution_agent: ExecutionAgent,
):
    order_result = execution_agent.execute(
        action="place-order",
        payload={
            "order_id": "order-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "quantity": 10.0,
            "order_type": "market",
            "price": 2025.0,
        },
    )

    assert order_result.success is True

    fill_result = execution_agent.execute(
        action="fill-order",
        payload={
            "order_id": "order-1",
            "fill_price": 2025.0,
        },
    )

    assert fill_result.success is True

    position_id = fill_result.data["position_id"]
    stored_position = broker_service.get_position(position_id)

    assert stored_position is not None
    assert stored_position.symbol == "XAUUSD"
    assert stored_position.side == "buy"
    assert stored_position.status == "open"


def test_backtest_service_is_visible_through_evaluation_agent(
    backtest_service: BacktestService,
    evaluation_agent: EvaluationAgent,
):
    result = evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "integration-backtest",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert result.success is True

    stored_run = backtest_service.get("integration-backtest")

    assert stored_run is not None
    assert stored_run.name == "integration-backtest"
    assert stored_run.result.total_profit == 75.0


def test_evaluation_agent_reads_backtest_service_state(
    evaluation_agent: EvaluationAgent,
):
    evaluation_agent.execute(
        action="run-backtest",
        payload={
            "name": "integration-backtest",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    result = evaluation_agent.execute(
        action="backtest-summary",
        payload={
            "name": "integration-backtest",
        },
    )

    assert result.success is True
    assert result.data["name"] == "integration-backtest"
    assert result.data["total_profit"] == 75.0
    assert result.data["total_trades"] == 3


def test_memory_agent_service_style_state_is_available_after_write(
    memory_agent: MemoryAgent,
):
    remember_result = memory_agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish continuation after news context.",
            "memory_type": "research",
            "importance": 0.8,
        },
    )

    recall_result = memory_agent.execute(
        action="recall",
        payload={
            "query": "XAUUSD bullish",
        },
    )

    assert remember_result.success is True
    assert recall_result.success is True
    assert recall_result.data["count"] == 1
    assert recall_result.data["results"][0]["record"]["memory_id"] == "memory-1"