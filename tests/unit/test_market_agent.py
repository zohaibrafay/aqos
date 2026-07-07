"""
Unit tests for MarketAgent.
"""

from aqos.agents import (
    AgentBase,
    MarketAgent,
)
from aqos.services import (
    EconomicCalendarService,
    MarketDataService,
    NewsService,
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
    service.add(
        news_id="news-2",
        title="Gold consolidates",
        source="local",
        published_at="2026-01-01T11:00:00",
        symbols=[
            "XAUUSD",
        ],
        sentiment="neutral",
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
        title="FOMC Minutes",
        country="United States",
        currency="USD",
        event_time="2026-01-02T19:00:00",
        impact="medium",
    )

    return service


def create_market_agent() -> MarketAgent:
    return MarketAgent(
        market_data_service=create_market_data_service(),
        news_service=create_news_service(),
        economic_calendar_service=create_calendar_service(),
    )


def test_market_agent_is_agent_base_instance():
    agent = MarketAgent()

    assert isinstance(agent, AgentBase)


def test_market_agent_name():
    agent = MarketAgent()

    assert agent.name == "market-agent"


def test_market_agent_description():
    agent = MarketAgent()

    assert agent.description == (
        "Agent for market snapshots, trend, regime, news, and calendar context."
    )


def test_available_actions():
    agent = MarketAgent()

    assert agent.available_actions() == [
        "calendar-context",
        "health",
        "market-state",
        "news-context",
        "regime-summary",
        "snapshot",
        "trend-summary",
    ]


def test_health():
    agent = create_market_agent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Market agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["market_data_feeds"] == 1
    assert result.data["news_items"] == 2
    assert result.data["economic_events"] == 2


def test_snapshot():
    agent = create_market_agent()

    result = agent.execute(
        action="snapshot",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "Market snapshot retrieved."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["source"] == "local"
    assert result.data["candles"] == 2
    assert result.data["timestamp"] == "2026-01-02"
    assert result.data["close"] == 2015.0


def test_snapshot_missing_feed():
    agent = MarketAgent()

    result = agent.execute(
        action="snapshot",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Market data feed does not exist."


def test_snapshot_missing_symbol():
    agent = MarketAgent()

    result = agent.execute(
        action="snapshot",
        payload={
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: symbol"


def test_trend_summary():
    agent = create_market_agent()

    result = agent.execute(
        action="trend-summary",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "Trend summary generated."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["trend"] == "uptrend"
    assert result.data["first_close"] == 2005.0
    assert result.data["last_close"] == 2015.0
    assert result.data["change"] == 10.0
    assert result.data["prices"] == 2


def test_trend_summary_missing_feed():
    agent = MarketAgent()

    result = agent.execute(
        action="trend-summary",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Market data feed does not exist."


def test_regime_summary():
    agent = create_market_agent()

    result = agent.execute(
        action="regime-summary",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "Market regime summary generated."
    assert result.data["regime"] == "bullish"
    assert result.data["trend"] == "uptrend"
    assert result.data["change"] == 10.0


def test_news_context():
    agent = create_market_agent()

    result = agent.execute(
        action="news-context",
        payload={
            "symbol": "XAUUSD",
        },
    )

    assert result.success is True
    assert result.message == "News context generated."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["items"] == 2
    assert result.data["sentiment_counts"]["positive"] == 1
    assert result.data["sentiment_counts"]["neutral"] == 1
    assert result.data["sentiment_counts"]["negative"] == 0
    assert result.data["high_impact_items"] == 1
    assert result.data["average_impact_score"] == 0.6000000000000001


def test_news_context_missing_symbol():
    agent = MarketAgent()

    result = agent.execute(
        action="news-context",
        payload={},
    )

    assert result.success is False
    assert result.message == "Missing required payload key: symbol"


def test_calendar_context():
    agent = create_market_agent()

    result = agent.execute(
        action="calendar-context",
        payload={
            "currency": "usd",
        },
    )

    assert result.success is True
    assert result.message == "Economic calendar context generated."
    assert result.data["currency"] == "USD"
    assert result.data["events"] == 2
    assert result.data["high_impact_events"] == 1
    assert result.data["event_titles"] == [
        "US CPI",
        "FOMC Minutes",
    ]


def test_calendar_context_missing_currency():
    agent = MarketAgent()

    result = agent.execute(
        action="calendar-context",
        payload={},
    )

    assert result.success is False
    assert result.message == "Missing required payload key: currency"


def test_market_state():
    agent = create_market_agent()

    result = agent.execute(
        action="market-state",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Market state generated."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["timestamp"] == "2026-01-02"
    assert result.data["close"] == 2015.0
    assert result.data["trend"] == "uptrend"
    assert result.data["regime"] == "bullish"
    assert result.data["change"] == 10.0
    assert result.data["news_items"] == 2
    assert result.data["average_news_impact"] == 0.6000000000000001
    assert result.metadata["request_id"] == "req-1"


def test_market_state_missing_feed():
    agent = MarketAgent()

    result = agent.execute(
        action="market-state",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Market data feed does not exist."


def test_unsupported_action():
    agent = MarketAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"