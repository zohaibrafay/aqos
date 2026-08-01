from __future__ import annotations

import pytest

from aqos.persistence.accounts import (
    AccountType,
    BrokerKind,
    TradingAccountRepository,
)
from aqos.persistence.database import AqosDatabase
from aqos.persistence.funded_rules import (
    AQOS_FUNDED_RULES_VERSION,
    DrawdownBasis,
    FundedAccountRules,
    FundedAccountRulesRepository,
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
from aqos.persistence.users import UserProfileRepository


@pytest.fixture
def funded_database() -> AqosDatabase:
    database = AqosDatabase()

    yield database

    database.close()


@pytest.fixture
def funded_account(funded_database):
    user = UserProfileRepository(funded_database).create_user(
        email="trader@example.com",
        display_name="Primary Trader",
        created_at_utc="2026-01-01T00:00:00Z",
    )

    return TradingAccountRepository(funded_database).create_account(
        user_id=user.user_id,
        name="Funded 100k",
        account_type=AccountType.FUNDED,
        broker=BrokerKind.MT5,
        initial_balance=100_000.0,
        created_at_utc="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def funded_rules_repository(funded_database) -> FundedAccountRulesRepository:
    return FundedAccountRulesRepository(funded_database)


def build_rules(**overrides) -> FundedAccountRules:
    payload = {
        "rules_id": "rules_1",
        "account_id": "account_1",
        "created_at_utc": "2026-01-01T00:00:00Z",
        "updated_at_utc": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)

    return FundedAccountRules(**payload)


def build_state(**overrides) -> FundedAccountState:
    payload = {
        "initial_balance": 100_000.0,
        "current_balance": 100_000.0,
        "equity": 100_000.0,
    }
    payload.update(overrides)

    return FundedAccountState(**payload)


def build_request(**overrides) -> FundedTradeRequest:
    payload = {
        "symbol": "XAUUSD",
        "lot_size": 1.0,
        "risk_fraction": 0.005,
    }
    payload.update(overrides)

    return FundedTradeRequest(**payload)


def test_funded_rules_version_is_exposed() -> None:
    assert AQOS_FUNDED_RULES_VERSION == "1.0"


def test_rules_validation_rejects_bad_identity() -> None:
    with pytest.raises(ValueError, match="rules_id cannot be empty"):
        build_rules(rules_id=" ")

    with pytest.raises(ValueError, match="account_id cannot be empty"):
        build_rules(account_id="")

    with pytest.raises(ValueError, match="created_at_utc cannot be empty"):
        build_rules(created_at_utc=" ")

    with pytest.raises(ValueError, match="updated_at_utc cannot be empty"):
        build_rules(updated_at_utc=" ")


def test_rules_validation_rejects_bad_fractions() -> None:
    with pytest.raises(ValueError, match="max_total_drawdown_fraction must be"):
        build_rules(max_total_drawdown_fraction=0.0)

    with pytest.raises(ValueError, match="max_daily_loss_fraction must be"):
        build_rules(max_daily_loss_fraction=1.5)

    with pytest.raises(ValueError, match="cannot exceed max_total_drawdown_fraction"):
        build_rules(max_total_drawdown_fraction=0.05, max_daily_loss_fraction=0.10)

    with pytest.raises(ValueError, match="max_risk_per_trade_fraction must be"):
        build_rules(max_risk_per_trade_fraction=0.0)

    with pytest.raises(ValueError, match="profit_target_fraction must be positive"):
        build_rules(profit_target_fraction=0.0)

    with pytest.raises(ValueError, match="consistency_fraction must be"):
        build_rules(consistency_fraction=1.5)


def test_rules_validation_rejects_bad_limits() -> None:
    with pytest.raises(ValueError, match="min_trading_days cannot be negative"):
        build_rules(min_trading_days=-1)

    with pytest.raises(ValueError, match="min_lot_size must be positive"):
        build_rules(min_lot_size=0.0)

    with pytest.raises(ValueError, match="max_lot_size cannot be smaller"):
        build_rules(min_lot_size=2.0, max_lot_size=1.0)

    with pytest.raises(ValueError, match="max_open_positions must be at least 1"):
        build_rules(max_open_positions=0)

    with pytest.raises(ValueError, match="news_blackout_minutes_before cannot"):
        build_rules(news_blackout_minutes_before=-1)

    with pytest.raises(ValueError, match="news_blackout_minutes_after cannot"):
        build_rules(news_blackout_minutes_after=-1)


def test_rules_symbol_allowance() -> None:
    unrestricted = build_rules()

    assert unrestricted.allows_symbol("ANYTHING") is True

    restricted = build_rules(allowed_symbols=("XAUUSD", "EURUSD"))

    assert restricted.allows_symbol("xauusd") is True
    assert restricted.allows_symbol("BTCUSD") is False


def test_rules_dict_payload() -> None:
    payload = build_rules().to_dict()

    assert payload["drawdown_basis"] == "static_initial"
    assert payload["news_restriction_enabled"] is True
    assert payload["weekend_holding_allowed"] is False
    assert payload["allowed_symbols"] == []


def test_state_validation() -> None:
    with pytest.raises(ValueError, match="initial_balance must be positive"):
        build_state(initial_balance=0.0)

    with pytest.raises(ValueError, match="current_balance cannot be negative"):
        build_state(current_balance=-1.0)

    with pytest.raises(ValueError, match="equity cannot be negative"):
        build_state(equity=-1.0)

    with pytest.raises(ValueError, match="open_position_count cannot be negative"):
        build_state(open_position_count=-1)

    with pytest.raises(ValueError, match="trading_days cannot be negative"):
        build_state(trading_days=-1)


def test_state_resolved_defaults() -> None:
    state = build_state()

    assert state.resolved_peak_equity == 100_000.0
    assert state.resolved_peak_balance == 100_000.0
    assert state.resolved_daily_start_balance == 100_000.0
    assert state.resolved_total_profit == 0.0
    assert state.to_dict()["total_profit"] == 0.0


def test_trade_request_validation() -> None:
    with pytest.raises(ValueError, match="symbol cannot be empty"):
        build_request(symbol=" ")

    with pytest.raises(ValueError, match="lot_size must be positive"):
        build_request(lot_size=0.0)

    with pytest.raises(ValueError, match="risk_fraction cannot be negative"):
        build_request(risk_fraction=-0.1)


def test_resolve_drawdown_reference_per_basis() -> None:
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


def test_calculate_total_drawdown_fraction() -> None:
    state = build_state(equity=93_000.0)

    assert calculate_total_drawdown_fraction(build_rules(), state) == pytest.approx(
        0.07
    )
    assert calculate_total_drawdown_fraction(
        build_rules(),
        build_state(equity=105_000.0),
    ) == 0.0


def test_trailing_drawdown_uses_peak() -> None:
    rules = build_rules(drawdown_basis=DrawdownBasis.TRAILING_EQUITY)
    state = build_state(equity=104_000.0, peak_equity=110_000.0)

    assert calculate_total_drawdown_fraction(rules, state) == pytest.approx(
        6_000.0 / 110_000.0
    )


def test_calculate_daily_loss_fraction() -> None:
    state = build_state(
        equity=97_000.0,
        daily_start_balance=100_000.0,
        daily_realized_pnl=-2_000.0,
    )

    assert calculate_daily_loss_fraction(state) == pytest.approx(0.03)
    assert calculate_daily_loss_fraction(build_state()) == 0.0


def test_daily_loss_uses_worst_of_realized_and_equity() -> None:
    state = build_state(
        equity=100_000.0,
        daily_start_balance=100_000.0,
        daily_realized_pnl=-4_000.0,
    )

    assert calculate_daily_loss_fraction(state) == pytest.approx(0.04)


def test_account_state_passes_when_within_limits() -> None:
    evaluation = evaluate_funded_account_state(build_rules(), build_state())

    assert evaluation.passed is True
    assert evaluation.violations == ()
    assert evaluation.to_dict()["breach_count"] == 0


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
    """Drawdown built up over earlier days, so only the total rule should warn."""

    evaluation = evaluate_funded_account_state(
        build_rules(),
        build_state(equity=91_500.0, daily_start_balance=92_000.0),
    )

    assert evaluation.passed is True
    assert len(evaluation.warnings) == 1
    assert evaluation.warnings[0].check == FundedRuleCheck.MAX_TOTAL_DRAWDOWN
    assert evaluation.warnings[0].severity == FundedRuleSeverity.WARNING


def test_daily_loss_breach_and_warning() -> None:
    breach = evaluate_funded_account_state(
        build_rules(),
        build_state(equity=94_500.0, daily_start_balance=100_000.0),
    )

    assert any(
        violation.check == FundedRuleCheck.MAX_DAILY_LOSS and violation.is_breach
        for violation in breach.violations
    )

    warning = evaluate_funded_account_state(
        build_rules(),
        build_state(equity=95_800.0, daily_start_balance=100_000.0),
    )

    assert warning.passed is True
    assert any(
        violation.check == FundedRuleCheck.MAX_DAILY_LOSS
        for violation in warning.warnings
    )


def test_consistency_rule_warns_on_concentrated_profit() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(),
        build_state(
            equity=110_000.0,
            largest_daily_profit=6_000.0,
            total_profit=10_000.0,
        ),
    )

    assert evaluation.passed is True
    assert evaluation.warnings[0].check == FundedRuleCheck.CONSISTENCY


def test_consistency_rule_is_quiet_when_balanced() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(),
        build_state(
            equity=110_000.0,
            largest_daily_profit=3_000.0,
            total_profit=10_000.0,
        ),
    )

    assert evaluation.violations == ()


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


def test_consistency_rule_ignores_losing_account() -> None:
    evaluation = evaluate_funded_account_state(
        build_rules(),
        build_state(equity=99_000.0, largest_daily_profit=500.0, total_profit=-1_000.0),
    )

    assert all(
        violation.check != FundedRuleCheck.CONSISTENCY
        for violation in evaluation.violations
    )


def test_trade_request_passes_when_compliant() -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(),
        build_state(),
        build_request(),
    )

    assert evaluation.passed is True


def test_trade_request_rejects_oversized_lot() -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(max_lot_size=2.0),
        build_state(),
        build_request(lot_size=3.0),
    )

    assert evaluation.breaches[0].check == FundedRuleCheck.MAX_LOT_SIZE


def test_trade_request_rejects_undersized_lot() -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(min_lot_size=0.1),
        build_state(),
        build_request(lot_size=0.05),
    )

    assert evaluation.breaches[0].check == FundedRuleCheck.MIN_LOT_SIZE


def test_trade_request_rejects_excess_risk() -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(max_risk_per_trade_fraction=0.01),
        build_state(),
        build_request(risk_fraction=0.05),
    )

    assert evaluation.breaches[0].check == FundedRuleCheck.MAX_RISK_PER_TRADE


def test_trade_request_rejects_when_position_limit_reached() -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(max_open_positions=2),
        build_state(open_position_count=2),
        build_request(),
    )

    assert evaluation.breaches[0].check == FundedRuleCheck.MAX_OPEN_POSITIONS


def test_trade_request_rejects_disallowed_symbol() -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(allowed_symbols=("EURUSD",)),
        build_state(),
        build_request(symbol="BTCUSD"),
    )

    assert evaluation.breaches[0].check == FundedRuleCheck.SYMBOL_NOT_ALLOWED


def test_news_blackout_blocks_trades_before_and_after_release() -> None:
    rules = build_rules(
        news_blackout_minutes_before=5,
        news_blackout_minutes_after=3,
    )

    before = evaluate_funded_trade_request(
        rules,
        build_state(),
        build_request(minutes_to_high_impact_news=2.0),
    )
    after = evaluate_funded_trade_request(
        rules,
        build_state(),
        build_request(minutes_to_high_impact_news=-1.0),
    )
    clear = evaluate_funded_trade_request(
        rules,
        build_state(),
        build_request(minutes_to_high_impact_news=30.0),
    )

    assert before.breaches[0].check == FundedRuleCheck.NEWS_BLACKOUT
    assert after.breaches[0].check == FundedRuleCheck.NEWS_BLACKOUT
    assert clear.passed is True


def test_news_restriction_can_be_disabled() -> None:
    evaluation = evaluate_funded_trade_request(
        build_rules(news_restriction_enabled=False),
        build_state(),
        build_request(minutes_to_high_impact_news=0.0),
    )

    assert evaluation.passed is True


def test_weekend_holding_rule() -> None:
    blocked = evaluate_funded_trade_request(
        build_rules(),
        build_state(),
        build_request(holds_over_weekend=True),
    )
    allowed = evaluate_funded_trade_request(
        build_rules(weekend_holding_allowed=True),
        build_state(),
        build_request(holds_over_weekend=True),
    )

    assert blocked.breaches[0].check == FundedRuleCheck.WEEKEND_HOLDING
    assert allowed.passed is True


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


def test_evaluate_funded_rules_without_request() -> None:
    evaluation = evaluate_funded_rules(build_rules(), build_state())

    assert evaluation.passed is True
    assert FundedRuleCheck.MAX_LOT_SIZE not in evaluation.checks_run


def test_profit_fraction_and_payout_status() -> None:
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

    assert status.profit_target_met is True
    assert status.trading_days_met is False
    assert status.payout_eligible is False
    assert status.remaining_trading_days == 3


def test_payout_blocked_by_breach() -> None:
    status = build_funded_payout_status(
        build_rules(drawdown_basis=DrawdownBasis.TRAILING_EQUITY),
        build_state(equity=111_000.0, peak_equity=130_000.0, trading_days=10),
    )

    assert status.rules_passed is False
    assert status.payout_eligible is False
    assert status.to_dict()["payout_eligible"] is False


def test_create_and_read_rules(funded_rules_repository, funded_account) -> None:
    rules = funded_rules_repository.create_rules(
        funded_account.account_id,
        created_at_utc="2026-01-01T00:00:00Z",
        max_total_drawdown_fraction=0.08,
        allowed_symbols=("XAUUSD", "EURUSD"),
    )

    stored = funded_rules_repository.require_rules(funded_account.account_id)

    assert stored.to_dict() == rules.to_dict()
    assert stored.allowed_symbols == ("XAUUSD", "EURUSD")
    assert stored.max_total_drawdown_fraction == 0.08


def test_create_rules_rejects_duplicate(funded_rules_repository, funded_account) -> None:
    funded_rules_repository.create_rules(funded_account.account_id)

    with pytest.raises(ValueError, match="already exist"):
        funded_rules_repository.create_rules(funded_account.account_id)


def test_get_rules_returns_none_when_missing(funded_rules_repository) -> None:
    assert funded_rules_repository.get_rules("account_missing") is None


def test_require_rules_raises_when_missing(funded_rules_repository) -> None:
    with pytest.raises(LookupError, match="do not exist"):
        funded_rules_repository.require_rules("account_missing")


def test_get_or_create_rules(funded_rules_repository, funded_account) -> None:
    first = funded_rules_repository.get_or_create_rules(
        funded_account.account_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )
    second = funded_rules_repository.get_or_create_rules(funded_account.account_id)

    assert first.rules_id == second.rules_id


def test_update_rules(funded_rules_repository, funded_account) -> None:
    funded_rules_repository.create_rules(
        funded_account.account_id,
        created_at_utc="2026-01-01T00:00:00Z",
    )

    updated = funded_rules_repository.update_rules(
        funded_account.account_id,
        max_total_drawdown_fraction=0.06,
        max_daily_loss_fraction=0.03,
        drawdown_basis=DrawdownBasis.TRAILING_EQUITY,
        min_trading_days=10,
        weekend_holding_allowed=True,
        allowed_symbols=("XAUUSD",),
        metadata={"provider": "prop_firm"},
        updated_at_utc="2026-02-01T00:00:00Z",
    )

    assert updated.max_total_drawdown_fraction == 0.06
    assert updated.drawdown_basis == DrawdownBasis.TRAILING_EQUITY
    assert updated.min_trading_days == 10
    assert updated.weekend_holding_allowed is True
    assert updated.allowed_symbols == ("XAUUSD",)
    assert updated.metadata == {"provider": "prop_firm"}
    assert updated.updated_at_utc == "2026-02-01T00:00:00Z"

    stored = funded_rules_repository.require_rules(funded_account.account_id)

    assert stored.to_dict() == updated.to_dict()


def test_update_rules_still_validates(funded_rules_repository, funded_account) -> None:
    funded_rules_repository.create_rules(funded_account.account_id)

    with pytest.raises(ValueError, match="cannot exceed max_total_drawdown_fraction"):
        funded_rules_repository.update_rules(
            funded_account.account_id,
            max_daily_loss_fraction=0.5,
        )


def test_set_active(funded_rules_repository, funded_account) -> None:
    funded_rules_repository.create_rules(funded_account.account_id)

    disabled = funded_rules_repository.set_active(funded_account.account_id, False)

    assert disabled.is_active is False
    assert funded_rules_repository.list_rules(active_only=True) == ()
    assert len(funded_rules_repository.list_rules()) == 1


def test_delete_rules(funded_rules_repository, funded_account) -> None:
    funded_rules_repository.create_rules(funded_account.account_id)

    assert funded_rules_repository.delete_rules(funded_account.account_id) is True
    assert funded_rules_repository.get_rules(funded_account.account_id) is None
    assert funded_rules_repository.delete_rules(funded_account.account_id) is False


def test_deleting_account_cascades_to_rules(
    funded_database,
    funded_rules_repository,
    funded_account,
) -> None:
    funded_rules_repository.create_rules(funded_account.account_id)

    TradingAccountRepository(funded_database).delete_account(funded_account.account_id)

    assert funded_rules_repository.get_rules(funded_account.account_id) is None
