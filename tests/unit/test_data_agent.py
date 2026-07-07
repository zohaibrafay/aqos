"""
Unit tests for DataAgent.
"""

from aqos.agents import (
    AgentBase,
    DataAgent,
)
from aqos.services import MarketDataService


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


def test_data_agent_is_agent_base_instance():
    agent = DataAgent()

    assert isinstance(agent, AgentBase)


def test_data_agent_name():
    agent = DataAgent()

    assert agent.name == "data-agent"


def test_data_agent_description():
    agent = DataAgent()

    assert agent.description == (
        "Agent for market data availability, preparation, and quality checks."
    )


def test_available_actions():
    agent = DataAgent()

    assert agent.available_actions() == [
        "availability",
        "close-prices",
        "health",
        "latest-candle",
        "prepare-ohlcv",
        "quality-check",
        "summary",
    ]


def test_health():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Data agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["feeds"] == 1


def test_availability_true():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="availability",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "Data availability checked."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["available"] is True


def test_availability_false():
    agent = DataAgent()

    result = agent.execute(
        action="availability",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.data["available"] is False


def test_availability_missing_symbol():
    agent = DataAgent()

    result = agent.execute(
        action="availability",
        payload={
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: symbol"


def test_summary():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="summary",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Data summary retrieved."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["source"] == "local"
    assert result.data["candles"] == 2
    assert result.data["latest_timestamp"] == "2026-01-02"
    assert result.data["latest_close"] == 2015.0
    assert result.data["metadata"]["provider"] == "test"
    assert result.metadata["request_id"] == "req-1"


def test_summary_missing_feed():
    agent = DataAgent()

    result = agent.execute(
        action="summary",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Market data feed does not exist."


def test_latest_candle():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="latest-candle",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "Latest candle retrieved."
    assert result.data["timestamp"] == "2026-01-02"
    assert result.data["open"] == 2010.0
    assert result.data["high"] == 2020.0
    assert result.data["low"] == 2005.0
    assert result.data["close"] == 2015.0
    assert result.data["volume"] == 1500.0


def test_latest_candle_missing_feed():
    agent = DataAgent()

    result = agent.execute(
        action="latest-candle",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Market data feed does not exist."


def test_close_prices():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="close-prices",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "Close prices retrieved."
    assert result.data["close_prices"] == [
        2005.0,
        2015.0,
    ]
    assert result.data["count"] == 2


def test_close_prices_with_limit():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="close-prices",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "limit": 1,
        },
    )

    assert result.success is True
    assert result.data["close_prices"] == [
        2015.0,
    ]
    assert result.data["count"] == 1


def test_close_prices_invalid_limit():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="close-prices",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "limit": 0,
        },
    )

    assert result.success is False
    assert result.message == "Limit must be greater than zero."


def test_prepare_ohlcv():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="prepare-ohlcv",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "OHLCV data prepared."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["rows"] == 2
    assert result.data["columns"] == [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]
    assert len(result.data["records"]) == 2


def test_prepare_ohlcv_with_limit():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="prepare-ohlcv",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
            "limit": 1,
        },
    )

    assert result.success is True
    assert result.data["rows"] == 1
    assert result.data["records"][0]["timestamp"] == "2026-01-02"


def test_quality_check():
    agent = DataAgent(
        market_data_service=create_market_data_service(),
    )

    result = agent.execute(
        action="quality-check",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is True
    assert result.message == "Data quality check completed."
    assert result.data["valid"] is True
    assert result.data["rows"] == 2
    assert result.data["missing_columns"] == []
    assert result.data["missing_values"] == 0
    assert result.data["duplicate_timestamps"] == 0
    assert result.data["invalid_price_rows"] == 0
    assert result.data["invalid_volume_rows"] == 0
    assert result.data["issues"] == []


def test_quality_check_missing_feed():
    agent = DataAgent()

    result = agent.execute(
        action="quality-check",
        payload={
            "symbol": "XAUUSD",
            "timeframe": "H1",
        },
    )

    assert result.success is False
    assert result.message == "Market data feed does not exist."


def test_unsupported_action():
    agent = DataAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"