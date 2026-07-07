"""
Unit tests for AQOS CLI memory commands.
"""

import json
from types import SimpleNamespace

import pytest

from aqos.api import api_failure, api_success
from aqos.cli import (
    CliMemoryIdRequest,
    CliMemorySummaryRequest,
    CliPatternMemoryRequest,
    CliRecallMemoryRequest,
    CliRememberMemoryRequest,
    CliTradeMemoryRequest,
    build_memory_cli_output,
    cli_forget,
    cli_get_memory,
    cli_memory_summary,
    cli_pattern_memory,
    cli_recall,
    cli_remember,
    cli_trade_memory,
    execute_memory_operation,
)


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
        "symbol": "XAUUSD",
        "side": "buy",
        "outcome": "profit",
        "importance": 0.9,
        "metadata": {
            "order_id": "order-1",
        },
    }


def fake_remember(agent, memory, request_id=None):
    return api_success(
        message="Memory stored.",
        data={
            "agent": agent.name,
            **memory,
        },
        request_id=request_id,
    )


def fake_recall(agent, recall, request_id=None):
    return api_success(
        message="Memory recall completed.",
        data={
            "agent": agent.name,
            "query": recall["query"],
            "memory_type": recall.get("memory_type"),
            "count": 1,
            "results": [
                {
                    "score": 1.0,
                    "record": sample_memory(),
                }
            ],
        },
        request_id=request_id,
    )


def fake_get_memory(agent, memory_id, request_id=None):
    return api_success(
        message="Memory loaded.",
        data={
            "agent": agent.name,
            "memory_id": memory_id,
            "content": "Memory content.",
            "memory_type": "research",
        },
        request_id=request_id,
    )


def fake_forget(agent, memory_id, request_id=None):
    return api_success(
        message="Memory forgotten.",
        data={
            "agent": agent.name,
            "memory_id": memory_id,
            "forgotten": True,
        },
        request_id=request_id,
    )


def fake_memory_summary(agent, request_id=None):
    return api_success(
        message="Memory summary loaded.",
        data={
            "agent": agent.name,
            "total_memories": 3,
            "memory_types": {
                "research": 1,
                "trade": 1,
                "observation": 1,
            },
        },
        request_id=request_id,
    )


def fake_pattern_memory(agent, pattern_memory, request_id=None):
    return api_success(
        message="Pattern memory stored.",
        data={
            "agent": agent.name,
            "memory_type": "pattern",
            **pattern_memory,
        },
        request_id=request_id,
    )


def fake_trade_memory(agent, trade_memory, request_id=None):
    return api_success(
        message="Trade memory stored.",
        data={
            "agent": agent.name,
            "memory_type": "trade",
            **trade_memory,
        },
        request_id=request_id,
    )


def fake_failure_memory(agent, memory=None, request_id=None):
    return api_failure(
        message="Memory command failed.",
        data={
            "memory_id": memory.get("memory_id") if memory else "missing-memory",
        },
        request_id=request_id,
    )


def test_cli_remember_memory_request_accepts_valid_values():
    agent = SimpleNamespace(name="memory-agent")

    request = CliRememberMemoryRequest(
        agent=agent,
        memory_id=" memory-1 ",
        content=" Research found that market regime improves entries. ",
        memory_type=" research ",
        importance=0.8,
        metadata={
            "symbol": "XAUUSD",
        },
        output_format="pretty-json",
        include_metadata=True,
        request_id="memory-request-1",
    )

    assert request.agent == agent
    assert request.output_format == "pretty-json"
    assert request.include_metadata is True
    assert request.request_id == "memory-request-1"
    assert request.to_memory() == sample_memory()


def test_cli_remember_memory_request_rejects_invalid_values():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=None,
            memory_id="memory-1",
            content="Memory.",
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="",
            content="Memory.",
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="memory-1",
            content="",
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="memory-1",
            content="Memory.",
            memory_type="bad",
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="memory-1",
            content="Memory.",
            importance=2,
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="memory-1",
            content="Memory.",
            metadata=[],
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="memory-1",
            content="Memory.",
            output_format="bad",
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="memory-1",
            content="Memory.",
            include_metadata="yes",
        )

    with pytest.raises(ValueError):
        CliRememberMemoryRequest(
            agent=agent,
            memory_id="memory-1",
            content="Memory.",
            request_id="",
        )


def test_cli_recall_memory_request_accepts_valid_values():
    agent = SimpleNamespace(name="memory-agent")

    request = CliRecallMemoryRequest(
        agent=agent,
        query=" market regime entries ",
        memory_type=" research ",
    )

    assert request.to_recall() == sample_recall()


def test_cli_recall_memory_request_without_memory_type():
    agent = SimpleNamespace(name="memory-agent")

    request = CliRecallMemoryRequest(
        agent=agent,
        query="market regime entries",
    )

    assert request.to_recall() == {
        "query": "market regime entries",
    }


def test_cli_recall_memory_request_rejects_invalid_values():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        CliRecallMemoryRequest(agent=None, query="market")

    with pytest.raises(ValueError):
        CliRecallMemoryRequest(agent=agent, query="")

    with pytest.raises(ValueError):
        CliRecallMemoryRequest(agent=agent, query="market", memory_type="bad")


def test_cli_memory_id_request_to_payload():
    agent = SimpleNamespace(name="memory-agent")

    request = CliMemoryIdRequest(
        agent=agent,
        memory_id=" memory-1 ",
    )

    assert request.to_payload() == {
        "memory_id": "memory-1",
    }


def test_cli_memory_id_request_rejects_invalid_values():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        CliMemoryIdRequest(agent=None, memory_id="memory-1")

    with pytest.raises(ValueError):
        CliMemoryIdRequest(agent=agent, memory_id="")


def test_cli_pattern_memory_request_accepts_valid_values():
    agent = SimpleNamespace(name="memory-agent")

    request = CliPatternMemoryRequest(
        agent=agent,
        memory_id=" pattern-1 ",
        pattern=" Bullish regime improves buy signal quality. ",
        importance=0.7,
        metadata={
            "symbol": "XAUUSD",
        },
    )

    assert request.to_pattern_memory() == sample_pattern_memory()


def test_cli_pattern_memory_request_rejects_invalid_values():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        CliPatternMemoryRequest(
            agent=None,
            memory_id="pattern-1",
            pattern="Pattern.",
        )

    with pytest.raises(ValueError):
        CliPatternMemoryRequest(
            agent=agent,
            memory_id="",
            pattern="Pattern.",
        )

    with pytest.raises(ValueError):
        CliPatternMemoryRequest(
            agent=agent,
            memory_id="pattern-1",
            pattern="",
        )

    with pytest.raises(ValueError):
        CliPatternMemoryRequest(
            agent=agent,
            memory_id="pattern-1",
            pattern="Pattern.",
            metadata=[],
        )


def test_cli_trade_memory_request_accepts_valid_values():
    agent = SimpleNamespace(name="memory-agent")

    request = CliTradeMemoryRequest(
        agent=agent,
        memory_id=" trade-1 ",
        symbol="xauusd",
        side="BUY",
        outcome=" profit ",
        importance=0.9,
        metadata={
            "order_id": "order-1",
        },
    )

    assert request.to_trade_memory() == sample_trade_memory()


def test_cli_trade_memory_request_rejects_invalid_values():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        CliTradeMemoryRequest(agent=None, memory_id="trade-1")

    with pytest.raises(ValueError):
        CliTradeMemoryRequest(agent=agent, memory_id="")

    with pytest.raises(ValueError):
        CliTradeMemoryRequest(agent=agent, memory_id="trade-1", symbol="")

    with pytest.raises(ValueError):
        CliTradeMemoryRequest(agent=agent, memory_id="trade-1", side="hold")

    with pytest.raises(ValueError):
        CliTradeMemoryRequest(agent=agent, memory_id="trade-1", outcome="")

    with pytest.raises(ValueError):
        CliTradeMemoryRequest(agent=agent, memory_id="trade-1", metadata=[])


def test_cli_memory_summary_request_rejects_invalid_values():
    with pytest.raises(ValueError):
        CliMemorySummaryRequest(agent=None)

    with pytest.raises(ValueError):
        CliMemorySummaryRequest(
            agent=SimpleNamespace(name="memory-agent"),
            output_format="bad",
        )


def test_execute_memory_operation_with_request_id():
    agent = SimpleNamespace(name="memory-agent")

    response = execute_memory_operation(
        fake_remember,
        agent=agent,
        memory=sample_memory(),
        request_id="request-1",
    )

    payload = response.to_dict()

    assert payload["success"] is True
    assert payload["metadata"]["request_id"] == "request-1"
    assert payload["data"]["agent"] == "memory-agent"


def test_execute_memory_operation_rejects_invalid_values():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        execute_memory_operation(
            "not-callable",
            agent=agent,
        )

    with pytest.raises(ValueError):
        execute_memory_operation(
            fake_remember,
            agent=None,
        )


def test_build_memory_cli_output_success():
    agent = SimpleNamespace(name="memory-agent")

    response = fake_remember(
        agent,
        sample_memory(),
        request_id="request-1",
    )

    cli_output = build_memory_cli_output(
        response,
        output_format="text",
        include_metadata=True,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Memory stored." in cli_output.output
    assert "memory_id: memory-1" in cli_output.output
    assert "request_id: request-1" in cli_output.output


def test_build_memory_cli_output_failure():
    agent = SimpleNamespace(name="memory-agent")

    response = fake_failure_memory(
        agent,
        sample_memory(),
    )

    cli_output = build_memory_cli_output(
        response,
        output_format="json",
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is False
    assert cli_output.exit_code == 1
    assert payload["success"] is False
    assert payload["message"] == "Memory command failed."


def test_cli_remember_text_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_remember(
        agent=agent,
        memory_id="memory-1",
        content="Research found that market regime improves entries.",
        memory_type="research",
        importance=0.8,
        metadata={
            "symbol": "XAUUSD",
        },
        output_format="text",
        request_id="remember-1",
        operation=fake_remember,
    )

    assert cli_output.success is True
    assert cli_output.exit_code == 0
    assert "SUCCESS: Memory stored." in cli_output.output
    assert "memory_id: memory-1" in cli_output.output
    assert "memory_type: research" in cli_output.output


def test_cli_remember_json_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_remember(
        agent=agent,
        memory_id="memory-1",
        content="Research found that market regime improves entries.",
        memory_type="research",
        output_format="json",
        operation=fake_remember,
    )

    payload = json.loads(cli_output.output)

    assert cli_output.success is True
    assert payload["success"] is True
    assert payload["data"]["memory_id"] == "memory-1"
    assert payload["data"]["memory_type"] == "research"
    assert "metadata" not in payload


def test_cli_remember_validation_failure():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        cli_remember(
            agent=agent,
            memory_id="",
            content="Memory.",
            operation=fake_remember,
        )


def test_cli_recall_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_recall(
        agent=agent,
        query="market regime entries",
        memory_type="research",
        output_format="text",
        request_id="recall-1",
        operation=fake_recall,
    )

    assert cli_output.success is True
    assert "SUCCESS: Memory recall completed." in cli_output.output
    assert "query: market regime entries" in cli_output.output
    assert "count: 1" in cli_output.output


def test_cli_get_memory_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_get_memory(
        agent=agent,
        memory_id="memory-1",
        output_format="text",
        operation=fake_get_memory,
    )

    assert cli_output.success is True
    assert "SUCCESS: Memory loaded." in cli_output.output
    assert "memory_id: memory-1" in cli_output.output


def test_cli_get_memory_validation_failure():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        cli_get_memory(
            agent=agent,
            memory_id="",
            operation=fake_get_memory,
        )


def test_cli_forget_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_forget(
        agent=agent,
        memory_id="memory-1",
        output_format="text",
        operation=fake_forget,
    )

    assert cli_output.success is True
    assert "SUCCESS: Memory forgotten." in cli_output.output
    assert "forgotten: true" in cli_output.output


def test_cli_memory_summary_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_memory_summary(
        agent=agent,
        output_format="text",
        request_id="summary-1",
        operation=fake_memory_summary,
    )

    assert cli_output.success is True
    assert "SUCCESS: Memory summary loaded." in cli_output.output
    assert "total_memories: 3" in cli_output.output
    assert "memory_types:" in cli_output.output


def test_cli_pattern_memory_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_pattern_memory(
        agent=agent,
        memory_id="pattern-1",
        pattern="Bullish regime improves buy signal quality.",
        importance=0.7,
        metadata={
            "symbol": "XAUUSD",
        },
        output_format="text",
        request_id="pattern-1",
        operation=fake_pattern_memory,
    )

    assert cli_output.success is True
    assert "SUCCESS: Pattern memory stored." in cli_output.output
    assert "memory_id: pattern-1" in cli_output.output
    assert "memory_type: pattern" in cli_output.output


def test_cli_pattern_memory_validation_failure():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        cli_pattern_memory(
            agent=agent,
            memory_id="pattern-1",
            pattern="",
            operation=fake_pattern_memory,
        )


def test_cli_trade_memory_success():
    agent = SimpleNamespace(name="memory-agent")

    cli_output = cli_trade_memory(
        agent=agent,
        memory_id="trade-1",
        symbol="xauusd",
        side="buy",
        outcome="profit",
        importance=0.9,
        metadata={
            "order_id": "order-1",
        },
        output_format="text",
        request_id="trade-1",
        operation=fake_trade_memory,
    )

    assert cli_output.success is True
    assert "SUCCESS: Trade memory stored." in cli_output.output
    assert "memory_id: trade-1" in cli_output.output
    assert "symbol: XAUUSD" in cli_output.output
    assert "side: buy" in cli_output.output
    assert "outcome: profit" in cli_output.output


def test_cli_trade_memory_validation_failure():
    agent = SimpleNamespace(name="memory-agent")

    with pytest.raises(ValueError):
        cli_trade_memory(
            agent=agent,
            memory_id="trade-1",
            side="hold",
            operation=fake_trade_memory,
        )