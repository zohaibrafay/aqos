"""
Unit tests for AgentInterface.
"""

from typing import Any

from aqos.interfaces import (
    APIInterface,
    AgentInterface,
    DashboardInterface,
    MemoryInterface,
    MemoryInterfaceRecord,
    MemoryInterfaceSearchResult,
    RiskInterface,
)
from aqos.services import MarketDataService


class DummyMemory(MemoryInterface):

    def __init__(self) -> None:
        self._records: dict[str, MemoryInterfaceRecord] = {}

    @property
    def name(self) -> str:
        return "dummy-memory"

    def store(
        self,
        memory_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryInterfaceRecord:
        self.validate_memory_id(memory_id)
        self.validate_content(content)

        record = MemoryInterfaceRecord(
            memory_id=memory_id,
            content=content,
            metadata=metadata or {},
        )

        self._records[memory_id] = record

        return record

    def get(
        self,
        memory_id: str,
    ) -> MemoryInterfaceRecord | None:
        self.validate_memory_id(memory_id)

        return self._records.get(memory_id)

    def search(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[MemoryInterfaceSearchResult]:
        self.validate_query(query)

        if limit is not None:
            self.validate_limit(limit)

        results = []

        for record in self._records.values():
            if query.lower() in record.content.lower():
                results.append(
                    MemoryInterfaceSearchResult(
                        record=record,
                        score=1.0,
                    )
                )

        if limit is not None:
            results = results[:limit]

        return results

    def remove(
        self,
        memory_id: str,
    ) -> None:
        self.validate_memory_id(memory_id)

        self._records.pop(memory_id, None)


class DummyRiskManager(RiskInterface):

    @property
    def name(self) -> str:
        return "dummy-risk-manager"

    def validate_trade(
        self,
        trade_request: dict[str, Any],
    ) -> bool:
        return trade_request["side"] in {"buy", "sell"}

    def rejection_reason(
        self,
        trade_request: dict[str, Any],
    ) -> str:
        return "Trade rejected."

    def calculate_position_size(
        self,
        account_balance: float,
        risk_percent: float,
        entry_price: float,
        stop_loss_price: float,
    ) -> float:
        return 10.0


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
    )

    return service


def create_agent() -> AgentInterface:
    market_data_service = create_market_data_service()

    api = APIInterface(
        market_data_service=market_data_service,
        risk_manager=DummyRiskManager(),
    )

    dashboard = DashboardInterface(
        market_data_service=market_data_service,
    )

    memory = DummyMemory()

    return AgentInterface(
        api_interface=api,
        dashboard_interface=dashboard,
        memory_interface=memory,
    )


def test_available_actions():
    agent = AgentInterface()

    assert agent.available_actions() == [
        "backtest",
        "dashboard-overview",
        "health",
        "market-summary",
        "recall",
        "remember",
        "risk-assessment",
        "strategy-decision",
    ]


def test_health():
    agent = AgentInterface()

    response = agent.health()

    assert response.success is True
    assert response.message == "Agent interface is healthy."
    assert response.payload["status"] == "ok"


def test_run_action_health():
    agent = AgentInterface()

    response = agent.run_action("health")

    assert response.success is True
    assert response.message == "Agent interface is healthy."


def test_run_action_normalizes_action():
    agent = AgentInterface()

    response = agent.run_action("DASHBOARD_OVERVIEW")

    assert response.success is True
    assert response.message == "Dashboard overview retrieved."


def test_run_action_unsupported_action():
    agent = AgentInterface()

    response = agent.run_action("unknown")

    assert response.success is False
    assert response.message == "Unsupported agent action: unknown"


def test_run_action_empty_action():
    agent = AgentInterface()

    response = agent.run_action("")

    assert response.success is False
    assert response.message == "Agent action cannot be empty."


def test_run_action_non_string_action():
    agent = AgentInterface()

    response = agent.run_action(123)

    assert response.success is False
    assert response.message == "Agent action must be a string."


def test_dashboard_overview():
    agent = create_agent()

    response = agent.dashboard_overview()

    assert response.success is True
    assert response.message == "Dashboard overview retrieved."
    assert response.payload["market_data_feeds"] == 1


def test_market_summary():
    agent = create_agent()

    response = agent.market_summary(
        {
            "symbol": "XAUUSD",
            "timeframe": "H1",
        }
    )

    assert response.success is True
    assert response.message == "Market data summary retrieved."
    assert response.payload["symbol"] == "XAUUSD"
    assert response.payload["timeframe"] == "H1"
    assert response.payload["latest_close"] == 2015.0


def test_market_summary_missing_symbol():
    agent = create_agent()

    response = agent.run_action(
        action="market-summary",
        payload={
            "timeframe": "H1",
        },
    )

    assert response.success is False
    assert response.message == "Missing required payload key: symbol"


def test_strategy_decision():
    agent = create_agent()

    response = agent.strategy_decision(
        {
            "market_state": {
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2000.0,
            },
            "metadata": {
                "symbol": "XAUUSD",
            },
        }
    )

    assert response.success is True
    assert response.message == "Strategy decision generated."
    assert response.payload["signal"] == "buy"
    assert response.payload["should_enter"] is True
    assert response.metadata["symbol"] == "XAUUSD"


def test_strategy_decision_missing_market_state():
    agent = create_agent()

    response = agent.run_action(
        action="strategy-decision",
        payload={},
    )

    assert response.success is False
    assert response.message == "Missing required payload key: market_state"


def test_risk_assessment():
    agent = create_agent()

    response = agent.risk_assessment(
        {
            "trade_request": {
                "symbol": "XAUUSD",
                "side": "buy",
                "account_balance": 10_000.0,
                "risk_percent": 0.01,
                "entry_price": 2000.0,
                "stop_loss_price": 1990.0,
            }
        }
    )

    assert response.success is True
    assert response.message == "Risk assessment completed."
    assert response.payload["allowed"] is True
    assert response.payload["position_size"] == 10.0


def test_risk_assessment_missing_trade_request():
    agent = create_agent()

    response = agent.run_action(
        action="risk-assessment",
        payload={},
    )

    assert response.success is False
    assert response.message == "Missing required payload key: trade_request"


def test_backtest():
    agent = create_agent()

    response = agent.backtest(
        {
            "name": "run-1",
            "profits": [
                100.0,
                -50.0,
                25.0,
            ],
            "initial_balance": 10_000.0,
        }
    )

    assert response.success is True
    assert response.message == "Backtest completed."
    assert response.payload["name"] == "run-1"
    assert response.payload["total_profit"] == 75.0


def test_backtest_missing_name():
    agent = create_agent()

    response = agent.run_action(
        action="backtest",
        payload={
            "profits": [
                100.0,
            ],
            "initial_balance": 10_000.0,
        },
    )

    assert response.success is False
    assert response.message == "Missing required payload key: name"


def test_remember_without_memory_interface():
    agent = AgentInterface()

    response = agent.remember(
        {
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout",
        }
    )

    assert response.success is False
    assert response.message == "Memory interface is not configured."


def test_remember():
    agent = create_agent()

    response = agent.remember(
        {
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout",
            "metadata": {
                "symbol": "XAUUSD",
            },
        }
    )

    assert response.success is True
    assert response.message == "Memory stored."
    assert response.payload["memory_id"] == "memory-1"
    assert response.payload["content"] == "XAUUSD bullish breakout"
    assert response.metadata["symbol"] == "XAUUSD"


def test_recall_without_memory_interface():
    agent = AgentInterface()

    response = agent.recall(
        {
            "query": "bullish",
        }
    )

    assert response.success is False
    assert response.message == "Memory interface is not configured."


def test_recall():
    agent = create_agent()

    agent.remember(
        {
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout",
        }
    )

    response = agent.recall(
        {
            "query": "bullish",
        }
    )

    assert response.success is True
    assert response.message == "Memory recall completed."
    assert response.payload["query"] == "bullish"
    assert len(response.payload["results"]) == 1
    assert response.payload["results"][0]["record"]["memory_id"] == "memory-1"


def test_recall_with_limit():
    agent = create_agent()

    agent.remember(
        {
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout",
        }
    )
    agent.remember(
        {
            "memory_id": "memory-2",
            "content": "EURUSD bullish continuation",
        }
    )

    response = agent.recall(
        {
            "query": "bullish",
            "limit": 1,
        }
    )

    assert response.success is True
    assert len(response.payload["results"]) == 1


def test_recall_missing_query():
    agent = create_agent()

    response = agent.run_action(
        action="recall",
        payload={},
    )

    assert response.success is False
    assert response.message == "Missing required payload key: query"