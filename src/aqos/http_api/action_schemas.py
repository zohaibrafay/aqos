"""
Request bodies for the signal lifecycle action endpoints.

These carry only what a caller is allowed to decide. Everything a client must
not be trusted with — the reason's category and severity, who acted, when it
happened — is derived on the server from the Sprint 045 taxonomy and the
authenticated session.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


AQOS_HTTP_ACTION_SCHEMAS_VERSION = "1.0"

#: Bound on free-text notes accepted at the edge.
#:
#: ``signals.status_reason`` and ``signal_reasons.message`` are both
#: ``VARCHAR(512)``, so a longer note would be refused by MySQL after the
#: transition had already been attempted. Refusing it here keeps the failure a
#: plain validation error.
MAX_NOTE_LENGTH = 512

#: Bound on a reason code before it is looked up in the taxonomy.
MAX_REASON_CODE_LENGTH = 64


class SignalActionRequest(BaseModel):
    """
    An action that needs no structured reason.

    The note is optional and purely descriptive: it is recorded on the
    lifecycle event so a human can see why somebody acted, and it never
    influences whether the transition is allowed.
    """

    model_config = {"extra": "forbid"}

    note: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


class SignalCancelRequest(BaseModel):
    """
    A cancellation, which must say why.

    Unlike an approval, cancelling destroys a trading opportunity, and the
    lifecycle repository requires a non-empty reason for it. Making the field
    required here turns "I forgot" into a validation error rather than a
    500 from deeper down.
    """

    model_config = {"extra": "forbid"}

    note: str = Field(min_length=1, max_length=MAX_NOTE_LENGTH)


class SignalDecisionRequest(BaseModel):
    """
    A rejection or a miss, which must carry a taxonomy reason code.

    Only the code and an optional human message are accepted. The category and
    the severity are resolved from the code by the taxonomy: letting a client
    send them would allow a breached funded rule to be filed as informational,
    which would hide it from every downstream report.

    Free-form metadata is deliberately not accepted. ``extra_metadata`` is
    never returned by the read APIs precisely because it is unvalidated client
    JSON, and an audit row is the last place to start storing some.
    """

    model_config = {"extra": "forbid"}

    reason_code: str = Field(min_length=1, max_length=MAX_REASON_CODE_LENGTH)
    message: str | None = Field(default=None, max_length=MAX_NOTE_LENGTH)


__all__ = [
    "AQOS_HTTP_ACTION_SCHEMAS_VERSION",
    "MAX_NOTE_LENGTH",
    "MAX_REASON_CODE_LENGTH",
    "SignalActionRequest",
    "SignalCancelRequest",
    "SignalDecisionRequest",
]
