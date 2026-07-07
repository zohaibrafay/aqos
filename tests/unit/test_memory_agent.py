"""
Unit tests for MemoryAgent.
"""

from aqos.agents import (
    AgentBase,
    MemoryAgent,
)


def create_memory_agent() -> MemoryAgent:
    return MemoryAgent()


def test_memory_agent_is_agent_base_instance():
    agent = MemoryAgent()

    assert isinstance(agent, AgentBase)


def test_memory_agent_name():
    agent = MemoryAgent()

    assert agent.name == "memory-agent"


def test_memory_agent_description():
    agent = MemoryAgent()

    assert agent.description == (
        "Agent for storing, recalling, forgetting, and summarizing AQOS memories."
    )


def test_available_actions():
    agent = MemoryAgent()

    assert agent.available_actions() == [
        "forget",
        "get-memory",
        "health",
        "memory-summary",
        "pattern-memory",
        "recall",
        "remember",
        "trade-memory",
    ]


def test_health():
    agent = create_memory_agent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Memory agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["records"] == 0


def test_remember():
    agent = create_memory_agent()

    result = agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout after CPI.",
            "memory_type": "research",
            "importance": 0.8,
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Memory stored."
    assert result.data["memory_id"] == "memory-1"
    assert result.data["content"] == "XAUUSD bullish breakout after CPI."
    assert result.data["memory_type"] == "research"
    assert result.data["importance"] == 0.8
    assert result.data["metadata"]["symbol"] == "XAUUSD"
    assert result.data["metadata"]["request_id"] == "req-1"
    assert result.metadata["request_id"] == "req-1"


def test_remember_defaults_type_and_importance():
    agent = create_memory_agent()

    result = agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "General observation.",
        },
    )

    assert result.success is True
    assert result.data["memory_type"] == "observation"
    assert result.data["importance"] == 0.5


def test_remember_rejects_missing_memory_id():
    agent = create_memory_agent()

    result = agent.execute(
        action="remember",
        payload={
            "content": "Missing memory id.",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: memory_id"


def test_remember_rejects_empty_content():
    agent = create_memory_agent()

    result = agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "",
        },
    )

    assert result.success is False
    assert result.message == "Memory content cannot be empty."


def test_remember_rejects_invalid_memory_type():
    agent = create_memory_agent()

    result = agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "Invalid type.",
            "memory_type": "invalid",
        },
    )

    assert result.success is False
    assert result.message == (
        "Memory type must be observation, pattern, trade, research, "
        "strategy, risk, execution, or evaluation."
    )


def test_remember_rejects_invalid_importance():
    agent = create_memory_agent()

    result = agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "Invalid importance.",
            "importance": 1.1,
        },
    )

    assert result.success is False
    assert result.message == "Importance must be between 0.0 and 1.0."


def test_get_memory():
    agent = create_memory_agent()

    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout after CPI.",
        },
    )

    result = agent.execute(
        action="get-memory",
        payload={
            "memory_id": "memory-1",
        },
    )

    assert result.success is True
    assert result.message == "Memory record retrieved."
    assert result.data["memory_id"] == "memory-1"


def test_get_missing_memory():
    agent = create_memory_agent()

    result = agent.execute(
        action="get-memory",
        payload={
            "memory_id": "missing",
        },
    )

    assert result.success is False
    assert result.message == "Memory record does not exist."


def test_recall():
    agent = create_memory_agent()

    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout after CPI.",
            "memory_type": "research",
            "importance": 0.9,
        },
    )
    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-2",
            "content": "EURUSD bearish continuation.",
            "memory_type": "research",
            "importance": 0.4,
        },
    )

    result = agent.execute(
        action="recall",
        payload={
            "query": "XAUUSD bullish",
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Memory recall completed."
    assert result.data["query"] == "XAUUSD bullish"
    assert result.data["count"] == 1
    assert result.data["results"][0]["record"]["memory_id"] == "memory-1"
    assert result.data["results"][0]["score"] == 1.0
    assert result.metadata["request_id"] == "req-1"


def test_recall_with_limit():
    agent = create_memory_agent()

    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout.",
        },
    )
    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-2",
            "content": "XAUUSD bullish continuation.",
        },
    )

    result = agent.execute(
        action="recall",
        payload={
            "query": "XAUUSD",
            "limit": 1,
        },
    )

    assert result.success is True
    assert result.data["count"] == 1


def test_recall_by_memory_type():
    agent = create_memory_agent()

    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "XAUUSD bullish breakout.",
            "memory_type": "research",
        },
    )
    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-2",
            "content": "XAUUSD trade closed in profit.",
            "memory_type": "trade",
        },
    )

    result = agent.execute(
        action="recall",
        payload={
            "query": "XAUUSD",
            "memory_type": "trade",
        },
    )

    assert result.success is True
    assert result.data["count"] == 1
    assert result.data["results"][0]["record"]["memory_id"] == "memory-2"


def test_recall_rejects_empty_query():
    agent = create_memory_agent()

    result = agent.execute(
        action="recall",
        payload={
            "query": "",
        },
    )

    assert result.success is False
    assert result.message == "Memory query cannot be empty."


def test_recall_rejects_invalid_limit():
    agent = create_memory_agent()

    result = agent.execute(
        action="recall",
        payload={
            "query": "XAUUSD",
            "limit": 0,
        },
    )

    assert result.success is False
    assert result.message == "Limit must be greater than zero."


def test_forget_existing_memory():
    agent = create_memory_agent()

    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "Forget this memory.",
        },
    )

    result = agent.execute(
        action="forget",
        payload={
            "memory_id": "memory-1",
        },
    )

    assert result.success is True
    assert result.message == "Memory forget completed."
    assert result.data["memory_id"] == "memory-1"
    assert result.data["removed"] is True


def test_forget_missing_memory():
    agent = create_memory_agent()

    result = agent.execute(
        action="forget",
        payload={
            "memory_id": "missing",
        },
    )

    assert result.success is True
    assert result.data["removed"] is False


def test_memory_summary():
    agent = create_memory_agent()

    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-1",
            "content": "Research finding.",
            "memory_type": "research",
            "importance": 0.8,
        },
    )
    agent.execute(
        action="remember",
        payload={
            "memory_id": "memory-2",
            "content": "Trade result.",
            "memory_type": "trade",
            "importance": 0.4,
        },
    )

    result = agent.execute(
        action="memory-summary",
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Memory summary generated."
    assert result.data["records"] == 2
    assert result.data["counts_by_type"]["research"] == 1
    assert result.data["counts_by_type"]["trade"] == 1
    assert result.data["high_importance_records"] == 1
    assert result.data["memory_ids"] == [
        "memory-1",
        "memory-2",
    ]
    assert result.metadata["request_id"] == "req-1"


def test_pattern_memory():
    agent = create_memory_agent()

    result = agent.execute(
        action="pattern-memory",
        payload={
            "memory_id": "pattern-1",
            "pattern": "bullish breakout",
            "importance": 0.7,
            "metadata": {
                "symbol": "XAUUSD",
            },
        },
    )

    assert result.success is True
    assert result.message == "Memory stored."
    assert result.data["memory_id"] == "pattern-1"
    assert result.data["memory_type"] == "pattern"
    assert result.data["content"] == "Pattern observed: bullish breakout"
    assert result.data["importance"] == 0.7
    assert result.data["metadata"]["symbol"] == "XAUUSD"


def test_pattern_memory_missing_pattern():
    agent = create_memory_agent()

    result = agent.execute(
        action="pattern-memory",
        payload={
            "memory_id": "pattern-1",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: pattern"


def test_trade_memory():
    agent = create_memory_agent()

    result = agent.execute(
        action="trade-memory",
        payload={
            "memory_id": "trade-1",
            "symbol": "XAUUSD",
            "side": "buy",
            "outcome": "profit",
            "importance": 0.9,
        },
    )

    assert result.success is True
    assert result.message == "Memory stored."
    assert result.data["memory_id"] == "trade-1"
    assert result.data["memory_type"] == "trade"
    assert result.data["content"] == "Trade memory: XAUUSD buy outcome profit."
    assert result.data["importance"] == 0.9


def test_trade_memory_missing_symbol():
    agent = create_memory_agent()

    result = agent.execute(
        action="trade-memory",
        payload={
            "memory_id": "trade-1",
            "side": "buy",
            "outcome": "profit",
        },
    )

    assert result.success is False
    assert result.message == "Missing required payload key: symbol"


def test_unsupported_action():
    agent = MemoryAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"