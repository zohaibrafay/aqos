from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from enum import Enum
from typing import Any

from aqos.persistence.database import AqosDatabase
from aqos.persistence.records import (
    build_record_id,
    decode_bool,
    decode_json_field,
    decode_string_list,
    encode_bool,
    encode_json_field,
    encode_string_list,
    normalize_required_text,
    record_utc_now,
)
from aqos.persistence.schema import ensure_aqos_schema


AQOS_FUNDED_RULES_VERSION = "1.0"


class DrawdownBasis(str, Enum):
    """What the maximum drawdown limit is measured against."""

    STATIC_INITIAL = "static_initial"
    TRAILING_EQUITY = "trailing_equity"
    TRAILING_BALANCE = "trailing_balance"


class FundedRuleCheck(str, Enum):
    MAX_TOTAL_DRAWDOWN = "max_total_drawdown"
    MAX_DAILY_LOSS = "max_daily_loss"
    MAX_RISK_PER_TRADE = "max_risk_per_trade"
    MAX_LOT_SIZE = "max_lot_size"
    MIN_LOT_SIZE = "min_lot_size"
    MAX_OPEN_POSITIONS = "max_open_positions"
    NEWS_BLACKOUT = "news_blackout"
    WEEKEND_HOLDING = "weekend_holding"
    CONSISTENCY = "consistency"
    SYMBOL_NOT_ALLOWED = "symbol_not_allowed"


class FundedRuleSeverity(str, Enum):
    WARNING = "warning"
    BREACH = "breach"


DEFAULT_MAX_TOTAL_DRAWDOWN_FRACTION = 0.10
DEFAULT_MAX_DAILY_LOSS_FRACTION = 0.05
DEFAULT_MAX_RISK_PER_TRADE_FRACTION = 0.01
DEFAULT_PROFIT_TARGET_FRACTION = 0.10
DEFAULT_MIN_TRADING_DAYS = 5
DEFAULT_MAX_LOT_SIZE = 5.0
DEFAULT_MIN_LOT_SIZE = 0.01
DEFAULT_MAX_OPEN_POSITIONS = 3
DEFAULT_NEWS_BLACKOUT_MINUTES = 2
DEFAULT_CONSISTENCY_FRACTION = 0.40

#: Warn once the account is this far into its drawdown allowance.
DRAWDOWN_WARNING_RATIO = 0.8


@dataclass(frozen=True)
class FundedAccountRules:
    rules_id: str
    account_id: str
    created_at_utc: str
    updated_at_utc: str
    max_total_drawdown_fraction: float = DEFAULT_MAX_TOTAL_DRAWDOWN_FRACTION
    max_daily_loss_fraction: float = DEFAULT_MAX_DAILY_LOSS_FRACTION
    max_risk_per_trade_fraction: float = DEFAULT_MAX_RISK_PER_TRADE_FRACTION
    profit_target_fraction: float = DEFAULT_PROFIT_TARGET_FRACTION
    drawdown_basis: DrawdownBasis = DrawdownBasis.STATIC_INITIAL
    min_trading_days: int = DEFAULT_MIN_TRADING_DAYS
    max_lot_size: float = DEFAULT_MAX_LOT_SIZE
    min_lot_size: float = DEFAULT_MIN_LOT_SIZE
    max_open_positions: int = DEFAULT_MAX_OPEN_POSITIONS
    news_restriction_enabled: bool = True
    news_blackout_minutes_before: int = DEFAULT_NEWS_BLACKOUT_MINUTES
    news_blackout_minutes_after: int = DEFAULT_NEWS_BLACKOUT_MINUTES
    weekend_holding_allowed: bool = False
    consistency_fraction: float | None = DEFAULT_CONSISTENCY_FRACTION
    allowed_symbols: tuple[str, ...] = ()
    is_active: bool = True
    metadata: dict[str, Any] = dataclass_field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.rules_id.strip():
            raise ValueError("rules_id cannot be empty.")

        if not self.account_id.strip():
            raise ValueError("account_id cannot be empty.")

        if not self.created_at_utc.strip():
            raise ValueError("created_at_utc cannot be empty.")

        if not self.updated_at_utc.strip():
            raise ValueError("updated_at_utc cannot be empty.")

        if not 0.0 < self.max_total_drawdown_fraction <= 1.0:
            raise ValueError(
                "max_total_drawdown_fraction must be greater than 0 and at most 1."
            )

        if not 0.0 < self.max_daily_loss_fraction <= 1.0:
            raise ValueError(
                "max_daily_loss_fraction must be greater than 0 and at most 1."
            )

        if self.max_daily_loss_fraction > self.max_total_drawdown_fraction:
            raise ValueError(
                "max_daily_loss_fraction cannot exceed max_total_drawdown_fraction."
            )

        if not 0.0 < self.max_risk_per_trade_fraction <= 1.0:
            raise ValueError(
                "max_risk_per_trade_fraction must be greater than 0 and at most 1."
            )

        if self.profit_target_fraction <= 0.0:
            raise ValueError("profit_target_fraction must be positive.")

        if self.min_trading_days < 0:
            raise ValueError("min_trading_days cannot be negative.")

        if self.min_lot_size <= 0:
            raise ValueError("min_lot_size must be positive.")

        if self.max_lot_size < self.min_lot_size:
            raise ValueError("max_lot_size cannot be smaller than min_lot_size.")

        if self.max_open_positions < 1:
            raise ValueError("max_open_positions must be at least 1.")

        if self.news_blackout_minutes_before < 0:
            raise ValueError("news_blackout_minutes_before cannot be negative.")

        if self.news_blackout_minutes_after < 0:
            raise ValueError("news_blackout_minutes_after cannot be negative.")

        if self.consistency_fraction is not None and not (
            0.0 < self.consistency_fraction <= 1.0
        ):
            raise ValueError(
                "consistency_fraction must be greater than 0 and at most 1."
            )

    def allows_symbol(self, symbol: str) -> bool:
        if not self.allowed_symbols:
            return True

        return symbol.strip().upper() in self.allowed_symbols

    def to_dict(self) -> dict[str, Any]:
        return {
            "rules_id": self.rules_id,
            "account_id": self.account_id,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "max_total_drawdown_fraction": self.max_total_drawdown_fraction,
            "max_daily_loss_fraction": self.max_daily_loss_fraction,
            "max_risk_per_trade_fraction": self.max_risk_per_trade_fraction,
            "profit_target_fraction": self.profit_target_fraction,
            "drawdown_basis": self.drawdown_basis.value,
            "min_trading_days": self.min_trading_days,
            "max_lot_size": self.max_lot_size,
            "min_lot_size": self.min_lot_size,
            "max_open_positions": self.max_open_positions,
            "news_restriction_enabled": self.news_restriction_enabled,
            "news_blackout_minutes_before": self.news_blackout_minutes_before,
            "news_blackout_minutes_after": self.news_blackout_minutes_after,
            "weekend_holding_allowed": self.weekend_holding_allowed,
            "consistency_fraction": self.consistency_fraction,
            "allowed_symbols": list(self.allowed_symbols),
            "is_active": self.is_active,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class FundedAccountState:
    """A point-in-time snapshot of everything the funded rules are measured on."""

    initial_balance: float
    current_balance: float
    equity: float
    peak_equity: float | None = None
    peak_balance: float | None = None
    daily_start_balance: float | None = None
    daily_realized_pnl: float = 0.0
    open_position_count: int = 0
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

    def raise_if_breached(self) -> None:
        if self.passed:
            return

        messages = [violation.message for violation in self.breaches]

        raise ValueError(
            f"Funded account rules breached for {self.account_id}: "
            + "; ".join(messages)
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


def build_funded_rules_from_row(row: dict[str, Any]) -> FundedAccountRules:
    return FundedAccountRules(
        rules_id=str(row["rules_id"]),
        account_id=str(row["account_id"]),
        created_at_utc=str(row["created_at_utc"]),
        updated_at_utc=str(row["updated_at_utc"]),
        max_total_drawdown_fraction=float(row["max_total_drawdown_fraction"]),
        max_daily_loss_fraction=float(row["max_daily_loss_fraction"]),
        max_risk_per_trade_fraction=float(row["max_risk_per_trade_fraction"]),
        profit_target_fraction=float(row["profit_target_fraction"]),
        drawdown_basis=DrawdownBasis(str(row["drawdown_basis"])),
        min_trading_days=int(row["min_trading_days"]),
        max_lot_size=float(row["max_lot_size"]),
        min_lot_size=float(row["min_lot_size"]),
        max_open_positions=int(row["max_open_positions"]),
        news_restriction_enabled=decode_bool(row["news_restriction_enabled"]),
        news_blackout_minutes_before=int(row["news_blackout_minutes_before"]),
        news_blackout_minutes_after=int(row["news_blackout_minutes_after"]),
        weekend_holding_allowed=decode_bool(row["weekend_holding_allowed"]),
        consistency_fraction=(
            float(row["consistency_fraction"])
            if row.get("consistency_fraction") is not None
            else None
        ),
        allowed_symbols=decode_string_list(row.get("allowed_symbols")),
        is_active=decode_bool(row["is_active"]),
        metadata=decode_json_field(row.get("metadata")),
    )


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
    reference = state.resolved_daily_start_balance

    if reference <= 0:
        return 0.0

    daily_change = state.equity - reference

    if state.daily_realized_pnl < daily_change:
        daily_change = state.daily_realized_pnl

    return max(0.0, -daily_change / reference)


def evaluate_drawdown_rules(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> list[FundedRuleViolation]:
    violations: list[FundedRuleViolation] = []

    drawdown = calculate_total_drawdown_fraction(rules, state)

    if drawdown >= rules.max_total_drawdown_fraction:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_TOTAL_DRAWDOWN,
                severity=FundedRuleSeverity.BREACH,
                message="Maximum total drawdown exceeded.",
                details={
                    "drawdown_fraction": drawdown,
                    "limit": rules.max_total_drawdown_fraction,
                    "basis": rules.drawdown_basis.value,
                },
            )
        )
    elif drawdown >= rules.max_total_drawdown_fraction * DRAWDOWN_WARNING_RATIO:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_TOTAL_DRAWDOWN,
                severity=FundedRuleSeverity.WARNING,
                message="Approaching maximum total drawdown.",
                details={
                    "drawdown_fraction": drawdown,
                    "limit": rules.max_total_drawdown_fraction,
                },
            )
        )

    daily_loss = calculate_daily_loss_fraction(state)

    if daily_loss >= rules.max_daily_loss_fraction:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_DAILY_LOSS,
                severity=FundedRuleSeverity.BREACH,
                message="Maximum daily loss exceeded.",
                details={
                    "daily_loss_fraction": daily_loss,
                    "limit": rules.max_daily_loss_fraction,
                },
            )
        )
    elif daily_loss >= rules.max_daily_loss_fraction * DRAWDOWN_WARNING_RATIO:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_DAILY_LOSS,
                severity=FundedRuleSeverity.WARNING,
                message="Approaching maximum daily loss.",
                details={
                    "daily_loss_fraction": daily_loss,
                    "limit": rules.max_daily_loss_fraction,
                },
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

    if share <= rules.consistency_fraction:
        return []

    return [
        FundedRuleViolation(
            check=FundedRuleCheck.CONSISTENCY,
            severity=FundedRuleSeverity.WARNING,
            message="Single day profit share exceeds the consistency limit.",
            details={
                "largest_daily_profit_share": share,
                "limit": rules.consistency_fraction,
            },
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
                details={"allowed_symbols": list(rules.allowed_symbols)},
            )
        )

    if request.lot_size > rules.max_lot_size:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_LOT_SIZE,
                severity=FundedRuleSeverity.BREACH,
                message="Requested lot size exceeds the account limit.",
                details={"lot_size": request.lot_size, "limit": rules.max_lot_size},
            )
        )

    if request.lot_size < rules.min_lot_size:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MIN_LOT_SIZE,
                severity=FundedRuleSeverity.BREACH,
                message="Requested lot size is below the account minimum.",
                details={"lot_size": request.lot_size, "limit": rules.min_lot_size},
            )
        )

    if request.risk_fraction > rules.max_risk_per_trade_fraction:
        violations.append(
            FundedRuleViolation(
                check=FundedRuleCheck.MAX_RISK_PER_TRADE,
                severity=FundedRuleSeverity.BREACH,
                message="Requested risk exceeds the per-trade limit.",
                details={
                    "risk_fraction": request.risk_fraction,
                    "limit": rules.max_risk_per_trade_fraction,
                },
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


def calculate_profit_fraction(state: FundedAccountState) -> float:
    return state.resolved_total_profit / state.initial_balance


def build_funded_payout_status(
    rules: FundedAccountRules,
    state: FundedAccountState,
) -> FundedPayoutStatus:
    profit_fraction = calculate_profit_fraction(state)

    return FundedPayoutStatus(
        account_id=rules.account_id,
        profit_target_fraction=rules.profit_target_fraction,
        current_profit_fraction=profit_fraction,
        profit_target_met=profit_fraction >= rules.profit_target_fraction,
        trading_days=state.trading_days,
        min_trading_days=rules.min_trading_days,
        trading_days_met=state.trading_days >= rules.min_trading_days,
        rules_passed=evaluate_funded_account_state(rules, state).passed,
    )


class FundedAccountRulesRepository:
    """One configurable funded rule set per trading account."""

    def __init__(self, database: AqosDatabase) -> None:
        self.database = database
        ensure_aqos_schema(database)

    def create_rules(
        self,
        account_id: str,
        rules_id: str | None = None,
        created_at_utc: str | None = None,
        **overrides: Any,
    ) -> FundedAccountRules:
        if self.get_rules(account_id) is not None:
            raise ValueError(f"Funded rules already exist for account: {account_id}")

        timestamp = created_at_utc or record_utc_now()

        rules = FundedAccountRules(
            rules_id=rules_id or build_record_id("fundedrules"),
            account_id=normalize_required_text(account_id, "account_id"),
            created_at_utc=timestamp,
            updated_at_utc=timestamp,
            **overrides,
        )

        self._insert(rules)

        return rules

    def get_rules(self, account_id: str) -> FundedAccountRules | None:
        row = self.database.query_one(
            "SELECT * FROM funded_account_rules WHERE account_id = ?;",
            (account_id,),
        )

        return build_funded_rules_from_row(row) if row is not None else None

    def require_rules(self, account_id: str) -> FundedAccountRules:
        rules = self.get_rules(account_id)

        if rules is None:
            raise LookupError(f"Funded rules do not exist for account: {account_id}")

        return rules

    def get_or_create_rules(
        self,
        account_id: str,
        created_at_utc: str | None = None,
    ) -> FundedAccountRules:
        existing = self.get_rules(account_id)

        if existing is not None:
            return existing

        return self.create_rules(account_id, created_at_utc=created_at_utc)

    def list_rules(self, active_only: bool = False) -> tuple[FundedAccountRules, ...]:
        if active_only:
            rows = self.database.query_all(
                "SELECT * FROM funded_account_rules WHERE is_active = 1 "
                "ORDER BY created_at_utc, rules_id;"
            )
        else:
            rows = self.database.query_all(
                "SELECT * FROM funded_account_rules "
                "ORDER BY created_at_utc, rules_id;"
            )

        return tuple(build_funded_rules_from_row(row) for row in rows)

    def update_rules(
        self,
        account_id: str,
        updated_at_utc: str | None = None,
        **changes: Any,
    ) -> FundedAccountRules:
        current = self.require_rules(account_id)

        applied = {key: value for key, value in changes.items() if value is not None}

        updated = replace(
            current,
            **applied,
            updated_at_utc=updated_at_utc or record_utc_now(),
        )

        self._update(updated)

        return updated

    def set_active(
        self,
        account_id: str,
        is_active: bool,
        updated_at_utc: str | None = None,
    ) -> FundedAccountRules:
        current = self.require_rules(account_id)

        updated = replace(
            current,
            is_active=is_active,
            updated_at_utc=updated_at_utc or record_utc_now(),
        )

        self._update(updated)

        return updated

    def delete_rules(self, account_id: str) -> bool:
        cursor = self.database.execute(
            "DELETE FROM funded_account_rules WHERE account_id = ?;",
            (account_id,),
        )

        return cursor.rowcount > 0

    def _insert(self, rules: FundedAccountRules) -> None:
        self.database.execute(
            """
            INSERT INTO funded_account_rules (
                rules_id, account_id, max_total_drawdown_fraction,
                max_daily_loss_fraction, max_risk_per_trade_fraction,
                profit_target_fraction, drawdown_basis, min_trading_days,
                max_lot_size, min_lot_size, max_open_positions,
                news_restriction_enabled, news_blackout_minutes_before,
                news_blackout_minutes_after, weekend_holding_allowed,
                consistency_fraction, allowed_symbols, is_active,
                created_at_utc, updated_at_utc, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            self._to_parameters(rules)
            + (
                rules.created_at_utc,
                rules.updated_at_utc,
                encode_json_field(rules.metadata),
            ),
        )

    def _update(self, rules: FundedAccountRules) -> None:
        self.database.execute(
            """
            UPDATE funded_account_rules
            SET max_total_drawdown_fraction = ?, max_daily_loss_fraction = ?,
                max_risk_per_trade_fraction = ?, profit_target_fraction = ?,
                drawdown_basis = ?, min_trading_days = ?, max_lot_size = ?,
                min_lot_size = ?, max_open_positions = ?,
                news_restriction_enabled = ?, news_blackout_minutes_before = ?,
                news_blackout_minutes_after = ?, weekend_holding_allowed = ?,
                consistency_fraction = ?, allowed_symbols = ?, is_active = ?,
                updated_at_utc = ?, metadata = ?
            WHERE account_id = ?;
            """,
            (
                rules.max_total_drawdown_fraction,
                rules.max_daily_loss_fraction,
                rules.max_risk_per_trade_fraction,
                rules.profit_target_fraction,
                rules.drawdown_basis.value,
                rules.min_trading_days,
                rules.max_lot_size,
                rules.min_lot_size,
                rules.max_open_positions,
                encode_bool(rules.news_restriction_enabled),
                rules.news_blackout_minutes_before,
                rules.news_blackout_minutes_after,
                encode_bool(rules.weekend_holding_allowed),
                rules.consistency_fraction,
                encode_string_list(rules.allowed_symbols),
                encode_bool(rules.is_active),
                rules.updated_at_utc,
                encode_json_field(rules.metadata),
                rules.account_id,
            ),
        )

    def _to_parameters(self, rules: FundedAccountRules) -> tuple[Any, ...]:
        return (
            rules.rules_id,
            rules.account_id,
            rules.max_total_drawdown_fraction,
            rules.max_daily_loss_fraction,
            rules.max_risk_per_trade_fraction,
            rules.profit_target_fraction,
            rules.drawdown_basis.value,
            rules.min_trading_days,
            rules.max_lot_size,
            rules.min_lot_size,
            rules.max_open_positions,
            encode_bool(rules.news_restriction_enabled),
            rules.news_blackout_minutes_before,
            rules.news_blackout_minutes_after,
            encode_bool(rules.weekend_holding_allowed),
            rules.consistency_fraction,
            encode_string_list(rules.allowed_symbols),
            encode_bool(rules.is_active),
        )


__all__ = [
    "AQOS_FUNDED_RULES_VERSION",
    "DEFAULT_CONSISTENCY_FRACTION",
    "DEFAULT_MAX_DAILY_LOSS_FRACTION",
    "DEFAULT_MAX_LOT_SIZE",
    "DEFAULT_MAX_OPEN_POSITIONS",
    "DEFAULT_MAX_RISK_PER_TRADE_FRACTION",
    "DEFAULT_MAX_TOTAL_DRAWDOWN_FRACTION",
    "DEFAULT_MIN_LOT_SIZE",
    "DEFAULT_MIN_TRADING_DAYS",
    "DEFAULT_NEWS_BLACKOUT_MINUTES",
    "DEFAULT_PROFIT_TARGET_FRACTION",
    "DRAWDOWN_WARNING_RATIO",
    "DrawdownBasis",
    "FundedAccountRules",
    "FundedAccountRulesRepository",
    "FundedAccountState",
    "FundedPayoutStatus",
    "FundedRuleCheck",
    "FundedRuleEvaluation",
    "FundedRuleSeverity",
    "FundedRuleViolation",
    "FundedTradeRequest",
    "build_funded_payout_status",
    "build_funded_rules_from_row",
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
