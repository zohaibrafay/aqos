"""
Data agent.

Provides agent-level workflows for market data availability,
OHLCV preparation, data summaries, and data quality checks.
"""

from __future__ import annotations

from typing import Any

from aqos.agents.base import (
    AgentBase,
    AgentResult,
    AgentTask,
)
from aqos.services import MarketDataService


class DataAgent(AgentBase):
    """
    Agent responsible for data-related workflows.
    """

    SUPPORTED_ACTIONS = {
        "health",
        "availability",
        "summary",
        "latest-candle",
        "close-prices",
        "prepare-ohlcv",
        "quality-check",
    }

    def __init__(
        self,
        market_data_service: MarketDataService | None = None,
    ) -> None:
        self._market_data_service = market_data_service or MarketDataService()

    @property
    def name(self) -> str:
        """
        Return agent name.
        """

        return "data-agent"

    @property
    def description(self) -> str:
        """
        Return agent description.
        """

        return "Agent for market data availability, preparation, and quality checks."

    def run(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a data agent task.
        """

        self.validate_task(task)

        if task.action == "health":
            return self.health(task)

        if task.action == "availability":
            return self.availability(task)

        if task.action == "summary":
            return self.summary(task)

        if task.action == "latest-candle":
            return self.latest_candle(task)

        if task.action == "close-prices":
            return self.close_prices(task)

        if task.action == "prepare-ohlcv":
            return self.prepare_ohlcv(task)

        if task.action == "quality-check":
            return self.quality_check(task)

        return self.failure(
            message=f"Unhandled data agent action: {task.action}",
            metadata=task.metadata,
        )

    def health(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return data agent health.
        """

        return self.success(
            message="Data agent is healthy.",
            data={
                "status": "ok",
                "feeds": self._market_data_service.count(),
            },
            metadata=task.metadata,
        )

    def availability(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Check whether market data is available.
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

        available = self._market_data_service.exists(
            symbol=symbol,
            timeframe=timeframe,
        )

        return self.success(
            message="Data availability checked.",
            data={
                "symbol": symbol.upper(),
                "timeframe": timeframe.upper(),
                "available": available,
            },
            metadata=task.metadata,
        )

    def summary(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return market data summary.
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
            message="Data summary retrieved.",
            data={
                "symbol": feed.symbol,
                "timeframe": feed.timeframe,
                "source": feed.source,
                "candles": len(feed.candles),
                "latest_timestamp": latest.timestamp,
                "latest_close": latest.close,
                "metadata": feed.metadata,
            },
            metadata=task.metadata,
        )

    def latest_candle(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return latest candle.
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

        try:
            candle = self._market_data_service.latest_candle(
                symbol=symbol,
                timeframe=timeframe,
            )

            return self.success(
                message="Latest candle retrieved.",
                data={
                    "timestamp": candle.timestamp,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def close_prices(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Return close prices.
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
        limit = task.payload.get("limit")

        if limit is not None:
            self._validate_limit(int(limit))

        try:
            prices = self._market_data_service.close_prices(
                symbol=symbol,
                timeframe=timeframe,
            )

            if limit is not None:
                prices = prices[-int(limit):]

            return self.success(
                message="Close prices retrieved.",
                data={
                    "symbol": symbol.upper(),
                    "timeframe": timeframe.upper(),
                    "close_prices": prices,
                    "count": len(prices),
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def prepare_ohlcv(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Prepare OHLCV records for downstream agents.
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
        limit = task.payload.get("limit")

        if limit is not None:
            self._validate_limit(int(limit))

        try:
            dataframe = self._market_data_service.to_dataframe(
                symbol=symbol,
                timeframe=timeframe,
            )

            if limit is not None:
                dataframe = dataframe.tail(int(limit)).reset_index(drop=True)

            return self.success(
                message="OHLCV data prepared.",
                data={
                    "symbol": symbol.upper(),
                    "timeframe": timeframe.upper(),
                    "records": dataframe.to_dict(orient="records"),
                    "rows": len(dataframe),
                    "columns": list(dataframe.columns),
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def quality_check(
        self,
        task: AgentTask,
    ) -> AgentResult:
        """
        Run a basic OHLCV data quality check.
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

        try:
            dataframe = self._market_data_service.to_dataframe(
                symbol=symbol,
                timeframe=timeframe,
            )

            required_columns = {
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            }

            missing_columns = sorted(
                required_columns.difference(dataframe.columns)
            )
            missing_values = int(dataframe.isna().sum().sum())
            duplicate_timestamps = int(
                dataframe["timestamp"].duplicated().sum()
            )

            invalid_price_rows = int(
                (
                    (dataframe["open"] <= 0)
                    | (dataframe["high"] <= 0)
                    | (dataframe["low"] <= 0)
                    | (dataframe["close"] <= 0)
                ).sum()
            )

            invalid_volume_rows = int(
                (dataframe["volume"] < 0).sum()
            )

            issues = []

            if missing_columns:
                issues.append("missing_columns")

            if missing_values > 0:
                issues.append("missing_values")

            if duplicate_timestamps > 0:
                issues.append("duplicate_timestamps")

            if invalid_price_rows > 0:
                issues.append("invalid_price_rows")

            if invalid_volume_rows > 0:
                issues.append("invalid_volume_rows")

            return self.success(
                message="Data quality check completed.",
                data={
                    "symbol": symbol.upper(),
                    "timeframe": timeframe.upper(),
                    "valid": not issues,
                    "rows": len(dataframe),
                    "columns": list(dataframe.columns),
                    "missing_columns": missing_columns,
                    "missing_values": missing_values,
                    "duplicate_timestamps": duplicate_timestamps,
                    "invalid_price_rows": invalid_price_rows,
                    "invalid_volume_rows": invalid_volume_rows,
                    "issues": issues,
                },
                metadata=task.metadata,
            )
        except ValueError as exc:
            return self.failure(
                message=str(exc),
                metadata=task.metadata,
            )

    def _validate_limit(
        self,
        limit: int,
    ) -> None:
        """
        Validate record limit.
        """

        if limit <= 0:
            raise ValueError("Limit must be greater than zero.")


__all__ = [
    "DataAgent",
]