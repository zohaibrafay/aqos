from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from aqos.signals.models import (
    AQOS_SIGNALS_VERSION,
    CREATABLE_SIGNAL_STATUSES,
    InvalidSignalTransitionError,
    OPEN_SIGNAL_STATUSES,
    SIGNAL_TRANSITIONS,
    SignalAction,
    SignalEvent,
    SignalSource,
    SignalStatus,
    TERMINAL_SIGNAL_STATUSES,
    TradingSignal,
    UNFILLED_SIGNAL_STATUSES,
    as_number,
    can_transition_signal,
    is_terminal_signal_status,
    normalize_signal_symbol,
    validate_signal_transition,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_signal(**overrides) -> TradingSignal:
    payload = {
        "signal_id": "signal_1",
        "user_id": "user_1",
        "symbol": "XAUUSD",
        "timeframe": "H1",
        "action": SignalAction.BUY,
        "source": SignalSource.MANUAL,
        "generated_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return TradingSignal(**payload)


def test_signals_version_is_exposed() -> None:
    assert AQOS_SIGNALS_VERSION == "1.0"


def test_all_required_statuses_exist() -> None:
    assert {status.value for status in SignalStatus} == {
        "generated",
        "pending_approval",
        "approved",
        "rejected",
        "missed",
        "expired",
        "executed",
        "failed",
        "cancelled",
    }


def test_all_required_sources_exist() -> None:
    assert {source.value for source in SignalSource} == {
        "rule_based",
        "ml_model",
        "manual",
        "backtest",
        "paper_trading",
        "external_webhook",
    }


def test_every_status_is_covered_by_the_transition_table() -> None:
    assert set(SIGNAL_TRANSITIONS) == set(SignalStatus)


def test_terminal_statuses_have_no_transitions() -> None:
    for status in TERMINAL_SIGNAL_STATUSES:
        assert is_terminal_signal_status(status) is True
        assert SIGNAL_TRANSITIONS[status] == ()


def test_open_and_terminal_statuses_partition_the_lifecycle() -> None:
    assert set(OPEN_SIGNAL_STATUSES) | set(TERMINAL_SIGNAL_STATUSES) == set(
        SignalStatus
    )
    assert set(OPEN_SIGNAL_STATUSES) & set(TERMINAL_SIGNAL_STATUSES) == set()


def test_unfilled_statuses_exclude_executed() -> None:
    assert SignalStatus.EXECUTED not in UNFILLED_SIGNAL_STATUSES
    assert set(UNFILLED_SIGNAL_STATUSES) < set(TERMINAL_SIGNAL_STATUSES)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (SignalStatus.GENERATED, SignalStatus.APPROVED),
        (SignalStatus.GENERATED, SignalStatus.REJECTED),
        (SignalStatus.GENERATED, SignalStatus.MISSED),
        (SignalStatus.GENERATED, SignalStatus.PENDING_APPROVAL),
        (SignalStatus.GENERATED, SignalStatus.EXPIRED),
        (SignalStatus.PENDING_APPROVAL, SignalStatus.APPROVED),
        (SignalStatus.PENDING_APPROVAL, SignalStatus.REJECTED),
        (SignalStatus.APPROVED, SignalStatus.EXECUTED),
        (SignalStatus.APPROVED, SignalStatus.EXPIRED),
        (SignalStatus.APPROVED, SignalStatus.FAILED),
    ],
)
def test_allowed_transitions(
    from_status: SignalStatus,
    to_status: SignalStatus,
) -> None:
    assert can_transition_signal(from_status, to_status) is True

    validate_signal_transition(from_status, to_status)


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        (SignalStatus.REJECTED, SignalStatus.EXECUTED),
        (SignalStatus.EXPIRED, SignalStatus.EXECUTED),
        (SignalStatus.FAILED, SignalStatus.EXECUTED),
        (SignalStatus.MISSED, SignalStatus.EXECUTED),
        (SignalStatus.CANCELLED, SignalStatus.EXECUTED),
        (SignalStatus.EXECUTED, SignalStatus.FAILED),
        (SignalStatus.GENERATED, SignalStatus.EXECUTED),
        (SignalStatus.PENDING_APPROVAL, SignalStatus.EXECUTED),
    ],
)
def test_forbidden_transitions(
    from_status: SignalStatus,
    to_status: SignalStatus,
) -> None:
    assert can_transition_signal(from_status, to_status) is False

    with pytest.raises(
        InvalidSignalTransitionError,
        match=f"cannot move from {from_status.value} to {to_status.value}",
    ):
        validate_signal_transition(from_status, to_status)


def test_execution_is_only_reachable_from_approved() -> None:
    """A signal must pass approval before it can ever be executed."""

    sources = [
        status
        for status, targets in SIGNAL_TRANSITIONS.items()
        if SignalStatus.EXECUTED in targets
    ]

    assert sources == [SignalStatus.APPROVED]


def test_invalid_transition_error_is_a_value_error() -> None:
    assert issubclass(InvalidSignalTransitionError, ValueError)


def test_creatable_statuses_are_limited() -> None:
    assert set(CREATABLE_SIGNAL_STATUSES) == {
        SignalStatus.GENERATED,
        SignalStatus.PENDING_APPROVAL,
    }


def test_normalize_signal_symbol() -> None:
    assert normalize_signal_symbol(" xau usd ") == "XAUUSD"

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        normalize_signal_symbol("   ")


def test_as_number_handles_decimal() -> None:
    assert as_number(Decimal("0.750000")) == pytest.approx(0.75)
    assert as_number(1.5) == pytest.approx(1.5)


def test_transient_signal_carries_lifecycle_defaults() -> None:
    """
    SQLAlchemy defaults only apply at flush time.

    A signal built but not saved must still report a usable status, otherwise
    every lifecycle check misreads it.
    """

    signal = build_signal()

    assert signal.status == SignalStatus.GENERATED
    assert signal.extra_metadata == {}
    assert signal.is_open is True

    signal.assert_no_unset_lifecycle_fields()


def test_unset_lifecycle_fields_are_rejected() -> None:
    signal = build_signal()
    signal.status = None

    with pytest.raises(ValueError, match="must never be unset"):
        signal.assert_no_unset_lifecycle_fields()

    with pytest.raises(ValueError, match="must never be unset"):
        signal.validate_traceability()


def test_signal_validates_symbol_and_timeframe() -> None:
    assert build_signal(symbol=" xau usd ").symbol == "XAUUSD"

    with pytest.raises(ValueError, match="symbol cannot be empty"):
        build_signal(symbol="   ")

    with pytest.raises(ValueError, match="timeframe cannot be empty"):
        build_signal(timeframe="  ")


def test_signal_validates_confidence_and_prices() -> None:
    with pytest.raises(ValueError, match="confidence must be between"):
        build_signal(confidence=1.4)

    with pytest.raises(ValueError, match="entry_price must be positive"):
        build_signal(entry_price=0.0)

    with pytest.raises(ValueError, match="stop_loss must be positive"):
        build_signal(stop_loss=-1.0)

    with pytest.raises(ValueError, match="take_profit must be positive"):
        build_signal(take_profit=0.0)

    build_signal(confidence=0.0)
    build_signal(confidence=1.0)


def test_model_signals_require_a_model_id() -> None:
    with pytest.raises(ValueError, match="model_id is required"):
        build_signal(source=SignalSource.ML_MODEL).validate_traceability()

    build_signal(
        source=SignalSource.ML_MODEL,
        model_id="model_abc",
        model_version="v1",
    ).validate_traceability()


def test_rule_based_signals_require_a_strategy_name() -> None:
    with pytest.raises(ValueError, match="strategy_name is required"):
        build_signal(source=SignalSource.RULE_BASED).validate_traceability()

    build_signal(
        source=SignalSource.RULE_BASED,
        strategy_name="close_momentum",
    ).validate_traceability()


def test_expiry_must_follow_generation() -> None:
    with pytest.raises(ValueError, match="expires_at_utc must be after"):
        build_signal(expires_at_utc=datetime(2025, 12, 31)).validate_traceability()

    build_signal(expires_at_utc=datetime(2026, 1, 1, 1, 0, 0)).validate_traceability()


def test_signal_expiry_check() -> None:
    signal = build_signal(expires_at_utc=datetime(2026, 1, 1, 1, 0, 0))

    assert signal.is_expired(datetime(2026, 1, 1, 0, 30, 0)) is False
    assert signal.is_expired(datetime(2026, 1, 1, 2, 0, 0)) is True
    assert build_signal().is_expired(datetime(2030, 1, 1)) is False


def test_signal_state_helpers() -> None:
    generated = build_signal()

    assert generated.is_terminal is False
    assert generated.is_open is True
    assert generated.reached_market is False
    assert generated.can_transition_to(SignalStatus.APPROVED) is True

    executed = build_signal(status=SignalStatus.EXECUTED)

    assert executed.is_terminal is True
    assert executed.is_open is False
    assert executed.reached_market is True
    assert executed.allowed_transitions == ()
    assert executed.can_transition_to(SignalStatus.FAILED) is False


def test_signal_dict_payload() -> None:
    payload = build_signal(
        confidence=0.72,
        entry_price=2300.0,
        stop_loss=2290.0,
        take_profit=2320.0,
        source=SignalSource.RULE_BASED,
        strategy_name="close_momentum",
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
        extra_metadata={"origin": "unit_test"},
    ).to_dict()

    assert payload["action"] == "buy"
    assert payload["status"] == "generated"
    assert payload["source"] == "rule_based"
    assert payload["confidence"] == pytest.approx(0.72)
    assert payload["entry_price"] == pytest.approx(2300.0)
    assert payload["is_open"] is True
    assert "approved" in payload["allowed_transitions"]
    assert payload["metadata"] == {"origin": "unit_test"}
    assert "signal_1" in repr(build_signal())


def test_event_payload_and_creation_flag() -> None:
    creation = SignalEvent(
        event_id="event_1",
        signal_id="signal_1",
        from_status=None,
        to_status=SignalStatus.GENERATED,
        occurred_at_utc=FIXED_NOW,
        reason="Signal created.",
        actor="system",
    )

    assert creation.is_creation is True
    assert creation.extra_metadata == {}

    payload = creation.to_dict()

    assert payload["from_status"] is None
    assert payload["to_status"] == "generated"
    assert payload["actor"] == "system"
    assert payload["occurred_at_utc"] == "2026-01-01T00:00:00"

    transition = SignalEvent(
        event_id="event_2",
        signal_id="signal_1",
        from_status=SignalStatus.GENERATED,
        to_status=SignalStatus.APPROVED,
        occurred_at_utc=FIXED_NOW,
    )

    assert transition.is_creation is False
    assert "signal_1" in repr(transition)
