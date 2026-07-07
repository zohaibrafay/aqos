"""
API interface.

Provides an application-facing interface for API-style access to AQOS.
This layer wraps service calls and returns standardized interface envelopes.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pandas as pd

from aqos.interfaces.risk import RiskInterface
from aqos.interfaces.schemas import (
    BacktestRequest,
    ExperimentRequest,
    InterfaceEnvelope,
    MarketDataRequest,
    PredictionRequest,
    RiskRequest,
    StrategyRequest,
)
from aqos.services import (
    BacktestService,
    DataService,
    ExperimentService,
    MarketDataService,
    ModelService,
    StrategyService,
)


class APIInterface:
    """
    API-facing interface for AQOS.
    """

    def __init__(
        self,
        data_service: DataService | None = None,
        market_data_service: MarketDataService | None = None,
        model_service: ModelService | None = None,
        strategy_service: StrategyService | None = None,
        backtest_service: BacktestService | None = None,
        experiment_service: ExperimentService | None = None,
        risk_manager: RiskInterface | None = None,
    ) -> None:
        self._data_service = data_service or DataService()
        self._market_data_service = market_data_service or MarketDataService()
        self._model_service = model_service or ModelService()
        self._strategy_service = strategy_service or StrategyService()
        self._backtest_service = backtest_service or BacktestService()
        self._experiment_service = experiment_service or ExperimentService()
        self._risk_manager = risk_manager

    def health(self) -> InterfaceEnvelope:
        """
        Return API interface health status.
        """

        return self._success(
            message="API interface is healthy.",
            payload={
                "status": "ok",
            },
        )

    def get_market_data(
        self,
        request: MarketDataRequest,
    ) -> InterfaceEnvelope:
        """
        Get market data from MarketDataService.
        """

        self._validate_request(request, MarketDataRequest)

        try:
            dataframe = self._market_data_service.to_dataframe(
                symbol=request.symbol,
                timeframe=request.timeframe,
            )

            if request.limit is not None:
                dataframe = dataframe.tail(request.limit)
                dataframe = dataframe.reset_index(drop=True)

            return self._success(
                message="Market data retrieved.",
                payload={
                    "symbol": request.symbol,
                    "timeframe": request.timeframe,
                    "records": dataframe.to_dict(orient="records"),
                },
                metadata=request.metadata,
            )
        except ValueError as exc:
            return self._failure(str(exc), request.metadata)

    def run_prediction(
        self,
        request: PredictionRequest,
    ) -> InterfaceEnvelope:
        """
        Run model prediction.
        """

        self._validate_request(request, PredictionRequest)

        try:
            features = pd.DataFrame(request.features)

            prediction = self._model_service.predict(
                name=request.model_name,
                features=features,
            )

            return self._success(
                message="Prediction completed.",
                payload=asdict(prediction),
                metadata=request.metadata,
            )
        except ValueError as exc:
            return self._failure(str(exc), request.metadata)

    def generate_strategy_decision(
        self,
        request: StrategyRequest,
    ) -> InterfaceEnvelope:
        """
        Generate a strategy decision.
        """

        self._validate_request(request, StrategyRequest)

        try:
            market_state = request.market_state

            regime = self._get_required_value(
                data=market_state,
                key="regime",
            )
            trend = self._get_required_value(
                data=market_state,
                key="trend",
            )
            entry_price = market_state.get("entry_price")

            decision = self._strategy_service.decide(
                regime=str(regime),
                trend=str(trend),
                entry_price=entry_price,
                metadata=request.metadata,
            )

            return self._success(
                message="Strategy decision generated.",
                payload=asdict(decision),
                metadata=request.metadata,
            )
        except ValueError as exc:
            return self._failure(str(exc), request.metadata)

    def assess_risk(
        self,
        request: RiskRequest,
    ) -> InterfaceEnvelope:
        """
        Assess risk through an injected RiskInterface implementation.
        """

        self._validate_request(request, RiskRequest)

        if self._risk_manager is None:
            return self._failure(
                message="Risk manager is not configured.",
                metadata=request.metadata,
            )

        try:
            decision = self._risk_manager.assess(
                trade_request=request.trade_request,
                metadata=request.metadata,
            )

            return self._success(
                message="Risk assessment completed.",
                payload=asdict(decision),
                metadata=request.metadata,
            )
        except ValueError as exc:
            return self._failure(str(exc), request.metadata)

    def run_backtest(
        self,
        request: BacktestRequest,
    ) -> InterfaceEnvelope:
        """
        Run a backtest.
        """

        self._validate_request(request, BacktestRequest)

        try:
            run = self._backtest_service.run(
                name=request.name,
                profits=request.profits,
                initial_balance=request.initial_balance,
                metadata=request.metadata,
            )

            return self._success(
                message="Backtest completed.",
                payload={
                    "name": run.name,
                    "initial_balance": run.result.initial_balance,
                    "final_balance": run.result.final_balance,
                    "total_profit": run.result.total_profit,
                    "return_percent": run.result.return_percent,
                    "win_rate": run.result.win_rate,
                    "max_drawdown": run.result.max_drawdown,
                    "metadata": run.metadata,
                },
                metadata=request.metadata,
            )
        except ValueError as exc:
            return self._failure(str(exc), request.metadata)

    def create_experiment(
        self,
        request: ExperimentRequest,
    ) -> InterfaceEnvelope:
        """
        Create an experiment.
        """

        self._validate_request(request, ExperimentRequest)

        try:
            experiment = self._experiment_service.create(
                name=request.name,
                description=request.description,
                metadata=request.metadata,
            )

            return self._success(
                message="Experiment created.",
                payload=asdict(experiment),
                metadata=request.metadata,
            )
        except ValueError as exc:
            return self._failure(str(exc), request.metadata)

    def _success(
        self,
        message: str,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> InterfaceEnvelope:
        """
        Build success envelope.
        """

        return InterfaceEnvelope(
            success=True,
            message=message,
            payload=payload or {},
            metadata=metadata or {},
        )

    def _failure(
        self,
        message: str,
        metadata: dict[str, Any] | None = None,
    ) -> InterfaceEnvelope:
        """
        Build failure envelope.
        """

        return InterfaceEnvelope(
            success=False,
            message=message,
            payload={},
            metadata=metadata or {},
        )

    def _validate_request(
        self,
        request: Any,
        expected_type: type,
    ) -> None:
        """
        Validate request type.
        """

        if not isinstance(request, expected_type):
            raise TypeError(
                f"Request must be {expected_type.__name__}."
            )

    def _get_required_value(
        self,
        data: dict[str, Any],
        key: str,
    ) -> Any:
        """
        Get required value from dictionary.
        """

        if key not in data:
            raise ValueError(f"Missing required key: {key}")

        return data[key]


__all__ = [
    "APIInterface",
]