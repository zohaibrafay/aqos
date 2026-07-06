"""
Unit tests for PaperTradingEngine.
"""

import pytest

from aqos.evaluation import PaperTrade, PaperTradingEngine


def test_open_trade():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    trade = engine.open_trade(
        trade_id="trade-1",
        symbol="XAUUSD",
        side="buy",
        quantity=2.0,
        entry_price=2000.0,
    )

    assert isinstance(trade, PaperTrade)
    assert trade.trade_id == "trade-1"
    assert trade.symbol == "XAUUSD"
    assert trade.side == "buy"
    assert trade.quantity == 2.0
    assert trade.entry_price == 2000.0
    assert trade.status == "open"


def test_close_buy_trade_with_profit():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    engine.open_trade(
        trade_id="trade-1",
        symbol="XAUUSD",
        side="buy",
        quantity=2.0,
        entry_price=2000.0,
    )

    trade = engine.close_trade(
        trade_id="trade-1",
        exit_price=2010.0,
    )

    assert trade.status == "closed"
    assert trade.exit_price == 2010.0
    assert trade.profit == 20.0
    assert engine.balance == 10_020.0


def test_close_sell_trade_with_profit():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    engine.open_trade(
        trade_id="trade-1",
        symbol="XAUUSD",
        side="sell",
        quantity=2.0,
        entry_price=2000.0,
    )

    trade = engine.close_trade(
        trade_id="trade-1",
        exit_price=1990.0,
    )

    assert trade.profit == 20.0
    assert engine.balance == 10_020.0


def test_close_buy_trade_with_loss():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    engine.open_trade(
        trade_id="trade-1",
        symbol="XAUUSD",
        side="buy",
        quantity=2.0,
        entry_price=2000.0,
    )

    trade = engine.close_trade(
        trade_id="trade-1",
        exit_price=1990.0,
    )

    assert trade.profit == -20.0
    assert engine.balance == 9_980.0


def test_get_trade():
    engine = PaperTradingEngine()

    engine.open_trade(
        trade_id="trade-1",
        symbol="XAUUSD",
        side="buy",
        quantity=1.0,
        entry_price=2000.0,
    )

    trade = engine.get_trade("trade-1")

    assert trade is not None
    assert trade.trade_id == "trade-1"


def test_get_missing_trade():
    engine = PaperTradingEngine()

    trade = engine.get_trade("missing")

    assert trade is None


def test_list_trades():
    engine = PaperTradingEngine()

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)
    engine.open_trade("trade-2", "EURUSD", "sell", 1000.0, 1.1)

    assert len(engine.list_trades()) == 2


def test_open_and_closed_trades():
    engine = PaperTradingEngine()

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)
    engine.open_trade("trade-2", "EURUSD", "sell", 1000.0, 1.1)

    engine.close_trade("trade-1", 2010.0)

    assert len(engine.open_trades()) == 1
    assert len(engine.closed_trades()) == 1


def test_total_profit():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)
    engine.close_trade("trade-1", 2010.0)

    assert engine.total_profit() == 10.0


def test_equity_without_current_prices():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    assert engine.equity() == 10_000.0


def test_equity_with_open_trade_unrealized_profit():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)

    equity = engine.equity(
        current_prices={
            "XAUUSD": 2010.0,
        }
    )

    assert equity == 10_010.0


def test_clear_trades():
    engine = PaperTradingEngine(initial_balance=10_000.0)

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)
    engine.close_trade("trade-1", 2010.0)

    engine.clear()

    assert engine.balance == 10_000.0
    assert engine.list_trades() == []


def test_invalid_initial_balance():
    with pytest.raises(ValueError):
        PaperTradingEngine(initial_balance=0)


def test_empty_trade_id():
    engine = PaperTradingEngine()

    with pytest.raises(ValueError):
        engine.open_trade("", "XAUUSD", "buy", 1.0, 2000.0)


def test_duplicate_trade_id():
    engine = PaperTradingEngine()

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)

    with pytest.raises(ValueError):
        engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)


def test_empty_symbol():
    engine = PaperTradingEngine()

    with pytest.raises(ValueError):
        engine.open_trade("trade-1", "", "buy", 1.0, 2000.0)


def test_invalid_side():
    engine = PaperTradingEngine()

    with pytest.raises(ValueError):
        engine.open_trade("trade-1", "XAUUSD", "hold", 1.0, 2000.0)


def test_invalid_quantity():
    engine = PaperTradingEngine()

    with pytest.raises(ValueError):
        engine.open_trade("trade-1", "XAUUSD", "buy", 0, 2000.0)


def test_invalid_entry_price():
    engine = PaperTradingEngine()

    with pytest.raises(ValueError):
        engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 0)


def test_close_missing_trade():
    engine = PaperTradingEngine()

    with pytest.raises(ValueError):
        engine.close_trade("missing", 2000.0)


def test_close_already_closed_trade():
    engine = PaperTradingEngine()

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)
    engine.close_trade("trade-1", 2010.0)

    with pytest.raises(ValueError):
        engine.close_trade("trade-1", 2020.0)


def test_invalid_exit_price():
    engine = PaperTradingEngine()

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)

    with pytest.raises(ValueError):
        engine.close_trade("trade-1", 0)


def test_invalid_current_price_for_equity():
    engine = PaperTradingEngine()

    engine.open_trade("trade-1", "XAUUSD", "buy", 1.0, 2000.0)

    with pytest.raises(ValueError):
        engine.equity(
            current_prices={
                "XAUUSD": 0,
            }
        )