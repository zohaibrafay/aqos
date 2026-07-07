"""
Dashboard interface.

Provides an application-facing interface for dashboard-style reads
from AQOS services through standardized interface envelopes.
"""

from __future__ import annotations

from typing import Any

from aqos.interfaces.schemas import InterfaceEnvelope
from aqos.services import (
    BacktestService,
    BrokerService,
    EconomicCalendarService,
    ExperimentService,
    MarketDataService,
    NewsService,
    StorageService,
)


class DashboardInterface:
    """
    Dashboard-facing interface for AQOS.
    """

    def __init__(
        self,
        market_data_service: MarketDataService | None = None,
        backtest_service: BacktestService | None = None,
        experiment_service: ExperimentService | None = None,
        broker_service: BrokerService | None = None,
        news_service: NewsService | None = None,
        economic_calendar_service: EconomicCalendarService | None = None,
        storage_service: StorageService | None = None,
    ) -> None:
        self._market_data_service = market_data_service or MarketDataService()
        self._backtest_service = backtest_service or BacktestService()
        self._experiment_service = experiment_service or ExperimentService()
        self._broker_service = broker_service or BrokerService()
        self._news_service = news_service or NewsService()
        self._economic_calendar_service = (
            economic_calendar_service or EconomicCalendarService()
        )
        self._storage_service = storage_service or StorageService()

    def health(self) -> InterfaceEnvelope:
        """
        Return dashboard interface health status.
        """

        return self._success(
            message="Dashboard interface is healthy.",
            payload={
                "status": "ok",
            },
        )

    def overview(self) -> InterfaceEnvelope:
        """
        Return dashboard overview counts.
        """

        return self._success(
            message="Dashboard overview retrieved.",
            payload={
                "market_data_feeds": self._market_data_service.count(),
                "backtest_runs": self._backtest_service.count(),
                "experiments": self._experiment_service.count(),
                "orders": self._broker_service.count_orders(),
                "positions": self._broker_service.count_positions(),
                "news_items": self._news_service.count(),
                "economic_events": self._economic_calendar_service.count(),
                "storage_records": self._storage_service.count(),
            },
        )

    def market_data_summary(
        self,
        symbol: str,
        timeframe: str,
    ) -> InterfaceEnvelope:
        """
        Return dashboard market data summary.
        """

        try:
            feed = self._market_data_service.get_feed(
                symbol=symbol,
                timeframe=timeframe,
            )

            if feed is None:
                return self._failure("Market data feed does not exist.")

            latest = self._market_data_service.latest_candle(
                symbol=symbol,
                timeframe=timeframe,
            )

            return self._success(
                message="Market data summary retrieved.",
                payload={
                    "symbol": feed.symbol,
                    "timeframe": feed.timeframe,
                    "source": feed.source,
                    "candles": len(feed.candles),
                    "latest_timestamp": latest.timestamp,
                    "latest_close": latest.close,
                    "metadata": feed.metadata,
                },
            )
        except ValueError as exc:
            return self._failure(str(exc))

    def backtest_summary(
        self,
        name: str,
    ) -> InterfaceEnvelope:
        """
        Return dashboard backtest summary.
        """

        try:
            run = self._backtest_service.get(name)

            if run is None:
                return self._failure("Backtest run does not exist.")

            return self._success(
                message="Backtest summary retrieved.",
                payload={
                    "name": run.name,
                    "initial_balance": run.result.initial_balance,
                    "final_balance": run.result.final_balance,
                    "total_profit": run.result.total_profit,
                    "return_percent": run.result.return_percent,
                    "win_rate": run.result.win_rate,
                    "max_drawdown": run.result.max_drawdown,
                    "total_trades": len(run.result.trades),
                    "metadata": run.metadata,
                },
            )
        except ValueError as exc:
            return self._failure(str(exc))

    def experiment_summary(
        self,
        name: str,
    ) -> InterfaceEnvelope:
        """
        Return dashboard experiment summary.
        """

        try:
            experiment = self._experiment_service.get(name)

            if experiment is None:
                return self._failure("Experiment does not exist.")

            return self._success(
                message="Experiment summary retrieved.",
                payload={
                    "name": experiment.name,
                    "status": experiment.status,
                    "description": experiment.description,
                    "results": experiment.results,
                    "metadata": experiment.metadata,
                },
            )
        except ValueError as exc:
            return self._failure(str(exc))

    def broker_summary(self) -> InterfaceEnvelope:
        """
        Return dashboard broker summary.
        """

        return self._success(
            message="Broker summary retrieved.",
            payload={
                "orders": self._broker_service.count_orders(),
                "positions": self._broker_service.count_positions(),
                "open_orders": len(self._broker_service.open_orders()),
                "filled_orders": len(self._broker_service.filled_orders()),
                "cancelled_orders": len(self._broker_service.cancelled_orders()),
                "open_positions": len(self._broker_service.open_positions()),
                "closed_positions": len(self._broker_service.closed_positions()),
                "realized_profit": self._broker_service.realized_profit(),
            },
        )

    def news_summary(
        self,
        symbol: str | None = None,
    ) -> InterfaceEnvelope:
        """
        Return dashboard news summary.
        """

        try:
            items = (
                self._news_service.filter_by_symbol(symbol)
                if symbol is not None
                else self._news_service.list()
            )

            high_impact_items = [
                item
                for item in items
                if item.impact_score >= 0.7
            ]

            return self._success(
                message="News summary retrieved.",
                payload={
                    "symbol": symbol,
                    "items": len(items),
                    "high_impact_items": len(high_impact_items),
                    "average_impact_score": self._news_service.average_impact_score(
                        symbol=symbol,
                    ),
                },
            )
        except ValueError as exc:
            return self._failure(str(exc))

    def economic_calendar_summary(
        self,
        currency: str | None = None,
    ) -> InterfaceEnvelope:
        """
        Return dashboard economic calendar summary.
        """

        try:
            events = (
                self._economic_calendar_service.filter_by_currency(currency)
                if currency is not None
                else self._economic_calendar_service.list()
            )

            high_impact_events = [
                event
                for event in events
                if event.impact == "high"
            ]

            return self._success(
                message="Economic calendar summary retrieved.",
                payload={
                    "currency": currency.upper() if currency is not None else None,
                    "events": len(events),
                    "high_impact_events": len(high_impact_events),
                },
            )
        except ValueError as exc:
            return self._failure(str(exc))

    def storage_summary(self) -> InterfaceEnvelope:
        """
        Return dashboard storage summary.
        """

        return self._success(
            message="Storage summary retrieved.",
            payload={
                "records": self._storage_service.count(),
                "namespaces": self._storage_service.list_namespaces(),
            },
        )

    def _success(
        self,
        message: str,
        payload: dict[str, Any] | None = None,
    ) -> InterfaceEnvelope:
        """
        Build success envelope.
        """

        return InterfaceEnvelope(
            success=True,
            message=message,
            payload=payload or {},
            metadata={},
        )

    def _failure(
        self,
        message: str,
    ) -> InterfaceEnvelope:
        """
        Build failure envelope.
        """

        return InterfaceEnvelope(
            success=False,
            message=message,
            payload={},
            metadata={},
        )


__all__ = [
    "DashboardInterface",
]