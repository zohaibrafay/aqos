"""
CLI interface.

Provides an application-facing interface for command-line style access
to AQOS through standardized interface envelopes.
"""

from __future__ import annotations

from typing import Any

from aqos.interfaces.api_interface import APIInterface
from aqos.interfaces.schemas import (
    BacktestRequest,
    ExperimentRequest,
    InterfaceEnvelope,
    MarketDataRequest,
    PredictionRequest,
    RiskRequest,
    StrategyRequest,
)


class CLIInterface:
    """
    CLI-facing interface for AQOS.
    """

    SUPPORTED_COMMANDS = {
        "health",
        "market-data",
        "predict",
        "strategy",
        "risk",
        "backtest",
        "experiment-create",
    }

    def __init__(
        self,
        api_interface: APIInterface | None = None,
    ) -> None:
        self._api_interface = api_interface or APIInterface()

    def execute(
        self,
        command: str,
        arguments: dict[str, Any] | None = None,
    ) -> InterfaceEnvelope:
        """
        Execute a CLI-style command.
        """

        try:
            normalized_command = self._normalize_command(command)
            arguments = arguments or {}

            if normalized_command not in self.SUPPORTED_COMMANDS:
                return self._failure(
                    message=f"Unsupported CLI command: {normalized_command}"
                )

            if normalized_command == "health":
                return self.health()

            if normalized_command == "market-data":
                return self.market_data(arguments)

            if normalized_command == "predict":
                return self.predict(arguments)

            if normalized_command == "strategy":
                return self.strategy(arguments)

            if normalized_command == "risk":
                return self.risk(arguments)

            if normalized_command == "backtest":
                return self.backtest(arguments)

            if normalized_command == "experiment-create":
                return self.create_experiment(arguments)

            return self._failure(
                message=f"Unsupported CLI command: {normalized_command}"
            )
        except (TypeError, ValueError) as exc:
            return self._failure(str(exc))

    def health(self) -> InterfaceEnvelope:
        """
        Run health command.
        """

        return self._api_interface.health()

    def market_data(
        self,
        arguments: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run market-data command.
        """

        request = MarketDataRequest(
            symbol=arguments.get("symbol", ""),
            timeframe=arguments.get("timeframe", ""),
            limit=arguments.get("limit"),
            metadata=arguments.get("metadata", {}),
        )

        return self._api_interface.get_market_data(request)

    def predict(
        self,
        arguments: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run predict command.
        """

        request = PredictionRequest(
            model_name=arguments.get("model_name", ""),
            features=arguments.get("features", []),
            metadata=arguments.get("metadata", {}),
        )

        return self._api_interface.run_prediction(request)

    def strategy(
        self,
        arguments: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run strategy command.
        """

        request = StrategyRequest(
            market_state=arguments.get("market_state", {}),
            metadata=arguments.get("metadata", {}),
        )

        return self._api_interface.generate_strategy_decision(request)

    def risk(
        self,
        arguments: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run risk command.
        """

        request = RiskRequest(
            trade_request=arguments.get("trade_request", {}),
            metadata=arguments.get("metadata", {}),
        )

        return self._api_interface.assess_risk(request)

    def backtest(
        self,
        arguments: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run backtest command.
        """

        request = BacktestRequest(
            name=arguments.get("name", ""),
            profits=arguments.get("profits", []),
            initial_balance=arguments.get("initial_balance", 0),
            metadata=arguments.get("metadata", {}),
        )

        return self._api_interface.run_backtest(request)

    def create_experiment(
        self,
        arguments: dict[str, Any],
    ) -> InterfaceEnvelope:
        """
        Run experiment-create command.
        """

        request = ExperimentRequest(
            name=arguments.get("name", ""),
            description=arguments.get("description", ""),
            metadata=arguments.get("metadata", {}),
        )

        return self._api_interface.create_experiment(request)

    def available_commands(self) -> list[str]:
        """
        Return supported CLI commands.
        """

        return sorted(self.SUPPORTED_COMMANDS)

    def _normalize_command(
        self,
        command: str,
    ) -> str:
        """
        Normalize CLI command.
        """

        if not isinstance(command, str):
            raise TypeError("CLI command must be a string.")

        if not command:
            raise ValueError("CLI command cannot be empty.")

        return command.lower().strip().replace("_", "-")

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
    "CLIInterface",
]