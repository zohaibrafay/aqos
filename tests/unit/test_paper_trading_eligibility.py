"""Unit tests for the paper execution rule gate."""

from __future__ import annotations

from datetime import datetime

import pytest

from aqos.accounts.models import AccountStatus, AccountType, BrokerKind, TradingAccount
from aqos.execution_policy.modes import (
    ExecutionConstraint,
    ExecutionConstraintSource,
    ExecutionMode,
)
from aqos.funded_rules.evaluation import (
    FundedRuleCheck,
    FundedRuleEvaluation,
    FundedRuleSeverity,
    FundedRuleViolation,
)
from aqos.model_training.model_evaluation import ModelPromotionStage
from aqos.paper_trading.contracts import (
    PaperAction,
    PaperExecutionRequest,
    PaperOrderType,
    PaperRejectionReason,
    PaperTradingError,
)
from aqos.paper_trading.eligibility import (
    AQOS_PAPER_ELIGIBILITY_VERSION,
    EXECUTABLE_SIGNAL_STATUS,
    PAPER_TRADING_PROMOTION_STAGE,
    PaperEligibilityContext,
    PaperEligibilityReason,
    PaperEligibilitySource,
    PaperExecutionEligibilityDecision,
    REQUIRED_PAPER_EXECUTION_MODES,
    collect_execution_constraints,
    evaluate_paper_execution_eligibility,
)
from aqos.signal_reasons.taxonomy import (
    SignalReasonCategory,
    SignalReasonCode,
    SignalReasonSeverity,
)
from aqos.signals.models import SignalAction, SignalSource, SignalStatus, TradingSignal
from aqos.trading_settings.models import TradingSettings


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)


def build_account(**overrides) -> TradingAccount:
    payload = {
        "account_id": "account_1",
        "user_id": "user_1",
        "name": "Paper One",
        "account_type": AccountType.PAPER,
        "broker": BrokerKind.INTERNAL_PAPER,
        "status": AccountStatus.ACTIVE,
        "execution_mode": ExecutionMode.AUTO_TRADE,
        "auto_trade_enabled": True,
        "currency": "USD",
        "initial_balance": 10_000.0,
        "current_balance": 10_000.0,
        "equity": 10_000.0,
        "leverage": 1,
    }
    payload.update(overrides)

    return TradingAccount(**payload)


def build_settings(
    execution_mode: ExecutionMode = ExecutionMode.AUTO_TRADE,
) -> TradingSettings:
    return TradingSettings(
        settings_id="settings_1",
        user_id="user_1",
        execution_mode=execution_mode,
        risk_per_trade_fraction=0.01,
        max_daily_loss_fraction=0.05,
        max_open_positions=3,
        max_daily_trades=10,
        default_timeframe="H1",
    )


def build_signal(
    status: SignalStatus = SignalStatus.APPROVED,
    model_id: str | None = None,
    signal_id: str = "signal_1",
) -> TradingSignal:
    return TradingSignal(
        signal_id=signal_id,
        user_id="user_1",
        account_id="account_1",
        symbol="XAUUSD",
        timeframe="H1",
        action=SignalAction.BUY,
        status=status,
        source=SignalSource.ML_MODEL if model_id else SignalSource.MANUAL,
        model_id=model_id,
        model_version="1.0" if model_id else None,
        generated_at_utc=FIXED_NOW,
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
    )


def build_request(**overrides) -> PaperExecutionRequest:
    payload = {
        "user_id": "user_1",
        "account_id": "account_1",
        "symbol": "XAUUSD",
        "action": PaperAction.BUY,
        "quantity": 2.0,
        "order_type": PaperOrderType.MARKET,
        "submitted_at_utc": FIXED_NOW,
    }
    payload.update(overrides)

    return PaperExecutionRequest(**payload)


def build_breached_funded_evaluation() -> FundedRuleEvaluation:
    return FundedRuleEvaluation(
        account_id="account_1",
        violations=(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_DAILY_LOSS,
                severity=FundedRuleSeverity.BREACH,
                message="Daily loss limit breached.",
            ),
        ),
        checks_run=(FundedRuleCheck.MAX_DAILY_LOSS,),
    )


def evaluate(**overrides) -> PaperExecutionEligibilityDecision:
    """Evaluate with an everything-permitted baseline unless overridden."""

    request = overrides.pop("request", None) or build_request()
    account = overrides.pop("account", None) or build_account()
    requested_mode = overrides.pop("requested_mode", ExecutionMode.AUTO_TRADE)
    extra_constraints = overrides.pop("extra_constraints", ())

    context = overrides.pop("context", None) or PaperEligibilityContext(
        settings=build_settings(),
        **overrides,
    )

    return evaluate_paper_execution_eligibility(
        request=request,
        account=account,
        context=context,
        requested_mode=requested_mode,
        extra_constraints=extra_constraints,
    )


def test_module_version_is_declared() -> None:
    assert AQOS_PAPER_ELIGIBILITY_VERSION == "1.0"


def test_only_approved_signals_may_execute() -> None:
    assert EXECUTABLE_SIGNAL_STATUS == SignalStatus.APPROVED


def test_paper_execution_requires_an_order_capable_mode() -> None:
    assert REQUIRED_PAPER_EXECUTION_MODES == (
        ExecutionMode.MANUAL_APPROVAL,
        ExecutionMode.AUTO_TRADE,
    )


class TestPaperEligibilityReason:
    def test_category_and_severity_come_from_the_taxonomy(self) -> None:
        reason = PaperEligibilityReason(
            code=SignalReasonCode.FUNDED_RULE_BREACHED,
            source=PaperEligibilitySource.FUNDED_RULE,
        )

        assert reason.category == SignalReasonCategory.FUNDED_RULE
        assert reason.severity == SignalReasonSeverity.CRITICAL

    def test_the_message_falls_back_to_the_taxonomy_default(self) -> None:
        reason = PaperEligibilityReason(
            code=SignalReasonCode.SYMBOL_BLOCKED,
            source=PaperEligibilitySource.SYMBOL_PREFERENCES,
        )

        assert reason.resolved_message == "Symbol is blocked for this user."

    def test_to_dict_carries_the_structured_fields(self) -> None:
        payload = PaperEligibilityReason(
            code=SignalReasonCode.RISK_LIMIT_EXCEEDED,
            source=PaperEligibilitySource.RISK_ENGINE,
            message="Daily loss cap reached.",
            details={"limit": 0.05},
        ).to_dict()

        assert payload["code"] == "risk_limit_exceeded"
        assert payload["source"] == "risk_engine"
        assert payload["category"] == "risk"
        assert payload["severity"] == "blocking"
        assert payload["is_blocking"] is True
        assert payload["details"] == {"limit": 0.05}


class TestDecisionContract:
    def test_an_allowed_decision_cannot_carry_blocking_reasons(self) -> None:
        with pytest.raises(PaperTradingError, match="cannot carry blocking"):
            PaperExecutionEligibilityDecision(
                is_allowed=True,
                requested_execution_mode=ExecutionMode.AUTO_TRADE,
                effective_execution_mode=ExecutionMode.AUTO_TRADE,
                user_id="user_1",
                account_id="account_1",
                symbol="XAUUSD",
                reasons=(
                    PaperEligibilityReason(
                        code=SignalReasonCode.SYMBOL_BLOCKED,
                        source=PaperEligibilitySource.SYMBOL_PREFERENCES,
                    ),
                ),
            )

    def test_a_refused_decision_must_carry_a_blocking_reason(self) -> None:
        with pytest.raises(PaperTradingError, match="must carry a blocking"):
            PaperExecutionEligibilityDecision(
                is_allowed=False,
                requested_execution_mode=ExecutionMode.AUTO_TRADE,
                effective_execution_mode=ExecutionMode.AUTO_TRADE,
                user_id="user_1",
                account_id="account_1",
                symbol="XAUUSD",
            )

    def test_a_warning_does_not_block(self) -> None:
        decision = PaperExecutionEligibilityDecision(
            is_allowed=True,
            requested_execution_mode=ExecutionMode.AUTO_TRADE,
            effective_execution_mode=ExecutionMode.AUTO_TRADE,
            user_id="user_1",
            account_id="account_1",
            symbol="XAUUSD",
            reasons=(
                PaperEligibilityReason(
                    code=SignalReasonCode.SPREAD_TOO_HIGH,
                    source=PaperEligibilitySource.VALIDATION,
                    is_blocking=False,
                ),
            ),
        )

        assert decision.blocking_reasons == ()
        assert len(decision.warnings) == 1

    def test_raise_if_blocked_is_quiet_when_allowed(self) -> None:
        evaluate().raise_if_blocked()

    def test_raise_if_blocked_raises_when_refused(self) -> None:
        decision = evaluate(account=build_account(status=AccountStatus.SUSPENDED))

        with pytest.raises(PaperTradingError, match="account_suspended"):
            decision.raise_if_blocked()


class TestAccountRules:
    def test_a_paper_account_is_allowed(self) -> None:
        decision = evaluate()

        assert decision.is_allowed is True
        assert decision.reasons == ()
        assert decision.blocking_sources == ()
        assert decision.effective_execution_mode == ExecutionMode.AUTO_TRADE

    @pytest.mark.parametrize(
        "account_type",
        [
            AccountType.LIVE,
            AccountType.FUNDED,
            AccountType.DEMO,
        ],
    )
    def test_a_non_paper_account_is_refused(self, account_type) -> None:
        """Paper execution stays paper-only, whatever the account is."""

        decision = evaluate(account=build_account(account_type=account_type))

        assert decision.is_allowed is False
        assert decision.reason_codes[0] == "account_not_paper"
        assert "account_type" in decision.blocking_sources

    @pytest.mark.parametrize(
        "broker",
        [BrokerKind.MT5, BrokerKind.BINANCE, BrokerKind.EXNESS],
    )
    def test_a_broker_backed_live_account_is_refused(self, broker) -> None:
        decision = evaluate(
            account=build_account(
                account_type=AccountType.LIVE,
                broker=broker,
            )
        )

        assert decision.is_allowed is False
        assert "account_not_paper" in decision.reason_codes

    def test_a_suspended_account_is_refused(self) -> None:
        decision = evaluate(account=build_account(status=AccountStatus.SUSPENDED))

        assert decision.is_allowed is False
        assert decision.reason_codes == ("account_suspended",)

    def test_an_archived_account_is_refused_as_disabled(self) -> None:
        decision = evaluate(account=build_account(status=AccountStatus.ARCHIVED))

        assert decision.is_allowed is False
        assert decision.reason_codes == ("account_disabled",)


class TestSymbolRules:
    def test_a_blocked_symbol_is_refused(self) -> None:
        decision = evaluate(blocked_symbols=("XAUUSD",))

        assert decision.is_allowed is False
        assert decision.reason_codes == ("symbol_blocked",)
        assert decision.blocking_sources == ("symbol_preferences",)

    def test_blocked_symbols_are_matched_after_normalisation(self) -> None:
        decision = evaluate(blocked_symbols=("xau usd",))

        assert decision.is_allowed is False
        assert decision.reason_codes == ("symbol_blocked",)

    def test_an_unblocked_symbol_passes(self) -> None:
        assert evaluate(blocked_symbols=("EURUSD",)).is_allowed is True

    def test_a_symbol_outside_the_allow_list_is_invalid(self) -> None:
        decision = evaluate(allowed_symbols=("EURUSD", "BTCUSD"))

        assert decision.is_allowed is False
        assert decision.reason_codes == ("invalid_symbol",)

    def test_a_symbol_inside_the_allow_list_passes(self) -> None:
        assert evaluate(allowed_symbols=("XAUUSD",)).is_allowed is True

    def test_no_allow_list_means_no_restriction(self) -> None:
        assert evaluate(allowed_symbols=None).is_allowed is True


class TestMarketData:
    def test_a_matching_bar_passes(self) -> None:
        assert evaluate(market_data_symbol="XAUUSD").is_allowed is True

    def test_a_bar_for_another_instrument_is_refused(self) -> None:
        """Filling from the wrong bar would book a fictional price."""

        decision = evaluate(market_data_symbol="EURUSD")

        assert decision.is_allowed is False
        assert decision.reason_codes == ("invalid_symbol",)
        assert decision.blocking_sources == ("validation",)

    def test_the_bar_symbol_is_normalised_before_comparing(self) -> None:
        assert evaluate(market_data_symbol="xau usd").is_allowed is True

    def test_no_bar_symbol_means_no_check(self) -> None:
        assert evaluate(market_data_symbol=None).is_allowed is True

    def test_the_refusal_keeps_the_precise_order_level_reason(self) -> None:
        decision = evaluate(market_data_symbol="EURUSD")

        assert decision.primary_reason.order_rejection_reason == (
            PaperRejectionReason.INVALID_SYMBOL
        )


class TestRequestShape:
    def test_a_wrong_side_stop_loss_keeps_its_precise_reason(self) -> None:
        """
        Several shape failures share ``validation_failed``.

        The order row keeps the narrower enum so the detail is not lost when the
        shape check moved inside the gate.
        """

        decision = evaluate(
            request=build_request(
                order_type=PaperOrderType.LIMIT,
                requested_price=100.0,
                stop_loss=105.0,
            )
        )

        assert decision.is_allowed is False
        assert decision.reason_codes == ("validation_failed",)
        assert decision.primary_reason.order_rejection_reason == (
            PaperRejectionReason.INVALID_PRICE
        )

    def test_an_unsupported_price_free_limit_order_is_refused(self) -> None:
        decision = evaluate(
            request=build_request(order_type=PaperOrderType.LIMIT)
        )

        assert decision.is_allowed is False
        assert decision.primary_reason.order_rejection_reason == (
            PaperRejectionReason.MISSING_REQUIRED_FIELD
        )

    def test_account_level_shape_failures_are_not_reported_twice(self) -> None:
        """The account rules already cover these, so the shape check defers."""

        decision = evaluate(account=build_account(status=AccountStatus.SUSPENDED))

        assert decision.reason_codes == ("account_suspended",)

    def test_a_well_formed_request_passes_the_shape_check(self) -> None:
        assert evaluate().is_allowed is True


class TestSignalLifecycle:
    def test_a_request_without_a_signal_skips_the_lifecycle_check(self) -> None:
        assert evaluate().is_allowed is True

    def test_an_approved_signal_may_execute(self) -> None:
        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(SignalStatus.APPROVED),
        )

        assert decision.is_allowed is True

    @pytest.mark.parametrize(
        "status",
        [
            SignalStatus.GENERATED,
            SignalStatus.PENDING_APPROVAL,
            SignalStatus.REJECTED,
            SignalStatus.MISSED,
            SignalStatus.EXPIRED,
            SignalStatus.EXECUTED,
            SignalStatus.FAILED,
            SignalStatus.CANCELLED,
        ],
    )
    def test_every_other_status_is_refused(self, status: SignalStatus) -> None:
        """Paper execution must not bypass the Sprint 044 lifecycle."""

        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(status),
        )

        assert decision.is_allowed is False
        assert "validation_failed" in decision.reason_codes
        assert "signal_lifecycle" in decision.blocking_sources

    def test_a_missing_signal_is_refused_rather_than_assumed_fine(self) -> None:
        decision = evaluate(request=build_request(signal_id="signal_missing"))

        assert decision.is_allowed is False
        assert decision.reason_codes == ("validation_failed",)
        assert "was not found" in decision.primary_reason.resolved_message

    def test_a_mismatched_signal_is_refused(self) -> None:
        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(signal_id="signal_other"),
        )

        assert decision.is_allowed is False
        assert "different signals" in decision.primary_reason.resolved_message


class TestDuplicateExecution:
    def test_an_existing_execution_refuses_the_second_attempt(self) -> None:
        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(),
            has_existing_execution=True,
        )

        assert decision.is_allowed is False
        assert decision.reason_codes[0] == "duplicate_signal"
        assert decision.blocking_sources[0] == "duplicate_execution"

    def test_a_request_without_a_signal_cannot_be_a_duplicate(self) -> None:
        assert evaluate(has_existing_execution=True).is_allowed is True


class TestModelPromotion:
    def test_a_manual_signal_needs_no_promotion(self) -> None:
        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(),
        )

        assert decision.is_allowed is True

    def test_a_model_promoted_to_paper_trading_may_execute(self) -> None:
        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(model_id="model_1"),
            model_promotion_stage=PAPER_TRADING_PROMOTION_STAGE,
        )

        assert decision.is_allowed is True

    def test_a_model_promoted_further_may_execute(self) -> None:
        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(model_id="model_1"),
            model_promotion_stage=ModelPromotionStage.LIVE,
        )

        assert decision.is_allowed is True

    @pytest.mark.parametrize(
        "stage",
        [ModelPromotionStage.RESEARCH, ModelPromotionStage.BLOCKED],
    )
    def test_an_unpromoted_model_is_refused(self, stage) -> None:
        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(model_id="model_1"),
            model_promotion_stage=stage,
        )

        assert decision.is_allowed is False
        assert "unpromoted_model" in decision.reason_codes

    def test_an_unverifiable_model_is_treated_as_unpromoted(self) -> None:
        """A missing stage must fail closed, not sail through."""

        decision = evaluate(
            request=build_request(signal_id="signal_1"),
            signal=build_signal(model_id="model_1"),
            model_promotion_stage=None,
        )

        assert decision.is_allowed is False
        assert "unpromoted_model" in decision.reason_codes
        assert decision.primary_reason.details["promotion_stage"] is None


class TestFundedAndRisk:
    def test_a_passing_funded_evaluation_allows_execution(self) -> None:
        decision = evaluate(
            funded_evaluation=FundedRuleEvaluation(account_id="account_1")
        )

        assert decision.is_allowed is True

    def test_a_breached_funded_rule_refuses_the_simulation(self) -> None:
        """Funded rules constrain the simulation; they never make it funded."""

        decision = evaluate(funded_evaluation=build_breached_funded_evaluation())

        assert decision.is_allowed is False
        assert "funded_rule_breached" in decision.reason_codes
        assert "funded_rule" in decision.blocking_sources

    def test_a_breached_risk_limit_is_refused(self) -> None:
        decision = evaluate(
            risk_limit_breached=True,
            risk_limit_message="Daily loss cap reached.",
        )

        assert decision.is_allowed is False
        assert "risk_limit_exceeded" in decision.reason_codes

    def test_risk_limits_pass_by_default(self) -> None:
        assert evaluate().is_allowed is True


class TestResolverIntegration:
    def test_the_strictest_ceiling_wins(self) -> None:
        """requested=auto_trade, user=manual_approval, account=signal_only."""

        decision = evaluate(
            account=build_account(execution_mode=ExecutionMode.SIGNAL_ONLY),
            context=PaperEligibilityContext(
                settings=build_settings(ExecutionMode.MANUAL_APPROVAL),
            ),
        )

        assert decision.effective_execution_mode == ExecutionMode.SIGNAL_ONLY
        assert decision.is_allowed is False
        assert "auto_trade_not_allowed" in decision.reason_codes

    def test_manual_approval_still_permits_a_paper_order(self) -> None:
        decision = evaluate(
            account=build_account(execution_mode=ExecutionMode.MANUAL_APPROVAL),
            context=PaperEligibilityContext(
                settings=build_settings(ExecutionMode.MANUAL_APPROVAL),
            ),
        )

        assert decision.is_allowed is True
        assert decision.requires_manual_approval is True

    def test_a_disabled_mode_refuses_execution(self) -> None:
        decision = evaluate(
            account=build_account(execution_mode=ExecutionMode.DISABLED),
        )

        assert decision.effective_execution_mode == ExecutionMode.DISABLED
        assert decision.is_allowed is False

    def test_an_extra_constraint_can_lower_the_ceiling(self) -> None:
        decision = evaluate(
            extra_constraints=(
                ExecutionConstraint(
                    source=ExecutionConstraintSource.RISK_ENGINE,
                    ceiling=ExecutionMode.SIGNAL_ONLY,
                ),
            ),
        )

        assert decision.effective_execution_mode == ExecutionMode.SIGNAL_ONLY
        assert decision.is_allowed is False

    def test_the_account_ceiling_applies_without_any_extra_constraint(self) -> None:
        """The gate never resolves with an empty constraint set."""

        constraints = collect_execution_constraints(
            account=build_account(),
            context=PaperEligibilityContext(),
        )

        assert len(constraints) >= 1
        assert constraints[0].source == ExecutionConstraintSource.ACCOUNT

    def test_an_unpromoted_model_also_lowers_the_ceiling(self) -> None:
        constraints = collect_execution_constraints(
            account=build_account(),
            context=PaperEligibilityContext(
                model_promotion_stage=ModelPromotionStage.RESEARCH,
            ),
        )
        sources = {constraint.source for constraint in constraints}

        assert ExecutionConstraintSource.MODEL_PROMOTION in sources


class TestDecisionReporting:
    def test_several_rules_can_fire_at_once(self) -> None:
        """A caller fixing one problem should be able to see the rest."""

        decision = evaluate(
            account=build_account(
                account_type=AccountType.LIVE,
                status=AccountStatus.SUSPENDED,
            ),
            blocked_symbols=("XAUUSD",),
        )

        assert decision.is_allowed is False
        assert set(decision.reason_codes) == {
            "account_not_paper",
            "account_suspended",
            "symbol_blocked",
        }

    def test_the_primary_reason_is_the_first_blocking_one(self) -> None:
        decision = evaluate(
            account=build_account(account_type=AccountType.LIVE),
            blocked_symbols=("XAUUSD",),
        )

        assert decision.primary_reason.code == SignalReasonCode.ACCOUNT_NOT_PAPER

    def test_blocking_sources_are_deduplicated_and_ordered(self) -> None:
        decision = evaluate(
            account=build_account(
                account_type=AccountType.LIVE,
                status=AccountStatus.SUSPENDED,
            ),
        )

        assert decision.blocking_sources == ("account_type", "account")

    def test_the_rejection_message_names_further_codes(self) -> None:
        decision = evaluate(
            account=build_account(account_type=AccountType.LIVE),
            blocked_symbols=("XAUUSD",),
        )
        message = decision.rejection_message()

        assert message.startswith("account_not_paper:")
        assert "also: symbol_blocked" in message

    def test_the_rejection_message_is_plain_for_a_single_reason(self) -> None:
        message = evaluate(blocked_symbols=("XAUUSD",)).rejection_message()

        assert message.startswith("symbol_blocked:")
        assert "also:" not in message

    def test_an_allowed_decision_explains_itself(self) -> None:
        assert evaluate().explain() == "Paper execution allowed at auto_trade."

    def test_to_dict_carries_the_whole_decision(self) -> None:
        payload = evaluate(blocked_symbols=("XAUUSD",)).to_dict()

        assert payload["is_allowed"] is False
        assert payload["requested_execution_mode"] == "auto_trade"
        assert payload["effective_execution_mode"] == "auto_trade"
        assert payload["reason_codes"] == ["symbol_blocked"]
        assert payload["blocking_sources"] == ["symbol_preferences"]
        assert payload["symbol"] == "XAUUSD"
        assert payload["decision_metadata"]["execution_mode_decision"]

    def test_a_mismatched_account_is_a_programming_error(self) -> None:
        with pytest.raises(PaperTradingError, match="different accounts"):
            evaluate_paper_execution_eligibility(
                request=build_request(account_id="account_other"),
                account=build_account(),
            )

    def test_the_gate_runs_with_no_context_at_all(self) -> None:
        decision = evaluate_paper_execution_eligibility(
            request=build_request(),
            account=build_account(),
        )

        assert decision.is_allowed is True
