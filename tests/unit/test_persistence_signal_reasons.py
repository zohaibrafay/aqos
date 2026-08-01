from __future__ import annotations

import pytest

from aqos.persistence.accounts import (
    AccountType,
    BrokerKind,
    TradingAccountRepository,
)
from aqos.persistence.database import AqosDatabase
from aqos.persistence.signal_reasons import (
    AQOS_SIGNAL_REASONS_VERSION,
    SIGNAL_REASON_CATEGORIES,
    SignalOutcome,
    SignalOutcomeRepository,
    SignalReasonCategory,
    SignalReasonCode,
    default_reason_message,
    fail_signal_with_reason,
    miss_signal_with_reason,
    reject_signal_with_reason,
    resolve_reason_category,
    validate_reason_outcome_status,
)
from aqos.persistence.signals import (
    SignalAction,
    SignalSource,
    SignalStatus,
    TradingSignalRepository,
)
from aqos.persistence.users import UserProfileRepository


@pytest.fixture
def reason_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def stored_user(reason_database):
    return UserProfileRepository(reason_database).create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def stored_account(reason_database, stored_user):
    return TradingAccountRepository(reason_database).create_account(
        user_id=stored_user.user_id,
        name="Paper One",
        account_type=AccountType.PAPER,
        broker=BrokerKind.PAPER,
        initial_balance=10_000.0,
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def signals(reason_database) -> TradingSignalRepository:
    return TradingSignalRepository(reason_database)


@pytest.fixture
def outcomes(reason_database) -> SignalOutcomeRepository:
    return SignalOutcomeRepository(reason_database)


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


def test_signal_reasons_version_is_exposed() -> None:
    assert AQOS_SIGNAL_REASONS_VERSION == "1.0"


def test_every_reason_code_has_a_category() -> None:
    assert set(SIGNAL_REASON_CATEGORIES) == set(SignalReasonCode)


def test_every_reason_code_has_a_default_message() -> None:
    for reason_code in SignalReasonCode:
        assert default_reason_message(reason_code).strip()


def test_resolve_reason_category() -> None:
    assert resolve_reason_category(SignalReasonCode.SPREAD_TOO_WIDE) == (
        SignalReasonCategory.MARKET
    )
    assert resolve_reason_category(SignalReasonCode.FUNDED_RULE) == (
        SignalReasonCategory.ACCOUNT
    )
    assert resolve_reason_category(SignalReasonCode.LOW_CONFIDENCE) == (
        SignalReasonCategory.MODEL
    )
    assert resolve_reason_category(SignalReasonCode.BROKER_DISCONNECTED) == (
        SignalReasonCategory.BROKER
    )


def test_validate_reason_outcome_status() -> None:
    validate_reason_outcome_status(SignalStatus.REJECTED)
    validate_reason_outcome_status(SignalStatus.MISSED)

    with pytest.raises(ValueError, match="cannot be recorded for status: executed"):
        validate_reason_outcome_status(SignalStatus.EXECUTED)


def test_outcome_validation() -> None:
    valid = {
        "outcome_id": "outcome_1",
        "signal_id": "signal_1",
        "status": SignalStatus.REJECTED,
        "reason_code": SignalReasonCode.RISK_LIMIT_REACHED,
        "category": SignalReasonCategory.RISK,
        "occurred_at_utc": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(ValueError, match="outcome_id cannot be empty"):
        SignalOutcome(**{**valid, "outcome_id": " "})

    with pytest.raises(ValueError, match="signal_id cannot be empty"):
        SignalOutcome(**{**valid, "signal_id": ""})

    with pytest.raises(ValueError, match="occurred_at_utc cannot be empty"):
        SignalOutcome(**{**valid, "occurred_at_utc": " "})

    with pytest.raises(ValueError, match="does not match the reason code category"):
        SignalOutcome(**{**valid, "category": SignalReasonCategory.BROKER})

    with pytest.raises(ValueError, match="cannot be recorded for status"):
        SignalOutcome(**{**valid, "status": SignalStatus.APPROVED})


def test_outcome_message_falls_back_to_default() -> None:
    outcome = SignalOutcome(
        outcome_id="outcome_1",
        signal_id="signal_1",
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.SPREAD_TOO_WIDE,
        category=SignalReasonCategory.MARKET,
        occurred_at_utc="2026-01-01T00:00:00Z",
    )

    assert outcome.message == default_reason_message(SignalReasonCode.SPREAD_TOO_WIDE)
    assert outcome.to_dict()["detail"] is None

    with_detail = SignalOutcome(
        outcome_id="outcome_2",
        signal_id="signal_1",
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.SPREAD_TOO_WIDE,
        category=SignalReasonCategory.MARKET,
        occurred_at_utc="2026-01-01T00:00:00Z",
        detail="Spread was 42 points.",
    )

    assert with_detail.message == "Spread was 42 points."


def test_record_outcome_persists(outcomes, signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    outcome = outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.LATE_SIGNAL,
        detail="Signal arrived 90 seconds late.",
        actor="execution_engine",
        occurred_at_utc="2026-01-01T00:05:00Z",
    )

    assert outcome.outcome_id.startswith("signaloutcome_")
    assert outcome.category == SignalReasonCategory.WORKFLOW

    stored = outcomes.get_outcome(outcome.outcome_id)

    assert stored is not None
    assert stored.to_dict() == outcome.to_dict()


def test_get_outcome_returns_none_when_missing(outcomes) -> None:
    assert outcomes.get_outcome("outcome_missing") is None


def test_reject_signal_with_reason_updates_both_stores(
    signals,
    outcomes,
    stored_user,
    stored_account,
) -> None:
    signal = create_signal(
        signals,
        stored_user.user_id,
        account_id=stored_account.account_id,
    )

    rejected, outcome = reject_signal_with_reason(
        signals=signals,
        outcomes=outcomes,
        signal_id=signal.signal_id,
        reason_code=SignalReasonCode.FUNDED_RULE,
        detail="Daily loss limit already reached.",
        actor="risk_engine",
        occurred_at_utc="2026-01-01T00:10:00Z",
    )

    assert rejected.status == SignalStatus.REJECTED
    assert rejected.status_reason == "Daily loss limit already reached."
    assert outcome.status == SignalStatus.REJECTED
    assert outcome.reason_code == SignalReasonCode.FUNDED_RULE
    assert outcome.account_id == stored_account.account_id
    assert outcome.occurred_at_utc == "2026-01-01T00:10:00Z"


def test_reject_signal_with_reason_uses_default_message(
    signals,
    outcomes,
    stored_user,
) -> None:
    signal = create_signal(signals, stored_user.user_id)

    rejected, outcome = reject_signal_with_reason(
        signals=signals,
        outcomes=outcomes,
        signal_id=signal.signal_id,
        reason_code=SignalReasonCode.SYMBOL_BLOCKED,
    )

    assert rejected.status_reason == default_reason_message(
        SignalReasonCode.SYMBOL_BLOCKED
    )
    assert outcome.detail is None


def test_miss_signal_with_reason(signals, outcomes, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    missed, outcome = miss_signal_with_reason(
        signals=signals,
        outcomes=outcomes,
        signal_id=signal.signal_id,
        reason_code=SignalReasonCode.SPREAD_TOO_WIDE,
        detail="Spread 45 points against a 20 point limit.",
    )

    assert missed.status == SignalStatus.MISSED
    assert outcome.status == SignalStatus.MISSED
    assert outcome.category == SignalReasonCategory.MARKET


def test_fail_signal_with_reason(signals, outcomes, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)
    signals.approve_signal(signal.signal_id)

    failed, outcome = fail_signal_with_reason(
        signals=signals,
        outcomes=outcomes,
        signal_id=signal.signal_id,
        reason_code=SignalReasonCode.BROKER_DISCONNECTED,
    )

    assert failed.status == SignalStatus.FAILED
    assert outcome.category == SignalReasonCategory.BROKER


def test_same_signal_can_have_per_account_outcomes(
    reason_database,
    signals,
    outcomes,
    stored_user,
    stored_account,
) -> None:
    second_account = TradingAccountRepository(reason_database).create_account(
        user_id=stored_user.user_id,
        name="Funded 100k",
        account_type=AccountType.FUNDED,
        broker=BrokerKind.MT5,
        initial_balance=100_000.0,
    )

    signal = create_signal(signals, stored_user.user_id)

    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.REJECTED,
        reason_code=SignalReasonCode.FUNDED_RULE,
        account_id=second_account.account_id,
        occurred_at_utc="2026-01-01T00:05:00Z",
    )
    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.SPREAD_TOO_WIDE,
        account_id=stored_account.account_id,
        occurred_at_utc="2026-01-01T00:06:00Z",
    )

    assert len(outcomes.list_outcomes(signal_id=signal.signal_id)) == 2
    assert len(outcomes.list_outcomes(account_id=stored_account.account_id)) == 1
    assert outcomes.list_outcomes(account_id=second_account.account_id)[0].reason_code == (
        SignalReasonCode.FUNDED_RULE
    )


def test_list_outcomes_filters(outcomes, signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.REJECTED,
        reason_code=SignalReasonCode.RISK_LIMIT_REACHED,
        occurred_at_utc="2026-01-01T00:01:00Z",
    )
    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.MARKET_CLOSED,
        occurred_at_utc="2026-01-02T00:01:00Z",
    )

    assert len(outcomes.list_outcomes(status=SignalStatus.MISSED)) == 1
    assert len(
        outcomes.list_outcomes(reason_code=SignalReasonCode.RISK_LIMIT_REACHED)
    ) == 1
    assert len(outcomes.list_outcomes(category=SignalReasonCategory.MARKET)) == 1
    assert len(
        outcomes.list_outcomes(occurred_since_utc="2026-01-02T00:00:00Z")
    ) == 1


def test_list_outcomes_is_ordered(outcomes, signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.LATE_SIGNAL,
        occurred_at_utc="2026-01-03T00:00:00Z",
    )
    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.SPREAD_TOO_WIDE,
        occurred_at_utc="2026-01-01T00:00:00Z",
    )

    listed = outcomes.list_outcomes()

    assert [outcome.reason_code for outcome in listed] == [
        SignalReasonCode.SPREAD_TOO_WIDE,
        SignalReasonCode.LATE_SIGNAL,
    ]


def test_summarize_reasons_ranks_by_count(outcomes, signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    for _ in range(3):
        outcomes.record_outcome(
            signal_id=signal.signal_id,
            status=SignalStatus.MISSED,
            reason_code=SignalReasonCode.SPREAD_TOO_WIDE,
            occurred_at_utc="2026-01-01T00:00:00Z",
        )

    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.REJECTED,
        reason_code=SignalReasonCode.RISK_LIMIT_REACHED,
        occurred_at_utc="2026-01-01T00:00:00Z",
    )

    summary = outcomes.summarize_reasons()

    assert summary.total == 4
    assert summary.top_reason is not None
    assert summary.top_reason.reason_code == SignalReasonCode.SPREAD_TOO_WIDE
    assert summary.top_reason.count == 3
    assert summary.by_category == {"market": 3, "risk": 1}
    assert summary.by_status == {"missed": 3, "rejected": 1}

    payload = summary.to_dict()

    assert payload["total"] == 4
    assert payload["top_reason"]["reason_code"] == "spread_too_wide"


def test_summarize_reasons_for_empty_store(outcomes) -> None:
    summary = outcomes.summarize_reasons()

    assert summary.total == 0
    assert summary.by_reason == ()
    assert summary.top_reason is None
    assert summary.by_category == {}


def test_summarize_reasons_filters_by_account(
    outcomes,
    signals,
    stored_user,
    stored_account,
) -> None:
    signal = create_signal(signals, stored_user.user_id)

    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.REJECTED,
        reason_code=SignalReasonCode.ACCOUNT_RULE,
        account_id=stored_account.account_id,
        occurred_at_utc="2026-01-01T00:00:00Z",
    )
    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.REJECTED,
        reason_code=SignalReasonCode.RISK_LIMIT_REACHED,
        occurred_at_utc="2026-01-01T00:00:00Z",
    )

    summary = outcomes.summarize_reasons(account_id=stored_account.account_id)

    assert summary.total == 1
    assert summary.by_reason[0].reason_code == SignalReasonCode.ACCOUNT_RULE


def test_delete_outcomes_for_signal(outcomes, signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.LATE_SIGNAL,
    )

    assert outcomes.delete_outcomes_for_signal(signal.signal_id) == 1
    assert outcomes.list_outcomes(signal_id=signal.signal_id) == ()


def test_deleting_signal_cascades_to_outcomes(outcomes, signals, stored_user) -> None:
    signal = create_signal(signals, stored_user.user_id)

    outcomes.record_outcome(
        signal_id=signal.signal_id,
        status=SignalStatus.MISSED,
        reason_code=SignalReasonCode.LATE_SIGNAL,
    )

    signals.delete_signal(signal.signal_id)

    assert outcomes.list_outcomes(signal_id=signal.signal_id) == ()
