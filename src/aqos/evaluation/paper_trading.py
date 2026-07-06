"""
Paper trading.

Provides a lightweight paper-trading engine for simulated trade
execution without broker integration.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class PaperTrade:
    """
    Represents a simulated paper trade.
    """

    trade_id: str
    symbol: str
    side: str
    quantity: float
    entry_price: float
    status: str
    exit_price: float | None = None
    profit: float = 0.0


class PaperTradingEngine:
    """
    Paper trading engine.
    """

    def __init__(
        self,
        initial_balance: float = 10_000.0,
    ) -> None:
        if initial_balance <= 0:
            raise ValueError("Initial balance must be greater than zero.")

        self.initial_balance = initial_balance
        self.balance = initial_balance
        self._trades: dict[str, PaperTrade] = {}

    def open_trade(
        self,
        trade_id: str,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
    ) -> PaperTrade:
        """
        Open a simulated trade.
        """

        self._validate_trade_id(trade_id)

        if trade_id in self._trades:
            raise ValueError("Trade ID already exists.")

        self._validate_symbol(symbol)
        self._validate_side(side)
        self._validate_positive("Quantity", quantity)
        self._validate_positive("Entry price", entry_price)

        trade = PaperTrade(
            trade_id=trade_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=entry_price,
            status="open",
        )

        self._trades[trade_id] = trade

        return trade

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
    ) -> PaperTrade:
        """
        Close a simulated trade.
        """

        self._validate_trade_id(trade_id)
        self._validate_positive("Exit price", exit_price)

        trade = self.get_trade(trade_id)

        if trade is None:
            raise ValueError("Trade does not exist.")

        if trade.status != "open":
            raise ValueError("Trade is already closed.")

        profit = self._calculate_profit(
            side=trade.side,
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            exit_price=exit_price,
        )

        closed_trade = PaperTrade(
            trade_id=trade.trade_id,
            symbol=trade.symbol,
            side=trade.side,
            quantity=trade.quantity,
            entry_price=trade.entry_price,
            exit_price=exit_price,
            profit=profit,
            status="closed",
        )

        self.balance += profit
        self._trades[trade_id] = closed_trade

        return closed_trade

    def get_trade(
        self,
        trade_id: str,
    ) -> PaperTrade | None:
        """
        Get a trade by ID.
        """

        return self._trades.get(trade_id)

    def list_trades(self) -> list[PaperTrade]:
        """
        Return all paper trades.
        """

        return list(self._trades.values())

    def open_trades(self) -> list[PaperTrade]:
        """
        Return all open trades.
        """

        return [
            trade
            for trade in self._trades.values()
            if trade.status == "open"
        ]

    def closed_trades(self) -> list[PaperTrade]:
        """
        Return all closed trades.
        """

        return [
            trade
            for trade in self._trades.values()
            if trade.status == "closed"
        ]

    def total_profit(self) -> float:
        """
        Return total realized paper-trading profit.
        """

        return self.balance - self.initial_balance

    def equity(
        self,
        current_prices: dict[str, float] | None = None,
    ) -> float:
        """
        Calculate account equity.

        If current prices are provided, unrealized PnL from open trades
        is included.
        """

        if current_prices is None:
            return self.balance

        equity = self.balance

        for trade in self.open_trades():
            if trade.symbol not in current_prices:
                continue

            current_price = current_prices[trade.symbol]

            self._validate_positive("Current price", current_price)

            equity += self._calculate_profit(
                side=trade.side,
                quantity=trade.quantity,
                entry_price=trade.entry_price,
                exit_price=current_price,
            )

        return equity

    def clear(self) -> None:
        """
        Clear all trades and reset balance.
        """

        self._trades.clear()
        self.balance = self.initial_balance

    def _calculate_profit(
        self,
        side: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
    ) -> float:
        """
        Calculate trade profit.
        """

        if side == "buy":
            return (exit_price - entry_price) * quantity

        return (entry_price - exit_price) * quantity

    def _validate_trade_id(
        self,
        trade_id: str,
    ) -> None:
        """
        Validate trade ID.
        """

        if not trade_id:
            raise ValueError("Trade ID cannot be empty.")

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
    "PaperTrade",
    "PaperTradingEngine",
]