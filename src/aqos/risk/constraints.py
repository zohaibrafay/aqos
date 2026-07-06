"""
Risk constraints.

Provides a unified rule engine for validating whether a trade or
portfolio state is allowed under configured risk limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class RiskDecision:
    """
    Represents the result of a risk constraint validation.
    """

    allowed: bool
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class RiskConstraints:
    """
    Risk constraint engine.
    """

    max_risk_percent: float = 0.01
    max_exposure_percent: float = 1.0
    max_drawdown_percent: float = 0.2

    def __post_init__(self) -> None:
        """
        Validate risk constraint configuration.
        """

        self._validate_percent(
            name="Max risk percent",
            value=self.max_risk_percent,
        )
        self._validate_percent(
            name="Max exposure percent",
            value=self.max_exposure_percent,
        )
        self._validate_percent(
            name="Max drawdown percent",
            value=self.max_drawdown_percent,
        )

    def validate_trade(
        self,
        account_balance: float,
        risk_amount: float,
        exposure: float,
        peak_equity: float,
        current_equity: float,
    ) -> RiskDecision:
        """
        Validate trade risk, exposure, and drawdown constraints.
        """

        reasons: list[str] = []

        if not self.is_risk_within_limit(
            risk_amount=risk_amount,
            account_balance=account_balance,
        ):
            reasons.append("Risk amount exceeds maximum risk limit.")

        if not self.is_exposure_within_limit(
            exposure=exposure,
            account_balance=account_balance,
        ):
            reasons.append("Exposure exceeds maximum exposure limit.")

        if not self.is_drawdown_within_limit(
            peak_equity=peak_equity,
            current_equity=current_equity,
        ):
            reasons.append("Drawdown exceeds maximum drawdown limit.")

        return RiskDecision(
            allowed=not reasons,
            reasons=reasons,
        )

    def is_risk_within_limit(
        self,
        risk_amount: float,
        account_balance: float,
    ) -> bool:
        """
        Check whether trade risk is within the configured limit.
        """

        if risk_amount < 0:
            raise ValueError("Risk amount cannot be negative.")

        risk_percent = self._percent_of_balance(
            amount=risk_amount,
            account_balance=account_balance,
        )

        return risk_percent <= self.max_risk_percent

    def is_exposure_within_limit(
        self,
        exposure: float,
        account_balance: float,
    ) -> bool:
        """
        Check whether exposure is within the configured limit.
        """

        if exposure < 0:
            raise ValueError("Exposure cannot be negative.")

        exposure_percent = self._percent_of_balance(
            amount=exposure,
            account_balance=account_balance,
        )

        return exposure_percent <= self.max_exposure_percent

    def is_drawdown_within_limit(
        self,
        peak_equity: float,
        current_equity: float,
    ) -> bool:
        """
        Check whether drawdown is within the configured limit.
        """

        drawdown_percent = self._drawdown_percent(
            peak_equity=peak_equity,
            current_equity=current_equity,
        )

        return drawdown_percent <= self.max_drawdown_percent

    def _percent_of_balance(
        self,
        amount: float,
        account_balance: float,
    ) -> float:
        """
        Calculate amount as percentage of account balance.
        """

        if account_balance <= 0:
            raise ValueError("Account balance must be greater than zero.")

        return amount / account_balance

    def _drawdown_percent(
        self,
        peak_equity: float,
        current_equity: float,
    ) -> float:
        """
        Calculate drawdown percentage.
        """

        if peak_equity <= 0:
            raise ValueError("Peak equity must be greater than zero.")

        if current_equity < 0:
            raise ValueError("Current equity cannot be negative.")

        drawdown = max(peak_equity - current_equity, 0.0)

        return drawdown / peak_equity

    def _validate_percent(
        self,
        name: str,
        value: float,
    ) -> None:
        """
        Validate percentage configuration.
        """

        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")

        if value > 1:
            raise ValueError(f"{name} cannot be greater than 1.")


__all__ = [
    "RiskConstraints",
    "RiskDecision",
]