from __future__ import annotations

import pytest

from aqos.persistence.accounts import (
    AccountType,
    BrokerKind,
    TradingAccountRepository,
)
from aqos.persistence.database import AqosDatabase
from aqos.persistence.signals import (
    AQOS_SIGNALS_VERSION,
    SIGNAL_TRANSITIONS,
    SignalAction,
    SignalEvent,
    SignalSource,
    SignalStatus,
    TERMINAL_SIGNAL_STATUSES,
    TradingSignal,
    TradingSignalRepository,
    can_transition_signal,
    is_terminal_signal_status,
    validate_signal_transition,
)
from aqos.persistence.users import UserProfileRepository


@pytest.fixture
def signal_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def stored_user(signal_database):
    return UserProfileRepository(signal_database).create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def stored_account(signal_database, stored_user):
    return TradingAccountRepository(signal_database).create_account(
        user_id=stored_user.user_id,
        name="Paper One",
        account_type=AccountType.PAPER,
        broker=BrokerKind.PAPER,
        initial_balance=10_000.0,
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def signals(signal_database) -> TradingSignalRepository:
    return TradingSignalRepository(signal_database)


def build_signal(**overrides) -> TradingSignal:
    payload = {
        "signal_id": "signal_1",
        "user_id": "user_1",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "action": SignalAction.BUY,
        "source": SignalSource.RULE_STRATEGY,
        "status": SignalStatus.GENERATED,
        "generated_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)

    return TradingSignal(**payload)


def create_signal(signals: TradingSignalRepository, user_id: str, **overrides):
    payload = {
        "user_id": user_id,
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "action": SignalAction.BUY,
        "source": SignalSource.RULE_STRATEGY,
        "generated_at_utc": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)

    return signals.create_signal(**payload)


def test_signals_version_is_exposed() -> None:
    assert AQOS_SIGNALS_VERSION == "1.0"


def test_terminal_statuses_have_no_transitions() -> None:
    for status in TERMINAL_SIGNAL_STATUSES:
        assert is_terminal_signal_status(status) is True
        assert SIGNAL_TRANSITIONS[status] == ()


def test_every_status_is_covered_by_the_transition_table() -> None:
    assert set(SIGNAL_TRANSITIONS) == set(SignalStatus)


def test_can_transition_signal() -> None:
    assert can_transition_signal(SignalStatus.GENERATED, SignalStatus.APPROVED) is True
    assert can_transition_signal(
        SignalStatus.PENDING_APPROVAL,
        SignalStatus.EXECUTED,
    ) is False
    assert can_transition_signal(SignalStatus.EXECUTED, SignalStatus.FAILED) is False


def test_validate_signal_transition_raises() -> None:
    validate_signal_transition(SignalStatus.APPROVED, SignalStatus.EXECUTED)

    with pytest.raises(ValueError, match="cannot move from executed to failed"):
        validate_signal_transition(SignalStatus.EXECUTED, SignalStatus.FAILED)


def test_signal_validation_rejects_bad_identity() -> None:
    with pytest.raises(ValueError, match="signal_id cannot be empty"):
        build_signal(signal_id=" ")

    with pytest.raises(ValueError, match="user_id cannot be empty"):
        build_signal(user_id="")

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        build_signal(symbol="  ")

    with pytest.raises(ValueError, match="upper case"):
        build_signal(symbol="xauusd")

    with pytest.raises(ValueError, match="timeframe cannot be empty"):
        build_signal(timeframe=" ")

    with pytest.raises(ValueError, match="generated_at_utc cannot be empty"):
        build_signal(generated_at_utc=" ")

    with pytest.raises(ValueError, match="updated_at_utc cannot be empty"):
        build_signal(updated_at_utc=" ")


def test_signal_validation_rejects_bad_numbers() -> None:
    with pytest.raises(ValueError, match="confidence must be between"):
        build_signal(confidence=1.4)

    with pytest.raises(ValueError, match="entry_price must be positive"):
        build_signal(entry_price=0.0)

    with pytest.raises(ValueError, match="stop_loss must be positive"):
        build_signal(stop_loss=-1.0)

    with pytest.raises(ValueError, match="take_profit must be positive"):
        build_signal(take_profit=0.0)


def test_signal_expiry_must_follow_generation() -> None:
    with pytest.raises(ValueError, match="expires_at_utc must be after"):
        build_signal(expires_at_utc="2025-12-31T00:00:00Z")


def test_model_signals_require_model_id() -> None:
    with pytest.raises(ValueError, match="model_id is required"):
        build_signal(source=SignalSource.ML_MODEL)

    signal = build_signal(source=SignalSource.ML_MODEL, model_id="model_abc")

    assert signal.model_id == "model_abc"


def test_signal_state_helpers() -> None:
    generated = build_signal()

    assert generated.is_terminal is False
    assert generated.is_actionable is True
    assert generated.reached_market is False

    executed = build_signal(status=SignalStatus.EXECUTED)

    assert executed.is_terminal is True
    assert executed.is_actionable is False
    assert executed.reached_market is True


def test_signal_expiry_check() -> None:
    signal = build_signal(expires_at_utc="2026-01-01T01:00:00Z")

    assert signal.is_expired("2026-01-01T00:30:00Z") is False
    assert signal.is_expired("2026-01-01T02:00:00Z") is True
    assert build_signal().is_expired("2030-01-01T00:00:00Z") is False


def test_signal_dict_payload() -> None:
    payload = build_signal(confidence=0.8, entry_price=2300.0).to_dict()

    assert payload["action"] == "buy"
    assert payload["source"] == "rule_strategy"
    assert payload["status"] == "generated"
    assert payload["confidence"] == 0.8
    assert payload["is_actionable"] is True


def test_signal_event_validation() -> None:
    valid = {
        "event_id": "event_1",
        "signal_id": "signal_1",
        "from_status": SignalStatus.GENERATED,
        "to_status": SignalStatus.APPROVED,
        "occurred_at_utc": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(ValueError, match="event_id cannot be empty"):
        SignalEvent(**{**valid, "event_id": " "})

    with pytest.raises(ValueError, match="signal_id cannot be empty"):
        SignalEvent(**{**valid, "signal_id": ""})

    with pytest.raises(ValueError, match="occurred_at_utc cannot be empty"):
        SignalEvent(**{**valid, "occurred_at_utc": " "})

    event = SignalEvent(**valid)

    assert event.to_dict()["from_status"] == "generated"


def test_create_signal_persists_and_logs(signals, stored_user) -> None:
    signal = create_signal(
        signals,
        stored_user.user_id,
        symbol=" xau usd ",
        confidence=0.72,
        entry_price=2300.0,
        stop_loss=2290.0,
        take_profit=2320.0,
        source_ref="close_momentum",
    )

    assert signal.signal_id.startswith("signal_")
    assert signal.symbol == "XAUUSD"
    assert signal.status == SignalStatus.GENERATED

    stored = signals.require_signal(signal.signal_id)

    assert stored.to_dict() == signal.to_dict()

    events = signals.list_events(signal.signal_id)

    assert len(events) == 1
    assert events[0].from_status is None
    assert events[0].to_status == SignalStatus.GENERATED


def test_create_signal_with_account(signals, stored_user, stored_account) -> None:
    signal = create_signal(
        signals,
        stored_user.user_id,
        account_id=stored_account.account_id,
    )

    assert signal.account_id == stored_account.account_id


def test_create_signal_rejects_terminal_start_status(signals, stored_user) -> None:
    with pytest.raises(ValueError, match="cannot be created as executed"):
        create_signal(signals, stored_user.user_id, status=SignalStatus.EXECUTED)


def test_create_signal_can_start_pending_approval(signals, stored_user) -> None:
    signal = create_signal(
        signals,
        stored_user.user_id,
        status=SignalStatus.PENDING_APPROVAL,
    )

    assert signal.status == SignalStatus.PENDING_APPROVAL


def test_get_signal_returns_none_when_missing(signals) -> None:
    assert signals.get_signal("signal_missing") is None


def test_require_signal_raises_when_missing(signals) -> None:
    with pytest.raises(LookupError, match="does not exist"):
        signals.require_signal("signal_missing")


def test_approve_then_execute_flow(signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    pending = signals.mark_pending_approval(
        signal.signal_id,
        actor="system",
        occurred_at_utc="2026-01-01T00:01:00Z",
    )
    approved = signals.approve_signal(
        signal.signal_id,
        reason="Approved by trader.",
        actor="user",
        occurred_at_utc="2026-01-01T00:02:00Z",
    )
    executed = signals.mark_executed(
        signal.signal_id,
        actor="paper_broker",
        occurred_at_utc="2026-01-01T00:03:00Z",
    )

    assert pending.status == SignalStatus.PENDING_APPROVAL
    assert approved.status == SignalStatus.APPROVED
    assert approved.status_reason == "Approved by trader."
    assert executed.status == SignalStatus.EXECUTED
    assert executed.updated_at_utc == "2026-01-01T00:03:00Z"

    events = signals.list_events(signal.signal_id)

    assert [event.to_status.value for event in events] == [
        "generated",
        "pending_approval",
        "approved",
        "executed",
    ]
    assert events[-1].actor == "paper_broker"


def test_reject_signal_requires_reason(signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    with pytest.raises(ValueError, match="reason cannot be empty"):
        signals.reject_signal(signal.signal_id, reason="  ")

    rejected = signals.reject_signal(
        signal.signal_id,
        reason="Risk limit reached.",
        actor="risk_engine",
    )

    assert rejected.status == SignalStatus.REJECTED
    assert rejected.status_reason == "Risk limit reached."
    assert rejected.is_terminal is True


def test_mark_missed_and_failed(signals, stored_user) -> None:
    missed_signal = create_signal(signals, stored_user.user_id)
    missed = signals.mark_missed(missed_signal.signal_id, reason="Spread too wide.")

    assert missed.status == SignalStatus.MISSED

    failing_signal = create_signal(signals, stored_user.user_id, symbol="EURUSD")
    signals.approve_signal(failing_signal.signal_id)
    failed = signals.mark_failed(
        failing_signal.signal_id,
        reason="Broker disconnected.",
    )

    assert failed.status == SignalStatus.FAILED
    assert failed.status_reason == "Broker disconnected."


def test_cancel_signal(signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    cancelled = signals.cancel_signal(signal.signal_id, reason="Superseded.")

    assert cancelled.status == SignalStatus.CANCELLED


def test_invalid_transition_is_rejected(signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)
    signals.mark_executed(
        signals.approve_signal(signal.signal_id).signal_id,
    )

    with pytest.raises(ValueError, match="cannot move from executed"):
        signals.mark_failed(signal.signal_id, reason="Too late.")


def test_generated_signal_cannot_jump_to_executed(signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    with pytest.raises(ValueError, match="cannot move from generated to executed"):
        signals.mark_executed(signal.signal_id)


def test_list_signals_filters(signals, stored_user, stored_account) -> None:
    create_signal(
        signals,
        stored_user.user_id,
        symbol="XAUUSD",
        generated_at_utc="2026-01-01T00:00:00Z",
    )
    create_signal(
        signals,
        stored_user.user_id,
        symbol="EURUSD",
        account_id=stored_account.account_id,
        source=SignalSource.ML_MODEL,
        model_id="model_abc",
        generated_at_utc="2026-01-02T00:00:00Z",
    )
    rejected = create_signal(
        signals,
        stored_user.user_id,
        symbol="BTCUSD",
        generated_at_utc="2026-01-03T00:00:00Z",
    )
    signals.reject_signal(rejected.signal_id, reason="Blocked symbol.")

    assert len(signals.list_signals(user_id=stored_user.user_id)) == 3
    assert len(signals.list_signals(symbol="eurusd")) == 1
    assert len(signals.list_signals(account_id=stored_account.account_id)) == 1
    assert len(signals.list_signals(source=SignalSource.ML_MODEL)) == 1
    assert len(signals.list_signals(status=SignalStatus.REJECTED)) == 1
    assert len(signals.list_signals(generated_since_utc="2026-01-02T00:00:00Z")) == 2
    assert len(signals.list_signals(limit=2)) == 2


def test_list_signals_is_ordered_by_generation_time(signals, stored_user) -> None:
    create_signal(
        signals,
        stored_user.user_id,
        symbol="BTCUSD",
        generated_at_utc="2026-01-03T00:00:00Z",
    )
    create_signal(
        signals,
        stored_user.user_id,
        symbol="XAUUSD",
        generated_at_utc="2026-01-01T00:00:00Z",
    )

    assert [signal.symbol for signal in signals.list_signals()] == [
        "XAUUSD",
        "BTCUSD",
    ]


def test_count_signals_by_status(signals, stored_user) -> None:
    first = create_signal(signals, stored_user.user_id, symbol="XAUUSD")
    create_signal(signals, stored_user.user_id, symbol="EURUSD")
    signals.reject_signal(first.signal_id, reason="Risk.")

    counts = signals.count_signals_by_status(user_id=stored_user.user_id)

    assert counts == {"generated": 1, "rejected": 1}


def test_expire_due_signals(signals, stored_user) -> None:
    expiring = create_signal(
        signals,
        stored_user.user_id,
        symbol="XAUUSD",
        generated_at_utc="2026-01-01T00:00:00Z",
        expires_at_utc="2026-01-01T00:30:00Z",
    )
    still_valid = create_signal(
        signals,
        stored_user.user_id,
        symbol="EURUSD",
        generated_at_utc="2026-01-01T00:00:00Z",
        expires_at_utc="2026-01-01T06:00:00Z",
    )
    no_expiry = create_signal(signals, stored_user.user_id, symbol="BTCUSD")

    expired = signals.expire_due_signals(now_utc="2026-01-01T01:00:00Z")

    assert [signal.signal_id for signal in expired] == [expiring.signal_id]
    assert signals.require_signal(expiring.signal_id).status == SignalStatus.EXPIRED
    assert signals.require_signal(still_valid.signal_id).status == (
        SignalStatus.GENERATED
    )
    assert signals.require_signal(no_expiry.signal_id).status == SignalStatus.GENERATED


def test_expire_due_signals_skips_terminal_signals(signals, stored_user) -> None:
    signal = create_signal(
        signals,
        stored_user.user_id,
        generated_at_utc="2026-01-01T00:00:00Z",
        expires_at_utc="2026-01-01T00:30:00Z",
    )
    signals.reject_signal(signal.signal_id, reason="Risk.")

    assert signals.expire_due_signals(now_utc="2026-01-01T02:00:00Z") == ()
    assert signals.require_signal(signal.signal_id).status == SignalStatus.REJECTED


def test_delete_signal_removes_events(signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)
    signals.approve_signal(signal.signal_id)

    assert signals.delete_signal(signal.signal_id) is True
    assert signals.get_signal(signal.signal_id) is None
    assert signals.list_events(signal.signal_id) == ()
    assert signals.delete_signal(signal.signal_id) is False


def test_deleting_user_cascades_to_signals(
    signal_database,
    signals,
    stored_user,
) -> None:
    create_signal(signals, stored_user.user_id)

    UserProfileRepository(signal_database).delete_user(stored_user.user_id)

    assert signals.list_signals(user_id=stored_user.user_id) == ()


def test_deleting_account_detaches_signals(
    signal_database,
    signals,
    stored_user,
    stored_account,
) -> None:
    signal = create_signal(
        signals,
        stored_user.user_id,
        account_id=stored_account.account_id,
    )

    TradingAccountRepository(signal_database).delete_account(stored_account.account_id)

    assert signals.require_signal(signal.signal_id).account_id is None
