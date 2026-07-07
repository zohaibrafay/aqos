"""
Unit tests for AQOS API memory operations.
"""

from types import SimpleNamespace

import pytest

from aqos.api import (
    MemoryIdRequest,
    PatternMemoryRequest,
    RecallMemoryRequest,
    RememberMemoryRequest,
    TradeMemoryRequest,
    api_forget,
    api_get_memory,
    api_memory_summary,
    api_pattern_memory,
    api_recall,
    api_remember,
    api_trade_memory,
    memory_agent_operation,
    normalize_pattern_memory_request,
    normalize_recall_request,
    normalize_remember_request,
    normalize_trade_memory_request,
)


class SuccessfulMemoryAgent:
    name = "memory-agent"

    def __init__(self):
        self.calls = []

    def execute(self, action, payload=None, metadata=None):
        payload = payload or {}

        self.calls.append(
            {
                "action": action,
                "payload": payload,
                "metadata": metadata,
            }
        )

        memory_record = {
            "memory_id": payload.get("memory_id", "memory-1"),
            "content": payload.get("content", "Memory content."),
            "memory_type": payload.get("memory_type", "observation"),
            "importance": payload.get("importance", 0.5),
            "metadata": payload.get("metadata", {}),
        }

        data_by_action = {
            "remember": memory_record,
            "recall": {
                "query": payload.get("query"),
                "memory_type": payload.get("memory_type"),
                "count": 1,
                "results": [
                    {
                        "score": 1.0,
                        "record": memory_record,
                    }
                ],
            },
            "get-memory": memory_record,
            "forget": {
                "memory_id": payload.get("memory_id"),
                "forgotten": True,
            },
            "memory-summary": {
                "total_memories": 3,
                "memory_types": {
                    "research": 1,
                    "trade": 1,
                    "observation": 1,
                },
            },
            "pattern-memory": {
                "memory_id": payload.get("memory_id"),
                "content": f"Pattern memory: {payload.get('pattern')}",
                "memory_type": "pattern",
                "importance": payload.get("importance"),
                "metadata": payload.get("metadata", {}),
            },
            "trade-memory": {
                "memory_id": payload.get("memory_id"),
                "symbol": payload.get("symbol"),
                "side": payload.get("side"),
                "outcome": payload.get("outcome"),
                "memory_type": "trade",
                "importance": payload.get("importance"),
                "metadata": payload.get("metadata", {}),
            },
        }

        return SimpleNamespace(
            success=True,
            message=f"{action} completed.",
            data=data_by_action[action],
            metadata={
                "source": "unit-test",
            },
        )


class FailingMemoryAgent:
    name = "memory-agent"

    def execute(self, action, payload=None, metadata=None):
        return SimpleNamespace(
            success=False,
            message="Memory agent failed.",
            data={
                "reason": "memory operation failed",
            },
            metadata={},
        )


class BrokenMemoryAgent:
    name = "broken-memory-agent"

    def execute(self, action, payload=None, metadata=None):
        raise RuntimeError("Memory agent exploded.")


def sample_memory():
    return {
        "memory_id": "memory-1",
        "content": "Research found that market regime improves entries.",
        "memory_type": "research",
        "importance": 0.8,
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def sample_recall():
    return {
        "query": "market regime entries",
        "memory_type": "research",
    }


def sample_pattern_memory():
    return {
        "memory_id": "pattern-1",
        "pattern": "Bullish regime improves buy signal quality.",
        "importance": 0.7,
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def sample_trade_memory():
    return {
        "memory_id": "trade-1",
        "symbol": "xauusd",
        "side": "buy",
        "outcome": "profit",
        "importance": 0.9,
        "metadata": {
            "order_id": "order-1",
        },
    }


def test_remember_memory_request_to_payload():
    request = RememberMemoryRequest(
        memory_id=" memory-1 ",
        content=" Memory content. ",
        memory_type=" research ",
        importance=0.8,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == {
        "memory_id": "memory-1",
        "content": "Memory content.",
        "memory_type": "research",
        "importance": 0.8,
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_remember_memory_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        RememberMemoryRequest(memory_id="", content="Memory.")

    with pytest.raises(ValueError):
        RememberMemoryRequest(memory_id="memory-1", content="")

    with pytest.raises(ValueError):
        RememberMemoryRequest(
            memory_id="memory-1",
            content="Memory.",
            memory_type="bad",
        )

    with pytest.raises(ValueError):
        RememberMemoryRequest(
            memory_id="memory-1",
            content="Memory.",
            importance=2,
        )

    with pytest.raises(ValueError):
        RememberMemoryRequest(
            memory_id="memory-1",
            content="Memory.",
            metadata=[],
        )


def test_recall_memory_request_to_payload():
    request = RecallMemoryRequest(
        query=" market regime ",
        memory_type=" research ",
    )

    assert request.to_payload() == {
        "query": "market regime",
        "memory_type": "research",
    }


def test_recall_memory_request_without_memory_type():
    request = RecallMemoryRequest(
        query="market regime",
    )

    assert request.to_payload() == {
        "query": "market regime",
    }


def test_recall_memory_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        RecallMemoryRequest(query="")

    with pytest.raises(ValueError):
        RecallMemoryRequest(query="market", memory_type="bad")


def test_memory_id_request_to_payload():
    request = MemoryIdRequest(memory_id=" memory-1 ")

    assert request.to_payload() == {
        "memory_id": "memory-1",
    }


def test_pattern_memory_request_to_payload():
    request = PatternMemoryRequest(
        memory_id=" pattern-1 ",
        pattern=" Bullish regime pattern. ",
        importance=0.7,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_payload() == {
        "memory_id": "pattern-1",
        "pattern": "Bullish regime pattern.",
        "importance": 0.7,
        "metadata": {
            "symbol": "XAUUSD",
        },
    }


def test_trade_memory_request_to_payload():
    request = TradeMemoryRequest(
        memory_id=" trade-1 ",
        symbol="xauusd",
        side="BUY",
        outcome=" profit ",
        importance=0.9,
        metadata={
            "order_id": "order-1",
        },
    )

    assert request.to_payload() == {
        "memory_id": "trade-1",
        "symbol": "XAUUSD",
        "side": "buy",
        "outcome": "profit",
        "importance": 0.9,
        "metadata": {
            "order_id": "order-1",
        },
    }


def test_trade_memory_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        TradeMemoryRequest(memory_id="")

    with pytest.raises(ValueError):
        TradeMemoryRequest(memory_id="trade-1", symbol="")

    with pytest.raises(ValueError):
        TradeMemoryRequest(memory_id="trade-1", side="hold")

    with pytest.raises(ValueError):
        TradeMemoryRequest(memory_id="trade-1", outcome="")

    with pytest.raises(ValueError):
        TradeMemoryRequest(memory_id="trade-1", metadata=[])


def test_normalize_remember_request_preserves_extra_fields():
    normalized = normalize_remember_request(
        {
            **sample_memory(),
            "source_id": "source-1",
        }
    )

    assert normalized["memory_id"] == "memory-1"
    assert normalized["memory_type"] == "research"
    assert normalized["importance"] == 0.8
    assert normalized["source_id"] == "source-1"


def test_normalize_remember_request_rejects_non_dict():
    with pytest.raises(ValueError, match="Remember request"):
        normalize_remember_request("bad")


def test_normalize_recall_request_preserves_extra_fields():
    normalized = normalize_recall_request(
        {
            **sample_recall(),
            "limit": 5,
        }
    )

    assert normalized["query"] == "market regime entries"
    assert normalized["memory_type"] == "research"
    assert normalized["limit"] == 5


def test_normalize_recall_request_rejects_non_dict():
    with pytest.raises(ValueError, match="Recall request"):
        normalize_recall_request("bad")


def test_normalize_pattern_memory_request_preserves_extra_fields():
    normalized = normalize_pattern_memory_request(
        {
            **sample_pattern_memory(),
            "source_id": "source-1",
        }
    )

    assert normalized["memory_id"] == "pattern-1"
    assert normalized["pattern"] == "Bullish regime improves buy signal quality."
    assert normalized["source_id"] == "source-1"


def test_normalize_trade_memory_request_preserves_extra_fields():
    normalized = normalize_trade_memory_request(
        {
            **sample_trade_memory(),
            "source_id": "source-1",
        }
    )

    assert normalized["memory_id"] == "trade-1"
    assert normalized["symbol"] == "XAUUSD"
    assert normalized["side"] == "buy"
    assert normalized["outcome"] == "profit"
    assert normalized["source_id"] == "source-1"


def test_memory_agent_operation_success():
    agent = SuccessfulMemoryAgent()

    response = memory_agent_operation(
        agent,
        action="remember",
        payload=sample_memory(),
        success_message="Memory stored.",
        failure_message="Memory failed.",
        request_id="memory-request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Memory stored."
    assert payload["data"]["action"] == "remember"
    assert payload["data"]["agent"] == "memory-agent"
    assert payload["data"]["result"]["memory_id"] == "memory-1"
    assert payload["metadata"]["request_id"] == "memory-request-1"


def test_memory_agent_operation_failure():
    response = memory_agent_operation(
        FailingMemoryAgent(),
        action="remember",
        payload=sample_memory(),
        success_message="Memory stored.",
        failure_message="Memory failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Memory failed."
    assert payload["errors"][0]["code"] == "MEMORY_AGENT_ERROR"
    assert payload["errors"][0]["message"] == "Memory agent failed."
    assert payload["data"]["result"] == {
        "reason": "memory operation failed",
    }


def test_memory_agent_operation_exception():
    response = memory_agent_operation(
        BrokenMemoryAgent(),
        action="remember",
        payload=sample_memory(),
        success_message="Memory stored.",
        failure_message="Memory failed.",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["message"] == "Memory failed. Unexpected exception."
    assert payload["errors"][0]["code"] == "RUNTIMEERROR"
    assert payload["errors"][0]["message"] == "Memory agent exploded."


def test_api_remember_success():
    agent = SuccessfulMemoryAgent()

    response = api_remember(
        agent,
        memory=sample_memory(),
        request_id="remember-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Memory stored."
    assert payload["data"]["action"] == "remember"
    assert payload["data"]["result"]["memory_id"] == "memory-1"
    assert payload["data"]["result"]["memory_type"] == "research"
    assert payload["metadata"]["request_id"] == "remember-1"

    assert agent.calls[0]["payload"]["memory_type"] == "research"


def test_api_remember_validation_failure():
    response = api_remember(
        SuccessfulMemoryAgent(),
        memory="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "memory"


def test_api_recall_success():
    response = api_recall(
        SuccessfulMemoryAgent(),
        recall=sample_recall(),
        request_id="recall-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Memory recall completed."
    assert payload["data"]["action"] == "recall"
    assert payload["data"]["result"]["count"] == 1
    assert payload["data"]["result"]["results"][0]["record"]["memory_id"] == (
        "memory-1"
    )
    assert payload["metadata"]["request_id"] == "recall-1"


def test_api_get_memory_success():
    response = api_get_memory(
        SuccessfulMemoryAgent(),
        memory_id="memory-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Memory loaded."
    assert payload["data"]["action"] == "get-memory"
    assert payload["data"]["result"]["memory_id"] == "memory-1"


def test_api_get_memory_validation_failure():
    response = api_get_memory(
        SuccessfulMemoryAgent(),
        memory_id="",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "memory_id"


def test_api_forget_success():
    response = api_forget(
        SuccessfulMemoryAgent(),
        memory_id="memory-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Memory forgotten."
    assert payload["data"]["action"] == "forget"
    assert payload["data"]["result"]["forgotten"] is True


def test_api_memory_summary_success():
    response = api_memory_summary(
        SuccessfulMemoryAgent(),
        request_id="summary-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Memory summary loaded."
    assert payload["data"]["action"] == "memory-summary"
    assert payload["data"]["result"]["total_memories"] == 3
    assert payload["metadata"]["request_id"] == "summary-1"


def test_api_pattern_memory_success():
    response = api_pattern_memory(
        SuccessfulMemoryAgent(),
        pattern_memory=sample_pattern_memory(),
        request_id="pattern-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Pattern memory stored."
    assert payload["data"]["action"] == "pattern-memory"
    assert payload["data"]["result"]["memory_type"] == "pattern"
    assert payload["metadata"]["request_id"] == "pattern-1"


def test_api_pattern_memory_validation_failure():
    response = api_pattern_memory(
        SuccessfulMemoryAgent(),
        pattern_memory="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "pattern_memory"


def test_api_trade_memory_success():
    response = api_trade_memory(
        SuccessfulMemoryAgent(),
        trade_memory=sample_trade_memory(),
        request_id="trade-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["message"] == "Trade memory stored."
    assert payload["data"]["action"] == "trade-memory"
    assert payload["data"]["result"]["symbol"] == "XAUUSD"
    assert payload["data"]["result"]["side"] == "buy"
    assert payload["data"]["result"]["outcome"] == "profit"
    assert payload["metadata"]["request_id"] == "trade-1"


def test_api_trade_memory_validation_failure():
    response = api_trade_memory(
        SuccessfulMemoryAgent(),
        trade_memory="bad",
    )

    payload = response.to_dict()

    assert payload["success"] is False
    assert payload["errors"][0]["code"] == "VALIDATION_ERROR"
    assert payload["errors"][0]["field"] == "trade_memory"