"""
Unit tests for AQOS broker account and position contracts.
"""

import pytest

from aqos.brokers import (
    BrokerAccount,
    BrokerAccountSnapshot,
    BrokerPosition,
    PositionAccountAdapter,
    PositionSide,
    apply_trade_to_position,
    build_broker_account,
    build_broker_account_snapshot,
    build_broker_config,
    build_broker_position,
    build_broker_trade,
    build_position_account_adapter,
    calculate_realized_pnl,
    normalize_position_side,
    opposite_position_side,
    position_id_for_symbol,
    position_side_from_trade_side,
    validate_account_currency,
    validate_broker_positions,
    validate_broker_trades,
    validate_number,
    validate_position_dict,
    validate_trade_dict,
)


def build_config():
    return build_broker_config(
        broker_id="paper-1",
        name="Paper",
        broker_type="paper",
        capabilities=["paper_trading"],
        paper_mode=True,
    )


def build_trade(
    *,
    trade_id="trade-1",
    side="buy",
    quantity=1,
    price=2000,
    fee=1,
):
    return build_broker_trade(
        trade_id=trade_id,
        order_id=f"order-{trade_id}",
        broker_id="paper-1",
        symbol="XAUUSD",
        side=side,
        quantity=quantity,
        price=price,
        fee=fee,
        executed_at="2026-01-01T00:00:00+00:00",
    )


def build_position():
    return build_broker_position(
        position_id="paper-1-position-XAUUSD",
        broker_id="paper-1",
        symbol="XAUUSD",
        side="long",
        quantity=2,
        average_price=2000,
        market_price=2010,
        fees=1,
        opened_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )


def test_position_side_normalizer():
    assert PositionSide.LONG.value == "long"
    assert PositionSide.SHORT.value == "short"
    assert PositionSide.FLAT.value == "flat"

    assert normalize_position_side(PositionSide.LONG) == PositionSide.LONG
    assert normalize_position_side(" SHORT ") == PositionSide.SHORT
    assert normalize_position_side(" flat ") == PositionSide.FLAT

    with pytest.raises(ValueError):
        normalize_position_side("bad")


def test_number_and_currency_validators():
    assert validate_number(1, "Value") == 1.0
    assert validate_number(-1.5, "Value") == -1.5
    assert validate_account_currency(" usd ") == "USD"

    with pytest.raises(ValueError):
        validate_number(True, "Value")

    with pytest.raises(ValueError):
        validate_number("1", "Value")

    with pytest.raises(ValueError):
        validate_account_currency("")

    with pytest.raises(ValueError):
        validate_account_currency("US")

    with pytest.raises(ValueError):
        validate_account_currency("US1")


def test_broker_account_to_dict():
    account = BrokerAccount(
        broker_id=" paper-1 ",
        account_id=" account-1 ",
        currency=" usd ",
        cash_balance=100000,
        equity=101000,
        buying_power=90000,
        margin_used=10000,
        realized_pnl=500,
        unrealized_pnl=500,
        updated_at="2026-01-01T00:00:00+00:00",
        metadata={
            "source": "test",
        },
    )

    payload = account.to_dict()

    assert account.available_cash == 90000.0
    assert account.total_pnl == 1000.0
    assert payload["broker_id"] == "paper-1"
    assert payload["account_id"] == "account-1"
    assert payload["currency"] == "USD"
    assert payload["available_cash"] == 90000.0
    assert payload["total_pnl"] == 1000.0
    assert payload["metadata"] == {
        "source": "test",
    }


def test_broker_account_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerAccount(broker_id="", account_id="account-1")

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="")

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", currency="US")

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", cash_balance=-1)

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", equity=-1)

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", buying_power=-1)

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", margin_used=-1)

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", realized_pnl="bad")

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", unrealized_pnl="bad")

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", updated_at="")

    with pytest.raises(ValueError):
        BrokerAccount(broker_id="paper-1", account_id="account-1", metadata=[])


def test_build_broker_account_defaults():
    account = build_broker_account(
        broker_id="paper-1",
        account_id="account-1",
        cash_balance=100000,
    )

    assert isinstance(account, BrokerAccount)
    assert account.equity == 100000
    assert account.buying_power == 100000


def test_broker_position_to_dict_long():
    position = build_position()
    payload = position.to_dict()

    assert position.open is True
    assert position.notional == 4000.0
    assert position.market_value == 4020.0
    assert position.unrealized_pnl == 20.0
    assert position.total_pnl == 19.0
    assert payload["position_id"] == "paper-1-position-XAUUSD"
    assert payload["symbol"] == "XAUUSD"
    assert payload["side"] == "long"
    assert payload["current_price"] == 2010.0


def test_broker_position_to_dict_short_and_flat():
    short = build_broker_position(
        position_id="paper-1-position-XAUUSD",
        broker_id="paper-1",
        symbol="XAUUSD",
        side="short",
        quantity=2,
        average_price=2000,
        market_price=1990,
    )
    flat = build_broker_position(
        position_id="paper-1-position-XAUUSD",
        broker_id="paper-1",
        symbol="XAUUSD",
        side="flat",
        quantity=0,
        average_price=0,
        market_price=1990,
    )

    assert short.market_value == -3980.0
    assert short.unrealized_pnl == 20.0
    assert flat.open is False
    assert flat.market_value == 0.0
    assert flat.unrealized_pnl == 0.0


def test_broker_position_rejects_invalid_values():
    with pytest.raises(ValueError):
        BrokerPosition(position_id="", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="", symbol="XAUUSD", side="long", quantity=1, average_price=1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="bad symbol", side="long", quantity=1, average_price=1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="bad", quantity=1, average_price=1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=0, average_price=1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="flat", quantity=1, average_price=1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=-1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=1, market_price=-1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=1, realized_pnl="bad")

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=1, fees=-1)

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=1, opened_at="")

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=1, updated_at="")

    with pytest.raises(ValueError):
        BrokerPosition(position_id="position-1", broker_id="paper-1", symbol="XAUUSD", side="long", quantity=1, average_price=1, metadata=[])


def test_snapshot_to_dict():
    account = build_broker_account(
        broker_id="paper-1",
        account_id="account-1",
        cash_balance=100000,
    )
    position = build_position()
    trade = build_trade()

    snapshot = BrokerAccountSnapshot(
        account=account,
        positions=[position],
        trades=[trade],
        metadata={
            "source": "test",
        },
    )

    payload = snapshot.to_dict()

    assert snapshot.position_count == 1
    assert snapshot.open_position_count == 1
    assert snapshot.trade_count == 1
    assert snapshot.total_market_value == 4020.0
    assert snapshot.total_unrealized_pnl == 20.0
    assert payload["metadata"] == {
        "source": "test",
    }


def test_snapshot_rejects_invalid_values():
    account = build_broker_account(
        broker_id="paper-1",
        account_id="account-1",
        cash_balance=100000,
    )

    with pytest.raises(ValueError):
        BrokerAccountSnapshot(account="bad")

    with pytest.raises(ValueError):
        BrokerAccountSnapshot(account=account, positions=["bad"])

    with pytest.raises(ValueError):
        BrokerAccountSnapshot(account=account, trades=["bad"])

    with pytest.raises(ValueError):
        BrokerAccountSnapshot(account=account, metadata=[])


def test_build_broker_account_snapshot():
    account = build_broker_account(
        broker_id="paper-1",
        account_id="account-1",
        cash_balance=100000,
    )

    snapshot = build_broker_account_snapshot(account=account)

    assert isinstance(snapshot, BrokerAccountSnapshot)
    assert snapshot.position_count == 0


def test_list_validators():
    position = build_position()
    trade = build_trade()

    assert validate_broker_positions([position]) == [position]
    assert validate_broker_trades([trade]) == [trade]
    assert validate_position_dict({"XAUUSD": position}) == {"XAUUSD": position}
    assert validate_trade_dict({"trade-1": trade}) == {"trade-1": trade}

    with pytest.raises(ValueError):
        validate_broker_positions("bad")

    with pytest.raises(ValueError):
        validate_broker_positions(["bad"])

    with pytest.raises(ValueError):
        validate_broker_trades("bad")

    with pytest.raises(ValueError):
        validate_broker_trades(["bad"])

    with pytest.raises(ValueError):
        validate_position_dict("bad")

    with pytest.raises(ValueError):
        validate_position_dict({"bad symbol": position})

    with pytest.raises(ValueError):
        validate_position_dict({"XAUUSD": "bad"})

    with pytest.raises(ValueError):
        validate_trade_dict("bad")

    with pytest.raises(ValueError):
        validate_trade_dict({"": trade})

    with pytest.raises(ValueError):
        validate_trade_dict({"trade-1": "bad"})


def test_position_helper_functions():
    assert position_id_for_symbol(broker_id="paper-1", symbol="xauusd") == "paper-1-position-XAUUSD"
    assert position_side_from_trade_side("buy") == PositionSide.LONG
    assert position_side_from_trade_side("sell") == PositionSide.SHORT
    assert opposite_position_side("long") == PositionSide.SHORT
    assert opposite_position_side("short") == PositionSide.LONG
    assert opposite_position_side("flat") == PositionSide.FLAT

    position = build_position()

    assert calculate_realized_pnl(position=position, exit_quantity=1, exit_price=2010) == 10.0

    short = build_broker_position(
        position_id="paper-1-position-XAUUSD",
        broker_id="paper-1",
        symbol="XAUUSD",
        side="short",
        quantity=2,
        average_price=2000,
        market_price=1990,
    )

    assert calculate_realized_pnl(position=short, exit_quantity=1, exit_price=1990) == 10.0

    with pytest.raises(ValueError):
        calculate_realized_pnl(position="bad", exit_quantity=1, exit_price=1)

    with pytest.raises(ValueError):
        calculate_realized_pnl(position=position, exit_quantity=0, exit_price=1)

    with pytest.raises(ValueError):
        calculate_realized_pnl(position=position, exit_quantity=1, exit_price=0)

    with pytest.raises(ValueError):
        calculate_realized_pnl(position=position, exit_quantity=3, exit_price=1)


def test_apply_trade_to_position_creates_new_position():
    trade = build_trade(
        trade_id="trade-1",
        side="buy",
        quantity=2,
        price=2000,
        fee=1,
    )

    position = apply_trade_to_position(
        existing_position=None,
        trade=trade,
    )

    assert position.side == PositionSide.LONG
    assert position.quantity == 2
    assert position.average_price == 2000
    assert position.fees == 1
    assert position.metadata["created_from_trade_id"] == "trade-1"


def test_apply_trade_to_position_adds_same_side():
    position = apply_trade_to_position(
        existing_position=None,
        trade=build_trade(trade_id="trade-1", side="buy", quantity=1, price=2000),
    )
    updated = apply_trade_to_position(
        existing_position=position,
        trade=build_trade(trade_id="trade-2", side="buy", quantity=1, price=2020),
    )

    assert updated.side == PositionSide.LONG
    assert updated.quantity == 2
    assert updated.average_price == 2010


def test_apply_trade_to_position_partial_close_full_close_and_flip():
    position = apply_trade_to_position(
        existing_position=None,
        trade=build_trade(trade_id="trade-1", side="buy", quantity=2, price=2000),
    )
    partial = apply_trade_to_position(
        existing_position=position,
        trade=build_trade(trade_id="trade-2", side="sell", quantity=1, price=2010),
    )
    flat = apply_trade_to_position(
        existing_position=partial,
        trade=build_trade(trade_id="trade-3", side="sell", quantity=1, price=2020),
    )
    flipped = apply_trade_to_position(
        existing_position=position,
        trade=build_trade(trade_id="trade-4", side="sell", quantity=3, price=1990),
    )

    assert partial.side == PositionSide.LONG
    assert partial.quantity == 1
    assert partial.realized_pnl == 10.0

    assert flat.side == PositionSide.FLAT
    assert flat.quantity == 0
    assert flat.realized_pnl == 30.0

    assert flipped.side == PositionSide.SHORT
    assert flipped.quantity == 1
    assert flipped.average_price == 1990
    assert flipped.realized_pnl == -20.0
    assert flipped.metadata["flipped_by_trade_id"] == "trade-4"

    with pytest.raises(ValueError):
        apply_trade_to_position(existing_position="bad", trade=build_trade())

    with pytest.raises(ValueError):
        apply_trade_to_position(existing_position=None, trade="bad")


def test_position_account_adapter_flow():
    config = build_config()
    adapter = build_position_account_adapter(
        broker_config=config,
        account_id="account-1",
        cash_balance=100000,
        metadata={
            "source": "test",
        },
    )

    position = adapter.apply_trade(
        build_trade(trade_id="trade-1", side="buy", quantity=2, price=2000),
    )
    updated_price = adapter.update_market_price(
        symbol="XAUUSD",
        market_price=2010,
    )
    snapshot = adapter.snapshot()

    assert isinstance(adapter, PositionAccountAdapter)
    assert adapter.broker_id == "paper-1"
    assert adapter.account_id == "account-1"
    assert position.quantity == 2
    assert updated_price.market_price == 2010
    assert adapter.get_position("xauusd").symbol == "XAUUSD"
    assert len(adapter.list_positions()) == 1
    assert len(adapter.open_positions()) == 1
    assert len(adapter.list_trades()) == 1
    assert snapshot.position_count == 1
    assert snapshot.trade_count == 1
    assert snapshot.total_unrealized_pnl == 20.0
    assert adapter.account.unrealized_pnl == 20.0
    assert adapter.account.metadata["gross_market_value"] == 4020.0

    adapter.reset_positions()

    assert adapter.list_positions() == []
    assert adapter.list_trades() == []


def test_position_account_adapter_closing_trade_removes_flat_position():
    adapter = build_position_account_adapter(
        broker_config=build_config(),
        account_id="account-1",
        cash_balance=100000,
    )

    adapter.apply_trade(build_trade(trade_id="trade-1", side="buy", quantity=1, price=2000))
    flat = adapter.apply_trade(build_trade(trade_id="trade-2", side="sell", quantity=1, price=2010))

    assert flat.side == PositionSide.FLAT
    assert adapter.get_position("XAUUSD") is None
    assert len(adapter.list_trades()) == 2


def test_position_account_adapter_rejects_invalid_values():
    config = build_config()
    account = build_broker_account(
        broker_id="paper-1",
        account_id="account-1",
        cash_balance=100000,
    )
    wrong_account = build_broker_account(
        broker_id="other",
        account_id="account-1",
        cash_balance=100000,
    )

    with pytest.raises(ValueError):
        PositionAccountAdapter(broker_config="bad", account=account)

    with pytest.raises(ValueError):
        PositionAccountAdapter(broker_config=config, account="bad")

    with pytest.raises(ValueError):
        PositionAccountAdapter(broker_config=config, account=wrong_account)

    with pytest.raises(ValueError):
        PositionAccountAdapter(broker_config=config, account=account, positions=[])

    with pytest.raises(ValueError):
        PositionAccountAdapter(broker_config=config, account=account, trades=[])

    with pytest.raises(ValueError):
        PositionAccountAdapter(broker_config=config, account=account, metadata=[])

    adapter = build_position_account_adapter(
        broker_config=config,
        account=account,
    )

    wrong_trade = build_broker_trade(
        trade_id="trade-1",
        order_id="order-1",
        broker_id="other",
        symbol="XAUUSD",
        side="buy",
        quantity=1,
        price=2000,
    )

    with pytest.raises(ValueError):
        build_position_account_adapter(broker_config="bad")

    with pytest.raises(ValueError):
        adapter.apply_trade("bad")

    with pytest.raises(ValueError):
        adapter.apply_trade(wrong_trade)

    with pytest.raises(ValueError):
        adapter.update_market_price(symbol="XAUUSD", market_price=0)


def test_update_market_price_returns_none_for_missing_position():
    adapter = build_position_account_adapter(
        broker_config=build_config(),
        account_id="account-1",
        cash_balance=100000,
    )

    assert adapter.update_market_price(symbol="XAUUSD", market_price=2000) is None


def test_broker_account_exports_exist():
    import aqos.brokers as brokers

    expected_exports = [
        "BrokerAccount",
        "BrokerAccountSnapshot",
        "BrokerPosition",
        "PositionAccountAdapter",
        "PositionSide",
        "apply_trade_to_position",
        "build_broker_account",
        "build_broker_account_snapshot",
        "build_broker_position",
        "build_position_account_adapter",
        "calculate_realized_pnl",
        "normalize_position_side",
        "opposite_position_side",
        "position_id_for_symbol",
        "position_side_from_trade_side",
        "validate_account_currency",
        "validate_broker_positions",
        "validate_broker_trades",
        "validate_number",
        "validate_position_dict",
        "validate_trade_dict",
    ]

    for export_name in expected_exports:
        assert hasattr(brokers, export_name), export_name