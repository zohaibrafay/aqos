from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from datetime import datetime
from enum import Enum
from typing import Any, Sequence

from aqos.accounts.models import AccountStatus, AccountType, TradingAccount
from aqos.execution_policy.modes import (
    ExecutionConstraint,
    ExecutionConstraintSource,
    ExecutionMode,
    ExecutionModeDecision,
    execution_mode_allows_orders,
    resolve_execution_mode,
)
from aqos.funded_rules.evaluation import FundedRuleEvaluation
from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.model_training.model_promotion import is_target_stage_allowed
from aqos.paper_trading.contracts import (
    PaperExecutionRequest,
    PaperRejectionReason,
    PaperTradingError,
    normalize_paper_symbol,
)
from aqos.paper_trading.validation import validate_paper_execution_request
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonSeverity,
    default_reason_message,
    resolve_minimum_severity,
    resolve_reason_category,
)
from aqos.signals.models import SignalStatus, TradingSignal
from aqos.trading_settings.models import TradingSettings


AQOS_PAPER_ELIGIBILITY_VERSION = "1.0"

#: The execution mode a paper order needs before it may be booked at all.
#: Paper trading is still an execution path, so it obeys the same ceiling logic
#: as every other venue.
REQUIRED_PAPER_EXECUTION_MODES = (
    ExecutionMode.MANUAL_APPROVAL,
    ExecutionMode.AUTO_TRADE,
)

#: The only signal status from which execution may proceed.
#:
#: Sprint 044 makes ``approved`` the sole predecessor of ``executed``. The gate
#: repeats that rule rather than trusting callers to have checked it.
EXECUTABLE_SIGNAL_STATUS = SignalStatus.APPROVED

#: The promotion stage a model must have reached to drive paper execution.
PAPER_TRADING_PROMOTION_STAGE = ModelPromotionStage.PAPER_TRADING


class PaperEligibilitySource(str, Enum):
    """Which rule produced a reason. Mirrors the blocking_sources audit trail."""

    ACCOUNT = "account"
    ACCOUNT_TYPE = "account_type"
    USER_SETTINGS = "user_settings"
    SYMBOL_PREFERENCES = "symbol_preferences"
    SIGNAL_LIFECYCLE = "signal_lifecycle"
    DUPLICATE_EXECUTION = "duplicate_execution"
    EXECUTION_POLICY = "execution_policy"
    FUNDED_RULE = "funded_rule"
    RISK_ENGINE = "risk_engine"
    MODEL_PROMOTION = "model_promotion"
    VALIDATION = "validation"


@dataclass(frozen=True)
class PaperEligibilityReason:
    """
    One structured reason a paper execution was refused or flagged.

    The code comes from the Sprint 045 taxonomy; the category and severity are
    derived from it so a caller cannot record a breach as informational.
    """

    code: SignalReasonCode
    source: PaperEligibilitySource
    message: str | None = None
    is_blocking: bool = True
    details: dict[str, Any] = dataclass_field(default_factory=dict)
    #: The precise order-level enum, when the rule knows something narrower
    #: than the taxonomy code. Several distinct shape failures share
    #: ``validation_failed``, and the order row should not lose that detail.
    order_rejection_reason: PaperRejectionReason | None = None

    @property
    def category(self) -> SignalReasonCategory:
        return resolve_reason_category(self.code)

    @property
    def severity(self) -> SignalReasonSeverity:
        return resolve_minimum_severity(self.code)

    @property
    def resolved_message(self) -> str:
        return self.message or default_reason_message(self.code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "source": self.source.value,
            "category": self.category.value,
            "severity": self.severity.value,
            "message": self.resolved_message,
            "is_blocking": self.is_blocking,
            "details": self.details,
        }


@dataclass(frozen=True)
class PaperExecutionEligibilityDecision:
    """
    Whether a paper execution may proceed, and exactly why not when it may not.

    Every refusal carries a structured taxonomy code, so a blocked execution can
    always be explained without parsing free text.
    """

    is_allowed: bool
    requested_execution_mode: ExecutionMode
    effective_execution_mode: ExecutionMode
    user_id: str
    account_id: str
    symbol: str
    blocking_sources: tuple[str, ...] = ()
    reasons: tuple[PaperEligibilityReason, ...] = ()
    signal_id: str | None = None
    decision_metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.is_allowed and self.blocking_reasons:
            raise PaperTradingError(
                "An allowed eligibility decision cannot carry blocking reasons."
            )

        if not self.is_allowed and not self.blocking_reasons:
            raise PaperTradingError(
                "A refused eligibility decision must carry a blocking reason."
            )

    @property
    def blocking_reasons(self) -> tuple[PaperEligibilityReason, ...]:
        return tuple(reason for reason in self.reasons if reason.is_blocking)

    @property
    def warnings(self) -> tuple[PaperEligibilityReason, ...]:
        return tuple(reason for reason in self.reasons if not reason.is_blocking)

    @property
    def reason_codes(self) -> tuple[str, ...]:
        return tuple(reason.code.value for reason in self.blocking_reasons)

    @property
    def primary_reason(self) -> PaperEligibilityReason | None:
        """The first blocking reason, which is the one worth surfacing."""

        blocking = self.blocking_reasons

        return blocking[0] if blocking else None

    @property
    def requires_manual_approval(self) -> bool:
        return self.effective_execution_mode == ExecutionMode.MANUAL_APPROVAL

    def explain(self) -> str:
        if self.is_allowed:
            return (
                f"Paper execution allowed at "
                f"{self.effective_execution_mode.value}."
            )

        return "Paper execution refused: " + "; ".join(
            f"{reason.source.value}={reason.code.value}"
            for reason in self.blocking_reasons
        )

    def rejection_message(self) -> str:
        """
        The message to surface on a refused execution.

        The primary reason's own wording is kept, because it names the specific
        ceiling or rule that fired; any further codes are appended so a refusal
        with several causes does not look like it had one.
        """

        primary = self.primary_reason

        if primary is None:
            return self.explain()

        others = tuple(
            reason.code.value for reason in self.blocking_reasons[1:]
        )
        suffix = f" (also: {', '.join(others)})" if others else ""

        return f"{primary.code.value}: {primary.resolved_message}{suffix}"

    def raise_if_blocked(self) -> None:
        if self.is_allowed:
            return

        raise PaperTradingError(self.explain())

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_allowed": self.is_allowed,
            "requested_execution_mode": self.requested_execution_mode.value,
            "effective_execution_mode": self.effective_execution_mode.value,
            "requires_manual_approval": self.requires_manual_approval,
            "blocking_sources": list(self.blocking_sources),
            "reason_codes": list(self.reason_codes),
            "reasons": [reason.to_dict() for reason in self.reasons],
            "signal_id": self.signal_id,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "symbol": self.symbol,
            "explanation": self.explain(),
            "decision_metadata": self.decision_metadata,
        }


@dataclass(frozen=True)
class PaperEligibilityContext:
    """
    Everything the gate needs beyond the request and the account.

    Inputs the gate cannot resolve for itself are passed in explicitly. Where an
    input is missing but the rule it feeds is safety-critical, the gate refuses
    rather than assuming the check passed.
    """

    settings: TradingSettings | None = None
    blocked_symbols: tuple[str, ...] = ()
    allowed_symbols: tuple[str, ...] | None = None
    signal: TradingSignal | None = None
    has_existing_execution: bool = False
    funded_evaluation: FundedRuleEvaluation | None = None
    risk_limit_breached: bool = False
    risk_limit_message: str | None = None
    model_promotion_stage: ModelPromotionStage | None = None
    #: Symbol of the bar the execution would price against, when one is known.
    #: A bar for a different instrument must never fill this request.
    market_data_symbol: str | None = None
    evaluated_at_utc: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_settings": self.settings is not None,
            "blocked_symbols": list(self.blocked_symbols),
            "allowed_symbols": (
                list(self.allowed_symbols)
                if self.allowed_symbols is not None
                else None
            ),
            "signal_status": (
                self.signal.status.value if self.signal is not None else None
            ),
            "has_existing_execution": self.has_existing_execution,
            "funded_rules_passed": (
                self.funded_evaluation.passed
                if self.funded_evaluation is not None
                else None
            ),
            "risk_limit_breached": self.risk_limit_breached,
            "model_promotion_stage": (
                self.model_promotion_stage.value
                if self.model_promotion_stage is not None
                else None
            ),
        }


def build_account_execution_constraint(
    account: TradingAccount,
) -> ExecutionConstraint:
    return ExecutionConstraint(
        source=ExecutionConstraintSource.ACCOUNT,
        ceiling=account.execution_mode,
        reason="Account execution mode.",
    )


def build_settings_execution_constraint(
    settings: TradingSettings,
) -> ExecutionConstraint:
    return ExecutionConstraint(
        source=ExecutionConstraintSource.USER_SETTINGS,
        ceiling=settings.execution_mode,
        reason="User trading settings execution mode.",
    )


def collect_execution_constraints(
    account: TradingAccount,
    context: PaperEligibilityContext,
    extra_constraints: Sequence[ExecutionConstraint] = (),
) -> tuple[ExecutionConstraint, ...]:
    """
    Gather every ceiling that applies, strictest-wins.

    The account always contributes one, so the resolver is never called with an
    empty set and can never hand back the requested mode unchecked.
    """

    constraints: list[ExecutionConstraint] = [
        build_account_execution_constraint(account)
    ]

    if context.settings is not None:
        constraints.append(build_settings_execution_constraint(context.settings))

    if context.model_promotion_stage is not None and not is_target_stage_allowed(
        PAPER_TRADING_PROMOTION_STAGE,
        context.model_promotion_stage,
    ):
        constraints.append(
            ExecutionConstraint(
                source=ExecutionConstraintSource.MODEL_PROMOTION,
                ceiling=ExecutionMode.SIGNAL_ONLY,
                reason=(
                    f"Model promotion stage "
                    f"{context.model_promotion_stage.value} does not reach "
                    f"{PAPER_TRADING_PROMOTION_STAGE.value}."
                ),
            )
        )

    if context.funded_evaluation is not None and not context.funded_evaluation.passed:
        constraints.append(
            ExecutionConstraint(
                source=ExecutionConstraintSource.FUNDED_RULE,
                ceiling=ExecutionMode.SIGNAL_ONLY,
                reason="Funded rules are breached.",
            )
        )

    if context.risk_limit_breached:
        constraints.append(
            ExecutionConstraint(
                source=ExecutionConstraintSource.RISK_ENGINE,
                ceiling=ExecutionMode.SIGNAL_ONLY,
                reason=context.risk_limit_message or "Risk limit exceeded.",
            )
        )

    constraints.extend(extra_constraints)

    return tuple(constraints)


#: Request-shape failures that the account rules already cover, so folding the
#: shape check into the gate does not report them twice.
ACCOUNT_LEVEL_REJECTIONS = (
    PaperRejectionReason.ACCOUNT_NOT_PAPER,
    PaperRejectionReason.ACCOUNT_NOT_ACTIVE,
)

#: How a request-shape rejection maps onto the taxonomy.
SHAPE_REJECTION_CODES: dict[PaperRejectionReason, SignalReasonCode] = {
    PaperRejectionReason.INVALID_SYMBOL: SignalReasonCode.INVALID_SYMBOL,
    PaperRejectionReason.INVALID_QUANTITY: SignalReasonCode.VALIDATION_FAILED,
    PaperRejectionReason.INVALID_PRICE: SignalReasonCode.VALIDATION_FAILED,
    PaperRejectionReason.MISSING_REQUIRED_FIELD: (
        SignalReasonCode.VALIDATION_FAILED
    ),
    PaperRejectionReason.UNSUPPORTED_ORDER_TYPE: (
        SignalReasonCode.VALIDATION_FAILED
    ),
    PaperRejectionReason.UNSAFE_ACTION: SignalReasonCode.VALIDATION_FAILED,
}


def check_request_shape(
    request: PaperExecutionRequest,
    account: TradingAccount,
) -> PaperEligibilityReason | None:
    """
    Fold the Sprint 048 request validation into the gate.

    Running it here rather than ahead of the gate means every refused attempt
    produces exactly one recorded decision, including the ones refused for a
    malformed request.
    """

    result = validate_paper_execution_request(request, account)

    if result.accepted or result.rejection_reason in ACCOUNT_LEVEL_REJECTIONS:
        return None

    return PaperEligibilityReason(
        code=SHAPE_REJECTION_CODES.get(
            result.rejection_reason,
            SignalReasonCode.VALIDATION_FAILED,
        ),
        source=PaperEligibilitySource.VALIDATION,
        message=result.rejection_message,
        details={
            "rejection_reason": (
                result.rejection_reason.value
                if result.rejection_reason is not None
                else None
            )
        },
        order_rejection_reason=result.rejection_reason,
    )


def check_market_data(
    request: PaperExecutionRequest,
    context: PaperEligibilityContext,
) -> PaperEligibilityReason | None:
    """
    The bar being priced against must be for the requested instrument.

    Filling an XAUUSD order from a EURUSD bar would book a fictional price, so
    the mismatch is refused here — inside the gate, so the attempt is recorded
    like every other refusal.
    """

    if context.market_data_symbol is None:
        return None

    bar_symbol = normalize_paper_symbol(context.market_data_symbol)

    if bar_symbol == request.symbol:
        return None

    return PaperEligibilityReason(
        code=SignalReasonCode.INVALID_SYMBOL,
        source=PaperEligibilitySource.VALIDATION,
        message=(
            f"Bar symbol {bar_symbol} does not match request symbol "
            f"{request.symbol}."
        ),
        details={"bar_symbol": bar_symbol, "request_symbol": request.symbol},
        order_rejection_reason=PaperRejectionReason.INVALID_SYMBOL,
    )


def check_account_is_paper(
    account: TradingAccount,
) -> PaperEligibilityReason | None:
    """
    Paper execution stays paper-only.

    Live, funded, demo and every broker-backed account are refused here, before
    any row is written, so simulated fills can never touch real capital.
    """

    if account.account_type == AccountType.PAPER:
        return None

    return PaperEligibilityReason(
        code=SignalReasonCode.ACCOUNT_NOT_PAPER,
        source=PaperEligibilitySource.ACCOUNT_TYPE,
        message=(
            f"Paper execution only runs on paper accounts, not "
            f"{account.account_type.value}."
        ),
        details={
            "account_type": account.account_type.value,
            "broker": account.broker.value,
        },
    )


def check_account_status(
    account: TradingAccount,
) -> PaperEligibilityReason | None:
    if account.status == AccountStatus.ACTIVE:
        return None

    code = (
        SignalReasonCode.ACCOUNT_SUSPENDED
        if account.status == AccountStatus.SUSPENDED
        else SignalReasonCode.ACCOUNT_DISABLED
    )

    return PaperEligibilityReason(
        code=code,
        source=PaperEligibilitySource.ACCOUNT,
        message=f"Account status is {account.status.value}.",
        details={"account_status": account.status.value},
    )


def check_symbol(
    request: PaperExecutionRequest,
    context: PaperEligibilityContext,
) -> PaperEligibilityReason | None:
    symbol = request.symbol

    if symbol in {normalize_paper_symbol(item) for item in context.blocked_symbols}:
        return PaperEligibilityReason(
            code=SignalReasonCode.SYMBOL_BLOCKED,
            source=PaperEligibilitySource.SYMBOL_PREFERENCES,
            message=f"Symbol {symbol} is blocked for this user.",
            details={"symbol": symbol},
        )

    if context.allowed_symbols is not None:
        allowed = {normalize_paper_symbol(item) for item in context.allowed_symbols}

        if symbol not in allowed:
            return PaperEligibilityReason(
                code=SignalReasonCode.INVALID_SYMBOL,
                source=PaperEligibilitySource.SYMBOL_PREFERENCES,
                message=f"Symbol {symbol} is not tradable for this user.",
                details={"symbol": symbol},
            )

    return None


def check_signal_lifecycle(
    request: PaperExecutionRequest,
    context: PaperEligibilityContext,
) -> PaperEligibilityReason | None:
    """
    A signal may only be executed from ``approved``.

    Executing a generated or pending signal would bypass the lifecycle entirely,
    and a rejected, missed, expired, failed or cancelled signal must never reach
    the market at all.
    """

    if request.signal_id is None:
        return None

    signal = context.signal

    if signal is None:
        return PaperEligibilityReason(
            code=SignalReasonCode.VALIDATION_FAILED,
            source=PaperEligibilitySource.SIGNAL_LIFECYCLE,
            message=(
                f"Signal {request.signal_id} was not found, so its lifecycle "
                "status cannot be verified."
            ),
            details={"signal_id": request.signal_id},
        )

    if signal.signal_id != request.signal_id:
        return PaperEligibilityReason(
            code=SignalReasonCode.VALIDATION_FAILED,
            source=PaperEligibilitySource.SIGNAL_LIFECYCLE,
            message="Request and signal refer to different signals.",
            details={
                "signal_id": request.signal_id,
                "context_signal_id": signal.signal_id,
            },
        )

    if signal.status != EXECUTABLE_SIGNAL_STATUS:
        return PaperEligibilityReason(
            code=SignalReasonCode.VALIDATION_FAILED,
            source=PaperEligibilitySource.SIGNAL_LIFECYCLE,
            message=(
                f"Signal status is {signal.status.value}; only "
                f"{EXECUTABLE_SIGNAL_STATUS.value} may execute."
            ),
            details={
                "signal_id": signal.signal_id,
                "signal_status": signal.status.value,
            },
        )

    return None


def check_duplicate_execution(
    request: PaperExecutionRequest,
    context: PaperEligibilityContext,
) -> PaperEligibilityReason | None:
    if request.signal_id is None or not context.has_existing_execution:
        return None

    return PaperEligibilityReason(
        code=SignalReasonCode.DUPLICATE_SIGNAL,
        source=PaperEligibilitySource.DUPLICATE_EXECUTION,
        message=(
            f"Signal {request.signal_id} already has an order on account "
            f"{request.account_id}."
        ),
        details={
            "signal_id": request.signal_id,
            "account_id": request.account_id,
        },
    )


def check_model_promotion(
    context: PaperEligibilityContext,
) -> PaperEligibilityReason | None:
    """
    A model-driven signal needs a model promoted at least to paper trading.

    When the signal names a model but no promotion stage was resolved, the gate
    refuses: an unverifiable model is treated exactly like an unpromoted one.
    """

    signal = context.signal

    if signal is None or not signal.model_id:
        return None

    stage = context.model_promotion_stage

    if is_target_stage_allowed(PAPER_TRADING_PROMOTION_STAGE, stage):
        return None

    return PaperEligibilityReason(
        code=SignalReasonCode.UNPROMOTED_MODEL,
        source=PaperEligibilitySource.MODEL_PROMOTION,
        message=(
            f"Model {signal.model_id} is not promoted to "
            f"{PAPER_TRADING_PROMOTION_STAGE.value}; resolved stage is "
            f"{stage.value if stage is not None else 'unknown'}."
        ),
        details={
            "model_id": signal.model_id,
            "model_version": signal.model_version,
            "promotion_stage": stage.value if stage is not None else None,
        },
    )


def check_funded_rules(
    context: PaperEligibilityContext,
) -> PaperEligibilityReason | None:
    """
    Funded rules constrain the simulation; they never make it a funded account.

    A paper account carrying a funded rule set is practising against those
    limits, so a breach blocks the simulated order the same way it would block a
    real one.
    """

    evaluation = context.funded_evaluation

    if evaluation is None or evaluation.passed:
        return None

    return PaperEligibilityReason(
        code=SignalReasonCode.FUNDED_RULE_BREACHED,
        source=PaperEligibilitySource.FUNDED_RULE,
        message=evaluation.breach_summary(),
        details={
            "breaches": [
                violation.check.value for violation in evaluation.breaches
            ],
        },
    )


def check_risk_limits(
    context: PaperEligibilityContext,
) -> PaperEligibilityReason | None:
    if not context.risk_limit_breached:
        return None

    return PaperEligibilityReason(
        code=SignalReasonCode.RISK_LIMIT_EXCEEDED,
        source=PaperEligibilitySource.RISK_ENGINE,
        message=context.risk_limit_message or None,
    )


def check_execution_mode(
    decision: ExecutionModeDecision,
) -> PaperEligibilityReason | None:
    if execution_mode_allows_orders(decision.effective):
        return None

    return PaperEligibilityReason(
        code=SignalReasonCode.AUTO_TRADE_NOT_ALLOWED,
        source=PaperEligibilitySource.EXECUTION_POLICY,
        message=decision.explain(),
        details={
            "effective_mode": decision.effective.value,
            "binding_sources": list(decision.binding_sources),
        },
    )


def evaluate_paper_execution_eligibility(
    request: PaperExecutionRequest,
    account: TradingAccount,
    context: PaperEligibilityContext | None = None,
    requested_mode: ExecutionMode = ExecutionMode.AUTO_TRADE,
    extra_constraints: Sequence[ExecutionConstraint] = (),
) -> PaperExecutionEligibilityDecision:
    """
    Decide whether one paper execution may proceed.

    Every rule runs, so the decision lists all of the reasons rather than only
    the first: a caller fixing one problem should be able to see the rest.
    """

    resolved_context = context or PaperEligibilityContext()

    if request.account_id != account.account_id:
        raise PaperTradingError(
            "Request and account refer to different accounts."
        )

    constraints = collect_execution_constraints(
        account=account,
        context=resolved_context,
        extra_constraints=extra_constraints,
    )
    mode_decision = resolve_execution_mode(requested_mode, constraints)

    candidates = (
        check_account_is_paper(account),
        check_account_status(account),
        check_market_data(request, resolved_context),
        check_request_shape(request, account),
        check_symbol(request, resolved_context),
        # Duplicate is checked before lifecycle: a second attempt on an already
        # executed signal is better explained as a duplicate than as a status
        # complaint about the status the first attempt caused.
        check_duplicate_execution(request, resolved_context),
        check_signal_lifecycle(request, resolved_context),
        check_model_promotion(resolved_context),
        check_funded_rules(resolved_context),
        check_risk_limits(resolved_context),
        check_execution_mode(mode_decision),
    )
    reasons = tuple(reason for reason in candidates if reason is not None)

    blocking = tuple(reason for reason in reasons if reason.is_blocking)
    blocking_sources = tuple(
        dict.fromkeys(reason.source.value for reason in blocking)
    )

    return PaperExecutionEligibilityDecision(
        is_allowed=not blocking,
        requested_execution_mode=requested_mode,
        effective_execution_mode=mode_decision.effective,
        user_id=request.user_id,
        account_id=request.account_id,
        symbol=request.symbol,
        blocking_sources=blocking_sources,
        reasons=reasons,
        signal_id=request.signal_id,
        decision_metadata={
            "execution_mode_decision": mode_decision.to_dict(),
            "context": resolved_context.to_dict(),
            "evaluated_at_utc": (
                resolved_context.evaluated_at_utc.isoformat()
                if resolved_context.evaluated_at_utc is not None
                else None
            ),
        },
    )


__all__ = [
    "AQOS_PAPER_ELIGIBILITY_VERSION",
    "EXECUTABLE_SIGNAL_STATUS",
    "PAPER_TRADING_PROMOTION_STAGE",
    "PaperEligibilityContext",
    "PaperEligibilityReason",
    "PaperEligibilitySource",
    "PaperExecutionEligibilityDecision",
    "ACCOUNT_LEVEL_REJECTIONS",
    "REQUIRED_PAPER_EXECUTION_MODES",
    "SHAPE_REJECTION_CODES",
    "build_account_execution_constraint",
    "build_settings_execution_constraint",
    "check_account_is_paper",
    "check_account_status",
    "check_duplicate_execution",
    "check_execution_mode",
    "check_funded_rules",
    "check_market_data",
    "check_model_promotion",
    "check_request_shape",
    "check_risk_limits",
    "check_signal_lifecycle",
    "check_symbol",
    "collect_execution_constraints",
    "evaluate_paper_execution_eligibility",
]
