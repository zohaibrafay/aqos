from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path

import pytest

from aqos.account_analytics.metrics import (
    AccountTradeRecord,
    calculate_trade_metrics,
)
from aqos.accounts.models import (
    AccountStatus,
    AccountType,
    BrokerKind,
    TradingAccount,
)
from aqos.execution_policy.modes import ExecutionMode
from aqos.paper_trading.contracts import (
    AQOS_PAPER_TRADING_VERSION,
    InvalidPaperOrderTransitionError,
    InvalidPaperPositionTransitionError,
    PAPER_ORDER_TRANSITIONS,
    PAPER_POSITION_TRANSITIONS,
    PaperAccountState,
    PaperAction,
    PaperBalance,
    PaperBroker,
    PaperExecutionRequest,
    PaperExecutionResult,
    PaperFill,
    PaperOrder,
    PaperOrderStatus,
    PaperOrderType,
    PaperPosition,
    PaperPositionStatus,
    PaperRejectionReason,
    PaperSide,
    PaperTrade,
    PaperTradingError,
    can_transition_order,
    normalize_paper_symbol,
    side_for_action,
    validate_order_transition,
    validate_position_transition,
)
from aqos.paper_trading.memory_broker import InMemoryPaperBroker
from aqos.paper_trading.validation import (
    PaperValidationResult,
    validate_paper_account,
    validate_paper_execution_request,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)
LATER = datetime(2026, 1, 1, 1, 0, 0)

PAPER_TRADING_ROOT = (
    Path(__file__).resolve().parents[2] / "src" / "aqos" / "paper_trading"
)


def build_account(**overrides) -> TradingAccount:
    payload = {
        "account_id": "account_1",
        "user_id": "user_1",
        "name": "Paper One",
        "account_type": AccountType.PAPER,
        "broker": BrokerKind.INTERNAL_PAPER,
        "status": AccountStatus.ACTIVE,
        "execution_mode": ExecutionMode.MANUAL_APPROVAL,
        "currency": "USD",
        "initial_balance": 10_000.0,
        "current_balance": 10_000.0,
        "equity": 10_000.0,
        "leverage": 1,
        "created_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return TradingAccount(**payload)


def build_request(**overrides) -> PaperExecutionRequest:
    payload = {
        "user_id": "user_1",
        "account_id": "account_1",
        "symbol": "XAUUSD",
        "action": PaperAction.BUY,
        "quantity": 1.0,
        "order_type": PaperOrderType.MARKET,
        "submitted_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return PaperExecutionRequest(**payload)


def build_broker(**overrides) -> InMemoryPaperBroker:
    return InMemoryPaperBroker(account=build_account(**overrides))


def test_paper_trading_version_is_exposed() -> None:
    assert AQOS_PAPER_TRADING_VERSION == "1.0"


def test_paper_trading_never_reaches_an_external_venue() -> None:
    """Paper trading is simulated inside AQOS and must not talk to a broker."""

    forbidden = (
        "requests",
        "httpx",
        "urllib",
        "socket",
        "MetaTrader5",
        "binance",
        "ccxt",
        "aiohttp",
    )

    for path in PAPER_TRADING_ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")

        for name in forbidden:
            assert f"import {name}" not in content, f"{path.name} imports {name}"
            assert f"from {name}" not in content, f"{path.name} imports {name}"


def test_all_required_order_statuses_exist() -> None:
    assert {status.value for status in PaperOrderStatus} == {
        "created",
        "accepted",
        "rejected",
        "partially_filled",
        "filled",
        "cancelled",
        "expired",
        "failed",
    }


def test_all_required_position_statuses_exist() -> None:
    assert {status.value for status in PaperPositionStatus} == {
        "open",
        "partially_closed",
        "closed",
    }


def test_every_order_status_is_in_the_transition_table() -> None:
    assert set(PAPER_ORDER_TRANSITIONS) == set(PaperOrderStatus)
    assert set(PAPER_POSITION_TRANSITIONS) == set(PaperPositionStatus)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (PaperOrderStatus.CREATED, PaperOrderStatus.ACCEPTED),
        (PaperOrderStatus.CREATED, PaperOrderStatus.REJECTED),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.PARTIALLY_FILLED),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.FILLED),
        (PaperOrderStatus.PARTIALLY_FILLED, PaperOrderStatus.FILLED),
        (PaperOrderStatus.ACCEPTED, PaperOrderStatus.CANCELLED),
    ],
)
def test_allowed_order_transitions(from_status, to_status) -> None:
    assert can_transition_order(from_status, to_status) is True

    validate_order_transition(from_status, to_status)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (PaperOrderStatus.CREATED, PaperOrderStatus.FILLED),
        (PaperOrderStatus.FILLED, PaperOrderStatus.CANCELLED),
        (PaperOrderStatus.REJECTED, PaperOrderStatus.FILLED),
        (PaperOrderStatus.CANCELLED, PaperOrderStatus.FILLED),
        (PaperOrderStatus.EXPIRED, PaperOrderStatus.FILLED),
    ],
)
def test_forbidden_order_transitions(from_status, to_status) -> None:
    assert can_transition_order(from_status, to_status) is False

    with pytest.raises(InvalidPaperOrderTransitionError, match="cannot move from"):
        validate_order_transition(from_status, to_status)


def test_a_filled_order_can_only_come_from_accepted_or_partial() -> None:
    """An order must be accepted before it can ever fill."""

    sources = {
        status
        for status, targets in PAPER_ORDER_TRANSITIONS.items()
        if PaperOrderStatus.FILLED in targets
    }

    assert sources == {
        PaperOrderStatus.ACCEPTED,
        PaperOrderStatus.PARTIALLY_FILLED,
    }


def test_position_transitions() -> None:
    validate_position_transition(
        PaperPositionStatus.OPEN,
        PaperPositionStatus.CLOSED,
    )

    with pytest.raises(InvalidPaperPositionTransitionError):
        validate_position_transition(
            PaperPositionStatus.CLOSED,
            PaperPositionStatus.OPEN,
        )


def test_normalize_paper_symbol() -> None:
    assert normalize_paper_symbol(" xau usd ") == "XAUUSD"

    with pytest.raises(PaperTradingError, match="symbol cannot be empty"):
        normalize_paper_symbol("   ")


def test_side_for_action() -> None:
    assert side_for_action(PaperAction.BUY) == PaperSide.LONG
    assert side_for_action(PaperAction.SELL) == PaperSide.SHORT

    with pytest.raises(PaperTradingError, match="does not open a position"):
        side_for_action(PaperAction.CLOSE)


def test_execution_request_normalizes_and_validates() -> None:
    request = build_request(symbol=" xau usd ")

    assert request.symbol == "XAUUSD"
    assert request.is_opening is True
    assert request.to_dict()["action"] == "buy"

    with pytest.raises(PaperTradingError, match="user_id cannot be empty"):
        build_request(user_id="  ")

    with pytest.raises(PaperTradingError, match="account_id cannot be empty"):
        build_request(account_id="")


def test_fill_validation() -> None:
    with pytest.raises(PaperTradingError, match="fill quantity must be positive"):
        PaperFill(
            fill_id="f1",
            order_id="o1",
            quantity=0.0,
            price=1.0,
            filled_at_utc=FIXED_NOW,
        )

    with pytest.raises(PaperTradingError, match="fill price must be positive"):
        PaperFill(
            fill_id="f1",
            order_id="o1",
            quantity=1.0,
            price=0.0,
            filled_at_utc=FIXED_NOW,
        )

    with pytest.raises(PaperTradingError, match="commission cannot be negative"):
        PaperFill(
            fill_id="f1",
            order_id="o1",
            quantity=1.0,
            price=1.0,
            filled_at_utc=FIXED_NOW,
            commission=-1.0,
        )

    fill = PaperFill(
        fill_id="f1",
        order_id="o1",
        quantity=2.0,
        price=100.0,
        filled_at_utc=FIXED_NOW,
    )

    assert fill.notional == pytest.approx(200.0)


def test_order_validation() -> None:
    base = {
        "order_id": "o1",
        "account_id": "account_1",
        "user_id": "user_1",
        "symbol": "XAUUSD",
        "action": PaperAction.BUY,
        "order_type": PaperOrderType.MARKET,
        "quantity": 1.0,
        "status": PaperOrderStatus.CREATED,
        "created_at_utc": FIXED_NOW,
        "updated_at_utc": FIXED_NOW,
    }

    with pytest.raises(PaperTradingError, match="quantity must be positive"):
        PaperOrder(**{**base, "quantity": 0.0})

    with pytest.raises(PaperTradingError, match="cannot exceed quantity"):
        PaperOrder(**{**base, "filled_quantity": 2.0})

    with pytest.raises(PaperTradingError, match="must carry a rejection reason"):
        PaperOrder(**{**base, "status": PaperOrderStatus.REJECTED})

    order = PaperOrder(**base)

    assert order.remaining_quantity == pytest.approx(1.0)
    assert order.is_open is True
    assert order.is_terminal is False


def test_order_with_status_validates_the_transition() -> None:
    order = PaperOrder(
        order_id="o1",
        account_id="account_1",
        user_id="user_1",
        symbol="XAUUSD",
        action=PaperAction.BUY,
        order_type=PaperOrderType.MARKET,
        quantity=1.0,
        status=PaperOrderStatus.CREATED,
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
    )

    accepted = order.with_status(PaperOrderStatus.ACCEPTED, LATER)

    assert accepted.status == PaperOrderStatus.ACCEPTED
    assert accepted.updated_at_utc == LATER

    with pytest.raises(InvalidPaperOrderTransitionError):
        order.with_status(PaperOrderStatus.FILLED, LATER)


def test_position_validation_and_pnl() -> None:
    position = PaperPosition(
        position_id="p1",
        account_id="account_1",
        symbol="XAUUSD",
        side=PaperSide.LONG,
        quantity=2.0,
        entry_price=2_000.0,
        opened_at_utc=FIXED_NOW,
    )

    assert position.open_quantity == pytest.approx(2.0)
    assert position.unrealized_pnl(2_050.0) == pytest.approx(100.0)

    short = PaperPosition(
        position_id="p2",
        account_id="account_1",
        symbol="XAUUSD",
        side=PaperSide.SHORT,
        quantity=1.0,
        entry_price=2_000.0,
        opened_at_utc=FIXED_NOW,
    )

    assert short.unrealized_pnl(1_950.0) == pytest.approx(50.0)

    with pytest.raises(PaperTradingError, match="current_price must be positive"):
        position.unrealized_pnl(0.0)

    with pytest.raises(PaperTradingError, match="must carry a close time"):
        PaperPosition(
            position_id="p3",
            account_id="account_1",
            symbol="XAUUSD",
            side=PaperSide.LONG,
            quantity=1.0,
            entry_price=1.0,
            opened_at_utc=FIXED_NOW,
            status=PaperPositionStatus.CLOSED,
        )


def test_balance_validation_and_derivations() -> None:
    balance = PaperBalance(
        currency="USD",
        starting_balance=10_000.0,
        current_balance=10_500.0,
        equity=10_800.0,
        margin_used=300.0,
    )

    assert balance.realized_pnl == pytest.approx(500.0)
    assert balance.open_pnl == pytest.approx(300.0)
    assert balance.free_margin == pytest.approx(10_500.0)

    with pytest.raises(PaperTradingError, match="starting_balance must be positive"):
        PaperBalance(
            currency="USD",
            starting_balance=0.0,
            current_balance=0.0,
            equity=0.0,
        )


def test_account_state_validation() -> None:
    with pytest.raises(PaperTradingError, match="cannot be negative"):
        PaperAccountState(
            account_id="account_1",
            balance=PaperBalance(
                currency="USD",
                starting_balance=1.0,
                current_balance=1.0,
                equity=1.0,
            ),
            updated_at_utc=FIXED_NOW,
            open_position_count=-1,
        )


def test_execution_result_requires_a_reason_when_rejected() -> None:
    state = PaperAccountState(
        account_id="account_1",
        balance=PaperBalance(
            currency="USD",
            starting_balance=1.0,
            current_balance=1.0,
            equity=1.0,
        ),
        updated_at_utc=FIXED_NOW,
    )

    with pytest.raises(PaperTradingError, match="must carry a rejection reason"):
        PaperExecutionResult(
            accepted=False,
            request=build_request(),
            account_state=state,
        )

    with pytest.raises(PaperTradingError, match="must carry an order"):
        PaperExecutionResult(
            accepted=True,
            request=build_request(),
            account_state=state,
        )


def test_trade_converts_to_the_analytics_contract() -> None:
    """Sprint 048 is the first real producer of AccountTradeRecord."""

    trade = PaperTrade(
        trade_id="t1",
        position_id="p1",
        account_id="account_1",
        symbol="XAUUSD",
        side=PaperSide.LONG,
        quantity=1.0,
        entry_price=2_000.0,
        exit_price=2_100.0,
        opened_at_utc=FIXED_NOW,
        closed_at_utc=LATER,
        gross_pnl=100.0,
        commission=4.0,
        risk_amount=50.0,
        reward_amount=100.0,
        balance_after=10_096.0,
    )

    record = trade.to_account_trade_record()

    assert isinstance(record, AccountTradeRecord)
    assert record.trade_id == "t1"
    assert record.net_pnl == pytest.approx(96.0)
    assert record.closed_at_utc == LATER
    assert record.balance_after == pytest.approx(10_096.0)
    assert record.reward_to_risk == pytest.approx(2.0)
    assert trade.is_win is True


def test_trade_validation() -> None:
    base = {
        "trade_id": "t1",
        "position_id": "p1",
        "account_id": "account_1",
        "symbol": "XAUUSD",
        "side": PaperSide.LONG,
        "quantity": 1.0,
        "entry_price": 100.0,
        "exit_price": 110.0,
        "opened_at_utc": FIXED_NOW,
        "closed_at_utc": LATER,
        "gross_pnl": 10.0,
    }

    with pytest.raises(PaperTradingError, match="quantity must be positive"):
        PaperTrade(**{**base, "quantity": 0.0})

    with pytest.raises(PaperTradingError, match="prices must be positive"):
        PaperTrade(**{**base, "exit_price": 0.0})

    with pytest.raises(PaperTradingError, match="cannot be before opened_at_utc"):
        PaperTrade(**{**base, "closed_at_utc": datetime(2025, 1, 1)})


def test_validation_accepts_a_good_request() -> None:
    result = validate_paper_execution_request(build_request(), build_account())

    assert result.accepted is True
    assert result.to_dict()["rejection_reason"] is None


@pytest.mark.parametrize(
    ("request_overrides", "expected_reason"),
    [
        ({"quantity": 0.0}, PaperRejectionReason.INVALID_QUANTITY),
        ({"quantity": -1.0}, PaperRejectionReason.INVALID_QUANTITY),
        (
            {"order_type": PaperOrderType.LIMIT},
            PaperRejectionReason.MISSING_REQUIRED_FIELD,
        ),
        (
            {"requested_price": -1.0},
            PaperRejectionReason.INVALID_PRICE,
        ),
        (
            {"requested_price": 2_000.0, "stop_loss": 2_100.0},
            PaperRejectionReason.INVALID_PRICE,
        ),
        (
            {"requested_price": 2_000.0, "take_profit": 1_900.0},
            PaperRejectionReason.INVALID_PRICE,
        ),
        ({"account_id": "account_other"}, PaperRejectionReason.MISSING_REQUIRED_FIELD),
        ({"user_id": "user_other"}, PaperRejectionReason.MISSING_REQUIRED_FIELD),
    ],
)
def test_validation_rejects_unsafe_requests(
    request_overrides: dict,
    expected_reason: PaperRejectionReason,
) -> None:
    result = validate_paper_execution_request(
        build_request(**request_overrides),
        build_account(),
    )

    assert result.accepted is False
    assert result.rejection_reason == expected_reason


def test_validation_rejects_a_short_with_an_inverted_stop() -> None:
    result = validate_paper_execution_request(
        build_request(
            action=PaperAction.SELL,
            requested_price=2_000.0,
            stop_loss=1_900.0,
        ),
        build_account(),
    )

    assert result.accepted is False
    assert result.rejection_reason == PaperRejectionReason.INVALID_PRICE


@pytest.mark.parametrize(
    "status",
    [AccountStatus.DISABLED, AccountStatus.SUSPENDED, AccountStatus.ARCHIVED],
)
def test_validation_rejects_a_non_active_account(status: AccountStatus) -> None:
    result = validate_paper_account(build_account(status=status))

    assert result.accepted is False
    assert result.rejection_reason == PaperRejectionReason.ACCOUNT_NOT_ACTIVE


@pytest.mark.parametrize(
    "account_type",
    [AccountType.LIVE, AccountType.FUNDED, AccountType.DEMO],
)
def test_validation_rejects_a_non_paper_account(account_type: AccountType) -> None:
    """Simulated fills must never be booked against a real-money account."""

    result = validate_paper_account(
        build_account(account_type=account_type, broker=BrokerKind.MT5)
    )

    assert result.accepted is False
    assert result.rejection_reason == PaperRejectionReason.ACCOUNT_NOT_PAPER


def test_validation_result_requires_a_reason_when_rejecting() -> None:
    with pytest.raises(ValueError, match="must carry a reason"):
        PaperValidationResult(accepted=False)


def test_in_memory_broker_satisfies_the_protocol() -> None:
    broker = build_broker()

    assert isinstance(broker, PaperBroker)

    for method in (
        "get_account_state",
        "submit_order",
        "cancel_order",
        "list_open_positions",
        "list_orders",
        "list_fills",
        "list_trades",
    ):
        assert callable(getattr(broker, method)), method
        assert inspect.signature(getattr(broker, method)) is not None


def test_broker_starts_flat() -> None:
    state = build_broker().get_account_state()

    assert state.open_position_count == 0
    assert state.open_order_count == 0
    assert state.closed_trade_count == 0
    assert state.balance.current_balance == pytest.approx(10_000.0)


def test_broker_accepts_and_books_an_order() -> None:
    broker = build_broker()

    result = broker.submit_order(build_request())

    assert result.accepted is True
    assert result.order is not None
    assert result.order.status == PaperOrderStatus.ACCEPTED
    assert broker.get_account_state().open_order_count == 1
    assert len(broker.list_orders()) == 1


def test_broker_rejects_an_invalid_request_without_booking_it() -> None:
    broker = build_broker()

    result = broker.submit_order(build_request(quantity=0.0))

    assert result.accepted is False
    assert result.rejection_reason == PaperRejectionReason.INVALID_QUANTITY
    assert result.order is None
    assert broker.list_orders() == ()

    with pytest.raises(PaperTradingError, match="Paper execution rejected"):
        result.raise_if_rejected()


def test_broker_rejects_a_close_without_an_open_position() -> None:
    broker = build_broker()

    result = broker.submit_order(build_request(action=PaperAction.CLOSE))

    assert result.accepted is False
    assert result.rejection_reason == PaperRejectionReason.NO_OPEN_POSITION


def test_broker_fills_an_order_and_opens_a_position() -> None:
    broker = build_broker()
    order_id = broker.submit_order(build_request()).order.order_id

    result = broker.fill_order(order_id, price=2_000.0, filled_at_utc=FIXED_NOW)

    assert result.order.status == PaperOrderStatus.FILLED
    assert result.order.average_fill_price == pytest.approx(2_000.0)
    assert result.position is not None
    assert result.position.side == PaperSide.LONG
    assert len(broker.list_open_positions()) == 1
    assert len(broker.list_fills()) == 1


def test_broker_supports_a_partial_fill() -> None:
    broker = build_broker()
    order_id = broker.submit_order(build_request(quantity=2.0)).order.order_id

    first = broker.fill_order(
        order_id,
        price=2_000.0,
        quantity=1.0,
        filled_at_utc=FIXED_NOW,
    )

    assert first.order.status == PaperOrderStatus.PARTIALLY_FILLED
    assert first.order.remaining_quantity == pytest.approx(1.0)

    second = broker.fill_order(
        order_id,
        price=2_010.0,
        quantity=1.0,
        filled_at_utc=LATER,
    )

    assert second.order.status == PaperOrderStatus.FILLED
    assert second.order.average_fill_price == pytest.approx(2_005.0)


def test_broker_refuses_to_overfill() -> None:
    broker = build_broker()
    order_id = broker.submit_order(build_request()).order.order_id

    with pytest.raises(PaperTradingError, match="cannot exceed the remaining"):
        broker.fill_order(order_id, price=2_000.0, quantity=5.0)


def test_broker_refuses_to_fill_a_terminal_order() -> None:
    broker = build_broker()
    order_id = broker.submit_order(build_request()).order.order_id
    broker.fill_order(order_id, price=2_000.0)

    with pytest.raises(PaperTradingError, match="already filled"):
        broker.fill_order(order_id, price=2_000.0)


def test_broker_cancels_an_order() -> None:
    broker = build_broker()
    order_id = broker.submit_order(build_request()).order.order_id

    result = broker.cancel_order(order_id)

    assert result.order.status == PaperOrderStatus.CANCELLED
    assert broker.get_account_state().open_order_count == 0


def test_broker_rejects_cancelling_an_unknown_order() -> None:
    with pytest.raises(PaperTradingError, match="does not exist"):
        build_broker().cancel_order("missing")


def test_full_round_trip_produces_a_trade_and_moves_the_balance() -> None:
    broker = build_broker()

    open_order = broker.submit_order(build_request()).order
    broker.fill_order(open_order.order_id, price=2_000.0, filled_at_utc=FIXED_NOW)

    close_order = broker.submit_order(
        build_request(action=PaperAction.CLOSE, submitted_at_utc=LATER)
    ).order
    result = broker.fill_order(
        close_order.order_id,
        price=2_100.0,
        filled_at_utc=LATER,
        commission=4.0,
    )

    assert result.trade is not None
    assert result.trade.gross_pnl == pytest.approx(100.0)
    assert result.trade.net_pnl == pytest.approx(96.0)
    assert result.position.status == PaperPositionStatus.CLOSED
    assert broker.list_open_positions() == ()

    state = broker.get_account_state()

    assert state.balance.current_balance == pytest.approx(10_096.0)
    assert state.closed_trade_count == 1


def test_short_round_trip_profits_when_price_falls() -> None:
    broker = build_broker()

    open_order = broker.submit_order(build_request(action=PaperAction.SELL)).order
    broker.fill_order(open_order.order_id, price=2_000.0, filled_at_utc=FIXED_NOW)

    close_order = broker.submit_order(
        build_request(action=PaperAction.CLOSE, submitted_at_utc=LATER)
    ).order
    result = broker.fill_order(
        close_order.order_id,
        price=1_950.0,
        filled_at_utc=LATER,
    )

    assert result.trade.gross_pnl == pytest.approx(50.0)


def test_broker_trades_feed_the_analytics_engine() -> None:
    """The whole point of the sprint: real trades, no invented numbers."""

    broker = build_broker()

    for index, (entry, exit_price) in enumerate(
        [(2_000.0, 2_100.0), (2_100.0, 2_050.0)]
    ):
        opened_at = datetime(2026, 1, index + 1)
        closed_at = datetime(2026, 1, index + 1, 12)

        open_order = broker.submit_order(
            build_request(submitted_at_utc=opened_at)
        ).order
        broker.fill_order(open_order.order_id, price=entry, filled_at_utc=opened_at)

        close_order = broker.submit_order(
            build_request(action=PaperAction.CLOSE, submitted_at_utc=closed_at)
        ).order
        broker.fill_order(
            close_order.order_id,
            price=exit_price,
            filled_at_utc=closed_at,
        )

    records = [trade.to_account_trade_record() for trade in broker.list_trades()]
    metrics = calculate_trade_metrics(records, starting_balance=10_000.0)

    assert metrics.is_available is True
    assert metrics.total_trades == 2
    assert metrics.winning_trades == 1
    assert metrics.losing_trades == 1
    assert metrics.win_rate == pytest.approx(0.5)
    assert metrics.net_pnl == pytest.approx(50.0)
    assert metrics.ending_balance == pytest.approx(10_050.0)


def test_broker_refuses_a_non_paper_account_at_submission() -> None:
    broker = InMemoryPaperBroker(
        account=build_account(
            account_type=AccountType.LIVE,
            broker=BrokerKind.MT5,
        )
    )

    result = broker.submit_order(build_request())

    assert result.accepted is False
    assert result.rejection_reason == PaperRejectionReason.ACCOUNT_NOT_PAPER
    assert broker.list_orders() == ()


def test_broker_requires_a_positive_starting_balance() -> None:
    with pytest.raises(PaperTradingError, match="starting_balance must be positive"):
        InMemoryPaperBroker(account=build_account(), starting_balance=0.0)
