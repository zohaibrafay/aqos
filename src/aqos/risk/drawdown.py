"""
Drawdown risk.

Calculates drawdown from equity values and validates drawdown limits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class DrawdownRecord:
    """
    Represents a drawdown calculation.
    """

    peak_equity: float
    current_equity: float
    drawdown: float
    drawdown_percent: float


@dataclass(slots=True)
class DrawdownManager:
    """
    Drawdown risk manager.
    """

    max_drawdown_percent: float = 0.2

    def __post_init__(self) -> None:
        """
        Validate drawdown configuration.
        """

        if self.max_drawdown_percent <= 0:
            raise ValueError(
                "Max drawdown percent must be greater than zero."
            )

        if self.max_drawdown_percent > 1:
            raise ValueError(
                "Max drawdown percent cannot be greater than 1."
            )

    def calculate(
        self,
        peak_equity: float,
        current_equity: float,
    ) -> float:
        """
        Calculate absolute drawdown.
        """

        if peak_equity <= 0:
            raise ValueError("Peak equity must be greater than zero.")

        if current_equity < 0:
            raise ValueError("Current equity cannot be negative.")

        return max(peak_equity - current_equity, 0.0)

    def calculate_percent(
        self,
        peak_equity: float,
        current_equity: float,
    ) -> float:
        """
        Calculate drawdown percentage.
        """

        drawdown = self.calculate(
            peak_equity=peak_equity,
            current_equity=current_equity,
        )

        return drawdown / peak_equity

    def is_within_limit(
        self,
        peak_equity: float,
        current_equity: float,
    ) -> bool:
        """
        Check whether drawdown is within the configured limit.
        """

        drawdown_percent = self.calculate_percent(
            peak_equity=peak_equity,
            current_equity=current_equity,
        )

        return drawdown_percent <= self.max_drawdown_percent

    def create_record(
        self,
        peak_equity: float,
        current_equity: float,
    ) -> DrawdownRecord:
        """
        Create a drawdown record.
        """

        drawdown = self.calculate(
            peak_equity=peak_equity,
            current_equity=current_equity,
        )

        drawdown_percent = self.calculate_percent(
            peak_equity=peak_equity,
            current_equity=current_equity,
        )

        return DrawdownRecord(
            peak_equity=peak_equity,
            current_equity=current_equity,
            drawdown=drawdown,
            drawdown_percent=drawdown_percent,
        )

    def max_drawdown(
        self,
        equity_curve: list[float],
    ) -> float:
        """
        Calculate maximum drawdown percentage from an equity curve.
        """

        if not equity_curve:
            raise ValueError("Equity curve cannot be empty.")

        if any(equity < 0 for equity in equity_curve):
            raise ValueError("Equity values cannot be negative.")

        if equity_curve[0] <= 0:
            raise ValueError(
                "Initial equity must be greater than zero."
            )

        peak_equity = equity_curve[0]
        max_drawdown_percent = 0.0

        for equity in equity_curve:
            peak_equity = max(peak_equity, equity)

            if peak_equity == 0:
                continue

            drawdown_percent = self.calculate_percent(
                peak_equity=peak_equity,
                current_equity=equity,
            )

            max_drawdown_percent = max(
                max_drawdown_percent,
                drawdown_percent,
            )

        return max_drawdown_percent


__all__ = [
    "DrawdownManager",
    "DrawdownRecord",
]