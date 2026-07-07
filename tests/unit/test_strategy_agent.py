"""
Unit tests for StrategyAgent.
"""

from aqos.agents import (
    AgentBase,
    StrategyAgent,
)


def create_strategy_agent() -> StrategyAgent:
    return StrategyAgent()


def test_strategy_agent_is_agent_base_instance():
    agent = StrategyAgent()

    assert isinstance(agent, AgentBase)


def test_strategy_agent_name():
    agent = StrategyAgent()

    assert agent.name == "strategy-agent"


def test_strategy_agent_description():
    agent = StrategyAgent()

    assert agent.description == (
        "Agent for strategy signals, decisions, explanations, and handoffs."
    )


def test_available_actions():
    agent = StrategyAgent()

    assert agent.available_actions() == [
        "decision",
        "entry-check",
        "exit-check",
        "explain-signal",
        "handoff",
        "health",
        "signal",
    ]


def test_health():
    agent = create_strategy_agent()

    result = agent.execute("health")

    assert result.success is True
    assert result.message == "Strategy agent is healthy."
    assert result.data["status"] == "ok"
    assert result.data["supported_signals"] == [
        "buy",
        "hold",
        "sell",
    ]


def test_signal_buy():
    agent = create_strategy_agent()

    result = agent.execute(
        action="signal",
        payload={
            "market_state": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2000.0,
            }
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Strategy signal generated."
    assert result.data["signal"] == "buy"
    assert result.data["regime"] == "bullish"
    assert result.data["trend"] == "uptrend"
    assert result.metadata["request_id"] == "req-1"


def test_signal_sell():
    agent = create_strategy_agent()

    result = agent.execute(
        action="signal",
        payload={
            "market_state": {
                "regime": "bearish",
                "trend": "downtrend",
                "entry_price": 2000.0,
            }
        },
    )

    assert result.success is True
    assert result.data["signal"] == "sell"


def test_signal_hold():
    agent = create_strategy_agent()

    result = agent.execute(
        action="signal",
        payload={
            "market_state": {
                "regime": "neutral",
                "trend": "sideways",
                "entry_price": 2000.0,
            }
        },
    )

    assert result.success is True
    assert result.data["signal"] == "hold"


def test_signal_missing_market_state():
    agent = create_strategy_agent()

    result = agent.execute(
        action="signal",
        payload={},
    )

    assert result.success is False
    assert result.message == "Missing required payload key: market_state"


def test_signal_missing_regime():
    agent = create_strategy_agent()

    result = agent.execute(
        action="signal",
        payload={
            "market_state": {
                "trend": "uptrend",
            }
        },
    )

    assert result.success is False
    assert result.message == "Market state is missing required key: regime"


def test_signal_missing_trend():
    agent = create_strategy_agent()

    result = agent.execute(
        action="signal",
        payload={
            "market_state": {
                "regime": "bullish",
            }
        },
    )

    assert result.success is False
    assert result.message == "Market state is missing required key: trend"


def test_signal_rejects_invalid_market_state_type():
    agent = create_strategy_agent()

    result = agent.execute(
        action="signal",
        payload={
            "market_state": "invalid",
        },
    )

    assert result.success is False
    assert result.message == "Market state must be a dictionary."


def test_decision():
    agent = create_strategy_agent()

    result = agent.execute(
        action="decision",
        payload={
            "market_state": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2000.0,
            }
        },
    )

    assert result.success is True
    assert result.message == "Strategy decision generated."
    assert result.data["signal"] == "buy"
    assert result.data["should_enter"] is True
    assert result.data["should_exit"] is False
    assert result.data["stop_loss_price"] is not None
    assert result.data["take_profit_price"] is not None


def test_decision_without_entry_price():
    agent = create_strategy_agent()

    result = agent.execute(
        action="decision",
        payload={
            "market_state": {
                "regime": "bullish",
                "trend": "uptrend",
            }
        },
    )

    assert result.success is True
    assert result.data["signal"] == "buy"


def test_explain_buy_signal():
    agent = create_strategy_agent()

    result = agent.execute(
        action="explain-signal",
        payload={
            "signal": "buy",
        },
    )

    assert result.success is True
    assert result.message == "Strategy signal explained."
    assert result.data["signal"] == "buy"
    assert result.data["bias"] == "bullish"
    assert result.data["explanation"] == "Buy signal indicates bullish strategy bias."


def test_explain_sell_signal():
    agent = create_strategy_agent()

    result = agent.execute(
        action="explain-signal",
        payload={
            "signal": "sell",
        },
    )

    assert result.success is True
    assert result.data["bias"] == "bearish"
    assert result.data["explanation"] == "Sell signal indicates bearish strategy bias."


def test_explain_hold_signal():
    agent = create_strategy_agent()

    result = agent.execute(
        action="explain-signal",
        payload={
            "signal": "hold",
        },
    )

    assert result.success is True
    assert result.data["bias"] == "neutral"
    assert result.data["explanation"] == "Hold signal indicates no active entry bias."


def test_explain_signal_rejects_invalid_signal():
    agent = create_strategy_agent()

    result = agent.execute(
        action="explain-signal",
        payload={
            "signal": "invalid",
        },
    )

    assert result.success is False
    assert result.message == "Signal must be buy, sell, or hold."


def test_entry_check_buy():
    agent = create_strategy_agent()

    result = agent.execute(
        action="entry-check",
        payload={
            "signal": "buy",
        },
    )

    assert result.success is True
    assert result.message == "Strategy entry check completed."
    assert result.data["should_enter"] is True
    assert result.data["reason"] == "buy signal allows a new strategy entry."


def test_entry_check_hold():
    agent = create_strategy_agent()

    result = agent.execute(
        action="entry-check",
        payload={
            "signal": "hold",
        },
    )

    assert result.success is True
    assert result.data["should_enter"] is False
    assert result.data["reason"] == "Hold signal does not allow a new strategy entry."


def test_exit_check_long_on_sell():
    agent = create_strategy_agent()

    result = agent.execute(
        action="exit-check",
        payload={
            "signal": "sell",
            "current_position": "long",
        },
    )

    assert result.success is True
    assert result.message == "Strategy exit check completed."
    assert result.data["should_exit"] is True
    assert result.data["reason"] == "long position should exit because signal is sell."


def test_exit_check_short_on_buy():
    agent = create_strategy_agent()

    result = agent.execute(
        action="exit-check",
        payload={
            "signal": "buy",
            "current_position": "short",
        },
    )

    assert result.success is True
    assert result.data["should_exit"] is True
    assert result.data["reason"] == "short position should exit because signal is buy."


def test_exit_check_hold_on_position():
    agent = create_strategy_agent()

    result = agent.execute(
        action="exit-check",
        payload={
            "signal": "hold",
            "current_position": "long",
        },
    )

    assert result.success is True
    assert result.data["should_exit"] is True
    assert result.data["reason"] == "long position should exit because signal is hold."


def test_exit_check_no_exit():
    agent = create_strategy_agent()

    result = agent.execute(
        action="exit-check",
        payload={
            "signal": "buy",
            "current_position": "long",
        },
    )

    assert result.success is True
    assert result.data["should_exit"] is False
    assert result.data["reason"] == "No strategy exit required."


def test_handoff():
    agent = create_strategy_agent()

    result = agent.execute(
        action="handoff",
        payload={
            "market_state": {
                "symbol": "XAUUSD",
                "timeframe": "H1",
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2000.0,
            }
        },
        metadata={
            "request_id": "req-1",
        },
    )

    assert result.success is True
    assert result.message == "Strategy handoff generated."
    assert result.data["symbol"] == "XAUUSD"
    assert result.data["timeframe"] == "H1"
    assert result.data["signal"] == "buy"
    assert result.data["should_enter"] is True
    assert result.data["should_exit"] is False
    assert result.data["entry_price"] == 2000.0
    assert result.data["stop_loss_price"] is not None
    assert result.data["take_profit_price"] is not None
    assert result.metadata["request_id"] == "req-1"


def test_handoff_defaults_symbol_and_timeframe():
    agent = create_strategy_agent()

    result = agent.execute(
        action="handoff",
        payload={
            "market_state": {
                "regime": "bullish",
                "trend": "uptrend",
                "entry_price": 2000.0,
            }
        },
    )

    assert result.success is True
    assert result.data["symbol"] == "UNKNOWN"
    assert result.data["timeframe"] == "UNKNOWN"


def test_unsupported_action():
    agent = StrategyAgent()

    result = agent.execute("unknown")

    assert result.success is False
    assert result.message == "Unsupported agent action: unknown"