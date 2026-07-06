"""
Portfolio risk.

Provides portfolio-level position value, exposure, and unrealized
profit/loss calculations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PortfolioPosition:
    """
    Represents a portfolio position.
    """

    symbol: str
    side: str
    quantity: float
    entry_price: float
    current_price: float
    value: float
    unrealized_pnl: float


@dataclass(slots=True)
class PortfolioRiskManager:
    """
    Portfolio risk manager.
    """

    max_symbol_exposure_percent: float = 0.5

    def __post_init__(self) -> None:
        """
        Validate portfolio risk configuration.
        """

        if self.max_symbol_exposure_percent <= 0:
            raise ValueError(
                "Max symbol exposure percent must be greater than zero."
            )

        if self.max_symbol_exposure_percent > 1:
            raise ValueError(
                "Max symbol exposure percent cannot be greater than 1."
            )

    def create_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        current_price: float,
    ) -> PortfolioPosition:
        """
        Create a portfolio position.
        """

        self._validate_symbol(symbol)
        self._validate_side(side)
        self._validate_positive("Quantity", quantity)
        self._validate_positive("Entry price", entry_price)
        self._validate_positive("Current price", current_price)

        value = quantity * current_price

        if side == "buy":
            unrealized_pnl = (current_price - entry_price) * quantity
        else:
            unrealized_pnl = (entry_price - current_price) * quantity

        return PortfolioPosition(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            current_price=current_price,
            value=value,
            unrealized_pnl=unrealized_pnl,
        )

    def total_value(
        self,
        positions: list[PortfolioPosition],
    ) -> float:
        """
        Calculate total portfolio position value.
        """

        return sum(position.value for position in positions)

    def total_unrealized_pnl(
        self,
        positions: list[PortfolioPosition],
    ) -> float:
        """
        Calculate total unrealized profit/loss.
        """

        return sum(position.unrealized_pnl for position in positions)

    def exposure_by_symbol(
        self,
        positions: list[PortfolioPosition],
    ) -> dict[str, float]:
        """
        Calculate exposure grouped by symbol.
        """

        exposure: dict[str, float] = {}

        for position in positions:
            exposure[position.symbol] = (
                exposure.get(position.symbol, 0.0) + position.value
            )

        return exposure

    def is_symbol_exposure_within_limit(
        self,
        positions: list[PortfolioPosition],
        symbol: str,
        account_balance: float,
    ) -> bool:
        """
        Check whether a symbol exposure is within configured limit.
        """

        self._validate_symbol(symbol)
        self._validate_positive("Account balance", account_balance)

        symbol_exposure = self.exposure_by_symbol(positions).get(
            symbol,
            0.0,
        )

        return (
            symbol_exposure / account_balance
        ) <= self.max_symbol_exposure_percent

    def largest_symbol_exposure_percent(
        self,
        positions: list[PortfolioPosition],
        account_balance: float,
    ) -> float:
        """
        Calculate largest symbol exposure percentage.
        """

        self._validate_positive("Account balance", account_balance)

        exposure = self.exposure_by_symbol(positions)

        if not exposure:
            return 0.0

        return max(exposure.values()) / account_balance

    def _validate_symbol(
        self,
        symbol: str,
    ) -> None:
        """
        Validate symbol.
        """

        if not symbol:
            raise ValueError("Symbol cannot be empty.")

    def _validate_side(
        self,
        side: str,
    ) -> None:
        """
        Validate side.
        """

        if side not in {"buy", "sell"}:
            raise ValueError("Side must be either 'buy' or 'sell'.")

    def _validate_positive(
        self,
        name: str,
        value: float,
    ) -> None:
        """
        Validate positive numeric value.
        """

        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")


__all__ = [
    "PortfolioPosition",
    "PortfolioRiskManager",
]