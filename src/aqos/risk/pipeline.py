"""
Risk pipeline.

Coordinates sizing, exposure, drawdown, constraints, stop-loss,
take-profit, and portfolio risk checks.
"""

from __future__ import annotations

from dataclasses import dataclass

from aqos.risk.constraints import RiskConstraints, RiskDecision
from aqos.risk.drawdown import DrawdownManager
from aqos.risk.exposure import ExposureManager
from aqos.risk.portfolio import PortfolioRiskManager
from aqos.risk.sizing import PositionSizer
from aqos.risk.stop_loss import StopLossManager
from aqos.risk.take_profit import TakeProfitManager


@dataclass(slots=True, frozen=True)
class RiskAssessment:
    """
    Represents a complete risk assessment.
    """

    allowed: bool
    position_size: float
    risk_amount: float
    exposure: float
    drawdown_percent: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_triggered: bool
    take_profit_hit: bool
    reasons: list[str]


@dataclass(slots=True)
class RiskPipeline:
    """
    Unified risk pipeline.
    """

    position_sizer: PositionSizer
    exposure_manager: ExposureManager
    drawdown_manager: DrawdownManager
    constraints: RiskConstraints
    stop_loss_manager: StopLossManager
    take_profit_manager: TakeProfitManager
    portfolio_manager: PortfolioRiskManager

    def assess_trade(
        self,
        account_balance: float,
        peak_equity: float,
        current_equity: float,
        entry_price: float,
        stop_loss_price: float,
        current_price: float,
        side: str,
    ) -> RiskAssessment:
        """
        Run a complete trade risk assessment.
        """

        self._validate_side(side)

        position_size = self.position_sizer.calculate(
            account_balance=account_balance,
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
        )

        risk_amount = position_size * abs(
            entry_price - stop_loss_price
        )

        exposure = self.exposure_manager.calculate(
            position_size=position_size,
            price=entry_price,
        )

        drawdown_percent = self.drawdown_manager.calculate_percent(
            peak_equity=peak_equity,
            current_equity=current_equity,
        )

        decision = self.constraints.validate_trade(
            account_balance=account_balance,
            risk_amount=risk_amount,
            exposure=exposure,
            peak_equity=peak_equity,
            current_equity=current_equity,
        )

        take_profit_price = self.take_profit_manager.calculate(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            side=side,
        )

        stop_loss_triggered = self.stop_loss_manager.is_triggered(
            current_price=current_price,
            stop_loss_price=stop_loss_price,
            side=side,
        )

        take_profit_hit = self.take_profit_manager.is_hit(
            current_price=current_price,
            take_profit_price=take_profit_price,
            side=side,
        )

        return RiskAssessment(
            allowed=decision.allowed,
            position_size=position_size,
            risk_amount=risk_amount,
            exposure=exposure,
            drawdown_percent=drawdown_percent,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            stop_loss_triggered=stop_loss_triggered,
            take_profit_hit=take_profit_hit,
            reasons=decision.reasons,
        )

    def validate_decision(
        self,
        decision: RiskDecision,
    ) -> bool:
        """
        Return whether a risk decision is allowed.
        """

        return decision.allowed

    def _validate_side(
        self,
        side: str,
    ) -> None:
        """
        Validate trade side.
        """

        if side not in {"buy", "sell"}:
            raise ValueError("Side must be either 'buy' or 'sell'.")


__all__ = [
    "RiskAssessment",
    "RiskPipeline",
]