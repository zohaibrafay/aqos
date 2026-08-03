from __future__ import annotations

from enum import Enum
from typing import Any

from aqos.signals.models import SignalStatus


AQOS_SIGNAL_REASON_TAXONOMY_VERSION = "1.0"


class SignalReasonCategory(str, Enum):
    RISK = "risk"
    ACCOUNT_RULE = "account_rule"
    FUNDED_RULE = "funded_rule"
    EXECUTION_POLICY = "execution_policy"
    MODEL_PROMOTION = "model_promotion"
    MARKET_CONDITION = "market_condition"
    SIGNAL_EXPIRY = "signal_expiry"
    USER_ACTION = "user_action"
    SYSTEM_ERROR = "system_error"
    BROKER_UNAVAILABLE = "broker_unavailable"
    DUPLICATE_SIGNAL = "duplicate_signal"
    VALIDATION_ERROR = "validation_error"


class SignalReasonSeverity(str, Enum):
    """
    How serious the reason is, independent of whether it stopped the signal.

    Ordering matters: a reason may be recorded at or above its canonical
    severity, never below it.
    """

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"
    CRITICAL = "critical"


class SignalReasonCode(str, Enum):
    # Rejection reasons.
    RISK_LIMIT_EXCEEDED = "risk_limit_exceeded"
    ACCOUNT_DISABLED = "account_disabled"
    ACCOUNT_SUSPENDED = "account_suspended"
    ACCOUNT_NOT_PAPER = "account_not_paper"
    FUNDED_RULE_BREACHED = "funded_rule_breached"
    AUTO_TRADE_NOT_ALLOWED = "auto_trade_not_allowed"
    UNPROMOTED_MODEL = "unpromoted_model"
    CONFIDENCE_BELOW_THRESHOLD = "confidence_below_threshold"
    INVALID_SYMBOL = "invalid_symbol"
    SYMBOL_BLOCKED = "symbol_blocked"
    SPREAD_TOO_HIGH = "spread_too_high"
    MARKET_CLOSED = "market_closed"
    DUPLICATE_SIGNAL = "duplicate_signal"
    MANUAL_REJECTION = "manual_rejection"
    VALIDATION_FAILED = "validation_failed"

    # Missed reasons.
    EXPIRED_BEFORE_APPROVAL = "expired_before_approval"
    APPROVAL_TIMEOUT = "approval_timeout"
    BROKER_DISCONNECTED = "broker_disconnected"
    ACCOUNT_NOT_READY = "account_not_ready"
    NO_ELIGIBLE_ACCOUNT = "no_eligible_account"
    RISK_CHECK_TIMEOUT = "risk_check_timeout"
    SIGNAL_ARRIVED_LATE = "signal_arrived_late"
    EXECUTION_WINDOW_CLOSED = "execution_window_closed"
    SYSTEM_PAUSED = "system_paused"
    USER_NOTIFICATIONS_DISABLED = "user_notifications_disabled"


SEVERITY_RANK: dict[SignalReasonSeverity, int] = {
    SignalReasonSeverity.INFO: 0,
    SignalReasonSeverity.WARNING: 1,
    SignalReasonSeverity.BLOCKING: 2,
    SignalReasonSeverity.CRITICAL: 3,
}

#: Lifecycle statuses a structured reason can explain.
REASON_BEARING_STATUSES = (
    SignalStatus.REJECTED,
    SignalStatus.MISSED,
    SignalStatus.FAILED,
    SignalStatus.EXPIRED,
    SignalStatus.CANCELLED,
)


class ReasonDefinition:
    """The canonical meaning of one reason code."""

    __slots__ = ("category", "minimum_severity", "statuses", "message")

    def __init__(
        self,
        category: SignalReasonCategory,
        minimum_severity: SignalReasonSeverity,
        statuses: tuple[SignalStatus, ...],
        message: str,
    ) -> None:
        self.category = category
        self.minimum_severity = minimum_severity
        self.statuses = statuses
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "minimum_severity": self.minimum_severity.value,
            "statuses": [status.value for status in self.statuses],
            "message": self.message,
        }


_REJECTED = (SignalStatus.REJECTED,)
_MISSED = (SignalStatus.MISSED,)
_MISSED_OR_FAILED = (SignalStatus.MISSED, SignalStatus.FAILED)
_REJECTED_OR_FAILED = (SignalStatus.REJECTED, SignalStatus.FAILED)


REASON_DEFINITIONS: dict[SignalReasonCode, ReasonDefinition] = {
    SignalReasonCode.RISK_LIMIT_EXCEEDED: ReasonDefinition(
        SignalReasonCategory.RISK,
        SignalReasonSeverity.BLOCKING,
        _REJECTED,
        "Risk limit exceeded for this account.",
    ),
    SignalReasonCode.ACCOUNT_DISABLED: ReasonDefinition(
        SignalReasonCategory.ACCOUNT_RULE,
        SignalReasonSeverity.BLOCKING,
        _REJECTED,
        "Account is disabled.",
    ),
    SignalReasonCode.ACCOUNT_SUSPENDED: ReasonDefinition(
        SignalReasonCategory.ACCOUNT_RULE,
        SignalReasonSeverity.BLOCKING,
        _REJECTED,
        "Account is suspended.",
    ),
    SignalReasonCode.ACCOUNT_NOT_PAPER: ReasonDefinition(
        SignalReasonCategory.ACCOUNT_RULE,
        SignalReasonSeverity.CRITICAL,
        _REJECTED,
        "Simulated execution was routed at a non-paper account.",
    ),
    SignalReasonCode.FUNDED_RULE_BREACHED: ReasonDefinition(
        SignalReasonCategory.FUNDED_RULE,
        SignalReasonSeverity.CRITICAL,
        _REJECTED,
        "Funded account rules are breached.",
    ),
    SignalReasonCode.AUTO_TRADE_NOT_ALLOWED: ReasonDefinition(
        SignalReasonCategory.EXECUTION_POLICY,
        SignalReasonSeverity.BLOCKING,
        _REJECTED,
        "Effective execution mode does not allow automatic orders.",
    ),
    SignalReasonCode.UNPROMOTED_MODEL: ReasonDefinition(
        SignalReasonCategory.MODEL_PROMOTION,
        SignalReasonSeverity.CRITICAL,
        _REJECTED,
        "Model is not promoted for this execution stage.",
    ),
    SignalReasonCode.CONFIDENCE_BELOW_THRESHOLD: ReasonDefinition(
        SignalReasonCategory.MODEL_PROMOTION,
        SignalReasonSeverity.WARNING,
        _REJECTED,
        "Model confidence was below the configured threshold.",
    ),
    SignalReasonCode.INVALID_SYMBOL: ReasonDefinition(
        SignalReasonCategory.VALIDATION_ERROR,
        SignalReasonSeverity.BLOCKING,
        _REJECTED,
        "Symbol is not valid for this account.",
    ),
    SignalReasonCode.SYMBOL_BLOCKED: ReasonDefinition(
        SignalReasonCategory.ACCOUNT_RULE,
        SignalReasonSeverity.BLOCKING,
        _REJECTED,
        "Symbol is blocked for this user.",
    ),
    SignalReasonCode.SPREAD_TOO_HIGH: ReasonDefinition(
        SignalReasonCategory.MARKET_CONDITION,
        SignalReasonSeverity.WARNING,
        _REJECTED,
        "Spread was wider than the allowed maximum.",
    ),
    SignalReasonCode.MARKET_CLOSED: ReasonDefinition(
        SignalReasonCategory.MARKET_CONDITION,
        SignalReasonSeverity.INFO,
        _REJECTED,
        "Market was closed for this symbol.",
    ),
    SignalReasonCode.DUPLICATE_SIGNAL: ReasonDefinition(
        SignalReasonCategory.DUPLICATE_SIGNAL,
        SignalReasonSeverity.INFO,
        _REJECTED,
        "Duplicate of an existing signal.",
    ),
    SignalReasonCode.MANUAL_REJECTION: ReasonDefinition(
        SignalReasonCategory.USER_ACTION,
        SignalReasonSeverity.INFO,
        _REJECTED,
        "Rejected manually.",
    ),
    SignalReasonCode.VALIDATION_FAILED: ReasonDefinition(
        SignalReasonCategory.VALIDATION_ERROR,
        SignalReasonSeverity.CRITICAL,
        _REJECTED_OR_FAILED,
        "Signal failed validation.",
    ),
    SignalReasonCode.EXPIRED_BEFORE_APPROVAL: ReasonDefinition(
        SignalReasonCategory.SIGNAL_EXPIRY,
        SignalReasonSeverity.WARNING,
        (SignalStatus.MISSED, SignalStatus.EXPIRED),
        "Signal expired before it was approved.",
    ),
    SignalReasonCode.APPROVAL_TIMEOUT: ReasonDefinition(
        SignalReasonCategory.USER_ACTION,
        SignalReasonSeverity.WARNING,
        _MISSED,
        "Manual approval was not given in time.",
    ),
    SignalReasonCode.BROKER_DISCONNECTED: ReasonDefinition(
        SignalReasonCategory.BROKER_UNAVAILABLE,
        SignalReasonSeverity.CRITICAL,
        _MISSED_OR_FAILED,
        "Broker connection was unavailable.",
    ),
    SignalReasonCode.ACCOUNT_NOT_READY: ReasonDefinition(
        SignalReasonCategory.ACCOUNT_RULE,
        SignalReasonSeverity.WARNING,
        _MISSED,
        "Account was not ready to trade.",
    ),
    SignalReasonCode.NO_ELIGIBLE_ACCOUNT: ReasonDefinition(
        SignalReasonCategory.ACCOUNT_RULE,
        SignalReasonSeverity.WARNING,
        _MISSED,
        "No eligible account was available for this signal.",
    ),
    SignalReasonCode.RISK_CHECK_TIMEOUT: ReasonDefinition(
        SignalReasonCategory.SYSTEM_ERROR,
        SignalReasonSeverity.CRITICAL,
        _MISSED_OR_FAILED,
        "Risk check did not complete in time.",
    ),
    SignalReasonCode.SIGNAL_ARRIVED_LATE: ReasonDefinition(
        SignalReasonCategory.MARKET_CONDITION,
        SignalReasonSeverity.WARNING,
        _MISSED,
        "Signal arrived too late to be actionable.",
    ),
    SignalReasonCode.EXECUTION_WINDOW_CLOSED: ReasonDefinition(
        SignalReasonCategory.MARKET_CONDITION,
        SignalReasonSeverity.INFO,
        _MISSED,
        "Execution window had already closed.",
    ),
    SignalReasonCode.SYSTEM_PAUSED: ReasonDefinition(
        SignalReasonCategory.SYSTEM_ERROR,
        SignalReasonSeverity.WARNING,
        _MISSED,
        "Trading was paused by the system.",
    ),
    SignalReasonCode.USER_NOTIFICATIONS_DISABLED: ReasonDefinition(
        SignalReasonCategory.USER_ACTION,
        SignalReasonSeverity.INFO,
        _MISSED,
        "User notifications were disabled.",
    ),
}


class SignalReasonError(ValueError):
    """Raised when a structured reason is not valid for the decision recorded."""


def severity_rank(severity: SignalReasonSeverity) -> int:
    return SEVERITY_RANK[severity]


def require_reason_definition(code: SignalReasonCode) -> ReasonDefinition:
    definition = REASON_DEFINITIONS.get(code)

    if definition is None:
        raise SignalReasonError(f"Reason code has no definition: {code}")

    return definition


def resolve_reason_category(code: SignalReasonCode) -> SignalReasonCategory:
    return require_reason_definition(code).category


def resolve_minimum_severity(code: SignalReasonCode) -> SignalReasonSeverity:
    return require_reason_definition(code).minimum_severity


def default_reason_message(code: SignalReasonCode) -> str:
    return require_reason_definition(code).message


def allowed_statuses_for_code(code: SignalReasonCode) -> tuple[SignalStatus, ...]:
    return require_reason_definition(code).statuses


def codes_for_status(status: SignalStatus) -> tuple[SignalReasonCode, ...]:
    return tuple(
        code
        for code, definition in REASON_DEFINITIONS.items()
        if status in definition.statuses
    )


def validate_reason_category(
    code: SignalReasonCode,
    category: SignalReasonCategory,
) -> None:
    """A code's category is fixed, so a mismatched one is a programming error."""

    expected = resolve_reason_category(code)

    if category != expected:
        raise SignalReasonError(
            f"Reason code {code.value} belongs to category {expected.value}, "
            f"not {category.value}."
        )


def validate_reason_severity(
    code: SignalReasonCode,
    severity: SignalReasonSeverity,
) -> None:
    """
    A reason may be escalated but never played down.

    Recording a breached funded rule as informational would hide a serious
    event from every downstream report, so it is refused.
    """

    minimum = resolve_minimum_severity(code)

    if severity_rank(severity) < severity_rank(minimum):
        raise SignalReasonError(
            f"Reason code {code.value} cannot be recorded below severity "
            f"{minimum.value}; got {severity.value}."
        )


def validate_reason_status(
    code: SignalReasonCode,
    status: SignalStatus,
) -> None:
    if status not in REASON_BEARING_STATUSES:
        raise SignalReasonError(
            f"Structured reasons cannot be recorded for status: {status.value}"
        )

    allowed = allowed_statuses_for_code(code)

    if status not in allowed:
        raise SignalReasonError(
            f"Reason code {code.value} cannot explain status {status.value}; "
            f"allowed statuses are: {', '.join(item.value for item in allowed)}"
        )


def validate_reason(
    code: SignalReasonCode,
    category: SignalReasonCategory,
    severity: SignalReasonSeverity,
    status: SignalStatus,
) -> None:
    validate_reason_category(code, category)
    validate_reason_severity(code, severity)
    validate_reason_status(code, status)


__all__ = [
    "AQOS_SIGNAL_REASON_TAXONOMY_VERSION",
    "REASON_BEARING_STATUSES",
    "REASON_DEFINITIONS",
    "ReasonDefinition",
    "SEVERITY_RANK",
    "SignalReasonCategory",
    "SignalReasonCode",
    "SignalReasonError",
    "SignalReasonSeverity",
    "allowed_statuses_for_code",
    "codes_for_status",
    "default_reason_message",
    "require_reason_definition",
    "resolve_minimum_severity",
    "resolve_reason_category",
    "severity_rank",
    "validate_reason",
    "validate_reason_category",
    "validate_reason_severity",
    "validate_reason_status",
]
