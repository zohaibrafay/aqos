from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from enum import Enum
from typing import Any

from aqos.funded_rules.models import (
    DrawdownBasis,
    FundedAccountRules,
    as_fraction,
)


AQOS_FUNDED_EVALUATION_VERSION = "1.0"

#: Warn once an account is this far into its drawdown allowance.
DRAWDOWN_WARNING_RATIO = 0.8


class FundedRuleCheck(str, Enum):
    MAX_TOTAL_DRAWDOWN = "max_total_drawdown"
    MAX_DAILY_LOSS = "max_daily_loss"
    MAX_RISK_PER_TRADE = "max_risk_per_trade"
    MAX_LOT_SIZE = "max_lot_size"
    MIN_LOT_SIZE = "min_lot_size"
    MAX_OPEN_POSITIONS = "max_open_positions"
    MAX_DAILY_TRADES = "max_daily_trades"
    NEWS_BLACKOUT = "news_blackout"
    WEEKEND_HOLDING = "weekend_holding"
    CONSISTENCY = "consistency"
    SYMBOL_NOT_ALLOWED = "symbol_not_allowed"


class FundedRuleSeverity(str, Enum):
    WARNING = "warning"
    BREACH = "breach"


@dataclass(frozen=True)
class FundedAccountState:
    """A point-in-time snapshot of everything the funded rules measure."""

    initial_balance: float
    current_balance: float
    equity: float
    peak_equity: float | None = None
    peak_balance: float | None = None
    daily_start_balance: float | None = None
    daily_realized_pnl: float = 0.0
    open_position_count: int = 0
    trades_today: int = 0
    trading_days: int = 0
    largest_daily_profit: float = 0.0
    total_profit: float | None = None

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive.")

        if self.current_balance < 0:
            raise ValueError("current_balance cannot be negative.")

        if self.equity < 0:
            raise ValueError("equity cannot be negative.")

        if self.open_position_count < 0:
            raise ValueError("open_position_count cannot be negative.")

        if self.trades_today < 0:
            raise ValueError("trades_today cannot be negative.")

        if self.trading_days < 0:
            raise ValueError("trading_days cannot be negative.")

    @property
    def resolved_peak_equity(self) -> float:
        return max(self.peak_equity or self.initial_balance, self.initial_balance)

    @property
    def resolved_peak_balance(self) -> float:
        return max(self.peak_balance or self.initial_balance, self.initial_balance)

    @property
    def resolved_daily_start_balance(self) -> float:
        return self.daily_start_balance or self.initial_balance

    @property
    def resolved_total_profit(self) -> float:
        if self.total_profit is not None:
            return self.total_profit

        return self.equity - self.initial_balance

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial_balance": self.initial_balance,
            "current_balance": self.current_balance,
            "equity": self.equity,
            "peak_equity": self.resolved_peak_equity,
            "peak_balance": self.resolved_peak_balance,
            "daily_start_balance": self.resolved_daily_start_balance,
            "daily_realized_pnl": self.daily_realized_pnl,
            "open_position_count": self.open_position_count,
            "trades_today": self.trades_today,
            "trading_days": self.trading_days,
            "largest_daily_profit": self.largest_daily_profit,
            "total_profit": self.resolved_total_profit,
        }


@dataclass(frozen=True)
class FundedTradeRequest:
    """A proposed trade, checked before anything reaches a broker."""

    symbol: str
    lot_size: float
    risk_fraction: float
    minutes_to_high_impact_news: float | None = None
    holds_over_weekend: bool = False

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("symbol cannot be empty.")

        if self.lot_size <= 0:
            raise ValueError("lot_size must be positive.")

        if self.risk_fraction < 0:
            raise ValueError("risk_fraction cannot be negative.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "lot_size": self.lot_size,
            "risk_fraction": self.risk_fraction,
            "minutes_to_high_impact_news": self.minutes_to_high_impact_news,
            "holds_over_weekend": self.holds_over_weekend,
        }


@dataclass(frozen=True)
class FundedRuleViolation:
    check: FundedRuleCheck
    severity: FundedRuleSeverity
    message: str
    details: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("Funded rule violation message cannot be empty.")

    @property
    def is_breach(self) -> bool:
        return self.severity == FundedRuleSeverity.BREACH

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check.value,
            "severity": self.severity.value,
            "message": self.message,
            "is_breach": self.is_breach,
            "details": self.details,
        }


@dataclass(frozen=True)
class FundedRuleEvaluation:
    account_id: str
    violations: tuple[FundedRuleViolation, ...] = ()
    checks_run: tuple[FundedRuleCheck, ...] = ()

    @property
    def breaches(self) -> tuple[FundedRuleViolation, ...]:
        return tuple(violation for violation in self.violations if violation.is_breach)

    @property
    def warnings(self) -> tuple[FundedRuleViolation, ...]:
        return tuple(
            violation for violation in self.violations if not violation.is_breach
        )

    @property
    def passed(self) -> bool:
        return not self.breaches

    def breach_summary(self) -> str:
        return "; ".join(violation.message for violation in self.breaches)

    def raise_if_breached(self) -> None:
        if self.passed:
            return

        raise ValueError(
            f"Funded account rules breached for {self.account_id}: "
            + self.breach_summary()
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "passed": self.passed,
            "breach_count": len(self.breaches),
            "warning_count": len(self.warnings),
            "checks_run": [check.value for check in self.checks_run],
            "violations": [violation.to_dict() for violation in self.violations],
        }


@dataclass(frozen=True)
class FundedPayoutStatus:
    account_id: str
    profit_target_fraction: float
    current_profit_fraction: float
    profit_target_met: bool
    trading_days: int
    min_trading_days: int
    trading_days_met: bool
    rules_passed: bool

    @property
    def payout_eligible(self) -> bool:
        return self.profit_target_met and self.trading_days_met and self.rules_passed

    @property
    def remaining_trading_days(self) -> int:
        return max(0, self.min_trading_days - self.trading_days)

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "profit_target_fraction": self.profit_target_fraction,
            "current_profit_fraction": self.current_profit_fraction,
            "profit_target_met": self.profit_target_met,
            "trading_days": self.trading_days,
            "min_trading_days": self.min_trading_days,
            "trading_days_met": self.trading_days_met,
            "remaining_trading_days": self.remaining_trading_days,
            "rules_passed": self.rules_passed,
            "payout_eligible": self.payout_eligible,
        }


def resolve_drawdown_reference(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> float:
    if rules.drawdown_basis == DrawdownBasis.TRAILING_EQUITY:
        return state.resolved_peak_equity

    if rules.drawdown_basis == DrawdownBasis.TRAILING_BALANCE:
        return state.resolved_peak_balance

    return state.initial_balance


def calculate_total_drawdown_fraction(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> float:
    reference = resolve_drawdown_reference(rules, state)

    if reference <= 0:
        return 0.0

    return max(0.0, (reference - state.equity) / reference)


def calculate_daily_loss_fraction(state: FundedAccountState) -> float:
    """
    Daily loss as a fraction of the day's starting balance.

    The worse of realized loss and open equity change is used, so an account
    cannot hide a losing day behind unrealized positions.
    """

    reference = state.resolved_daily_start_balance

    if reference <= 0:
        return 0.0

    daily_change = min(state.equity - reference, state.daily_realized_pnl)

    return max(0.0, -daily_change / reference)


def calculate_profit_fraction(state: FundedAccountState) -> float:
    return state.resolved_total_profit / state.initial_balance


def evaluate_drawdown_rules(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> list[FundedRuleViolation]:
    violations: list[FundedRuleViolation] = []

    drawdown = calculate_total_drawdown_fraction(rules, state)
    drawdown_limit = as_fraction(rules.max_total_drawdown_fraction)

    if drawdown >= drawdown_limit:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_TOTAL_DRAWDOWN,
                severity=FundedRuleSeverity.BREACH,
                message="Maximum total drawdown exceeded.",
                details={
                    "drawdown_fraction": drawdown,
                    "limit": drawdown_limit,
                    "basis": rules.drawdown_basis.value,
                },
            )
        )
    elif drawdown >= drawdown_limit * DRAWDOWN_WARNING_RATIO:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_TOTAL_DRAWDOWN,
                severity=FundedRuleSeverity.WARNING,
                message="Approaching maximum total drawdown.",
                details={"drawdown_fraction": drawdown, "limit": drawdown_limit},
            )
        )

    daily_loss = calculate_daily_loss_fraction(state)
    daily_limit = as_fraction(rules.max_daily_loss_fraction)

    if daily_loss >= daily_limit:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_DAILY_LOSS,
                severity=FundedRuleSeverity.BREACH,
                message="Maximum daily loss exceeded.",
                details={"daily_loss_fraction": daily_loss, "limit": daily_limit},
            )
        )
    elif daily_loss >= daily_limit * DRAWDOWN_WARNING_RATIO:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_DAILY_LOSS,
                severity=FundedRuleSeverity.WARNING,
                message="Approaching maximum daily loss.",
                details={"daily_loss_fraction": daily_loss, "limit": daily_limit},
            )
        )

    return violations


def evaluate_consistency_rule(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> list[FundedRuleViolation]:
    if rules.consistency_fraction is None:
        return []

    total_profit = state.resolved_total_profit

    if total_profit <= 0 or state.largest_daily_profit <= 0:
        return []

    share = state.largest_daily_profit / total_profit
    limit = as_fraction(rules.consistency_fraction)

    if share <= limit:
        return []

    return [
        FundedRuleViolation(
            check=FundedRuleCheck.CONSISTENCY,
            severity=FundedRuleSeverity.WARNING,
            message="Single day profit share exceeds the consistency limit.",
            details={"largest_daily_profit_share": share, "limit": limit},
        )
    ]


def evaluate_funded_account_state(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> FundedRuleEvaluation:
    violations = evaluate_drawdown_rules(rules, state)
    violations.extend(evaluate_consistency_rule(rules, state))

    return FundedRuleEvaluation(
        account_id=rules.account_id,
        violations=tuple(violations),
        checks_run=(
            FundedRuleCheck.MAX_TOTAL_DRAWDOWN,
            FundedRuleCheck.MAX_DAILY_LOSS,
            FundedRuleCheck.CONSISTENCY,
        ),
    )


def evaluate_funded_trade_request(
    rules: FundedAccountRules,
    state: FundedAccountState,
    request: FundedTradeRequest,
) -> FundedRuleEvaluation:
    violations: list[FundedRuleViolation] = []

    if not rules.allows_symbol(request.symbol):
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.SYMBOL_NOT_ALLOWED,
                severity=FundedRuleSeverity.BREACH,
                message=f"Symbol is not allowed on this account: {request.symbol}",
                details={"allowed_symbols": list(rules.allowed_symbols or [])},
            )
        )

    max_lot = as_fraction(rules.max_lot_size)
    min_lot = as_fraction(rules.min_lot_size)

    if request.lot_size > max_lot:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_LOT_SIZE,
                severity=FundedRuleSeverity.BREACH,
                message="Requested lot size exceeds the account limit.",
                details={"lot_size": request.lot_size, "limit": max_lot},
            )
        )

    if request.lot_size < min_lot:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MIN_LOT_SIZE,
                severity=FundedRuleSeverity.BREACH,
                message="Requested lot size is below the account minimum.",
                details={"lot_size": request.lot_size, "limit": min_lot},
            )
        )

    risk_limit = as_fraction(rules.max_risk_per_trade_fraction)

    if request.risk_fraction > risk_limit:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_RISK_PER_TRADE,
                severity=FundedRuleSeverity.BREACH,
                message="Requested risk exceeds the per-trade limit.",
                details={"risk_fraction": request.risk_fraction, "limit": risk_limit},
            )
        )

    if state.open_position_count >= rules.max_open_positions:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_OPEN_POSITIONS,
                severity=FundedRuleSeverity.BREACH,
                message="Maximum open positions reached.",
                details={
                    "open_position_count": state.open_position_count,
                    "limit": rules.max_open_positions,
                },
            )
        )

    if state.trades_today >= rules.max_daily_trades:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_DAILY_TRADES,
                severity=FundedRuleSeverity.BREACH,
                message="Maximum daily trades reached.",
                details={
                    "trades_today": state.trades_today,
                    "limit": rules.max_daily_trades,
                },
            )
        )

    if (
        rules.news_restriction_enabled
        and request.minutes_to_high_impact_news is not None
    ):
        minutes = request.minutes_to_high_impact_news

        within_blackout = (
            -rules.news_blackout_minutes_after
            <= minutes
            <= rules.news_blackout_minutes_before
        )

        if within_blackout:
            violations.append(
                FundedRuleViolation(
                    check=FundedRuleCheck.NEWS_BLACKOUT,
                    severity=FundedRuleSeverity.BREACH,
                    message="Trade falls inside the high impact news blackout window.",
                    details={
                        "minutes_to_news": minutes,
                        "minutes_before": rules.news_blackout_minutes_before,
                        "minutes_after": rules.news_blackout_minutes_after,
                    },
                )
            )

    if request.holds_over_weekend and not rules.weekend_holding_allowed:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.WEEKEND_HOLDING,
                severity=FundedRuleSeverity.BREACH,
                message="Weekend holding is not allowed on this account.",
            )
        )

    return FundedRuleEvaluation(
        account_id=rules.account_id,
        violations=tuple(violations),
        checks_run=(
            FundedRuleCheck.SYMBOL_NOT_ALLOWED,
            FundedRuleCheck.MAX_LOT_SIZE,
            FundedRuleCheck.MIN_LOT_SIZE,
            FundedRuleCheck.MAX_RISK_PER_TRADE,
            FundedRuleCheck.MAX_OPEN_POSITIONS,
            FundedRuleCheck.MAX_DAILY_TRADES,
            FundedRuleCheck.NEWS_BLACKOUT,
            FundedRuleCheck.WEEKEND_HOLDING,
        ),
    )


def evaluate_funded_rules(
    rules: FundedAccountRules,
    state: FundedAccountState,
    request: FundedTradeRequest | None = None,
) -> FundedRuleEvaluation:
    """Run every applicable funded rule and merge the results."""

    account_evaluation = evaluate_funded_account_state(rules, state)

    if request is None:
        return account_evaluation

    trade_evaluation = evaluate_funded_trade_request(rules, state, request)

    return FundedRuleEvaluation(
        account_id=rules.account_id,
        violations=account_evaluation.violations + trade_evaluation.violations,
        checks_run=account_evaluation.checks_run + trade_evaluation.checks_run,
    )


def build_funded_payout_status(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> FundedPayoutStatus:
    profit_fraction = calculate_profit_fraction(state)

    return FundedPayoutStatus(
        account_id=rules.account_id,
        profit_target_fraction=as_fraction(rules.profit_target_fraction),
        current_profit_fraction=profit_fraction,
        profit_target_met=profit_fraction
        >= as_fraction(rules.profit_target_fraction),
        trading_days=state.trading_days,
        min_trading_days=rules.min_trading_days,
        trading_days_met=state.trading_days >= rules.min_trading_days,
        rules_passed=evaluate_funded_account_state(rules, state).passed,
    )


__all__ = [
    "AQOS_FUNDED_EVALUATION_VERSION",
    "DRAWDOWN_WARNING_RATIO",
    "FundedAccountState",
    "FundedPayoutStatus",
    "FundedRuleCheck",
    "FundedRuleEvaluation",
    "FundedRuleSeverity",
    "FundedRuleViolation",
    "FundedTradeRequest",
    "build_funded_payout_status",
    "calculate_daily_loss_fraction",
    "calculate_profit_fraction",
    "calculate_total_drawdown_fraction",
    "evaluate_consistency_rule",
    "evaluate_drawdown_rules",
    "evaluate_funded_account_state",
    "evaluate_funded_rules",
    "evaluate_funded_trade_request",
    "resolve_drawdown_reference",
]
