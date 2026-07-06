"""
Backtesting.

Provides a lightweight foundational backtesting engine based on
completed trade profit/loss values.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BacktestTrade:
    """
    Represents a single backtest trade result.
    """

    index: int
    profit: float
    balance: float


@dataclass(slots=True, frozen=True)
class BacktestResult:
    """
    Represents a complete backtest result.
    """

    initial_balance: float
    final_balance: float
    total_profit: float
    return_percent: float
    win_rate: float
    max_drawdown: float
    trades: list[BacktestTrade]


@dataclass(slots=True)
class Backtester:
    """
    Backtesting engine.
    """

    def run(
        self,
        profits: list[float],
        initial_balance: float,
    ) -> BacktestResult:
        """
        Run a backtest from trade profit/loss values.
        """

        self._validate_profits(profits)
        self._validate_initial_balance(initial_balance)

        balance = initial_balance
        trades: list[BacktestTrade] = []

        for index, profit in enumerate(profits):
            balance += profit

            trades.append(
                BacktestTrade(
                    index=index,
                    profit=profit,
                    balance=balance,
                )
            )

        total_profit = balance - initial_balance
        return_percent = total_profit / initial_balance
        win_rate = self.win_rate(profits)
        max_drawdown = self.max_drawdown(
            self.equity_curve(
                profits=profits,
                initial_balance=initial_balance,
            )
        )

        return BacktestResult(
            initial_balance=initial_balance,
            final_balance=balance,
            total_profit=total_profit,
            return_percent=return_percent,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            trades=trades,
        )

    def equity_curve(
        self,
        profits: list[float],
        initial_balance: float,
    ) -> list[float]:
        """
        Build an equity curve from profit/loss values.
        """

        self._validate_profits(profits)
        self._validate_initial_balance(initial_balance)

        balance = initial_balance
        curve = [balance]

        for profit in profits:
            balance += profit
            curve.append(balance)

        return curve

    def win_rate(
        self,
        profits: list[float],
    ) -> float:
        """
        Calculate win rate.
        """

        self._validate_profits(profits)

        wins = sum(
            1
            for profit in profits
            if profit > 0
        )

        return wins / len(profits)

    def max_drawdown(
        self,
        equity_curve: list[float],
    ) -> float:
        """
        Calculate maximum drawdown percentage from an equity curve.
        """

        if not equity_curve:
            raise ValueError("Equity curve cannot be empty.")

        if any(value < 0 for value in equity_curve):
            raise ValueError("Equity values cannot be negative.")

        if equity_curve[0] <= 0:
            raise ValueError(
                "Initial equity must be greater than zero."
            )

        peak = equity_curve[0]
        max_drawdown = 0.0

        for equity in equity_curve:
            peak = max(peak, equity)

            drawdown = (peak - equity) / peak

            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def _validate_profits(
        self,
        profits: list[float],
    ) -> None:
        """
        Validate profit/loss input.
        """

        if not profits:
            raise ValueError("Profits cannot be empty.")

    def _validate_initial_balance(
        self,
        initial_balance: float,
    ) -> None:
        """
        Validate initial balance.
        """

        if initial_balance <= 0:
            raise ValueError("Initial balance must be greater than zero.")


__all__ = [
    "Backtester",
    "BacktestResult",
    "BacktestTrade",
]