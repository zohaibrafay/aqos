"""
Unit tests for the signal action decisions that need no database.

The transition rules themselves belong to Sprint 044 and the reason taxonomy to
Sprint 045; both are tested there. What is tested here is the layer in between:
that the HTTP surface asks the right question, refuses the right things, and
never lets a client decide something the taxonomy is supposed to decide.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from aqos.http_api.action_schemas import (
    MAX_NOTE_LENGTH,
    SignalActionRequest,
    SignalCancelRequest,
    SignalDecisionRequest,
)
from aqos.http_api.errors import ApiErrorCode, AqosApiError, ValidationApiError
from aqos.http_api.routes_signal_actions import (
    NOT_DUE_MESSAGE,
    REASON_BEARING_ACTIONS,
    SIGNAL_ACTION_STATUSES,
    refuse_invalid_transition,
    require_due_expiry,
    resolve_reason_code,
)
from aqos.signal_reasons.taxonomy import (
    SignalReasonCode,
    codes_for_status,
    resolve_minimum_severity,
    resolve_reason_category,
)
from aqos.signals.models import (
    InvalidSignalTransitionError,
    SignalStatus,
    TERMINAL_SIGNAL_STATUSES,
    TradingSignal,
)


FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0)


def build_signal(
    status: SignalStatus = SignalStatus.GENERATED,
    expires_at_utc: datetime | None = None,
) -> TradingSignal:
    return TradingSignal(
        signal_id="signal_1",
        status=status,
        expires_at_utc=expires_at_utc,
    )


class TestActionSurface:
    def test_the_actions_are_exactly_these(self) -> None:
        """
        An allow list of reachable transitions.

        A new action has to be written down here, so no further part of the
        lifecycle becomes reachable over HTTP by accident.
        """

        assert set(SIGNAL_ACTION_STATUSES) == {
            "approve",
            "reject",
            "miss",
            "expire",
            "cancel",
            "mark-pending-approval",
        }

    def test_execution_outcomes_are_not_reachable(self) -> None:
        """
        ``executed`` and ``failed`` describe what a broker did.

        Nothing in Sprint 059 talks to a broker, so no endpoint may claim an
        order reached the market or failed there.
        """

        reachable = set(SIGNAL_ACTION_STATUSES.values())

        assert SignalStatus.EXECUTED not in reachable
        assert SignalStatus.FAILED not in reachable

    def test_only_reject_and_miss_carry_reasons(self) -> None:
        assert REASON_BEARING_ACTIONS == ("reject", "miss")

        for action in REASON_BEARING_ACTIONS:
            assert action in SIGNAL_ACTION_STATUSES


class TestReasonCodeResolution:
    def test_a_valid_rejection_code_is_accepted(self) -> None:
        code = resolve_reason_code(
            SignalReasonCode.SPREAD_TOO_HIGH.value,
            SignalStatus.REJECTED,
        )

        assert code is SignalReasonCode.SPREAD_TOO_HIGH

    def test_an_unknown_code_is_refused(self) -> None:
        with pytest.raises(ValidationApiError) as raised:
            resolve_reason_code("not_a_real_code", SignalStatus.REJECTED)

        assert raised.value.code is ApiErrorCode.VALIDATION_ERROR

    def test_a_code_that_cannot_explain_the_status_is_refused(self) -> None:
        """
        The taxonomy decides which code fits which outcome.

        A code that only explains a rejection cannot be used to explain a miss,
        or the reason rows would stop meaning anything.
        """

        rejected_only = [
            code
            for code in codes_for_status(SignalStatus.REJECTED)
            if code not in codes_for_status(SignalStatus.MISSED)
        ]

        assert rejected_only, "expected at least one rejection-only code"

        with pytest.raises(ValidationApiError) as raised:
            resolve_reason_code(rejected_only[0].value, SignalStatus.MISSED)

        assert raised.value.code is ApiErrorCode.VALIDATION_ERROR

    def test_the_refusal_names_what_would_have_worked(self) -> None:
        rejected_only = [
            code
            for code in codes_for_status(SignalStatus.REJECTED)
            if code not in codes_for_status(SignalStatus.MISSED)
        ]

        with pytest.raises(ValidationApiError) as raised:
            resolve_reason_code(rejected_only[0].value, SignalStatus.MISSED)

        allowed = raised.value.details["allowed_reason_codes"]

        assert allowed == [
            code.value for code in codes_for_status(SignalStatus.MISSED)
        ]
        assert rejected_only[0].value not in allowed

    def test_every_offered_code_resolves(self) -> None:
        """Whatever the refusal advertises must actually be accepted."""

        for status in (SignalStatus.REJECTED, SignalStatus.MISSED):
            for code in codes_for_status(status):
                assert resolve_reason_code(code.value, status) is code


class TestClientCannotDecideTaxonomy:
    def test_the_request_has_no_category_or_severity_field(self) -> None:
        """
        Category and severity are derived, never submitted.

        Accepting them would let a breached funded rule be filed as
        informational, which would hide it from every downstream report.
        """

        fields = set(SignalDecisionRequest.model_fields)

        assert fields == {"reason_code", "message"}

    @pytest.mark.parametrize(
        "field, value",
        [
            ("severity", "informational"),
            ("reason_category", "market_condition"),
            ("metadata", {"anything": True}),
            ("signal_status", "executed"),
            ("user_id", "user_someone_else"),
        ],
    )
    def test_smuggling_an_extra_field_is_refused(
        self,
        field: str,
        value,
    ) -> None:
        with pytest.raises(ValidationError):
            SignalDecisionRequest(
                reason_code=SignalReasonCode.SPREAD_TOO_HIGH.value,
                **{field: value},
            )

    def test_category_and_severity_come_from_the_code(self) -> None:
        """What the server will write is a function of the code alone."""

        code = SignalReasonCode.SPREAD_TOO_HIGH

        assert resolve_reason_category(code) is resolve_reason_category(code)
        assert resolve_minimum_severity(code) is resolve_minimum_severity(code)


class TestRequestSchemas:
    def test_a_decision_needs_a_reason_code(self) -> None:
        with pytest.raises(ValidationError):
            SignalDecisionRequest()

    def test_an_empty_reason_code_is_refused(self) -> None:
        with pytest.raises(ValidationError):
            SignalDecisionRequest(reason_code="")

    def test_a_cancellation_must_say_why(self) -> None:
        """Cancelling destroys an opportunity, so it is never silent."""

        with pytest.raises(ValidationError):
            SignalCancelRequest()

        with pytest.raises(ValidationError):
            SignalCancelRequest(note="")

    def test_an_approval_note_is_optional(self) -> None:
        assert SignalActionRequest().note is None
        assert SignalActionRequest(note="looks good").note == "looks good"

    @pytest.mark.parametrize(
        "model, payload",
        [
            (SignalActionRequest, {"note": "x" * (MAX_NOTE_LENGTH + 1)}),
            (SignalCancelRequest, {"note": "x" * (MAX_NOTE_LENGTH + 1)}),
            (
                SignalDecisionRequest,
                {
                    "reason_code": SignalReasonCode.SPREAD_TOO_HIGH.value,
                    "message": "x" * (MAX_NOTE_LENGTH + 1),
                },
            ),
        ],
    )
    def test_an_oversized_note_is_refused_at_the_edge(
        self,
        model,
        payload: dict,
    ) -> None:
        """
        Both columns are ``VARCHAR(512)``.

        Refusing here makes it a validation error instead of a database failure
        after the transition has already been attempted.
        """

        with pytest.raises(ValidationError):
            model(**payload)

    def test_a_note_of_the_maximum_length_is_accepted(self) -> None:
        assert len(SignalCancelRequest(note="x" * MAX_NOTE_LENGTH).note) == (
            MAX_NOTE_LENGTH
        )


class TestInvalidTransitionRefusal:
    def test_it_is_a_conflict(self) -> None:
        signal = build_signal(status=SignalStatus.APPROVED)

        error = refuse_invalid_transition(
            InvalidSignalTransitionError(
                "Signal cannot move from approved to approved."
            ),
            signal,
            SignalStatus.APPROVED,
        )

        assert isinstance(error, AqosApiError)
        assert error.code is ApiErrorCode.CONFLICT
        assert error.status_code == 409

    def test_it_says_where_the_signal_actually_is(self) -> None:
        signal = build_signal(status=SignalStatus.REJECTED)

        error = refuse_invalid_transition(
            InvalidSignalTransitionError("nope"),
            signal,
            SignalStatus.APPROVED,
        )

        assert error.details["from_status"] == "rejected"
        assert error.details["to_status"] == "approved"
        assert error.details["allowed_transitions"] == []

    @pytest.mark.parametrize("status", TERMINAL_SIGNAL_STATUSES)
    def test_a_terminal_signal_offers_nothing(
        self,
        status: SignalStatus,
    ) -> None:
        """Repeating a terminal action can only ever be refused."""

        error = refuse_invalid_transition(
            InvalidSignalTransitionError("nope"),
            build_signal(status=status),
            SignalStatus.CANCELLED,
        )

        assert error.details["allowed_transitions"] == []

    def test_it_leaks_no_internals(self) -> None:
        error = refuse_invalid_transition(
            InvalidSignalTransitionError(
                "Signal cannot move from approved to approved."
            ),
            build_signal(status=SignalStatus.APPROVED),
            SignalStatus.APPROVED,
        )
        rendered = f"{error.message} {error.details}"

        for fragment in (
            "InvalidSignalTransitionError",
            "Traceback",
            "SELECT",
            "sqlalchemy",
        ):
            assert fragment not in rendered


class TestExpiryIsHonest:
    def test_a_due_signal_may_expire(self) -> None:
        signal = build_signal(expires_at_utc=FIXED_NOW - timedelta(minutes=1))

        require_due_expiry(signal, FIXED_NOW)

    def test_expiry_exactly_now_counts_as_due(self) -> None:
        signal = build_signal(expires_at_utc=FIXED_NOW)

        require_due_expiry(signal, FIXED_NOW)

    def test_a_live_signal_may_not_be_called_expired(self) -> None:
        """
        ``expired`` means the market moved on, not "I changed my mind".

        Allowing it on a live signal would make it a synonym for ``cancelled``
        and would put a false statement in the audit trail.
        """

        signal = build_signal(expires_at_utc=FIXED_NOW + timedelta(minutes=1))

        with pytest.raises(AqosApiError) as raised:
            require_due_expiry(signal, FIXED_NOW)

        assert raised.value.code is ApiErrorCode.CONFLICT
        assert raised.value.message == NOT_DUE_MESSAGE
        assert raised.value.details["has_expiry"] is True

    def test_a_signal_with_no_expiry_may_not_be_expired(self) -> None:
        """Unknown is not "already passed"."""

        with pytest.raises(AqosApiError) as raised:
            require_due_expiry(build_signal(), FIXED_NOW)

        assert raised.value.details["has_expiry"] is False

    def test_the_refusal_points_at_the_right_action(self) -> None:
        signal = build_signal(expires_at_utc=FIXED_NOW + timedelta(hours=1))

        with pytest.raises(AqosApiError) as raised:
            require_due_expiry(signal, FIXED_NOW)

        assert "Cancel it instead" in raised.value.message
