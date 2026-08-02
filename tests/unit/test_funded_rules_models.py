from __future__ import annotations

from datetime import datetime

import pytest

from aqos.accounts.models import AccountStatus, AccountType, BrokerKind, TradingAccount
from aqos.execution_policy.modes import (
    ExecutionConstraintSource,
    ExecutionMode,
    resolve_execution_mode,
)
from aqos.funded_rules.evaluation import (
    FundedAccountState,
    FundedRuleCheck,
    FundedRuleSeverity,
    FundedTradeRequest,
    build_funded_payout_status,
    calculate_daily_loss_fraction,
    calculate_profit_fraction,
    calculate_total_drawdown_fraction,
    evaluate_funded_account_state,
    evaluate_funded_rules,
    evaluate_funded_trade_request,
    resolve_drawdown_reference,
)
from aqos.funded_rules.models import (
    AQOS_FUNDED_RULES_VERSION,
    BLOCKING_FUNDED_RULE_STATUSES,
    DrawdownBasis,
    FundedAccountRules,
    FundedRuleStatus,
    FundedRuleTemplate,
    normalize_allowed_symbols,
    normalize_rule_name,
)
from aqos.trading_settings.models import TradingSettings


FIXED_NOW = datetime(2026, 1, 1, 0, 0, 0)

BASE_RULE_VALUES = {
    "max_daily_loss_fraction": 0.05,
    "max_total_drawdown_fraction": 0.10,
    "profit_target_fraction": 0.10,
    "max_risk_per_trade_fraction": 0.01,
    "min_lot_size": 0.01,
    "max_lot_size": 5.0,
    "max_open_positions": 3,
    "max_daily_trades": 10,
    "min_trading_days": 5,
}


def build_rules(**overrides) -> FundedAccountRules:
    payload = {
        "rules_id": "rules_1",
        "account_id": "account_1",
        "status": FundedRuleStatus.ACTIVE,
        "execution_mode": ExecutionMode.SIGNAL_ONLY,
        "drawdown_basis": DrawdownBasis.STATIC_INITIAL,
        "allowed_symbols": [],
        **BASE_RULE_VALUES,
    }
    payload.update(overrides)

    return FundedAccountRules(**payload)


def build_template(**overrides) -> FundedRuleTemplate:
    payload = {
        "template_id": "template_1",
        "name": "Conservative 100k",
        "execution_mode": ExecutionMode.SIGNAL_ONLY,
        "drawdown_basis": DrawdownBasis.STATIC_INITIAL,
        "allowed_symbols": [],
        **BASE_RULE_VALUES,
    }
    payload.update(overrides)

    return FundedRuleTemplate(**payload)


def build_state(**overrides) -> FundedAccountState:
    payload = {
        "initial_balance": 100_000.0,
        "current_balance": 100_000.0,
        "equity": 100_000.0,
    }
    payload.update(overrides)

    return FundedAccountState(**payload)


def build_request(**overrides) -> FundedTradeRequest:
    payload = {"symbol": "XAUUSD", "lot_size": 1.0, "risk_fraction": 0.005}
    payload.update(overrides)

    return FundedTradeRequest(**payload)


def build_settings(execution_mode: ExecutionMode) -> TradingSettings:
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


def build_account(execution_mode: ExecutionMode) -> TradingAccount:
    return TradingAccount(
        account_id="account_1",
        user_id="user_1",
        name="Funded 100k",
        account_type=AccountType.FUNDED,
        broker=BrokerKind.MT5,
        status=AccountStatus.ACTIVE,
        execution_mode=execution_mode,
        currency="USD",
        initial_balance=100_000.0,
        current_balance=100_000.0,
        equity=100_000.0,
        leverage=1,
    )


def test_funded_rules_version_is_exposed() -> None:
    assert AQOS_FUNDED_RULES_VERSION == "1.0"


def test_no_prop_firm_is_hardcoded() -> None:
    """Templates are configuration, so AQOS must not name any firm in code."""

    from pathlib import Path

    package = Path(__file__).resolve().parents[2] / "src" / "aqos" / "funded_rules"
    firm_names = ("ftmo", "the5ers", "myforexfunds", "mff", "fundednext", "e8")

    for path in package.rglob("*.py"):
        content = path.read_text(encoding="utf-8").lower()

        for firm in firm_names:
            assert firm not in content, f"{path.name} references {firm}"


def test_transient_rules_carry_every_default() -> None:
    """
    SQLAlchemy defaults only apply at flush time.

    A rule set built but not yet saved must still behave like a saved one,
    otherwise an omitted field reads as None and a restriction silently
    evaluates as "off".
    """

    minimal = FundedAccountRules(rules_id="rules_x", account_id="account_x")

    assert minimal.status == FundedRuleStatus.ACTIVE
    assert minimal.execution_mode == ExecutionMode.SIGNAL_ONLY
    assert minimal.news_restriction_enabled is True
    assert minimal.news_blackout_minutes_before == 2
    assert minimal.weekend_holding_allowed is False
    assert minimal.allowed_symbols == []
    assert minimal.max_open_positions >= 1

    minimal.assert_no_unset_rule_fields()


def test_transient_template_carries_every_default() -> None:
    minimal = FundedRuleTemplate(template_id="template_x", name="Minimal")

    assert minimal.is_active is True
    assert minimal.news_restriction_enabled is True
    assert minimal.to_dict()["is_active"] is True

    minimal.assert_no_unset_rule_fields()


def test_news_restriction_is_never_skipped_by_an_unset_field() -> None:
    """The regression this guard exists for."""

    rules = FundedAccountRules(rules_id="rules_x", account_id="account_x")

    evaluation = evaluate_funded_trade_request(
        rules,
        build_state(),
        build_request(minutes_to_high_impact_news=0.0),
    )

    assert evaluation.passed is False
    assert FundedRuleCheck.NEWS_BLACKOUT in {
        violation.check for violation in evaluation.breaches
    }


def test_unset_rule_fields_are_rejected() -> None:
    rules = build_rules()
    rules.news_restriction_enabled = None

    with pytest.raises(ValueError, match="must never be unset"):
        rules.assert_no_unset_rule_fields()

    with pytest.raises(ValueError, match="must never be unset"):
        rules.validate_consistency()


def test_normalize_rule_name() -> None:
    assert normalize_rule_name("  Conservative 100k ") == "Conservative 100k"

    with pytest.raises(ValueError, match="name cannot be empty"):
        normalize_rule_name("   ")


def test_normalize_allowed_symbols() -> None:
    assert normalize_allowed_symbols([" xau usd ", "XAUUSD", "eurusd"]) == [
        "XAUUSD",
        "EURUSD",
    ]
    assert normalize_allowed_symbols(None) == []

    with pytest.raises(ValueError, match="allowed symbol cannot be empty"):
        normalize_allowed_symbols(["  "])


def test_rules_validate_fractions() -> None:
    with pytest.raises(ValueError, match="max_daily_loss_fraction must be"):
        build_rules(max_daily_loss_fraction=0.0)

    with pytest.raises(ValueError, match="max_total_drawdown_fraction must be"):
        build_rules(max_total_drawdown_fraction=1.5)

    with pytest.raises(ValueError, match="max_risk_per_trade_fraction must be"):
        build_rules(max_risk_per_trade_fraction=0.0)

    with pytest.raises(ValueError, match="profit_target_fraction must be positive"):
        build_rules(profit_target_fraction=0.0)

    with pytest.raises(ValueError, match="consistency_fraction must be"):
        build_rules(consistency_fraction=1.5)


def test_rules_validate_limits() -> None:
    with pytest.raises(ValueError, match="min_lot_size must be positive"):
        build_rules(min_lot_size=0.0)

    with pytest.raises(ValueError, match="max_open_positions must be at least 1"):
        build_rules(max_open_positions=0)

    with pytest.raises(ValueError, match="max_daily_trades must be at least 1"):
        build_rules(max_daily_trades=0)

    with pytest.raises(ValueError, match="min_trading_days cannot be negative"):
        build_rules(min_trading_days=-1)

    with pytest.raises(
        ValueError,
        match="news_blackout_minutes_before cannot be negative",
    ):
        build_rules(news_blackout_minutes_before=-1)


def test_cross_field_consistency() -> None:
    with pytest.raises(ValueError, match="cannot exceed max_total_drawdown_fraction"):
        build_rules(
            max_daily_loss_fraction=0.20,
            max_total_drawdown_fraction=0.10,
        ).validate_consistency()

    with pytest.raises(ValueError, match="max_lot_size cannot be smaller"):
        build_rules(min_lot_size=2.0, max_lot_size=1.0).validate_consistency()

    build_rules().validate_consistency()


def test_template_and_rules_share_the_same_shape() -> None:
    template = build_template()
    rules = build_rules()

    assert set(template.rule_values()) == set(rules.rule_values())


def test_template_rule_values_can_seed_an_assignment() -> None:
    template = build_template(
        max_daily_loss_fraction=0.03,
        max_lot_size=2.0,
        allowed_symbols=["XAUUSD"],
    )

    rules = FundedAccountRules(
        rules_id="rules_2",
        account_id="account_2",
        template_id=template.template_id,
        **template.rule_values(),
    )

    assert float(rules.max_daily_loss_fraction) == pytest.approx(0.03)
    assert float(rules.max_lot_size) == pytest.approx(2.0)
    assert rules.allowed_symbols == ["XAUUSD"]


def test_allows_symbol() -> None:
    assert build_rules().allows_symbol("ANYTHING") is True

    restricted = build_rules(allowed_symbols=["XAUUSD", "EURUSD"])

    assert restricted.allows_symbol("xau usd") is True
    assert restricted.allows_symbol("BTCUSD") is False


def test_breach_record_requires_a_timestamp() -> None:
    rules = build_rules(status=FundedRuleStatus.BREACHED)

    with pytest.raises(ValueError, match="breached_at_utc is required"):
        rules.validate_breach_record()

    rules.breached_at_utc = FIXED_NOW
    rules.validate_breach_record()


def test_active_rules_contribute_their_configured_ceiling() -> None:
    assert build_rules(
        execution_mode=ExecutionMode.MANUAL_APPROVAL
    ).execution_ceiling() == ExecutionMode.MANUAL_APPROVAL


def test_breached_rules_contribute_disabled() -> None:
    rules = build_rules(
        status=FundedRuleStatus.BREACHED,
        breached_at_utc=FIXED_NOW,
        execution_mode=ExecutionMode.AUTO_TRADE,
    )

    assert rules.is_breached is True
    assert rules.is_blocking is True
    assert rules.execution_ceiling() == ExecutionMode.DISABLED


def test_disabled_rules_contribute_disabled() -> None:
    rules = build_rules(
        status=FundedRuleStatus.DISABLED,
        execution_mode=ExecutionMode.AUTO_TRADE,
    )

    assert rules.is_blocking is True
    assert rules.execution_ceiling() == ExecutionMode.DISABLED
    assert set(BLOCKING_FUNDED_RULE_STATUSES) == {
        FundedRuleStatus.BREACHED,
        FundedRuleStatus.DISABLED,
    }


def test_passed_rules_still_contribute_their_ceiling() -> None:
    rules = build_rules(
        status=FundedRuleStatus.PASSED,
        execution_mode=ExecutionMode.MANUAL_APPROVAL,
    )

    assert rules.is_blocking is False
    assert rules.execution_ceiling() == ExecutionMode.MANUAL_APPROVAL


def test_funded_constraint_payload() -> None:
    constraint = build_rules(
        execution_mode=ExecutionMode.SIGNAL_ONLY
    ).execution_constraint()

    assert constraint.source == ExecutionConstraintSource.FUNDED_RULE
    assert constraint.ceiling == ExecutionMode.SIGNAL_ONLY
    assert "signal_only" in (constraint.reason or "")


def test_breached_constraint_explains_the_breach() -> None:
    constraint = build_rules(
        status=FundedRuleStatus.BREACHED,
        breached_at_utc=FIXED_NOW,
        breach_reason="Maximum daily loss exceeded.",
    ).execution_constraint()

    assert constraint.ceiling == ExecutionMode.DISABLED
    assert constraint.reason == "Maximum daily loss exceeded."


def test_disabled_constraint_explains_the_status() -> None:
    constraint = build_rules(status=FundedRuleStatus.DISABLED).execution_constraint()

    assert constraint.ceiling == ExecutionMode.DISABLED
    assert "disabled" in (constraint.reason or "")


def test_three_ceilings_resolve_to_the_strictest() -> None:
    """The scenario from the Sprint 043 brief."""

    decision = resolve_execution_mode(
        requested=ExecutionMode.AUTO_TRADE,
        constraints=(
            build_settings(ExecutionMode.AUTO_TRADE).execution_constraint(),
            build_account(ExecutionMode.MANUAL_APPROVAL).execution_constraint(),
            build_rules(
                execution_mode=ExecutionMode.SIGNAL_ONLY
            ).execution_constraint(),
        ),
    )

    assert decision.effective == ExecutionMode.SIGNAL_ONLY
    assert decision.was_downgraded is True
    assert decision.allows_orders is False
    assert decision.binding_sources == ("funded_rule",)
    assert (
        decision.explain()
        == "Execution mode downgraded from auto_trade to signal_only by: "
        "funded_rule=signal_only"
    )


def test_breached_funded_rules_resolve_to_disabled() -> None:
    decision = resolve_execution_mode(
        requested=ExecutionMode.AUTO_TRADE,
        constraints=(
            build_settings(ExecutionMode.AUTO_TRADE).execution_constraint(),
            build_account(ExecutionMode.AUTO_TRADE).execution_constraint(),
            build_rules(
                status=FundedRuleStatus.BREACHED,
                breached_at_utc=FIXED_NOW,
                breach_reason="Maximum total drawdown exceeded.",
                execution_mode=ExecutionMode.AUTO_TRADE,
            ).execution_constraint(),
        ),
    )

    assert decision.effective == ExecutionMode.DISABLED
    assert decision.allows_orders is False
    assert decision.binding_sources == ("funded_rule",)
    assert "funded_rule=disabled" in decision.explain()


def test_disabled_funded_rules_resolve_to_disabled() -> None:
    decision = resolve_execution_mode(
        requested=ExecutionMode.MANUAL_APPROVAL,
        constraints=(
            build_settings(ExecutionMode.AUTO_TRADE).execution_constraint(),
            build_account(ExecutionMode.MANUAL_APPROVAL).execution_constraint(),
            build_rules(status=FundedRuleStatus.DISABLED).execution_constraint(),
        ),
    )

    assert decision.effective == ExecutionMode.DISABLED
    assert decision.binding_sources == ("funded_rule",)


def test_drawdown_reference_per_basis() -> None:
    state = build_state(peak_equity=110_000.0, peak_balance=105_000.0)

    assert resolve_drawdown_reference(build_rules(), state) == 100_000.0
    assert resolve_drawdown_reference(
        build_rules(drawdown_basis=DrawdownBasis.TRAILING_EQUITY),
        state,
    ) == 110_000.0
    assert resolve_drawdown_reference(
        build_rules(drawdown_basis=DrawdownBasis.TRAILING_BALANCE),
        state,
    ) == 105_000.0


def test_total_drawdown_fraction() -> None:
    assert calculate_total_drawdown_fraction(
        build_rules(),
        build_state(equity=93_000.0),
    ) == pytest.approx(0.07)

    assert calculate_total_drawdown_fraction(
        build_rules(),
        build_state(equity=105_000.0),
    ) == 0.0


def test_daily_loss_uses_the_worse_of_realized_and_equity() -> None:
    assert calculate_daily_loss_fraction(
        build_state(
            equity=97_000.0,
            daily_start_balance=100_000.0,
            daily_realized_pnl=-2_000.0,
        )
    ) == pytest.approx(0.03)

    assert calculate_daily_loss_fraction(
        build_state(
            equity=100_000.0,
            daily_start_balance=100_000.0,
            daily_realized_pnl=-4_000.0,
        )
    ) == pytest.approx(0.04)

    assert calculate_daily_loss_fraction(build_state()) == 0.0


def test_state_validation() -> None:
    with pytest.raises(ValueError, match="initial_balance must be positive"):
        build_state(initial_balance=0.0)

    with pytest.raises(ValueError, match="trades_today cannot be negative"):
        build_state(trades_today=-1)

    with pytest.raises(ValueError, match="trading_days cannot be negative"):
        build_state(trading_days=-1)


def test_request_validation() -> None:
    with pytest.raises(ValueError, match="symbol cannot be empty"):
        build_request(symbol=" ")

    with pytest.raises(ValueError, match="lot_size must be positive"):
        build_request(lot_size=0.0)

    with pytest.raises(ValueError, match="risk_fraction cannot be negative"):
        build_request(risk_fraction=-0.1)


def test_account_state_passes_within_limits() -> None:
    evaluation = evaluate_funded_account_state(build_rules(), build_state())

    assert evaluation.passed is True
    assert evaluation.violations == ()


def test_total_drawdown_breach() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(),
        build_state(equity=89_000.0),
    )

    assert evaluation.passed is False
    assert evaluation.breaches[0].check == FundedRuleCheck.MAX_TOTAL_DRAWDOWN

    with pytest.raises(ValueError, match="Funded account rules breached"):
        evaluation.raise_if_breached()


def test_total_drawdown_warning_before_breach() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(),
        build_state(equity=91_500.0, daily_start_balance=92_000.0),
    )

    assert evaluation.passed is True
    assert evaluation.warnings[0].check == FundedRuleCheck.MAX_TOTAL_DRAWDOWN
    assert evaluation.warnings[0].severity == FundedRuleSeverity.WARNING


def test_daily_loss_breach() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(),
        build_state(equity=94_500.0, daily_start_balance=100_000.0),
    )

    assert any(
        violation.check == FundedRuleCheck.MAX_DAILY_LOSS and violation.is_breach
        for violation in evaluation.violations
    )


def test_consistency_rule_warns_on_concentrated_profit() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(consistency_fraction=0.40),
        build_state(
            equity=110_000.0,
            largest_daily_profit=6_000.0,
            total_profit=10_000.0,
        ),
    )

    assert evaluation.passed is True
    assert evaluation.warnings[0].check == FundedRuleCheck.CONSISTENCY


def test_consistency_rule_can_be_disabled() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(consistency_fraction=None),
        build_state(
            equity=110_000.0,
            largest_daily_profit=9_000.0,
            total_profit=10_000.0,
        ),
    )

    assert evaluation.violations == ()


def test_trade_request_passes_when_compliant() -> None:
    assert evaluate_funded_trade_request(
        build_rules(),
        build_state(),
        build_request(),
    ).passed is True


@pytest.mark.parametrize(
    ("rule_overrides", "state_overrides", "request_overrides", "expected_check"),
    [
        ({"max_lot_size": 2.0}, {}, {"lot_size": 3.0}, FundedRuleCheck.MAX_LOT_SIZE),
        ({"min_lot_size": 0.1}, {}, {"lot_size": 0.05}, FundedRuleCheck.MIN_LOT_SIZE),
        (
            {"max_risk_per_trade_fraction": 0.01},
            {},
            {"risk_fraction": 0.05},
            FundedRuleCheck.MAX_RISK_PER_TRADE,
        ),
        (
            {"max_open_positions": 2},
            {"open_position_count": 2},
            {},
            FundedRuleCheck.MAX_OPEN_POSITIONS,
        ),
        (
            {"max_daily_trades": 3},
            {"trades_today": 3},
            {},
            FundedRuleCheck.MAX_DAILY_TRADES,
        ),
        (
            {"allowed_symbols": ["EURUSD"]},
            {},
            {"symbol": "BTCUSD"},
            FundedRuleCheck.SYMBOL_NOT_ALLOWED,
        ),
        ({}, {}, {"holds_over_weekend": True}, FundedRuleCheck.WEEKEND_HOLDING),
        (
            {"news_blackout_minutes_before": 5},
            {},
            {"minutes_to_high_impact_news": 2.0},
            FundedRuleCheck.NEWS_BLACKOUT,
        ),
    ],
)
def test_trade_request_breaches(
    rule_overrides: dict,
    state_overrides: dict,
    request_overrides: dict,
    expected_check: FundedRuleCheck,
) -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(**rule_overrides),
        build_state(**state_overrides),
        build_request(**request_overrides),
    )

    assert evaluation.passed is False
    assert expected_check in {violation.check for violation in evaluation.breaches}


def test_news_blackout_covers_both_sides_of_the_release() -> None:
    rules = build_rules(
        news_blackout_minutes_before=5,
        news_blackout_minutes_after=3,
    )

    assert evaluate_funded_trade_request(
        rules,
        build_state(),
        build_request(minutes_to_high_impact_news=-1.0),
    ).passed is False

    assert evaluate_funded_trade_request(
        rules,
        build_state(),
        build_request(minutes_to_high_impact_news=30.0),
    ).passed is True


def test_news_restriction_can_be_disabled() -> None:
    assert evaluate_funded_trade_request(
        build_rules(news_restriction_enabled=False),
        build_state(),
        build_request(minutes_to_high_impact_news=0.0),
    ).passed is True


def test_weekend_holding_can_be_allowed() -> None:
    assert evaluate_funded_trade_request(
        build_rules(weekend_holding_allowed=True),
        build_state(),
        build_request(holds_over_weekend=True),
    ).passed is True


def test_evaluate_funded_rules_merges_account_and_trade_checks() -> None:
    evaluation = evaluate_funded_rules(
        build_rules(max_lot_size=1.0),
        build_state(equity=89_000.0),
        build_request(lot_size=5.0),
    )

    checks = {violation.check for violation in evaluation.breaches}

    assert FundedRuleCheck.MAX_TOTAL_DRAWDOWN in checks
    assert FundedRuleCheck.MAX_LOT_SIZE in checks
    assert evaluation.passed is False
    assert evaluation.breach_summary()


def test_evaluate_funded_rules_without_a_request() -> None:
    evaluation = evaluate_funded_rules(build_rules(), build_state())

    assert evaluation.passed is True
    assert FundedRuleCheck.MAX_LOT_SIZE not in evaluation.checks_run


def test_profit_and_payout_status() -> None:
    state = build_state(equity=112_000.0, trading_days=7)

    assert calculate_profit_fraction(state) == pytest.approx(0.12)

    status = build_funded_payout_status(build_rules(), state)

    assert status.profit_target_met is True
    assert status.trading_days_met is True
    assert status.rules_passed is True
    assert status.payout_eligible is True
    assert status.remaining_trading_days == 0


def test_payout_blocked_by_trading_days() -> None:
    status = build_funded_payout_status(
        build_rules(),
        build_state(equity=115_000.0, trading_days=2),
    )

    assert status.payout_eligible is False
    assert status.remaining_trading_days == 3
    assert status.to_dict()["payout_eligible"] is False


def test_rules_dict_payload() -> None:
    payload = build_rules(
        status=FundedRuleStatus.BREACHED,
        breached_at_utc=FIXED_NOW,
        breach_reason="Maximum daily loss exceeded.",
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
    ).to_dict()

    assert payload["status"] == "breached"
    assert payload["execution_ceiling"] == "disabled"
    assert payload["is_breached"] is True
    assert payload["breach_reason"] == "Maximum daily loss exceeded."
    assert payload["drawdown_basis"] == "static_initial"
    assert "account_1" in repr(build_rules())


def test_template_dict_payload() -> None:
    payload = build_template(
        description="Conservative limits",
        created_at_utc=FIXED_NOW,
        updated_at_utc=FIXED_NOW,
    ).to_dict()

    assert payload["name"] == "Conservative 100k"
    assert payload["description"] == "Conservative limits"
    assert payload["is_active"] is True
    assert payload["execution_mode"] == "signal_only"
    assert "Conservative 100k" in repr(build_template())
