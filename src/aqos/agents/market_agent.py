"""
Market agent.

Provides agent-level workflows for market snapshots, trend analysis,
regime summaries, news context, economic calendar context, and market state.
"""

from __future__ import annotations

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)
from aqos.services import (
    EconomicCalendarService,
    MarketDataService,
    NewsService,
)


class MarketAgent(AgentBase):
    """
    Agent responsible for market analysis workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "snapshot",
        "trend-summary",
        "regime-summary",
        "news-context",
        "calendar-context",
        "market-state",
    }

    def __init__(
        self,
        market_data_service: MarketDataService | None = None,
        news_service: NewsService | None = None,
        economic_calendar_service: EconomicCalendarService | None = None,
    ) -> None:
        self._market_data_service = market_data_service or MarketDataService()
        self._news_service = news_service or NewsService()
        self._economic_calendar_service = (
            economic_calendar_service or EconomicCalendarService()
        )

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "market-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for market snapshots, trend, regime, news, and calendar context."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a market agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "snapshot":
            return self.snapshot(task)

        if task.action == "trend-summary":
            return self.trend_summary(task)

        if task.action == "regime-summary":
            return self.regime_summary(task)

        if task.action == "news-context":
            return self.news_context(task)

        if task.action == "calendar-context":
            return self.calendar_context(task)

        if task.action == "market-state":
            return self.market_state(task)

        return self.failure(
            message=f"Unhandled market agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return market agent health.
        """

        return self.success(
            message="Market agent is healthy.",
            data={
                "status": "ok",
                "market_data_feeds": self._market_data_service.count(),
                "news_items": self._news_service.count(),
                "economic_events": self._economic_calendar_service.count(),
            },
            metadata=task.metadata,
        )

    def snapshot(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return latest market snapshot.
        """

        symbol, timeframe = self._get_symbol_timeframe(task)

        try:
            feed = self._market_data_service.get_feed(
                symbol=symbol,
                timeframe=timeframe,
            )

            if feed is None:
                return self.failure(
                    message="Market data feed does not exist.",
                    metadata=task.metadata,
                )

            latest = self._market_data_service.latest_candle(
                symbol=symbol,
                timeframe=timeframe,
            )

            return self.success(
                message="Market snapshot retrieved.",
                data={
                    "symbol": feed.symbol,
                    "timeframe": feed.timeframe,
                    "source": feed.source,
                    "candles": len(feed.candles),
                    "timestamp": latest.timestamp,
                    "open": latest.open,
                    "high": latest.high,
                    "low": latest.low,
                    "close": latest.close,
                    "volume": latest.volume,
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def trend_summary(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return trend summary from close prices.
        """

        symbol, timeframe = self._get_symbol_timeframe(task)

        try:
            close_prices = self._market_data_service.close_prices(
                symbol=symbol,
                timeframe=timeframe,
            )

            analysis = self._analyze_close_prices(close_prices)

            return self.success(
                message="Trend summary generated.",
                data={
                    "symbol": symbol.upper(),
                    "timeframe": timeframe.upper(),
                    **analysis,
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def regime_summary(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return market regime summary.
        """

        symbol, timeframe = self._get_symbol_timeframe(task)

        try:
            close_prices = self._market_data_service.close_prices(
                symbol=symbol,
                timeframe=timeframe,
            )

            analysis = self._analyze_close_prices(close_prices)
            regime = self._classify_regime(
                trend=analysis["trend"],
                change_percent=analysis["change_percent"],
            )

            return self.success(
                message="Market regime summary generated.",
                data={
                    "symbol": symbol.upper(),
                    "timeframe": timeframe.upper(),
                    "regime": regime,
                    "trend": analysis["trend"],
                    "first_close": analysis["first_close"],
                    "last_close": analysis["last_close"],
                    "change": analysis["change"],
                    "change_percent": analysis["change_percent"],
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def news_context(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return news context for a symbol.
        """

        symbol = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="symbol",
            )
        )

        try:
            items = self._news_service.filter_by_symbol(symbol)

            sentiment_counts = {
                "positive": 0,
                "negative": 0,
                "neutral": 0,
            }

            high_impact_items = 0

            for item in items:
                sentiment_counts[item.sentiment] += 1

                if item.impact_score >= 0.7:
                    high_impact_items += 1

            return self.success(
                message="News context generated.",
                data={
                    "symbol": symbol.upper(),
                    "items": len(items),
                    "sentiment_counts": sentiment_counts,
                    "high_impact_items": high_impact_items,
                    "average_impact_score": self._news_service.average_impact_score(
                        symbol=symbol,
                    ),
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def calendar_context(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return economic calendar context for a currency.
        """

        currency = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="currency",
            )
        )

        try:
            events = self._economic_calendar_service.filter_by_currency(currency)

            high_impact_events = [
                event
                for event in events
                if event.impact == "high"
            ]

            return self.success(
                message="Economic calendar context generated.",
                data={
                    "currency": currency.upper(),
                    "events": len(events),
                    "high_impact_events": len(high_impact_events),
                    "event_titles": [
                        event.title
                        for event in events
                    ],
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def market_state(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Build a market state payload for downstream agents.
        """

        symbol, timeframe = self._get_symbol_timeframe(task)

        try:
            latest = self._market_data_service.latest_candle(
                symbol=symbol,
                timeframe=timeframe,
            )
            close_prices = self._market_data_service.close_prices(
                symbol=symbol,
                timeframe=timeframe,
            )

            analysis = self._analyze_close_prices(close_prices)
            regime = self._classify_regime(
                trend=analysis["trend"],
                change_percent=analysis["change_percent"],
            )

            news_items = self._news_service.filter_by_symbol(symbol)

            return self.success(
                message="Market state generated.",
                data={
                    "symbol": symbol.upper(),
                    "timeframe": timeframe.upper(),
                    "timestamp": latest.timestamp,
                    "open": latest.open,
                    "high": latest.high,
                    "low": latest.low,
                    "close": latest.close,
                    "volume": latest.volume,
                    "trend": analysis["trend"],
                    "regime": regime,
                    "change": analysis["change"],
                    "change_percent": analysis["change_percent"],
                    "news_items": len(news_items),
                    "average_news_impact": self._news_service.average_impact_score(
                        symbol=symbol,
                    ),
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def _get_symbol_timeframe(
        self,
        task: AgentTask,
    ) -> tuple[str, str]:
        """
        Get symbol and timeframe from task payload.
        """

        symbol = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="symbol",
            )
        )
        timeframe = str(
            self.get_required_payload_value(
                payload=task.payload,
                key="timeframe",
            )
        )

        return symbol, timeframe

    def _analyze_close_prices(
        self,
        close_prices: list[float],
    ) -> dict[str, float | str | int]:
        """
        Analyze close prices.
        """

        if not close_prices:
            raise ValueError("Close prices cannot be empty.")

        first_close = float(close_prices[0])
        last_close = float(close_prices[-1])
        change = last_close - first_close

        change_percent = 0.0

        if first_close != 0:
            change_percent = (change / first_close) * 100

        if change > 0:
            trend = "uptrend"
        elif change < 0:
            trend = "downtrend"
        else:
            trend = "sideways"

        return {
            "trend": trend,
            "first_close": first_close,
            "last_close": last_close,
            "change": change,
            "change_percent": change_percent,
            "prices": len(close_prices),
        }

    def _classify_regime(
        self,
        trend: str,
        change_percent: float,
    ) -> str:
        """
        Classify market regime.
        """

        if trend == "uptrend" and change_percent >= 0:
            return "bullish"

        if trend == "downtrend" and change_percent <= 0:
            return "bearish"

        return "neutral"


__all__ = [
    "MarketAgent",
]