from __future__ import annotations

from datetime import datetime

import pytest

from aqos.signals.models import SignalStatus
from aqos.signal_reasons.models import (
    AQOS_SIGNAL_REASON_MODELS_VERSION,
    SignalReason,
    build_reason_message,
)
from aqos.signal_reasons.taxonomy import (
    AQOS_SIGNAL_REASON_TAXONOMY_VERSION,
    REASON_BEARING_STATUSES,
    REASON_DEFINITIONS,
    SEVERITY_RANK,
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonError,
    SignalReasonSeverity,
    allowed_statuses_for_code,
    codes_for_status,
    default_reason_message,
    require_reason_definition,
    resolve_minimum_severity,
    resolve_reason_category,
    severity_rank,
    validate_reason,
    validate_reason_category,
    validate_reason_severity,
    validate_reason_status,
)


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_reason(**overrides) -> SignalReason:
    payload = {
        "reason_id": "reason_1",
        "signal_id": "signal_1",
        "user_id": "user_1",
        "signal_status": SignalStatus.REJECTED,
        "reason_code": SignalReasonCode.RISK_LIMIT_EXCEEDED,
        "created_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return SignalReason(**payload)


def test_versions_are_exposed() -> None:
    assert AQOS_SIGNAL_REASON_TAXONOMY_VERSION == "1.0"
    assert AQOS_SIGNAL_REASON_MODELS_VERSION == "1.0"


def test_all_required_categories_exist() -> None:
    assert {item.value for item in SignalReasonCategory} == {
        "risk",
        "account_rule",
        "funded_rule",
        "execution_policy",
        "model_promotion",
        "market_condition",
        "signal_expiry",
        "user_action",
        "system_error",
        "broker_unavailable",
        "duplicate_signal",
        "validation_error",
    }


def test_all_required_severities_exist() -> None:
    assert {item.value for item in SignalReasonSeverity} == {
        "info",
        "warning",
        "blocking",
        "critical",
    }
    assert set(SEVERITY_RANK) == set(SignalReasonSeverity)


def test_severity_rank_is_ordered() -> None:
    assert severity_rank(SignalReasonSeverity.INFO) == 0
    assert severity_rank(SignalReasonSeverity.WARNING) == 1
    assert severity_rank(SignalReasonSeverity.BLOCKING) == 2
    assert severity_rank(SignalReasonSeverity.CRITICAL) == 3


def test_every_reason_code_has_a_definition() -> None:
    """An undefined code would have no category, severity or allowed status."""

    assert set(REASON_DEFINITIONS) == set(SignalReasonCode)


def test_every_definition_is_complete() -> None:
    for code, definition in REASON_DEFINITIONS.items():
        assert isinstance(definition.category, SignalReasonCategory), code
        assert isinstance(definition.minimum_severity, SignalReasonSeverity), code
        assert definition.statuses, code
        assert definition.message.strip(), code

        for status in definition.statuses:
            assert status in REASON_BEARING_STATUSES, code


def test_all_required_rejection_codes_exist() -> None:
    rejection_codes = {code.value for code in codes_for_status(SignalStatus.REJECTED)}

    assert {
        "risk_limit_exceeded",
        "account_disabled",
        "account_suspended",
        "funded_rule_breached",
        "auto_trade_not_allowed",
        "unpromoted_model",
        "confidence_below_threshold",
        "invalid_symbol",
        "symbol_blocked",
        "spread_too_high",
        "market_closed",
        "duplicate_signal",
        "manual_rejection",
        "validation_failed",
    } <= rejection_codes


def test_all_required_missed_codes_exist() -> None:
    missed_codes = {code.value for code in codes_for_status(SignalStatus.MISSED)}

    assert {
        "expired_before_approval",
        "approval_timeout",
        "broker_disconnected",
        "account_not_ready",
        "no_eligible_account",
        "risk_check_timeout",
        "signal_arrived_late",
        "execution_window_closed",
        "system_paused",
        "user_notifications_disabled",
    } <= missed_codes


def test_require_reason_definition() -> None:
    definition = require_reason_definition(SignalReasonCode.FUNDED_RULE_BREACHED)

    assert definition.category == SignalReasonCategory.FUNDED_RULE
    assert definition.minimum_severity == SignalReasonSeverity.CRITICAL
    assert definition.to_dict()["category"] == "funded_rule"


def test_resolve_helpers() -> None:
    assert resolve_reason_category(SignalReasonCode.SYMBOL_BLOCKED) == (
        SignalReasonCategory.ACCOUNT_RULE
    )
    assert resolve_minimum_severity(SignalReasonCode.MARKET_CLOSED) == (
        SignalReasonSeverity.INFO
    )
    assert default_reason_message(SignalReasonCode.BROKER_DISCONNECTED).strip()
    assert allowed_statuses_for_code(SignalReasonCode.APPROVAL_TIMEOUT) == (
        SignalStatus.MISSED,
    )


def test_category_mismatch_is_rejected() -> None:
    validate_reason_category(
        SignalReasonCode.RISK_LIMIT_EXCEEDED,
        SignalReasonCategory.RISK,
    )

    with pytest.raises(SignalReasonError, match="belongs to category risk"):
        validate_reason_category(
            SignalReasonCode.RISK_LIMIT_EXCEEDED,
            SignalReasonCategory.MARKET_CONDITION,
        )


def test_severity_can_be_escalated_but_never_played_down() -> None:
    """Recording a critical reason as informational would hide it downstream."""

    validate_reason_severity(
        SignalReasonCode.FUNDED_RULE_BREACHED,
        SignalReasonSeverity.CRITICAL,
    )

    for severity in (
        SignalReasonSeverity.INFO,
        SignalReasonSeverity.WARNING,
        SignalReasonSeverity.BLOCKING,
    ):
        with pytest.raises(SignalReasonError, match="cannot be recorded below"):
            validate_reason_severity(
                SignalReasonCode.FUNDED_RULE_BREACHED,
                severity,
            )

    validate_reason_severity(
        SignalReasonCode.MARKET_CLOSED,
        SignalReasonSeverity.CRITICAL,
    )


def test_status_must_be_reason_bearing() -> None:
    with pytest.raises(SignalReasonError, match="cannot be recorded for status"):
        validate_reason_status(
            SignalReasonCode.RISK_LIMIT_EXCEEDED,
            SignalStatus.EXECUTED,
        )

    with pytest.raises(SignalReasonError, match="cannot be recorded for status"):
        validate_reason_status(
            SignalReasonCode.RISK_LIMIT_EXCEEDED,
            SignalStatus.APPROVED,
        )


def test_code_cannot_explain_an_unrelated_status() -> None:
    """A rejection code must not be used to explain a missed signal."""

    with pytest.raises(SignalReasonError, match="cannot explain status missed"):
        validate_reason_status(
            SignalReasonCode.RISK_LIMIT_EXCEEDED,
            SignalStatus.MISSED,
        )

    with pytest.raises(SignalReasonError, match="cannot explain status rejected"):
        validate_reason_status(
            SignalReasonCode.APPROVAL_TIMEOUT,
            SignalStatus.REJECTED,
        )


def test_codes_valid_for_several_statuses() -> None:
    validate_reason_status(
        SignalReasonCode.BROKER_DISCONNECTED,
        SignalStatus.MISSED,
    )
    validate_reason_status(
        SignalReasonCode.BROKER_DISCONNECTED,
        SignalStatus.FAILED,
    )


def test_validate_reason_combines_every_check() -> None:
    validate_reason(
        code=SignalReasonCode.SYMBOL_BLOCKED,
        category=SignalReasonCategory.ACCOUNT_RULE,
        severity=SignalReasonSeverity.BLOCKING,
        status=SignalStatus.REJECTED,
    )

    with pytest.raises(SignalReasonError):
        validate_reason(
            code=SignalReasonCode.SYMBOL_BLOCKED,
            category=SignalReasonCategory.RISK,
            severity=SignalReasonSeverity.BLOCKING,
            status=SignalStatus.REJECTED,
        )


def test_build_reason_message_falls_back_to_canonical() -> None:
    assert build_reason_message(SignalReasonCode.MARKET_CLOSED) == (
        default_reason_message(SignalReasonCode.MARKET_CLOSED)
    )
    assert build_reason_message(SignalReasonCode.MARKET_CLOSED, "   ") == (
        default_reason_message(SignalReasonCode.MARKET_CLOSED)
    )
    assert build_reason_message(
        SignalReasonCode.MARKET_CLOSED,
        "Closed for a bank holiday.",
    ) == "Closed for a bank holiday."


def test_reason_derives_category_severity_and_message() -> None:
    """A caller supplying only the code still gets a fully populated row."""

    reason = build_reason()

    assert reason.reason_category == SignalReasonCategory.RISK
    assert reason.severity == SignalReasonSeverity.BLOCKING
    assert reason.message == default_reason_message(
        SignalReasonCode.RISK_LIMIT_EXCEEDED
    )
    assert reason.extra_metadata == {}

    reason.validate_taxonomy()


def test_reason_accepts_a_string_code() -> None:
    reason = build_reason(reason_code="market_closed")

    assert reason.reason_code == SignalReasonCode.MARKET_CLOSED
    assert reason.reason_category == SignalReasonCategory.MARKET_CONDITION


def test_reason_rejects_an_empty_message() -> None:
    with pytest.raises(SignalReasonError, match="message cannot be empty"):
        build_reason().message = "   "


def test_reason_rejects_unset_fields() -> None:
    reason = build_reason()
    reason.severity = None

    with pytest.raises(SignalReasonError, match="must never be unset"):
        reason.assert_no_unset_reason_fields()

    with pytest.raises(SignalReasonError, match="must never be unset"):
        reason.validate_taxonomy()


def test_reason_rejects_a_downgraded_severity() -> None:
    reason = build_reason(
        reason_code=SignalReasonCode.FUNDED_RULE_BREACHED,
        severity=SignalReasonSeverity.INFO,
    )

    with pytest.raises(SignalReasonError, match="cannot be recorded below"):
        reason.validate_taxonomy()


def test_reason_rejects_a_mismatched_category() -> None:
    reason = build_reason(reason_category=SignalReasonCategory.MARKET_CONDITION)

    with pytest.raises(SignalReasonError, match="belongs to category risk"):
        reason.validate_taxonomy()


def test_reason_rejects_a_status_the_code_cannot_explain() -> None:
    reason = build_reason(signal_status=SignalStatus.MISSED)

    with pytest.raises(SignalReasonError, match="cannot explain status missed"):
        reason.validate_taxonomy()


def test_reason_severity_helpers() -> None:
    assert build_reason().is_blocking is True
    assert build_reason().is_critical is False

    critical = build_reason(reason_code=SignalReasonCode.FUNDED_RULE_BREACHED)

    assert critical.is_critical is True
    assert critical.is_blocking is True

    informational = build_reason(reason_code=SignalReasonCode.MARKET_CLOSED)

    assert informational.is_blocking is False


def test_reason_dict_payload() -> None:
    payload = build_reason(
        account_id="account_1",
        source="risk_engine",
        extra_metadata={"limit": 0.05},
    ).to_dict()

    assert payload["reason_code"] == "risk_limit_exceeded"
    assert payload["reason_category"] == "risk"
    assert payload["severity"] == "blocking"
    assert payload["signal_status"] == "rejected"
    assert payload["account_id"] == "account_1"
    assert payload["source"] == "risk_engine"
    assert payload["is_blocking"] is True
    assert payload["metadata"] == {"limit": 0.05}
    assert payload["created_at_utc"] == "2026-01-01T00:00:00"
    assert "signal_1" in repr(build_reason())
